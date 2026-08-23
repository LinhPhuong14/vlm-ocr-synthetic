"""Local ink degradation -- the model DocCreator is known for.

Ported from ``GrayscaleCharsDegradationModel.cpp``, which implements Kieu
et al.'s local noise model. Its own description:

    We propose a local noise model for grayscale document images. The main
    principle of our model is to locally degrade the image in the
    neighborhoods of "seed-points", randomly selected. These points define
    the centers of ellipse-shape "noise regions" where the axis of the
    ellipse are measured by local gradient value. A degradation level of
    each pixel in the noise region is set by a Gaussian random
    distribution, based on its distance towards the center of its noise
    region.

Three things make it look like real ink decay rather than added noise, and
all three are kept here:

1. **Seed points are placed relative to the characters**, not uniformly.
   DocCreator splits them three ways -- independent specks on the
   background, "cheval" points straddling a character edge, and points
   inside the ink -- and shifts the proportions with the degradation level
   (``degradateByLevel``: 50/30/20 up to level 4, 30/50/20 to level 7,
   20/30/50 above). Low levels speckle the page; high levels eat the
   glyphs.
2. **The number of regions scales with the amount of ink**:
   ``2 * connected_components * level / 5``. A sparse page gets sparse
   damage.
3. **Each region fades from its centre by a Gaussian**, so regions have
   no hard edges and overlapping ones compound naturally.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

# DocCreator: NUMBER_NOISE_PER_CC
NOISE_REGIONS_PER_COMPONENT = 2

# How much of DocCreator's dose to actually apply. A quarter.
#
# Their constant is two noise regions per connected component, and it was
# tuned on scanned prose, where a component is a letter. It does not survive
# the move to a Vietnamese invoice, because a *dotted leader line* -- the row
# of full stops after "Ma so thue:" -- makes every dot its own component.
# Measured on one page per layout at level 5:
#
#     eatery_ascii          403 components ->   806 seed points, 0% of them dots
#     invoice_brand         544                1088                8%
#     market_compact        476                 952               23%
#     invoice_hotel_stay  2,250               4,500               70%
#     invoice_export      3,132               6,264               49%
#     invoice_vat_form    3,233               6,466               74%
#
# So the same `level` put eight times the speckle on an invoice as on a
# receipt, for a reason that has nothing to do with how much ink is on the
# page. Those are also, in that order, the layouts that lose most recall to
# ageing (0.026 for `invoice_brand` against 0.487-0.521 for the three dotted
# ones) -- see `data/dataset60/proof/README.md`.
#
# The real repair is to stop deriving the dose from a component count at all.
# This is the smaller, reversible step: keep the shape of DocCreator's model
# and thin it. `density` is a parameter of `ink_degradation`, so a chain in
# `rules/augmentation.yaml` can override it per scenario without editing code.
#
# 0.35 is a bit over a third of DocCreator's dose. It was settled by eye
# against a rendered A4 invoice over three passes -- 0.25, then 0.175, then
# back up to here -- so it is a judgement about how a Vietnamese invoice
# should look, not a measurement, and nothing derives it. What each setting
# costs the reference page, at level 5:
#
#     density   changed px   blots on blank paper
#     1.00        190,056     236
#     0.35         84,952      75
#     0.25         64,905      64
#     0.175        45,995      42
#
# Because nothing derives it, nothing else would notice it drifting, which is
# why `tests/test_ink_degradation.py` pins the exact value.
DENSITY = 0.35
# DocCreator: _sigma_gausien, the spread of the grey values drawn per region
GREY_SIGMA = 20.0

# level -> (independent, cheval, inside) percentages, from degradateByLevel_cv
SEED_MIX = (
    (4, (50, 30, 20)),
    (7, (30, 50, 20)),
    (10, (20, 30, 50)),
)


def seed_mix(level: int) -> tuple[int, int, int]:
    """Percentages of independent / straddling / inside-ink seed points."""
    for threshold, mix in SEED_MIX:
        if level <= threshold:
            return mix
    return SEED_MIX[-1][1]


@dataclass
class InkDegradationConfig:
    level: int = 5  # 1..10, as in DocCreator's UI
    min_axis: int = 2
    max_axis: int = 9
    ink_threshold: int = 128
    # Above this grey the pixel is the sheet rather than what it lies on.
    paper_threshold: int = 150


def _ink_mask(grey: np.ndarray, threshold: int) -> np.ndarray:
    return grey < threshold


def _paper_mask(grey: np.ndarray, threshold: int) -> np.ndarray:
    """The sheet itself, separated from whatever it is lying on.

    Order matters and getting it wrong is visible: closing first *dilates*,
    so isolated bright noise on a dark background grows into blobs that
    count as paper, and specks then get drawn in mid-air. Open first to
    remove those, close afterwards to fill the holes the glyphs punch, then
    keep the largest region -- a page is one sheet, not confetti.
    """
    import cv2

    binary = (grey >= threshold).astype(np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))

    count, labels, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return binary.astype(bool)

    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    return labels == largest


def _component_count(ink: np.ndarray) -> int:
    import cv2

    count, _ = cv2.connectedComponents(ink.astype(np.uint8), connectivity=8)
    return max(count - 1, 1)  # label 0 is the background


def _seed_points(
    ink: np.ndarray,
    paper: np.ndarray,
    counts: tuple[int, int, int],
    rng: random.Random,
) -> list[tuple[int, int, str]]:
    """Sample the three kinds of seed point DocCreator distinguishes.

    ``paper`` matters: DocCreator's "background" is the sheet, because its
    input is a scanned page that fills the frame. A generator's output
    often does not -- a receipt sits on a dark surface -- and scattering
    independent specks over that surface produces white dots in mid-air.
    They are confined to the sheet here.
    """
    import cv2

    height, width = ink.shape
    inside = np.argwhere(ink)
    background = np.argwhere(paper & ~ink)
    # A character edge: ink pixels that touch background.
    eroded = cv2.erode(ink.astype(np.uint8), np.ones((3, 3), np.uint8))
    edge = np.argwhere(ink & (eroded == 0))

    points: list[tuple[int, int, str]] = []

    n_independent, n_cheval, n_inside = counts
    if len(background):
        for _ in range(n_independent):
            y, x = background[rng.randrange(len(background))]
            points.append((int(x), int(y), "independent"))

    for source, count, kind in ((edge, n_cheval, "cheval"), (inside, n_inside, "inside")):
        if len(source) == 0:
            continue
        for _ in range(count):
            y, x = source[rng.randrange(len(source))]
            points.append((int(x), int(y), kind))

    return points


def ink_degradation(
    image: np.ndarray,
    level: int = 5,
    density: float | None = None,
    rng: random.Random | None = None,
    config: InkDegradationConfig | None = None,
) -> np.ndarray:
    """Degrade ink locally around seed points.

    ``level`` is 1 (light) to 10 and sets how far each blot moves the pixels
    under it. ``density`` scales how *many* blots there are, over and above
    what ``level`` does; it defaults to `DENSITY`, which is a quarter of
    DocCreator's dose and the reason is written there.
    """
    import cv2

    rng = rng or random.Random(0)
    config = config or InkDegradationConfig(level=level)
    level = max(1, min(int(level), 10))

    colour = image.ndim == 3
    grey = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if colour else image.copy()

    ink = _ink_mask(grey, config.ink_threshold)
    if not ink.any():
        return image

    paper = _paper_mask(grey, config.paper_threshold)

    scale = DENSITY if density is None else float(density)
    if scale < 0:
        raise ValueError(f"density must not be negative, got {density!r}")
    total = int(NOISE_REGIONS_PER_COMPONENT * scale * _component_count(ink) * level / 5)
    total = max(total, 1)

    independent, cheval, inside = seed_mix(level)
    counts = (
        total * independent // 100,
        total * cheval // 100,
        total * inside // 100,
    )

    # Mean grey of paper and of ink: the values a degraded pixel moves between.
    on_paper = paper & ~ink
    mean_background = float(grey[on_paper].mean()) if on_paper.any() else 255.0
    mean_foreground = float(grey[ink].mean())

    out = grey.astype(np.float32)
    height, width = grey.shape

    for x, y, kind in _seed_points(ink, paper, counts, rng):
        axis_a = rng.randint(config.min_axis, config.max_axis)
        axis_b = rng.randint(config.min_axis, config.max_axis)

        x0, x1 = max(0, x - axis_a), min(width, x + axis_a + 1)
        y0, y1 = max(0, y - axis_b), min(height, y + axis_b + 1)
        if x1 <= x0 or y1 <= y0:
            continue

        yy, xx = np.mgrid[y0:y1, x0:x1]
        # Normalised distance from the seed, inside the ellipse.
        radial = ((xx - x) / axis_a) ** 2 + ((yy - y) / axis_b) ** 2
        region = radial <= 1.0
        if not region.any():
            continue

        # Gaussian fade from the centre (DocCreator's per-pixel weighting).
        weight = np.exp(-2.0 * radial) * region

        # Independent and straddling points lighten towards paper (ink lost);
        # points inside the ink darken it (a blot).
        target_mean = mean_background if kind != "inside" else mean_foreground * 0.6
        target = np.clip(rng.gauss(target_mean, GREY_SIGMA), 0, 255)

        patch = out[y0:y1, x0:x1]
        out[y0:y1, x0:x1] = patch * (1.0 - weight) + target * weight

    degraded = np.clip(out, 0, 255).astype(np.uint8)
    if not colour:
        return degraded

    # Carry the change back into colour without shifting the paper's hue.
    ratio = np.divide(
        degraded.astype(np.float32),
        np.maximum(grey.astype(np.float32), 1.0),
    )[:, :, None]
    return np.clip(image.astype(np.float32) * ratio, 0, 255).astype(np.uint8)
