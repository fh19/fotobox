"""Captive portal: joining the guest WiFi opens the gallery by itself.

Phones test their new connection against a fixed URL and expect a very specific
answer — Android a bare 204, Apple the word "Success", Windows a known text file.
Anything else means "there is a portal here", and the system pops up its little
sign-in browser. The box answers those probes with a redirect to the gallery, so
guests land on their photos without anyone reading out an IP address.

This only works together with the DNS hijack in :func:`app.system.captive_dns_write`
(every hostname resolves to the box) and with the backend listening on port 80 —
the probes are plain HTTP on the default port, nowhere else.

Only clients on the access point's own subnet are redirected. On the house
network a mistyped URL must stay a normal 404.
"""

from __future__ import annotations

import ipaddress
import logging

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, Response

log = logging.getLogger("fotobox.captive")

router = APIRouter()

# What the phones ask for. The exact paths matter; the query string does not.
PROBE_PATHS = (
    "/generate_204",  # Android
    "/gen_204",  # Android (older)
    "/hotspot-detect.html",  # iOS / macOS
    "/library/test/success.html",  # iOS (older)
    "/connecttest.txt",  # Windows
    "/ncsi.txt",  # Windows (older)
    "/success.txt",  # Firefox
    "/canonical.html",  # Ubuntu / GNOME
)


def _target(request: Request) -> str:
    """Where a captured client should end up."""
    return "/gallery" if request.app.state.config.network.gallery_enabled else "/"


def is_captured(request: Request) -> bool:
    """True for a client on the access point subnet while the portal is on."""
    access_point = request.app.state.config.network.access_point
    if not access_point.captive_portal:
        return False
    client = request.client.host if request.client else None
    if not client:
        return False
    try:
        subnet = ipaddress.ip_network(f"{access_point.address}/24", strict=False)
        return ipaddress.ip_address(client) in subnet
    except ValueError:
        return False


def redirect_to_gallery(request: Request) -> Response:
    """A 302 — what every captive-portal detector reacts to."""
    return RedirectResponse(_target(request), status_code=302)


async def _probe(request: Request) -> Response:
    if is_captured(request):
        return redirect_to_gallery(request)
    # Not a guest on the AP: answer as "internet is fine" so nothing else breaks.
    return Response(status_code=204)


for _path in PROBE_PATHS:
    router.add_api_route(_path, _probe, methods=["GET"], include_in_schema=False)
