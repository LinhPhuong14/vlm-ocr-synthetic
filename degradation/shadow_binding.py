"""Shadow along a page border — the shadow a bound page casts near its spine.

Ported from DocCreator's ``framework/src/Degradations/ShadowBinding.cpp``
(LaBRI, Bordeaux). The falloff is theirs, not an approximation: for each
column ``i`` pixels from the border,

    phi   = theta * (1 - i / distance)
    c     = l0 / (l0 + distance * (1 - cos(phi)))
    coeff = c ** 2

and the column is multiplied by ``coeff``. ``l0 = intensity * 100 + 1`` is
the light's distance in their model, so the shape is an inverse-square
falloff of a light source occluded by the fold — which is why it looks
right and a linear ramp does not.
"""

from __future__ import annotations

import math

import numpy as np

BORDERS = ("left", "right", "top", "bottom")


def shadow_binding(
    image: np.ndarray,
    border: str = "left",
    distance_ratio: float = 0.15,
    intensity: float = 0.5,
    angle: float = 30.0,
) -> np.ndarray:
    """Darken a band along ``border``.

    ``distance_ratio`` is the band width as a fraction of the page
    (of the width for left/right, of the height for top/bottom).
    ``intensity`` in [0, 1]; ``angle`` in degrees is how far the page is
    folded away from the light.
    """
    if border not in BORDERS:
        raise ValueError(f"border must be one of {BORDERS}, got {border!r}")

    height, width = image.shape[:2]
    span = width if border in ("left", "right") else height
    distance = max(1, int(round(distance_ratio * span)))

    theta = math.radians(angle)
    l0 = intensity * 100.0 + 1.0

    # One coefficient per row/column of the band.
    steps = np.arange(distance, dtype=np.float64)
    phi = theta * (1.0 - steps / distance)
    c = l0 / (l0 + distance * (1.0 - np.cos(phi)))
    coeff = (c * c).astype(np.float32)

    # A full-size multiplier map keeps the indexing readable and works for
    # greyscale and colour alike.
    gain = np.ones((height, width), dtype=np.float32)
    if border == "left":
        gain[:, :distance] = coeff[None, :]
    elif border == "right":
        gain[:, width - distance :] = coeff[::-1][None, :]
    elif border == "top":
        gain[:distance, :] = coeff[:, None]
    else:
        gain[height - distance :, :] = coeff[::-1][:, None]

    if image.ndim == 3:
        gain = gain[:, :, None]

    return np.clip(image.astype(np.float32) * gain, 0, 255).astype(np.uint8)
