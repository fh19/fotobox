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


class NotFound(Exception):
    """A referenced resource does not exist (maps to HTTP 404)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


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
        self._last_avail = None

    # --- message plumbing ---------------------------------------------------

    def _on_sm_emit(self, event_type: str, payload: dict) -> None:
        if event_type == "state_changed":
            if self.sm.state == State.CAPTURE:
                self._capture_ready_at = None  # start a fresh flash phase
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
        self.sm.start()
        self._drive()

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
        """Shared shutter release for calibration and test shot (admin, IDLE only)."""
        if self.sm.state != State.IDLE:
            raise ActionRejected("invalid_state", "Probefoto nur im Ruhezustand möglich")
        try:
            result = self.backends.camera.capture()
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
    _EDITABLE_SECTIONS = ("ui", "countdown", "timeouts", "printing")

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

    def network_status(self) -> dict:
        from app import system

        ap = self.config.network.access_point
        active = system.ap_active()
        # In AP mode the box is reachable at its own AP address; otherwise at the
        # DHCP/Ethernet address. The gallery URL is built by the client (it knows
        # its own port) — we only supply the host.
        return {
            "ap_enabled": active,
            "ssid": ap.ssid,
            "ip": ap.address if active else system.primary_ip(),
        }

    def network_ap(self, enabled: bool) -> dict:
        """Switch the guest access point on/off (M7b). Blocking — call off-thread."""
        from app import system

        ap = self.config.network.access_point
        try:
            if enabled:
                system.ap_enable(ap.ssid, ap.passphrase, ap.channel, ap.address)
                self._log("warning", "system", "ap_on", f"Access-Point '{ap.ssid}' an")
            else:
                system.ap_disable()
                self._log("info", "system", "ap_off", "Access-Point aus")
        except Exception as exc:
            self._log("error", "system", "ap_failed", str(exc))
            raise ActionRejected("ap_failed", f"Netzwerkumschaltung fehlgeschlagen: {exc}") from exc
        return self.network_status()

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
        if self.camera_manager is not None and self.camera_manager.rediscover_if_missing(now):
            self.backends = self.camera_manager.backends
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
            }

        status = {
            "state": str(sm.state),
            "session": session_payload,
            "printer": {
                "available": printer.available(),
                "state": str(printer.state()),
                "paused": printer.paused(),
                "message": None,
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
        if sm.state == State.ERROR and sm.error is not None:
            status["error"] = {"code": sm.error.code, "message": sm.error.message}
        return status

    def _print_allowed(self, print_count: int) -> bool:
        printing = self.config.printing
        if not printing.enabled or not self.backends.printer.available():
            return False
        if print_count >= printing.max_per_photo:
            return False
        return db.count_event_prints(self.conn, self.active_event["id"]) < printing.max_per_event

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

    def event_files(self, event_id: int, variant: str) -> list[tuple[str, Path]]:
        """(*arcname*, *path*) pairs for a ZIP export of an event's photos."""
        entries: list[tuple[str, Path]] = []
        event = db.get_event(self.conn, event_id)
        if event is None:
            return entries
        directory = event["directory"]
        for photo in db.iter_event_photos(self.conn, event_id):
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
