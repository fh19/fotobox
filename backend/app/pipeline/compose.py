"""Alpha compositing of the cut-out subject over a background canvas."""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

log = logging.getLogger("fotobox.pipeline")


def composite(background: Image.Image, foreground: Image.Image, alpha: Image.Image) -> Image.Image:
    """Composite ``foreground`` (RGB) over ``background`` (RGB) using ``alpha`` (L).

    All three must be the same size (the canvas size).
    """
    result = background.convert("RGB").copy()
    fg = foreground.convert("RGB").copy()
    fg.putalpha(alpha.convert("L"))
    result.paste(fg, (0, 0), fg)
    return result


def _scaled_path(path: Path, size: tuple[int, int]) -> Path:
    """Where the canvas-sized copy of an overlay is kept (hidden, next to it)."""
    return path.with_name(f".{path.stem}-{size[0]}x{size[1]}.png")


@lru_cache(maxsize=4)
def _prepared(path: str, mtime_ns: int, size: tuple[int, int]) -> Image.Image:
    """Load an overlay once, as RGBA at canvas size. Cached — see :func:`overlay_for`."""
    source = Path(path)
    scaled = _scaled_path(source, size)
    try:
        if scaled.exists() and scaled.stat().st_mtime_ns >= mtime_ns:
            return Image.open(scaled).convert("RGBA")
    except Exception as exc:  # unreadable cache is never fatal
        log.info("Skalierter Rahmen %s unbrauchbar: %s", scaled.name, exc)

    overlay = Image.open(source).convert("RGBA")
    if overlay.size == size:
        return overlay

    log.info("Rahmen %s ist %dx%d, skaliere auf %dx%d", source.name, *overlay.size, *size)
    overlay = overlay.resize(size, Image.LANCZOS)
    # Keep it on disk so a restart does not pay the second again. Best effort:
    # a read-only or full /data must not stop the box from taking photos.
    try:
        overlay.save(scaled, format="PNG")
    except Exception as exc:
        log.info("Skalierter Rahmen nicht speicherbar: %s", exc)
    return overlay


def overlay_for(path: Path, size: tuple[int, int]) -> Image.Image:
    """The overlay ready to paste, prepared once instead of per photo.

    Loading and LANCZOS-scaling a frame PNG cost 1.2 s on the Pi, and the frame
    mode did it *twice* per photo (once to find the window, once to lay it on
    top) — 2.4 s of the 3.7 s pipeline, identical work for every guest. The
    result is keyed by file mtime, so an overlay replaced in the admin is picked
    up without a restart.

    The returned image is shared: callers must not modify it. Pasting *from* it
    is fine, which is all the pipeline does.
    """
    return _prepared(str(path), path.stat().st_mtime_ns, size)


@lru_cache(maxsize=4)
def _window(path: str, mtime_ns: int, size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    return detect_window(_prepared(path, mtime_ns, size))


def window_for(path: Path, size: tuple[int, int]) -> tuple[int, int, int, int] | None:
    """The frame's transparent window — scanned once, not per photo."""
    return _window(str(path), path.stat().st_mtime_ns, size)


def apply_overlay(image: Image.Image, overlay: Image.Image) -> Image.Image:
    """Lay an RGBA overlay over the image, resizing it to the canvas if needed."""
    overlay = overlay.convert("RGBA")
    if overlay.size != image.size:
        overlay = overlay.resize(image.size, Image.LANCZOS)
    result = image.convert("RGB").copy()
    result.paste(overlay, (0, 0), overlay)
    return result


def detect_window(overlay: Image.Image, threshold: int = 16) -> tuple[int, int, int, int] | None:
    """Bounding box (x, y, w, h) of the overlay's transparent area — the frame window.

    A clean frame has one rectangular transparent hole; its bounding box is the
    window the photo is placed into (``frame`` mode). Returns None if the overlay
    is fully opaque.
    """
    alpha = np.asarray(overlay.convert("RGBA").getchannel("A"))
    ys, xs = np.where(alpha < threshold)
    if xs.size == 0:
        return None
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)
