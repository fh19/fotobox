"""Logging configuration.

Logs to the rotating file from the config when its directory is writable, and
always to the console. On a dev box where the configured path (``/data/logs``)
is not writable, it degrades to console-only instead of crashing at startup.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import Config


def setup_logging(config: Config) -> None:
    root = logging.getLogger()
    root.setLevel(config.logging.level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    log_path = Path(config.logging.file)
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=config.logging.max_bytes,
            backupCount=config.logging.backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        root.warning("Logdatei %s nicht beschreibbar (%s) — nur Konsole.", log_path, exc)
