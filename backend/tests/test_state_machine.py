"""Pure state-machine behaviour: transitions, guards, InvalidTransition."""

from __future__ import annotations

import pytest

from app.clock import FakeClock
from app.state_machine import ActionRejected, StateMachine
from app.states import ALLOWED_TRANSITIONS, InvalidTransition, State


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def __call__(self, event_type: str, payload: dict) -> None:
        self.events.append((event_type, payload))

    def states(self) -> list[str]:
        return [p["new"] for t, p in self.events if t == "state_changed"]


@pytest.fixture
def sm(tmp_path):
    from tests.conftest import make_config

    config = make_config(tmp_path)
    clock = FakeClock()
    recorder = Recorder()
    machine = StateMachine(config, clock, recorder)
    return machine, clock, recorder, config


def test_starts_in_idle(sm):
    machine, *_ = sm
    assert machine.state == State.IDLE
    assert machine.session is None


def test_start_enters_background_select(sm):
    machine, _clock, recorder, _config = sm
    machine.start()
    assert machine.state == State.BACKGROUND_SELECT
    assert recorder.states() == ["BACKGROUND_SELECT"]


def test_start_skips_selection_when_disabled(tmp_path):
    from tests.conftest import make_config

    config = make_config(tmp_path, ui__background_select_enabled=False)
    machine = StateMachine(config, FakeClock(), Recorder())
    machine.start()
    assert machine.state == State.COUNTDOWN


def test_start_twice_is_rejected(sm):
    machine, *_ = sm
    machine.start()
    with pytest.raises(ActionRejected) as exc:
        machine.start()
    assert exc.value.code == "invalid_state"


def test_cancel_from_background_select(sm):
    machine, *_ = sm
    machine.start()
    machine.cancel()
    assert machine.state == State.IDLE
    assert machine.session is None


def test_cancel_in_idle_is_rejected(sm):
    machine, *_ = sm
    with pytest.raises(ActionRejected):
        machine.cancel()


def test_invalid_transition_raises(sm):
    machine, *_ = sm
    # PREVIEW is not reachable directly from IDLE.
    with pytest.raises(InvalidTransition):
        machine._set_state(State.PREVIEW)


def test_every_undocumented_transition_raises(sm):
    machine, *_ = sm
    for source in State:
        for target in State:
            machine._state = source
            if (source, target) in ALLOWED_TRANSITIONS:
                continue
            with pytest.raises(InvalidTransition):
                machine._set_state(target)


def test_full_transition_table_is_accepted(sm):
    machine, *_ = sm
    for source, target in ALLOWED_TRANSITIONS:
        machine._state = source
        if target == State.COUNTDOWN:
            machine._session = machine._session or _dummy_session(machine)
        machine._set_state(target)
        assert machine.state == target


def _dummy_session(machine):
    from app.state_machine import Session

    machine._session = Session()
    return machine._session


# --- screensaver -------------------------------------------------------------
#
# "wenn die Box für zB 5min nicht benutzt wurde, sollen die bisherigen Bilder in
# zufälliger Reihenfolge auf dem Schirm angezeigt werden."


def test_idle_turns_into_the_slideshow_after_the_quiet_time(sm):
    machine, clock, recorder, config = sm
    clock.advance(config.screensaver.after_seconds - 1)
    machine.poll()
    assert machine.state == State.IDLE

    clock.advance(2)
    machine.poll()
    assert machine.state == State.SCREENSAVER
    assert recorder.states() == ["SCREENSAVER"]


def test_the_first_touch_only_brings_the_start_screen_back(sm):
    """It must not already take a picture — somebody just wanted to wake it."""
    machine, clock, _recorder, config = sm
    clock.advance(config.screensaver.after_seconds + 1)
    machine.poll()

    machine.wake()
    assert machine.state == State.IDLE
    assert machine.session is None  # nothing started


def test_the_quiet_time_restarts_after_a_session(sm):
    machine, clock, _recorder, config = sm
    clock.advance(config.screensaver.after_seconds + 1)
    machine.poll()
    machine.wake()

    clock.advance(config.screensaver.after_seconds - 1)
    machine.poll()
    assert machine.state == State.IDLE  # the clock started over on waking


def test_the_slideshow_never_times_out(sm):
    """A resting state like IDLE: a timeout could only send it back to a screen
    the box already decided nobody is looking at."""
    machine, clock, _recorder, config = sm
    clock.advance(config.screensaver.after_seconds + 1)
    machine.poll()

    clock.advance(24 * 3600)
    machine.poll()
    assert machine.state == State.SCREENSAVER


def test_the_slideshow_can_be_switched_off(tmp_path):
    from tests.conftest import make_config

    config = make_config(tmp_path, screensaver__enabled=False)
    machine = StateMachine(config, clock := FakeClock(), Recorder())
    clock.advance(10 * 3600)
    machine.poll()
    assert machine.state == State.IDLE


def test_waking_outside_the_slideshow_is_rejected(sm):
    machine, *_ = sm
    with pytest.raises(ActionRejected):
        machine.wake()


def test_a_session_cannot_start_from_the_slideshow(sm):
    """The touch that wakes the box must not run through to a countdown."""
    machine, clock, _recorder, config = sm
    clock.advance(config.screensaver.after_seconds + 1)
    machine.poll()
    with pytest.raises(ActionRejected):
        machine.start()
