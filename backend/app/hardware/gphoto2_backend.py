"""Real DSLR capture via python-gphoto2 (milestone M5).

Only the shutter is driven here — the live preview comes from a separate camera
(CLAUDE.md rule 1). ``python-gphoto2`` is imported lazily so the rest of the app
runs on machines without it. Two verified essentials (see the M5 memory):

- the OS must not let gvfs claim the camera (handled in deploy/setup.sh);
- autofocus must not block the shutter — ``autofocus=off`` fires immediately with
  the current (manual) focus; ``before_capture`` drives AF first but still fires.
"""

from __future__ import annotations

import io
import logging
import time

from PIL import Image

from app.config import Config
from app.hardware.base import CaptureResult
from app.hardware.discovery import DetectedCamera

log = logging.getLogger("fotobox.camera")

_AVAILABILITY_TTL = 2.0  # seconds; avoid hammering USB on every status poll


class Gphoto2Camera:
    def __init__(self, config: Config, selected: DetectedCamera | None) -> None:
        self._config = config
        self._selected = selected
        self._available = selected is not None
        self._checked_at = 0.0

    # --- protocol -----------------------------------------------------------

    def available(self) -> bool:
        now = time.monotonic()
        if now - self._checked_at > _AVAILABILITY_TTL:
            self._available = self._detect()
            self._checked_at = now
        return self._available

    def model(self) -> str | None:
        if self._selected is None:
            return None
        return self._selected.model if self.available() else None

    def capture(self) -> CaptureResult:
        gp = _import_gphoto2()
        camera = self._open(gp)
        try:
            self._prepare_focus(gp, camera)
            jpeg = self._trigger_and_download(gp, camera)
        finally:
            camera.exit()
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
            gp = _import_gphoto2()
            detected = list(gp.Camera.autodetect())
        except Exception:
            return False
        if self._selected is not None and self._selected.port:
            return any(port == self._selected.port for _, port in detected)
        return len(detected) > 0

    def _open(self, gp):
        camera = gp.Camera()
        # Address the chosen camera by its port when one is selected.
        if self._selected is not None and self._selected.port:
            port_info_list = gp.PortInfoList()
            port_info_list.load()
            index = port_info_list.lookup_path(self._selected.port)
            if index >= 0:
                camera.set_port_info(port_info_list[index])
        camera.init()
        return camera

    def _set_widget(self, gp, camera, name: str, value) -> bool:
        try:
            config = camera.get_config()
            widget = config.get_child_by_name(name)
            widget.set_value(value)
            camera.set_config(config)
            return True
        except Exception as exc:  # widget missing / read-only on this body
            log.debug("Kamera-Einstellung %s=%s nicht möglich: %s", name, value, exc)
            return False

    def _prepare_focus(self, gp, camera) -> None:
        if self._config.hardware.camera.autofocus == "before_capture":
            # Try to focus, but never let it block the shutter later.
            self._set_widget(gp, camera, "autofocus", "On")
            self._set_widget(gp, camera, "autofocusdrive", 1)
        else:
            self._set_widget(gp, camera, "autofocus", "Off")

    def _trigger_and_download(self, gp, camera) -> bytes:
        try:
            path = camera.capture(gp.GP_CAPTURE_IMAGE)
        except Exception:
            # AF-priority may still refuse; fall back to firing without focus.
            self._set_widget(gp, camera, "autofocus", "Off")
            path = camera.capture(gp.GP_CAPTURE_IMAGE)
        camera_file = camera.file_get(path.folder, path.name, gp.GP_FILE_TYPE_NORMAL)
        jpeg = bytes(camera_file.get_data_and_size())
        # Tidy up the card so it does not fill during a long event.
        try:
            camera.file_delete(path.folder, path.name)
        except Exception:
            pass
        return jpeg


def _import_gphoto2():
    try:
        import gphoto2 as gp
    except Exception as exc:  # not installed on the dev machine
        raise RuntimeError(f"python-gphoto2 nicht verfügbar: {exc}") from exc
    return gp


def _jpeg_size(jpeg: bytes) -> tuple[int, int]:
    with Image.open(io.BytesIO(jpeg)) as image:
        return image.size
