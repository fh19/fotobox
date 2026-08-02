"""Camera selection infrastructure: discovery, resolution, manager, admin API."""

from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.clock import RealClock
from app.config import load_config, save_config
from app.hardware import factory
from app.hardware.discovery import DetectedCamera, DetectedPreview, MockDiscovery
from app.hardware.factory import CameraManager
from app.hardware.mock import MockCamera
from app.hardware.selection import resolve_camera, resolve_preview
from app.main import create_app
from tests.conftest import make_config

PIN = {"X-Fotobox-Pin": "2606"}  # matches config.example.yaml admin_pin


# --- resolution -------------------------------------------------------------


def _cams():
    return [
        DetectedCamera(
            id="usb:001,004", model="Nikon DSC D7200", port="usb:001,004", source="mock"
        ),
        DetectedCamera(
            id="usb:001,005", model="Sony Alpha 6000", port="usb:001,005", source="mock"
        ),
    ]


def test_resolve_camera_auto_picks_first():
    assert resolve_camera("auto", _cams()).model == "Nikon DSC D7200"


def test_resolve_camera_by_model_and_port():
    assert resolve_camera("Sony Alpha 6000", _cams()).id == "usb:001,005"
    assert resolve_camera("usb:001,004", _cams()).model == "Nikon DSC D7200"


def test_resolve_camera_unknown_or_empty():
    assert resolve_camera("Canon", _cams()) is None
    assert resolve_camera("auto", []) is None


def test_resolve_preview_backend_and_device():
    previews = [
        DetectedPreview(id="csi0", name="Pi Cam", device="csi0", backend="picamera2"),
        DetectedPreview(id="/dev/video0", name="C920", device="/dev/video0", backend="v4l2"),
    ]
    assert resolve_preview("auto", "auto", previews).id == "csi0"
    assert resolve_preview("auto", "v4l2", previews).id == "/dev/video0"
    assert resolve_preview("/dev/video0", "auto", previews).backend == "v4l2"
    assert resolve_preview("auto", "auto", []) is None


def test_a_missing_preview_backend_falls_back_to_what_is_attached():
    """Reported from the box: with `backend: gphoto2` saved and the DSLR
    unplugged, the webcam was ignored — no live image, and because capture falls
    back to the preview camera, no photos either. The setting is a preference."""
    webcam = DetectedPreview(id="/dev/video0", name="eMeet", device="/dev/video0", backend="v4l2")

    assert resolve_preview("auto", "gphoto2", [webcam]).id == "/dev/video0"
    assert resolve_preview("usb:002,002", "gphoto2", [webcam]).id == "/dev/video0"
    # A DSLR that is there still wins when it is the one asked for.
    dslr = DetectedPreview(id="usb:002,002", name="a7 IV", device="usb:002,002", backend="gphoto2")
    assert resolve_preview("auto", "gphoto2", [webcam, dslr]).id == "usb:002,002"
    assert resolve_preview("auto", "auto", [webcam, dslr]).id == "/dev/video0"


# --- manager (mock mode) ----------------------------------------------------


def test_manager_auto_selects_and_builds(tmp_path):
    manager = CameraManager(make_config(tmp_path))
    assert manager.selected_camera.model == "Nikon DSC D7200"
    assert manager.backends.camera.available() is True
    assert manager.backends.camera.model() == "Nikon DSC D7200"


def test_manager_reselect_changes_camera(tmp_path):
    manager = CameraManager(make_config(tmp_path))
    manager.select(camera_select="Sony Alpha 6000")
    assert manager.selected_camera.model == "Sony Alpha 6000"
    assert manager.backends.camera.model() == "Sony Alpha 6000"


def test_manager_no_cameras_marks_unavailable(tmp_path):
    config = make_config(tmp_path)
    manager = CameraManager(config)
    # Force empty discovery and rebuild.
    manager._discovery = MockDiscovery(cameras=[], previews=[])
    manager.rebuild()
    assert manager.selected_camera is None
    assert manager.backends.camera.available() is True  # mock stays available in mock mode


# --- late-booting DSLR ------------------------------------------------------
#
# The box boots faster than the camera: a Sony a7 IV needs ~50 s to appear on the
# USB bus, so the discovery at startup finds nothing and every photo would be taken
# by the fallback camera until someone re-selects the DSLR in the admin UI.


class _CountingDiscovery:
    """MockDiscovery that records how often the camera list was asked for."""

    def __init__(self, cameras):
        self.cameras_list = list(cameras)
        self.calls = 0

    def cameras(self):
        self.calls += 1
        return list(self.cameras_list)

    def previews(self):
        return []


