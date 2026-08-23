"""Frame mode (photo fitted into an overlay window) and background upload admin."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.backgrounds import Background
from app.clock import RealClock
from app.main import create_app
from app.pipeline import run_pipeline
from app.pipeline.compose import detect_window
from app.pipeline.runner import PipelineOutputs
from tests.conftest import make_config

PIN = {"X-Fotobox-Pin": "2606"}


def _overlay_with_window(w, h, window):
    """Opaque black overlay with a transparent rectangular window (x, y, ww, wh)."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
    x, y, ww, wh = window
    hole = Image.new("RGBA", (ww, wh), (0, 0, 0, 0))
    img.paste(hole, (x, y))
    return img


# --- detect_window ----------------------------------------------------------


def test_detect_window_finds_transparent_box():
    overlay = _overlay_with_window(1000, 1500, (100, 200, 700, 1100))
    assert detect_window(overlay) == (100, 200, 700, 1100)


def test_detect_window_none_when_opaque():
    assert detect_window(Image.new("RGBA", (10, 10), (0, 0, 0, 255))) is None


# --- frame pipeline ---------------------------------------------------------


def _run_frame(tmp_path, fit):
    # Window coordinates below are print pixels — compose at print scale.
    config = make_config(tmp_path, pipeline__processed_scale=1)
    cw, ch = config.printing.canvas_width, config.printing.canvas_height
    window = (200, 300, cw - 400, ch - 600)

    overlay_path = tmp_path / "overlay.png"
    _overlay_with_window(cw, ch, window).save(overlay_path)

    original_path = tmp_path / "orig.jpg"
    Image.new("RGB", (600, 400), (0, 0, 255)).save(original_path)  # blue 3:2 photo

    background = Background(
        id="rahmen",
        name="Rahmen",
        mode="frame",
        enabled=True,
        sort_order=1,
        overlay_path=overlay_path,
        fit=fit,
        background_color="#ff0000",  # red so letterbox bars are detectable
    )
    outputs = PipelineOutputs(
        processed=tmp_path / "p.jpg", print=tmp_path / "pr.jpg", thumb=tmp_path / "t.jpg"
    )
    run_pipeline(config, background, 1, original_path, outputs)
    return Image.open(outputs.processed).convert("RGB"), (cw, ch), window


