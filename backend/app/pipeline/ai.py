"""AI background segmentation (rembg / ONNX).

Runs strictly against the local ONNX model at ``pipeline.ai.model_path`` — no
network access (CLAUDE.md rule 7). rembg is imported lazily so the rest of the
pipeline works on machines where it (or the model) is absent; in that case AI
mode raises :class:`PipelineError` and the caller keeps the original safe.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
from PIL import Image

from app.config import Config
from app.pipeline.errors import PipelineError

_sessions: dict[str, object] = {}


def _session(model_path: Path):
    key = str(model_path)
    if key in _sessions:
        return _sessions[key]
    # Point rembg at the local model directory so it never downloads.
    os.environ.setdefault("U2NET_HOME", str(model_path.parent))
    try:
        from rembg import new_session
    except Exception as exc:  # rembg/onnxruntime not installed
        raise PipelineError(f"rembg/onnxruntime nicht verfügbar: {exc}") from exc
    session = new_session(model_path.stem)  # e.g. "u2netp"
    _sessions[key] = session
    return session


def ai_alpha(rgb_image: Image.Image, config: Config) -> np.ndarray:
    """Return an 8-bit alpha mask for the subject using the local ONNX model."""
    model_path = Path(config.pipeline.ai.model_path)
    if not model_path.exists():
        raise PipelineError(f"KI-Modell nicht gefunden: {model_path}")

    try:
        from rembg import remove
    except Exception as exc:
        raise PipelineError(f"rembg/onnxruntime nicht verfügbar: {exc}") from exc

    mask = remove(rgb_image.convert("RGB"), session=_session(model_path), only_mask=True)
    mask = mask.convert("L")
    if mask.size != rgb_image.size:
        mask = mask.resize(rgb_image.size, Image.LANCZOS)
    return np.array(mask)
