"""Ink from the other side of the sheet showing through.

DocCreator's ``BleedThrough.cpp`` composites a *verso* image into the
*recto* by taking, per pixel, the darker of the two after the verso has
been attenuated -- iterated ``nb_iter`` times, which spreads the ink the
way it spreads in wet paper. The verso is mirrored horizontally, because
that is what the back of a page looks like from the front.

Unlike a plain alpha blend, using the minimum means bleed-through can only
ever darken the page, and dark recto ink is never lightened by pale verso
ink -- the property that makes the result look like paper rather than a
double exposure.
"""

from __future__ import annotations

import numpy as np


def bleed_through(
    recto: np.ndarray,
    verso: np.ndarray | None = None,
    nb_iter: int = 10,
    intensity: float = 0.7,
    blur_sigma: float = 1.2,
) -> np.ndarray:
    """Bleed ``verso`` through ``recto``.

    ``verso=None`` uses a mirrored copy of the page itself, which is what
    you want when you only have one side.
    """
    import cv2

    if verso is None:
        verso = recto[:, ::-1].copy()

    if verso.shape[:2] != recto.shape[:2]:
        verso = cv2.resize(verso, (recto.shape[1], recto.shape[0]))
    if verso.ndim != recto.ndim:
        verso = cv2.cvtColor(verso, cv2.COLOR_GRAY2BGR if recto.ndim == 3 else cv2.COLOR_BGR2GRAY)

    # Ink spreading in the fibres: blur, then fade towards white.
    spread = cv2.GaussianBlur(verso.astype(np.float32), (0, 0), blur_sigma)
    faded = 255.0 - (255.0 - spread) * float(np.clip(intensity, 0.0, 1.0))

    out = recto.astype(np.float32)
    for step in range(max(1, nb_iter)):
        # Each iteration lets a little more through, as DocCreator does.
        weight = (step + 1) / max(1, nb_iter)
        candidate = 255.0 - (255.0 - faded) * weight
        out = np.minimum(out, candidate)

    return np.clip(out, 0, 255).astype(np.uint8)
