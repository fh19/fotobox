"""Wire discovery + selection into concrete backends.

``hardware.mode: mock`` forces everything to mocks (dev machine). In ``real`` mode
each subsystem follows its own ``backend`` field, so the Pi can run the real DSLR
while preview and printer stay mocked until that hardware is attached.
"""

from __future__ import annotations

from app.config import Config
from app.hardware.base import Backends
from app.hardware.discovery import DetectedCamera, DetectedPreview, Discovery, MockDiscovery
from app.hardware.mock import MockCamera, MockPreview, MockPrinter
from app.hardware.selection import resolve_camera, resolve_preview


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


def build_preview(config: Config, selected: DetectedPreview | None):
    if _use_mock(config, config.hardware.preview.backend):
        return MockPreview(available=True)
    if selected is None:
        return MockPreview(available=False)
    from app.hardware.real import build_real_preview

    try:
        return build_real_preview(config, selected)
    except NotImplementedError:
        # Real preview backend not built yet (M5b) — degrade to an unavailable mock.
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
        self.rebuild()

    def discover(self) -> tuple[list[DetectedCamera], list[DetectedPreview]]:
        return self._discovery.cameras(), self._discovery.previews()

    def rebuild(self) -> None:
        cameras, previews = self.discover()
        self.selected_camera = resolve_camera(self.config.hardware.camera.select, cameras)
        self.selected_preview = resolve_preview(
            self.config.hardware.preview.device, self.config.hardware.preview.backend, previews
        )
        old_preview = self.preview
        self.camera = build_camera(self.config, self.selected_camera)
        self.preview = build_preview(self.config, self.selected_preview)
        # Free the old preview device (e.g. a V4L2 webcam) so it isn't left busy.
        if old_preview is not None and old_preview is not self.preview:
            close = getattr(old_preview, "close", None)
            if callable(close):
                close()
        # Backup: fall back to the preview camera for capture when the DSLR is gone.
        if self.config.hardware.camera.fallback_to_preview:
            from app.hardware.fallback_camera import FallbackCamera

            self.camera = FallbackCamera(self.camera, self.preview)

    @property
    def backends(self) -> Backends:
        return Backends(camera=self.camera, preview=self.preview, printer=self._printer)

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
