"""Pipeline orchestration.

Chain (docs/druck-layout.md):
  original → cut out (chroma | ai) or unchanged (overlay | none)
          → composite over background (chroma | ai)
          → overlay.png → caption → QR
          → processed/ (pipeline.processed_scale x print size) and a thumbnail
          → prints/ (scaled down to the print raster)

The composed image carries the camera's EXIF over. A failure anywhere
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
from app.pipeline.compose import apply_overlay, composite, overlay_for, window_for
from app.pipeline.errors import PipelineError
from app.pipeline.geometry import Canvas, canvas_for, contain_resize, cover_resize
from app.pipeline.qr import draw_qr

_ORIENTATION = 274  # EXIF tag


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
        result, exif = _compose(config, background, photo_id, original_path)
        _write_outputs(config, result, outputs, exif)
    except PipelineError:
        raise
    except Exception as exc:  # any imaging error → failed, original untouched
        raise PipelineError(str(exc)) from exc
    return int((time.monotonic() - start) * 1000)


def _compose(
    config: Config, background: Background, photo_id: int, original_path: Path
) -> tuple[Image.Image, Image.Exif]:
    """Compose the photo and return it with the EXIF to carry over."""
    canvas = canvas_for(config.printing, config.pipeline.processed_scale)
    # Honour the camera's EXIF orientation so a portrait-mounted DSLR comes out
    # upright (docs/druck-layout.md — the sensor is always landscape).
    source = Image.open(original_path)
    exif = source.getexif()
    # The rotation is baked in below, so the tag must not ask for it again.
    exif[_ORIENTATION] = 1
    original = ImageOps.exif_transpose(source).convert("RGB")

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
        # Prepared once and cached — this used to reload and rescale the frame for
        # every single photo, the largest item in the pipeline (see overlay_for).
        result = apply_overlay(
            result, overlay_for(background.overlay_path, (canvas.width, canvas.height))
        )

    if config.printing.caption.enabled:
        draw_caption(result, config.printing.caption, canvas)
    if config.printing.qr.enabled:
        draw_qr(result, config.printing.qr, photo_id, canvas)

    return result, exif


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

    size = (canvas.width, canvas.height)
    window = background.window or window_for(background.overlay_path, size)
    x, y, w, h = window or (0, 0, canvas.width, canvas.height)

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


def _write_outputs(
    config: Config, result: Image.Image, outputs: PipelineOutputs, exif: Image.Exif | None = None
) -> None:
    """Write the three variants. ``result`` may be larger than the print canvas.

    The camera's EXIF (time, model, aperture, ISO) rides along: guests who take
    their photos home should get the shot data, and the composed file used to
    carry none of it.
    """
    quality = config.pipeline.jpeg_quality
    for path in (outputs.processed, outputs.print, outputs.thumb):
        path.parent.mkdir(parents=True, exist_ok=True)
    save_args = {"format": "JPEG", "quality": quality, "subsampling": 0}
    if exif is not None:
        save_args["exif"] = exif

    result.save(outputs.processed, **save_args)
    # The printer only ever needs the postcard raster; composing above it is for
    # the download. Scaling down here keeps the print job exactly as it was.
    print_canvas = canvas_for(config.printing)
    printable = result
    if result.size != (print_canvas.width, print_canvas.height):
        printable = result.resize((print_canvas.width, print_canvas.height), Image.LANCZOS)
    printable.save(outputs.print, **save_args)

    thumb_width = config.pipeline.thumbnail_width
    thumb_height = max(1, round(result.height * thumb_width / result.width))
    thumb = result.resize((thumb_width, thumb_height), Image.LANCZOS)
    thumb.save(outputs.thumb, format="JPEG", quality=85)
