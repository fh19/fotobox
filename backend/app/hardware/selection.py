"""Resolve the configured selection against the detected devices.

Capture camera: ``select`` is "auto" (first detected) or a model name / port.
Preview camera: ``backend`` narrows the class ("auto" = any), ``device`` is "auto"
(first) or a specific device/id.
"""

from __future__ import annotations

import logging

from app.hardware.discovery import DetectedCamera, DetectedPreview

log = logging.getLogger("fotobox.camera")


def resolve_camera(select: str, cameras: list[DetectedCamera]) -> DetectedCamera | None:
    """Pick the capture camera. ``select`` is a preference, not a demand.

    A pinned port goes stale the moment the camera is switched off and on (it
    comes back under a new USB device number), and a pinned model goes stale when
    the body is swapped. Neither should send anyone into the admin menu, so an
    attached camera is used even when it is not the one that was asked for.
    """
    if not cameras:
        return None
    if select == "auto":
        return cameras[0]
    for camera in cameras:
        if select in (camera.id, camera.model, camera.port):
            return camera
    log.warning("Kamera %s nicht gefunden, nutze %s", select, cameras[0].model)
    return cameras[0]


def resolve_preview(
    device: str, backend: str, previews: list[DetectedPreview]
) -> DetectedPreview | None:
    """Pick a preview device. ``backend``/``device`` are preferences, not demands.

    A configured backend that is not attached must not leave the box without a
    live image: with ``backend: gphoto2`` saved and the DSLR unplugged, the
    preview went dark *and* photos stopped working, because capture falls back to
    the preview camera. So the preference is tried first and anything else that is
    attached is used rather than nothing.

    The DSLR is the exception and is **never** chosen automatically. On a mirrored
    body live view flips the mirror up and empties the battery in well under an
    hour, so it takes an explicit ``backend: gphoto2`` or the camera's port as
    ``device`` — a deliberate choice, sensible on a mirrorless body.
    """
    if not previews:
        return None
    wants_dslr = backend == "gphoto2" or any(
        p.backend == "gphoto2" and device in (p.id, p.device) for p in previews
    )
    usable = previews if wants_dslr else [p for p in previews if p.backend != "gphoto2"]
    if not usable:
        return None
    preferred = usable
    if backend not in ("auto", "mock"):
        preferred = [p for p in usable if p.backend == backend]
    for candidates in (preferred, usable):
        if not candidates:
            continue
        if device == "auto":
            return candidates[0]
        for preview in candidates:
            if device in (preview.id, preview.device):
                return preview
    # Neither the wanted backend nor the wanted device is here — take what is.
    log.warning("Vorschau %s/%s nicht gefunden, nutze %s", backend, device, usable[0].device)
    return usable[0]
