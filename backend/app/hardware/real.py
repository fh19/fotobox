"""Real hardware discovery and the real preview backend wiring.

The real DSLR capture lives in :mod:`app.hardware.gphoto2_backend`, the printer in
:mod:`app.hardware.cups_printer`, and the V4L2 (USB) preview camera in
:mod:`app.hardware.v4l2_preview`. Discovery of DSLRs (python-gphoto2) and video
devices lives here. picamera2 (Pi Camera Module) is not implemented yet.
"""

from __future__ import annotations

import glob
import os
import re
from pathlib import Path

from app.config import Config
from app.hardware.discovery import DetectedCamera, DetectedPreview
from app.hardware.gphoto2_lock import CAMERA_LOCK

# Pi-internal V4L2 nodes (codec/ISP), not real capture cameras — filtered out.
_NON_CAMERA = ("bcm2835", "codec", "isp", "hevc")


def _video_index(dev: str) -> int:
    match = re.search(r"(\d+)$", dev)
    return int(match.group(1)) if match else 0


def _v4l2_name(dev: str) -> str | None:
    """Human name of a /dev/videoN capture device, or None if it isn't one."""
    node = dev.rsplit("/", 1)[-1]
    try:
        name = Path(f"/sys/class/video4linux/{node}/name").read_text().strip()
    except Exception:
        return f"Videogerät {dev}"
    low = name.lower()
    if not name or any(token in low for token in _NON_CAMERA):
        return None
    return name


class RealDiscovery:
    def __init__(self, config: Config) -> None:
        self._config = config

    def cameras(self) -> list[DetectedCamera]:
        # Under the lock: autodetect claims the USB device, and doing that while a
        # capture holds it wedges the camera (see app.hardware.gphoto2_lock).
        # Blocking is fine here — every caller runs off the event loop.
        with CAMERA_LOCK:
            try:
                import gphoto2 as gp

                return [
                    DetectedCamera(id=port, model=name, port=port, source="gphoto2")
                    for name, port in gp.Camera.autodetect()
                ]
            except Exception:
                return []

    def previews(self) -> list[DetectedPreview]:
        devices = self._video_devices()
        # The DSLR can serve the live view too (gphoto2 capture_preview). Listed
        # last on purpose: "auto" keeps preferring a real preview camera (rule 1),
        # and only falls back to the DSLR when there is no webcam at all.
        devices.extend(
            DetectedPreview(
                id=camera.id, name=camera.model, device=camera.port or camera.id, backend="gphoto2"
            )
            for camera in self.cameras()
        )
        return devices

    def _video_devices(self) -> list[DetectedPreview]:
        # Real USB cameras only (drop Pi codec/ISP nodes), lowest node per physical
        # camera (its capture node), sorted numerically so "auto" picks video0.
        devices: list[DetectedPreview] = []
        seen: set[str] = set()
        for dev in sorted(glob.glob("/dev/video*"), key=_video_index):
            name = _v4l2_name(dev)
            if name is None:
                continue
            node = dev.rsplit("/", 1)[-1]
            try:
                physical = os.path.realpath(f"/sys/class/video4linux/{node}/device")
            except Exception:
                physical = dev
            if physical in seen:
                continue  # another node of a camera we already listed
            seen.add(physical)
            devices.append(DetectedPreview(id=dev, name=name, device=dev, backend="v4l2"))
        return devices


def build_real_preview(config: Config, selected: DetectedPreview, camera: DetectedCamera | None):
    backend = selected.backend if selected is not None else config.hardware.preview.backend
    if backend == "v4l2":
        from app.hardware.v4l2_preview import V4l2Preview

        preview = config.hardware.preview
        device = selected.device if selected is not None else preview.device
        return V4l2Preview(
            device,
            preview.width,
            preview.height,
            preview.fps,
            preview.jpeg_quality,
            preview.idle_after_seconds,
        )
    if backend == "gphoto2":
        # Shares the open camera handle with the shutter — see gphoto2_session.
        from app.hardware.gphoto2_preview import Gphoto2Preview

        return Gphoto2Preview(config, camera)
    raise NotImplementedError("Nur V4L2- und DSLR-Vorschau sind implementiert; picamera2 folgt.")
