"""Image pipeline (M3): dimensions, overlay, chroma quality, caption, QR,
error-safety and a regression against reference images."""

from __future__ import annotations

import shutil
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.config import Config
from app.pipeline import PipelineError, PipelineOutputs, run_pipeline
from app.pipeline.geometry import canvas_for
from tests.conftest import EXPECTED_DIR, FIXTURES_DIR, make_background, make_config

GOOD = FIXTURES_DIR / "greenscreen" / "good_single.jpg"


@pytest.fixture
def config(tmp_path) -> Config:
    # These tests are about placement and colour, not resolution: at the print
    # scale the expected pixel positions are the canvas positions. The scaled
    # output has its own tests below.
    return make_config(tmp_path, pipeline__processed_scale=1)


def _outputs(tmp_path) -> PipelineOutputs:
    return PipelineOutputs(
        processed=tmp_path / "processed.jpg",
        print=tmp_path / "print.jpg",
        thumb=tmp_path / "thumb.jpg",
    )


def _run(config, mode, tmp_path, *, original=GOOD, photo_id=1, with_overlay=False):
    background = make_background(config, mode, with_overlay=with_overlay)
    outputs = _outputs(tmp_path)
    ms = run_pipeline(config, background, photo_id, original, outputs)
    return outputs, ms


# --- dimensions & outputs ---------------------------------------------------


@pytest.mark.parametrize("mode", ["none", "overlay", "chroma"])
def test_output_is_canvas_sized(config, mode, tmp_path):
    outputs, ms = _run(config, mode, tmp_path)
    assert ms >= 0
    with Image.open(outputs.processed) as img:
        assert img.size == (1248, 1872)
    with Image.open(outputs.print) as img:
        assert img.size == (1248, 1872)  # the print raster, whatever the scale
    with Image.open(outputs.thumb) as thumb:
        assert thumb.width == config.pipeline.thumbnail_width


def test_landscape_swaps_canvas(tmp_path):
    config = make_config(tmp_path, printing__orientation="landscape", pipeline__processed_scale=1)
    assert canvas_for(config.printing).width == 1872
    outputs, _ = _run(config, "none", tmp_path)
    with Image.open(outputs.processed) as img:
        assert img.size == (1872, 1248)


# --- overlay ----------------------------------------------------------------


def test_overlay_is_aligned(config, tmp_path):
    outputs, _ = _run(config, "overlay", tmp_path)
    result = np.asarray(Image.open(outputs.processed))
    # The frame border is opaque white near the very edge.
    corner = result[5, 5]
    assert corner[0] > 200 and corner[1] > 200 and corner[2] > 200


# --- chroma quality ---------------------------------------------------------


def _green_fringe_fraction(image: Image.Image) -> float:
    arr = np.asarray(image).astype(int)
    r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
    greenish = (g > r + 40) & (g > b + 40)
    return float(greenish.mean())


def test_chroma_has_no_green_seam(config, tmp_path):
    outputs, _ = _run(config, "chroma", tmp_path)
    with Image.open(outputs.processed) as img:
        assert _green_fringe_fraction(img) < 0.005  # < 0.5 % greenish pixels


def test_green_garment_makes_holes(config, tmp_path):
    """The green-garment fixture keeps far less foreground than a normal subject
    — the clothing is keyed out as holes. Documented, not a bug."""
    green = FIXTURES_DIR / "greenscreen" / "green_garment.jpg"
    from app.pipeline import chroma
    from app.pipeline.geometry import cover_resize

    def kept_fraction(path):
        fg = cover_resize(Image.open(path).convert("RGB"), 1248, 1872)
        alpha = chroma.chroma_alpha(np.asarray(fg), make_background(config, "chroma").chroma)
        return (alpha > 127).mean()

    assert kept_fraction(green) < 0.6 * kept_fraction(GOOD)


# --- caption & QR -----------------------------------------------------------


def test_caption_stays_in_safe_area_with_shadow(tmp_path):
    config = make_config(
        tmp_path,
        printing__caption__enabled=True,
        printing__caption__text="Anna & Ben",
        printing__caption__color="#ffffff",
        pipeline__processed_scale=1,  # positions below are print pixels
    )
    outputs, _ = _run(config, "none", tmp_path, original=GOOD)
    arr = np.asarray(Image.open(outputs.processed))
    canvas = canvas_for(config.printing)

    # Bright caption pixels exist somewhere in the lower safe area.
    band = arr[canvas.safe_bottom - 120 : canvas.safe_bottom, canvas.safe_left : canvas.safe_right]
    bright = (band > 240).all(axis=2)
    assert bright.sum() > 50, "keine hellen Caption-Pixel im sicheren Bereich"

    # Shadow: some near-black pixels next to the bright text.
    dark = (band < 40).all(axis=2)
    assert dark.sum() > 20, "kein Schatten unter der Caption"

    # Nothing drawn outside the safe area (bottom margin stays as the photo was).
    margin = arr[canvas.safe_bottom :, :]
    assert not (margin > 250).all(axis=2).any()


def test_qr_is_rendered_in_safe_area(tmp_path):
    config = make_config(
        tmp_path,
        printing__qr__enabled=True,
        printing__qr__position="bottom_right",
        pipeline__processed_scale=1,  # positions below are print pixels
    )
    outputs, _ = _run(config, "none", tmp_path)
    arr = np.asarray(Image.open(outputs.processed))
    canvas = canvas_for(config.printing)
    size = config.printing.qr.size_px
    region = arr[
        canvas.safe_bottom - size - 8 : canvas.safe_bottom - 8,
        canvas.safe_right - size - 8 : canvas.safe_right - 8,
    ]
    # A QR has strong black/white contrast.
    assert region.min() < 40 and region.max() > 220


