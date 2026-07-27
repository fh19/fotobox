"""Hardware backends.

All hardware access lives here (CLAUDE.md rule 2). Business logic talks only to
the ``CameraBackend``, ``PrinterBackend`` and ``PreviewBackend`` protocols — no
``subprocess``, ``gphoto2`` or ``pycups`` anywhere else.
"""

from app.hardware.base import (
    Backends,
    CameraBackend,
    CaptureResult,
    PreviewBackend,
    PrinterBackend,
    PrinterState,
)
from app.hardware.discovery import DetectedCamera, DetectedPreview, Discovery
from app.hardware.factory import CameraManager, create_backends, create_discovery

__all__ = [
    "Backends",
    "CameraBackend",
    "CameraManager",
    "CaptureResult",
    "DetectedCamera",
    "DetectedPreview",
    "Discovery",
    "PreviewBackend",
    "PrinterBackend",
    "PrinterState",
    "create_backends",
    "create_discovery",
]
