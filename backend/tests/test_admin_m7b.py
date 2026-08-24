"""M7b: guest access point toggle and USB event export (admin API)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app import system
from app.clock import RealClock
from app.main import create_app
from tests.conftest import make_config

PIN = {"X-Fotobox-Pin": "2606"}  # matches config.example.yaml admin_pin


def _client(tmp_path, **overrides):
    return TestClient(create_app(make_config(tmp_path, **overrides), RealClock()))


# --- network / access point -------------------------------------------------


def test_network_requires_pin(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/admin/network").status_code == 401
    assert client.post("/api/admin/network/ap", json={"enabled": True}).status_code == 401


def test_network_status_reports_client_ip(tmp_path, monkeypatch):
    monkeypatch.setattr(system, "ap_active", lambda: False)
    monkeypatch.setattr(system, "primary_ip", lambda: "192.168.0.134")
    client = _client(tmp_path)
    body = client.get("/api/admin/network", headers=PIN).json()
    assert body == {
        "ap_enabled": False,
        "ap_auto": True,
        "ssid": "Fotobox",
        "ip": "192.168.0.134",
    }


def test_ap_toggle_on_and_off(tmp_path, monkeypatch):
    calls = {"enabled": False}
    monkeypatch.setattr(system, "primary_ip", lambda: "192.168.0.134")
    monkeypatch.setattr(system, "ap_active", lambda: calls["enabled"])

    def fake_enable(ssid, passphrase, channel, address, captive=False):
        calls.update(enabled=True, ssid=ssid, address=address, captive=captive)

    monkeypatch.setattr(system, "ap_enable", fake_enable)
    monkeypatch.setattr(system, "ap_disable", lambda: calls.update(enabled=False))

    client = _client(tmp_path)
    on = client.post("/api/admin/network/ap", json={"enabled": True}, headers=PIN).json()
    assert on == {"ap_enabled": True, "ap_auto": True, "ssid": "Fotobox", "ip": "192.168.4.1"}
    assert calls["ssid"] == "Fotobox" and calls["address"] == "192.168.4.1"
    assert calls["captive"] is True  # guests land in the gallery on connecting

    off = client.post("/api/admin/network/ap", json={"enabled": False}, headers=PIN).json()
    assert off["ap_enabled"] is False
    assert off["ip"] == "192.168.0.134"  # back to the client IP


def test_ap_failure_is_a_clean_409(tmp_path, monkeypatch):
    def boom(*a):
        raise RuntimeError("nmcli fehlt")

    monkeypatch.setattr(system, "ap_enable", boom)
    client = _client(tmp_path)
    res = client.post("/api/admin/network/ap", json={"enabled": True}, headers=PIN)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "ap_failed"


# --- USB export -------------------------------------------------------------


def test_export_no_usb_is_409(tmp_path, monkeypatch):
    monkeypatch.setattr(system, "find_usb_storage", lambda: None)
    client = _client(tmp_path)
    res = client.post("/api/admin/export/usb", headers=PIN)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "no_usb"


def test_export_copies_event_and_reports_progress(tmp_path, monkeypatch):
    client = _client(tmp_path)
    engine = client.app.state.engine

    # Populate the active event with a couple of files across variants.
    event_dir = engine._event_dir()
    (event_dir / "originals" / "IMG_0001.jpg").write_bytes(b"a" * 100)
    (event_dir / "processed" / "IMG_0001.jpg").write_bytes(b"b" * 200)
    (event_dir / "thumbs" / "IMG_0001.jpg").write_bytes(b"c" * 50)

    stick_mount = tmp_path / "usb"
    stick_mount.mkdir()
    monkeypatch.setattr(
        system, "find_usb_storage", lambda: {"device": "/dev/fake1", "fstype": "vfat"}
    )
    monkeypatch.setattr(system, "mount_usb", lambda device, fstype: stick_mount)
    monkeypatch.setattr(system, "unmount_usb", lambda: None)

    start = client.post("/api/admin/export/usb", headers=PIN).json()
    assert start["started"] is True
    assert start["total"] == 3

    # Poll until the background copy finishes.
    for _ in range(100):
        status = client.get("/api/admin/export/usb", headers=PIN).json()
        if status["finished"]:
            break
        time.sleep(0.02)
    assert status["finished"] is True
    assert status["error"] is None
    assert status["done"] == 3
    assert status["bytes"] == 350

    target = stick_mount / f"Fotobox_{engine.active_event['directory']}"
    assert (target / "originals" / "IMG_0001.jpg").read_bytes() == b"a" * 100
    assert (target / "processed" / "IMG_0001.jpg").read_bytes() == b"b" * 200
    assert (target / "thumbs" / "IMG_0001.jpg").read_bytes() == b"c" * 50


def test_export_busy_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(
        system, "find_usb_storage", lambda: {"device": "/dev/fake1", "fstype": "vfat"}
    )
    client = _client(tmp_path)
    engine = client.app.state.engine
    engine._export["running"] = True  # pretend an export is in flight
    res = client.post("/api/admin/export/usb", headers=PIN)
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "export_busy"


# --- the access point comes up on its own ------------------------------------
#
# "AP automatisch einschalten, wenn keine Verbindung zum Heimnetzwerk": at a
# venue there is no home WiFi, and somebody had to notice and flip the switch.


def _offline_engine(tmp_path, monkeypatch, *, connected=False, ap_on=False, **overrides):
    from app.clock import FakeClock

    clock = FakeClock()
    app = create_app(make_config(tmp_path, **overrides), clock)
    monkeypatch.setattr(system, "network_connected", lambda: connected)
    monkeypatch.setattr(system, "ap_active", lambda: ap_on)
    switched = []
    monkeypatch.setattr(
        app.state.engine, "network_ap", lambda enabled: switched.append(enabled) or {}
    )
    return app.state.engine, clock, switched


def test_a_short_outage_does_not_open_the_access_point(tmp_path, monkeypatch):
    """A router reboot must not throw the box into AP mode."""
    engine, clock, switched = _offline_engine(tmp_path, monkeypatch)

    assert engine.consider_offline_ap() is False  # first look: only remembers
    clock.advance(60)  # grace is 120 s
    assert engine.consider_offline_ap() is False
    assert switched == []


def test_a_lasting_outage_opens_the_access_point(tmp_path, monkeypatch):
    engine, clock, switched = _offline_engine(tmp_path, monkeypatch)

    engine.consider_offline_ap()
    clock.advance(121)
    assert engine.consider_offline_ap() is True
    assert switched == [True]


def test_the_timer_restarts_when_the_network_returns(tmp_path, monkeypatch):
    engine, clock, switched = _offline_engine(tmp_path, monkeypatch)
    engine.consider_offline_ap()
    clock.advance(119)

    monkeypatch.setattr(system, "network_connected", lambda: True)
    engine.consider_offline_ap()  # back → forget how long we were away
    monkeypatch.setattr(system, "network_connected", lambda: False)
    engine.consider_offline_ap()
    clock.advance(60)

    assert engine.consider_offline_ap() is False
    assert switched == []


def test_a_running_access_point_is_left_alone(tmp_path, monkeypatch):
    engine, clock, switched = _offline_engine(tmp_path, monkeypatch, ap_on=True)
    engine.consider_offline_ap()
    clock.advance(300)
    assert engine.consider_offline_ap() is False
    assert switched == []


def test_the_automatic_can_be_switched_off(tmp_path, monkeypatch):
    engine, clock, switched = _offline_engine(tmp_path, monkeypatch)
    engine.set_ap_auto(False)

    engine.consider_offline_ap()
    clock.advance(600)

    assert engine.consider_offline_ap() is False
    assert switched == []


def test_the_switch_survives_a_restart(tmp_path, monkeypatch):
    """Persisted, or every reboot would re-arm what the operator turned off."""
    from app.config import load_config, save_config

    path = tmp_path / "config.yaml"
    save_config(make_config(tmp_path), path)
    with TestClient(create_app(config_path=path)) as client:
        res = client.post("/api/admin/network/ap-auto", json={"enabled": False}, headers=PIN)
    assert res.status_code == 200
    assert res.json()["ap_auto"] is False
    assert load_config(path).network.access_point.auto_when_offline is False


def test_an_unclear_answer_counts_as_connected(tmp_path, monkeypatch):
    """`ip` failing is not proof of an outage — never open the AP on a hiccup."""

    def boom(*args, **kwargs):
        raise OSError("no ip command")

    monkeypatch.setattr(system.subprocess, "run", boom)
    assert system.network_connected() is True


def test_an_outage_after_a_working_network_is_waited_out(tmp_path, monkeypatch):
    """The box was connected and lost it — that is roaming or a router hiccup.
    Opening the AP takes wlan0 away and the recovery can never happen.

    Not theory: with a mesh SSID the box bounced between nodes for two minutes,
    the AP came up in that window, and it stayed off the network until somebody
    switched it off by hand.
    """
    engine, clock, switched = _offline_engine(tmp_path, monkeypatch, connected=True)
    engine.consider_offline_ap()  # sees a network

    monkeypatch.setattr(system, "network_connected", lambda: False)
    engine.consider_offline_ap()
    clock.advance(10 * engine.config.network.access_point.auto_grace_seconds)

    assert engine.consider_offline_ap() is False
    assert switched == []


def test_a_venue_without_any_network_still_gets_the_access_point(tmp_path, monkeypatch):
    """Never connected since the start — that is the case the feature is for."""
    engine, clock, switched = _offline_engine(tmp_path, monkeypatch, connected=False)

    engine.consider_offline_ap()
    clock.advance(engine.config.network.access_point.auto_grace_seconds + 1)

    assert engine.consider_offline_ap() is True
    assert switched == [True]
