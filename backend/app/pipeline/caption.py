"""Frame caption rendering.

The caption stays inside the safe area (docs/druck-layout.md) and — since the
background image behind it is unknown — is drawn with a shadow so white text
stays legible on both light and dark grounds.

Fonts are referenced by path (no fontconfig on a read-only rootfs). If the
configured font is missing, a font bundled with the app is used as a fallback so
development and tests work without the deployed assets.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from app.config import CaptionConfig
from app.pipeline.geometry import Canvas

BUNDLED_FONT = Path(__file__).resolve().parents[2] / "assets" / "fonts" / "DejaVuSerif.ttf"

_PAD = 8  # inner padding from the safe edge, in px


def _load_font(font_path: str, size_px: int) -> ImageFont.FreeTypeFont:
    for candidate in (font_path, str(BUNDLED_FONT)):
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size_px)
    return ImageFont.load_default()


def draw_caption(image: Image.Image, caption: CaptionConfig, canvas: Canvas) -> None:
    """Render the caption onto ``image`` in place."""
    text = caption.text.strip()
    if not text:
        return

    # Sizes are given in print pixels; on a scaled canvas they grow with it.
    font = _load_font(caption.font, canvas.px(caption.size_px))
    draw = ImageDraw.Draw(image)

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    if caption.position == "bottom_right":
        x = canvas.safe_right - text_w - canvas.px(_PAD)
        y = canvas.safe_bottom - text_h - canvas.px(_PAD)
    elif caption.position == "top_center":
        x = canvas.safe_left + (canvas.safe_width - text_w) // 2
        y = canvas.safe_top + canvas.px(_PAD)
    else:  # bottom_center (default)
        x = canvas.safe_left + (canvas.safe_width - text_w) // 2
        y = canvas.safe_bottom - text_h - canvas.px(_PAD)

    # textbbox may report a non-zero origin offset; correct for it.
    x -= bbox[0]
    y -= bbox[1]

    if caption.shadow:
        shadow = (0, 0, 0)
        for dx, dy in ((2, 2), (2, -2), (-2, 2), (-2, -2)):
            draw.text((x + dx, y + dy), text, font=font, fill=shadow)

    draw.text((x, y), text, font=font, fill=caption.color)
