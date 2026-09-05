"""Invert a rendered UV map into a source-pixel -> render-pixel map.

Adapted from tanguymagne/SyntheticDoc (generation/backward_mapping/uv_to_backward_map.py),
MIT License -- see vendor/LICENSE. Two changes from upstream: the EXR is read with OpenCV
(already a dependency of every renderer here) instead of the separate `OpenEXR` package, and
only `uv_to_backward_map` and its helpers are kept -- the CLI and the `.npy`-writing,
grid-sample-ready normalisation are dropped, since `render.py` samples this array directly.

Upstream's own name for this -- "backward map" -- is from a DEWARPING model's point of view:
given a flat target pixel, which rendered pixel does its colour come from. That is exactly
the direction `render.py` needs too, just for a different reason: a label quad is already
in flat, pre-warp pixel coordinates, and `render.py` asks "where did THIS flat point end up
in the render" -- the same map, sampled at the quad's own corners instead of every pixel.
"""

from __future__ import annotations

import os

# A build-time security default in OpenCV, checked at every EXR read -- not a compile flag,
# but it still has to be set before `read_uv_inverse_exr` is ever called, so it happens here
# at import time rather than inside that function.
os.environ.setdefault("OPENCV_IO_ENABLE_OPENEXR", "1")

import cv2  # noqa: E402
import numpy as np  # noqa: E402

# The four directions a missing pixel can be extrapolated from, as (row, column) steps.
_DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _extrapolate(array: np.ndarray, rows_nan: np.ndarray, cols_nan: np.ndarray,
                  drow: int, dcol: int) -> np.ndarray:
    """Extrapolate `array` at the given pixels from their two neighbours along (drow, dcol)."""
    h, w = array.shape
    rows1, cols1 = rows_nan + drow, cols_nan + dcol
    rows2, cols2 = rows_nan + 2 * drow, cols_nan + 2 * dcol

    # Pixels whose neighbours fall outside the array, or are missing themselves, extrapolate to NaN.
    inside = (rows2 >= 0) & (rows2 < h) & (cols2 >= 0) & (cols2 < w)
    rows1, cols1 = np.clip(rows1, 0, h - 1), np.clip(cols1, 0, w - 1)
    rows2, cols2 = np.clip(rows2, 0, h - 1), np.clip(cols2, 0, w - 1)

    # Constant slope from the second neighbour to the first one, continued to the target pixel.
    return np.where(inside, 2 * array[rows1, cols1] - array[rows2, cols2], np.nan)


def _fill_missing(array: np.ndarray) -> np.ndarray:
    """Fill the NaNs of a 2D array by repeatedly extrapolating from its valid pixels."""
    filled = np.copy(array)
    rows_nan, cols_nan = np.where(np.isnan(filled))

    while rows_nan.size > 0:
        candidates = np.stack([_extrapolate(filled, rows_nan, cols_nan, *d) for d in _DIRECTIONS])

        # A single direction is too unreliable to extrapolate from, so two are required.
        fillable = np.count_nonzero(~np.isnan(candidates), axis=0) >= 2
        if not fillable.any():
            break

        filled[rows_nan[fillable], cols_nan[fillable]] = np.nanmean(candidates[:, fillable], axis=0)
        rows_nan, cols_nan = rows_nan[~fillable], cols_nan[~fillable]

    return filled


def uv_to_backward_map(uv_map: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Turn a rendered UV map into a `size`-shaped map of render-pixel coordinates.

    `uv_map` is `(H, W, 3)`: R=u, G=v (both in [0, 1]), B>0 marking a pixel that shows the
    paper (see `vendor/ground_truth_module.py::createUVGradientMaterial`). `size` is
    `(height, width)` of the FLAT document the page was rendered from -- i.e. the shape a
    label quad's own pixel coordinates already live in.

    Returns an array of that shape plus 2, `bm[y, x] = (row, col)`: the pixel of the
    RENDERED image that flat point `(x, y)` ended up at. A point never sampled by any visible
    render pixel (folded out of frame, occluded) is filled by extrapolating from its nearest
    filled neighbours, so the array has no gaps.
    """
    height, width = size

    u_map = uv_map[:, :, 0]
    v_map = uv_map[:, :, 1]
    visible = uv_map[:, :, 2] > 0

    if not visible.any():
        raise ValueError("UV map has no visible page pixels -- nothing to invert")

    from scipy.interpolate import LinearNDInterpolator
    from scipy.spatial import Delaunay

    us, vs = u_map[visible] * width, v_map[visible] * height
    rows, cols = np.where(visible)

    grid_u, grid_v = np.meshgrid(np.arange(width), np.arange(height))
    queries = np.stack([grid_u.ravel(), grid_v.ravel()], axis=1)

    # Shifted by half a pixel, to place grid samples at the centre of each output pixel.
    triangulation = Delaunay(np.stack([us, vs], axis=1) - 0.5)

    bm_x = LinearNDInterpolator(triangulation, cols, fill_value=np.nan)(queries).reshape(size)
    bm_y = LinearNDInterpolator(triangulation, rows, fill_value=np.nan)(queries).reshape(size)
    bm = np.dstack([_fill_missing(bm_y), _fill_missing(bm_x)])  # (row, col), not (x, y)

    # V grows upwards in the UV map, whereas rows grow downwards in a normal image.
    return bm[::-1]


def read_uv_inverse_exr(path) -> np.ndarray:
    """Read a `uv_inverse.exr` written by `vendor/ground_truth_module.py`, as `(H, W, 3)` RGB.

    OpenCV needs `OPENCV_IO_ENABLE_OPENEXR=1` set before it is imported to read EXR at all
    (a build-time security default, not a runtime flag) -- `render.py` sets it. It also reads
    multi-channel images as BGR regardless of format, so the channels are flipped here to the
    R=u, G=v, B=visible order `uv_to_backward_map` expects.
    """
    image = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if image is None:
        raise RuntimeError(f"could not read {path} as an image (OpenEXR support missing?)")
    return image[..., ::-1]


__all__ = ["read_uv_inverse_exr", "uv_to_backward_map"]
