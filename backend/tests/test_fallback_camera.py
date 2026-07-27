"""Fallback capture: use the preview camera when the DSLR is unavailable."""

from __future__ import annotations

import io

from PIL import Image

from app.hardware.base import CaptureResult
from app.hardware.fallback_camera import FALLBACK_MODEL, FallbackCamera


def _jpeg(w=640, h=480) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


class FakePrimary:
    def __init__(self, available, model="Nikon D7200", raises=False):
        self._a, self._m, self._raises = available, model, raises

    def available(self):
        return self._a

    def model(self):
        return self._m if self._a else None

    def capture(self):
        if self._raises:
            raise RuntimeError("shutter failed")
        return CaptureResult(jpeg=_jpeg(), width=6000, height=4000, camera_model=self._m)


class FakePreview:
    def __init__(self, available, jpeg=b""):
        self._a, self._jpeg = available, jpeg

    def available(self):
        return self._a

    def frame(self):
        return self._jpeg


def test_uses_dslr_when_available():
    cam = FallbackCamera(FakePrimary(True), FakePreview(True, _jpeg()))
    assert cam.model() == "Nikon D7200"
    assert cam.using_fallback() is False
    result = cam.capture()
    assert result.camera_model == "Nikon D7200" and result.width == 6000


def test_falls_back_when_dslr_absent():
    cam = FallbackCamera(FakePrimary(False), FakePreview(True, _jpeg(1280, 720)))
    assert cam.available() is True
    assert cam.model() == FALLBACK_MODEL
    assert cam.using_fallback() is True
    result = cam.capture()
    assert result.camera_model == FALLBACK_MODEL
    assert (result.width, result.height) == (1280, 720)


def test_falls_back_when_dslr_trigger_fails():
    cam = FallbackCamera(FakePrimary(True, raises=True), FakePreview(True, _jpeg(800, 600)))
    result = cam.capture()  # DSLR raises → preview used
    assert result.camera_model == FALLBACK_MODEL and result.width == 800


def test_unavailable_when_both_gone():
    cam = FallbackCamera(FakePrimary(False), FakePreview(False))
    assert cam.available() is False
    assert cam.model() is None


def test_manager_wraps_camera_in_fallback(tmp_path):
    from app.hardware.factory import CameraManager
    from tests.conftest import make_config

    manager = CameraManager(make_config(tmp_path))
    assert type(manager.camera).__name__ == "FallbackCamera"
    # In mock mode the mock camera is available, so it behaves like the DSLR.
    assert manager.camera.available() is True
