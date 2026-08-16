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
    assert resolve_camera("auto", []) is None
    # A pinned camera that is not attached must not disable the one that is: the
    # pin goes stale on every battery change (new USB device number) and on every
    # body swap, and nobody should have to open the admin menu for that.
    assert resolve_camera("Canon EOS", _cams()).model == "Nikon DSC D7200"
    assert resolve_camera("usb:001,099", _cams()).model == "Nikon DSC D7200"
    assert resolve_camera("Sony Alpha 6000", _cams()).model == "Sony Alpha 6000"


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
    assert resolve_preview("usb:002,002", "auto", [webcam, dslr]).id == "usb:002,002"
    assert resolve_preview("auto", "auto", [webcam, dslr]).id == "/dev/video0"


def test_the_dslr_is_never_the_automatic_preview():
    """Live view flips a DSLR's mirror up and drains the battery within the hour
    (D7200 on the box). Without an explicit choice: no live image instead."""
    dslr = DetectedPreview(id="usb:001,004", name="D7200", device="usb:001,004", backend="gphoto2")
    assert resolve_preview("auto", "auto", [dslr]) is None
    assert resolve_preview("auto", "v4l2", [dslr]) is None
    # Asked for by backend or by port, it is used.
    assert resolve_preview("auto", "gphoto2", [dslr]).id == "usb:001,004"
    assert resolve_preview("usb:001,004", "auto", [dslr]).id == "usb:001,004"


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


# --- battery change ---------------------------------------------------------
#
# Reported from the box: after switching the camera off and on, photos came from
# the webcam until someone re-picked the camera in the admin menu. It returns
# under a *new* USB device number, so the stored port goes stale.


class _PortAwareCamera:
    """Available exactly while its port is on the bus — like the real backend."""

    def __init__(self, selected, discovery):
        self._selected = selected
        self._discovery = discovery

    def available(self) -> bool:
        if self._selected is None:
            return False
        return any(c.port == self._selected.port for c in self._discovery.cameras_list)

    def model(self) -> str | None:
        return self._selected.model if self.available() else None

    def capture(self):
        raise AssertionError("kein Foto nötig, um die Kamera wiederzufinden")


def _nikon(port: str) -> DetectedCamera:
    return DetectedCamera(id=port, model="Nikon DSC D7200", port=port, source="gphoto2")


def test_a_camera_that_comes_back_on_a_new_port_is_picked_up(tmp_path, monkeypatch):
    discovery = _CountingDiscovery([_nikon("usb:001,004")])
    monkeypatch.setattr(
        factory, "build_camera", lambda config, selected: _PortAwareCamera(selected, discovery)
    )
    config = make_config(tmp_path)
    config.hardware.camera.reconnect_backoff_seconds = [1.0]
    manager = CameraManager(config)
    manager._discovery = discovery
    manager.rebuild()
    assert manager.camera.available() is True

    now = datetime(2026, 8, 16, 20, 0, 0)
    discovery.cameras_list = []  # battery out
    manager.rediscover_if_missing(now)  # arms the retry
    discovery.cameras_list = [_nikon("usb:001,005")]  # back, new device number

    assert manager.rediscover_if_missing(now + timedelta(seconds=2)) is True
    assert manager.selected_camera.port == "usb:001,005"
    assert manager.camera.available() is True
    # No photo had to be sacrificed to notice.


def test_the_stale_handle_is_dropped_before_looking_again(tmp_path, monkeypatch):
    """The dead handle of a switched-off camera must not be reused (-52)."""
    closed: list[int] = []
    monkeypatch.setattr(factory, "close_session", lambda: closed.append(1))
    manager = _missing_camera_manager(tmp_path, monkeypatch)
    now = datetime(2026, 8, 16, 20, 0, 0)

    manager.rediscover_if_missing(now)
    assert closed == []  # first tick only arms the retry
    manager.rediscover_if_missing(now + timedelta(seconds=5))
    assert closed == [1]


def test_the_retry_interval_is_capped_once_a_camera_has_been_seen(tmp_path, monkeypatch):
    """Waiting 30 s is fine before any camera has shown up; after a battery
    change it is half a minute of quietly shooting with the webcam."""
    discovery = _CountingDiscovery([_nikon("usb:001,004")])
    monkeypatch.setattr(
        factory, "build_camera", lambda config, selected: _PortAwareCamera(selected, discovery)
    )
    config = make_config(tmp_path)
    config.hardware.camera.reconnect_backoff_seconds = [1.0, 30.0]
    config.hardware.camera.reconnect_max_seconds = 10.0
    manager = CameraManager(config)
    manager._discovery = discovery
    manager.rebuild()

    now = datetime(2026, 8, 16, 20, 0, 0)
    manager.rediscover_if_missing(now)  # camera present → remembers it was seen
    discovery.cameras_list = []
    manager.rediscover_if_missing(now)  # arms the retry at +1 s
    manager.rediscover_if_missing(now + timedelta(seconds=2))  # step up: capped to 10, not 30

    discovery.cameras_list = [_nikon("usb:001,009")]
    # Next attempt is 10 s after the last one (t=12), not 30 s (t=32).
    assert manager.rediscover_if_missing(now + timedelta(seconds=11)) is False
    assert manager.rediscover_if_missing(now + timedelta(seconds=13)) is True
    assert manager.selected_camera.port == "usb:001,009"