def _missing_camera_manager(tmp_path, monkeypatch):
    """A manager whose DSLR is gone, with availability following the selection."""
    monkeypatch.setattr(
        factory,
        "build_camera",
        lambda config, selected: MockCamera(
            model=selected.model if selected else "", available=selected is not None
        ),
    )
    config = make_config(tmp_path)
    config.hardware.camera.reconnect_backoff_seconds = [1.0, 2.0]
    manager = CameraManager(config)
    manager._discovery = _CountingDiscovery([])
    manager.rebuild()
    return manager


def test_late_camera_is_picked_up_after_the_backoff(tmp_path, monkeypatch):
    manager = _missing_camera_manager(tmp_path, monkeypatch)
    now = datetime(2026, 8, 2, 14, 0, 0)
    assert manager.selected_camera is None

    assert manager.rediscover_if_missing(now) is False  # first tick only arms the retry
    assert manager.rediscover_if_missing(now + timedelta(seconds=0.5)) is False  # too early
    assert manager.rediscover_if_missing(now + timedelta(seconds=1.5)) is False  # still nothing

    manager._discovery.cameras_list = _cams()
    assert manager.rediscover_if_missing(now + timedelta(seconds=10)) is True
    assert manager.selected_camera.model == "Nikon DSC D7200"
    assert manager.backends.camera.model() == "Nikon DSC D7200"


def test_rediscovery_leaves_the_preview_device_alone(tmp_path, monkeypatch):
    """Re-opening the webcam every few seconds would break the live stream."""
    manager = _missing_camera_manager(tmp_path, monkeypatch)
    now = datetime(2026, 8, 2, 14, 0, 0)
    preview = manager.preview

    manager.rediscover_if_missing(now)
    manager._discovery.cameras_list = _cams()
    assert manager.rediscover_if_missing(now + timedelta(seconds=10)) is True
    assert manager.preview is preview
    assert manager.backends.preview is preview


def test_no_rediscovery_while_the_camera_is_there(tmp_path, monkeypatch):
    manager = _missing_camera_manager(tmp_path, monkeypatch)
    manager._discovery.cameras_list = _cams()
    manager.rebuild()
    discovery = manager._discovery
    discovery.calls = 0

    now = datetime(2026, 8, 2, 14, 0, 0)
    for offset in (0, 5, 60):
        assert manager.rediscover_if_missing(now + timedelta(seconds=offset)) is False
    assert discovery.calls == 0


def test_engine_swaps_in_the_camera_found_later(tmp_path, monkeypatch, make_engine, clock):
    """The engine holds its own Backends snapshot — it must pick up the new camera."""
    engine = make_engine()
    manager = _missing_camera_manager(tmp_path, monkeypatch)
    engine.camera_manager = manager
    engine.backends = manager.backends
    assert engine.build_status()["camera"]["model"] == "Vorschaukamera (Ersatz)"

    engine.tick()
    manager._discovery.cameras_list = _cams()
    clock.advance(seconds=10)
    engine.tick()

    assert engine.backends.camera is manager.camera
    assert engine.build_status()["camera"]["model"] == "Nikon DSC D7200"


# --- admin API --------------------------------------------------------------


def _client(tmp_path, **overrides):
    return TestClient(create_app(make_config(tmp_path, **overrides), RealClock()))


