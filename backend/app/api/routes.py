"""REST endpoints for the guest flow.

All state-changing actions are POSTs (api-contract): the WebSocket is one-way, so
there is exactly one path that mutates state. After every mutation the router
flushes queued WebSocket messages so connected clients see the transition.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request, Response
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.engine import Engine

router = APIRouter()

# api variant name -> directory on disk
_VARIANT_DIRS = {
    "original": "originals",
    "processed": "processed",
    "print": "prints",
    "thumb": "thumbs",
}


def _engine(request: Request) -> Engine:
    return request.app.state.engine


def _photo_aspect(config) -> float:
    """Width divided by height of every processed photo (the print canvas)."""
    from app.pipeline.geometry import canvas_for

    canvas = canvas_for(config.printing)
    return round(canvas.width / canvas.height, 4)


async def _mutate_and_flush(engine: Engine, action) -> JSONResponse:
    action()
    await engine.flush()
    return JSONResponse(engine.build_status())


# --- status & catalogue -----------------------------------------------------


@router.get("/api/status")
async def get_status(request: Request) -> JSONResponse:
    return JSONResponse(_engine(request).build_status())


@router.get("/api/client-config")
async def get_client_config(request: Request) -> JSONResponse:
    """Non-sensitive, config-driven values the guest UI needs for its timers.

    Additive to the api-contract: it exposes only presentational numbers/flags so
    the frontend never hard-codes them (CLAUDE.md rule 6). No secrets (no PIN).
    """
    config = _engine(request).config
    return JSONResponse(
        {
            "mirror_preview": config.ui.mirror_preview,
            "idle_hint_pulse": config.ui.idle_hint_pulse,
            "flash_enabled": config.ui.flash_enabled,
            "processing_warn_seconds": config.timeouts.processing_warn_seconds,
            "preview_seconds": config.timeouts.preview_seconds,
            "preview_fps": config.hardware.preview.fps,
            # Seitenverhältnis der fertigen Fotos, damit Galerie und Kiosk keine
            # Kachelform hartkodieren (Regel 6) — dreht mit printing.orientation.
            "photo_aspect": _photo_aspect(config),
            "gallery_enabled": config.network.gallery_enabled,
            "gallery_return_seconds": config.network.gallery_return_seconds,
            "admin_corner": config.ui.admin_corner,
            "admin_longpress_seconds": config.ui.admin_longpress_seconds,
        }
    )


@router.get("/api/backgrounds")
async def get_backgrounds(request: Request) -> JSONResponse:
    engine = _engine(request)
    return JSONResponse(
        {
            "backgrounds": [
                {
                    "id": bg.id,
                    "name": bg.name,
                    "mode": bg.mode,
                    "thumbnail_url": f"/api/backgrounds/{bg.id}/thumbnail",
                    "enabled": bg.enabled,
                    "sort_order": bg.sort_order,
                }
                for bg in engine.backgrounds.list()
            ]
        }
    )


@router.get("/api/backgrounds/{background_id}/thumbnail")
async def get_background_thumbnail(request: Request, background_id: str) -> Response:
    path = _engine(request).background_thumbnail_path(background_id)
    if path is None or not path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Kein Vorschaubild vorhanden"}},
        )
    return FileResponse(path, media_type="image/jpeg")


# --- session actions --------------------------------------------------------


class BackgroundSelection(BaseModel):
    background_id: str


@router.post("/api/session/start")
async def session_start(request: Request) -> JSONResponse:
    engine = _engine(request)
    return await _mutate_and_flush(engine, engine.start)


@router.post("/api/session/background")
async def session_background(request: Request, body: BackgroundSelection) -> JSONResponse:
    engine = _engine(request)
    return await _mutate_and_flush(engine, lambda: engine.select_background(body.background_id))


@router.post("/api/session/cancel")
async def session_cancel(request: Request) -> JSONResponse:
    engine = _engine(request)
    return await _mutate_and_flush(engine, engine.cancel)


@router.post("/api/session/print")
async def session_print(request: Request) -> JSONResponse:
    engine = _engine(request)
    return await _mutate_and_flush(engine, engine.request_print)


@router.post("/api/session/finish")
async def session_finish(request: Request) -> JSONResponse:
    engine = _engine(request)
    return await _mutate_and_flush(engine, engine.finish)


@router.post("/api/session/wake")
async def session_wake(request: Request) -> JSONResponse:
    """Leave the slideshow. Does not start a session — that takes a second touch."""
    engine = _engine(request)
    return await _mutate_and_flush(engine, engine.wake_from_screensaver)


# --- media ------------------------------------------------------------------


@router.get("/api/photos/{photo_id}/{variant}")
async def get_photo(request: Request, photo_id: int, variant: str) -> Response:
    if variant == "thumb-original":
        # Not a stored variant: made on first request from the original, because
        # the events already on the card predate it.
        thumbnail = _engine(request).original_thumbnail_path(photo_id)
        if thumbnail is None:
            return JSONResponse(
                status_code=404,
                content={"error": {"code": "not_found", "message": "Bild nicht gefunden"}},
            )
        return FileResponse(thumbnail, media_type="image/jpeg")
    directory = _VARIANT_DIRS.get(variant)
    if directory is None:
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Unbekannte Variante"}},
        )
    path = _engine(request).photo_variant_path(directory, photo_id)
    if not path.exists():
        return JSONResponse(
            status_code=404,
            content={"error": {"code": "not_found", "message": "Bild nicht gefunden"}},
        )
    return FileResponse(path, media_type="image/jpeg")


@router.get("/preview/frame")
async def preview_frame(request: Request) -> Response:
    """A single current JPEG frame.

    The kiosk polls this to drive a self-healing live preview: every frame is an
    independent request, so a stalled or dropped connection can never leave the
    preview stuck black — unlike a long-lived ``multipart/x-mixed-replace`` stream,
    which Chromium can silently freeze without firing an ``error`` the frontend
    could react to. The backend is read fresh on each call, so a rebuilt preview
    (admin re-select / reconnect) is picked up immediately.
    """
    frame = _engine(request).backends.preview.frame()
    return Response(
        content=frame,
        media_type="image/jpeg",
        headers={"Cache-Control": "no-store, max-age=0"},
    )


@router.get("/preview/stream")
async def preview_stream(request: Request) -> StreamingResponse:
    """MJPEG stream (kept for compatibility; the kiosk uses ``/preview/frame``)."""
    engine = _engine(request)
    interval = 1.0 / engine.config.hardware.preview.fps

    async def frames():
        while True:
            if await request.is_disconnected():
                break
            # Read the current backend each iteration so a rebuilt preview is
            # used instead of a dead reference; never let one bad frame end the
            # stream.
            try:
                frame = engine.backends.preview.frame()
            except Exception:
                await asyncio.sleep(interval)
                continue
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(interval)

    return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame")
