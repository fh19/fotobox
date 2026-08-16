"""Captive portal: joining the guest WiFi opens the gallery by itself.

A phone checks its new connection against a fixed URL; anything but the expected
answer makes it show its sign-in browser. The box redirects those probes to the
gallery — but only for clients on the access point's own subnet, so a mistyped
URL on the house network stays an honest 404.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.captive import PROBE_PATHS
from app.clock import RealClock
from app.main import create_app
from tests.conftest import make_config

GUEST = "192.168.4.57"  # a phone on the access point
HOUSE = "192.168.0.20"  # a laptop on the normal network


class _FromAddress:
    """ASGI wrapper that fakes the client address — this TestClient cannot."""

    def __init__(self, app, host: str) -> None:
        self._app = app
        self._host = host

    async def __call__(self, scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            scope = dict(scope, client=(self._host, 51000))
        await self._app(scope, receive, send)


def _client(tmp_path, who, **overrides):
    app = create_app(make_config(tmp_path, **overrides), RealClock())
    return TestClient(_FromAddress(app, who))


def test_probes_send_a_guest_to_the_gallery(tmp_path):
    client = _client(tmp_path, GUEST)
    for path in PROBE_PATHS:
        res = client.get(path, follow_redirects=False)
        assert res.status_code == 302, path
        assert res.headers["location"] == "/gallery", path


def test_probes_stay_harmless_on_the_house_network(tmp_path):
    client = _client(tmp_path, HOUSE)
    for path in PROBE_PATHS:
        assert client.get(path, follow_redirects=False).status_code == 204, path


def test_any_address_a_guest_tries_lands_in_the_gallery(tmp_path):
    """With the DNS hijack every hostname resolves to the box, so unknown paths
    are what most phones actually request."""
    client = _client(tmp_path, GUEST)
    res = client.get("/irgendwas/das/es/nicht/gibt", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/gallery"


def test_unknown_paths_stay_404_on_the_house_network(tmp_path):
    client = _client(tmp_path, HOUSE)
    res = client.get("/irgendwas/das/es/nicht/gibt", follow_redirects=False)
    assert res.status_code == 404
    assert res.json()["error"]["code"] == "not_found"


def test_the_portal_can_be_switched_off(tmp_path):
    client = _client(tmp_path, GUEST, network__access_point__captive_portal=False)
    assert client.get("/generate_204", follow_redirects=False).status_code == 204
    assert client.get("/gibtsnicht", follow_redirects=False).status_code == 404


def test_without_a_gallery_the_guest_gets_the_kiosk_page(tmp_path):
    client = _client(tmp_path, GUEST, network__gallery_enabled=False)
    res = client.get("/generate_204", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/"


def test_the_real_pages_still_work_for_a_guest(tmp_path):
    """The redirect must not swallow the gallery itself or its assets."""
    client = _client(tmp_path, GUEST)
    assert client.get("/gallery").status_code == 200
    assert client.get("/gallery.js").status_code == 200
    assert client.get("/api/status").status_code == 200
