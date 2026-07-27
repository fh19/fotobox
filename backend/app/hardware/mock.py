"""Mock hardware for development on the workstation (FOTOBOX_HARDWARE=mock).

Only these mocks are tested; the real backends are exercised on the Pi
(CLAUDE.md tests section). The mocks are fully controllable so tests can force a
disconnected camera or an unavailable printer.
"""

from __future__ import annotations

from app.hardware.base import CaptureResult, PrinterState
from app.hardware.synthetic import greenscreen_jpeg

# Portrait 2:3 "DSLR" capture and a landscape live-preview frame, generated once.
_CAPTURE_W, _CAPTURE_H = 1200, 1800
_PREVIEW_W, _PREVIEW_H = 1280, 720
_PREVIEW_FRAME = greenscreen_jpeg(_PREVIEW_W, _PREVIEW_H)


class MockCamera:
    def __init__(self, model: str = "Mock DSLR", available: bool = True) -> None:
        self._model = model
        self._available = available
        self.captures = 0

    def set_available(self, value: bool) -> None:
        self._available = value

    def available(self) -> bool:
        return self._available

    def model(self) -> str | None:
        return self._model if self._available else None

    def capture(self) -> CaptureResult:
        if not self._available:
            raise RuntimeError("camera_disconnected")
        jpeg = greenscreen_jpeg(_CAPTURE_W, _CAPTURE_H, seed=self.captures)
        self.captures += 1
        return CaptureResult(
            jpeg=jpeg, width=_CAPTURE_W, height=_CAPTURE_H, camera_model=self._model
        )


class MockPreview:
    def __init__(self, available: bool = True) -> None:
        self._available = available

    def set_available(self, value: bool) -> None:
        self._available = value

    def available(self) -> bool:
        return self._available

    def frame(self) -> bytes:
        return _PREVIEW_FRAME


class MockPrinter:
    def __init__(self, available: bool = True, remaining: int = 108) -> None:
        self._available = available
        self._paused = False
        self._remaining = remaining
        self._next_job_id = 1

    def set_available(self, value: bool) -> None:
        self._available = value

    def set_paused(self, value: bool) -> None:
        self._paused = value

    def available(self) -> bool:
        return self._available and not self._paused

    def state(self) -> PrinterState:
        if not self._available:
            return PrinterState.OFFLINE
        if self._paused:
            return PrinterState.ERROR
        return PrinterState.IDLE

    def paused(self) -> bool:
        return self._paused

    def prints_remaining_estimate(self) -> int | None:
        return self._remaining

    def submit(self, path: str) -> int:
        if not self.available():
            raise RuntimeError("printer_unavailable")
        job_id = self._next_job_id
        self._next_job_id += 1
        if self._remaining > 0:
            self._remaining -= 1
        return job_id

    # --- admin operations ---------------------------------------------------

    def resume(self) -> None:
        self._paused = False
        self._available = True

    def cancel_all(self) -> None:
        pass

    def reset_counter(self) -> None:
        self._remaining = 108

    def queue_length(self) -> int:
        return 0
