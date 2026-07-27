"""Gallery endpoints and streaming ZIP export (M4)."""

from __future__ import annotations

import io
import tracemalloc
import zipfile
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app import db
from app.clock import RealClock
from app.main import create_app
from app.zipstream import stream_zip
from tests.conftest import make_config


def _app(tmp_path, **overrides):
    return create_app(make_config(tmp_path, **overrides), RealClock())


def _populate(app, count, *, ok=True):
    engine = app.state.engine
    event = engine.active_event
    ids = []
    for _ in range(count):
        photo_id = db.insert_photo(
            engine.conn,
            event_id=event["id"],
            captured_at=datetime.now(UTC),
            background_id=None,
            background_mode="none",
            camera_model="Mock",
            width=1200,
            height=1800,
        )
        if ok:
            db.set_pipeline_ok(engine.conn, photo_id, 5)
        for variant in ("originals", "processed", "thumbs", "prints"):
            path = engine.photo_variant_path(variant, photo_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"{variant}-{photo_id}".encode() * 100)
        ids.append(photo_id)
    return ids


# --- events & photos --------------------------------------------------------


def test_events_lists_active_event_with_count(tmp_path):
    app = _app(tmp_path)
    _populate(app, 3)
    body = TestClient(app).get("/api/events").json()
    assert len(body["events"]) == 1
    assert body["events"][0]["photo_count"] == 3


def test_photos_are_paginated(tmp_path):
    app = _app(tmp_path)
    _populate(app, 5)
    event_id = app.state.engine.active_event["id"]
    client = TestClient(app)

    page1 = client.get(f"/api/events/{event_id}/photos?page=1&per_page=2").json()
    assert page1["total"] == 5
    assert len(page1["photos"]) == 2
    assert page1["photos"][0]["thumb_url"].startswith("/api/photos/")

    page3 = client.get(f"/api/events/{event_id}/photos?page=3&per_page=2").json()
    assert len(page3["photos"]) == 1


def test_unknown_event_is_404(tmp_path):
    app = _app(tmp_path)
    assert TestClient(app).get("/api/events/999/photos").status_code == 404


# --- gallery gate -----------------------------------------------------------


def test_gallery_disabled_returns_404(tmp_path):
    app = _app(tmp_path, network__gallery_enabled=False)
    client = TestClient(app)
    assert client.get("/api/events").status_code == 404
    assert client.get("/gallery").status_code == 404


def test_gallery_page_served_when_enabled(tmp_path):
    app = _app(tmp_path)
    res = TestClient(app).get("/gallery")
    assert res.status_code == 200
    assert "Galerie" in res.text


# --- download info & zip ----------------------------------------------------


def test_download_info_counts_files(tmp_path):
    app = _app(tmp_path)
    _populate(app, 3)
    event_id = app.state.engine.active_event["id"]
    info = TestClient(app).get(f"/api/events/{event_id}/download-info?variant=processed").json()
    assert info["file_count"] == 3
    assert info["size_bytes"] > 0


def test_zip_contains_all_photos(tmp_path):
    app = _app(tmp_path)
    _populate(app, 4)
    event_id = app.state.engine.active_event["id"]
    res = TestClient(app).get(f"/api/events/{event_id}/download.zip?variant=processed")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
        names = archive.namelist()
    assert len(names) == 4
    assert all(name.startswith("IMG_") for name in names)


def test_zip_both_variants_has_two_folders(tmp_path):
    app = _app(tmp_path)
    _populate(app, 2)
    event_id = app.state.engine.active_event["id"]
    res = TestClient(app).get(f"/api/events/{event_id}/download.zip?variant=both")
    with zipfile.ZipFile(io.BytesIO(res.content)) as archive:
        names = archive.namelist()
    assert sum(n.startswith("original/") for n in names) == 2
    assert sum(n.startswith("bearbeitet/") for n in names) == 2


def test_invalid_variant_is_404(tmp_path):
    app = _app(tmp_path)
    event_id = app.state.engine.active_event["id"]
    assert (
        TestClient(app).get(f"/api/events/{event_id}/download.zip?variant=nope").status_code == 404
    )


# --- streaming memory (criterion: memory does not grow with photo count) ----


def test_zip_stream_memory_is_flat(tmp_path):
    payload = b"x" * 50_000
    files = []
    for i in range(300):
        path = tmp_path / f"f{i}.jpg"
        path.write_bytes(payload)
        files.append((f"IMG_{i:04d}.jpg", path))

    tracemalloc.start()
    total = 0
    for chunk in stream_zip(files):  # consume and discard, like the HTTP transport
        total += len(chunk)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    assert total > 300 * 50_000 * 0.9  # everything was actually streamed (~15 MB)
    assert peak < 2_000_000  # but peak memory stays near one file, not the whole archive
