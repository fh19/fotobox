"""The engine: wires the pure state machine to hardware, database and WebSocket.

The state machine decides *what* the state is; the engine performs the side
effects a transition implies — triggering the DSLR, running the pipeline,
submitting a print job — and builds the full status object broadcast on every
change.

Write order on capture is fixed (CLAUDE.md rule 3, docs/datenmodell.md):
original file + DB row first, pipeline afterwards. A pipeline failure never
loses the original.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import shutil
import sqlite3
import threading
from datetime import timedelta
from pathlib import Path

from app import db
from app.backgrounds import BackgroundRegistry
from app.broadcaster import Broadcaster
from app.clock import Clock
from app.config import Config, save_config
from app.hardware.base import Backends
from app.hardware.factory import CameraManager
from app.pipeline import PipelineError, PipelineOutputs, detect_orientation, run_pipeline
from app.state_machine import ActionRejected, StateMachine
from app.states import State

log = logging.getLogger("fotobox.engine")

# Name of the resettable running total in the counters table.
PRINTS_TOTAL = "prints_total"

# Why the printer cannot print, in German (docs/ui-screens.md). "nicht verfügbar"
# alone left whoever ran the party guessing between paper, ribbon and an open lid.
PRINTER_REASON_TEXT = {
    "media_empty": "Kein Papier",
    "ribbon_empty": "Farbband verbraucht",
    "jam": "Papierstau",
    "cover_open": "Klappe offen",
    "offline": "Drucker nicht erreichbar",
    "stopped": "Warteschlange angehalten",
}


class NotFound(Exception):
    """A referenced resource does not exist (maps to HTTP 404)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _printer_message(printer) -> str | None:
    """German reason why printing is impossible, or None when all is well.

    Mock printers have no ``reason()``; they simply never explain themselves.
    """
    reason = getattr(printer, "reason", None)
    if not callable(reason):
        return None
    return PRINTER_REASON_TEXT.get(reason() or "")


def _camera_json(camera) -> dict | None:
    if camera is None:
        return None
    return {"id": camera.id, "model": camera.model, "port": camera.port}


def _preview_json(preview) -> dict | None:
    if preview is None:
        return None
    return {
        "id": preview.id,
        "name": preview.name,
        "device": preview.device,
        "backend": preview.backend,
    }


def _idle_rerender() -> dict:
    """Fresh progress record for re-running the pipeline over an old event."""
    return {
        "running": False,
        "finished": False,
        "done": 0,
        "failed": 0,
        "total": 0,
        "event": None,
        "error": None,
    }


def _idle_export() -> dict:
    """Fresh USB-export progress record (M7b)."""
    return {
        "running": False,
        "finished": False,
        "done": 0,
        "total": 0,
        "bytes": 0,
        "event": None,
        "target": None,
        "error": None,
    }