def test_without_a_camera_ever_seen_the_long_wait_stays(tmp_path, monkeypatch):
    """Nothing is lost by looking rarely while no camera has ever been attached."""
    manager = _missing_camera_manager(tmp_path, monkeypatch)
    manager.config.hardware.camera.reconnect_backoff_seconds = [1.0, 30.0]
    manager.config.hardware.camera.reconnect_max_seconds = 10.0

    now = datetime(2026, 8, 16, 20, 0, 0)
    manager.rediscover_if_missing(now)
    manager.rediscover_if_missing(now + timedelta(seconds=2))  # steps to 30 s
    manager._discovery.cameras_list = _cams()
    assert manager.rediscover_if_missing(now + timedelta(seconds=11)) is False
    assert manager.rediscover_if_missing(now + timedelta(seconds=33)) is True


# --- preview device disappears ----------------------------------------------
#
# Reported from the box: the webcam was unplugged and the kiosk had no live image
# at all, even though the DSLR was attached and can serve one. The preview device
# was resolved once at startup and never looked at again.


class _SwitchablePreview:
    """Available only while its device is still in the discovery list."""

    def __init__(self, selected, discovery):
        self.selected = selected
        self._discovery = discovery
        self.closed = False

    def available(self) -> bool:
        if self.selected is None:
            return False
        return any(p.device == self.selected.device for p in self._discovery.previews_list)

    def frame(self) -> bytes:
        return b"\xff\xd8\xff"

    def close(self) -> None:
        self.closed = True


class _PreviewDiscovery:
    def __init__(self, previews):
        self.previews_list = list(previews)

    def cameras(self):
        return []

    def previews(self):
        return list(self.previews_list)


def _webcam():
    return DetectedPreview(id="/dev/video0", name="eMeet", device="/dev/video0", backend="v4l2")


def _dslr_preview():
    return DetectedPreview(
        id="usb:001,004", name="Nikon DSC D7200", device="usb:001,004", backend="gphoto2"
    )


def _preview_manager(tmp_path, monkeypatch, discovery):
    monkeypatch.setattr(
        factory,
        "build_preview",
        lambda config, selected, camera=None: _SwitchablePreview(selected, discovery),
    )
    config = make_config(tmp_path)
    config.hardware.camera.reconnect_backoff_seconds = [1.0]
    manager = CameraManager(config)
    manager._discovery = discovery
    manager.rebuild()
    return manager


def test_a_second_webcam_takes_over_when_the_first_is_unplugged(tmp_path, monkeypatch):
    other = DetectedPreview(id="/dev/video2", name="Logitech", device="/dev/video2", backend="v4l2")
    discovery = _PreviewDiscovery([_webcam(), other])
    manager = _preview_manager(tmp_path, monkeypatch, discovery)
    assert manager.selected_preview.device == "/dev/video0"

    now = datetime(2026, 8, 16, 21, 0, 0)
    discovery.previews_list = [other]  # first webcam pulled
    assert manager.repair_preview_if_missing(now) is False  # arms the retry
    assert manager.repair_preview_if_missing(now + timedelta(seconds=2)) is True
    assert manager.selected_preview.device == "/dev/video2"
    assert manager.backends.preview.available() is True


def test_the_dslr_never_takes_over_by_itself(tmp_path, monkeypatch):
    """A mirrored body flips the mirror up for live view and is empty within the
    hour. Reported for the D7200 — the live image is not worth the battery."""
    discovery = _PreviewDiscovery([_webcam(), _dslr_preview()])
    manager = _preview_manager(tmp_path, monkeypatch, discovery)

    now = datetime(2026, 8, 16, 21, 0, 0)
    discovery.previews_list = [_dslr_preview()]  # only the DSLR left
    manager.repair_preview_if_missing(now)
    assert manager.repair_preview_if_missing(now + timedelta(seconds=2)) is False
    assert manager.selected_preview is None  # no live image beats a dead battery


def test_the_dslr_is_used_when_it_is_asked_for(tmp_path, monkeypatch):
    """Explicitly configured, it is a fine preview — a mirrorless a7 IV delivers
    1024x768 in 9-34 ms without any mechanical part moving."""
    discovery = _PreviewDiscovery([_webcam(), _dslr_preview()])
    monkeypatch.setattr(
        factory,
        "build_preview",
        lambda config, selected, camera=None: _SwitchablePreview(selected, discovery),
    )
    config = make_config(
        tmp_path, hardware__preview__backend="gphoto2", hardware__preview__device="auto"
    )
    manager = CameraManager(config)
    manager._discovery = discovery
    manager.rebuild()

    assert manager.selected_preview.backend == "gphoto2"


def test_a_working_preview_is_never_torn_down(tmp_path, monkeypatch):
    """Rebuilding costs the live image a moment — only do it when it is gone."""
    discovery = _PreviewDiscovery([_webcam()])
    manager = _preview_manager(tmp_path, monkeypatch, discovery)
    preview = manager.preview

    now = datetime(2026, 8, 16, 21, 0, 0)
    for offset in (0, 5, 60):
        assert manager.repair_preview_if_missing(now + timedelta(seconds=offset)) is False
    assert manager.preview is preview
    assert preview.closed is False


def test_the_fallback_camera_follows_the_new_preview(tmp_path, monkeypatch):
    """Capture falls back to the preview camera — it must not hold the dead one."""
    discovery = _PreviewDiscovery([_webcam(), _dslr_preview()])
    manager = _preview_manager(tmp_path, monkeypatch, discovery)

    now = datetime(2026, 8, 16, 21, 0, 0)
    discovery.previews_list = [_dslr_preview()]
    manager.repair_preview_if_missing(now)
    manager.repair_preview_if_missing(now + timedelta(seconds=2))
    assert manager.camera._preview is manager.preview
