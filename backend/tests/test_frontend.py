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


# --- gallery tile shape -----------------------------------------------------
#
# Reported from the box: the gallery showed portrait tiles, so every landscape
# photo was cropped down its middle. The shape has to follow the photos.


def test_client_config_reports_the_photo_aspect(tmp_path):
    landscape = TestClient(create_app(make_config(tmp_path, printing__orientation="landscape")))
    assert landscape.get("/api/client-config").json()["photo_aspect"] > 1

    portrait = TestClient(create_app(make_config(tmp_path, printing__orientation="portrait")))
    assert portrait.get("/api/client-config").json()["photo_aspect"] < 1


def test_the_gallery_takes_its_tile_shape_from_the_config(tmp_path):
    """No hardcoded aspect in the stylesheet — it reads the custom property."""
    css = (FRONTEND_DIR / "gallery.css").read_text(encoding="utf-8")
    assert "var(--photo-aspect" in css
    assert "aspect-ratio: 2 / 3;" not in css  # the old fixed portrait tile
    js = (FRONTEND_DIR / "gallery.js").read_text(encoding="utf-8")
    assert "photo_aspect" in js and "--photo-aspect" in js


def test_the_kiosk_offers_a_way_into_the_gallery(tmp_path):
    """Looking at the photos was only possible over the guest WiFi before."""
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    assert 'href="/gallery?kiosk=1"' in html
    assert ">Galerie<" in html


def test_the_single_view_can_be_stepped_through_and_printed(tmp_path):
    html = (FRONTEND_DIR / "gallery.html").read_text(encoding="utf-8")
    for element in ("lightbox-prev", "lightbox-next", "lightbox-print", "back-to-box"):
        assert element in html, element
    js = (FRONTEND_DIR / "gallery.js").read_text(encoding="utf-8")
    assert "touchstart" in js and "ArrowRight" in js  # swipe and keyboard
    assert "/print" in js


def test_the_gallery_button_does_not_also_take_a_photo(tmp_path):
    """Reported from the box: tapping "Galerie" opened the gallery *and* started a
    session that then ran unseen in the background. The whole idle screen is the
    shutter, so real controls on it have to be excluded."""
    js = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
    idle = js[js.index('el("screen-idle").addEventListener') :][:400]
    assert 'closest("a, button")' in idle
    assert idle.index('closest("a, button")') < idle.index("session/start")


def test_the_gallery_shows_screen_sized_images(tmp_path):
    """processed/ is composed above print resolution for downloads; decoding it
    made stepping through the photos and the back button feel stuck."""
    js = (FRONTEND_DIR / "gallery.js").read_text(encoding="utf-8")
    assert "photo.print_url" in js
    assert "photo.processed_url" in js  # only as the fallback


def test_frontend_assets_are_revalidated(tmp_path):
    """A cached stylesheet against fresh HTML looks like a broken layout and sends
    you hunting in the wrong direction. Reported from a PC browser: the new
    lightbox controls appeared unstyled and in the wrong place."""
    client = TestClient(create_app(make_config(tmp_path), RealClock()))
    for path in ("/gallery.css", "/gallery.js", "/app.js", "/style.css"):
        res = client.get(path)
        assert res.status_code == 200, path
        assert res.headers.get("cache-control") == "no-cache", path
        assert res.headers.get("etag"), path  # revalidation stays cheap


def test_the_admin_has_an_onscreen_keyboard(tmp_path):
    """ "in der Konfiguration kann man ohne Tastatur nur sehr wenig ändern" — the
    box has a touchscreen and no keyboard."""
    html = (FRONTEND_DIR / "admin.html").read_text(encoding="utf-8")
    assert 'id="osk"' in html
    js = (FRONTEND_DIR / "admin.js").read_text(encoding="utf-8")
    assert "onscreen_keyboard" in js
    # German names need umlauts, and numbers need their own pad.
    assert "ü" in js and "ö" in js and "ä" in js and "ß" in js
    assert "OSK_DIGITS" in js
    # The field must keep focus, or the next key has nowhere to write.
    assert "pointerdown" in js and "preventDefault" in js


def test_the_keyboard_setting_is_configurable(tmp_path):
    client = TestClient(create_app(make_config(tmp_path), RealClock()))
    body = client.get("/api/admin/config", headers={"X-Fotobox-Pin": "2606"}).json()
    assert body["ui"]["onscreen_keyboard"] == "auto"


def test_the_gallery_can_select_and_download_a_subset(tmp_path):
    html = (FRONTEND_DIR / "gallery.html").read_text(encoding="utf-8")
    for element in ("select-mode", "selection-bar", "download-selection", "selection-clear"):
        assert element in html, element
    js = (FRONTEND_DIR / "gallery.js").read_text(encoding="utf-8")
    assert "&ids=" in js and "state.selected" in js


def test_the_keyboard_does_not_trust_the_hover_query(tmp_path):
    """The box's touchscreen registers a mouse device too, so the browser claims
    a hovering pointer and the keyboard never appeared."""
    js = (FRONTEND_DIR / "admin.js").read_text(encoding="utf-8")
    assert "matchMedia" not in js
    assert "maxTouchPoints" in js and 'pointerType === "touch"' in js


def test_the_admin_can_switch_the_automatic_access_point(tmp_path):
    html = (FRONTEND_DIR / "admin.html").read_text(encoding="utf-8")
    assert "net-ap-auto" in html
    assert "Automatisch, wenn kein Netzwerk da ist" in " ".join(html.split())
    js = (FRONTEND_DIR / "admin.js").read_text(encoding="utf-8")
    assert "/api/admin/network/ap-auto" in js


def test_the_admin_gallery_navigates_events_and_deletes(tmp_path):
    """ "Button für Hauptgallerie / von dort aus in die Veranstaltungen
    navigieren / Bilder auswählen können / Download und Löschen anbieten"."""
    admin = (FRONTEND_DIR / "admin.html").read_text(encoding="utf-8")
    assert "/gallery?admin=1" in admin and "Hauptgalerie öffnen" in admin

    js = (FRONTEND_DIR / "gallery.js").read_text(encoding="utf-8")
    assert 'has("admin")' in js  # the guest gallery must not grow a delete button
    assert "event-pick" in (FRONTEND_DIR / "gallery.html").read_text(encoding="utf-8")
    assert "/api/admin/photos/delete" in js
    # The PIN travels in sessionStorage, never in a shareable URL.
    assert "fotobox_pin" in js and "pin=" not in js

    admin_js = (FRONTEND_DIR / "admin.js").read_text(encoding="utf-8")
    assert "/api/admin/photos/purge" in admin_js


def test_the_kiosk_shows_a_slideshow_and_wakes_without_shooting(tmp_path):
    html = (FRONTEND_DIR / "index.html").read_text(encoding="utf-8")
    assert 'id="screen-screensaver"' in html
    assert 'id="saver-a"' in html and 'id="saver-b"' in html  # cross-fade needs two

    css = (FRONTEND_DIR / "style.css").read_text(encoding="utf-8")
    assert 'body[data-state="SCREENSAVER"] #screen-screensaver' in css

    js = (FRONTEND_DIR / "app.js").read_text(encoding="utf-8")
    assert "/api/session/wake" in js
    # The wake tap must not fall through to a capture.
    assert (
        'el("screen-screensaver").addEventListener("click", () => postAction("/api/session/wake"))'
        in js
    )
    # No live preview behind a slideshow nobody watches.
    assert 'body.dataset.state === "SCREENSAVER"' in js
