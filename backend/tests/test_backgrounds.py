"""Background registry: scanning, chroma-default merge, broken config, rescan."""

from __future__ import annotations

import json

from PIL import Image

from app.backgrounds import BackgroundRegistry
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
