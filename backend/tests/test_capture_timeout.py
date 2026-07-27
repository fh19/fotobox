"""A hanging DSLR (e.g. focus failure) must time out, not freeze the box."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.clock import RealClock
from app.main import create_app
from tests.conftest import make_config


def test_capture_times_out_instead_of_hanging(tmp_path):
    app = create_app(
        make_config(tmp_path, hardware__camera__capture_timeout_seconds=0.2), RealClock()
    )
    with TestClient(app) as client:
        engine = client.app.state.engine

        class HangingCamera:
            def capture(self):
                time.sleep(5)  # shutter never fires

        class Backends:
            camera = HangingCamera()

        engine.backends = Backends()
        start = time.monotonic()
        with pytest.raises(TimeoutError):
            engine._capture_with_timeout()
        assert time.monotonic() - start < 2.0  # returned promptly, not after 5 s


def test_capture_success_passes_through(tmp_path):
    app = create_app(make_config(tmp_path), RealClock())
    with TestClient(app) as client:
        engine = client.app.state.engine
        result = engine._capture_with_timeout()  # mock camera returns immediately
        assert result is not None and result.jpeg
