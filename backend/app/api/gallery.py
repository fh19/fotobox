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
        "thumb_url": f"/api/photos/{photo_id}/thumb",
    }


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
    request: Request, event_id: int, variant: str = Query("processed")
) -> Response:
    engine = _engine(request)
    if not engine.config.network.gallery_enabled:
        return _disabled()
    if variant not in _VARIANTS:
        return _not_found("Unbekannte Variante")
    if db.get_event(engine.conn, event_id) is None:
        return _not_found("Event nicht gefunden")

    files = [(arc, path) for arc, path in engine.event_files(event_id, variant) if path.exists()]
    size = sum(path.stat().st_size for _, path in files)
    return JSONResponse({"variant": variant, "file_count": len(files), "size_bytes": size})


@router.get("/api/events/{event_id}/download.zip")
async def download_zip(
    request: Request, event_id: int, variant: str = Query("processed")
) -> Response:
    engine = _engine(request)
    if not engine.config.network.gallery_enabled:
        return _disabled()
    if variant not in _VARIANTS:
        return _not_found("Unbekannte Variante")
    event = db.get_event(engine.conn, event_id)
    if event is None:
        return _not_found("Event nicht gefunden")

    entries = engine.event_files(event_id, variant)
    filename = f"{event['directory']}.zip"
    return StreamingResponse(
        stream_zip(entries),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
