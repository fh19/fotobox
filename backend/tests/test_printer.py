"""Printer admin operations (M6), mock-backed."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.clock import RealClock
from app.main import create_app
from tests.conftest import make_config

PIN = {"X-Fotobox-Pin": "2606"}


def _app(tmp_path, **overrides):
    return create_app(make_config(tmp_path, **overrides), RealClock())


def test_printer_endpoints_require_pin(tmp_path):
    client = TestClient(_app(tmp_path))
    assert client.get("/api/admin/printer").status_code == 401
    assert client.post("/api/admin/printer/resume").status_code == 401


def test_printer_status_shape(tmp_path):
    client = TestClient(_app(tmp_path))
    body = client.get("/api/admin/printer", headers=PIN).json()
    assert set(body) >= {
        "available",
        "state",
        "paused",
        "prints_remaining_estimate",
        "queue_length",
    }


def test_resume_re_enables_after_paper_out(tmp_path):
    app = _app(tmp_path)
    app.state.engine.backends.printer.set_paused(True)
    assert app.state.engine.backends.printer.available() is False
    body = TestClient(app).post("/api/admin/printer/resume", headers=PIN).json()
    assert body["paused"] is False
    assert body["available"] is True


def test_paper_reset_restores_counter(tmp_path):
    app = _app(tmp_path)
    app.state.engine.backends.printer._remaining = 5
    body = TestClient(app).post("/api/admin/printer/paper-reset", headers=PIN).json()
    assert body["prints_remaining_estimate"] == 108


def test_cancel_all(tmp_path):
    client = TestClient(_app(tmp_path))
    assert client.post("/api/admin/printer/cancel-all", headers=PIN).status_code == 200


def test_test_page_submits_a_job(tmp_path):
    client = TestClient(_app(tmp_path))
    res = client.post("/api/admin/printer/test-page", headers=PIN)
    assert res.status_code == 200
    assert "job_id" in res.json()
