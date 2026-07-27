"""Real preview camera over V4L2 (USB webcam) via OpenCV — milestone M5b.

A background thread grabs frames continuously and keeps the latest JPEG, so the
MJPEG endpoint's ``frame()`` call never blocks the event loop and the camera's
frame rate is decoupled from the number of clients. MJPG is requested from the
device (USB webcams deliver it natively; YUYV would be far heavier to decode).
"""

from __future__ import annotations

import io
import logging
import threading
import time

log = logging.getLogger("fotobox.preview")

_placeholder_jpeg: bytes | None = None


def _placeholder() -> bytes:
    """A tiny dark frame shown until the first real frame arrives / on failure."""
    global _placeholder_jpeg
    if _placeholder_jpeg is None:
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (16, 9), (17, 17, 17)).save(buffer, format="JPEG")
        _placeholder_jpeg = buffer.getvalue()
    return _placeholder_jpeg


class V4l2Preview:
    def __init__(self, device: str, width: int, height: int, fps: int, jpeg_quality: int) -> None:
        import cv2

        self._cv2 = cv2
        self._quality = jpeg_quality
        self._latest: bytes | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()

        cap = cv2.VideoCapture(device, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, fps)
        self._cap = cap
        self._opened = cap.isOpened()
        if self._opened:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        else:
            log.warning("Vorschaukamera %s ließ sich nicht öffnen", device)

    def _run(self) -> None:
        cv2 = self._cv2
        fails = 0
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            if not ok:
                fails += 1
                if fails > 30:  # camera vanished — mark unavailable and stop
                    self._opened = False
                    break
                time.sleep(0.05)
                continue
            fails = 0
            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._quality])
            if ok:
                with self._lock:
                    self._latest = buffer.tobytes()

    def available(self) -> bool:
        return self._opened and self._latest is not None

    def frame(self) -> bytes:
        with self._lock:
            if self._latest is not None:
                return self._latest
        return _placeholder()

    def close(self) -> None:
        self._stop.set()
        try:
            self._cap.release()
        except Exception:
            pass
