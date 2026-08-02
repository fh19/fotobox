"""V4L2 preview backend — failure path (no real camera in CI)."""

from __future__ import annotations

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
