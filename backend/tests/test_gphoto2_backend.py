"""Gphoto2 capture: the camera does not always hand us a JPEG.

Reproduces the Sony a7 IV case seen on the box: the camera shoots RAW+JPEG, and
``capture()`` returns the ``.ARW`` path. Downloading that gave 35 MB of TIFF,
Pillow refused it, and the fallback camera silently took over — the photo came
from the webcam while the shutter had fired.

The real ``gphoto2`` module is not installed on the dev machine, so a fake one
stands in; only our own logic is under test.
"""

from __future__ import annotations

import contextlib
import io
import os
import threading

import pytest
from PIL import Image

from app.hardware import gphoto2_backend, gphoto2_session, usb_reset
from app.hardware.discovery import DetectedCamera
from app.hardware.gphoto2_backend import Gphoto2Camera
from app.hardware.gphoto2_lock import CAMERA_LOCK
from app.hardware.gphoto2_session import CameraSession
from app.hardware.usb_reset import device_path
from tests.conftest import make_config


def _jpeg_bytes(size=(120, 80)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, (10, 120, 200)).save(buffer, format="JPEG")
    return buffer.getvalue()


RAW_BYTES = b"II*\x00" + b"\x00" * 64  # TIFF header, as an .ARW starts


class _Path:
    def __init__(self, folder: str, name: str) -> None:
        self.folder = folder
        self.name = name


class _Gp:
    """The handful of gphoto2 names the backend touches."""

    GP_CAPTURE_IMAGE = 0
    GP_FILE_TYPE_NORMAL = 1
    GP_EVENT_TIMEOUT = 0
    GP_EVENT_FILE_ADDED = 2


class _File:
    def __init__(self, data: bytes) -> None:
        self._data = data

    def get_data_and_size(self) -> bytes:
        return self._data


class _FakeCamera:
    """Camera stub: ``files`` maps name -> bytes, ``events`` is the event queue."""

    def __init__(self, capture_name: str, files: dict[str, bytes], events=()) -> None:
        self._capture_name = capture_name
        self.files = dict(files)
        self.events = list(events)
        self.downloaded: list[str] = []
        self.settings: dict[str, object] = {}
        self.exited = False

    # settings ---------------------------------------------------------------
    def get_config(self):
        return self

    def get_child_by_name(self, name: str):
        if name not in ("imagequality", "imagesize", "capturetarget", "autofocus"):
            raise RuntimeError(f"widget {name} missing")
        return _Widget(self, name)

    def set_config(self, _config) -> None:
        pass

    # capture ----------------------------------------------------------------
    def capture(self, _type):
        return _Path("/", self._capture_name)

    def file_get(self, _folder: str, name: str, _file_type):
        self.downloaded.append(name)
        return _File(self.files[name])

    def file_delete(self, _folder: str, _name: str) -> None:
        raise RuntimeError("Sony refuses deletion")

    def wait_for_event(self, _timeout_ms: int):
        if not self.events:
            return _Gp.GP_EVENT_TIMEOUT, None
        return self.events.pop(0)

    def exit(self) -> None:
        self.exited = True


class _Widget:
    def __init__(self, camera: _FakeCamera, name: str) -> None:
        self._camera = camera
        self._name = name

    def set_value(self, value) -> None:
        self._camera.settings[self._name] = value


@pytest.fixture
def config(tmp_path):
    return make_config(tmp_path)


def _session(monkeypatch, config, camera: _FakeCamera) -> CameraSession:
    """A session whose "open camera" is the fake, settings applied like the real one."""
    monkeypatch.setattr(gphoto2_backend, "import_gphoto2", lambda: _Gp)
    monkeypatch.setattr(gphoto2_session, "import_gphoto2", lambda: _Gp)
    selected = DetectedCamera(
        id="usb:002,002", model="Sony a7 IV", port="usb:002,002", source="gphoto2"
    )
    session = CameraSession(config, selected)

    def ensure_open():
        session._camera = camera
        session._apply_settings(_Gp, camera)
        return camera

    monkeypatch.setattr(session, "_ensure_open", ensure_open)
    return session


def _backend(monkeypatch, config, camera: _FakeCamera) -> Gphoto2Camera:
    session = _session(monkeypatch, config, camera)
    return Gphoto2Camera(config, session.selected, session=session)


