"""Timeouts, exercised with a fake clock (no sleep) — milestone M1 acceptance."""

from __future__ import annotations

import pytest

from app.clock import FakeClock
from app.state_machine import StateMachine
from app.states import State
from tests.conftest import make_config


def _machine(tmp_path, **overrides):
    config = make_config(tmp_path, **overrides)
    clock = FakeClock()
    events: list = []
    machine = StateMachine(config, clock, lambda t, p: events.append((t, p)))
    return machine, clock, config


def test_background_select_times_out_to_idle(tmp_path):
    machine, clock, config = _machine(tmp_path)
    machine.start()
    assert machine.state == State.BACKGROUND_SELECT

    clock.advance(config.timeouts.background_select_seconds - 0.1)
    machine.poll()
    assert machine.state == State.BACKGROUND_SELECT  # not yet

    clock.advance(0.2)
    machine.poll()
    assert machine.state == State.IDLE


def test_preview_times_out_to_idle(tmp_path):
    machine, clock, config = _machine(tmp_path)
    # Drive to PREVIEW via the allowed edges.
    machine.start()
    machine.select_background("none", "none")
    machine._set_state(State.CAPTURE)  # COUNTDOWN -> CAPTURE (countdown expiry)
    machine.capture_succeeded(1)  # CAPTURE -> PROCESSING
    assert machine.state == State.PROCESSING
    machine.processing_succeeded()
    assert machine.state == State.PREVIEW

    clock.advance(config.timeouts.preview_seconds + 1)
    machine.poll()
    assert machine.state == State.IDLE


def test_capture_times_out_to_error(tmp_path):
    machine, clock, config = _machine(tmp_path)
    machine.start()
    machine.select_background("none", "none")
    # Now in COUNTDOWN; force the CAPTURE state as the engine would.
    machine._set_state(State.CAPTURE)

    clock.advance(config.timeouts.capture_seconds + 1)
    machine.poll()
    assert machine.state == State.ERROR
    assert machine.error.code == "camera_timeout"


def test_processing_times_out_to_error(tmp_path):
    machine, clock, config = _machine(tmp_path)
    machine.start()
    machine.select_background("none", "none")
    machine._set_state(State.CAPTURE)
    machine.capture_succeeded(1)
    assert machine.state == State.PROCESSING

    clock.advance(config.timeouts.processing_seconds + 1)
    machine.poll()
    assert machine.state == State.ERROR
    assert machine.error.code == "pipeline_failed"


def test_error_times_out_to_idle(tmp_path):
    machine, clock, config = _machine(tmp_path)
    machine.start()
    machine.select_background("none", "none")
    machine._set_state(State.CAPTURE)
    machine.capture_failed("capture_failed")
    assert machine.state == State.ERROR

    clock.advance(config.timeouts.error_seconds + 1)
    machine.poll()
    assert machine.state == State.IDLE


def test_countdown_last_second_is_not_cancelable(tmp_path):
    from app.state_machine import ActionRejected

    machine, clock, config = _machine(tmp_path, countdown__duration_seconds=5)
    machine.start()
    machine.select_background("none", "none")
    assert machine.state == State.COUNTDOWN

    # Advance into the grace window (last second).
    grace = config.timeouts.countdown_cancel_grace_seconds
    clock.advance(config.countdown.duration_seconds - grace)
    with pytest.raises(ActionRejected):
        machine.cancel()
