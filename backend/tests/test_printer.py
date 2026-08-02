"""Printer admin operations (M6), mock-backed."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import db
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
        "prints_done_event",
        "prints_total",
        "queue_length",
    }


def test_resume_re_enables_after_paper_out(tmp_path):
    app = _app(tmp_path)
    app.state.engine.backends.printer.set_paused(True)
    assert app.state.engine.backends.printer.available() is False
    body = TestClient(app).post("/api/admin/printer/resume", headers=PIN).json()
    assert body["paused"] is False
    assert body["available"] is True


def test_counter_reset_zeroes_the_running_total(tmp_path):
    app = _app(tmp_path)
    engine = app.state.engine
    db.increment_counter(engine.conn, "prints_total", 7)
    engine.conn.commit()
    assert engine.printer_status()["prints_total"] == 7

    body = TestClient(app).post("/api/admin/printer/counter-reset", headers=PIN).json()
    assert body["prints_total"] == 0


def test_cancel_all(tmp_path):
    client = TestClient(_app(tmp_path))
    assert client.post("/api/admin/printer/cancel-all", headers=PIN).status_code == 200


def test_test_page_submits_a_job(tmp_path):
    client = TestClient(_app(tmp_path))
    res = client.post("/api/admin/printer/test-page", headers=PIN)
    assert res.status_code == 200
    assert "job_id" in res.json()


# --- paper out: say why, and come back on your own --------------------------
#
# Reported from a real evening: an empty tray showed up only as "nicht
# verfügbar", and after refilling the box stayed unavailable — CUPS keeps the
# queue stopped until someone runs cupsenable.


def test_status_names_the_problem(tmp_path):
    app = _app(tmp_path)
    app.state.engine.backends.printer.set_reason("media_empty")
    client = TestClient(app)

    assert client.get("/api/status").json()["printer"]["message"] == "Kein Papier"
    assert client.get("/api/admin/printer", headers=PIN).json()["message"] == "Kein Papier"


def test_no_message_while_everything_is_fine(tmp_path):
    client = TestClient(_app(tmp_path))
    assert client.get("/api/status").json()["printer"]["message"] is None


def test_refilled_paper_recovers_without_the_admin(tmp_path, clock):
    engine = create_app(make_config(tmp_path), clock).state.engine
    printer = engine.backends.printer
    printer.set_reason("media_empty")
    interval = engine.config.hardware.printer.auto_resume_seconds

    engine.tick()  # first tick only arms the retry
    assert printer.paused() is True

    clock.advance(interval + 1)
    engine.tick()
    assert printer.paused() is False
    assert printer.available() is True
    assert engine.build_status()["printer"]["message"] is None


def test_an_empty_tray_keeps_the_queue_stopped(tmp_path, clock):
    """Retrying is harmless: with the supply still out it just stops again."""
    engine = create_app(make_config(tmp_path), clock).state.engine
    printer = engine.backends.printer
    printer.supply_empty = True
    printer.set_reason("media_empty")
    interval = engine.config.hardware.printer.auto_resume_seconds

    for _ in range(3):
        engine.tick()
        clock.advance(interval + 1)
        engine.tick()
    assert printer.paused() is True
    assert engine.build_status()["printer"]["message"] == "Kein Papier"


def test_auto_resume_can_be_switched_off(tmp_path, clock):
    config = make_config(tmp_path, hardware__printer__auto_resume_seconds=0)
    engine = create_app(config, clock).state.engine
    engine.backends.printer.set_reason("media_empty")

    engine.tick()
    clock.advance(600)
    engine.tick()
    assert engine.backends.printer.paused() is True


def test_reason_codes_cover_what_cups_reports():
    """The strings CUPS puts in printer-state-reasons, mapped to our codes."""
    from app.hardware.cups_printer import _is_blocking, _reason_code

    assert _reason_code("media-empty-error") == "media_empty"
    assert _reason_code("media-empty-warning") == "media_empty"
    assert _reason_code("media-needed") == "media_empty"
    assert _reason_code("marker-supply-empty-error") == "ribbon_empty"
    assert _reason_code("media-jam-error") == "jam"
    assert _reason_code("cover-open-warning") == "cover_open"
    assert _reason_code("door-open-report") == "cover_open"
    assert _reason_code("offline-report") == "offline"
    assert _reason_code("none") is None
    assert _reason_code("marker-supply-low-warning") is None  # low is not empty

    assert _is_blocking("media-empty-error") is True
    assert _is_blocking("none") is False


def test_the_reason_is_read_from_the_message_too(tmp_path):
    """Seen on the box: cupsdisable -r leaves reasons=['paused'] and puts the
    real cause in printer-state-message. Both shapes have to be understood."""
    from app.config import Config
    from app.hardware.cups_printer import CupsPrinter

    printer = CupsPrinter(make_config(tmp_path))
    assert isinstance(printer._config, Config)

    printer._attrs = lambda: {
        "printer-state": 5,
        "printer-state-reasons": ["paused"],
        "printer-state-message": "media-empty-error",
    }
    assert printer.reason() == "media_empty"

    printer._attrs = lambda: {
        "printer-state": 5,
        "printer-state-reasons": ["media-jam-error"],
        "printer-state-message": "",
    }
    assert printer.reason() == "jam"

    printer._attrs = lambda: {
        "printer-state": 5,
        "printer-state-reasons": ["paused"],
        "printer-state-message": "",
    }
    assert printer.reason() == "stopped"

    printer._attrs = lambda: {
        "printer-state": 3,
        "printer-state-reasons": ["none"],
        "printer-state-message": "",
    }
    assert printer.reason() is None
