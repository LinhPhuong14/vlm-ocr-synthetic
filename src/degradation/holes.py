"""Tears, rips and punched holes -- DocCreator's `HoleDegradation`.

``framework/src/Degradations/HoleDegradation.{hpp,cpp}``, 566 lines, is the
model for missing paper. Four things in it matter, and each is a decision worth
copying rather than reinventing:

**A hole is a pattern image, not a shape formula.** DocCreator ships binary
masks -- ``data/Image/holePatterns/{centerHoles, borderHoles, cornerHoles}``,
18/18/28 of them -- in which **black marks the paper that is gone**. The ragged
edge of a tear comes from the mask, which is why theirs look torn and a drawn
ellipse never does.

**The hole is filled with a flat colour, and the default is black.**
``fillHoleWithColor`` is one line of substance::

    if (p[x] == PIXEL_BLACK) { d[x + xOrigin] = color; }

and the application sets that colour, in ``Assistant.cpp:153``, to
``QColor Hole_defaultBackgroundColor(0, 0, 0, 255)``. A page photographed over
a dark surface shows black through the tear, so black is what a scan of one
looks like.

**Or with what is behind the sheet.** ``fillHoleWithImage`` takes ``matBelow``
-- the table, the next page -- and shows it through the tear instead.

**A tear has a shaded rim.** ``drawBorder``/``isInMarge`` darken the pixels
within ``shadowBorderWidth`` of the tear's edge by
``intensity^2 / z1^2``. Without it the hole reads as a sticker laid on top.

``getRandomPosition`` has one more idea: ``ratioOutside`` lets the pattern hang
off the edge of the page, because a border tear's missing part is outside the
sheet, not inside it.

Deviations here, both deliberate:

* The patterns are **generated** rather than vendored -- DocCreator's are LGPL
  data. `torn_pattern` builds a centre hole from summed sines in polar
  coordinates, and a border or corner tear from a smoothed random walk. Point
  `patterns` at a directory of real masks and those are used instead.
* DocCreator applies the rim only when filling with an image; a comment in
  their own source flags the colour path as an oversight
  (``//B:TODO: why don't we also pass "shadowBorderWidth & shadowBorderIntensity"
  to fillHoleWithColor ?``). The rim is applied in both here.
"""

from __future__ import annotations

import random
from pathlib import Path

import cv2
import numpy as np

PLACEMENTS = ("center", "border", "corner")
# DocCreator's application default: what shows through a tear is the dark
# surface the page was photographed on.
BLACK = (0, 0, 0)


def _ragged_radius(samples: int, roughness: float, rng: random.Random) -> np.ndarray:
    """A closed, ragged outline as radius against angle.

    Summed sines rather than per-point noise: the outline has to close on
    itself and stay connected, and harmonics of a full turn do that for free.
    Low harmonics give the tear its overall lobed shape, high ones the fibre.
    """
    theta = np.linspace(0, 2 * np.pi, samples, endpoint=False)
    radius = np.ones(samples, dtype=np.float32)
    for harmonic, weight in ((2, 0.30), (3, 0.22), (5, 0.14), (9, 0.09),
                             (17, 0.05), (31, 0.03)):
        radius += (
            weight * roughness
            * np.sin(harmonic * theta + rng.uniform(0, 2 * np.pi)).astype(np.float32)
        )
    return np.clip(radius, 0.25, 2.0)


