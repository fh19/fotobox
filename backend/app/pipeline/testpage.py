"""A borderless-postcard test print (admin ``Testdruck``).

Draws an edge frame (to confirm borderless reaches the paper edge), the safe-area
box, corner marks, a colour strip and centred text — enough to verify sizing,
borderless and colour on a real sheet.
"""

from __future__ import annotations

from PIL import Image, ImageDraw

from app.config import Config
from app.pipeline.caption import _load_font
from app.pipeline.geometry import canvas_for


def make_test_page(config: Config) -> Image.Image:
    canvas = canvas_for(config.printing)
    width, height = canvas.width, canvas.height
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    # Outer frame — should reach the paper edge if borderless works.
    draw.rectangle([3, 3, width - 4, height - 4], outline=(20, 20, 20), width=3)
    # Safe area.
    draw.rectangle(
        [canvas.safe_left, canvas.safe_top, canvas.safe_right, canvas.safe_bottom],
        outline=(200, 0, 0),
        width=2,
    )
    # Corner marks.
    m = 60
    for cx, cy in [(0, 0), (width, 0), (0, height), (width, height)]:
        draw.line([cx, cy, cx + (m if cx == 0 else -m), cy], fill=(0, 0, 0), width=4)
        draw.line([cx, cy, cx, cy + (m if cy == 0 else -m)], fill=(0, 0, 0), width=4)

    # Colour strip.
    colours = [(255, 0, 0), (0, 200, 0), (0, 0, 255), (0, 0, 0), (128, 128, 128)]
    strip_h = 80
    seg = width // len(colours)
    y0 = height // 2 + 40
    for i, colour in enumerate(colours):
        draw.rectangle([i * seg, y0, (i + 1) * seg, y0 + strip_h], fill=colour)

    # Centred text.
    font = _load_font(config.printing.caption.font, 64)
    text = "Fotobox · Testdruck"
    bbox = draw.textbbox((0, 0), text, font=font)
    tx = (width - (bbox[2] - bbox[0])) // 2 - bbox[0]
    ty = height // 2 - 100
    draw.text((tx + 2, ty + 2), text, font=font, fill=(180, 180, 180))
    draw.text((tx, ty), text, font=font, fill=(20, 20, 20))
    return image