def test_capture_returns_jpeg_directly(monkeypatch, config):
    jpeg = _jpeg_bytes()
    camera = _FakeCamera("capt0001.jpg", {"capt0001.jpg": jpeg})
    result = _backend(monkeypatch, config, camera).capture()

    assert result.jpeg == jpeg
    assert (result.width, result.height) == (120, 80)
    # The handle stays open — reopening it per photo cost 3.5 s on the a7 IV.
    assert camera.exited is False


def test_raw_plus_jpeg_takes_the_jpeg_from_the_event(monkeypatch, config):
    jpeg = _jpeg_bytes()
    camera = _FakeCamera(
        "capt_A7H00089.ARW",
        {"capt_A7H00089.ARW": RAW_BYTES, "capt_A7H00089.JPG": jpeg},
        events=[(_Gp.GP_EVENT_FILE_ADDED, _Path("/", "capt_A7H00089.JPG"))],
    )
    result = _backend(monkeypatch, config, camera).capture()

    assert result.jpeg == jpeg
    # The 35 MB RAW is never pulled over USB.
    assert camera.downloaded == ["capt_A7H00089.JPG"]


def test_raw_only_fails_loudly(monkeypatch, config):
    """No JPEG at all: a clear error beats a silent switch to the webcam."""
    config.hardware.camera.capture_timeout_seconds = 0.1
    camera = _FakeCamera("capt_A7H00090.ARW", {"capt_A7H00090.ARW": RAW_BYTES})

    with pytest.raises(RuntimeError, match="kein JPEG"):
        _backend(monkeypatch, config, camera).capture()


def test_configured_settings_are_pushed_before_the_shutter(monkeypatch, config):
    config.hardware.camera.image_quality = "JPEG"
    config.hardware.camera.capture_target = "sdram"
    camera = _FakeCamera("capt0001.jpg", {"capt0001.jpg": _jpeg_bytes()})
    _backend(monkeypatch, config, camera).capture()

    assert camera.settings["imagequality"] == "JPEG"
    assert camera.settings["capturetarget"] == "sdram"


def test_empty_settings_leave_the_camera_alone(monkeypatch, config):
    config.hardware.camera.image_quality = ""
    config.hardware.camera.capture_target = ""
    camera = _FakeCamera("capt0001.jpg", {"capt0001.jpg": _jpeg_bytes()})
    _backend(monkeypatch, config, camera).capture()

    assert "imagequality" not in camera.settings
    assert "capturetarget" not in camera.settings


# --- the camera lock --------------------------------------------------------
#
# Two threads in libgphoto2 at once left the USB device claimed inside our own
# process; every later init() then failed with "[-53] Could not claim the USB
# device" and the photo silently came from the webcam. The lock has to be taken
# from another thread here — an RLock does not block its own owner.


@contextlib.contextmanager
def _lock_held_elsewhere():
    holder_has_it = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with CAMERA_LOCK:
            holder_has_it.set()
            release.wait(5)

    thread = threading.Thread(target=hold, daemon=True)
    thread.start()
    assert holder_has_it.wait(5)
    try:
        yield
    finally:
        release.set()
        thread.join(5)


def test_availability_uses_the_cache_while_a_capture_runs(monkeypatch, config):
    """A camera that is exposing right now is obviously there — never probe it."""
    camera = _FakeCamera("capt0001.jpg", {})
    backend = _backend(monkeypatch, config, camera)
    detects: list[int] = []
    monkeypatch.setattr(backend, "_detect", lambda: detects.append(1) or True)
    backend._checked_at = 0.0  # force the TTL to be expired

    with _lock_held_elsewhere():
        assert backend.available() is True  # the seeded value, not a fresh probe
    assert detects == []

    assert backend.available() is True  # lock free again → probe runs
    assert detects == [1]


def test_capture_reports_a_busy_camera_instead_of_minus_53(monkeypatch, config):
    config.hardware.camera.capture_timeout_seconds = 0.1
    camera = _FakeCamera("capt0001.jpg", {"capt0001.jpg": _jpeg_bytes()})
    backend = _backend(monkeypatch, config, camera)

    with _lock_held_elsewhere(), pytest.raises(RuntimeError, match="beschäftigt"):
        backend.capture()


def test_capture_releases_the_lock_even_when_it_fails(monkeypatch, config):
    config.hardware.camera.capture_timeout_seconds = 0.1
    camera = _FakeCamera("capt_A7H00090.ARW", {"capt_A7H00090.ARW": RAW_BYTES})
    backend = _backend(monkeypatch, config, camera)

    with pytest.raises(RuntimeError):
        backend.capture()
    assert CAMERA_LOCK.acquire(blocking=False)
    CAMERA_LOCK.release()


