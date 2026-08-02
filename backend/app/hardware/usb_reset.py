"""Reset a camera on the USB bus without touching the rest of the system.

The recovery path for a wedged camera: when libgphoto2 (or a capture thread that
ran into its timeout and was abandoned) leaves the device claimed, no amount of
rebuilding Python objects gets it back — the kernel still has the old claim. A
``USBDEVFS_RESET`` ioctl forces the device to re-enumerate, which invalidates
every stale claim and lets the next ``init()`` succeed.

No root needed: ``/dev/bus/usb/*/*`` is ``crw-rw-r-- root plugdev`` and the
service user is in ``plugdev``. After a reset the kernel usually hands out a new
device number (``usb:002,002`` → ``usb:002,003``), so the caller **must** run
discovery again instead of reusing the old port.
"""

from __future__ import annotations

import fcntl
import logging
import os
import re

log = logging.getLogger("fotobox.camera")

USBDEVFS_RESET = 0x5514  # _IO('U', 20)
_PORT = re.compile(r"^usb:(\d{1,3}),(\d{1,3})$")


def device_path(port: str | None) -> str | None:
    """``"usb:002,002"`` → ``"/dev/bus/usb/002/002"``; None if it is no USB port."""
    match = _PORT.match((port or "").strip())
    if match is None:
        return None
    bus, device = match.groups()
    return f"/dev/bus/usb/{int(bus):03d}/{int(device):03d}"


def reset_usb_device(port: str | None) -> bool:
    """Re-enumerate the camera behind ``port``. True when the ioctl went through."""
    path = device_path(port)
    if path is None:
        log.warning("USB-Reset nicht möglich: %r ist kein USB-Port", port)
        return False
    try:
        fd = os.open(path, os.O_WRONLY)
    except OSError as exc:
        log.warning("USB-Reset: %s ließ sich nicht öffnen: %s", path, exc)
        return False
    try:
        fcntl.ioctl(fd, USBDEVFS_RESET, 0)
    except OSError as exc:
        log.warning("USB-Reset auf %s fehlgeschlagen: %s", path, exc)
        return False
    finally:
        os.close(fd)
    log.info("USB-Reset auf %s ausgeführt", path)
    return True
