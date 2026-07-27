"""Camera discovery: enumerate attached capture cameras (DSLRs) and preview
(video) devices, so main and preview camera can be chosen independently.

Two device classes:
- capture (DSLR via gphoto2) → triggers the shutter
- preview (V4L2/CSI video) → the live MJPEG stream

Mocks simulate several devices for development; the real discovery uses
python-gphoto2 for DSLRs and enumerates ``/dev/video*`` for preview cameras.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class DetectedCamera:
    id: str  # stable handle, e.g. the gphoto2 port "usb:001,005"
    model: str  # "Nikon DSC D7200"
    port: str | None  # gphoto2 port
    source: str  # "gphoto2" | "mock"


@dataclass(frozen=True)
class DetectedPreview:
    id: str  # stable handle, e.g. "/dev/video0" or "csi0"
    name: str  # "Pi Camera Module 3"
    device: str  # V4L2 path or CSI id
    backend: str  # "picamera2" | "v4l2" | "mock"


@runtime_checkable
class Discovery(Protocol):
    def cameras(self) -> list[DetectedCamera]: ...

    def previews(self) -> list[DetectedPreview]: ...


class MockDiscovery:
    """Simulated devices for development: two DSLRs and two preview cameras."""

    def __init__(
        self,
        cameras: list[DetectedCamera] | None = None,
        previews: list[DetectedPreview] | None = None,
    ) -> None:
        self._cameras = cameras if cameras is not None else list(_DEFAULT_MOCK_CAMERAS)
        self._previews = previews if previews is not None else list(_DEFAULT_MOCK_PREVIEWS)

    def cameras(self) -> list[DetectedCamera]:
        return list(self._cameras)

    def previews(self) -> list[DetectedPreview]:
        return list(self._previews)


_DEFAULT_MOCK_CAMERAS = (
    DetectedCamera(id="usb:001,004", model="Nikon DSC D7200", port="usb:001,004", source="mock"),
    DetectedCamera(id="usb:001,005", model="Sony Alpha 6000", port="usb:001,005", source="mock"),
)

_DEFAULT_MOCK_PREVIEWS = (
    DetectedPreview(id="csi0", name="Pi Camera Module 3", device="csi0", backend="mock"),
    DetectedPreview(id="/dev/video0", name="Logitech C920", device="/dev/video0", backend="mock"),
)
