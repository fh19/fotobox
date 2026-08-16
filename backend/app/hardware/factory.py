"""Wire discovery + selection into concrete backends.

``hardware.mode: mock`` forces everything to mocks (dev machine). In ``real`` mode
each subsystem follows its own ``backend`` field, so the Pi can run the real DSLR
while preview and printer stay mocked until that hardware is attached.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.config import Config
from app.hardware.base import Backends
from app.hardware.discovery import DetectedCamera, DetectedPreview, Discovery, MockDiscovery
from app.hardware.gphoto2_lock import CAMERA_LOCK
from app.hardware.gphoto2_session import close_session
from app.hardware.mock import MockCamera, MockPreview, MockPrinter
from app.hardware.selection import resolve_camera, resolve_preview
from app.hardware.usb_reset import reset_usb_device

log = logging.getLogger("fotobox.camera")


def create_discovery(config: Config) -> Discovery:
    if config.hardware.mode == "mock":
        return MockDiscovery()
    from app.hardware.real import RealDiscovery

    return RealDiscovery(config)


def _use_mock(config: Config, backend: str) -> bool:
    return config.hardware.mode == "mock" or backend == "mock"


def build_camera(config: Config, selected: DetectedCamera | None):
    if _use_mock(config, config.hardware.camera.backend):
        model = selected.model if selected else "Mock DSLR"
        return MockCamera(model=model, available=True)
    if selected is None:
        return MockCamera(available=False)  # real requested, nothing attached
    from app.hardware.gphoto2_backend import Gphoto2Camera

    return Gphoto2Camera(config, selected)


def build_preview(
    config: Config, selected: DetectedPreview | None, camera: DetectedCamera | None = None
):
    if _use_mock(config, config.hardware.preview.backend):
        return MockPreview(available=True)
    if selected is None:
        return MockPreview(available=False)
    from app.hardware.real import build_real_preview

    try:
        return build_real_preview(config, selected, camera)
    except NotImplementedError:
        # Real preview backend not built yet (picamera2) — degrade to a mock.
        return MockPreview(available=False)


def build_printer(config: Config):
    if _use_mock(config, config.hardware.printer.backend):
        return MockPrinter()
    from app.hardware.cups_printer import CupsPrinter

    return CupsPrinter(config)


class CameraManager:
    """Owns discovery + the current selection, and builds the backends.

    Re-selecting rebuilds the capture/preview backends live (used by the admin
    camera picker). The printer is built once.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self._discovery = create_discovery(config)
        self._printer = build_printer(config)
        self.selected_camera: DetectedCamera | None = None
        self.selected_preview: DetectedPreview | None = None
        self.camera = None
        self.preview = None
        self._primary = None  # the DSLR itself, before the fallback wrapper
        self._retry_at: datetime | None = None
        self._retry_step = 0
        self._failures = 0  # consecutive capture failures, for the automatic USB reset
        self._camera_was_seen = False  # a camera that was here once comes back fast
        self.rebuild()

    def discover(self) -> tuple[list[DetectedCamera], list[DetectedPreview]]:
        return self._discovery.cameras(), self._discovery.previews()

    def rebuild(self) -> None:
        cameras, previews = self.discover()
        # The capture camera is resolved first: a DSLR live preview borrows its
        # open handle, so it needs to know which camera was picked.
        self._build_primary(cameras)
        self._rebuild_preview(previews)
        self._wrap_camera()

    def _rebuild_preview(self, previews: list[DetectedPreview]) -> None:
        self.selected_preview = resolve_preview(
            self.config.hardware.preview.device, self.config.hardware.preview.backend, previews
        )
        old_preview = self.preview
        self.preview = build_preview(self.config, self.selected_preview, self.selected_camera)
        # Free the old preview device (e.g. a V4L2 webcam) so it isn't left busy.
        if old_preview is not None and old_preview is not self.preview:
            close = getattr(old_preview, "close", None)
            if callable(close):
                close()

    def _build_primary(self, cameras: list[DetectedCamera]) -> None:
        self.selected_camera = resolve_camera(self.config.hardware.camera.select, cameras)
        self._primary = build_camera(self.config, self.selected_camera)

    def _wrap_camera(self) -> None:
        self.camera = self._primary
        # Backup: fall back to the preview camera for capture when the DSLR is gone.
        if self.config.hardware.camera.fallback_to_preview:
            from app.hardware.fallback_camera import FallbackCamera

            self.camera = FallbackCamera(self._primary, self.preview)

    def _rebuild_camera(self, cameras: list[DetectedCamera]) -> None:
        """Rebuild the capture camera, leaving the preview device alone.

        Exception: a DSLR live preview shares the camera handle, so it has to be
        rebuilt along with the camera it borrows from.
        """
        before = self.selected_camera.port if self.selected_camera else None
        self._build_primary(cameras)
        after = self.selected_camera.port if self.selected_camera else None
        if before != after and getattr(self.preview, "uses_camera_session", False):
            _, previews = self.discover()
            self._rebuild_preview(previews)
        self._wrap_camera()

    def _backoff(self) -> list[float]:
        """Retry intervals, shortened once this box has had a camera at all.

        Waiting 30 s is fine while nothing has ever been attached; after a battery
        change it is half a minute of the box quietly shooting with the webcam.
        """
        backoff = self.config.hardware.camera.reconnect_backoff_seconds
        if not self._camera_was_seen:
            return backoff
        cap = self.config.hardware.camera.reconnect_max_seconds
        return [min(seconds, cap) for seconds in backoff] if cap > 0 else backoff

    def rediscover_if_missing(self, now: datetime) -> bool:
        """Look for the DSLR again while it is missing; True when one was found.

        A camera can be slower to boot than the box: the Sony a7 IV takes ~50 s to
        appear on the USB bus in PC-remote mode, long after the service has started
        its discovery. Without this the box would quietly shoot every photo with the
        fallback camera until someone re-selects the DSLR in the admin UI. Retries
        follow ``camera.reconnect_backoff_seconds``, capped at
        ``reconnect_max_seconds`` once a camera has been seen — a battery change
        must not cost half a minute just because the box had been waiting a while.
        Only the capture camera is rebuilt — re-opening the preview device would
        interrupt the live stream every few seconds.
        """
        if self._primary is not None and self._primary.available():
            self._retry_at = None
            self._retry_step = 0
            self._camera_was_seen = True
            return False
        backoff = self._backoff()
        if not backoff:
            return False
        if self._retry_at is None:
            self._retry_at = now + timedelta(seconds=backoff[0])
            return False
        if now < self._retry_at:
            return False
        self._retry_step = min(self._retry_step + 1, len(backoff) - 1)
        self._retry_at = now + timedelta(seconds=backoff[self._retry_step])
        # Drop the handle first: a camera that was switched off leaves a dead one
        # behind, and reusing it would fail with -52 on the first photo.
        close_session()
        self._rebuild_camera(self._discovery.cameras())
        found = self._primary.available()
        if found:
            log.info("Kamera gefunden: %s", self._primary.model())
            self._retry_at = None
            self._retry_step = 0
        return found

    def rescan(self) -> bool:
        """Run discovery again and rebuild the capture camera. True when one is there.

        For a camera that was plugged in (or switched on) after the box booted. The
        preview device is deliberately left open — rebuilding it would tear down the
        live stream for a moment.
        """
        self._rebuild_camera(self._discovery.cameras())
        self._retry_at = None
        self._retry_step = 0
        self._failures = 0
        return self._primary.available()

    def reset(self) -> dict:
        """Recover a wedged camera: USB reset + reopen the preview + rescan.

        The escape hatch for ``[-53] Could not claim the USB device`` — a claim that
        survives inside our own process and that no amount of rebuilding Python
        objects can release. Reported per device so the admin UI can say what
        actually happened.
        """
        port = self.selected_camera.port if self.selected_camera else None
        with CAMERA_LOCK:
            # Let go of our own handle first — resetting a device we still hold open
            # is what leaves the claim behind in the first place.
            close_session()
            camera_reset = reset_usb_device(port) if port else False
            # The device comes back with a new number, so the old port is stale.
            self.selected_camera = None
            preview_reset = self._reopen_preview()
            found = self.rescan()
        return {"camera_reset": camera_reset, "preview_reset": preview_reset, "found": found}

    def _reopen_preview(self) -> bool:
        """Close and rebuild the preview device (a V4L2 webcam can hang too)."""
        old_preview = self.preview
        close = getattr(old_preview, "close", None)
        if callable(close):
            close()
        _, previews = self.discover()
        self.selected_preview = resolve_preview(
            self.config.hardware.preview.device, self.config.hardware.preview.backend, previews
        )
        self.preview = build_preview(self.config, self.selected_preview)
        return self.preview is not old_preview

    def note_capture_failed(self) -> bool:
        """Count a failed shutter release; True when that triggered a USB reset.

        ``camera.usbreset_after_failures`` (0 = never) makes the box heal itself
        during an event: after that many failures in a row the camera is reset
        without anyone opening the admin UI.
        """
        self._failures += 1
        limit = self.config.hardware.camera.usbreset_after_failures
        if limit <= 0 or self._failures < limit:
            return False
        log.warning("%d Auslöse-Fehler in Folge — Kamera wird zurückgesetzt", self._failures)
        self._failures = 0
        self.reset()
        return True

    def note_capture_ok(self) -> None:
        self._failures = 0

    @property
    def backends(self) -> Backends:
        return Backends(camera=self.camera, preview=self.preview, printer=self._printer)

    @property
    def using_fallback(self) -> bool:
        """True when photos would come from the preview camera instead of the DSLR."""
        check = getattr(self.camera, "using_fallback", None)
        return bool(check()) if callable(check) else False

    def select(
        self,
        *,
        camera_select: str | None = None,
        preview_device: str | None = None,
        preview_backend: str | None = None,
    ) -> None:
        if camera_select is not None:
            self.config.hardware.camera.select = camera_select
        if preview_device is not None:
            self.config.hardware.preview.device = preview_device
        if preview_backend is not None:
            self.config.hardware.preview.backend = preview_backend
        self.rebuild()


def create_backends(config: Config) -> Backends:
    """Backends for a fresh manager (compat helper for simple callers)."""
    return CameraManager(config).backends
