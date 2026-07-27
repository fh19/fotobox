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
