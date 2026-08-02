"""Live preview from the DSLR — the fallback when there is no second camera.

CLAUDE.md rule 1 keeps the separate preview camera as the default; this backend
only steps in when none is attached. It borrows the capture camera's open handle,
so the interesting parts are: frames arrive, a busy camera does not break it, and
it never holds the handle while idle.
"""

from __future__ import annotations

import threading
import time

from app.hardware.discovery import DetectedCamera, DetectedPreview
from app.hardware.gphoto2_lock import CAMERA_LOCK
from app.hardware.gphoto2_preview import Gphoto2Preview
from app.hardware.gphoto2_session import CameraSession
from app.hardware.v4l2_preview import placeholder_frame
from tests.conftest import make_config

JPEG = b"\xff\xd8\xff" + b"frame" * 20


class _FakeFile:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def get_data_and_size(self) -> bytes:
        return self._data


class _FakeCamera:
    def __init__(self, data: bytes = JPEG) -> None:
        self._data = data
        self.previews = 0

    def capture_preview(self):
        self.previews += 1
        return _FakeFile(self._data)

    def exit(self) -> None:
        pass


def _preview(monkeypatch, tmp_path, camera, **overrides):
    config = make_config(tmp_path, **overrides)
    session = CameraSession(config, None)
    monkeypatch.setattr(session, "_ensure_open", lambda: camera)
    return Gphoto2Preview(config, None, session=session), config


def _wait_for(predicate, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_frames_arrive_from_the_camera(monkeypatch, tmp_path):
    camera = _FakeCamera()
    preview, _ = _preview(monkeypatch, tmp_path, camera)
    try:
        assert _wait_for(preview.available)
        assert preview.frame() == JPEG
    finally:
        preview.close()


def test_placeholder_until_the_first_frame(monkeypatch, tmp_path):
    class _Silent(_FakeCamera):
        def capture_preview(self):
            raise RuntimeError("noch kein Bild")

    preview, _ = _preview(monkeypatch, tmp_path, _Silent())
    try:
        assert preview.available() is False
        assert preview.frame() == placeholder_frame()
    finally:
        preview.close()


def test_the_capture_can_take_the_camera_away(monkeypatch, tmp_path):
    """A photo must not have to wait for the preview loop to finish."""
    camera = _FakeCamera()
    preview, _ = _preview(monkeypatch, tmp_path, camera)
    try:
        assert _wait_for(preview.available)
        got_it = threading.Event()

        def capture_like() -> None:
            if CAMERA_LOCK.acquire(timeout=2.0):
                got_it.set()
                CAMERA_LOCK.release()

        thread = threading.Thread(target=capture_like, daemon=True)
        thread.start()
        thread.join(3)
        assert got_it.is_set()
        # The last frame stays on screen while the shutter has the camera.
        assert preview.frame() == JPEG
    finally:
        preview.close()


def test_garbage_is_not_served_as_a_frame(monkeypatch, tmp_path):
    """Reproduces a real bug: the CameraFile was freed before its buffer was copied,
    so capture_preview() handed back non-JPEG bytes that blanked the kiosk."""
    preview, _ = _preview(monkeypatch, tmp_path, _FakeCamera(b"\x60\x08\x00\x5c" + b"\x00" * 64))
    try:
        assert _wait_for(lambda: preview._latest is not None, timeout=0.7) is False
        assert preview.available() is False
        assert preview.frame() == placeholder_frame()
    finally:
        preview.close()


def test_closing_stops_the_thread(monkeypatch, tmp_path):
    camera = _FakeCamera()
    preview, _ = _preview(monkeypatch, tmp_path, camera)
    assert _wait_for(preview.available)
    preview.close()
    seen = camera.previews
    time.sleep(0.3)
    assert camera.previews == seen


def test_discovery_lists_the_dslr_last(monkeypatch, tmp_path):
    """ "auto" must keep preferring a real preview camera (rule 1)."""
    from app.hardware import real

    discovery = real.RealDiscovery(make_config(tmp_path))
    webcam = DetectedPreview(id="/dev/video0", name="eMeet", device="/dev/video0", backend="v4l2")
    monkeypatch.setattr(discovery, "_video_devices", lambda: [webcam])
    monkeypatch.setattr(
        discovery,
        "cameras",
        lambda: [
            DetectedCamera(id="usb:002,002", model="Sony a7 IV", port="usb:002,002", source="g")
        ],
    )

    previews = discovery.previews()
    assert [p.backend for p in previews] == ["v4l2", "gphoto2"]
    assert previews[-1].name == "Sony a7 IV"
