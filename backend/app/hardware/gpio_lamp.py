"""The photo lamp on a GPIO pin, switching a solid state relay.

The relay in this box is a Panasonic/Matsushita AQ2A2-ZP3: its input is
voltage-driven from 3 to 28 V DC with a built-in 1.6 kΩ resistor, so a pin at
3.3 V pushes about 2 mA through it — far inside what a Pi pin may source.
Nothing stands between the pin and the relay.

``lgpio`` talks to /dev/gpiochip0 through the character device, which needs no
root: the ``gpio`` group owns it. The import is local so a development machine
without the library still starts.
"""

from __future__ import annotations

import logging

log = logging.getLogger("fotobox.lamp")


class GpioLamp:
    def __init__(self, pin: int, active_high: bool = True, chip: int = 0) -> None:
        self._pin = pin
        self._active_high = active_high
        self._on = False
        self._handle = None

        try:
            import lgpio
        except ImportError as exc:  # pragma: no cover - depends on the machine
            log.warning("lgpio fehlt — Lampe bleibt aus: %s", exc)
            return

        self._lgpio = lgpio
        try:
            self._handle = lgpio.gpiochip_open(chip)
            # Claim it low, whatever "low" means for this wiring: a lamp that
            # comes on by itself while the box boots is worse than one that
            # stays dark.
            lgpio.gpio_claim_output(self._handle, pin, self._level(False))
        except Exception as exc:
            log.warning("GPIO %d nicht belegbar — Lampe bleibt aus: %s", pin, exc)
            self._handle = None

    def _level(self, on: bool) -> int:
        return int(on) if self._active_high else int(not on)

    def available(self) -> bool:
        return self._handle is not None

    def is_on(self) -> bool:
        return self._on

    def set(self, on: bool) -> None:
        if self._handle is None:
            raise RuntimeError(f"GPIO {self._pin} nicht verfügbar")
        self._lgpio.gpio_write(self._handle, self._pin, self._level(on))
        self._on = on

    def close(self) -> None:
        if self._handle is None:
            return
        try:
            self._lgpio.gpio_write(self._handle, self._pin, self._level(False))
            self._lgpio.gpiochip_close(self._handle)
        except Exception:  # pragma: no cover - nothing useful left to do
            pass
        self._handle = None
