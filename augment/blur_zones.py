"""Blur, either over the whole page or only in patches.

``BlurFilter.cpp`` offers whole-page blur and *blur zones*: the page is
blurred only where a pattern says so, with the pattern's edges feathered so
the sharp and blurred parts meet gradually. That is what a scanner with an
uneven focal plane actually produces -- a uniformly blurred page looks
synthetic.
"""

from __future__ import annotations

import random

import numpy as np


def blur(image: np.ndarray, radius: float = 1.0) -> np.ndarray:
    """Whole-page Gaussian blur."""
    import cv2

    if radius <= 0:
        return image
    return cv2.GaussianBlur(image, (0, 0), radius)


def blur_zones(
    image: np.ndarray,
    radius: float = 2.5,
    zones: int = 3,
    coverage: float = 0.25,
    feather: float = 0.12,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Blur ``zones`` elliptical patches covering roughly ``coverage`` of the page.

    ``feather`` is the softness of each patch edge, as a fraction of its
    radius; it is what stops the patches looking like cut-outs.
    """
    import cv2

    rng = rng or random.Random(0)
    height, width = image.shape[:2]

    mask = np.zeros((height, width), dtype=np.float32)
    area_target = coverage * height * width
    per_zone = max(area_target / max(zones, 1), 1.0)
    radius_px = int(round((per_zone / np.pi) ** 0.5))

    for _ in range(zones):
        cx = rng.randrange(width)
        cy = rng.randrange(height)
        axes = (
            max(4, int(radius_px * rng.uniform(0.6, 1.6))),
            max(4, int(radius_px * rng.uniform(0.6, 1.6))),
        )
        cv2.ellipse(mask, (cx, cy), axes, rng.uniform(0, 180), 0, 360, 1.0, -1)

    softness = max(1.0, feather * radius_px)
    mask = cv2.GaussianBlur(mask, (0, 0), softness)
    mask = np.clip(mask, 0.0, 1.0)
    if image.ndim == 3:
        mask = mask[:, :, None]

    blurred = cv2.GaussianBlur(image, (0, 0), radius).astype(np.float32)
    out = image.astype(np.float32) * (1.0 - mask) + blurred * mask
    return np.clip(out, 0, 255).astype(np.uint8)
