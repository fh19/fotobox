"""The screensaver: after a few quiet minutes the box shows the evening's photos.

From Optimierungen2.md — "wenn die Box für zB 5min nicht benutzt wurde, sollen
die bisherigen Bilder in zufälliger Reihenfolge auf dem Schirm angezeigt werden.
sobald man den Schirm antippt, kommt der Screen und erst jetzt kann man Fotos
per Tippen auslösen".
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app import db
from app.clock import FakeClock
from app.main import create_app
from tests.conftest import make_config


def _box(tmp_path, photos=5, **overrides):
    clock = FakeClock()
    app = create_app(make_config(tmp_path, **overrides), clock)
    engine = app.state.engine
    for _ in range(photos):
        photo_id = db.insert_photo(
            engine.conn,
            event_id=engine.active_event["id"],
            captured_at=datetime.now(UTC).astimezone(),
            background_id=None,
            background_mode="none",
            camera_model="Nikon",
            width=1872,
            height=1248,
        )
        path = engine.photo_variant_path("processed", photo_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"\xff\xd8\xff" + b"x" * 100)
    return app, engine, clock


def _fall_asleep(engine, clock):
    clock.advance(engine.config.screensaver.after_seconds + 1)
    engine.sm.poll()


def test_the_status_carries_the_photos_and_the_timing(tmp_path):
    app, engine, clock = _box(tmp_path, photos=5)
    _fall_asleep(engine, clock)

    status = engine.build_status()
    assert status["state"] == "SCREENSAVER"
    saver = status["screensaver"]
    assert len(saver["photos"]) == 5
    assert all(url.endswith("/processed") for url in saver["photos"])
    assert saver["interval_ms"] == int(engine.config.screensaver.interval_seconds * 1000)
    assert saver["fade_ms"] == engine.config.screensaver.fade_ms


def test_the_order_is_shuffled_in_the_backend(tmp_path):
    """The order is a decision, so it is not left to the browser (rule 5)."""
    app, engine, clock = _box(tmp_path, photos=40)

    orders = set()
    for _ in range(6):
        _fall_asleep(engine, clock)
        orders.add(tuple(engine.build_status()["screensaver"]["photos"]))
        engine.wake_from_screensaver()
    assert len(orders) > 1


def test_photos_without_a_file_are_left_out(tmp_path):
    """A failed pipeline or a purged photo must not leave a hole in the show."""
    app, engine, clock = _box(tmp_path, photos=3)
    missing = db.insert_photo(
        engine.conn,
        event_id=engine.active_event["id"],
        captured_at=datetime.now(UTC).astimezone(),
        background_id=None,
        background_mode="none",
        camera_model="Nikon",
        width=10,
        height=10,
    )
    _fall_asleep(engine, clock)

    photos = engine.build_status()["screensaver"]["photos"]
    assert len(photos) == 3
    assert f"/api/photos/{missing}/processed" not in photos


def test_the_list_is_capped(tmp_path):
    app, engine, clock = _box(tmp_path, photos=12, screensaver__max_photos=5)
    _fall_asleep(engine, clock)
    assert len(engine.build_status()["screensaver"]["photos"]) == 5


def test_an_empty_event_still_falls_asleep(tmp_path):
    """A box switched on early has nothing to show, and that must not crash it."""
    app, engine, clock = _box(tmp_path, photos=0)
    _fall_asleep(engine, clock)
    assert engine.build_status()["screensaver"]["photos"] == []


def test_waking_over_the_api_does_not_take_a_photo(tmp_path):
    app, engine, clock = _box(tmp_path, photos=2)
    _fall_asleep(engine, clock)
    client = TestClient(app)

    res = client.post("/api/session/wake")
    assert res.status_code == 200
    assert res.json()["state"] == "IDLE"
    assert res.json()["session"] is None
    assert db.count_photos(engine.conn, engine.active_event["id"]) == 2


def test_starting_a_session_from_the_slideshow_is_refused(tmp_path):
    app, engine, clock = _box(tmp_path, photos=2)
    _fall_asleep(engine, clock)
    assert TestClient(app).post("/api/session/start").status_code == 409


def test_the_photo_list_is_dropped_on_waking(tmp_path):
    """It must not linger — the next slideshow reshuffles and may see new photos."""
    app, engine, clock = _box(tmp_path, photos=2)
    _fall_asleep(engine, clock)
    engine.wake_from_screensaver()
    assert "screensaver" not in engine.build_status()
