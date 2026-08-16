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
        # This class is also what a real box gets when no preview device was
        # found at all. Handing out a synthetic picture there froze the kiosk on
        # something that looked like a live image (api-contract: a still frame).
        if not self._available:
            from app.hardware.v4l2_preview import placeholder_frame

            return placeholder_frame()
        return _PREVIEW_FRAME


class MockPrinter:
    def __init__(self, available: bool = True) -> None:
        self._available = available
        self._paused = False
        self._reason: str | None = None
        # Set to True to mimic a supply that is still empty: resume() then leaves
        # the queue stopped, the way CUPS does when the next job fails again.
        self.supply_empty = False
        self._next_job_id = 1
        # Submitted jobs finish right away so mock development shows realistic
        # counters; tests override single jobs via set_job_state().
        self._job_states: dict[int, str] = {}

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

    def reason(self) -> str | None:
        if self._reason is not None:
            return self._reason
        if not self._available:
            return "offline"
        return "stopped" if self._paused else None

    def set_reason(self, value: str | None) -> None:
        """Simulate a paper-out or similar: stops the queue, like CUPS does."""
        self._reason = value
        self._paused = value is not None

    def set_job_state(self, job_id: int, state: str) -> None:
        self._job_states[job_id] = state

    def submit(self, path: str) -> int:
        if not self.available():
            raise RuntimeError("printer_unavailable")
        job_id = self._next_job_id
        self._next_job_id += 1
        self._job_states[job_id] = "done"
        return job_id

    def job_state(self, job_id: int) -> str | None:
        return self._job_states.get(job_id)

    # --- admin operations ---------------------------------------------------

    def resume(self) -> None:
        if self.supply_empty:
            return  # cupsenable runs, the next job fails, the queue stops again
        self._paused = False
        self._available = True
        self._reason = None

    def cancel_all(self) -> None:
        for job_id, state in list(self._job_states.items()):
            if state == "pending":
                self._job_states[job_id] = "cancelled"

    def queue_length(self) -> int:
        return sum(1 for s in self._job_states.values() if s == "pending")
