"""V4L2 preview backend — failure path (no real camera in CI)."""

from __future__ import annotations

import threading

from app.hardware.v4l2_preview import V4l2Preview, placeholder_frame


def test_placeholder_is_valid_jpeg():
    data = placeholder_frame()
    assert isinstance(data, bytes) and data[:2] == b"\xff\xd8"  # JPEG SOI marker


def test_unopenable_device_is_unavailable_but_still_yields_a_frame():
    preview = V4l2Preview("/dev/does-not-exist-999", 640, 480, 15, 80)
    try:
        assert preview.available() is False
        frame = preview.frame()
        assert isinstance(frame, bytes) and frame[:2] == b"\xff\xd8"
    finally:
        preview.close()


def test_a_dead_camera_stops_serving_its_last_frame():
    """Reported from the box: the webcam was unplugged and the kiosk kept showing
    the last picture, looking live. A blank frame is the honest answer."""
    preview = V4l2Preview.__new__(V4l2Preview)  # no device to open in a test
    preview._lock = threading.Lock()
    preview._latest = b"\xff\xd8\xff-ein-bild"
    preview._opened = True
    assert preview.frame() == b"\xff\xd8\xff-ein-bild"
    assert preview.available() is True

    preview._opened = False  # camera gone; the thread kept the last frame
    assert preview.frame() == placeholder_frame()
    assert preview.available() is False


def test_no_preview_device_serves_the_placeholder():
    """What a real box gets when nothing was detected: MockPreview(available=False).
    It must not hand out its synthetic picture — on the kiosk that looked like a
    frozen live image while the webcam was in fact unplugged."""
    from app.hardware.mock import MockPreview

    gone = MockPreview(available=False)
    assert gone.frame() == placeholder_frame()

    working = MockPreview(available=True)
    assert working.frame() != placeholder_frame()