def _ragged_line(length: int, roughness: float, rng: random.Random) -> np.ndarray:
    """A ragged 1-D profile in [0, 1]: how deep the tear bites, per column."""
    length = max(int(length), 2)

    def walk(smoothing: int) -> np.ndarray:
        """A smoothed random walk, normalised to [-1, 1]."""
        steps = np.asarray([rng.gauss(0.0, 1.0) for _ in range(length)], dtype=np.float32)
        path = np.cumsum(steps)
        kernel = max(int(smoothing), 1)
        path = np.convolve(path, np.ones(kernel, dtype=np.float32) / kernel, mode="same")
        path -= path.mean()
        span = float(np.abs(path).max()) or 1.0
        return path / span

    # A walk, not summed sines: sines are periodic, and a periodic tear line
    # comes out as evenly spaced battlements. Coarse walk for the shape of the
    # tear, fine walk for the fibres along it.
    coarse = walk(max(length // 6, 3))
    fine = walk(max(length // 90, 2))
    profile = 0.55 + roughness * (0.30 * coarse + 0.055 * fine)
    return np.clip(profile, 0.05, 1.0)


def torn_pattern(size: int, rng: random.Random, roughness: float = 1.0,
                 placement: str = "center") -> np.ndarray:
    """One hole mask: 0 where the paper is gone, 255 where it remains.

    Stands in for `data/Image/holePatterns/`, and like those, a border or
    corner pattern is drawn **oriented to the top / top-left** and rotated at
    placement time -- DocCreator's header says the same of theirs.

    The three placements are genuinely different shapes, not one shape moved:

    center
        a closed ragged outline -- a hole punched or worn through the sheet.
    border
        everything from the edge inwards to a ragged line. A torn edge is not
        a hole that happens to sit near the border; it is paper *missing all
        the way to the edge*, and drawing it as a blob near the edge is what
        makes a synthetic tear look pasted on.
    corner
        the same idea across a diagonal: the corner is gone.
    """
    size = max(int(size), 8)
    mask = np.full((size, size), 255, dtype=np.uint8)

    if placement == "border":
        depth = _ragged_line(size, roughness, rng) * size
        rows = np.arange(size, dtype=np.float32)[:, None]
        mask[rows < depth[None, :]] = 0
        return mask

    if placement == "corner":
        # How deep the corner is torn, as a function of where you are *along*
        # the tear. The position along an anti-diagonal cut is (x - y); the
        # depth is (x + y). Indexing the profile by the depth instead makes the
        # boundary a fixed point of one value -- a perfectly straight diagonal.
        ys, xs = np.mgrid[0:size, 0:size]
        cut = _ragged_line(2 * size, roughness, rng) * size * 1.3
        along = np.clip(xs - ys + size, 0, 2 * size - 1)
        mask[(xs + ys) < cut[along]] = 0
        return mask

    samples = 512
    radius = _ragged_radius(samples, roughness, rng) * (size / 2.0) * 0.92
    theta = np.linspace(0, 2 * np.pi, samples, endpoint=False)
    centre = size / 2.0
    points = np.stack(
        [centre + radius * np.cos(theta), centre + radius * np.sin(theta)], axis=1
    ).astype(np.int32)
    cv2.fillPoly(mask, [points], 0)
    return mask


def _load_patterns(directory: Path | None) -> list[Path]:
    if directory is None or not Path(directory).is_dir():
        return []
    return sorted(
        p for p in Path(directory).iterdir()
        if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )


def _orient(pattern: np.ndarray, placement: str, rng: random.Random):
    """Rotate the top / top-left pattern onto a randomly chosen side, and say
    where it goes. DocCreator rotates theirs the same way, for the same reason:
    one pattern set covers four sides."""
    if placement == "center":
        return pattern, None
    if placement == "border":
        side = rng.choice(("top", "bottom", "left", "right"))
        turns = {"top": 0, "left": 1, "bottom": 2, "right": 3}[side]
        return np.rot90(pattern, turns).copy(), side
    corner = rng.choice(("topleft", "bottomleft", "bottomright", "topright"))
    turns = {"topleft": 0, "bottomleft": 1, "bottomright": 2, "topright": 3}[corner]
    return np.rot90(pattern, turns).copy(), corner


def _place(shape: tuple[int, int], size: int, placement: str, side: str | None,
           ratio_outside: float, rng: random.Random) -> tuple[int, int]:
    """Top-left corner at which to stamp the pattern.

    A border or corner pattern sits **flush with its edge** -- that is what
    makes the paper actually missing all the way out. `ratio_outside` is
    DocCreator's: it slides the pattern further off the sheet, so only part of
    its depth bites into the page and the tear comes out shallower.
    """
    height, width = shape
    out = int(size * ratio_outside)
    if placement == "center":
        return (rng.randrange(0, max(width - size, 1)),
                rng.randrange(0, max(height - size, 1)))
    if placement == "border":
        along = lambda span: rng.randrange(-size // 3, max(span - size + size // 3, 1))
        if side == "top":
            return along(width), -out
        if side == "bottom":
            return along(width), height - size + out
        if side == "left":
            return -out, along(height)
        return width - size + out, along(height)
    return {
        "topleft": (-out, -out),
        "topright": (width - size + out, -out),
        "bottomleft": (-out, height - size + out),
        "bottomright": (width - size + out, height - size + out),
    }[side or "topleft"]


def _resolve_fill(fill, paper_colour: int):
    if fill is None or fill == "black":
        return BLACK
    if fill == "paper":
        return (paper_colour,) * 3
    if fill == "white":
        return (255, 255, 255)
    if isinstance(fill, (list, tuple)) and len(fill) == 3:
        return tuple(int(v) for v in fill)
    raise ValueError(
        f"fill must be 'black', 'paper', 'white' or a BGR triple; got {fill!r}"
    )


def holes(
    image: np.ndarray,
    count: int = 2,
    placement: str = "border",
    size_ratio: float = 0.05,
    fill="black",
    ratio_outside: float = 0.0,
    roughness: float = 1.0,
    shadow_width: int = 3,
    shadow_intensity: float = 0.45,
    patterns: str | Path | None = None,
    rng: random.Random | None = None,
    paper_colour: int = 255,
    below: np.ndarray | None = None,
) -> np.ndarray:
    """Tear `count` pieces out of the page.

    `size_ratio` is the tear's size over the page's short side. `fill` is what
    shows through: `'black'` (DocCreator's default -- a dark surface under the
    sheet), `'paper'`, `'white'`, or a BGR triple. `below` supplies an image to
    show through instead, DocCreator's `matBelow`.

    `ratio_outside` slides a border or corner pattern further off the sheet, so
    less of its depth bites in. It defaults to 0, which places the pattern
    flush and gives the full tear; DocCreator defaults it higher because their
    patterns are photographs with their own margins built in.
    """
    if placement not in PLACEMENTS:
        raise ValueError(f"placement must be one of {PLACEMENTS}")

    rng = rng or random.Random(0)
    height, width = image.shape[:2]
    size = max(int(size_ratio * min(height, width)), 8)
    colour = _resolve_fill(fill, paper_colour)

    out = image.copy()
    if out.ndim == 2:
        colour_value = int(np.mean(colour))
    available = _load_patterns(Path(patterns) if patterns else None)

    for _ in range(int(count)):
        if available:
            pattern = cv2.imread(str(rng.choice(available)), cv2.IMREAD_GRAYSCALE)
            pattern = cv2.resize(pattern, (size, size), interpolation=cv2.INTER_NEAREST)
            _, pattern = cv2.threshold(pattern, 127, 255, cv2.THRESH_BINARY)
        else:
            pattern = torn_pattern(size, rng, roughness, placement)

        pattern, side = _orient(pattern, placement, rng)
        x0, y0 = _place((height, width), size, placement, side,
                        ratio_outside if placement != "center" else 0.0, rng)

        # Clip the pattern against the page rather than the page against the
        # pattern -- a border tear is mostly off the sheet by design.
        sx0, sy0 = max(-x0, 0), max(-y0, 0)
        dx0, dy0 = max(x0, 0), max(y0, 0)
        span_x = min(size - sx0, width - dx0)
        span_y = min(size - sy0, height - dy0)
        if span_x <= 0 or span_y <= 0:
            continue

        window = pattern[sy0:sy0 + span_y, sx0:sx0 + span_x]
        gone = window == 0
        if not gone.any():
            continue

        region = out[dy0:dy0 + span_y, dx0:dx0 + span_x]
        if below is not None:
            patch = cv2.resize(below, (width, height))[dy0:dy0 + span_y, dx0:dx0 + span_x]
            region[gone] = patch[gone]
        else:
            region[gone] = colour_value if out.ndim == 2 else colour

        # The shaded rim: pixels of the hole within `shadow_width` of paper.
        # `isInMarge` walks outwards pixel by pixel; an erosion is the same
        # test done for every pixel at once.
        if shadow_width > 0 and shadow_intensity > 0:
            kernel = np.ones((2 * int(shadow_width) + 1,) * 2, np.uint8)
            inner = cv2.erode(gone.astype(np.uint8), kernel, iterations=1).astype(bool)
            rim = gone & ~inner
            if rim.any():
                faded = region.astype(np.float32) * (1.0 - float(shadow_intensity))
                mask = rim[:, :, None] if region.ndim == 3 else rim
                region[...] = np.where(mask, faded, region).astype(np.uint8)

        out[dy0:dy0 + span_y, dx0:dx0 + span_x] = region

    return out


__all__ = ["BLACK", "PLACEMENTS", "holes", "torn_pattern"]
