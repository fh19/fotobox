"""Which personality the box boots into — Fotobox or print server.

The plan in Optimierungen2.md was to detect it from the devices present at boot
("Bildschirm und Webcam verfügbar"). That is the one class of automatic the box
has already been bitten by: USB enumeration is not deterministic at boot, the
failure is silent and total, and a camera three seconds late would decide
whether a wedding gets a photobooth. So it is a choice the operator makes and
the box remembers.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.clock import RealClock
from app.main import create_app
from tests.conftest import make_config

PIN = {"X-Fotobox-Pin": "2606"}


def _client(tmp_path):
    app = create_app(make_config(tmp_path), RealClock())
    return TestClient(app), app.state.engine


def test_without_a_file_it_is_the_photobooth(tmp_path):
    client, engine = _client(tmp_path)
    assert not (engine.config.data_dir / "mode").exists()
    assert client.get("/api/admin/mode", headers=PIN).json()["mode"] == "fotobox"


def test_the_choice_is_written_where_it_survives_the_read_only_root(tmp_path):
    client, engine = _client(tmp_path)
    res = client.post("/api/admin/mode", json={"mode": "printserver"}, headers=PIN)
    assert res.status_code == 200
    assert res.json() == {
        "mode": "printserver",
        "running": "fotobox",
        "reboot_required": True,
    }

    written = engine.config.data_dir / "mode"
    assert written.read_text(encoding="utf-8").strip() == "printserver"
    assert client.get("/api/admin/mode", headers=PIN).json()["mode"] == "printserver"


def test_nonsense_in_the_file_falls_back_to_the_photobooth(tmp_path):
    """A half-written file must not leave the box without a personality."""
    client, engine = _client(tmp_path)
    (engine.config.data_dir / "mode").write_text("halb geschrieben", encoding="utf-8")
    assert client.get("/api/admin/mode", headers=PIN).json()["mode"] == "fotobox"


def test_an_unknown_mode_is_refused(tmp_path):
    client, _ = _client(tmp_path)
    assert client.post("/api/admin/mode", json={"mode": "kaffee"}, headers=PIN).status_code == 409


def test_switching_needs_the_pin(tmp_path):
    client, engine = _client(tmp_path)
    assert client.post("/api/admin/mode", json={"mode": "printserver"}).status_code == 401
    assert client.get("/api/admin/mode").status_code == 401
    assert not (engine.config.data_dir / "mode").exists()


def test_the_kiosk_script_blocks_instead_of_exiting(tmp_path):
    """lwrespawn restarts the script in a loop one second apart, for as long as
    labwc runs — exiting would busy-loop the box."""
    from pathlib import Path

    script = Path(__file__).resolve().parents[2] / "deploy" / "kiosk.sh"
    text = script.read_text(encoding="utf-8")
    assert "printserver" in text
    # Warten statt beenden — und warten heißt hier: die Datei im Auge behalten.
    assert 'while [ "$MODE" = "printserver" ]' in text
    # The mode file is passed in, not hard-coded into the script's logic.
    assert 'MODE_FILE="${2:-/data/mode}"' in text


def test_the_running_mode_is_not_the_chosen_one_until_a_restart(tmp_path):
    """Choosing does not change what is running — that takes a reboot."""
    client, engine = _client(tmp_path)
    client.post("/api/admin/mode", json={"mode": "printserver"}, headers=PIN)

    status = client.get("/api/admin/mode", headers=PIN).json()
    assert status["mode"] == "printserver"
    assert status["running"] == "fotobox"
    assert status["reboot_required"] is True


def test_no_pending_restart_when_the_choice_matches(tmp_path):
    client, engine = _client(tmp_path)
    client.post("/api/admin/mode", json={"mode": "fotobox"}, headers=PIN)
    assert client.get("/api/admin/mode", headers=PIN).json()["reboot_required"] is False


def test_the_lamp_is_left_alone_in_print_server_mode(tmp_path):
    """ "die lampe ist im druckermodus nicht eingesteckt" — so do not reach for
    it, and do not fill the log with failures either."""
    from app.clock import FakeClock

    config = make_config(tmp_path, hardware__lamp__backend="mock")
    (config.data_dir).mkdir(parents=True, exist_ok=True)
    (config.data_dir / "mode").write_text("printserver\n", encoding="utf-8")
    engine = create_app(config, FakeClock()).state.engine

    engine.sm.start()
    assert engine.backends.lamp.calls == []


def test_the_admin_names_the_way_back(tmp_path):
    """Print-server mode has no kiosk, so the route back has to be readable at
    the moment of switching — not in a document the box can no longer show."""
    from pathlib import Path

    js = (Path(__file__).resolve().parents[2] / "frontend" / "admin.js").read_text(encoding="utf-8")
    assert "fotobox.local" in js
    assert "Zurückschalten von einem anderen" in js

    manual = (Path(__file__).resolve().parents[2] / "docs" / "bedienungsanleitung.md").read_text(
        encoding="utf-8"
    )
    assert "Zurück in den Fotobox-Modus" in manual
    assert "192.168.4.1/admin" in manual  # der Weg ohne Netzwerk


# --- back to the photobooth when a camera turns up ---------------------------
#
# Deliberately one-way. A detected camera says something definite; a missing one
# does not, because at boot there is no telling whether a device is absent or
# merely late.


def _cameras(engine, available: bool) -> None:
    """Both backends report the same thing; the camera sits in a fallback
    wrapper, so there is no set_available() to reach for."""
    engine.backends.camera.available = lambda: available
    engine.backends.preview.available = lambda: available


def _printserver(tmp_path, **overrides):
    from app.clock import FakeClock

    config = make_config(tmp_path, **overrides)
    config.data_dir.mkdir(parents=True, exist_ok=True)
    (config.data_dir / "mode").write_text("printserver\n", encoding="utf-8")
    clock = FakeClock()
    engine = create_app(config, clock).state.engine
    return engine, clock


def test_a_camera_ends_print_server_mode(tmp_path):
    engine, clock = _printserver(tmp_path)
    assert engine.mode_status()["running"] == "printserver"

    _cameras(engine, False)
    assert engine.consider_camera_return() is False  # arms the trigger
    _cameras(engine, True)
    assert engine.consider_camera_return() is False  # first sighting only
    assert engine.consider_camera_return() is True  # confirmed

    assert engine.kiosk_mode() == "fotobox"
    assert engine.mode_status()["running"] == "fotobox"
    assert (engine.config.data_dir / "mode").read_text(encoding="utf-8").strip() == "fotobox"


def test_one_sighting_is_not_a_camera(tmp_path):
    """The webcam once enumerated and dropped off the bus a second later."""
    engine, clock = _printserver(tmp_path)
    _cameras(engine, False)
    engine.consider_camera_return()  # armed
    _cameras(engine, True)
    engine.consider_camera_return()  # seen once

    _cameras(engine, False)
    assert engine.consider_camera_return() is False

    _cameras(engine, True)
    assert engine.consider_camera_return() is False  # counting starts over
    assert engine.kiosk_mode() == "printserver"


def test_the_window_closes_when_one_is_configured(tmp_path):
    """Optional: by default there is no window, because the trigger is an edge."""
    engine, clock = _printserver(tmp_path, mode__return_grace_seconds=120)
    _cameras(engine, False)

    clock.advance(engine.config.mode.return_grace_seconds + 1)
    assert engine.consider_camera_return() is False
    assert engine.mode_watch_finished is True

    _cameras(engine, True)
    assert engine.consider_camera_return() is False
    assert engine.kiosk_mode() == "printserver"


def test_it_never_runs_the_other_way(tmp_path):
    """Nothing turns a photobooth into a print server on its own."""
    client, engine = _client(tmp_path)  # boots as fotobox
    assert engine.mode_watch_finished is True
    _cameras(engine, True)

    assert engine.consider_camera_return() is False
    assert engine.kiosk_mode() == "fotobox"


def test_it_can_be_switched_off(tmp_path):
    engine, clock = _printserver(tmp_path, mode__return_on_camera=False)
    _cameras(engine, False)
    engine.consider_camera_return()
    _cameras(engine, True)
    assert engine.consider_camera_return() is False
    assert engine.consider_camera_return() is False
    assert engine.kiosk_mode() == "printserver"


def test_a_camera_that_never_left_does_not_trigger(tmp_path):
    """Switching to print server with the camera still plugged in must stick —
    otherwise the mode would be unreachable, undone by the next check."""
    engine, clock = _printserver(tmp_path)
    _cameras(engine, True)

    for _ in range(10):
        assert engine.consider_camera_return() is False
    assert engine.kiosk_mode() == "printserver"
    assert engine.mode_status()["running"] == "printserver"


def test_unplugging_and_plugging_back_in_is_what_triggers_it(tmp_path):
    """The trigger is the edge, not the level."""
    engine, clock = _printserver(tmp_path)
    _cameras(engine, True)
    assert engine.consider_camera_return() is False  # still attached, nothing

    _cameras(engine, False)
    assert engine.consider_camera_return() is False  # now armed
    _cameras(engine, True)
    engine.consider_camera_return()
    assert engine.consider_camera_return() is True


def test_the_kiosk_picks_the_change_up_without_a_reboot(tmp_path):
    """Rebooting a print server would throw away its queue (tmpfs spool)."""
    from pathlib import Path

    script = (Path(__file__).resolve().parents[2] / "deploy" / "kiosk.sh").read_text(
        encoding="utf-8"
    )
    assert 'while [ "$MODE" = "printserver" ]' in script
    assert "exec sleep infinity" not in script  # would never notice the change
