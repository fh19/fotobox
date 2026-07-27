"""Shared test fixtures.

The state machine and pipeline must be fully testable without real hardware
(CLAUDE.md tests section). Time is controlled with a :class:`FakeClock` so
countdown and timeouts are deterministic — no ``sleep``.
"""

from __future__ import annotations

import copy
import runpy
from pathlib import Path
from typing import Any

import pytest
import yaml

from app import db
from app.backgrounds import Background
from app.broadcaster import Broadcaster
from app.clock import FakeClock
from app.config import Config
from app.engine import Engine
from app.hardware.base import Backends
from app.hardware.mock import MockCamera, MockPreview, MockPrinter

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLE_CONFIG = REPO_ROOT / "config.example.yaml"
BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures"
EXPECTED_DIR = BACKEND_DIR / "tests" / "expected"


@pytest.fixture(scope="session", autouse=True)
def ensure_fixtures() -> None:
    """Generate the M3 fixtures if they are missing (they are gitignored)."""
    if not (FIXTURES_DIR / "greenscreen" / "good_single.jpg").exists():
        runpy.run_path(str(BACKEND_DIR / "tools" / "make_fixtures.py"), run_name="__main__")


def make_background(config: Config, mode: str, *, with_overlay: bool = False) -> Background:
    """A Background pointing at the fixture assets, for pipeline tests."""
    chroma = dict(config.pipeline.chroma_defaults.model_dump())
    needs_bg = mode in ("chroma", "ai")
    needs_overlay = with_overlay or mode == "overlay"
    return Background(
        id="test",
        name="Test",
        mode=mode,
        enabled=True,
        sort_order=0,
        directory=FIXTURES_DIR,
        background_path=(FIXTURES_DIR / "scene_beach.jpg") if needs_bg else None,
        overlay_path=(FIXTURES_DIR / "frame_overlay.png") if needs_overlay else None,
        chroma=chroma,
    )


def _deep_set(data: dict, dotted: str, value: Any) -> None:
    keys = dotted.split(".")
    node = data
    for key in keys[:-1]:
        node = node.setdefault(key, {})
    node[keys[-1]] = value


def make_config(tmp_path: Path, **overrides: Any) -> Config:
    """Build a validated Config from the shipped example, patched for tests."""
    raw = yaml.safe_load(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
    raw = copy.deepcopy(raw)
    raw["hardware"]["mode"] = "mock"
    raw["storage"]["data_dir"] = str(tmp_path)
    raw["logging"]["file"] = str(tmp_path / "logs" / "fotobox.log")
    # Test baseline: fixtures/goldens were generated in portrait. Keep it stable
    # regardless of the production default (now landscape); tests that need
    # landscape pass printing__orientation="landscape".
    raw["printing"]["orientation"] = "portrait"
    # Flash off by default so the capture flow stays single-tick in flow tests;
    # the flash-phase test enables it explicitly.
    raw["ui"]["flash_enabled"] = False
    for dotted, value in overrides.items():
        _deep_set(raw, dotted.replace("__", "."), value)
    return Config.model_validate(raw)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_engine(tmp_path: Path, clock: FakeClock):
    """Factory: build an Engine on a fresh temp DB with mock hardware."""

    def _factory(**overrides: Any) -> Engine:
        config = make_config(tmp_path, **overrides)
        conn = db.connect(config.db_path)
        db.migrate(conn)
        backends = Backends(
            camera=MockCamera(),
            preview=MockPreview(),
            printer=MockPrinter(),
        )
        return Engine(config, clock, conn, backends, Broadcaster())

    return _factory


def state_changes(engine: Engine) -> list[str]:
    """The sequence of target states from the engine's queued messages."""
    return [msg["payload"]["state"] for msg in engine._outbox if msg["type"] == "state_changed"]


def messages_of_type(engine: Engine, message_type: str) -> list[dict]:
    return [msg for msg in engine._outbox if msg["type"] == message_type]
