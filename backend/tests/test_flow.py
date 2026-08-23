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


# --- shutter lead -----------------------------------------------------------
#
# The shutter is not instant: flash duration plus camera latency put the actual
# exposure a moment after the countdown hits zero. The lead fires that much
# earlier so the picture is taken when the guests expect it.


def test_shutter_lead_fires_the_capture_early(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=3, countdown__shutter_lead_ms=600)
    engine.start()
    engine.select_background("none")

    engine.tick()
    clock.advance(2.3)
    engine.tick()
    assert engine.sm.state == State.COUNTDOWN  # 700 ms left, lead is 600 ms

    clock.advance(0.15)
    engine.tick()
    assert engine.sm.state == State.PREVIEW  # fired at 2.45 s of a 3 s countdown


def test_without_a_lead_the_capture_waits_for_zero(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=3)
    engine.start()
    engine.select_background("none")

    engine.tick()
    clock.advance(2.9)
    engine.tick()
    assert engine.sm.state == State.COUNTDOWN

    clock.advance(0.2)
    engine.tick()
    assert engine.sm.state == State.PREVIEW


def test_a_lead_longer_than_the_countdown_keeps_the_last_second(make_engine, clock):
    """Guests still get a countdown — the lead is capped at duration minus one."""
    engine = make_engine(countdown__duration_seconds=3, countdown__shutter_lead_ms=5000)
    engine.start()
    engine.select_background("none")

    engine.tick()
    clock.advance(0.8)
    engine.tick()
    assert engine.sm.state == State.COUNTDOWN  # lead capped to 2 s → not before t=1

    clock.advance(0.4)
    engine.tick()
    assert engine.sm.state == State.PREVIEW


# --- why printing is not offered --------------------------------------------
#
# From the first real event: the print button simply vanished when the event
# quota ran out. No message anywhere, and the search for the cause took a while.


def _to_preview(engine, clock, duration=1):
    engine.start()
    engine.select_background("none")
    _run_countdown(engine, clock, duration=duration)
    assert engine.sm.state == State.PREVIEW


def test_the_exhausted_quota_says_so(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=1, printing__max_per_event=0)
    _to_preview(engine, clock)

    session = engine.build_status()["session"]
    assert session["print_allowed"] is False
    assert session["print_hint"] == "Das Druckkontingent für heute ist aufgebraucht"


def test_an_unavailable_printer_names_its_problem(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=1)
    engine.backends.printer.set_reason("media_empty")
    _to_preview(engine, clock)

    session = engine.build_status()["session"]
    assert session["print_allowed"] is False
    assert session["print_hint"] == "Kein Papier"


def test_nothing_is_said_while_printing_works(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=1)
    _to_preview(engine, clock)

    session = engine.build_status()["session"]
    assert session["print_allowed"] is True
    assert session["print_hint"] is None


def test_the_admin_sees_the_quota_before_it_runs_out(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=1, printing__max_per_event=50)
    status = engine.printer_status()
    assert status["quota_total"] == 50
    assert status["quota_used"] == 0
