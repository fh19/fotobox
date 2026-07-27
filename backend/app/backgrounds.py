"""Background registry.

Reads configurable backgrounds from ``<data_dir>/backgrounds/<id>/`` — each with a
``config.json``, a ``background.jpg`` (chroma/ai), and an optional ``overlay.png``.
Missing chroma keys are filled from ``pipeline.chroma_defaults`` (docs/datenmodell.md).

A broken ``config.json`` disables only that one background and logs a warning; it
must never prevent startup. New or changed backgrounds are picked up without a
restart: the directory is re-scanned when its contents change.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.config import Config

log = logging.getLogger("fotobox.backgrounds")

_VALID_MODES = {"chroma", "ai", "overlay", "frame", "none"}


@dataclass(frozen=True)
class Background:
    id: str
    name: str
    mode: str  # chroma | ai | overlay | frame | none
    enabled: bool
    sort_order: int
    directory: Path | None = None
    background_path: Path | None = None
    overlay_path: Path | None = None
    chroma: dict = field(default_factory=dict)
    # frame mode: where the photo goes inside the overlay, and how it fits there.
    # window is (x, y, w, h) in canvas pixels; None → auto-detect from the overlay's
    # transparent area. fit is "cover" (fill, may crop) or "contain" (whole photo).
    window: tuple[int, int, int, int] | None = None
    fit: str = "cover"
    background_color: str = "#ffffff"


# The first tile is always "Ohne Hintergrund" (docs/ui-screens.md).
NONE_BACKGROUND = Background(
    id="none", name="Ohne Hintergrund", mode="none", enabled=True, sort_order=0
)


class BackgroundRegistry:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._cache: list[Background] = [NONE_BACKGROUND]
        self._signature: tuple | None = None

    def list(self) -> list[Background]:
        """All enabled backgrounds, re-scanning if the folder changed."""
        self._refresh()
        return [bg for bg in self._cache if bg.enabled]

    def all(self) -> list[Background]:
        """Every background including disabled ones (admin view)."""
        self._refresh()
        return list(self._cache)

    def get(self, background_id: str) -> Background | None:
        for background in self.list():
            if background.id == background_id:
                return background
        return None

    def resolve(self, background_id: str | None) -> Background:
        """Resolve to a concrete background, falling back to 'none'."""
        return self.get(background_id or "none") or NONE_BACKGROUND

    # --- scanning -----------------------------------------------------------

    def _dir(self) -> Path:
        return self._config.backgrounds_dir

    def _current_signature(self) -> tuple:
        directory = self._dir()
        if not directory.exists():
            return ()
        entries = []
        for sub in sorted(directory.iterdir()):
            config_file = sub / "config.json"
            if sub.is_dir() and config_file.exists():
                entries.append((sub.name, config_file.stat().st_mtime_ns))
        return tuple(entries)

    def _refresh(self) -> None:
        signature = self._current_signature()
        if signature == self._signature:
            return
        self._signature = signature
        self._cache = self._scan()

    def _scan(self) -> list[Background]:
        backgrounds = [NONE_BACKGROUND]
        directory = self._dir()
        if directory.exists():
            for sub in sorted(directory.iterdir()):
                if not sub.is_dir() or not (sub / "config.json").exists():
                    continue
                background = self._load_one(sub)
                if background is not None:
                    backgrounds.append(background)
        backgrounds.sort(key=lambda bg: (bg.sort_order, bg.id))
        return backgrounds

    def _load_one(self, directory: Path) -> Background | None:
        try:
            data = json.loads((directory / "config.json").read_text(encoding="utf-8"))
            mode = data["mode"]
            name = data["name"]
            if mode not in _VALID_MODES:
                raise ValueError(f"ungültiger Modus '{mode}'")
        except Exception as exc:
            log.warning(
                "Hintergrund %s deaktiviert (fehlerhafte config.json: %s)", directory.name, exc
            )
            return None

        overlay_name = data.get("overlay", "overlay.png")
        overlay_path = directory / overlay_name
        background_path = directory / "background.jpg"

        chroma = dict(self._config.pipeline.chroma_defaults.model_dump())
        chroma.update(data.get("chroma", {}))

        window = data.get("window")
        if isinstance(window, list | tuple) and len(window) == 4:
            window = tuple(int(v) for v in window)
        else:
            window = None

        return Background(
            id=directory.name,
            name=name,
            mode=mode,
            enabled=bool(data.get("enabled", True)),
            sort_order=int(data.get("sort_order", 0)),
            directory=directory,
            background_path=background_path if background_path.exists() else None,
            overlay_path=overlay_path if overlay_path.exists() else None,
            chroma=chroma,
            window=window,
            fit="contain" if data.get("fit") == "contain" else "cover",
            background_color=str(data.get("background_color", "#ffffff")),
        )
