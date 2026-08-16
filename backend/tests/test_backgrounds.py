"""Background registry: scanning, chroma-default merge, broken config, rescan."""

from __future__ import annotations

import json

from PIL import Image

from app.backgrounds import BackgroundRegistry
from app.main import create_app
from app.states import State
from tests.conftest import make_config


def _make_background_dir(config, name, data, *, with_image=True):
    directory = config.backgrounds_dir / name
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(json.dumps(data), encoding="utf-8")
    if with_image:
        Image.new("RGB", (60, 90), (10, 20, 30)).save(directory / "background.jpg")
    return directory


def test_none_is_always_present(tmp_path):
    registry = BackgroundRegistry(make_config(tmp_path))
    ids = [bg.id for bg in registry.list()]
    assert ids == ["none"]
    assert registry.get("none").name == "Ohne Hintergrund"


def test_scans_valid_background(tmp_path):
    config = make_config(tmp_path)
    _make_background_dir(config, "strand", {"name": "Strand", "mode": "chroma", "sort_order": 10})
    registry = BackgroundRegistry(config)
    strand = registry.get("strand")
    assert strand is not None
    assert strand.name == "Strand"
    assert strand.mode == "chroma"
    assert strand.background_path is not None


def test_chroma_defaults_are_merged(tmp_path):
    config = make_config(tmp_path)
    _make_background_dir(
        config, "strand", {"name": "Strand", "mode": "chroma", "chroma": {"hue_center": 55}}
    )
    registry = BackgroundRegistry(config)
    chroma = registry.get("strand").chroma
    assert chroma["hue_center"] == 55  # overridden
    assert (
        chroma["saturation_min"] == config.pipeline.chroma_defaults.saturation_min
    )  # from defaults


def test_broken_config_disables_only_that_one(tmp_path):
    config = make_config(tmp_path)
    (config.backgrounds_dir / "kaputt").mkdir(parents=True)
    (config.backgrounds_dir / "kaputt" / "config.json").write_text(
        "{not valid json", encoding="utf-8"
    )
    _make_background_dir(config, "gut", {"name": "Gut", "mode": "overlay"})
    registry = BackgroundRegistry(config)
    ids = [bg.id for bg in registry.list()]
    assert "gut" in ids
    assert "kaputt" not in ids  # broken one skipped, no crash


def test_disabled_background_not_listed(tmp_path):
    config = make_config(tmp_path)
    _make_background_dir(config, "aus", {"name": "Aus", "mode": "chroma", "enabled": False})
    registry = BackgroundRegistry(config)
    assert registry.get("aus") is None


def test_new_background_appears_without_restart(tmp_path):
    config = make_config(tmp_path)
    config.backgrounds_dir.mkdir(parents=True, exist_ok=True)
    registry = BackgroundRegistry(config)
    assert [bg.id for bg in registry.list()] == ["none"]

    _make_background_dir(config, "spaeter", {"name": "Später", "mode": "none"})
    assert "spaeter" in [bg.id for bg in registry.list()]


# --- the frame without asking -----------------------------------------------
#
# The guests should not be asked "mit oder ohne Rahmen" — the box has one frame
# and every photo gets it. Two versions are kept either way: the untouched
# original and the processed one that also goes to the printer.


def _upload_frame(engine, name: str) -> None:
    """A frame background on disk: opaque PNG with a transparent window."""
    directory = engine.config.backgrounds_dir / name.lower()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "config.json").write_text(
        json.dumps({"name": name, "mode": "frame"}), encoding="utf-8"
    )
    overlay = Image.new("RGBA", (600, 900), (0, 0, 0, 255))
    overlay.paste(Image.new("RGBA", (400, 600), (0, 0, 0, 0)), (100, 150))
    overlay.save(directory / "overlay.png")


def _engine_without_selection(tmp_path, clock, **overrides):
    settings = {"ui__background_select_enabled": False, "ui__default_background": "auto"}
    settings.update(overrides)
    config = make_config(tmp_path, **settings)
    return create_app(config, clock).state.engine


def test_auto_picks_the_uploaded_frame(tmp_path, clock):
    engine = _engine_without_selection(tmp_path, clock)
    _upload_frame(engine, "Hochzeitsrahmen")

    engine.start()
    assert engine.sm.state == State.COUNTDOWN
    assert engine.sm.session.background_mode == "frame"
    assert engine.sm.session.background_id is not None


def test_auto_without_any_frame_shoots_plain(tmp_path, clock):
    engine = _engine_without_selection(tmp_path, clock)

    engine.start()
    assert engine.sm.state == State.COUNTDOWN
    assert engine.sm.session.background_id is None
    assert engine.sm.session.background_mode == "none"


def test_a_fixed_id_wins_over_auto(tmp_path, clock):
    engine = _engine_without_selection(tmp_path, clock, ui__default_background="none")
    _upload_frame(engine, "Hochzeitsrahmen")

    engine.start()
    assert engine.sm.session.background_id is None
    assert engine.sm.session.background_mode == "none"


def test_both_versions_are_kept_and_the_print_is_the_framed_one(tmp_path, clock):
    engine = _engine_without_selection(tmp_path, clock)
    _upload_frame(engine, "Hochzeitsrahmen")

    engine.start()
    for _ in range(engine.config.countdown.duration_seconds + 1):
        engine.tick()
        clock.advance(1)
    engine.tick()
    assert engine.sm.state == State.PREVIEW

    photo_id = engine.sm.session.photo_id
    original = engine._variant_path("originals", photo_id)
    processed = engine._variant_path("processed", photo_id)
    printable = engine._variant_path("prints", photo_id)
    assert original.exists() and processed.exists() and printable.exists()
    # The original is untouched; the other two went through the frame.
    assert original.read_bytes() != processed.read_bytes()
    assert printable.stat().st_size > 0
