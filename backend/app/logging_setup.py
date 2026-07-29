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

# Access-log paths too chatty to log per request. The live-preview poller hits
# /preview/frame at the camera fps (~15/s), which would otherwise flood the log
# and bury real entries.
_QUIET_ACCESS_PATHS = ("/preview/frame",)


class _SuppressAccessPaths(logging.Filter):
    """Drop uvicorn.access records whose request path is in ``paths``.

    uvicorn logs access lines with ``record.args = (client, method, path, http, status)``;
    the path carries the query string, so compare on the part before ``?``.
    """

    def __init__(self, paths: tuple[str, ...]) -> None:
        super().__init__()
        self._paths = paths

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3:
            path = str(args[2]).split("?", 1)[0]
            if path in self._paths:
                return False
        return True


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

    # Silence the per-frame preview poller in uvicorn's access log.
    access = logging.getLogger("uvicorn.access")
    if not any(isinstance(f, _SuppressAccessPaths) for f in access.filters):
        access.addFilter(_SuppressAccessPaths(_QUIET_ACCESS_PATHS))
