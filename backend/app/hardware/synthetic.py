"""Synthetic green-screen imagery for the mock hardware.

Lets the mock camera and preview produce a realistic green-screen portrait so the
full pipeline (chroma cut-out, compositing) can be exercised through the real app
during development, not just in unit tests.
"""

from __future__ import annotations

import io

from PIL import Image, ImageDraw

GREEN = (0, 200, 0)


def greenscreen_jpeg(width: int, height: int, *, seed: int = 0, quality: int = 88) -> bytes:
    """Render a simple person on a green background and return JPEG bytes."""
    image = Image.new("RGB", (width, height), GREEN)
    draw = ImageDraw.Draw(image)

    cx = width // 2 + (seed % 3 - 1) * width // 12
    head_r = int(min(width, height) * 0.12)
    head_cy = int(height * 0.32)
    body_w = int(width * 0.34)
    body_h = int(height * 0.5)
    body_top = head_cy + head_r - head_r // 6
    clothing = [(40, 70, 150), (150, 40, 60), (40, 120, 130)][seed % 3]

    draw.ellipse(
        [cx - head_r - 10, head_cy - head_r - 14, cx + head_r + 10, head_cy + head_r // 3],
        fill=(70, 45, 30),
    )
    draw.ellipse(
        [cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r], fill=(255, 219, 172)
    )
    draw.rounded_rectangle(
        [cx - body_w // 2, body_top, cx + body_w // 2, body_top + body_h],
        radius=int(head_r * 0.4),
        fill=clothing,
    )

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG", quality=quality)
    return buffer.getvalue()