# --- USB reset --------------------------------------------------------------


def test_device_path_from_gphoto_port():
    assert device_path("usb:002,002") == "/dev/bus/usb/002/002"
    assert device_path("usb:1,4") == "/dev/bus/usb/001/004"
    assert device_path("ptpip:") is None
    assert device_path(None) is None


def test_reset_usb_device_sends_the_ioctl(monkeypatch, tmp_path):
    node = tmp_path / "002"
    node.write_bytes(b"")
    opened: list[str] = []
    calls: list[int] = []
    real_open = os.open  # grab it before patching the module-global os.open

    def fake_open(path, flags):
        opened.append(path)
        return real_open(node, flags)

    monkeypatch.setattr(usb_reset.os, "open", fake_open)
    monkeypatch.setattr(usb_reset.fcntl, "ioctl", lambda fd, request, arg: calls.append(request))

    assert usb_reset.reset_usb_device("usb:002,002") is True
    assert opened == ["/dev/bus/usb/002/002"]
    assert calls == [usb_reset.USBDEVFS_RESET]


def test_reset_usb_device_survives_a_missing_node(monkeypatch):
    assert usb_reset.reset_usb_device("usb:099,099") is False  # no such device
    assert usb_reset.reset_usb_device("nonsense") is False


# --- the shared session -----------------------------------------------------
#
# libgphoto2 makes the a7 IV wait 3 s after init() before the first release, so
# opening the camera per photo cost 4.2 s against 650 ms with it kept open.


def test_the_camera_is_opened_once_for_many_photos(monkeypatch, config):
    camera = _FakeCamera("capt0001.jpg", {"capt0001.jpg": _jpeg_bytes()})
    session = CameraSession(config, None)
    opens: list[int] = []

    def ensure_open():
        if session._camera is None:
            opens.append(1)
            session._camera = camera
            session._apply_settings(_Gp, camera)
        return camera

    monkeypatch.setattr(gphoto2_backend, "import_gphoto2", lambda: _Gp)
    monkeypatch.setattr(session, "_ensure_open", ensure_open)
    backend = Gphoto2Camera(config, None, session=session)

    for _ in range(3):
        backend.capture()
    assert opens == [1]  # one init for three photos
    assert camera.settings["imagequality"] == "JPEG"  # applied once, not per shot


def test_a_failed_capture_drops_the_handle(monkeypatch, config):
    """A broken session must not be inherited by the next attempt."""
    config.hardware.camera.capture_timeout_seconds = 0.1
    camera = _FakeCamera("capt_A7H00090.ARW", {"capt_A7H00090.ARW": RAW_BYTES})
    session = _session(monkeypatch, config, camera)
    backend = Gphoto2Camera(config, session.selected, session=session)

    with pytest.raises(RuntimeError):
        backend.capture()
    assert session.is_open() is False
    assert camera.exited is True


def test_an_open_handle_is_no_proof_the_camera_is_there(monkeypatch, config):
    """Reported after a battery change: the camera comes back under a new USB
    device number, and the still-open handle kept claiming "da" — so nothing
    re-detected it and the next photo failed with -52 and fell back to the
    webcam. The bus is asked, never the handle."""
    camera = _FakeCamera("capt0001.jpg", {})
    session = _session(monkeypatch, config, camera)
    backend = Gphoto2Camera(config, session.selected, session=session)
    session._camera = camera  # handle open, but the camera was switched off
    monkeypatch.setattr(backend, "_detect", lambda: False)

    backend._checked_at = 0.0
    assert backend.available() is False


def test_the_image_size_is_pushed_to_the_camera(monkeypatch, config):
    """One step down from L halves transfer and pipeline time, and even the
    smallest step still out-resolves the postcard print."""
    config.hardware.camera.image_size = "4496x3000"
    camera = _FakeCamera("capt0001.jpg", {"capt0001.jpg": _jpeg_bytes()})
    _backend(monkeypatch, config, camera).capture()

    assert camera.settings["imagesize"] == "4496x3000"


def test_an_empty_image_size_leaves_the_camera_alone(monkeypatch, config):
    config.hardware.camera.image_size = ""
    camera = _FakeCamera("capt0001.jpg", {"capt0001.jpg": _jpeg_bytes()})
    _backend(monkeypatch, config, camera).capture()

    assert "imagesize" not in camera.settings