def test_cameras_requires_pin(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/admin/cameras").status_code == 401
    assert client.get("/api/admin/cameras", headers={"X-Fotobox-Pin": "0000"}).status_code == 401


def test_cameras_lists_detected(tmp_path):
    client = _client(tmp_path)
    body = client.get("/api/admin/cameras", headers=PIN).json()
    models = [c["model"] for c in body["capture"]["detected"]]
    assert "Nikon DSC D7200" in models and "Sony Alpha 6000" in models
    assert body["capture"]["selected"]["model"] == "Nikon DSC D7200"
    assert body["capture"]["autofocus"] == "off"


def test_select_camera_changes_selection(tmp_path):
    client = _client(tmp_path)
    res = client.post("/api/admin/cameras", headers=PIN, json={"camera_select": "Sony Alpha 6000"})
    assert res.status_code == 200
    assert res.json()["capture"]["selected"]["model"] == "Sony Alpha 6000"
    # reflected in the guest status
    assert client.get("/api/status").json()["camera"]["model"] == "Sony Alpha 6000"


def test_select_unknown_camera_is_404(tmp_path):
    client = _client(tmp_path)
    res = client.post("/api/admin/cameras", headers=PIN, json={"camera_select": "Canon EOS"})
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "unknown_camera"


def test_select_only_in_idle(tmp_path):
    client = _client(tmp_path)
    client.post("/api/session/start")  # -> BACKGROUND_SELECT
    res = client.post("/api/admin/cameras", headers=PIN, json={"camera_select": "Sony Alpha 6000"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "invalid_state"


# --- rescan / reset / test shot ---------------------------------------------


def test_rescan_and_reset_and_testshot_require_a_pin(tmp_path):
    client = _client(tmp_path)
    for path in ("/api/admin/camera/rescan", "/api/admin/camera/reset"):
        assert client.post(path).status_code == 401
    assert client.post("/api/admin/camera/testshot").status_code == 401
    assert client.get("/api/admin/camera/testshot.jpg").status_code == 401


def test_rescan_returns_the_camera_list(tmp_path):
    client = _client(tmp_path)
    body = client.post("/api/admin/camera/rescan", headers=PIN).json()
    assert body["capture"]["selected"]["model"] == "Nikon DSC D7200"
    assert body["capture"]["fallback"] is False


def test_reset_reports_what_it_did(tmp_path, monkeypatch):
    resets: list[str] = []
    monkeypatch.setattr(factory, "reset_usb_device", lambda port: bool(resets.append(port)) or True)
    client = _client(tmp_path)
    body = client.post("/api/admin/camera/reset", headers=PIN).json()

    assert resets == ["usb:001,004"]  # the port of the selected mock camera
    assert body["reset"]["camera_reset"] is True
    assert body["capture"]["selected"]["model"] == "Nikon DSC D7200"


def test_reset_only_in_idle(tmp_path):
    client = _client(tmp_path)
    client.post("/api/session/start")
    res = client.post("/api/admin/camera/reset", headers=PIN)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "invalid_state"


def test_testshot_reports_the_camera_and_serves_the_image(tmp_path):
    client = _client(tmp_path)
    body = client.post("/api/admin/camera/testshot", headers=PIN).json()

    assert body["model"] == "Nikon DSC D7200"
    assert (body["width"], body["height"]) == (1200, 1800)
    assert body["fallback"] is False
    image = client.get("/api/admin/camera/testshot.jpg", headers=PIN)
    assert image.status_code == 200
    assert image.content.startswith(b"\xff\xd8\xff")
    # A test shot is not a photo of the party — it stays out of the event.
    assert client.get("/api/status").json()["event"]["photo_count"] == 0


def test_testshot_without_a_photo_yet_is_404(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/admin/camera/testshot.jpg", headers=PIN).status_code == 404


def test_status_flags_the_fallback_camera(tmp_path, monkeypatch):
    """The silent switch to the webcam was the whole problem — make it visible."""
    manager = _missing_camera_manager(tmp_path, monkeypatch)
    engine = create_app(make_config(tmp_path), RealClock()).state.engine
    engine.camera_manager = manager
    engine.backends = manager.backends

    assert engine.build_status()["camera"]["fallback"] is True
    assert engine.list_cameras()["capture"]["fallback"] is True


def test_automatic_usb_reset_after_repeated_failures(tmp_path, monkeypatch):
    """usbreset_after_failures: the box heals itself without anyone opening admin."""
    resets: list[str] = []
    monkeypatch.setattr(factory, "reset_usb_device", lambda port: bool(resets.append(port)) or True)
    config = make_config(tmp_path)
    config.hardware.camera.usbreset_after_failures = 2
    manager = CameraManager(config)

    assert manager.note_capture_failed() is False
    assert resets == []
    assert manager.note_capture_failed() is True
    assert resets == ["usb:001,004"]

    # The counter starts over, and a success clears it too.
    manager.note_capture_failed()
    manager.note_capture_ok()
    assert manager.note_capture_failed() is False


def test_no_automatic_reset_when_disabled(tmp_path, monkeypatch):
    resets: list[str] = []
    monkeypatch.setattr(factory, "reset_usb_device", lambda port: bool(resets.append(port)) or True)
    config = make_config(tmp_path)
    config.hardware.camera.usbreset_after_failures = 0
    manager = CameraManager(config)

    for _ in range(5):
        assert manager.note_capture_failed() is False
    assert resets == []


def test_selection_persists_to_config_file(tmp_path):
    # Write a config file, run the app against it, change the camera, reload the file.
    path = tmp_path / "config.yaml"
    save_config(make_config(tmp_path), path)
    app = create_app(config_path=path)
    with TestClient(app) as client:
        client.post("/api/admin/cameras", headers=PIN, json={"camera_select": "Sony Alpha 6000"})
    assert load_config(path).hardware.camera.select == "Sony Alpha 6000"
