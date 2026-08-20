"""Generate the shared paper textures.

    python tools/make_textures.py

Every renderer composites onto `assets/textures/paper/`, so these eight sheets are what
a receipt is printed on whether it was drawn with glyphs or with HTML. They are
generated rather than photographed for two reasons: photographs of paper are
rarely redistributable, so a fresh clone would have nothing to render onto; and
a seed reproduces a sheet exactly, which a scan cannot.

Swap in real scans whenever you have them -- drop them in `assets/textures/paper/`
under the same names and nothing else changes.
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import cv2
import numpy as np

SIZE = (720, 1000)  # width, height -- portrait, like the sheet it stands in for


def _noise(shape: tuple[int, int], cell: int, rng: random.Random) -> np.ndarray:
    height, width = shape
    small = np.asarray(
        [[rng.random() for _ in range(max(width // cell, 2))]
         for _ in range(max(height // cell, 2))],
        dtype=np.float32,
    )
    return cv2.resize(small, (width, height), interpolation=cv2.INTER_CUBIC)


def _fbm(shape: tuple[int, int], rng: random.Random, octaves: int = 4) -> np.ndarray:
    """Fractal noise -- paper has structure at several scales at once."""
    field = np.zeros(shape, dtype=np.float32)
    amplitude, cell = 1.0, 128
    for _ in range(octaves):
        field += amplitude * _noise(shape, max(cell, 2), rng)
        amplitude *= 0.5
        cell //= 2
    return field / field.max()


def _vignette(shape: tuple[int, int], strength: float) -> np.ndarray:
    """Edges of a sheet sit slightly away from the platen and read darker."""
    height, width = shape
    ys = np.linspace(-1, 1, height, dtype=np.float32)[:, None]
    xs = np.linspace(-1, 1, width, dtype=np.float32)[None, :]
    radius = np.sqrt(xs**2 + ys**2) / np.sqrt(2)
    return 1.0 - strength * radius**2


def _to_bgr(field: np.ndarray, tint: tuple[float, float, float]) -> np.ndarray:
    channels = [np.clip(field * value, 0, 255) for value in tint]  # BGR order
    return np.stack(channels, axis=2).astype(np.uint8)


def thermal_white(rng: random.Random) -> np.ndarray:
    """Fresh thermal roll: near-white, smooth, faint vertical roller streaks."""
    width, height = SIZE
    field = 0.955 + 0.025 * _fbm((height, width), rng, octaves=3)
    streaks = _noise((height, width), 1, rng)
    streaks = cv2.resize(cv2.resize(streaks, (48, height)), (width, height))
    field *= 1.0 - 0.020 * (streaks - streaks.mean())
    field *= _vignette((height, width), 0.05)
    return _to_bgr(field * 255, (252.0 / 255, 253.0 / 255, 1.0))


def thermal_cream(rng: random.Random) -> np.ndarray:
    """Thermal paper left in a wallet: yellowed, with blotchy heat marks."""
    width, height = SIZE
    field = 0.90 + 0.06 * _fbm((height, width), rng, octaves=4)
    # Heat marks are small and scattered. A coarse noise here gives long
    # wormy blobs that read as smudges rather than as a browning thermal coat.
    blotch = _noise((height, width), 22, rng)
    field *= 1.0 - 0.055 * np.clip(blotch - 0.72, 0, 1) * 3.6
    field *= _vignette((height, width), 0.13)
    return _to_bgr(field * 255, (196.0 / 255, 224.0 / 255, 244.0 / 255))


def recycled(rng: random.Random) -> np.ndarray:
    """Recycled stock: visible fibre flecks, warm, uneven."""
    width, height = SIZE
    field = 0.88 + 0.08 * _fbm((height, width), rng, octaves=5)
    flecks = _noise((height, width), 2, rng)
    field -= 0.12 * np.clip(flecks - 0.86, 0, 1) * 7.0   # dark specks of pulp
    field += 0.05 * np.clip(0.12 - flecks, 0, 1) * 7.0   # and light ones
    field *= _vignette((height, width), 0.10)
    return _to_bgr(np.clip(field, 0, 1) * 255, (214.0 / 255, 228.0 / 255, 240.0 / 255))


def office_a5(rng: random.Random) -> np.ndarray:
    """Office paper: almost flat, just enough mottling not to look synthetic."""
    width, height = SIZE
    field = 0.975 + 0.015 * _fbm((height, width), rng, octaves=3)
    field *= _vignette((height, width), 0.04)
    return _to_bgr(field * 255, (250.0 / 255, 251.0 / 255, 252.0 / 255))


PAPERS = {
    "thermal_white": thermal_white,
    "thermal_cream": thermal_cream,
    "recycled": recycled,
    "office_a5": office_a5,
}

# --------------------------------------------------------------- surfaces
#
# Coarse sheets, generated the way DocCreator generates a desk top:
# `data/Mesh/Background/wood00..04.jpg`. Their images are LGPL data, the same
# reason the stain and phantom patterns are not vendored either, so the grain
# is synthesised here instead.
#
# These started life as what a receipt was photographed ON and are now four
# more sheets it can be printed on. `paper_texture` is multiplicative and
# takes an `alpha`, so at 0.3-0.5 a wood or weave grain reads as coarse recycled
# stock rather than as a table -- while `assets/textures/background/` holds real
# photographs, which no generator can match.

SURFACE_SIZE = (1200, 800)


def _wood(rng: random.Random, tint, plank_px: int, contrast: float) -> np.ndarray:
    """Wood grain: irregularly spaced rings along each plank, plus seams.

    Two properties do all the work, and both are easy to miss.

    **Ring spacing is irregular.** A sinusoid gives evenly spaced ribs and the
    result reads as corrugated panel, not timber. The gaps here are a cumulative
    sum of random widths, so no two rings sit the same distance apart -- that
    irregularity is what the eye actually uses to call something wood.

    **A ring is a narrow dark band, not half a wave.** Latewood is a thin hard
    line with a wide pale gap after it, so each ring is drawn as a Gaussian a
    few pixels wide rather than as the dark half of a sine.

    Each plank gets its own ring pattern and its own slight tint, because a
    table top is sawn from several boards and they never match.
    """
    width, height = SURFACE_SIZE
    field = np.ones((height, width), dtype=np.float32)

    # Grain wanders slowly along the plank; sampled once per surface so the
    # rings of one plank stay parallel to each other.
    xs = np.linspace(0, 1, width, dtype=np.float32)
    wander = sum(
        amp * plank_px * np.sin(2 * np.pi * freq * xs + rng.uniform(0, 6.28))
        for freq, amp in ((0.6, 0.10), (1.7, 0.05), (3.9, 0.02))
    ).astype(np.float32)[None, :]

    top = 0
    while top < height:
        depth_px = int(plank_px * rng.uniform(0.8, 1.2))
        bottom = min(top + depth_px, height)
        rows = np.arange(top, bottom, dtype=np.float32)[:, None]
        position = rows - wander                       # ring coordinate

        plank = np.ones((bottom - top, width), dtype=np.float32)
        plank *= rng.uniform(0.92, 1.08)               # board-to-board variation

        ring = top - plank_px * rng.uniform(0, 1)
        while ring < bottom + plank_px:
            ring += plank_px * rng.uniform(0.04, 0.18)  # irregular gap
            sharpness = plank_px * rng.uniform(0.006, 0.02)
            plank *= 1.0 - contrast * rng.uniform(0.5, 1.0) * np.exp(
                -(((position - ring) / sharpness) ** 2)
            )

        field[top:bottom] = plank
        if bottom < height:                            # the seam between boards
            field[max(bottom - 1, 0):bottom + 1, :] *= rng.uniform(0.6, 0.8)
        top = bottom

    fibre = cv2.blur(_noise((height, width), 2, rng), (41, 1))  # along the grain
    field *= 1.0 - 0.10 * contrast * (1.0 - fibre)
    field *= _vignette((height, width), 0.22)
    return _to_bgr(np.clip(field, 0, 1) * 255, tint)


def wood_light(rng: random.Random) -> np.ndarray:
    """Light wooden table -- the DocCreator `wood03` sort of surface."""
    return _wood(rng, (150.0 / 255, 200.0 / 255, 234.0 / 255), plank_px=190, contrast=0.30)


def wood_dark(rng: random.Random) -> np.ndarray:
    """Dark wooden table: a receipt on it is high contrast, and hard for OCR."""
    return _wood(rng, (58.0 / 255, 78.0 / 255, 104.0 / 255), plank_px=150, contrast=0.55)


def stone_top(rng: random.Random) -> np.ndarray:
    """Stone or laminate counter: mottled, cool, low contrast."""
    width, height = SURFACE_SIZE
    field = 0.42 + 0.18 * _fbm((height, width), rng, octaves=5)
    speck = _noise((height, width), 2, rng)
    field += 0.10 * np.clip(speck - 0.82, 0, 1) * 6.0
    field -= 0.08 * np.clip(0.18 - speck, 0, 1) * 6.0
    field *= _vignette((height, width), 0.20)
    return _to_bgr(np.clip(field, 0, 1) * 255, (196.0 / 255, 196.0 / 255, 192.0 / 255))


def table_cloth(rng: random.Random) -> np.ndarray:
    """Table cloth: a woven grid, so the noise has structure at one scale."""
    width, height = SURFACE_SIZE
    xs = np.arange(width, dtype=np.float32)[None, :]
    ys = np.arange(height, dtype=np.float32)[:, None]
    pitch = rng.uniform(5.0, 9.0)
    weave = (np.sin(2 * np.pi * xs / pitch) * np.sin(2 * np.pi * ys / pitch)) * 0.5 + 0.5
    field = 0.36 + 0.10 * weave + 0.10 * _fbm((height, width), rng, octaves=4)
    field *= _vignette((height, width), 0.26)
    return _to_bgr(np.clip(field, 0, 1) * 255, (120.0 / 255, 132.0 / 255, 150.0 / 255))


SURFACES = {
    "wood_light": wood_light,
    "wood_dark": wood_dark,
    "stone_top": stone_top,
    "table_cloth": table_cloth,
}


TEXTURES = Path(__file__).resolve().parent.parent / "assets" / "textures"


def _write(catalogue: dict, out: Path, seed: int, quality: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    for index, (name, make) in enumerate(sorted(catalogue.items())):
        image = make(random.Random(seed + index * 101))
        path = out / f"{name}.jpg"
        cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, quality])
        print(f"[ok] {path}  {image.shape[1]}x{image.shape[0]}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=TEXTURES,
                        help="root; everything is written under it into paper/")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--only", choices=("smooth", "coarse"),
                        help="regenerate just one set")
    args = parser.parse_args()

    # Both sets land in paper/. They are kept as two catalogues with two seed
    # bases rather than merged into one, because `_write` seeds each sheet by
    # its position in the sorted catalogue -- merging them would renumber every
    # entry and silently redraw all eight files.
    if args.only != "coarse":
        _write(PAPERS, args.out / "paper", args.seed, 92)
    if args.only != "smooth":
        # Coarse sheets are big and flat; 88 is plenty and halves the cost.
        _write(SURFACES, args.out / "paper", args.seed + 7000, 88)

    # assets/textures/background/ is NOT generated: it holds SynthDoG's photographs of
    # real scenes, and a synthetic table top is exactly the thing that gives a
    # composited receipt away.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
