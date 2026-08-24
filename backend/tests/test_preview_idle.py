"""The preview stops working when nobody is looking.

The grab thread used to decode and JPEG-encode every frame around the clock,
whether or not anyone had ever asked for one. On the box that was two thirds of
a core — during the screensaver, in the gallery, and all day in print-server
mode. Grabbing continues (the picture must be instant when someone looks
again); the expensive half does not.
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock

from app.hardware.v4l2_preview import V4l2Preview


def _preview(monkeypatch, idle_after=0.05):
    """A V4l2Preview whose OpenCV is a counting stand-in."""
    cv2 = MagicMock()
    cap = MagicMock()
    cap.isOpened.return_value = True
    cap.grab.return_value = True
    cap.retrieve.return_value = (True, "frame")
    cv2.VideoCapture.return_value = cap
    cv2.imencode.return_value = (True, MagicMock(tobytes=lambda: b"\xff\xd8jpeg"))
    monkeypatch.setitem(__import__("sys").modules, "cv2", cv2)

    preview = V4l2Preview("/dev/video0", 1280, 720, 25, 80, idle_after)
    return preview, cap, cv2


def test_it_stops_encoding_when_nobody_asks(monkeypatch):
    preview, cap, cv2 = _preview(monkeypatch)
    try:
        time.sleep(0.3)  # well past idle_after
        grabs_before = cap.grab.call_count
        encodes_before = cv2.imencode.call_count
        time.sleep(0.3)

        assert cap.grab.call_count > grabs_before, "grabbing must continue"
        assert cv2.imencode.call_count == encodes_before, "encoding must stop"
    finally:
        preview.close() if hasattr(preview, "close") else preview._stop.set()


def test_asking_for_a_frame_starts_it_again(monkeypatch):
    preview, cap, cv2 = _preview(monkeypatch)
    try:
        time.sleep(0.3)
        encodes_before = cv2.imencode.call_count

        preview.frame()  # somebody is looking
        time.sleep(0.1)
        assert cv2.imencode.call_count > encodes_before
    finally:
        preview._stop.set()


def test_zero_means_always_encode(monkeypatch):
    """The old behaviour stays reachable from the config."""
    preview, cap, cv2 = _preview(monkeypatch, idle_after=0)
    try:
        time.sleep(0.2)
        assert cv2.imencode.call_count > 0
        assert preview._idle() is False
    finally:
        preview._stop.set()
