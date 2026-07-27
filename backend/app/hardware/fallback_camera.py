"""Capture backend that falls back to the preview camera when the DSLR is gone.

Wraps the real DSLR capture backend plus the preview camera. While the DSLR is
available it behaves exactly like the DSLR. If the DSLR is unavailable (dead
battery, unplugged) or a trigger fails, it grabs a still frame from the preview
camera so the box keeps taking (lower-quality) photos instead of erroring out.

It satisfies the ``CameraBackend`` protocol, so the state machine / engine never
know a fallback happened — they just call ``capture()``.
"""

from __future__ import annotations

import io
import logging

from app.hardware.base import CaptureResult

log = logging.getLogger("fotobox.camera")

FALLBACK_MODEL = "Vorschaukamera (Ersatz)"


def _jpeg_size(jpeg: bytes) -> tuple[int, int]:
    from PIL import Image

    with Image.open(io.BytesIO(jpeg)) as image:
        return image.size


class FallbackCamera:
    def __init__(self, primary, preview) -> None:
        self._primary = primary
        self._preview = preview

    def available(self) -> bool:
        return self._primary.available() or self._preview.available()

    def model(self) -> str | None:
        if self._primary.available():
            return self._primary.model()
        if self._preview.available():
            return FALLBACK_MODEL
        return None

    def using_fallback(self) -> bool:
        """True when the DSLR is gone and the preview camera would be used."""
        return not self._primary.available() and self._preview.available()

    def capture(self) -> CaptureResult:
        if self._primary.available():
            try:
                return self._primary.capture()
            except Exception as exc:  # trigger failed mid-capture
                if not self._preview.available():
                    raise
                log.warning("DSLR-Auslösung fehlgeschlagen, nutze Vorschaukamera: %s", exc)
        return self._capture_from_preview()

    def _capture_from_preview(self) -> CaptureResult:
        jpeg = self._preview.frame()
        width, height = _jpeg_size(jpeg)
        return CaptureResult(jpeg=jpeg, width=width, height=height, camera_model=FALLBACK_MODEL)
