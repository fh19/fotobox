"""Frontend serving and M2 guarantees: verbatim texts, no external resources."""

from __future__ import annotations

import re

import pytest
from fastapi.testclient import TestClient

from app.clock import RealClock
from app.main import FRONTEND_DIR, create_app
from tests.conftest import make_config

# The exact German strings from docs/ui-screens.md. Wortgleich — nicht umformulieren.
REQUIRED_TEXTS = [
    "Bereit für dein Foto?",
    "Tippe auf den Bildschirm",
    "Drucken ist gerade nicht möglich — Fotos werden gespeichert",
    "Kleine Pause",
    "Die Fotobox ist gleich wieder da",
    "Wähle deinen Hintergrund",
    "Ohne Hintergrund",
    "Abbrechen",
    "Lächeln!",
    "Einen Moment …",
    "Dein Foto wird fertig gemacht",
    "Gleich ist es soweit",
    "Drucken",
    "Fertig",
    "Wird gedruckt …",
    "Da ist etwas schiefgelaufen",
    "Versuch es gleich noch einmal",
    "Verbindung wird wiederhergestellt …",
]


@pytest.fixture
def client(tmp_path):
    app = create_app(make_config(tmp_path), RealClock())
    with TestClient(app) as test_client:
        yield test_client


def _frontend_source() -> str:
    parts = []
    for name in ("index.html", "style.css", "app.js"):
        parts.append((FRONTEND_DIR / name).read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_index_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Fotobox" in response.text


def test_static_assets_served(client):
    for path, content_type in (("/style.css", "text/css"), ("/app.js", "javascript")):
        response = client.get(path)
        assert response.status_code == 200
        assert content_type in response.headers["content-type"]


def test_client_config_exposes_ui_timings(client):
    body = client.get("/api/client-config").json()
    assert set(body) >= {
        "mirror_preview",
        "idle_hint_pulse",
        "processing_warn_seconds",
        "preview_seconds",
    }
    assert "admin_pin" not in body  # no secrets leak to the guest UI


def test_all_screen_texts_present():
    source = _frontend_source()
    missing = [text for text in REQUIRED_TEXTS if text not in source]
    assert not missing, f"Fehlende UI-Texte: {missing}"


def test_no_external_resources():
    """No CDN/font/host references — everything is served from localhost."""
    source = _frontend_source()
    forbidden = re.findall(r"https?://[^\s\"')]+", source)
    # A ws(s):// URL built from location.host at runtime is fine; literal http(s)
    # hosts are not.
    assert forbidden == [], f"Externe Ressourcen referenziert: {forbidden}"
    for needle in ("googleapis", "gstatic", "cdn.", "unpkg", "jsdelivr", "//fonts"):
        assert needle not in source, f"Externe Referenz gefunden: {needle}"


def test_viewport_disables_zoom():
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    assert "user-scalable=no" in html
    assert "maximum-scale=1" in html
