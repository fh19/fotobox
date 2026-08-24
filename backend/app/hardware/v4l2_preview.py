"""Real preview camera over V4L2 (USB webcam) via OpenCV — milestone M5b.

A background thread grabs frames continuously and keeps the latest JPEG, so the
MJPEG endpoint's ``frame()`` call never blocks the event loop and the camera's
frame rate is decoupled from the number of clients. MJPG is requested from the
device (USB webcams deliver it natively; YUYV would be far heavier to decode).

While nobody asks for frames the thread still *grabs* them — that keeps the
stream flowing and the picture instant when someone looks again — but skips the
decode and the JPEG encode, which is where the work actually is. Without that
the box spent two thirds of a core drawing a picture nobody was watching: during
the screensaver, in the gallery, and all day in print-server mode.
"""

from __future__ import annotations

import io
import logging
import threading
import time

log = logging.getLogger("fotobox.preview")

_placeholder_jpeg: bytes | None = None


def placeholder_frame() -> bytes:
    """A tiny dark frame shown until the first real frame arrives / on failure."""
    global _placeholder_jpeg
    if _placeholder_jpeg is None:
        from PIL import Image

        buffer = io.BytesIO()
        Image.new("RGB", (16, 9), (17, 17, 17)).save(buffer, format="JPEG")
        _placeholder_jpeg = buffer.getvalue()
    return _placeholder_jpeg


class V4l2Preview:
    def __init__(
        self,
        device: str,
        width: int,
        height: int,
        fps: int,
        jpeg_quality: int,
        idle_after_seconds: float = 5.0,
    ) -> None:
        import cv2

        self._cv2 = cv2
        self._device = device
        self._width = width
        self._height = height
        self._fps = fps
        self._quality = jpeg_quality
        self._idle_after = idle_after_seconds
        self._last_request = time.monotonic()
        self._latest: bytes | None = None
        self._lock = threading.Lock()
        self._stop = threading.Event()

        cap = self._open()
        self._cap = cap
        self._opened = cap.isOpened()
        if self._opened:
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
        else:
            log.warning("Vorschaukamera %s ließ sich nicht öffnen", device)

    def _open(self):
        cv2 = self._cv2
        cap = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        cap.set(cv2.CAP_PROP_FPS, self._fps)
        return cap

    def _idle(self) -> bool:
        """True while nobody has asked for a frame for a while."""
        if self._idle_after <= 0:
            return False
        return (time.monotonic() - self._last_request) > self._idle_after

    def _run(self) -> None:
        cv2 = self._cv2
        fails = 0
        while not self._stop.is_set():
            # grab() fetches without decoding — the cheap half. retrieve() and
            # the JPEG encode only happen when somebody is actually looking.
            ok = self._cap.grab()
            frame = None
            if ok and not self._idle():
                ok, frame = self._cap.retrieve()
            if not ok:
                fails += 1
                if fails > 30:
                    # Camera glitched (USB hiccup, brief unplug, driver reset).
                    # Reopen instead of giving up for good, so the preview *and*
                    # capture-from-preview recover on their own without a restart.
                    self._opened = False
                    log.warning("Vorschaukamera %s liefert nichts — Neuöffnen", self._device)
                    try:
                        self._cap.release()
                    except Exception:
                        pass
                    if self._stop.is_set():
                        break
                    self._cap = self._open()
                    self._opened = self._cap.isOpened()
                    fails = 0
                    if not self._opened:
                        time.sleep(1.0)  # device still gone — back off before retrying
                    continue
                time.sleep(0.05)
                continue
            fails = 0
            self._opened = True  # recovered after a previous glitch
            if frame is None:
                continue  # idle: grabbed and dropped, nothing to encode
            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self._quality])
            if ok:
                with self._lock:
                    self._latest = buffer.tobytes()

    def available(self) -> bool:
        return self._opened and self._latest is not None

    def frame(self) -> bytes:
        # Somebody is looking — the grab loop starts encoding again.
        self._last_request = time.monotonic()
        # Only while the device is actually delivering. Handing out the last frame
        # of an unplugged camera freezes the kiosk on a picture that looks live —
        # far more confusing than an obviously blank one (api-contract).
        with self._lock:
            if self._opened and self._latest is not None:
                return self._latest
        return placeholder_frame()

    def close(self) -> None:
        self._stop.set()
        try:
            self._cap.release()
        except Exception:
            pass
