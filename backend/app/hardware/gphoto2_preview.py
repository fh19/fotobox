"""Live preview straight from the DSLR (gphoto2 ``capture_preview``).

CLAUDE.md rule 1 says the live image comes from a separate preview camera and
never from the DSLR — that is still the default and the recommended setup. This
backend exists because the box may run without a second camera at all: with the
webcam unplugged there would otherwise be no live image whatsoever.

It works because preview and shutter share one open camera handle
(:mod:`app.hardware.gphoto2_session`). A frame costs 9–34 ms on a Sony a7 IV
(1024×768 JPEG, measured on the Pi). While a photo is being taken the loop simply
waits for the lock, so the last frame stays on screen for those ~650 ms.

Same threading shape as :mod:`app.hardware.v4l2_preview`: a background thread
keeps the newest JPEG, so ``frame()`` never blocks the event loop.
"""

from __future__ import annotations

import logging
import threading
import time

from app.config import Config
from app.hardware.discovery import DetectedCamera
from app.hardware.gphoto2_session import CameraSession, get_session
from app.hardware.v4l2_preview import placeholder_frame

log = logging.getLogger("fotobox.preview")

_STALE_AFTER = 3.0  # seconds without a frame before the preview counts as gone
_JPEG_MAGIC = b"\xff\xd8\xff"


class Gphoto2Preview:
    # Tells the CameraManager that this preview borrows the capture camera's handle
    # and therefore has to be rebuilt whenever that camera changes.
    uses_camera_session = True

    def __init__(
        self, config: Config, selected: DetectedCamera | None, session: CameraSession | None = None
    ) -> None:
        self._session = session if session is not None else get_session(config, selected)
        self._interval = 1.0 / max(1, config.hardware.preview.fps)
        self._latest: bytes | None = None
        self._latest_at = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        fails = 0
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                # A short lock timeout: during a capture the camera is busy for a
                # moment, and skipping a frame is better than piling up waiters.
                with self._session.use(timeout=self._interval * 2) as camera:
                    # Keep the CameraFile alive while its buffer is copied —
                    # get_data_and_size() returns a view into memory that the
                    # temporary would otherwise free, yielding garbage bytes.
                    camera_file = camera.capture_preview()
                    data = bytes(camera_file.get_data_and_size())
                if not data.startswith(_JPEG_MAGIC):
                    # Not an image — serving it would blank the kiosk preview with
                    # no hint as to why. Better to keep the last good frame.
                    fails += 1
                    if fails == 5:
                        log.warning("DSLR lieferte kein JPEG als Live-Bild (%d Bytes)", len(data))
                    self._stop.wait(0.5)
                    continue
                with self._lock:
                    self._latest = data
                    self._latest_at = time.monotonic()
                fails = 0
            except Exception as exc:
                fails += 1
                if fails == 5:  # log once per outage, not per frame
                    log.warning("Live-Bild der DSLR nicht verfügbar: %s", exc)
                if fails % 20 == 0:
                    # Camera wedged or unplugged — drop the handle so the next
                    # round re-initializes instead of retrying a dead one.
                    self._session.invalidate()
                self._stop.wait(0.5)
                continue
            self._stop.wait(max(0.0, self._interval - (time.monotonic() - started)))

    def available(self) -> bool:
        with self._lock:
            return self._latest is not None and time.monotonic() - self._latest_at < _STALE_AFTER

    def frame(self) -> bytes:
        # Stale frames are not served: a frozen picture reads as a working live
        # image and hides that the camera is gone.
        with self._lock:
            if self._latest is not None and time.monotonic() - self._latest_at < _STALE_AFTER:
                return self._latest
        return placeholder_frame()

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
