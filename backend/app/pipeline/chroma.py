"""Chroma-key (green screen) segmentation.

Produces an alpha mask (foreground = subject) and suppresses green spill on the
subject's edges. All thresholds come from the background's resolved chroma
parameters (config defaults merged with the background's ``config.json``).

Green clothing is keyed out too — that is expected and documented as holes, not a
bug (docs/meilensteine.md M3).
"""

from __future__ import annotations

import cv2
import numpy as np

# OpenCV hue is 0..179; the config's hue_center/tolerance are on that scale.


def chroma_alpha(rgb: np.ndarray, params: dict) -> np.ndarray:
    """Return an 8-bit alpha mask (255 = keep, 0 = background) for an RGB array."""
    hsv = cv2.cvtColor(rgb, cv2.COLOR_RGB2HSV)
    hue = hsv[:, :, 0].astype(np.int16)
    sat = hsv[:, :, 1]
    val = hsv[:, :, 2]

    center = float(params["hue_center"])
    tolerance = float(params["hue_tolerance"])
    hue_diff = np.abs(hue - center)
    is_green = (
        (hue_diff <= tolerance) & (sat >= params["saturation_min"]) & (val >= params["value_min"])
    )

    alpha = np.where(is_green, 0, 255).astype(np.uint8)

    feather = int(round(params.get("edge_feather_px", 0)))
    if feather > 0:
        ksize = 2 * feather + 1
        alpha = cv2.GaussianBlur(alpha, (ksize, ksize), 0)
    return alpha


def suppress_spill(rgb: np.ndarray, params: dict) -> np.ndarray:
    """Reduce green spill: where green dominates, pull it down towards red/blue."""
    strength = float(params.get("spill_suppression", 0.0))
    if strength <= 0:
        return rgb
    out = rgb.astype(np.float32)
    red, green, blue = out[:, :, 0], out[:, :, 1], out[:, :, 2]
    max_rb = np.maximum(red, blue)
    spill = green > max_rb
    # New green = max(R,B) + (G - max(R,B)) * (1 - strength)
    green_new = max_rb + (green - max_rb) * (1.0 - strength)
    out[:, :, 1] = np.where(spill, green_new, green)
    return np.clip(out, 0, 255).astype(np.uint8)
