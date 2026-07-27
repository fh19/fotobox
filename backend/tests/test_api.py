"""HTTP and WebSocket surface via the ASGI app (mock hardware, real clock)."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.clock import RealClock
from app.main import create_app
from tests.conftest import make_config


@pytest.fixture
def client(tmp_path):
    app = create_app(make_config(tmp_path, countdown__duration_seconds=2), RealClock())
    with TestClient(app) as test_client:
        yield test_client


def test_status_starts_idle(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "IDLE"
    assert body["session"] is None


def test_backgrounds_lists_ohne_hintergrund(client):
    body = client.get("/api/backgrounds").json()
    ids = [bg["id"] for bg in body["backgrounds"]]
    assert "none" in ids
    assert body["backgrounds"][0]["name"] == "Ohne Hintergrund"


def test_print_in_idle_is_conflict(client):
    response = client.post("/api/session/print")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state"


def test_background_in_idle_is_conflict(client):
    response = client.post("/api/session/background", json={"background_id": "none"})
    assert response.status_code == 409


def test_unknown_background_is_not_found(client):
    client.post("/api/session/start")
    response = client.post("/api/session/background", json={"background_id": "mars"})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_background"


def test_start_moves_to_background_select(client):
    response = client.post("/api/session/start")
    assert response.status_code == 200
    assert response.json()["state"] == "BACKGROUND_SELECT"


def test_websocket_receives_full_flow(client):
    with client.websocket_connect("/ws") as ws:
        client.post("/api/session/start")
        client.post("/api/session/background", json={"background_id": "none"})

        states: list[str] = []
        ticks: list[int] = []
        deadline = time.time() + 15
        while time.time() < deadline:
            message = ws.receive_json()
            if message["type"] == "state_changed":
                payload = message["payload"]
                # Every state_changed carries the complete status object.
                assert {"state", "session", "printer", "camera", "event"} <= payload.keys()
                states.append(payload["state"])
                if payload["state"] == "PREVIEW":
                    break
            elif message["type"] == "countdown_tick":
                ticks.append(message["payload"]["remaining"])

        assert states == [
            "BACKGROUND_SELECT",
            "COUNTDOWN",
            "CAPTURE",
            "PROCESSING",
            "PREVIEW",
        ]
        # Exactly countdown.duration_seconds ticks.
        assert ticks == [2, 1]
