"""Hardware protocols and shared value types.

These protocols are the entire surface the business logic is allowed to use.
Real (gphoto2/picamera2/cups) and mock implementations both satisfy them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class CaptureResult:
    """A single frame captured from the DSLR."""

    jpeg: bytes
    width: int
    height: int
    camera_model: str | None


class PrinterState(str, Enum):
    IDLE = "idle"
    PRINTING = "printing"
    ERROR = "error"
    OFFLINE = "offline"

    def __str__(self) -> str:
        return self.value


@runtime_checkable
class CameraBackend(Protocol):
    """The DSLR. Used only to trigger a capture (CLAUDE.md rule 1)."""

    def available(self) -> bool: ...

    def model(self) -> str | None: ...

    def capture(self) -> CaptureResult:
        """Trigger the shutter and return the downloaded JPEG. May raise on failure."""
        ...


@runtime_checkable
class PreviewBackend(Protocol):
    """The separate live-preview camera (Pi Camera Module 3), never the DSLR."""

    def available(self) -> bool: ...

    def frame(self) -> bytes:
        """A single JPEG frame for the MJPEG stream."""
        ...


@runtime_checkable
class PrinterBackend(Protocol):
    """The Selphy CP1500 via CUPS."""

    def available(self) -> bool: ...

    def state(self) -> PrinterState: ...

    def paused(self) -> bool: ...

    def submit(self, path: str) -> int:
        """Hand a print job to CUPS and return the job id. May raise on failure."""
        ...

    def job_state(self, job_id: int) -> str | None:
        """State of a submitted job: ``pending``, ``done``, ``failed`` or
        ``cancelled``; ``None`` when it cannot be determined (the job may have
        been purged from the CUPS history). The engine counts only ``done``."""
        ...

    # Admin operations.
    def resume(self) -> None:
        """Re-enable the queue after a paper/band change (cupsenable)."""
        ...

    def cancel_all(self) -> None: ...

    def queue_length(self) -> int: ...


@runtime_checkable
class LampBackend(Protocol):
    """The photo lamp, switched with the box's mood.

    "wenn Bildschirmschoner läuft oder im Galleriemodus => Lampe aus, nur im
    Fotomodus => Lampe an" (Optimierungen2.md). Whether that is a USB-controlled
    mains socket, a relay on a GPIO or nothing at all is none of the engine's
    business — it only ever says on or off.
    """

    def available(self) -> bool: ...

    def is_on(self) -> bool: ...

    def set(self, on: bool) -> None:
        """Switch the lamp. May raise; a lamp must never end a session."""
        ...


@dataclass
class Backends:
    """The backends bundled together for wiring."""

    camera: CameraBackend
    preview: PreviewBackend
    printer: PrinterBackend
    lamp: LampBackend | None = None
