"""Optional QR code, placed inside the safe area.

The QR encodes ``qr.base_url`` + photo id and is rendered ``qr.size_px`` square,
including a 4-module quiet zone (docs/druck-layout.md).
"""

from __future__ import annotations

import qrcode
from PIL import Image

from app.config import QRConfig
from app.pipeline.geometry import Canvas

_PAD = 8


def draw_qr(image: Image.Image, qr_config: QRConfig, photo_id: int, canvas: Canvas) -> None:
    """Render the QR code onto ``image`` in place."""
    data = f"{qr_config.base_url}{photo_id}"
    code = qrcode.QRCode(border=4)  # 4 modules of quiet zone
    code.add_data(data)
    code.make(fit=True)
    tile = code.make_image(fill_color="black", back_color="white").convert("RGB")
    tile = tile.resize((qr_config.size_px, qr_config.size_px), Image.NEAREST)

    size = qr_config.size_px
    if qr_config.position == "bottom_left":
        x = canvas.safe_left + _PAD
        y = canvas.safe_bottom - size - _PAD
    elif qr_config.position == "bottom_center":
        x = canvas.safe_left + (canvas.safe_width - size) // 2
        y = canvas.safe_bottom - size - _PAD
    else:  # bottom_right (default)
        x = canvas.safe_right - size - _PAD
        y = canvas.safe_bottom - size - _PAD

    image.paste(tile, (x, y))
