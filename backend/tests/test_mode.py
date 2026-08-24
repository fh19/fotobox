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
    assert "exec sleep infinity" in text
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
