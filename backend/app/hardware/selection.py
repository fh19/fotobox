"""Resolve the configured selection against the detected devices.

Capture camera: ``select`` is "auto" (first detected) or a model name / port.
Preview camera: ``backend`` narrows the class ("auto" = any), ``device`` is "auto"
(first) or a specific device/id.
"""

from __future__ import annotations

from app.hardware.discovery import DetectedCamera, DetectedPreview


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
    candidates = previews
    if backend not in ("auto", "mock"):
        candidates = [p for p in candidates if p.backend == backend]
    if not candidates:
        return None
    if device == "auto":
        return candidates[0]
    for preview in candidates:
        if device in (preview.id, preview.device):
            return preview
    return None
