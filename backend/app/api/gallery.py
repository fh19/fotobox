"""Gallery REST endpoints (after the event).

Reachable only when ``network.gallery_enabled`` is true (api-contract). Read-only:
list events, paginate photos, and stream a ZIP export. The ZIP is streamed, never
buffered, so memory stays flat for thousands of photos (M4).
"""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse

from app import db
from app.engine import Engine
from app.zipstream import stream_zip

router = APIRouter()

DEFAULT_PER_PAGE = 60
MAX_PER_PAGE = 200
_VARIANTS = {"processed", "original", "both"}


def _engine(request: Request) -> Engine:
    return request.app.state.engine


def _disabled() -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={"error": {"code": "gallery_disabled", "message": "Die Galerie ist deaktiviert"}},
    )


def _photo_ids(raw: str | None) -> set[int] | None:
    """``?ids=12,13,14`` → a selection, or None for the whole event."""
    if not raw:
        return None
    ids = {int(part) for part in raw.split(",") if part.strip().isdigit()}
    return ids or None


def _not_found(message: str) -> JSONResponse:
    return JSONResponse(
        status_code=404, content={"error": {"code": "not_found", "message": message}}
    )


def _photo_payload(row) -> dict:
    photo_id = row["id"]
    return {
        "id": photo_id,
        "filename": row["filename"],
        "captured_at": row["captured_at"],
        "background_id": row["background_id"],
        "background_mode": row["background_mode"],
        "pipeline_status": row["pipeline_status"],
        "original_url": f"/api/photos/{photo_id}/original",
        "processed_url": f"/api/photos/{photo_id}/processed",
        # The print raster (1872x1248) doubles as the on-screen version: the
        # processed master is composed above print size for downloads and takes
        # the Pi a moment to decode, which made the gallery feel sluggish.
        "print_url": f"/api/photos/{photo_id}/print",
        "thumb_url": f"/api/photos/{photo_id}/thumb",
        # The grid needs a thumbnail per view — the stored one is made from the
        # framed copy, so "Original" used to show the frame anyway.
        "thumb_original_url": f"/api/photos/{photo_id}/thumb-original",
    }


@router.post("/api/photos/{photo_id}/print")
async def post_photo_print(
    request: Request, photo_id: int, variant: str = Query("processed")
) -> Response:
    """Print a stored photo again — the gallery's reprint button.

    Read-only everywhere else in this router; this is the one action, and it is
    guarded by the event's print quota rather than by who is asking.
    """
    engine = _engine(request)
    if not engine.config.network.gallery_enabled:
        return _disabled()
    return JSONResponse(engine.reprint_photo(photo_id, variant))


@router.get("/api/events")
async def get_events(request: Request) -> Response:
    engine = _engine(request)
    if not engine.config.network.gallery_enabled:
        return _disabled()
    rows = db.list_events(engine.conn)
    return JSONResponse(
        {
            "events": [
                {
                    "id": row["id"],
                    "name": row["name"],
                    "created_at": row["created_at"],
                    "photo_count": row["photo_count"],
                }
                for row in rows
            ]
        }
    )


@router.get("/api/events/{event_id}/photos")
async def get_event_photos(
    request: Request,
    event_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PER_PAGE, ge=1, le=MAX_PER_PAGE),
) -> Response:
    engine = _engine(request)
    if not engine.config.network.gallery_enabled:
        return _disabled()
    if db.get_event(engine.conn, event_id) is None:
        return _not_found("Event nicht gefunden")

    total = db.count_photos(engine.conn, event_id)
    rows = db.list_photos(engine.conn, event_id, limit=per_page, offset=(page - 1) * per_page)
    return JSONResponse(
        {
            "photos": [_photo_payload(row) for row in rows],
            "page": page,
            "per_page": per_page,
            "total": total,
        }
    )


@router.get("/api/events/{event_id}/download-info")
async def get_download_info(
    request: Request,
    event_id: int,
    variant: str = Query("processed"),
    ids: str | None = Query(None),
) -> Response:
    engine = _engine(request)
    if not engine.config.network.gallery_enabled:
        return _disabled()
    if variant not in _VARIANTS:
        return _not_found("Unbekannte Variante")
    if db.get_event(engine.conn, event_id) is None:
        return _not_found("Event nicht gefunden")

    selection = _photo_ids(ids)
    files = [
        (arc, path)
        for arc, path in engine.event_files(event_id, variant, selection)
        if path.exists()
    ]
    size = sum(path.stat().st_size for _, path in files)
    return JSONResponse({"variant": variant, "file_count": len(files), "size_bytes": size})


@router.get("/api/events/{event_id}/download.zip")
async def download_zip(
    request: Request,
    event_id: int,
    variant: str = Query("processed"),
    ids: str | None = Query(None),
) -> Response:
    engine = _engine(request)
    if not engine.config.network.gallery_enabled:
        return _disabled()
    if variant not in _VARIANTS:
        return _not_found("Unbekannte Variante")
    event = db.get_event(engine.conn, event_id)
    if event is None:
        return _not_found("Event nicht gefunden")

    selection = _photo_ids(ids)
    entries = engine.event_files(event_id, variant, selection)
    # Im Download-Ordner liegen die Archive später nebeneinander — der Name muss
    # allein verraten, was drin ist.
    kind = {"processed": "rahmen", "original": "original", "both": "beide"}[variant]
    suffix = f"_auswahl-{len(selection)}" if selection else ""
    filename = f"{event['directory']}_{kind}{suffix}.zip"
    return StreamingResponse(
        stream_zip(entries),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
