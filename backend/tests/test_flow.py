"""End-to-end session flow through the engine, with mock hardware and a fake clock."""

from __future__ import annotations

from app.states import State
from tests.conftest import messages_of_type, state_changes


def _run_countdown(engine, clock, duration):
    engine.tick()  # emits the first tick immediately (remaining == duration)
    for _ in range(duration):
        clock.advance(1)
        engine.tick()


def test_full_happy_path(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=1)
    assert engine.sm.state == State.IDLE

    engine.start()
    assert engine.sm.state == State.BACKGROUND_SELECT

    engine.select_background("none")
    assert engine.sm.state == State.COUNTDOWN

    _run_countdown(engine, clock, duration=1)
    # CAPTURE and PROCESSING are driven synchronously to PREVIEW by the engine.
    assert engine.sm.state == State.PREVIEW
    assert engine.sm.session.photo_id == 1

    engine.finish()
    assert engine.sm.state == State.IDLE

    assert state_changes(engine) == [
        "BACKGROUND_SELECT",
        "COUNTDOWN",
        "CAPTURE",
        "PROCESSING",
        "PREVIEW",
        "IDLE",
    ]


def test_original_and_variants_written(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=1)
    engine.start()
    engine.select_background("none")
    _run_countdown(engine, clock, duration=1)

    event_dir = engine.config.events_dir / engine.active_event["directory"]
    for variant in ("originals", "processed", "prints", "thumbs"):
        assert (event_dir / variant / "IMG_0001.jpg").exists()


def test_photo_row_marked_ok(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=1)
    engine.start()
    engine.select_background("none")
    _run_countdown(engine, clock, duration=1)

    row = engine.conn.execute("SELECT * FROM photos WHERE id = 1").fetchone()
    assert row["pipeline_status"] == "ok"
    assert row["filename"] == "IMG_0001.jpg"
    assert row["pipeline_ms"] is not None


def test_countdown_emits_exactly_duration_ticks(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=5)
    engine.start()
    engine.select_background("none")
    _run_countdown(engine, clock, duration=5)

    ticks = messages_of_type(engine, "countdown_tick")
    assert [m["payload"]["remaining"] for m in ticks] == [5, 4, 3, 2, 1]


def test_state_changed_carries_full_status(make_engine, clock):
    engine = make_engine()
    engine.start()
    payload = messages_of_type(engine, "state_changed")[0]["payload"]
    for key in ("state", "session", "printer", "camera", "preview", "event", "storage"):
        assert key in payload


def test_print_flow(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=1)
    engine.start()
    engine.select_background("none")
    _run_countdown(engine, clock, duration=1)
    assert engine.sm.state == State.PREVIEW

    engine.request_print()
    # PRINTING is momentary: back in PREVIEW once the job is handed to CUPS.
    assert engine.sm.state == State.PREVIEW
    assert engine.sm.session.print_count == 1
    assert [m["type"] for m in engine._outbox if m["type"].startswith("print")] == [
        "print_started",
        "print_finished",
    ]

    row = engine.conn.execute("SELECT * FROM print_jobs").fetchone()
    assert row["status"] == "queued"


def test_print_limit_reached(make_engine, clock):
    from app.state_machine import ActionRejected

    engine = make_engine(countdown__duration_seconds=1)
    engine.start()
    engine.select_background("none")
    _run_countdown(engine, clock, duration=1)
    engine.request_print()

    try:
        engine.request_print()
    except ActionRejected as exc:
        assert exc.code == "print_limit_reached"
    else:
        raise AssertionError("expected ActionRejected")


def test_capture_failure_goes_to_error(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=1)
    engine.backends.camera.set_available(False)
    engine.start()
    engine.select_background("none")
    _run_countdown(engine, clock, duration=1)

    assert engine.sm.state == State.ERROR
    assert engine.sm.error.code == "capture_failed"
    error_msgs = messages_of_type(engine, "error")
    assert error_msgs and error_msgs[0]["payload"]["code"] == "capture_failed"
