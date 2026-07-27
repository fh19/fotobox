"""Camera selection infrastructure: discovery, resolution, manager, admin API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.clock import RealClock
from app.config import load_config, save_config
from app.hardware.discovery import DetectedCamera, DetectedPreview, MockDiscovery
from app.hardware.factory import CameraManager
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


def test_selection_persists_to_config_file(tmp_path):
    # Write a config file, run the app against it, change the camera, reload the file.
    path = tmp_path / "config.yaml"
    save_config(make_config(tmp_path), path)
    app = create_app(config_path=path)
    with TestClient(app) as client:
        client.post("/api/admin/cameras", headers=PIN, json={"camera_select": "Sony Alpha 6000"})
    assert load_config(path).hardware.camera.select == "Sony Alpha 6000"
