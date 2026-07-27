"""Pipeline orchestration.

Chain (docs/druck-layout.md):
  original → cut out (chroma | ai) or unchanged (overlay | none)
          → composite over background (chroma | ai)
          → overlay.png → caption → QR
          → processed/ (== prints/) and a thumbnail

The output is always exactly the canvas size, JPEG, sRGB. A failure anywhere
raises :class:`PipelineError`; the caller never touches the original
(CLAUDE.md rule 3), so the photo is never lost.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageColor, ImageOps

from app.backgrounds import Background
from app.config import Config
from app.pipeline import ai, chroma
from app.pipeline.caption import draw_caption
from app.pipeline.compose import apply_overlay, composite, detect_window
from app.pipeline.errors import PipelineError
from app.pipeline.geometry import Canvas, canvas_for, contain_resize, cover_resize
from app.pipeline.qr import draw_qr


@dataclass(frozen=True)
class PipelineOutputs:
    processed: Path
    print: Path
    thumb: Path


def run_pipeline(
    config: Config,
    background: Background,
    photo_id: int,
    original_path: Path,
    outputs: PipelineOutputs,
) -> int:
    """Produce the derived variants. Returns elapsed milliseconds.

    Raises :class:`PipelineError` on any failure without modifying the original.
    """
    start = time.monotonic()
    try:
        result = _compose(config, background, photo_id, original_path)
        _write_outputs(config, result, outputs)
    except PipelineError:
        raise
    except Exception as exc:  # any imaging error → failed, original untouched
        raise PipelineError(str(exc)) from exc
    return int((time.monotonic() - start) * 1000)


def _compose(
    config: Config, background: Background, photo_id: int, original_path: Path
) -> Image.Image:
    canvas = canvas_for(config.printing)
    # Honour the camera's EXIF orientation so a portrait-mounted DSLR comes out
    # upright (docs/druck-layout.md — the sensor is always landscape).
    original = ImageOps.exif_transpose(Image.open(original_path)).convert("RGB")

    if background.mode == "frame":
        # The photo is fitted into the overlay's transparent window, not the whole
        # canvas; the overlay (the frame) is then laid on top by the block below.
        result = _place_in_frame(background, original, canvas)
    else:
        foreground = cover_resize(original, canvas.width, canvas.height)
        if background.mode in ("none", "overlay"):
            result = foreground
        elif background.mode in ("chroma", "ai"):
            result = _cut_out_and_composite(
                config, background, foreground, canvas.width, canvas.height
            )
        else:
            raise PipelineError(f"Unbekannter Modus: {background.mode}")

    # Overlay: always in overlay/frame mode; for chroma/ai only if an overlay.png exists.
    if background.overlay_path is not None and background.overlay_path.exists():
        result = apply_overlay(result, Image.open(background.overlay_path))

    if config.printing.caption.enabled:
        draw_caption(result, config.printing.caption, canvas)
    if config.printing.qr.enabled:
        draw_qr(result, config.printing.qr, photo_id, canvas)

    return result


def _cut_out_and_composite(
    config: Config, background: Background, foreground: Image.Image, width: int, height: int
) -> Image.Image:
    if background.background_path is None or not background.background_path.exists():
        raise PipelineError("Hintergrundbild fehlt für Freistell-Modus")

    fg_array = np.asarray(foreground)
    if background.mode == "chroma":
        alpha = chroma.chroma_alpha(fg_array, background.chroma)
        fg_array = chroma.suppress_spill(fg_array, background.chroma)
        foreground = Image.fromarray(fg_array)
    else:  # ai
        alpha = ai.ai_alpha(foreground, config)

    background_image = cover_resize(
        Image.open(background.background_path).convert("RGB"), width, height
    )
    return composite(background_image, foreground, Image.fromarray(alpha, "L"))


def _place_in_frame(background: Background, original: Image.Image, canvas: Canvas) -> Image.Image:
    """Fit the photo into the overlay's window on a coloured canvas (``frame`` mode)."""
    if background.overlay_path is None or not background.overlay_path.exists():
        raise PipelineError("Rahmen-PNG fehlt für Rahmen-Modus")

    overlay = Image.open(background.overlay_path).convert("RGBA")
    if overlay.size != (canvas.width, canvas.height):
        overlay = overlay.resize((canvas.width, canvas.height), Image.LANCZOS)

    window = background.window or detect_window(overlay) or (0, 0, canvas.width, canvas.height)
    x, y, w, h = window

    try:
        fill = ImageColor.getrgb(background.background_color)
    except ValueError:
        fill = (255, 255, 255)
    base = Image.new("RGB", (canvas.width, canvas.height), fill)

    if background.fit == "contain":
        photo = contain_resize(original, w, h)
    else:
        photo = cover_resize(original, w, h)
    # Centre the photo inside the window (matters only for "contain").
    base.paste(photo, (x + (w - photo.width) // 2, y + (h - photo.height) // 2))
    return base


def _write_outputs(config: Config, result: Image.Image, outputs: PipelineOutputs) -> None:
    quality = config.pipeline.jpeg_quality
    for path in (outputs.processed, outputs.print, outputs.thumb):
        path.parent.mkdir(parents=True, exist_ok=True)

    result.save(outputs.processed, format="JPEG", quality=quality, subsampling=0)
    result.save(outputs.print, format="JPEG", quality=quality, subsampling=0)

    thumb_width = config.pipeline.thumbnail_width
    thumb_height = max(1, round(result.height * thumb_width / result.width))
    thumb = result.resize((thumb_width, thumb_height), Image.LANCZOS)
    thumb.save(outputs.thumb, format="JPEG", quality=85)
