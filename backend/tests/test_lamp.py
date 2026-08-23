"""The photo lamp follows the box's mood (Optimierungen2.md).

"wenn Bildschirmschoner (Show mit den bisherigen Bildern) läuft oder im
Galleriemodus => Lampe aus, nur im Fotomodus => Lampe an."

Only the mock exists so far; the switching hardware is still being chosen. That
is the point of the protocol — the behaviour can be finished and tested before
any relay is bought.
"""

from __future__ import annotations

from app.clock import FakeClock
from app.hardware.base import LampBackend
from app.hardware.mock import MockLamp
from app.main import create_app
from tests.conftest import make_config


def _box(tmp_path, **overrides):
    clock = FakeClock()
    app = create_app(make_config(tmp_path, hardware__lamp__backend="mock", **overrides), clock)
    return app.state.engine, clock, app.state.engine.backends.lamp


def test_the_mock_satisfies_the_protocol():
    assert isinstance(MockLamp(), LampBackend)


def test_no_lamp_configured_means_nothing_happens(tmp_path):
    """The default: most boxes have no lamp wired at all."""
    app = create_app(make_config(tmp_path), FakeClock())
    assert app.state.engine.backends.lamp is None
    app.state.engine.sm.poll()  # must not raise


def test_the_slideshow_switches_the_lamp_off(tmp_path):
    engine, clock, lamp = _box(tmp_path)
    engine.sm.start()  # a session turns it on
    engine.sm.cancel()  # back to IDLE, and the quiet clock starts there
    assert lamp.is_on() is True

    clock.advance(engine.config.screensaver.after_seconds + 1)
    engine.sm.poll()
    assert str(engine.sm.state) == "SCREENSAVER"
    assert lamp.is_on() is False
    assert lamp.calls == [True, False]


def test_waking_switches_it_back_on(tmp_path):
    engine, clock, lamp = _box(tmp_path)
    engine.sm.start()
    engine.sm.cancel()
    clock.advance(engine.config.screensaver.after_seconds + 1)
    engine.sm.poll()
    assert lamp.is_on() is False

    engine.wake_from_screensaver()
    assert lamp.is_on() is True


def test_it_is_not_switched_again_when_nothing_changed(tmp_path):
    """Every state change asks; a relay should not chatter through a session."""
    engine, clock, lamp = _box(tmp_path)
    engine.sm.start()
    engine.sm.select_background("none", "none")  # BACKGROUND_SELECT -> COUNTDOWN
    assert lamp.calls == [True]


def test_the_states_are_configurable(tmp_path):
    """Someone may want it dark during the preview too — that is a config
    question, not a code change."""
    engine, clock, lamp = _box(tmp_path, hardware__lamp__off_states=["SCREENSAVER", "PREVIEW"])
    engine.sm.start()
    assert lamp.is_on() is True

    engine.sm.select_background("none", "none")  # -> COUNTDOWN
    clock.advance(engine.config.countdown.duration_seconds + 1)
    engine.sm.poll()  # -> CAPTURE
    engine.sm.capture_succeeded(1)  # -> PROCESSING
    engine.sm.processing_succeeded()  # -> PREVIEW
    assert lamp.is_on() is False


def test_a_lamp_that_refuses_never_costs_the_photo(tmp_path):
    """Rule 8: guests are mid-session; a stuck relay is a log line, not an end."""
    engine, clock, lamp = _box(tmp_path)
    lamp.set_available(False)

    engine.sm.start()  # must not raise
    assert str(engine.sm.state) == "BACKGROUND_SELECT"
    assert lamp.calls == []
