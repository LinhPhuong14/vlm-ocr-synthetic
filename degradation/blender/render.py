"""Warp a page through Blender -- geometry, materials, camera and lighting, all real.

The successor to an earlier pure-numpy `degradation/geometry.py` (removed): that module
approximated a curl or a fold as a 2D pixel remap plus an analytic Lambertian shade, and
looked like it next to SyntheticDoc's own renders (github.com/tanguymagne/SyntheticDoc,
`media/teaser.jpg`) -- flat where theirs has real directional shading and true perspective
foreshortening from a page sitting on a table, photographed at an angle. This module gets
that by actually rendering: `degradation/blender/meshes.py` bends a flat page into a 3D
mesh (numpy, no physics engine -- see that module's docstring for why), and
`vendor/sample_renderer.py` (adapted from SyntheticDoc, MIT license) puts it in a Blender
scene with a real paper material, a real camera search for an unoccluded angle, and one of
four studio lighting presets, then renders it.

The cost of that realism is real too: a call here shells out to Blender and takes on the
order of a minute (`vendor/config.py`'s `RENDER_SAMPLES`/`SIMULATION_FRAMES` are tuned for
speed over photorealism, by eye, against this repo's CPU-only Cycles), against the
microseconds of a pixel remap -- which is exactly why every rule-base option that names a
scenario here ships `enabled: false`. See `rulebase/rules/augmentation.yaml`'s "HÌNH HỌC"
section.

    from degradation.blender.render import warp_regions
    image, boxes, words, cells = warp_regions(
        "page_curl", image, {"angle": [20, 45]}, rng, boxes, words, cells)

Box remapping -- the part that keeps `nhãn khớp pixel` (labels matching pixels) once the
page is no longer a flat crop of the render -- goes through `uv_inverse.py`: Blender also
renders a UV-inverse map (which flat point each rendered pixel shows), inverted here into
the opposite direction, source pixel -> render pixel, and every quad corner is resampled
through that map.

The render canvas itself (`vendor/config.py`'s `RESOLUTION_X`/`RESOLUTION_Y`) is sized for
the worst-case camera distance a stubborn fold's visibility-check retries can reach, not for
how big the page usually looks -- left alone, most pages would be a small object surrounded
by background. `apply_warp` crops back to the page's own footprint (`_page_bounding_box`,
read off the same UV-inverse map) plus a small margin before returning, which is also why
the camera is free to back off as far as it needs to: a page that ends up tiny in-frame gets
cropped back to size, not shipped tiny.
"""

from __future__ import annotations

import json
import random
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from scipy.ndimage import map_coordinates

from . import meshes
from .uv_inverse import read_uv_inverse_exr, uv_to_backward_map

REPO_ROOT = Path(__file__).resolve().parents[2]
VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
SAMPLE_RENDERER = VENDOR_DIR / "sample_renderer.py"
BACKGROUND_DIR = REPO_ROOT / "textures" / "background"

# A physical width for the page, in metres -- arbitrary (only the ASPECT RATIO, derived from
# the image below, actually shapes the mesh), but has to be in the right order of magnitude
# for `vendor/config.py`'s camera lens/light/table constants, all tuned for an A4-ish sheet.
PAGE_WIDTH_M = 0.21

# `NoValidCameraAngleError` has two causes (see `_render`'s docstring), and backing the
# camera off helps both: a mesh that does not fit the frame obviously needs more room, but a
# multi-bump mesh (`crease_bundle`, `crumple`) that fails on local normal consistency instead
# also clears more candidates once it is not ALSO fighting an out-of-frame rejection on top --
# confirmed by hand: a `crease_bundle` mesh that failed all 26 candidates at ~0.7m passed 6 of
# them at 1.5m, nothing else about the mesh changed. Retried up to this many times, with the
# mesh regenerated fresh each attempt (see `_render`) since the distance alone does not fix
# every failure.
_CAMERA_DISTANCE_RETRIES = 6
_CAMERA_DISTANCE_GROWTH = 1.5


