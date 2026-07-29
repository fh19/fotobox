"""The access-log filter that mutes the per-frame preview poller."""

from __future__ import annotations

import logging

from app.logging_setup import _SuppressAccessPaths


def _access_record(path: str) -> logging.LogRecord:
    # Mirrors uvicorn.access: args = (client, method, path, http_version, status).
    return logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname=__file__,
        lineno=0,
        msg='%s - "%s %s HTTP/%s" %d',
        args=("127.0.0.1:1", "GET", path, "1.1", 200),
        exc_info=None,
    )


def test_preview_frame_is_suppressed():
    f = _SuppressAccessPaths(("/preview/frame",))
    assert f.filter(_access_record("/preview/frame?ts=123")) is False
    assert f.filter(_access_record("/preview/frame")) is False


def test_other_paths_pass_through():
    f = _SuppressAccessPaths(("/preview/frame",))
    assert f.filter(_access_record("/api/status")) is True
    assert f.filter(_access_record("/preview/stream")) is True
