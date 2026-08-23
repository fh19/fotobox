"""Admin auth (PIN + lockout) and runtime config/event (M7)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.clock import RealClock
from app.main import create_app
from tests.conftest import make_config

PIN = {"X-Fotobox-Pin": "2606"}
WRONG = {"X-Fotobox-Pin": "0000"}


def _app(tmp_path, **overrides):
    return create_app(make_config(tmp_path, **overrides), RealClock())


def test_auth_accepts_and_rejects(tmp_path):
    client = TestClient(_app(tmp_path))
    assert client.post("/api/admin/auth", headers=PIN).status_code == 200
    assert client.post("/api/admin/auth", headers=WRONG).status_code == 401


def test_lockout_after_five_wrong(tmp_path):
    client = TestClient(_app(tmp_path))
    for _ in range(5):
        assert client.post("/api/admin/auth", headers=WRONG).status_code == 401
    # Locked now — even the correct PIN is refused with 423 + Retry-After.
    locked = client.post("/api/admin/auth", headers=PIN)
    assert locked.status_code == 423
    assert "retry-after" in {k.lower() for k in locked.headers}


def test_every_admin_endpoint_needs_pin(tmp_path):
    client = TestClient(_app(tmp_path))
    for path in (
        "/api/admin/config",
        "/api/admin/system",
        "/api/admin/printer",
        "/api/admin/cameras",
    ):
        assert client.get(path).status_code == 401


def test_config_get_returns_editable_sections(tmp_path):
    client = TestClient(_app(tmp_path))
    body = client.get("/api/admin/config", headers=PIN).json()
    assert set(body) == {"ui", "countdown", "timeouts", "printing", "screensaver"}


def test_config_put_changes_countdown_live(tmp_path):
    app = _app(tmp_path)
    res = TestClient(app).put(
        "/api/admin/config", headers=PIN, json={"countdown": {"duration_seconds": 3}}
    )
    assert res.status_code == 200
    assert app.state.engine.config.countdown.duration_seconds == 3


def test_config_put_changes_the_fill_flash(tmp_path):
    """The white screen at capture time is a matter of taste and of the room."""
    app = _app(tmp_path)
    res = TestClient(app).put(
        "/api/admin/config",
        headers=PIN,
        json={"ui": {"flash_enabled": True, "flash_duration_ms": 250}},
    )
    assert res.status_code == 200
    assert app.state.engine.config.ui.flash_enabled is True
    assert app.state.engine.config.ui.flash_duration_ms == 250
    # The kiosk reads it from client-config when the page loads.
    assert TestClient(app).get("/api/client-config").json()["flash_enabled"] is True


def test_config_put_rejects_non_editable_section(tmp_path):
    client = TestClient(_app(tmp_path))
    res = client.put("/api/admin/config", headers=PIN, json={"hardware": {"mode": "real"}})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "invalid_key"


def test_config_put_validates_values(tmp_path):
    client = TestClient(_app(tmp_path))
    res = client.put("/api/admin/config", headers=PIN, json={"countdown": {"duration_seconds": 0}})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "invalid_value"


def test_create_event_becomes_active(tmp_path):
    app = _app(tmp_path)
    res = TestClient(app).post("/api/admin/event", headers=PIN, json={"name": "Hochzeit Test"})
    assert res.status_code == 200
    assert res.json()["name"] == "Hochzeit Test"
    assert app.state.engine.active_event["name"] == "Hochzeit Test"


def test_system_info(tmp_path):
    body = TestClient(_app(tmp_path)).get("/api/admin/system", headers=PIN).json()
    assert "storage" in body and "versions" in body and "printer" in body


def test_admin_page_served(tmp_path):
    res = TestClient(_app(tmp_path)).get("/admin")
    assert res.status_code == 200
    assert "Admin" in res.text
