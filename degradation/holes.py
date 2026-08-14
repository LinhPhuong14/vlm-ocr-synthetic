"""Holes punched, worn or torn through the page.

``HoleDegradation.cpp`` composites a hole image onto the page in one of
three placements -- centre, border, corner -- darkening the rim so the hole
reads as depth rather than a white blob. DocCreator ships photographs of
real holes; this generates the shape instead, so nothing has to be
downloaded, keeping the placement logic and the shaded rim.
"""

from __future__ import annotations

import random

import numpy as np

PLACEMENTS = ("center", "border", "corner")


def holes(
    image: np.ndarray,
    count: int = 2,
    placement: str = "border",
    size_ratio: float = 0.05,
    rng: random.Random | None = None,
    paper_colour: int = 255,
) -> np.ndarray:
    """Punch ``count`` holes; ``size_ratio`` is the radius over the short side."""
    import cv2

    if placement not in PLACEMENTS:
        raise ValueError(f"placement must be one of {PLACEMENTS}")

    rng = rng or random.Random(0)
    height, width = image.shape[:2]
    radius = max(3, int(size_ratio * min(height, width)))

    out = image.astype(np.float32)
    for _ in range(count):
        if placement == "center":
            cx = rng.randrange(width // 4, 3 * width // 4)
            cy = rng.randrange(height // 4, 3 * height // 4)
        elif placement == "border":
            side = rng.choice(("left", "right", "top", "bottom"))
            cx, cy = {
                "left": (rng.randrange(0, radius), rng.randrange(height)),
                "right": (rng.randrange(width - radius, width), rng.randrange(height)),
                "top": (rng.randrange(width), rng.randrange(0, radius)),
                "bottom": (rng.randrange(width), rng.randrange(height - radius, height)),
            }[side]
        else:
            cx = rng.choice((0, width))
            cy = rng.choice((0, height))

        shape = np.zeros((height, width), dtype=np.float32)
        # An irregular blob, not a circle: real holes are torn.
        axes = (int(radius * rng.uniform(0.7, 1.3)), int(radius * rng.uniform(0.7, 1.3)))
        cv2.ellipse(shape, (cx, cy), axes, rng.uniform(0, 180), 0, 360, 1.0, -1)
        shape = cv2.GaussianBlur(shape, (0, 0), max(1.0, radius * 0.12))

        hole = shape > 0.6          # what is missing
        rim = (shape > 0.15) & ~hole  # the shaded edge around it

        mask_hole = hole[:, :, None] if out.ndim == 3 else hole
        mask_rim = rim[:, :, None] if out.ndim == 3 else rim

        out = np.where(mask_hole, float(paper_colour), out)
        out = np.where(mask_rim, out * 0.55, out)

    return np.clip(out, 0, 255).astype(np.uint8)
