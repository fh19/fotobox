"""Pre-capture flash phase and proactive availability push."""

from __future__ import annotations

from app.states import State


def _to_countdown_done(engine, clock, duration=1):
    engine.start()
    engine.select_background("none")
    engine.tick()  # first countdown tick
    clock.advance(duration)
    engine.tick()  # countdown elapsed → CAPTURE


def test_flash_phase_delays_the_shutter(make_engine, clock):
    engine = make_engine(
        countdown__duration_seconds=1, ui__flash_enabled=True, ui__flash_duration_ms=400
    )
    _to_countdown_done(engine, clock, duration=1)
    # In CAPTURE the shutter has NOT fired yet — the screen flash is building up.
    assert engine.sm.state == State.CAPTURE
    assert engine.sm.session.photo_id is None

    clock.advance(0.2)  # still within the flash duration
    engine.tick()
    assert engine.sm.state == State.CAPTURE  # still flashing, not fired

    clock.advance(0.3)  # 0.5 s total > 0.4 s flash → fire now
    engine.tick()
    assert engine.sm.state == State.PREVIEW
    assert engine.sm.session.photo_id == 1


def test_no_flash_fires_immediately(make_engine, clock):
    engine = make_engine(countdown__duration_seconds=1, ui__flash_enabled=False)
    _to_countdown_done(engine, clock, duration=1)
    # Without the flash, CAPTURE → PROCESSING → PREVIEW happens in the same tick.
    assert engine.sm.state == State.PREVIEW


def test_availability_change_pushes_status(make_engine, clock):
    engine = make_engine()
    engine.tick()  # seeds the availability baseline (mock camera available)
    engine._outbox.clear()

    engine.backends.camera.set_available(False)  # camera "vanishes"
    clock.advance(1.1)  # past the 1 s throttle
    engine.tick()
    assert any(m["type"] == "state_changed" for m in engine._outbox)

    engine._outbox.clear()
    engine.backends.camera.set_available(True)  # camera returns
    clock.advance(1.1)
    engine.tick()
    assert any(m["type"] == "state_changed" for m in engine._outbox)


def test_availability_no_push_when_stable(make_engine, clock):
    engine = make_engine()
    engine.tick()
    engine._outbox.clear()
    clock.advance(1.1)
    engine.tick()  # nothing changed → no extra broadcast
    assert engine._outbox == []