class Engine:
    def __init__(
        self,
        config: Config,
        clock: Clock,
        conn: sqlite3.Connection,
        backends: Backends,
        broadcaster: Broadcaster,
        camera_manager: CameraManager | None = None,
        config_path: Path | None = None,
    ) -> None:
        self.config = config
        self.clock = clock
        self.conn = conn
        self.backends = backends
        self.broadcaster = broadcaster
        self.camera_manager = camera_manager
        self.config_path = config_path
        self.backgrounds = BackgroundRegistry(config)
        self.sm = StateMachine(config, clock, self._on_sm_emit)
        self._outbox: list[dict] = []
        self._flush_lock = asyncio.Lock()
        self.active_event = db.ensure_active_event(
            conn, config.runtime.default_event_name, clock.now()
        )
        self._ensure_event_dirs()
        # Progress of a running USB export (M7b), polled via GET /api/admin/export/usb.
        self._export = _idle_export()
        # Pre-capture flash phase: when set, the shutter fires once now >= this.
        self._capture_ready_at = None
        # Throttled availability watch → push status when camera/printer come or go.
        self._avail_check_at = None
        # First moment the box was seen without a network; the guest AP opens on
        # its own once this is older than access_point.auto_grace_seconds.
        self._offline_since = None
        # Shuffled photo URLs for the slideshow; refilled on entering SCREENSAVER.
        self._screensaver_photos: list[str] = []
        # Progress of a running re-render, polled via GET /api/admin/rerender.
        self._rerender = _idle_rerender()
        self._last_avail = None
        self._printer_resume_at = None

    # --- message plumbing ---------------------------------------------------

    def _on_sm_emit(self, event_type: str, payload: dict) -> None:
        if event_type == "state_changed":
            if self.sm.state == State.CAPTURE:
                self._capture_ready_at = None  # start a fresh flash phase
            if self.sm.state == State.SCREENSAVER:
                self._shuffle_screensaver()
            else:
                self._screensaver_photos = []
            self._queue("state_changed", self.build_status())
            if self.sm.state == State.ERROR and self.sm.error is not None:
                self._queue(
                    "error",
                    {"code": self.sm.error.code, "message": self.sm.error.message},
                )
        elif event_type == "countdown_tick":
            self._queue("countdown_tick", payload)

    def _queue(self, message_type: str, payload: dict) -> None:
        self._outbox.append(
            {"type": message_type, "payload": payload, "ts": self.clock.now().isoformat()}
        )

    async def flush(self) -> None:
        async with self._flush_lock:
            pending, self._outbox = self._outbox, []
            for message in pending:
                await self.broadcaster.broadcast(message)

    # --- client operations (called by the REST layer) -----------------------

    def start(self) -> None:
        if self._storage_status()["blocked"]:
            raise ActionRejected("storage_full", "Der Speicher ist voll")
        default = self._default_background()
        self.sm.start(
            background_id=default.id if default else None,
            background_mode=default.mode if default else None,
        )
        self._drive()

    def _default_background(self):
        """What a session uses when the guests are not asked (M-extra).

        ``ui.default_background: auto`` means "the frame, if this box has one" —
        so uploading a frame is enough to get it on every photo, without also
        editing the config. A fixed id still works and wins over the automatism.
        """
        configured = self.config.ui.default_background
        if configured != "auto":
            return self.backgrounds.get(configured)
        return next((bg for bg in self.backgrounds.list() if bg.mode != "none"), None)

    def select_background(self, background_id: str) -> None:
        background = self.backgrounds.get(background_id)
        if background is None:
            raise NotFound("unknown_background", "Dieser Hintergrund ist nicht verfügbar")
        self.sm.select_background(background.id, background.mode)
        self._drive()

    def cancel(self) -> None:
        self.sm.cancel()

    def finish(self) -> None:
        self.sm.finish()

    def request_print(self) -> None:
        if self.sm.state != State.PREVIEW:
            raise ActionRejected("invalid_state", "Keine Vorschau aktiv")
        session = self.sm.session
        assert session is not None
        printing = self.config.printing
        if session.print_count >= printing.max_per_photo:
            raise ActionRejected("print_limit_reached", "Dieses Foto wurde schon gedruckt")
        if not self.backends.printer.available():
            raise ActionRejected("printer_unavailable", "Der Drucker ist gerade nicht bereit")
        if db.count_event_prints(self.conn, self.active_event["id"]) >= printing.max_per_event:
            raise ActionRejected("daily_limit_reached", "Das Druck-Kontingent ist erschöpft")

        self.sm.begin_print()
        self._run_print(session.photo_id)

    def reprint_photo(self, photo_id: int, variant: str = "processed") -> dict:
        """Print a stored photo again, from the gallery, outside any session.

        Wanted after the first event: a guest asks for a copy an hour later and
        there was no way to get one. Independent of the state machine — nothing
        about the running session changes, the sheet just goes to CUPS.

        Guarded by the event quota, not by ``max_per_photo``: that limit exists to
        stop one guest tapping "Drucken" five times on the same preview, while a
        reprint is a deliberate second copy.

        ``variant`` follows what the gallery is showing: printing the framed copy
        while the original is on screen is not what anyone asked for. The original
        has the same 3:2 aspect as the print raster, so CUPS scales it to the page.
        """
        row = db.get_photo_with_event(self.conn, photo_id)
        if row is None:
            raise NotFound("unknown_photo", "Dieses Foto gibt es nicht")
        printing = self.config.printing
        if not printing.enabled:
            raise ActionRejected("printing_disabled", "Drucken ist ausgeschaltet")
        if not self.backends.printer.available():
            message = _printer_message(self.backends.printer)
            raise ActionRejected(
                "printer_unavailable", message or "Der Drucker ist gerade nicht bereit"
            )
        if db.count_event_prints(self.conn, row["event_id"]) >= printing.max_per_event:
            raise ActionRejected(
                "daily_limit_reached", "Das Druckkontingent für heute ist aufgebraucht"
            )

        folder = "originals" if variant == "original" else "prints"
        path = self.config.events_dir / row["event_directory"] / folder / row["filename"]
        if not path.exists():
            raise NotFound("no_printable", "Von diesem Foto gibt es keine Druckfassung")
        try:
            job_id = self.backends.printer.submit(str(path))
        except Exception as exc:
            self._log("error", "printer", "print_failed", str(exc), photo_id)
            raise ActionRejected("print_failed", "Der Druck konnte nicht gestartet werden") from exc

        db.insert_print_job(
            self.conn,
            photo_id=photo_id,
            cups_job_id=job_id,
            requested_at=self.clock.now(),
            status="queued",
        )
        self._log(
            "info", "printer", "reprint", f"Foto {photo_id} nachgedruckt ({folder})", photo_id
        )
        used = db.count_event_prints(self.conn, row["event_id"])
        return {
            "queued": True,
            "photo_id": photo_id,
            "job_id": job_id,
            "quota_used": used,
            "quota_total": printing.max_per_event,
        }

    # --- camera selection (admin) -------------------------------------------

    def list_cameras(self) -> dict:
        """Detected capture/preview devices plus the current selection."""
        manager = self.camera_manager
        if manager is None:
            return {"capture": {"detected": []}, "preview": {"detected": []}}
        cameras, previews = manager.discover()
        camera_cfg = self.config.hardware.camera
        preview_cfg = self.config.hardware.preview
        return {
            "capture": {
                "select": camera_cfg.select,
                "autofocus": camera_cfg.autofocus,
                "selected": _camera_json(manager.selected_camera),
                "detected": [_camera_json(c) for c in cameras],
                "fallback": manager.using_fallback,
            },
            "preview": {
                "backend": preview_cfg.backend,
                "device": preview_cfg.device,
                "selected": _preview_json(manager.selected_preview),
                "detected": [_preview_json(p) for p in previews],
            },
        }

    def reselect_cameras(
        self,
        *,
        camera_select: str | None = None,
        preview_device: str | None = None,
        preview_backend: str | None = None,
    ) -> dict:
        """Change which camera/preview is used. Only in IDLE (no mid-session swap)."""
        manager = self.camera_manager
        if manager is None:
            raise ActionRejected("unavailable", "Kameraauswahl ist nicht verfügbar")
        if self.sm.state != State.IDLE:
            raise ActionRejected("invalid_state", "Kamerawechsel nur im Ruhezustand möglich")

        cameras, previews = manager.discover()
        if camera_select and camera_select != "auto":
            if not any(camera_select in (c.id, c.model, c.port) for c in cameras):
                raise NotFound("unknown_camera", "Diese Kamera wurde nicht erkannt")
        if preview_device and preview_device != "auto" and preview_backend != "mock":
            if not any(preview_device in (p.id, p.device) for p in previews):
                raise NotFound("unknown_preview", "Diese Vorschaukamera wurde nicht erkannt")

        manager.select(
            camera_select=camera_select,
            preview_device=preview_device,
            preview_backend=preview_backend,
        )
        self.backends = manager.backends
        if self.config_path is not None:
            save_config(self.config, self.config_path)
        return self.list_cameras()

    def rescan_cameras(self) -> dict:
        """Look for cameras again — for one plugged in after the box started."""
        manager = self._require_manager()
        found = manager.rescan()
        self.backends = manager.backends
        self._log(
            "info",
            "camera",
            "rescan",
            f"Kamera gefunden: {manager.camera.model()}" if found else "Keine Kamera gefunden",
        )
        return self.list_cameras()

    def reset_cameras(self) -> dict:
        """USB-reset the DSLR and reopen the preview device, then look again.

        Recovers the box from a camera that is on the bus but cannot be claimed
        (``[-53]``) without a reboot — see ``app.hardware.usb_reset``.
        """
        manager = self._require_manager()
        if self.sm.state != State.IDLE:
            raise ActionRejected("invalid_state", "Zurücksetzen nur im Ruhezustand möglich")
        outcome = manager.reset()
        self.backends = manager.backends
        self._log("info", "camera", "reset", f"Kamera zurückgesetzt: {outcome}")
        return {**self.list_cameras(), "reset": outcome}

    def test_shot(self) -> dict:
        """Take a photo that goes nowhere near the event — just to see what fires."""
        result = self._capture_test_photo()
        path = self.test_shot_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(result.jpeg)
        manager = self.camera_manager
        return {
            "model": result.camera_model,
            "width": result.width,
            "height": result.height,
            "fallback": manager.using_fallback if manager is not None else False,
        }

    @property
    def test_shot_path(self) -> Path:
        """Outside the event tree: a test shot is not a photo of the party."""
        return self.config.data_dir / "tmp" / "testshot.jpg"

    def _require_manager(self):
        manager = self.camera_manager
        if manager is None:
            raise ActionRejected("unavailable", "Kameraauswahl ist nicht verfügbar")
        return manager

    def _capture_test_photo(self):
        """Shared shutter release for calibration and test shot (admin, IDLE only).

        Through the same timeout as the guest flow: a camera stuck mid-operation
        held the admin request open for minutes, which looks like a dead box to
        whoever is trying to diagnose it.
        """
        if self.sm.state != State.IDLE:
            raise ActionRejected("invalid_state", "Probefoto nur im Ruhezustand möglich")
        try:
            result = self._capture_with_timeout()
        except Exception as exc:
            self._log("error", "camera", "capture_failed", str(exc))
            if self.camera_manager is not None:
                self.camera_manager.note_capture_failed()
            raise ActionRejected(
                "capture_failed", "Probefoto konnte nicht aufgenommen werden"
            ) from exc
        if self.camera_manager is not None:
            self.camera_manager.note_capture_ok()
        return result

    def calibrate_orientation(self) -> dict:
        """Take a test photo and set portrait/landscape for the whole event.

        One-time auto-calibration (docs/druck-layout.md allows fixing orientation
        once; only per-shot auto-rotation is forbidden). Detected from the photo's
        EXIF-corrected aspect.
        """
        result = self._capture_test_photo()
        orientation = detect_orientation(result.jpeg)
        self.config.printing.orientation = orientation
        if self.config_path is not None:
            save_config(self.config, self.config_path)
        self._log("info", "camera", "calibration", f"Ausrichtung erkannt: {orientation}")
        return {
            "orientation": orientation,
            "width": result.width,
            "height": result.height,
        }

    # --- printer admin ------------------------------------------------------

    def printer_status(self) -> dict:
        printer = self.backends.printer
        return {
            "available": printer.available(),
            "state": str(printer.state()),
            "paused": printer.paused(),
            "message": _printer_message(printer),
            # The quota: reaching it silently withdrew the print button mid-party.
            "quota_used": db.count_event_prints(self.conn, self.active_event["id"]),
            "quota_total": self.config.printing.max_per_event,
            "prints_done_event": db.count_event_prints_done(self.conn, self.active_event["id"]),
            "prints_total": db.get_counter(self.conn, PRINTS_TOTAL),
            "queue_length": printer.queue_length(),
        }

    def printer_resume(self) -> dict:
        self.backends.printer.resume()
        self._log("info", "printer", "resume", "Drucker fortgesetzt")
        return self.printer_status()

    def printer_cancel_all(self) -> dict:
        self.backends.printer.cancel_all()
        self._log("info", "printer", "cancel_all", "Warteschlange geleert")
        return self.printer_status()

    def printer_reset_counter(self) -> dict:
        """Zero the running total. The per-event count comes from print_jobs and
        is not touched — it is history, not a counter."""
        db.reset_counter(self.conn, PRINTS_TOTAL)
        self.conn.commit()
        self._log("info", "printer", "counter_reset", "Druckzähler zurückgesetzt")
        return self.printer_status()

    def reconcile_print_jobs(self) -> int:
        """Ask the printer what became of the still-open jobs and persist it.

        Returns the number of jobs that reached ``done`` in this pass, so the
        caller can tell whether anything changed. Jobs the backend cannot judge
        (``None`` — purged from the CUPS history) stay open and are retried.
        """
        printer = self.backends.printer
        finished = 0
        for row in db.pending_print_jobs(self.conn):
            state = printer.job_state(row["cups_job_id"])
            if state is None or state == "pending":
                continue
            db.update_print_job_status(
                self.conn, job_id=row["id"], status=state, finished_at=self.clock.now()
            )
            if state == "done":
                db.increment_counter(self.conn, PRINTS_TOTAL)
                finished += 1
        if finished or self.conn.in_transaction:
            self.conn.commit()
        return finished

    def printer_test_page(self) -> dict:
        from app.pipeline.testpage import make_test_page

        path = self.config.data_dir / "testpage.jpg"
        make_test_page(self.config).save(path, format="JPEG", quality=95, subsampling=0)
        try:
            job_id = self.backends.printer.submit(str(path))
        except Exception as exc:
            self._log("error", "printer", "test_page_failed", str(exc))
            raise ActionRejected("printer_unavailable", "Testdruck fehlgeschlagen") from exc
        self._log("info", "printer", "test_page", f"Testdruck (Job {job_id})")
        return {"job_id": job_id}

    # --- config / event / system (admin) ------------------------------------

    # Only these sections may be edited at runtime (api-contract).
    _EDITABLE_SECTIONS = ("ui", "countdown", "timeouts", "printing", "screensaver")

    def editable_config(self) -> dict:
        return {
            section: getattr(self.config, section).model_dump(mode="json")
            for section in self._EDITABLE_SECTIONS
        }

    def update_config(self, updates: dict) -> dict:
        """Apply partial updates to the editable sections; validate + persist.

        Takes effect immediately — the state machine reads timeouts/countdown live
        (M7: geänderte Countdown-Dauer wirkt sofort).
        """
        for section, values in updates.items():
            if section not in self._EDITABLE_SECTIONS:
                raise ActionRejected("invalid_key", f"Abschnitt '{section}' ist nicht änderbar")
            target = getattr(self.config, section)
            try:
                for key, value in values.items():
                    setattr(target, key, value)
            except Exception as exc:
                raise ActionRejected(
                    "invalid_value", f"Ungültiger Wert in {section}: {exc}"
                ) from exc
        if self.config_path is not None:
            save_config(self.config, self.config_path)
        return self.editable_config()

    def create_new_event(self, name: str) -> dict:
        name = (name or "").strip()
        if not name:
            raise ActionRejected("invalid_value", "Eventname darf nicht leer sein")
        self.active_event = db.create_event(self.conn, name, self.clock.now())
        self._ensure_event_dirs()
        self._log("info", "system", "event_created", f"Neues Event: {name}")
        return {"id": self.active_event["id"], "name": self.active_event["name"]}

    # --- backgrounds / frames (admin) ---------------------------------------

    # Modes an admin upload can create (``none`` is the built-in first tile).
    _UPLOAD_MODES = {"overlay", "frame", "chroma", "ai"}

    def list_backgrounds_admin(self) -> dict:
        """Every uploaded background (incl. disabled), for the admin list."""
        items = []
        for bg in self.backgrounds.all():
            if bg.id == "none":
                continue
            items.append(
                {
                    "id": bg.id,
                    "name": bg.name,
                    "mode": bg.mode,
                    "enabled": bg.enabled,
                    "sort_order": bg.sort_order,
                    "has_overlay": bg.overlay_path is not None,
                    "has_background": bg.background_path is not None,
                }
            )
        return {"backgrounds": items}

    def add_background(self, name: str, mode: str, sort_order: int, data: bytes) -> dict:
        """Create a background/frame folder from an uploaded image (admin)."""
        import io
        import json
        import re

        from PIL import Image

        name = (name or "").strip()
        if not name:
            raise ActionRejected("invalid_value", "Name darf nicht leer sein")
        if mode not in self._UPLOAD_MODES:
            raise ActionRejected("invalid_value", f"Modus '{mode}' ist nicht erlaubt")

        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "hintergrund"
        target = self.config.backgrounds_dir / slug
        if target.exists():
            raise ActionRejected("exists", "Ein Hintergrund mit diesem Namen existiert schon")

        try:
            image = Image.open(io.BytesIO(data))
            image.load()
        except Exception as exc:
            raise ActionRejected("invalid_image", "Datei ist kein gültiges Bild") from exc

        needs_alpha = mode in ("overlay", "frame")
        if needs_alpha and "A" not in image.getbands():
            raise ActionRejected("no_alpha", "Rahmen/Overlay braucht ein PNG mit Transparenz")

        target.mkdir(parents=True)
        try:
            if needs_alpha:
                image.convert("RGBA").save(target / "overlay.png", format="PNG")
            else:
                image.convert("RGB").save(target / "background.jpg", format="JPEG", quality=95)
            config = {
                "name": name,
                "mode": mode,
                "enabled": True,
                "sort_order": int(sort_order),
            }
            (target / "config.json").write_text(
                json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            shutil.rmtree(target, ignore_errors=True)
            raise

        self._log("info", "system", "background_added", f"Hintergrund '{name}' ({mode})")
        return {"id": slug, "name": name, "mode": mode}

    def delete_background(self, background_id: str) -> dict:
        """Remove an uploaded background folder (admin)."""
        if background_id in ("", "none") or "/" in background_id or "\\" in background_id:
            raise NotFound("unknown_background", "Dieser Hintergrund existiert nicht")
        target = (self.config.backgrounds_dir / background_id).resolve()
        if target.parent != self.config.backgrounds_dir.resolve() or not target.is_dir():
            raise NotFound("unknown_background", "Dieser Hintergrund existiert nicht")
        shutil.rmtree(target)
        self._log("info", "system", "background_deleted", f"Hintergrund '{background_id}' gelöscht")
        return {"ok": True}

    def system_info(self) -> dict:
        from app import system

        return {
            "cpu_temp": system.cpu_temp(),
            "uptime_seconds": system.uptime_seconds(),
            "versions": system.versions(),
            "storage": self._storage_status(),
            "camera": {
                "available": self.backends.camera.available(),
                "model": self.backends.camera.model(),
            },
            "printer": self.printer_status(),
            "event": {
                "id": self.active_event["id"],
                "name": self.active_event["name"],
                "photo_count": db.count_photos(self.conn, self.active_event["id"]),
            },
        }

    def shutdown(self) -> dict:
        from app import system

        self._log("warning", "system", "shutdown", "Herunterfahren angefordert")
        system.poweroff()
        return {"ok": True}

    def reboot(self) -> dict:
        from app import system

        self._log("warning", "system", "reboot", "Neustart angefordert")
        system.reboot()
        return {"ok": True}

    # --- network / export (M7b) ---------------------------------------------

    # --- screensaver --------------------------------------------------------

    def _shuffle_screensaver(self) -> None:
        """Pick the photos for the slideshow, in random order.

        The order is a decision, so it is made here and not in the browser
        (CLAUDE.md rule 5). Only photos whose file actually exists: a failed
        pipeline or a purged photo must not leave a hole in the show.
        """
        settings = self.config.screensaver
        variant = "processed" if settings.variant == "processed" else "originals"
        directory = self.active_event["directory"]
        urls = []
        for photo in db.iter_event_photos(self.conn, self.active_event["id"]):
            path = self._event_variant_path(directory, variant, photo["filename"])
            if path.exists():
                urls.append(f"/api/photos/{photo['id']}/{settings.variant}")
        random.shuffle(urls)
        self._screensaver_photos = urls[: settings.max_photos]

    def wake_from_screensaver(self) -> dict:
        """First touch on the slideshow — back to the start screen, no photo yet."""
        self.sm.wake()
        return self.build_status()

    def network_status(self) -> dict:
        from app import system

        ap = self.config.network.access_point
        active = system.ap_active()
        # In AP mode the box is reachable at its own AP address; otherwise at the
        # DHCP/Ethernet address. The gallery URL is built by the client (it knows
        # its own port) — we only supply the host.
        return {
            "ap_enabled": active,
            "ap_auto": ap.auto_when_offline,
            "ssid": ap.ssid,
            "ip": ap.address if active else system.primary_ip(),
        }

    def set_ap_auto(self, enabled: bool) -> dict:
        """Switch the automatic access point on/off and persist it."""
        self.config.network.access_point.auto_when_offline = enabled
        if self.config_path is not None:
            save_config(self.config, self.config_path)
        self._offline_since = None
        return self.network_status()

    def consider_offline_ap(self) -> bool:
        """Open the guest AP when the box has been without a network for a while.

        At a venue there is no home WiFi to join, and until now somebody had to
        notice that and switch the AP on by hand in the admin. Blocking (nmcli) —
        call off the event loop. Returns True if the AP was switched on.

        Only ever switches *on*. In AP mode wlan0 no longer sees the home
        network, so "is it back?" cannot be answered without dropping every
        guest — that decision stays with the operator.
        """
        from app import system

        ap = self.config.network.access_point
        if not ap.auto_when_offline:
            self._offline_since = None
            return False
        if system.network_connected() or system.ap_active():
            self._offline_since = None
            return False

        now = self.clock.now()
        if self._offline_since is None:
            self._offline_since = now
            return False
        waited = (now - self._offline_since).total_seconds()
        if waited < ap.auto_grace_seconds:
            return False

        self._log(
            "warning",
            "system",
            "ap_auto",
            f"Kein Netzwerk seit {int(waited)}s — Access-Point '{ap.ssid}' wird eingeschaltet",
        )
        self._offline_since = None
        try:
            self.network_ap(True)
        except ActionRejected:
            return False  # already logged; try again on the next round
        return True

    def network_ap(self, enabled: bool) -> dict:
        """Switch the guest access point on/off (M7b). Blocking — call off-thread."""
        from app import system

        ap = self.config.network.access_point
        try:
            if enabled:
                system.ap_enable(
                    ap.ssid, ap.passphrase, ap.channel, ap.address, captive=ap.captive_portal
                )
                self._log("warning", "system", "ap_on", f"Access-Point '{ap.ssid}' an")
            else:
                system.ap_disable()
                self._log("info", "system", "ap_off", "Access-Point aus")
        except Exception as exc:
            self._log("error", "system", "ap_failed", str(exc))
            raise ActionRejected("ap_failed", f"Netzwerkumschaltung fehlgeschlagen: {exc}") from exc
        return self.network_status()

    # --- re-rendering an old event -----------------------------------------

    def start_rerender(self, event_id: int) -> dict:
        """Run the pipeline again over every photo of an event, in the background.

        The processed files are only as good as the pipeline that made them: the
        photos from the first wedding are still 1872x1248 without EXIF, because
        that is what the pipeline did back then. The originals are untouched, so
        the framed copies can simply be made again — with today's resolution and
        with the camera's EXIF carried over.
        """
        if self._rerender["running"]:
            raise ActionRejected("rerender_busy", "Es läuft bereits eine Neuberechnung")
        event = db.get_event(self.conn, event_id)
        if event is None:
            raise ActionRejected("not_found", "Event nicht gefunden")
        photos = db.iter_event_photos(self.conn, event_id)
        self._rerender = _idle_rerender()
        self._rerender.update(running=True, total=len(photos), event=event["name"])
        threading.Thread(
            target=self._run_rerender,
            args=(event_id, event["directory"]),
            daemon=True,
        ).start()
        return {"started": True, "total": len(photos), "event": event["name"]}

    def _run_rerender(self, event_id: int, directory: str) -> None:
        """Own DB connection: this runs in a thread, next to the live session."""
        conn = db.connect(self.config.db_path)
        try:
            for photo in db.iter_event_photos(conn, event_id):
                row = dict(photo)
                row["event_directory"] = directory
                if self._reprocess(conn, row):
                    self._rerender["done"] += 1
                else:
                    self._rerender["failed"] += 1
            self._log(
                "info",
                "pipeline",
                "rerender_done",
                f"{self._rerender['done']} Bilder neu berechnet, "
                f"{self._rerender['failed']} fehlgeschlagen",
            )
        except Exception as exc:  # never let a background thread die silently
            self._rerender["error"] = str(exc)
            self._log("error", "pipeline", "rerender_failed", str(exc))
        finally:
            self._rerender.update(running=False, finished=True)
            conn.close()

    def rerender_status(self) -> dict:
        return dict(self._rerender)

    def start_usb_export(self) -> dict:
        """Copy the full active event to a USB stick in the background (M7b)."""
        from app import system

        if self._export["running"]:
            raise ActionRejected("export_busy", "Ein Export läuft bereits")
        stick = system.find_usb_storage()
        if stick is None:
            raise ActionRejected("no_usb", "Kein USB-Stick gefunden")
        source = self._event_dir()
        files = sorted(p for p in source.rglob("*") if p.is_file())
        self._export = _idle_export()
        self._export.update(running=True, total=len(files), event=self.active_event["name"])
        threading.Thread(
            target=self._run_usb_export,
            args=(stick, files, source),
            daemon=True,
        ).start()
        return {"started": True, "total": len(files), "device": stick["device"]}

    def _run_usb_export(self, stick: dict, files: list[Path], source: Path) -> None:
        from app import system

        try:
            mount = system.mount_usb(stick["device"], stick["fstype"])
            target = mount / f"Fotobox_{self.active_event['directory']}"
            target.mkdir(parents=True, exist_ok=True)
            done = copied_bytes = 0
            for path in files:
                dest = target / path.relative_to(source)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, dest)
                done += 1
                copied_bytes += path.stat().st_size
                self._export.update(done=done, bytes=copied_bytes, target=str(target))
            system.unmount_usb()
            self._export.update(running=False, finished=True)
            self._log("info", "system", "export_usb", f"USB-Export: {done} Dateien kopiert")
        except Exception as exc:
            try:
                system.unmount_usb()
            except Exception:
                pass
            self._export.update(running=False, finished=True, error=str(exc))
            self._log("error", "system", "export_failed", str(exc))

    def export_status(self) -> dict:
        return dict(self._export)

    # --- time-driven progression -------------------------------------------

    def tick(self) -> None:
        """One scheduler tick: advance the clock-driven state, run side effects."""
        self.sm.poll()
        self._drive()
        self._check_availability()

    # --- side effects -------------------------------------------------------

    def _drive(self) -> None:
        """Run side effects for auto-advancing states until the state settles."""
        while True:
            state = self.sm.state
            if state == State.CAPTURE:
                if not self._run_capture():
                    return  # still in the pre-capture flash phase; wait for next tick
            elif state == State.PROCESSING:
                self._run_processing()
            else:
                return

    def _auto_resume_printer(self, now) -> None:
        """Re-enable a queue that CUPS stopped, in case the paper is back.

        Refilling paper does not restart the queue — CUPS keeps it disabled until
        someone runs ``cupsenable``, and its ``printer-state-reasons`` stay stale
        until a job is attempted. Without this the box reported "nicht verfügbar"
        for the rest of the evening even though the printer was ready. If the
        supply really is still empty, the next job stops the queue again and this
        just tries later. ``printer.auto_resume_seconds: 0`` turns it off.
        """
        interval = self.config.hardware.printer.auto_resume_seconds
        printer = self.backends.printer
        if interval <= 0 or not printer.paused():
            self._printer_resume_at = None
            return
        if self._printer_resume_at is None:  # first tick: wait one interval
            self._printer_resume_at = now + timedelta(seconds=interval)
            return
        if now < self._printer_resume_at:
            return
        self._printer_resume_at = now + timedelta(seconds=interval)
        try:
            printer.resume()
        except Exception as exc:
            log.debug("Drucker-Freigabe fehlgeschlagen: %s", exc)
            return
        if not printer.paused():
            self._log("info", "printer", "auto_resume", "Drucker automatisch fortgesetzt")

    def _check_availability(self) -> None:
        """Push a fresh status when camera/printer/preview availability changes.

        state_changed only fires on real state transitions, so without this the
        kiosk would stay on "Kleine Pause" after a camera returns in IDLE. Throttled
        to once a second.
        """
        now = self.clock.now()
        if self._avail_check_at is not None and now < self._avail_check_at:
            return
        self._avail_check_at = now + timedelta(seconds=1)
        # A DSLR that boots slower than the box only shows up on a later discovery.
        if self.camera_manager is not None:
            manager = self.camera_manager
            # A camera that is gone, and a preview source that is gone — both can
            # be replaced by whatever else is attached, without anyone noticing.
            manager.rediscover_if_missing(now)
            manager.repair_preview_if_missing(now)
            # Always re-read: the preview repair finishes on its own thread, so
            # there is no return value to react to.
            self.backends = manager.backends
        self._auto_resume_printer(now)
        current = (
            self.backends.camera.available(),
            self.backends.camera.model(),
            self.backends.printer.available(),
            self.backends.preview.available(),
        )
        if self._last_avail is None:
            self._last_avail = current  # first tick: seed, don't broadcast
            return
        if current != self._last_avail:
            self._last_avail = current
            self._queue("state_changed", self.build_status())

    def _run_capture(self) -> bool:
        """Fire the shutter (return True) or hold the pre-capture flash (False).

        With ``ui.flash_enabled`` the first CAPTURE tick only arms the flash and
        returns; the queued CAPTURE ``state_changed`` then flushes and the screen
        turns white. Once the flash duration has passed, the shutter fires — so the
        DSLR/webcam exposes while the screen is bright (a fill-light "flash").
        """
        ui = self.config.ui
        if ui.flash_enabled and ui.flash_duration_ms > 0:
            now = self.clock.now()
            if self._capture_ready_at is None:
                self._capture_ready_at = now + timedelta(milliseconds=ui.flash_duration_ms)
                return False
            if now < self._capture_ready_at:
                return False
        self._capture_ready_at = None
        session = self.sm.session
        assert session is not None
        try:
            result = self._capture_with_timeout()
        except TimeoutError as exc:  # DSLR did not fire (e.g. focus failure)
            self._log("error", "camera", "camera_timeout", str(exc))
            self._note_capture_failed()
            self.sm.capture_failed("camera_timeout")
            return True
        except Exception as exc:  # camera gone, download failed, ...
            self._log("error", "camera", "capture_failed", str(exc))
            self._note_capture_failed()
            self.sm.capture_failed("capture_failed")
            return True
        if self.camera_manager is not None:
            self.camera_manager.note_capture_ok()

        # Rule 3: original file + DB row before the pipeline runs.
        photo_id = db.insert_photo(
            self.conn,
            event_id=self.active_event["id"],
            captured_at=self.clock.now(),
            background_id=session.background_id,
            background_mode=session.background_mode,
            camera_model=result.camera_model,
            width=result.width,
            height=result.height,
        )
        original_path = self._variant_path("originals", photo_id)
        original_path.parent.mkdir(parents=True, exist_ok=True)
        original_path.write_bytes(result.jpeg)
        self._log("info", "camera", "capture_ok", f"Foto {photo_id} aufgenommen", photo_id)
        self.sm.capture_succeeded(photo_id)
        return True

    def _note_capture_failed(self) -> None:
        """Count the failure and let the manager reset the USB device if it repeats."""
        if self.camera_manager is None:
            return
        if self.camera_manager.note_capture_failed():
            self.backends = self.camera_manager.backends
            self._log("info", "camera", "reset", "Kamera nach wiederholten Fehlern zurückgesetzt")

    def _capture_with_timeout(self):
        """Run the (blocking) DSLR capture with a hard timeout.

        ``capture()`` runs off the event loop in a daemon thread and is joined for
        at most ``camera.capture_timeout_seconds``. If the shutter never fires (a
        focus failure can hang gphoto2 indefinitely), we raise ``TimeoutError`` so
        the state machine recovers to ERROR → IDLE instead of freezing the whole
        box. The orphaned thread is abandoned — Python cannot kill it, and it still
        owns the camera. The next capture therefore fails fast on the camera lock
        instead of hitting ``-53``, and ``usbreset_after_failures`` resets the USB
        device once that has happened often enough (see ``_note_capture_failed``).
        """
        timeout = self.config.hardware.camera.capture_timeout_seconds
        box: dict = {}

        def work() -> None:
            try:
                box["result"] = self.backends.camera.capture()
            except Exception as exc:  # noqa: BLE001 — re-raised on the caller thread
                box["error"] = exc

        thread = threading.Thread(target=work, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            raise TimeoutError(f"Kamera reagierte nicht innerhalb von {timeout:.0f} s")
        if "error" in box:
            raise box["error"]
        return box["result"]

    def _run_processing(self) -> None:
        session = self.sm.session
        assert session is not None and session.photo_id is not None
        photo_id = session.photo_id
        original_path = self._variant_path("originals", photo_id)
        background = self.backgrounds.resolve(session.background_id)
        outputs = PipelineOutputs(
            processed=self._variant_path("processed", photo_id),
            print=self._variant_path("prints", photo_id),
            thumb=self._variant_path("thumbs", photo_id),
        )
        try:
            pipeline_ms = run_pipeline(self.config, background, photo_id, original_path, outputs)
        except PipelineError as exc:
            db.set_pipeline_failed(self.conn, photo_id, str(exc))
            self._log("error", "pipeline", "pipeline_failed", str(exc), photo_id)
            self.sm.processing_failed("pipeline_failed")
            return

        db.set_pipeline_ok(self.conn, photo_id, pipeline_ms)
        self._log("info", "pipeline", "pipeline_ok", f"{pipeline_ms} ms", photo_id)
        self._queue(
            "photo_ready",
            {"photo_id": photo_id, "processed_url": f"/api/photos/{photo_id}/processed"},
        )
        self.sm.processing_succeeded()

    def _run_print(self, photo_id: int | None) -> None:
        assert photo_id is not None
        print_path = self._variant_path("prints", photo_id)
        try:
            job_id = self.backends.printer.submit(str(print_path))
        except Exception as exc:
            self._log("error", "printer", "print_failed", str(exc), photo_id)
            self.sm.print_failed("printer_unavailable")
            return

        db.insert_print_job(
            self.conn,
            photo_id=photo_id,
            cups_job_id=job_id,
            requested_at=self.clock.now(),
            status="queued",
        )
        self._queue("print_started", {"photo_id": photo_id, "job_id": job_id})
        # PRINTING ends the moment the job is handed to CUPS, not when the sheet
        # is done (docs/druck-layout.md): the session must not block.
        self.sm.print_submitted()
        self._queue("print_finished", {"photo_id": photo_id, "job_id": job_id, "success": True})

    # --- status -------------------------------------------------------------

    def build_status(self) -> dict:
        sm = self.sm
        printer = self.backends.printer
        camera = self.backends.camera
        preview = self.backends.preview
        event = self.active_event

        session_payload = None
        if sm.state != State.IDLE and sm.session is not None:
            session = sm.session
            processed_url = (
                f"/api/photos/{session.photo_id}/processed" if session.photo_id else None
            )
            session_payload = {
                "photo_id": session.photo_id,
                "background_id": session.background_id,
                "countdown_remaining": sm.countdown_remaining(),
                "processed_url": processed_url,
                "print_count": session.print_count,
                "print_allowed": self._print_allowed(session.print_count),
                "print_hint": self._print_block(session.print_count),
            }

        status = {
            "state": str(sm.state),
            "session": session_payload,
            "printer": {
                "available": printer.available(),
                "state": str(printer.state()),
                "paused": printer.paused(),
                "message": _printer_message(printer),
            },
            "camera": {
                "available": camera.available(),
                "model": camera.model(),
                # The box keeps shooting with the webcam when the DSLR is gone — but
                # it says so instead of letting the switch pass unnoticed.
                "fallback": self.camera_manager.using_fallback
                if self.camera_manager is not None
                else False,
            },
            "preview": {"available": preview.available()},
            "event": {
                "id": event["id"],
                "name": event["name"],
                "photo_count": db.count_photos(self.conn, event["id"]),
            },
            "storage": self._storage_status(),
        }
        if sm.state == State.SCREENSAVER:
            settings = self.config.screensaver
            status["screensaver"] = {
                "photos": self._screensaver_photos,
                "interval_ms": int(settings.interval_seconds * 1000),
                "fade_ms": settings.fade_ms,
            }
        if sm.state == State.ERROR and sm.error is not None:
            status["error"] = {"code": sm.error.code, "message": sm.error.message}
        return status

    def _print_allowed(self, print_count: int) -> bool:
        return self._print_block(print_count) is None

    def _print_block(self, print_count: int) -> str | None:
        """Why printing is not offered — or None when it is. German, for the guests.

        The button used to just disappear. When the event quota ran out mid-party
        that looked like a broken box and cost a long search; now it says so.
        """
        printing = self.config.printing
        if not printing.enabled:
            return "Drucken ist ausgeschaltet"
        printer_problem = _printer_message(self.backends.printer)
        if not self.backends.printer.available():
            return printer_problem or "Der Drucker ist gerade nicht bereit"
        if print_count >= printing.max_per_photo:
            return "Dieses Foto wurde schon gedruckt"
        if db.count_event_prints(self.conn, self.active_event["id"]) >= printing.max_per_event:
            return "Das Druckkontingent für heute ist aufgebraucht"
        return None

    def _storage_status(self) -> dict:
        usage = shutil.disk_usage(self.config.data_dir)
        used_percent = (usage.used / usage.total) * 100 if usage.total else 0
        return {
            "free_bytes": usage.free,
            "warning": used_percent >= self.config.storage.warn_threshold_percent,
            "blocked": used_percent >= self.config.storage.block_threshold_percent,
        }

    # --- helpers ------------------------------------------------------------

    def _event_dir(self) -> Path:
        return self.config.events_dir / self.active_event["directory"]

    def _variant_path(self, variant: str, photo_id: int) -> Path:
        return self._event_dir() / variant / db.photo_filename(photo_id)

    def photo_variant_path(self, variant_dir: str, photo_id: int) -> Path:
        """Path of a stored photo variant (``originals``/``processed``/...)."""
        return self._variant_path(variant_dir, photo_id)

    def background_thumbnail_path(self, background_id: str) -> Path | None:
        """Return a 400×267 thumbnail path (api-contract), generating it on demand."""
        background = self.backgrounds.get(background_id)
        if background is None or background.directory is None:
            return None  # "Ohne Hintergrund" has no image
        thumbnail = background.directory / "thumbnail.jpg"
        if thumbnail.exists():
            return thumbnail
        source = background.background_path or background.overlay_path
        if source is None:
            return None
        from PIL import Image

        from app.pipeline.geometry import cover_resize

        image = cover_resize(Image.open(source).convert("RGB"), 400, 267)
        image.save(thumbnail, format="JPEG", quality=85)
        return thumbnail

    def _ensure_event_dirs(self) -> None:
        for variant in ("originals", "processed", "prints", "thumbs"):
            (self._event_dir() / variant).mkdir(parents=True, exist_ok=True)

    def _log(
        self,
        level: str,
        component: str,
        code: str,
        message: str,
        photo_id: int | None = None,
    ) -> None:
        db.log_event(
            self.conn,
            now=self.clock.now(),
            level=level,
            component=component,
            code=code,
            message=message,
            photo_id=photo_id,
        )

    def _event_variant_path(self, directory: str, variant: str, filename: str) -> Path:
        return self.config.events_dir / directory / variant / filename

    # Every place a photo leaves a file behind.
    _PHOTO_VARIANTS = ("originals", "processed", "prints", "thumbs", "thumbs_original")

    def original_thumbnail_path(self, photo_id: int) -> Path | None:
        """Thumbnail of the untouched original, made on first request.

        The grid used the processed thumbnail for both views, so switching to
        "Original" still showed the framed copies — the one thing that view is
        for. Generated lazily and kept: the events already on the card were shot
        long before this existed.
        """
        photo = db.get_photo_with_event(self.conn, photo_id)
        if photo is None:
            return None
        directory = photo["event_directory"]
        filename = photo["filename"]
        thumbnail = self._event_variant_path(directory, "thumbs_original", filename)
        if thumbnail.exists():
            return thumbnail
        original = self._event_variant_path(directory, "originals", filename)
        if not original.exists():
            return None

        from PIL import Image, ImageOps

        thumbnail.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(original) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            width = self.config.pipeline.thumbnail_width
            height = max(1, round(image.height * width / image.width))
            image.resize((width, height), Image.LANCZOS).save(thumbnail, format="JPEG", quality=85)
        # Same date as the photo, not "made when someone first scrolled past it".
        try:
            stamp = original.stat()
            os.utime(thumbnail, (stamp.st_atime, stamp.st_mtime))
        except OSError:
            pass
        return thumbnail

    def _photo_files(self, directory: str, filename: str) -> list[Path]:
        return [self._event_variant_path(directory, v, filename) for v in self._PHOTO_VARIANTS]

    def delete_photos(self, photo_ids: list[int]) -> dict:
        """Flag photos as deleted — they leave gallery and counters at once.

        The files stay until the explicit purge below (datenmodell.md).
        """
        ids = [int(pid) for pid in photo_ids]
        if not ids:
            raise ActionRejected("invalid_value", "Keine Fotos ausgewählt")
        count = db.mark_photos_deleted(self.conn, ids)
        self._log("warning", "system", "photos_deleted", f"{count} Foto(s) gelöscht")
        return {"deleted": count, "pending_purge": self.deleted_photo_stats()}

    def deleted_photo_stats(self) -> dict:
        """How much a final purge would actually free."""
        total = 0
        count = 0
        for row in db.deleted_photos_with_event(self.conn):
            sizes = [
                p.stat().st_size
                for p in self._photo_files(row["event_directory"], row["filename"])
                if p.exists()
            ]
            if sizes:
                count += 1
                total += sum(sizes)
        return {"count": count, "bytes": total}

    def purge_deleted_photos(self) -> dict:
        """Remove the files of every flagged photo. Irreversible, hence separate.

        The rows stay: photo ids are also filenames and run across all events, so
        reusing them would be a collision waiting to happen.
        """
        removed = 0
        freed = 0
        for row in db.deleted_photos_with_event(self.conn):
            for path in self._photo_files(row["event_directory"], row["filename"]):
                if not path.exists():
                    continue
                try:
                    freed += path.stat().st_size
                    path.unlink()
                    removed += 1
                except OSError as exc:
                    self._log("error", "system", "purge_failed", f"{path.name}: {exc}")
        self._log("warning", "system", "photos_purged", f"{removed} Datei(en) entfernt")
        return {"purged": removed, "freed_bytes": freed}

    def event_files(
        self, event_id: int, variant: str, photo_ids: set[int] | None = None
    ) -> list[tuple[str, Path]]:
        """(*arcname*, *path*) pairs for a ZIP export of an event's photos.

        ``photo_ids`` limits the export to a selection — asked for after the first
        event, where the only choice was "all 252 photos or one at a time".
        """
        entries: list[tuple[str, Path]] = []
        event = db.get_event(self.conn, event_id)
        if event is None:
            return entries
        directory = event["directory"]
        for photo in db.iter_event_photos(self.conn, event_id):
            if photo_ids is not None and photo["id"] not in photo_ids:
                continue
            filename = photo["filename"]
            if variant in ("original", "both"):
                arc = f"original/{filename}" if variant == "both" else filename
                entries.append((arc, self._event_variant_path(directory, "originals", filename)))
            if variant in ("processed", "both"):
                arc = f"bearbeitet/{filename}" if variant == "both" else filename
                entries.append((arc, self._event_variant_path(directory, "processed", filename)))
        return entries

    def recover_pending_pipelines(self) -> int:
        """Re-run the pipeline for photos left ``pending`` by a crash/restart.

        Uses its own DB connection so it is safe to run in a background thread.
        The original is always present, so a failed re-run only marks the photo.
        """
        conn = db.connect(self.config.db_path)
        try:
            pending = db.pending_pipeline_photos_with_event(conn)
            if not pending:
                return 0
            log.info("Hole %d unfertige Pipeline(s) nach.", len(pending))
            recovered = 0
            for photo in pending:
                if self._reprocess(conn, photo):
                    recovered += 1
            return recovered
        finally:
            conn.close()

    def _reprocess(self, conn: sqlite3.Connection, photo: sqlite3.Row) -> bool:
        photo_id = photo["id"]
        directory = photo["event_directory"]
        filename = photo["filename"]
        original = self._event_variant_path(directory, "originals", filename)
        if not original.exists():
            db.set_pipeline_failed(conn, photo_id, "Original fehlt")
            return False
        outputs = PipelineOutputs(
            processed=self._event_variant_path(directory, "processed", filename),
            print=self._event_variant_path(directory, "prints", filename),
            thumb=self._event_variant_path(directory, "thumbs", filename),
        )
        background = self.backgrounds.resolve(photo["background_id"])
        try:
            pipeline_ms = run_pipeline(self.config, background, photo_id, original, outputs)
        except PipelineError as exc:
            db.set_pipeline_failed(conn, photo_id, str(exc))
            db.log_event(
                conn,
                now=self.clock.now(),
                level="error",
                component="pipeline",
                code="pipeline_failed",
                message=str(exc),
                photo_id=photo_id,
            )
            return False
        db.set_pipeline_ok(conn, photo_id, pipeline_ms)
        return True
