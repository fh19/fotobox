"""Canvas geometry and aspect-preserving resizing.

All pixel sizes come from the config (CLAUDE.md rule 6). Portrait uses
``canvas_width`` × ``canvas_height``; landscape swaps both the canvas and the safe
margins (docs/druck-layout.md).
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image, ImageOps

from app.config import PrintingConfig


def detect_orientation(jpeg: bytes) -> str:
    """Detect portrait/landscape from a photo's true (EXIF-corrected) aspect.

    Used for the one-time auto-calibration: the DSLR sensor is always landscape,
    so a portrait mounting is only visible via the EXIF orientation tag.
    """
    with Image.open(io.BytesIO(jpeg)) as image:
        upright = ImageOps.exif_transpose(image)
        return "portrait" if upright.height > upright.width else "landscape"


@dataclass(frozen=True)
class Canvas:
    width: int
    height: int
    margin_x: int
    margin_y: int
    # >1 while composing above print resolution: the download deserves more than
    # the 1872x1248 the postcard needs. Everything measured in print pixels
    # (caption size, QR size, padding) has to grow with it — see :meth:`px`.
    scale: int = 1

    def px(self, print_pixels: int) -> int:
        """A length given in print pixels, expressed in canvas pixels."""
        return max(1, round(print_pixels * self.scale))

    @property
    def safe_left(self) -> int:
        return self.margin_x

    @property
    def safe_top(self) -> int:
        return self.margin_y

    @property
    def safe_right(self) -> int:
        return self.width - self.margin_x

    @property
    def safe_bottom(self) -> int:
        return self.height - self.margin_y

    @property
    def safe_width(self) -> int:
        return self.width - 2 * self.margin_x

    @property
    def safe_height(self) -> int:
        return self.height - 2 * self.margin_y


def canvas_for(printing: PrintingConfig, scale: int = 1) -> Canvas:
    if printing.orientation == "portrait":
        width, height = printing.canvas_width, printing.canvas_height
        margin_x, margin_y = printing.safe_margin_x, printing.safe_margin_y
    else:  # landscape: canvas and margins are swapped
        width, height = printing.canvas_height, printing.canvas_width
        margin_x, margin_y = printing.safe_margin_y, printing.safe_margin_x
    return Canvas(width * scale, height * scale, margin_x * scale, margin_y * scale, scale)


def cover_resize(image: Image.Image, width: int, height: int) -> Image.Image:
    """Scale to cover the target box, then centre-crop. Aspect ratio is preserved.

    When the input aspect already matches the target (the mounted DSLR case,
    docs/druck-layout.md), this is a plain resize with no crop.
    """
    scale = max(width / image.width, height / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS
    )
    left = (resized.width - width) // 2
    top = (resized.height - height) // 2
    return resized.crop((left, top, left + width, top + height))


def contain_resize(image: Image.Image, width: int, height: int) -> Image.Image:
    """Scale to fit *inside* the target box, preserving aspect (no crop).

    Used by the ``frame`` mode so the whole photo stays visible inside the
    overlay's window; the caller centres the result on the frame background.
    """
    scale = min(width / image.width, height / image.height)
    return image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))), Image.LANCZOS
    )