def test_frame_contain_keeps_photo_and_shows_bars(tmp_path):
    result, (cw, ch), (x, y, ww, wh) = _run_frame(tmp_path, fit="contain")
    assert result.size == (cw, ch)
    # Centre of the window shows the photo (blue).
    assert result.getpixel((cw // 2, ch // 2))[2] > 200
    # Far outside the window is the opaque frame (black).
    assert result.getpixel((5, 5)) == (0, 0, 0)
    # A 3:2 photo in a portrait window is letterboxed → red bar just below the top edge.
    assert result.getpixel((cw // 2, y + 10))[0] > 200


def test_frame_cover_fills_window(tmp_path):
    result, (cw, ch), (x, y, ww, wh) = _run_frame(tmp_path, fit="cover")
    # No bars: near the window's top edge is still the photo (blue), not red.
    assert result.getpixel((cw // 2, y + 10))[2] > 200


# --- background upload (admin) ----------------------------------------------


def _png_bytes(alpha=True):
    mode, color = ("RGBA", (0, 0, 0, 255)) if alpha else ("RGB", (10, 20, 30))
    buf = io.BytesIO()
    Image.new(mode, (1248, 1872), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpg_bytes():
    buf = io.BytesIO()
    Image.new("RGB", (1248, 1872), (10, 20, 30)).save(buf, format="JPEG")
    return buf.getvalue()


def _client(tmp_path):
    return TestClient(create_app(make_config(tmp_path), RealClock()))


def test_backgrounds_require_pin(tmp_path):
    client = _client(tmp_path)
    assert client.get("/api/admin/backgrounds").status_code == 401


def test_upload_list_and_delete_frame(tmp_path):
    client = _client(tmp_path)
    res = client.post(
        "/api/admin/backgrounds",
        data={"name": "Mein Rahmen", "mode": "frame"},
        files={"file": ("frame.png", _png_bytes(), "image/png")},
        headers=PIN,
    )
    assert res.status_code == 200, res.text
    assert res.json()["id"] == "mein-rahmen"

    listing = client.get("/api/admin/backgrounds", headers=PIN).json()["backgrounds"]
    assert any(b["id"] == "mein-rahmen" and b["mode"] == "frame" for b in listing)

    folder = make_config(tmp_path).backgrounds_dir / "mein-rahmen"
    assert (folder / "config.json").exists()
    assert (folder / "overlay.png").exists()

    assert client.delete("/api/admin/backgrounds/mein-rahmen", headers=PIN).status_code == 200
    assert client.get("/api/admin/backgrounds", headers=PIN).json()["backgrounds"] == []


def test_upload_frame_without_alpha_is_rejected(tmp_path):
    client = _client(tmp_path)
    res = client.post(
        "/api/admin/backgrounds",
        data={"name": "Kein Alpha", "mode": "frame"},
        files={"file": ("x.jpg", _jpg_bytes(), "image/jpeg")},
        headers=PIN,
    )
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "no_alpha"


def test_delete_none_is_404(tmp_path):
    client = _client(tmp_path)
    assert client.delete("/api/admin/backgrounds/none", headers=PIN).status_code == 404


# --- the frame is prepared once, not per photo ------------------------------
#
# Measured on the box: loading and LANCZOS-scaling a 3780x2504 frame PNG cost
# 1.2 s, and frame mode did it twice per photo — 2.4 s of a 3.7 s pipeline,
# identical work for every guest.


def test_the_scaled_frame_is_kept_on_disk(tmp_path):
    from app.pipeline.compose import _scaled_path, overlay_for, window_for

    source = tmp_path / "overlay.png"
    _overlay_with_window(800, 600, (100, 100, 400, 300)).save(source)
    size = (400, 300)
    scaled = _scaled_path(source, size)
    assert not scaled.exists()

    prepared = overlay_for(source, size)
    assert prepared.size == size
    assert scaled.exists()  # survives a restart, so the first photo is fast too

    # A fresh process (empty memory cache) reads the file instead of rescaling.
    from app.pipeline import compose

    compose._prepared.cache_clear()
    compose._window.cache_clear()
    again = overlay_for(source, size)
    assert again.size == size
    assert window_for(source, size) is not None


def test_a_replaced_frame_is_not_served_from_the_old_cache(tmp_path):
    from app.pipeline import compose
    from app.pipeline.compose import _scaled_path, overlay_for

    source = tmp_path / "overlay.png"
    _overlay_with_window(800, 600, (100, 100, 400, 300)).save(source)
    size = (400, 300)
    overlay_for(source, size)
    assert _scaled_path(source, size).exists()

    # Admin uploads a new frame with a different window.
    compose._prepared.cache_clear()
    compose._window.cache_clear()
    _overlay_with_window(800, 600, (0, 0, 200, 150)).save(source)
    import os

    later = _scaled_path(source, size).stat().st_mtime_ns + 10**9
    os.utime(source, ns=(later, later))

    x, y, w, h = compose.window_for(source, size)
    assert (w, h) == (100, 75)  # the new window, scaled to the canvas


# --- processed_scale: auto ---------------------------------------------------
#
# "der Download der Originalbilder ist 2,1 GB gross, der mit Rahmen nur ~500 MB
# ... die Originalbilder 1:1 übernehmen, den Rahmen hochskalieren."


def _run_auto(tmp_path, original_size, *, scale="auto", mode="frame"):
    config = make_config(tmp_path, pipeline__processed_scale=scale)
    cw, ch = config.printing.canvas_width, config.printing.canvas_height
    window = (200, 300, cw - 400, ch - 600)
    overlay_path = tmp_path / "overlay.png"
    _overlay_with_window(cw, ch, window).save(overlay_path)

    original_path = tmp_path / "orig.jpg"
    Image.new("RGB", original_size, (0, 0, 255)).save(original_path)

    background = Background(
        id="rahmen",
        name="Rahmen",
        mode=mode,
        enabled=True,
        sort_order=1,
        overlay_path=overlay_path if mode == "frame" else None,
        fit="cover",
        background_color="#ff0000",
    )
    outputs = PipelineOutputs(
        processed=tmp_path / "p.jpg", print=tmp_path / "pr.jpg", thumb=tmp_path / "t.jpg"
    )
    run_pipeline(config, background, 1, original_path, outputs)
    return (
        Image.open(outputs.processed),
        Image.open(outputs.print),
        (cw, ch),
        window,
    )


def test_auto_grows_the_canvas_until_the_window_holds_the_original(tmp_path):
    processed, _print, (cw, ch), window = _run_auto(tmp_path, (4496, 3000))
    _, _, window_w, window_h = window
    grown = processed.width / cw

    # "cover" scales the photo by the larger of the two ratios and crops the
    # rest; at the right canvas that factor is 1 — every pixel kept, none added.
    cover = max(window_w * grown / 4496, window_h * grown / 3000)
    assert 0.99 <= cover <= 1.01
    assert processed.width > cw * 2  # clearly beyond the old fixed factor of 2


def test_auto_never_falls_below_print_resolution(tmp_path):
    """The fallback webcam delivers 1280x720 — that must not shrink the master."""
    processed, printed, (cw, ch), _ = _run_auto(tmp_path, (1280, 720))
    assert (processed.width, processed.height) == (cw, ch)
    assert (printed.width, printed.height) == (cw, ch)


def test_the_print_stays_the_postcard_raster_whatever_the_scale(tmp_path):
    """Composing larger is for the download; the printer never sees it."""
    _processed, printed, (cw, ch), _ = _run_auto(tmp_path, (4496, 3000))
    assert (printed.width, printed.height) == (cw, ch)


def test_a_fixed_scale_still_wins_when_configured(tmp_path):
    processed, _print, (cw, ch), _ = _run_auto(tmp_path, (4496, 3000), scale=2)
    assert (processed.width, processed.height) == (cw * 2, ch * 2)


def test_auto_also_works_without_a_frame(tmp_path):
    """Without a window the whole canvas is the target."""
    processed, _print, (cw, ch), _ = _run_auto(tmp_path, (4496, 3000), mode="none")
    cover = max(processed.width / 4496, processed.height / 3000)
    assert 0.99 <= cover <= 1.01


def test_auto_is_capped(tmp_path):
    """A stray huge file must not allocate gigabytes.

    Checked on the scale itself: an image big enough to reach the cap is also
    big enough for Pillow to refuse it as a decompression bomb.
    """
    from app.pipeline.runner import _MAX_AUTO_SCALE, _scale_for

    config = make_config(
        tmp_path,
        pipeline__processed_scale="auto",
        printing__canvas_width=100,  # winzige Leinwand: der Deckel ist erreichbar,
        printing__canvas_height=150,  # ohne ein Bild zu bauen, das Pillow ablehnt
    )
    original_path = tmp_path / "huge.jpg"
    Image.new("RGB", (2000, 3000), (0, 0, 255)).save(original_path)
    background = Background(
        id="ohne", name="Ohne", mode="none", enabled=True, sort_order=1, overlay_path=None
    )
    assert _scale_for(config, background, original_path) == _MAX_AUTO_SCALE


def test_the_derived_files_keep_the_original_date(tmp_path):
    """After re-rendering an old event they would all say "today" otherwise —
    and file managers and ZIP archives sort by exactly this."""
    import os

    config = make_config(tmp_path, pipeline__processed_scale=1)
    original_path = tmp_path / "orig.jpg"
    Image.new("RGB", (600, 400), (0, 0, 255)).save(original_path)
    long_ago = 1_500_000_000  # 2017
    os.utime(original_path, (long_ago, long_ago))

    background = Background(
        id="ohne", name="Ohne", mode="none", enabled=True, sort_order=1, overlay_path=None
    )
    outputs = PipelineOutputs(
        processed=tmp_path / "p.jpg", print=tmp_path / "pr.jpg", thumb=tmp_path / "t.jpg"
    )
    run_pipeline(config, background, 1, original_path, outputs)

    for path in (outputs.processed, outputs.print, outputs.thumb):
        assert int(path.stat().st_mtime) == long_ago, path.name
