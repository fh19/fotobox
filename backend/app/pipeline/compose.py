"""Alpha compositing of the cut-out subject over a background canvas."""

from __future__ import annotations

import numpy as np
from PIL import Image


def composite(background: Image.Image, foreground: Image.Image, alpha: Image.Image) -> Image.Image:
    """Composite ``foreground`` (RGB) over ``background`` (RGB) using ``alpha`` (L).

    All three must be the same size (the canvas size).
    """
    result = background.convert("RGB").copy()
    fg = foreground.convert("RGB").copy()
    fg.putalpha(alpha.convert("L"))
    result.paste(fg, (0, 0), fg)
    return result


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