# Fraction of the page's own bounding-box size added back as a margin on every side after
# cropping to it -- enough that a label quad drawn right at the page edge (rare, but the
# UV-visibility mask can be a pixel tighter than the geometry it came from) is not cut off.
_CROP_MARGIN_RATIO = 0.04


class BlenderWarpError(RuntimeError):
    """A Blender render failed for a reason other than camera framing."""


def _page_bounding_box(uv_map: np.ndarray) -> tuple[int, int, int, int] | None:
    """Pixel bounding box `(x0, y0, x1, y1)` (inclusive) of the visible page in a UV-inverse
    render, expanded by `_CROP_MARGIN_RATIO`. `None` if the mask is empty (should not happen
    for a render that already passed the visibility check, but a page that vanished would
    otherwise crop to a zero-size image with no error)."""
    mask = uv_map[..., 2] > 0
    if not mask.any():
        return None
    ys, xs = np.where(mask)
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    margin_x = max(1, round((x1 - x0) * _CROP_MARGIN_RATIO))
    margin_y = max(1, round((y1 - y0) * _CROP_MARGIN_RATIO))
    height, width = mask.shape
    x0 = max(0, x0 - margin_x)
    x1 = min(width - 1, x1 + margin_x)
    y0 = max(0, y0 - margin_y)
    y1 = min(height - 1, y1 + margin_y)
    return x0, y0, x1, y1


