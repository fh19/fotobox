"""Storage warning and full-disk blocking (M4)."""

from __future__ import annotations

import pytest

from app.clock import RealClock
from app.main import create_app
from app.state_machine import ActionRejected
from tests.conftest import make_config


def _engine(tmp_path, **overrides):
    return create_app(make_config(tmp_path, **overrides), RealClock()).state.engine


def test_warning_triggers_at_threshold(tmp_path):
    # warn at 0 % used → always warns; block at 100 % → never blocks.
    engine = _engine(
        tmp_path, storage__warn_threshold_percent=0, storage__block_threshold_percent=100
    )
    storage = engine.build_status()["storage"]
    assert storage["warning"] is True
    assert storage["blocked"] is False


def test_no_warning_below_threshold(tmp_path):
    engine = _engine(tmp_path, storage__warn_threshold_percent=100)
    assert engine.build_status()["storage"]["warning"] is False


def test_full_disk_blocks_start(tmp_path):
    engine = _engine(tmp_path, storage__block_threshold_percent=0)  # 0 % → always blocked
    assert engine.build_status()["storage"]["blocked"] is True
    with pytest.raises(ActionRejected) as exc:
        engine.start()
    assert exc.value.code == "storage_full"