# --- error safety -----------------------------------------------------------


def test_pipeline_failure_keeps_original(config, tmp_path):
    corrupt = tmp_path / "corrupt.jpg"
    corrupt.write_bytes(b"not a real jpeg")
    outputs = _outputs(tmp_path)
    background = make_background(config, "none")
    with pytest.raises(PipelineError):
        run_pipeline(config, background, 1, corrupt, outputs)
    # Original untouched, no processed written.
    assert corrupt.read_bytes() == b"not a real jpeg"
    assert not outputs.processed.exists()


def test_chroma_without_background_image_fails_safely(config, tmp_path):
    from app.backgrounds import Background

    background = Background(
        id="x",
        name="X",
        mode="chroma",
        enabled=True,
        sort_order=0,
        directory=tmp_path,
        background_path=None,
        overlay_path=None,
        chroma=make_background(config, "chroma").chroma,
    )
    with pytest.raises(PipelineError):
        run_pipeline(config, background, 1, GOOD, _outputs(tmp_path))


# --- AI mode ----------------------------------------------------------------


def test_ai_mode_without_model_fails_safely(config, tmp_path):
    """Without the local ONNX model, AI mode raises PipelineError (no crash, no
    network) so the caller keeps the original and marks the photo failed."""
    assert not Path(config.pipeline.ai.model_path).exists()
    with pytest.raises(PipelineError):
        _run(config, "ai", tmp_path)


def test_ai_mode_runs_when_model_present(config, tmp_path):
    model = Path(config.pipeline.ai.model_path)
    try:
        import rembg  # noqa: F401
    except Exception:
        pytest.skip("rembg/onnxruntime nicht installiert")
    if not model.exists():
        pytest.skip("KI-Modell nicht vorhanden (Deploy-Asset)")
    outputs, _ = _run(config, "ai", tmp_path)
    with Image.open(outputs.processed) as img:
        assert img.size == (1248, 1872)


# --- determinism & regression ----------------------------------------------


def test_pipeline_is_deterministic(config, tmp_path):
    out_a, _ = _run(config, "chroma", tmp_path / "a")
    out_b, _ = _run(config, "chroma", tmp_path / "b")
    assert out_a.processed.read_bytes() == out_b.processed.read_bytes()


def _mae(a: Path, b: Path) -> float:
    with Image.open(a) as ia, Image.open(b) as ib:
        return float(np.abs(np.asarray(ia).astype(int) - np.asarray(ib).astype(int)).mean())


@pytest.mark.parametrize("mode", ["none", "overlay", "chroma"])
def test_regression_matches_reference(config, mode, tmp_path):
    outputs, _ = _run(config, mode, tmp_path)
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    golden = EXPECTED_DIR / f"{mode}.jpg"
    if not golden.exists():
        shutil.copy(outputs.print, golden)  # bootstrap the committed reference
    # The *print* is the guarded output: it must look the same no matter what
    # resolution the download copy is composed at.
    assert _mae(outputs.print, golden) <= 3.0


# --- download resolution and EXIF -------------------------------------------
#
# From the first real event: the framed photos guests took home were 1872x1248
# (the postcard raster) and carried no EXIF at all, while the originals had the
# full shot data. Both were losses nobody chose.


def _exif_original(path, when="2026:08:22 05:14:34"):
    """A JPEG with camera EXIF, like the ones coming off the DSLR."""
    image = Image.new("RGB", (2400, 1600), (90, 140, 60))
    exif = image.getexif()
    exif[271] = "NIKON CORPORATION"  # Make
    exif[272] = "NIKON D7200"  # Model
    exif[306] = when  # DateTime
    exif[274] = 6  # Orientation: rotate — must not survive twice
    image.save(path, format="JPEG", quality=90, exif=exif)
    return path


def test_processed_is_larger_than_the_print(tmp_path):
    config = make_config(tmp_path, pipeline__processed_scale=2)
    outputs, _ = _run(config, "none", tmp_path)

    with Image.open(outputs.processed) as processed:
        assert processed.size == (2496, 3744)  # twice the portrait canvas
    with Image.open(outputs.print) as printable:
        assert printable.size == (1248, 1872)  # the printer sees no change


def test_scale_one_keeps_print_and_download_identical(tmp_path):
    config = make_config(tmp_path, pipeline__processed_scale=1)
    outputs, _ = _run(config, "none", tmp_path)
    with Image.open(outputs.processed) as a, Image.open(outputs.print) as b:
        assert a.size == b.size == (1248, 1872)


def test_the_camera_exif_rides_along(tmp_path):
    config = make_config(tmp_path, pipeline__processed_scale=1)
    original = _exif_original(tmp_path / "dslr.jpg")
    outputs, _ = _run(config, "none", tmp_path, original=original)

    for path in (outputs.processed, outputs.print):
        exif = Image.open(path).getexif()
        assert exif.get(271) == "NIKON CORPORATION", path
        assert exif.get(272) == "NIKON D7200", path
        assert exif.get(306) == "2026:08:22 05:14:34", path
        # The rotation is baked into the pixels; asking for it again would tip
        # every photo on its side in the viewer.
        assert exif.get(274) == 1, path


def test_caption_and_qr_grow_with_the_canvas(tmp_path):
    """Sizes are given in print pixels — on a 2x canvas they must double, or the
    caption would end up half as large relative to the photo."""
    from app.pipeline.geometry import canvas_for

    printing = make_config(tmp_path).printing
    assert canvas_for(printing, 1).px(44) == 44
    assert canvas_for(printing, 2).px(44) == 88
    assert canvas_for(printing, 2).width == 2 * canvas_for(printing, 1).width
