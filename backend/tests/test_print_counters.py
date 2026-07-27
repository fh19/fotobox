"""Print counters (persistent) and the CUPS job status reconciliation.

The counter used to live in the printer backend as a plain attribute, so every
backend start reset it and the admin always saw a full cartridge. These tests
pin down the replacement: outcomes are persisted per job, the per-event count
comes from print_jobs and the running total survives a restart.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import db
from app.clock import RealClock
from app.main import create_app
from tests.conftest import make_config

PIN = {"X-Fotobox-Pin": "2606"}


def _app(tmp_path, **overrides):
    return create_app(make_config(tmp_path, **overrides), RealClock())


def _photo(engine) -> int:
    return db.insert_photo(
        engine.conn,
        event_id=engine.active_event["id"],
        captured_at=engine.clock.now(),
        background_id=None,
        background_mode=None,
        camera_model=None,
        width=None,
        height=None,
    )


def _queue_job(engine, photo_id: int, cups_job_id: int) -> int:
    job_id = db.insert_print_job(
        engine.conn,
        photo_id=photo_id,
        cups_job_id=cups_job_id,
        requested_at=engine.clock.now(),
        status="queued",
    )
    engine.conn.commit()
    return job_id


def test_reconcile_marks_done_and_counts(tmp_path):
    engine = _app(tmp_path).state.engine
    photo_id = _photo(engine)
    printer = engine.backends.printer
    cups_job_id = printer.submit("/tmp/x.jpg")  # mock finishes jobs right away
    _queue_job(engine, photo_id, cups_job_id)

    assert engine.reconcile_print_jobs() == 1

    status = engine.printer_status()
    assert status["prints_done_event"] == 1
    assert status["prints_total"] == 1


def test_failed_and_cancelled_jobs_do_not_count(tmp_path):
    engine = _app(tmp_path).state.engine
    photo_id = _photo(engine)
    printer = engine.backends.printer
    for state in ("failed", "cancelled"):
        job = printer.submit("/tmp/x.jpg")
        printer.set_job_state(job, state)
        _queue_job(engine, photo_id, job)

    engine.reconcile_print_jobs()

    status = engine.printer_status()
    assert status["prints_done_event"] == 0
    assert status["prints_total"] == 0


def test_unknown_job_state_stays_open_for_a_later_pass(tmp_path):
    """A job purged from the CUPS history must not be guessed either way."""
    engine = _app(tmp_path).state.engine
    photo_id = _photo(engine)
    _queue_job(engine, photo_id, 999)  # never submitted → mock returns None

    assert engine.reconcile_print_jobs() == 0
    assert len(db.pending_print_jobs(engine.conn)) == 1
    assert engine.printer_status()["prints_total"] == 0


def test_counters_survive_a_restart(tmp_path):
    """The old counter reset to the full cartridge on every start."""
    engine = _app(tmp_path).state.engine
    photo_id = _photo(engine)
    job = engine.backends.printer.submit("/tmp/x.jpg")
    _queue_job(engine, photo_id, job)
    engine.reconcile_print_jobs()
    assert engine.printer_status()["prints_total"] == 1

    # Same data directory, fresh engine — as after a reboot.
    restarted = _app(tmp_path).state.engine
    status = restarted.printer_status()
    assert status["prints_total"] == 1
    assert status["prints_done_event"] == 1


def test_reset_zeroes_total_but_keeps_event_history(tmp_path):
    app = _app(tmp_path)
    engine = app.state.engine
    photo_id = _photo(engine)
    job = engine.backends.printer.submit("/tmp/x.jpg")
    _queue_job(engine, photo_id, job)
    engine.reconcile_print_jobs()

    body = TestClient(app).post("/api/admin/printer/counter-reset", headers=PIN).json()
    assert body["prints_total"] == 0
    # The per-event figure is history from print_jobs, not a counter.
    assert body["prints_done_event"] == 1


def test_max_per_event_still_counts_submitted_jobs(tmp_path):
    """Regression guard: the limit must bite when a job is queued, not only
    once it finished — otherwise a stalled queue lets prints through."""
    app = _app(tmp_path, printing__max_per_event=1)
    engine = app.state.engine
    photo_id = _photo(engine)
    _queue_job(engine, photo_id, 4242)  # queued, outcome still open

    assert db.count_event_prints(engine.conn, engine.active_event["id"]) == 1
    assert db.count_event_prints_done(engine.conn, engine.active_event["id"]) == 0
