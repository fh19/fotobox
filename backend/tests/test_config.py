"""Config loading: valid example, unknown keys, and readable error messages."""

from __future__ import annotations

import pytest

from app.config import ConfigError, load_config
from tests.conftest import EXAMPLE_CONFIG


def test_example_config_is_valid(tmp_path):
    config = load_config(EXAMPLE_CONFIG)
    assert config.countdown.duration_seconds == 5
    assert config.printing.canvas_width == 1248


def _write(tmp_path, text):
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_missing_file_is_readable(tmp_path):
    with pytest.raises(ConfigError) as exc:
        load_config(tmp_path / "nope.yaml")
    assert "nicht gefunden" in str(exc.value)


def test_unknown_key_is_rejected(tmp_path):
    base = EXAMPLE_CONFIG.read_text(encoding="utf-8")
    path = _write(tmp_path, base + "\nunexpected_key: 42\n")
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    assert "unexpected_key" in str(exc.value)


def test_invalid_value_gives_readable_message(tmp_path):
    base = EXAMPLE_CONFIG.read_text(encoding="utf-8")
    broken = base.replace("duration_seconds: 5", "duration_seconds: 0")
    path = _write(tmp_path, broken)
    with pytest.raises(ConfigError) as exc:
        load_config(path)
    message = str(exc.value)
    assert "countdown.duration_seconds" in message
    # Readable, not a raw traceback.
    assert "Traceback" not in message


def test_non_mapping_is_rejected(tmp_path):
    path = _write(tmp_path, "- just\n- a\n- list\n")
    with pytest.raises(ConfigError):
        load_config(path)
