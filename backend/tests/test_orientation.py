"""EXIF orientation handling and the one-time auto-calibration."""

from __future__ import annotations

import io

from fastapi.testclient import TestClient
from PIL import Image

from app.clock import RealClock
from app.main import create_app
from app.pipeline import detect_orientation
from tests.conftest import make_config

PIN = {"X-Fotobox-Pin": "2606"}


def _jpeg(width: int, height: int, orientation: int | None = None) -> bytes:
    image = Image.new("RGB", (width, height), (90, 90, 90))
    buf = io.BytesIO()
    if orientation is not None:
        exif = image.getexif()
        exif[274] = orientation  # 274 = Orientation tag
        image.save(buf, "JPEG", exif=exif)
    else:
        image.save(buf, "JPEG")
    return buf.getvalue()


def test_detect_orientation_by_aspect():
    assert detect_orientation(_jpeg(1800, 1200)) == "landscape"
    assert detect_orientation(_jpeg(1200, 1800)) == "portrait"


def test_detect_orientation_honours_exif():
    # Landscape pixels, but EXIF says "rotate 90" → upright is portrait.
    assert detect_orientation(_jpeg(1800, 1200, orientation=6)) == "portrait"
    assert detect_orientation(_jpeg(1200, 1800, orientation=8)) == "landscape"


def test_calibration_sets_and_persists_orientation(tmp_path):
    # Start as landscape; the mock capture is 1200×1800 (portrait) → flips to portrait.
    app = create_app(make_config(tmp_path, printing__orientation="landscape"), RealClock())
    client = TestClient(app)
    res = client.post("/api/admin/calibration", headers=PIN)
    assert res.status_code == 200
    assert res.json()["orientation"] == "portrait"
    assert app.state.engine.config.printing.orientation == "portrait"


def test_calibration_requires_pin(tmp_path):
    client = TestClient(create_app(make_config(tmp_path), RealClock()))
    assert client.post("/api/admin/calibration").status_code == 401


def test_calibration_only_in_idle(tmp_path):
    client = TestClient(create_app(make_config(tmp_path), RealClock()))
    client.post("/api/session/start")  # -> BACKGROUND_SELECT
    assert client.post("/api/admin/calibration", headers=PIN).status_code == 409