def find_blender() -> str:
    """A `blender` executable, or raise with where to get one.

    Checked on `PATH` first (`shutil.which`), which covers `apt install blender` and any
    manual install that added itself there; a short list of common install locations
    covers the platforms whose installer does not.
    """
    on_path = shutil.which("blender")
    if on_path:
        return on_path

    candidates = [
        "/usr/bin/blender",
        "/opt/blender/blender",
        "/Applications/Blender.app/Contents/MacOS/Blender",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate

    raise BlenderWarpError(
        "no `blender` executable found. Install it (`make setup-blender`, or "
        "https://www.blender.org/download/ -- 4.1+ preferred, see vendor/blender_utils.py "
        "for what changes on 4.0) and make sure it is on PATH.")


def _pick_background(rng: random.Random) -> Path:
    """One of this repo's own `textures/background/*` photos, as its own directory.

    Blender's `createPBRMaterial` (vendor/material_handler.py) treats every image in a
    directory as a map of the SAME material -- Node Wrangler would try to read eight
    unrelated photos as eight channels of one surface. So the chosen file is copied into
    its own temporary directory rather than pointed at `textures/background/` directly.
    """
    photos = sorted(p for p in BACKGROUND_DIR.iterdir() if p.is_file())
    if not photos:
        raise BlenderWarpError(f"no background photos in {BACKGROUND_DIR}")
    return Path(rng.choice(photos))


def _run_sample_renderer(
    blender: str, mesh_path: Path, document_path: Path, background_dir: Path,
    output_dir: Path, sample_id: int, camera_distance: float,
) -> dict[str, Any]:
    """One `blender --background` call; returns the metadata dict `sample_renderer.py` prints."""
    result = subprocess.run(
        [blender, "--background", "--python", str(SAMPLE_RENDERER), "--",
         "--mesh-path", str(mesh_path), "--document-path", str(document_path),
         "--background-path", str(background_dir), "--output-dir", str(output_dir),
         "--sample-id", str(sample_id), "--camera-distance", str(camera_distance)],
        capture_output=True, text=True,
        # `vendor/config.py::BASE_PAPER_MATERIAL_BLEND` is relative -- SyntheticDoc's own
        # README says its rendering scripts run "from this folder", and vendoring kept
        # that rather than hardcoding an absolute path config.py has no other reason to know.
        cwd=str(VENDOR_DIR),
    )
    # `sample_renderer.py` prints its metadata as one line of stdout on both a successful
    # and a caught-and-recorded failure -- but not the LAST line: `--background` mode
    # prints its own "Blender quit" after control returns from the script. Searched from
    # the end rather than assumed to be last, then, and skipped entirely only by a crash
    # before that point (a missing `numpy` in Blender's own Python, most often), which
    # leaves nothing to find and is reported through stderr instead.
    for line in reversed(result.stdout.strip().splitlines()):
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            continue
    raise BlenderWarpError(
        f"blender produced no parseable metadata (exit {result.returncode}); "
        f"stderr tail:\n{result.stderr[-3000:]}\nstdout tail:\n{result.stdout[-1000:]}")


def _render(
    name: str, width_m: float, height_m: float, params: dict[str, Any] | None, rng: random.Random,
    tmp_dir: Path,
) -> dict[str, Any]:
    """Pick a background and render -- retrying with a fresh mesh draw and a larger camera
    distance on a camera-angle failure.

    `NoValidCameraAngleError` has two, unrelated causes (`vendor/camera_angle_sampler.py::
    isMeshVisibleFromCamera`): the mesh does not FIT the frame (fixed by backing the camera
    off, which is all the retry used to do), or parts of it face away from every candidate
    angle -- a fold-back the visibility check is designed to catch (fixed by nothing except a
    different mesh; several independent creases summed rather than integrated, as
    `crease_bundle` and `crumple` are, can draw a combination steep enough to trigger this).
    The mesh is regenerated every attempt now, from the same `rng`, so a retry can fix either.
    """
    blender = find_blender()
    background_photo = _pick_background(rng)
    background_dir = tmp_dir / "background"
    background_dir.mkdir()
    shutil.copy(background_photo, background_dir / background_photo.name)

    output_dir = tmp_dir / "out"
    distance = 2.5 * ((width_m**2 + height_m**2) ** 0.5)

    last_metadata = None
    for attempt in range(_CAMERA_DISTANCE_RETRIES):
        mesh_path = tmp_dir / f"mesh_{attempt}.obj"
        meshes.generate(name, width_m, height_m, rng, mesh_path, params)
        sample_id = rng.randint(0, 2**31 - 1)
        metadata = _run_sample_renderer(
            blender, mesh_path, tmp_dir / "document.png", background_dir,
            output_dir, sample_id, distance)
        if metadata.get("status") == "success":
            return metadata
        last_metadata = metadata
        if metadata.get("error_type") != "NoValidCameraAngleError":
            raise BlenderWarpError(
                f"blender render failed ({metadata.get('error_type')}): {metadata.get('error')}")
        distance *= _CAMERA_DISTANCE_GROWTH

    raise BlenderWarpError(
        f"no camera angle saw the whole page after {_CAMERA_DISTANCE_RETRIES} attempts "
        f"(last distance tried {distance / _CAMERA_DISTANCE_GROWTH:.3f}m); last error: "
        f"{last_metadata.get('error') if last_metadata else '?'}")


def apply_warp(
    name: str, image: np.ndarray, quads: np.ndarray,
    params: dict[str, Any] | None = None, rng: random.Random | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Warp `image` through Blender and remap `quads` (an `(N, 4, 2)` array) along with it.

    `quads` may be empty (shape `(0, 4, 2)`) -- the render still runs, nothing is remapped.
    See the module docstring for `params` (passed to the mesh scenario in `meshes.py`) and
    the cost of a call.
    """
    if name not in meshes.MESHES:
        raise KeyError(f"unknown warp {name!r}; have {', '.join(meshes.names())}")
    rng = rng or random.Random()
    quads = np.asarray(quads, dtype=np.float32).reshape(-1, 4, 2)

    height, width = image.shape[:2]
    width_m = PAGE_WIDTH_M
    height_m = width_m * height / width

    tmp_dir = Path(tempfile.mkdtemp(prefix="blender_warp_"))
    try:
        cv2.imwrite(str(tmp_dir / "document.png"), image)
        metadata = _render(name, width_m, height_m, params, rng, tmp_dir)

        render_path = Path(metadata["outputs"]["render"])
        uv_path = Path(metadata["outputs"]["uv_inverse_map"])
        rendered = cv2.imread(str(render_path))
        if rendered is None:
            raise BlenderWarpError(f"blender wrote {render_path} but it could not be read back")

        # The render canvas (config.RESOLUTION_X/Y, 1024x1440 by default) is sized for the
        # WORST-case camera distance the visibility-check retries can reach (see `_render`),
        # not for how big the page usually needs to look -- most of the time the page is a
        # small object in a mostly-background frame. Cropped down to its own footprint (plus
        # a margin) here, which is also why the retries above are free to back the camera off
        # as far as a stubborn fold needs: a page that ends up tiny in-frame is cropped back
        # to size, not shipped tiny.
        uv_map = read_uv_inverse_exr(uv_path)
        bbox = _page_bounding_box(uv_map)
        crop_x0, crop_y0 = bbox[:2] if bbox else (0, 0)
        if bbox:
            x0, y0, x1, y1 = bbox
            rendered = rendered[y0:y1 + 1, x0:x1 + 1]

        if quads.size:
            backward_map = uv_to_backward_map(uv_map, size=(height, width))
            ys = quads[..., 1].ravel()
            xs = quads[..., 0].ravel()
            new_rows = map_coordinates(backward_map[..., 0], [ys, xs], order=1, mode="nearest")
            new_cols = map_coordinates(backward_map[..., 1], [ys, xs], order=1, mode="nearest")

            # `uv_inverse.fill_missing` extrapolates a quad corner that lands on a source
            # point never sampled by any visible render pixel (folded out of frame, occluded
            # by another part of the sheet) -- usually off by a few pixels, occasionally, for
            # a corner near a steep fold, by a wild margin (seen once during testing:
            # (-1868, 7181) against a 1024x1440 canvas). A page with one such corner fails
            # `pipeline.record.validate`'s frame check anyway, so it is caught HERE instead,
            # loudly, rather than shipped as a record with one silently wrong label. Checked
            # against the UNCROPPED render, which is the space `backward_map` is in.
            uncropped_h, uncropped_w = uv_map.shape[:2]
            margin = max(uncropped_h, uncropped_w)
            in_range = (
                np.isfinite(new_rows) & np.isfinite(new_cols)
                & (new_rows >= -margin) & (new_rows <= uncropped_h + margin)
                & (new_cols >= -margin) & (new_cols <= uncropped_w + margin)
            )
            if not in_range.all():
                bad = int((~in_range).sum())
                raise BlenderWarpError(
                    f"{bad}/{in_range.size} quad corners remapped to a wild position after "
                    "warping (backward-map extrapolation near a steep fold) -- retry with a "
                    "different seed rather than trust this render's labels")

            new_rows -= crop_y0
            new_cols -= crop_x0
            quads = np.stack([new_cols, new_rows], axis=-1).reshape(quads.shape).astype(np.float32)

        return rendered, quads
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def warp_regions(
    name: str, image: np.ndarray, params: dict[str, Any] | None, rng: random.Random,
    *region_lists: list[dict[str, Any]],
) -> tuple[Any, ...]:
    """Warp `image` and every quad in `region_lists` through the SAME Blender render.

    Same contract the old `degradation/geometry.py::warp_regions` had, and the same reason
    for it: `boxes`, `words` and `cells` describe one page, so they have to be warped by one
    render and one box-remap pass, not warped -- and re-rendered -- separately.
    """
    counts = [len(regions) for regions in region_lists]
    flat = [box["quad"] for regions in region_lists for box in regions]
    quads = (np.asarray(flat, dtype=np.float32).reshape(-1, 4, 2)
              if flat else np.zeros((0, 4, 2), dtype=np.float32))

    new_image, new_quads = apply_warp(name, image, quads, params, rng)

    out: list[list[dict[str, Any]]] = []
    offset = 0
    for regions, count in zip(region_lists, counts):
        updated = []
        for box, quad in zip(regions, new_quads[offset:offset + count].tolist()):
            updated.append({**box, "quad": [[round(x, 1), round(y, 1)] for x, y in quad]})
        out.append(updated)
        offset += count
    return (new_image, *out)


__all__ = ["BlenderWarpError", "apply_warp", "find_blender", "warp_regions"]
