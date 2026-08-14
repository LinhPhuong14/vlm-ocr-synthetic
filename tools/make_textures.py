"""Generate the shared paper textures.

    python tools/make_textures.py

Every renderer composites onto `textures/paper/`, so these four sheets are what
a receipt is printed on whether it was drawn with glyphs or with HTML. They are
generated rather than photographed for two reasons: photographs of paper are
rarely redistributable, so a fresh clone would have nothing to render onto; and
a seed reproduces a sheet exactly, which a scan cannot.

Swap in real scans whenever you have them -- drop them in `textures/paper/`
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


def nhiet_trang(rng: random.Random) -> np.ndarray:
    """Fresh thermal roll: near-white, smooth, faint vertical roller streaks."""
    width, height = SIZE
    field = 0.955 + 0.025 * _fbm((height, width), rng, octaves=3)
    streaks = _noise((height, width), 1, rng)
    streaks = cv2.resize(cv2.resize(streaks, (48, height)), (width, height))
    field *= 1.0 - 0.020 * (streaks - streaks.mean())
    field *= _vignette((height, width), 0.05)
    return _to_bgr(field * 255, (252.0 / 255, 253.0 / 255, 1.0))


def nhiet_nga(rng: random.Random) -> np.ndarray:
    """Thermal paper left in a wallet: yellowed, with blotchy heat marks."""
    width, height = SIZE
    field = 0.90 + 0.06 * _fbm((height, width), rng, octaves=4)
    # Heat marks are small and scattered. A coarse noise here gives long
    # wormy blobs that read as smudges rather than as a browning thermal coat.
    blotch = _noise((height, width), 22, rng)
    field *= 1.0 - 0.055 * np.clip(blotch - 0.72, 0, 1) * 3.6
    field *= _vignette((height, width), 0.13)
    return _to_bgr(field * 255, (196.0 / 255, 224.0 / 255, 244.0 / 255))


def giay_tai_che(rng: random.Random) -> np.ndarray:
    """Recycled stock: visible fibre flecks, warm, uneven."""
    width, height = SIZE
    field = 0.88 + 0.08 * _fbm((height, width), rng, octaves=5)
    flecks = _noise((height, width), 2, rng)
    field -= 0.12 * np.clip(flecks - 0.86, 0, 1) * 7.0   # dark specks of pulp
    field += 0.05 * np.clip(0.12 - flecks, 0, 1) * 7.0   # and light ones
    field *= _vignette((height, width), 0.10)
    return _to_bgr(np.clip(field, 0, 1) * 255, (214.0 / 255, 228.0 / 255, 240.0 / 255))


def giay_a5(rng: random.Random) -> np.ndarray:
    """Office paper: almost flat, just enough mottling not to look synthetic."""
    width, height = SIZE
    field = 0.975 + 0.015 * _fbm((height, width), rng, octaves=3)
    field *= _vignette((height, width), 0.04)
    return _to_bgr(field * 255, (250.0 / 255, 251.0 / 255, 252.0 / 255))


PAPERS = {
    "nhiet_trang": nhiet_trang,
    "nhiet_nga": nhiet_nga,
    "giay_tai_che": giay_tai_che,
    "giay_a5": giay_a5,
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o", "--out", type=Path,
        default=Path(__file__).resolve().parent.parent / "textures" / "paper",
    )
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    for index, (name, make) in enumerate(sorted(PAPERS.items())):
        rng = random.Random(args.seed + index * 101)
        image = make(rng)
        path = args.out / f"{name}.jpg"
        cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 92])
        print(f"[ok] {path}  {image.shape[1]}x{image.shape[0]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
