"""Resolve the configured selection against the detected devices.

Capture camera: ``select`` is "auto" (first detected) or a model name / port.
Preview camera: ``backend`` narrows the class ("auto" = any), ``device`` is "auto"
(first) or a specific device/id.
"""

from __future__ import annotations

import logging

from app.hardware.discovery import DetectedCamera, DetectedPreview

log = logging.getLogger("fotobox.preview")


def resolve_camera(select: str, cameras: list[DetectedCamera]) -> DetectedCamera | None:
    if not cameras:
        return None
    if select == "auto":
        return cameras[0]
    for camera in cameras:
        if select in (camera.id, camera.model, camera.port):
            return camera
    return None


def resolve_preview(
    device: str, backend: str, previews: list[DetectedPreview]
) -> DetectedPreview | None:
    """Pick a preview device. ``backend``/``device`` are preferences, not demands.

    A configured backend that is not attached must not leave the box without a
    live image: with ``backend: gphoto2`` saved and the DSLR unplugged, the
    preview went dark *and* photos stopped working, because capture falls back to
    the preview camera. So the preference is tried first and anything detected is
    used rather than nothing.
    """
    if not previews:
        return None
    preferred = previews
    if backend not in ("auto", "mock"):
        preferred = [p for p in previews if p.backend == backend]
    for candidates in (preferred, previews):
        if not candidates:
            continue
        if device == "auto":
            return candidates[0]
        for preview in candidates:
            if device in (preview.id, preview.device):
                return preview
    # Neither the wanted backend nor the wanted device is here — take what is.
    log.warning("Vorschau %s/%s nicht gefunden, nutze %s", backend, device, previews[0].device)
    return previews[0]
