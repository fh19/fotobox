"""The one open gphoto2 camera handle in this process.

Two things forced this into existence, both measured on the Pi with a Sony a7 IV:

1. **Latency.** libgphoto2 makes ILCE bodies wait until 3 s have passed since
   ``init()`` before the first shutter release (``camera_sony_capture`` in
   ``camlibs/ptp2/library.c``). Opening the camera per photo therefore cost
   **4.2 s**; keeping it open makes the same capture take **650 ms**.
2. **Live view.** ``capture_preview()`` delivers a 1024×768 JPEG in 9–34 ms — but
   only from an already initialized camera, and a second ``Camera`` object on the
   same device fails to claim it (``-53``). Preview and shutter must share one
   handle, not open their own.

So exactly one :class:`CameraSession` owns the handle, guarded by
:data:`app.hardware.gphoto2_lock.CAMERA_LOCK`, and both the capture backend and
the live preview borrow it through :meth:`use`.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from app.config import Config
from app.hardware.discovery import DetectedCamera
from app.hardware.gphoto2_lock import CAMERA_LOCK

log = logging.getLogger("fotobox.camera")

_session: CameraSession | None = None


def import_gphoto2():
    try:
        import gphoto2 as gp
    except Exception as exc:  # not installed on the dev machine
        raise RuntimeError(f"python-gphoto2 nicht verfügbar: {exc}") from exc
    return gp


class CameraSession:
    """Owns an initialized camera and hands it out under the lock."""

    def __init__(self, config: Config, selected: DetectedCamera | None) -> None:
        self._config = config
        self._selected = selected
        self._camera = None
        self._settings_applied = False

    @property
    def selected(self) -> DetectedCamera | None:
        return self._selected

    def is_open(self) -> bool:
        return self._camera is not None

    @contextmanager
    def use(self, timeout: float | None = None):
        """Borrow the initialized camera. Raises if the lock cannot be had in time."""
        if not CAMERA_LOCK.acquire(timeout=-1 if timeout is None else timeout):
            raise RuntimeError("Kamera ist noch mit der letzten Aufnahme beschäftigt")
        try:
            yield self._ensure_open()
        finally:
            CAMERA_LOCK.release()

    def invalidate(self) -> None:
        """Drop the handle after an error so the next use re-initializes."""
        with CAMERA_LOCK:
            self._close_locked()

    def close(self) -> None:
        with CAMERA_LOCK:
            self._close_locked()

    # --- internals ----------------------------------------------------------

    def _close_locked(self) -> None:
        camera, self._camera = self._camera, None
        self._settings_applied = False
        if camera is None:
            return
        try:
            camera.exit()
        except Exception as exc:  # already gone — nothing left to release
            log.debug("Kamera-exit fehlgeschlagen: %s", exc)

    def _ensure_open(self):
        if self._camera is not None:
            return self._camera
        gp = import_gphoto2()
        camera = gp.Camera()
        # Address the chosen camera by its port when one is selected.
        if self._selected is not None and self._selected.port:
            port_info_list = gp.PortInfoList()
            port_info_list.load()
            index = port_info_list.lookup_path(self._selected.port)
            if index >= 0:
                camera.set_port_info(port_info_list[index])
        camera.init()
        self._camera = camera
        self._apply_settings(gp, camera)
        return camera

    def _apply_settings(self, gp, camera) -> None:
        """Push the configured shooting settings once per session, not per photo.

        ``get_config``/``set_config`` cost ~400 ms each on the a7 IV — that used to
        sit between the countdown reaching zero and the shutter.
        """
        if self._settings_applied:
            return
        camera_config = self._config.hardware.camera
        if camera_config.image_quality:
            self.set_widget(camera, "imagequality", camera_config.image_quality)
        if camera_config.capture_target:
            self.set_widget(camera, "capturetarget", camera_config.capture_target)
        if camera_config.autofocus == "off":
            self.set_widget(camera, "autofocus", "Off")
        self._settings_applied = True

    def set_widget(self, camera, name: str, value) -> bool:
        try:
            config = camera.get_config()
            widget = config.get_child_by_name(name)
            widget.set_value(value)
            camera.set_config(config)
            return True
        except Exception as exc:  # widget missing / read-only on this body
            log.debug("Kamera-Einstellung %s=%s nicht möglich: %s", name, value, exc)
            return False


def get_session(config: Config, selected: DetectedCamera | None) -> CameraSession:
    """The session for ``selected``, reused while the camera stays the same."""
    global _session
    port = selected.port if selected else None
    if _session is not None:
        current = _session.selected.port if _session.selected else None
        if current == port:
            return _session
        _session.close()
    _session = CameraSession(config, selected)
    return _session


def close_session() -> None:
    """Release the handle — before a USB reset or when the selection changes."""
    global _session
    if _session is not None:
        _session.close()
        _session = None
