"""The lamp on a GPIO pin.

CLAUDE.md says only the mocks of the hardware backends are tested, not the real
ones. This tests the part that is not hardware: which level goes to the pin, and
that a missing library or a pin somebody else holds leaves a box that still
takes photographs.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from app.hardware.base import LampBackend
from app.hardware.gpio_lamp import GpioLamp


@pytest.fixture
def lgpio(monkeypatch):
    fake = MagicMock()
    fake.gpiochip_open.return_value = 7  # a handle
    monkeypatch.setitem(sys.modules, "lgpio", fake)
    return fake


def test_it_satisfies_the_protocol(lgpio):
    assert isinstance(GpioLamp(17), LampBackend)


def test_the_pin_is_claimed_low(lgpio):
    """A lamp that comes on by itself while the box boots is worse than one
    that stays dark."""
    lamp = GpioLamp(17)
    lgpio.gpio_claim_output.assert_called_once_with(7, 17, 0)
    assert lamp.is_on() is False
    assert lamp.available() is True


def test_switching_writes_the_level(lgpio):
    lamp = GpioLamp(17)
    lamp.set(True)
    lgpio.gpio_write.assert_called_with(7, 17, 1)
    assert lamp.is_on() is True

    lamp.set(False)
    lgpio.gpio_write.assert_called_with(7, 17, 0)
    assert lamp.is_on() is False


def test_active_low_wiring_inverts_everything(lgpio):
    lamp = GpioLamp(17, active_high=False)
    lgpio.gpio_claim_output.assert_called_once_with(7, 17, 1)  # off is high here
    lamp.set(True)
    lgpio.gpio_write.assert_called_with(7, 17, 0)


def test_a_pin_somebody_else_holds_is_not_available(lgpio):
    lgpio.gpio_claim_output.side_effect = OSError("GPIO busy")
    lamp = GpioLamp(17)

    assert lamp.available() is False
    with pytest.raises(RuntimeError):
        lamp.set(True)


def test_without_the_library_the_box_still_runs(monkeypatch):
    """A development machine has no lgpio, and neither has a box where the
    install went wrong. Neither may keep the Fotobox from starting."""
    monkeypatch.setitem(sys.modules, "lgpio", None)
    lamp = GpioLamp(17)
    assert lamp.available() is False


def test_closing_leaves_the_lamp_off(lgpio):
    lamp = GpioLamp(17)
    lamp.set(True)
    lamp.close()
    lgpio.gpio_write.assert_called_with(7, 17, 0)
    lgpio.gpiochip_close.assert_called_once_with(7)
    assert lamp.available() is False
