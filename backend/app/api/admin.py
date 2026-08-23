"""Admin endpoints (M5/M6/M7).

Every ``/api/admin/`` route needs the ``X-Fotobox-Pin`` header (api-contract).
Wrong PIN → 401; after 5 wrong attempts the PIN is locked for 60 s (423). Runtime
config edits are limited to ui/countdown/timeouts/printing; hardware/path settings
are not changeable at runtime.
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, File, Form, Header, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel

from app.engine import Engine

router = APIRouter(prefix="/api/admin")


class PinError(Exception):
    """Wrong or missing admin PIN (maps to HTTP 401)."""


class LockedError(Exception):
    """Too many wrong PINs — temporarily locked (maps to HTTP 423)."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("PIN gesperrt")
        self.retry_after = retry_after


class AdminAuth:
    """Tracks failed PIN attempts and enforces a lockout (single kiosk)."""

    def __init__(self, max_attempts: int = 5, lock_seconds: int = 60) -> None:
        self._max = max_attempts
        self._lock_seconds = lock_seconds
        self._fails = 0
        self._locked_until = 0.0

    def verify(self, pin: str | None, expected: str) -> None:
        now = time.monotonic()
        if now < self._locked_until:
            raise LockedError(retry_after=int(self._locked_until - now) + 1)
        if pin == expected:
            self._fails = 0
            return
        self._fails += 1
        if self._fails >= self._max:
            self._locked_until = now + self._lock_seconds
            self._fails = 0
        raise PinError()


def _require_pin(request: Request, pin: str | None) -> None:
    request.app.state.admin_auth.verify(pin, request.app.state.config.ui.admin_pin)


def _engine(request: Request) -> Engine:
    return request.app.state.engine


# --- auth -------------------------------------------------------------------


@router.post("/auth")
async def auth(request: Request, x_fotobox_pin: str | None = Header(default=None)) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse({"ok": True})


# --- cameras (M5) -----------------------------------------------------------


class CameraSelection(BaseModel):
    camera_select: str | None = None
    preview_device: str | None = None
    preview_backend: str | None = None


@router.get("/cameras")
async def get_cameras(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).list_cameras())


@router.post("/cameras")
async def post_cameras(
    request: Request, body: CameraSelection, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(
        _engine(request).reselect_cameras(
            camera_select=body.camera_select,
            preview_device=body.preview_device,
            preview_backend=body.preview_backend,
        )
    )


@router.post("/camera/rescan")
async def post_camera_rescan(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    """Look for cameras again — for one connected after the box booted."""
    _require_pin(request, x_fotobox_pin)
    # Off the event loop: discovery talks to USB and can take a moment.
    return JSONResponse(await asyncio.to_thread(_engine(request).rescan_cameras))


@router.post("/camera/reset")
async def post_camera_reset(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    """USB-reset the DSLR and reopen the preview device, then look again."""
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(await asyncio.to_thread(_engine(request).reset_cameras))


@router.post("/camera/testshot")
async def post_camera_testshot(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    """Take a photo that goes nowhere near the event — just to see what fires."""
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(await asyncio.to_thread(_engine(request).test_shot))


@router.get("/camera/testshot.jpg")
async def get_camera_testshot(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    path = _engine(request).test_shot_path
    if not path.exists():
        return JSONResponse({"error": {"code": "not_found", "message": "Kein Probefoto"}}, 404)
    return Response(
        path.read_bytes(), media_type="image/jpeg", headers={"Cache-Control": "no-store"}
    )


@router.post("/calibration")
async def post_calibration(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).calibrate_orientation())


# --- printer (M6) -----------------------------------------------------------


@router.get("/printer")
async def get_printer(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).printer_status())


@router.post("/printer/resume")
async def printer_resume(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).printer_resume())


@router.post("/printer/cancel-all")
async def printer_cancel_all(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).printer_cancel_all())


@router.post("/printer/counter-reset")
async def printer_counter_reset(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).printer_reset_counter())


@router.post("/printer/test-page")
async def printer_test_page(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).printer_test_page())


# --- config / event / system (M7) -------------------------------------------


@router.get("/config")
async def get_config(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).editable_config())


@router.put("/config")
async def put_config(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    updates = await request.json()
    return JSONResponse(_engine(request).update_config(updates))


class NewEvent(BaseModel):
    name: str


@router.post("/event")
async def post_event(
    request: Request, body: NewEvent, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).create_new_event(body.name))


# --- backgrounds / frames (M-extra) -----------------------------------------


@router.get("/backgrounds")
async def get_backgrounds(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).list_backgrounds_admin())


@router.post("/backgrounds")
async def post_background(
    request: Request,
    name: str = Form(...),
    mode: str = Form(...),
    sort_order: int = Form(default=10),
    file: UploadFile = File(...),
    x_fotobox_pin: str | None = Header(default=None),
) -> Response:
    _require_pin(request, x_fotobox_pin)
    data = await file.read()
    return JSONResponse(_engine(request).add_background(name, mode, sort_order, data))


@router.delete("/backgrounds/{background_id}")
async def delete_background(
    request: Request, background_id: str, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).delete_background(background_id))


@router.get("/system")
async def get_system(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).system_info())


@router.post("/shutdown")
async def post_shutdown(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).shutdown())


@router.post("/reboot")
async def post_reboot(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).reboot())


# --- gallery management -----------------------------------------------------
#
# "Anschauen und Löschen aller Veranstaltungsbilder aus dem Konfig-Menü heraus".
# Viewing happens in the gallery page (opened with ?admin=1); the two steps that
# change something live here, behind the PIN.


class PhotoIds(BaseModel):
    ids: list[int]


@router.post("/photos/delete")
async def post_photos_delete(
    request: Request, body: PhotoIds, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    """Flag photos as deleted. The files stay until the purge below."""
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).delete_photos(body.ids))


@router.get("/photos/deleted")
async def get_photos_deleted(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).deleted_photo_stats())


@router.post("/photos/purge")
async def post_photos_purge(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    """Finally remove the files of every flagged photo — irreversible."""
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(await asyncio.to_thread(_engine(request).purge_deleted_photos))


@router.post("/events/{event_id}/rerender")
async def post_event_rerender(
    request: Request, event_id: int, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    """Run the pipeline again over an old event — new resolution, EXIF kept."""
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).start_rerender(event_id))


@router.get("/rerender")
async def get_rerender(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).rerender_status())


# --- network / export (M7b) -------------------------------------------------


class NetworkAP(BaseModel):
    enabled: bool


@router.get("/network")
async def get_network(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).network_status())


@router.post("/network/ap-auto")
async def post_network_ap_auto(
    request: Request, body: NetworkAP, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    """Turn the automatic access point on/off (no radio change, just the rule)."""
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).set_ap_auto(body.enabled))


@router.post("/network/ap")
async def post_network_ap(
    request: Request, body: NetworkAP, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    # nmcli blocks for a few seconds and drops the WiFi — keep the event loop free.
    result = await asyncio.to_thread(_engine(request).network_ap, body.enabled)
    return JSONResponse(result)


@router.post("/export/usb")
async def post_export_usb(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).start_usb_export())


@router.get("/export/usb")
async def get_export_usb(
    request: Request, x_fotobox_pin: str | None = Header(default=None)
) -> Response:
    _require_pin(request, x_fotobox_pin)
    return JSONResponse(_engine(request).export_status())
