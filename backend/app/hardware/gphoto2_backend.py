"""Real DSLR capture via python-gphoto2 (milestone M5).

The shutter is driven here; the camera handle itself belongs to
:mod:`app.hardware.gphoto2_session`, which the live preview borrows too. Two
verified essentials (see the M5 memory):

- the OS must not let gvfs claim the camera (handled in deploy/setup.sh);
- autofocus must not block the shutter — ``autofocus=off`` fires immediately with
  the current (manual) focus; ``before_capture`` drives AF first but still fires.

What comes back is not always a JPEG: a Sony a7 IV set to RAW+JPEG hands us the
``.ARW`` path first. ``image_quality`` from the config prevents that, and if the
camera ignores the setting the JPEG is picked up from the following file event.
"""

from __future__ import annotations

import io
import logging
import time

from PIL import Image

from app.config import Config
from app.hardware.base import CaptureResult
from app.hardware.discovery import DetectedCamera
from app.hardware.gphoto2_lock import CAMERA_LOCK
from app.hardware.gphoto2_session import CameraSession, get_session, import_gphoto2

log = logging.getLogger("fotobox.camera")

_AVAILABILITY_TTL = 2.0  # seconds; avoid hammering USB on every status poll
_JPEG_MAGIC = b"\xff\xd8\xff"
_JPEG_SUFFIXES = (".jpg", ".jpeg")


class Gphoto2Camera:
    def __init__(
        self, config: Config, selected: DetectedCamera | None, session: CameraSession | None = None
    ) -> None:
        self._config = config
        self._selected = selected
        self._session = session if session is not None else get_session(config, selected)
        self._available = selected is not None
        self._checked_at = 0.0

    # --- protocol -----------------------------------------------------------

    def available(self) -> bool:
        now = time.monotonic()
        if now - self._checked_at <= _AVAILABILITY_TTL:
            return self._available
        # Never probe the USB device while a capture or a live-view frame owns it —
        # that collision is what used to wedge the camera. A camera that is exposing
        # right now is obviously there, so the cached answer is the correct one.
        if not CAMERA_LOCK.acquire(blocking=False):
            return self._available
        try:
            # Always ask the bus, never the handle: after a battery change the
            # camera comes back under a new USB device number, and our still-open
            # handle would keep claiming "da" until a photo failed with -52.
            self._available = self._detect()
            self._checked_at = now
        finally:
            CAMERA_LOCK.release()
        return self._available

    def model(self) -> str | None:
        if self._selected is None:
            return None
        return self._selected.model if self.available() else None

    def capture(self) -> CaptureResult:
        timeout = self._config.hardware.camera.capture_timeout_seconds
        with self._session.use(timeout=timeout) as camera:
            try:
                gp = import_gphoto2()
                self._prepare_focus(gp, camera)
                jpeg = self._trigger_and_download(gp, camera)
            except Exception:
                # Something went wrong on the wire: drop the handle so the next
                # attempt starts from a fresh init instead of inheriting a broken
                # session. Done while we still hold the lock (it is reentrant), so
                # a busy camera never makes the error path wait on someone else.
                self._session.invalidate()
                raise
        width, height = _jpeg_size(jpeg)
        return CaptureResult(
            jpeg=jpeg,
            width=width,
            height=height,
            camera_model=self._selected.model if self._selected else None,
        )

    # --- internals ----------------------------------------------------------

    def _detect(self) -> bool:
        try:
            gp = import_gphoto2()
            detected = list(gp.Camera.autodetect())
        except Exception:
            return False
        if self._selected is not None and self._selected.port:
            return any(port == self._selected.port for _, port in detected)
        return len(detected) > 0

    def _set_widget(self, gp, camera, name: str, value) -> bool:
        return self._session.set_widget(camera, name, value)

    def _prepare_focus(self, gp, camera) -> None:
        # ``autofocus=off`` is set once when the session opens; only the AF-first
        # mode has to touch the camera before every shot.
        if self._config.hardware.camera.autofocus == "before_capture":
            # Try to focus, but never let it block the shutter later.
            self._set_widget(gp, camera, "autofocus", "On")
            self._set_widget(gp, camera, "autofocusdrive", 1)

    def _trigger_and_download(self, gp, camera) -> bytes:
        try:
            path = camera.capture(gp.GP_CAPTURE_IMAGE)
        except Exception:
            # AF-priority may still refuse; fall back to firing without focus.
            self._set_widget(gp, camera, "autofocus", "Off")
            path = camera.capture(gp.GP_CAPTURE_IMAGE)
        if _is_jpeg_name(path.name):
            jpeg = self._download(gp, camera, path.folder, path.name)
            if jpeg.startswith(_JPEG_MAGIC):
                return jpeg
            log.warning("Kamera lieferte %s ohne JPEG-Inhalt — warte auf das JPEG", path.name)
        else:
            # RAW+JPEG: the RAW arrives first and is useless here, so it is not even
            # downloaded (35 MB over USB). The JPEG follows as its own file event.
            log.info("Kamera lieferte %s (RAW) — warte auf das JPEG", path.name)
        jpeg = self._wait_for_jpeg(gp, camera)
        if jpeg is None:
            raise RuntimeError(
                f"Kamera lieferte kein JPEG (nur {path.name}). "
                "Bildqualität an der Kamera auf JPEG stellen."
            )
        return jpeg

    def _download(self, gp, camera, folder: str, name: str) -> bytes:
        camera_file = camera.file_get(folder, name, gp.GP_FILE_TYPE_NORMAL)
        data = bytes(camera_file.get_data_and_size())
        # Tidy up the card so it does not fill during a long event. Not every body
        # allows deletion (Sony refuses), hence the bare except.
        try:
            camera.file_delete(folder, name)
        except Exception:
            pass
        return data

    def _wait_for_jpeg(self, gp, camera) -> bytes | None:
        """Collect file events until a JPEG shows up or the capture timeout runs out."""
        deadline = time.monotonic() + self._config.hardware.camera.capture_timeout_seconds
        while True:
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                return None
            event_type, event_data = camera.wait_for_event(remaining_ms)
            if event_type == gp.GP_EVENT_TIMEOUT:
                return None
            if event_type != gp.GP_EVENT_FILE_ADDED or not _is_jpeg_name(event_data.name):
                continue
            data = self._download(gp, camera, event_data.folder, event_data.name)
            if data.startswith(_JPEG_MAGIC):
                return data


def _is_jpeg_name(name: str) -> bool:
    return name.lower().endswith(_JPEG_SUFFIXES)


def _jpeg_size(jpeg: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg)) as image:
        return image.size
