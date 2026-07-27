"""Generate deterministic test fixtures into backend/tests/fixtures/.

Produces the >= 12 green-screen subjects required by docs/meilensteine.md M3
(good/bad lighting, single/group, dark/white clothing, long hair, glasses, and a
green-garment negative case), plus a scene background and an overlay frame used
by the compositing tests. Fully deterministic — no randomness — so regression
references stay valid when fixtures are regenerated.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"
GREEN = (0, 200, 0)  # chroma-key green (OpenCV H~60, high S)

W, H = 900, 1350  # portrait 2:3, small for fast tests


def _green_canvas(lighting: str = "even") -> Image.Image:
    arr = np.zeros((H, W, 3), dtype=np.float32)
    arr[:, :] = GREEN
    if lighting == "bad":
        # Uneven light: dark towards the bottom (green there falls below value_min).
        grad = np.linspace(1.0, 0.3, H, dtype=np.float32)[:, None]
        arr *= grad[:, :, None]
    elif lighting == "overexposed":
        # Washed out: add white, saturation drops, keying gets harder.
        arr = arr * 0.6 + np.float32(150.0)
    elif lighting == "dim":
        arr *= 0.55
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")


def _draw_person(
    img: Image.Image,
    *,
    cx: int = W // 2,
    scale: float = 1.0,
    skin=(255, 219, 172),
    hair=(70, 45, 30),
    clothing=(40, 70, 150),
    hair_long: bool = False,
    glasses: bool = False,
) -> None:
    draw = ImageDraw.Draw(img)
    head_r = int(120 * scale)
    head_cy = int(H * 0.30)
    body_w = int(300 * scale)
    body_h = int(620 * scale)
    body_top = head_cy + head_r - int(20 * scale)

    if hair_long:
        draw.ellipse(
            [cx - head_r - 30, head_cy - head_r, cx + head_r + 30, body_top + int(260 * scale)],
            fill=hair,
        )
    # hair cap
    draw.ellipse(
        [cx - head_r - 12, head_cy - head_r - 18, cx + head_r + 12, head_cy + int(30 * scale)],
        fill=hair,
    )
    # head
    draw.ellipse([cx - head_r, head_cy - head_r, cx + head_r, head_cy + head_r], fill=skin)
    # body
    draw.rounded_rectangle(
        [cx - body_w // 2, body_top, cx + body_w // 2, body_top + body_h],
        radius=int(48 * scale),
        fill=clothing,
    )
    if glasses:
        eye_y = head_cy - int(10 * scale)
        r = int(38 * scale)
        for ex in (cx - int(48 * scale), cx + int(48 * scale)):
            draw.ellipse(
                [ex - r, eye_y - r, ex + r, eye_y + r], outline=(20, 20, 20), width=int(8 * scale)
            )
        draw.line(
            [cx - int(10 * scale), eye_y, cx + int(10 * scale), eye_y],
            fill=(20, 20, 20),
            width=int(8 * scale),
        )


def _subject(name: str, lighting: str = "even", **person) -> None:
    img = _green_canvas(lighting)
    _draw_person(img, **person)
    img.save(FIXTURES_DIR / "greenscreen" / f"{name}.jpg", quality=92)


def _group(name: str) -> None:
    img = _green_canvas("even")
    _draw_person(img, cx=int(W * 0.34), scale=0.8, clothing=(150, 40, 60))
    _draw_person(img, cx=int(W * 0.66), scale=0.8, clothing=(40, 120, 130))
    img.save(FIXTURES_DIR / "greenscreen" / f"{name}.jpg", quality=92)


def _scene_background() -> None:
    # A simple sky/sand gradient — clearly not green so it reads as "the beach".
    arr = np.zeros((1400, 933, 3), dtype=np.uint8)
    for y in range(arr.shape[0]):
        t = y / arr.shape[0]
        if t < 0.6:
            arr[y, :] = (int(120 + 80 * t), int(170 + 40 * t), 230)  # sky
        else:
            arr[y, :] = (222, int(200 - 30 * t), 150)  # sand
    Image.fromarray(arr, "RGB").save(FIXTURES_DIR / "scene_beach.jpg", quality=92)


def _overlay_frame() -> None:
    # Transparent centre, opaque decorative border — exactly canvas size.
    overlay = Image.new("RGBA", (1248, 1872), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    border = 40
    draw.rectangle([0, 0, 1247, 1871], outline=(255, 255, 255, 230), width=border)
    draw.rectangle(
        [border + 20, border + 20, 1247 - border - 20, 1871 - border - 20],
        outline=(255, 215, 120, 200),
        width=6,
    )
    overlay.save(FIXTURES_DIR / "frame_overlay.png")


def main() -> None:
    (FIXTURES_DIR / "greenscreen").mkdir(parents=True, exist_ok=True)

    _subject("good_single")
    _subject("good_single_2", clothing=(60, 60, 60))
    _subject("bad_lighting", lighting="bad")
    _subject("dark_clothing", clothing=(18, 18, 24))
    _subject("white_dress", clothing=(245, 245, 245), hair_long=True)
    _subject("long_hair", hair_long=True, hair=(30, 20, 15))
    _subject("glasses", glasses=True)
    _subject("green_garment", clothing=GREEN)  # negative case: expect holes
    _subject("edge_person", cx=int(W * 0.16))
    _subject("overexposed", lighting="overexposed")
    _subject("low_light", lighting="dim", clothing=(30, 30, 40))
    _group("group")

    _scene_background()
    _overlay_frame()

    count = len(list((FIXTURES_DIR / "greenscreen").glob("*.jpg")))
    print(f"{count} Greenscreen-Fixtures erzeugt in {FIXTURES_DIR / 'greenscreen'}")
    print(f"Szene + Overlay erzeugt in {FIXTURES_DIR}")


if __name__ == "__main__":
    main()
