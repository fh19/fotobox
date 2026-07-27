"""Restart pipeline recovery (M4): pending photos are reprocessed."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app import db
from app.clock import RealClock
from app.hardware.synthetic import greenscreen_jpeg
from app.main import create_app
from tests.conftest import make_config


def _insert_pending(engine, *, with_original=True):
    photo_id = db.insert_photo(
        engine.conn,
        event_id=engine.active_event["id"],
        captured_at=datetime.now(UTC),
        background_id=None,
        background_mode="none",
        camera_model="Mock",
        width=1200,
        height=1800,
    )
    if with_original:
        original = engine.photo_variant_path("originals", photo_id)
        original.parent.mkdir(parents=True, exist_ok=True)
        original.write_bytes(greenscreen_jpeg(300, 450))
    return photo_id


def _status(engine, photo_id):
    return engine.conn.execute(
        "SELECT pipeline_status FROM photos WHERE id = ?", (photo_id,)
    ).fetchone()["pipeline_status"]


def test_pending_pipeline_is_recovered(make_engine):
    engine = make_engine()
    photo_id = _insert_pending(engine)
    assert _status(engine, photo_id) == "pending"

    recovered = engine.recover_pending_pipelines()

    assert recovered == 1
    assert _status(engine, photo_id) == "ok"
    assert engine.photo_variant_path("processed", photo_id).exists()
    assert engine.photo_variant_path("thumbs", photo_id).exists()


def test_missing_original_is_marked_failed(make_engine):
    engine = make_engine()
    photo_id = _insert_pending(engine, with_original=False)

    recovered = engine.recover_pending_pipelines()

    assert recovered == 0
    assert _status(engine, photo_id) == "failed"


def test_recovery_runs_on_startup(tmp_path):
    # First app instance: create a pending photo, then "restart".
    app = create_app(make_config(tmp_path), RealClock())
    photo_id = _insert_pending(app.state.engine)

    # Restart: a fresh app on the same data dir recovers pending pipelines in its
    # lifespan (background thread).
    restarted = create_app(make_config(tmp_path), RealClock())
    with TestClient(restarted):
        engine = restarted.state.engine
        deadline = time.time() + 5
        while time.time() < deadline and _status(engine, photo_id) == "pending":
            time.sleep(0.05)
    assert _status(engine, photo_id) == "ok"
