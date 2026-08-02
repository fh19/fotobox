"""One lock for every libgphoto2 call in this process.

libgphoto2 talks to the camera over a claimed USB device, and two threads doing
that at once wedge it: the box polled ``available()`` (→ ``gp.Camera.autodetect``)
every 2 s on the event loop thread while a 4-second ``capture()`` ran in its own
thread (``Engine._capture_with_timeout``). The collision left ``/dev/bus/usb/…``
claimed *inside our own process*, so every later ``init()`` failed with
``[-53] Could not claim the USB device`` until the service was restarted — the
photo silently came from the fallback webcam instead.

Every entry point into gphoto2 (discovery, availability, capture) therefore goes
through :data:`CAMERA_LOCK`. It is reentrant so a capture may call helpers that
take it again. Holders must never block forever: capture acquires with the
configured capture timeout, availability probes use ``blocking=False`` and fall
back to their cached answer.
"""

from __future__ import annotations

import threading

CAMERA_LOCK = threading.RLock()
