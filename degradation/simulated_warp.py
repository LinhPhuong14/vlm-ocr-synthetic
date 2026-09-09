"""Warp a page onto a mesh a CLOTH SIMULATOR deformed -- the one engine here that
can genuinely destroy text, and says which labels it destroyed.

Measured against the two engines that came before it, on the same 60-box probe page:

    engine                     méo tối đa   hộp hỏng   hộp bị che
    paper_photo (ảnh giấy)          ~1.0       0/60         0/60
    blender (mesh giải tích)        1.46       0/60         0/60
    simulated (ARCSim crumple)     14.42      24/60        53/60

The first two cannot destroy a glyph, and that is structural, not luck.
`paper_photo` bounds the Jacobian by construction. `blender/meshes.py` builds
DEVELOPABLE surfaces -- arc-length preserving, so a fold cannot stretch what is
printed on it -- and `vendor/camera_angle_sampler.py` refuses any camera that
cannot see the whole sheet, measured: `crumple` at amplitude 0.030 (twice what
the rule-base ships) is REFUSED after six attempts. A page that reaches a dataset
through those engines is a page whose every label still describes readable ink.

A real crumple is a different object. It is not developable: material folds onto
itself, facets turn edge-on to the camera, and parts of the sheet hide behind
other parts. That is where an OCR model actually fails, and it is the one thing a
generator cannot fake by filtering pixels.

## Where the meshes come from, and the licence

Nothing here simulates anything. This engine READS pre-simulated meshes from a
directory the rules name, and ships pointing at nothing: with no mesh directory
it is a no-op, the same contract `texture.paper_overlay` has for a missing photo.

The meshes this was built and measured against came from ARCSim
(graphics.eecs.berkeley.edu/resources/ARCSim/, Narain et al. 2012/2013), which is
licensed for "educational, research, and not-for-profit purposes" ONLY -- see
`degradation/blender/vendor/NOTICE.md` for why that licence kept ARCSim out of
this repository's own pipeline, and note that the decision recorded there is
about VENDORING the simulator, which this file still does not do. Producing the
meshes is a step the operator runs outside this repository, under whatever
licence applies to them; this file is a mesh reader and knows nothing about what
wrote them. **A commercial dataset must not be built on ARCSim output without
Berkeley's commercial licence.** Any simulator whose `.obj` frames carry material
-space coordinates works here.

## Material-space coordinates are the whole trick

A simulated `.obj` carries `ms` lines -- the position of each vertex on the FLAT
sheet, in metres, one per vertex. That is the true UV: it says exactly which part
of the printed page each scrap of crumpled paper is. The Blender path cannot use
it (`vendor/uv_unwrap.py` runs an ANGLE-BASED unwrap that overwrites any UV the
mesh arrived with -- correct for a near-flat surface, garbage for a ball), which
is why this engine projects and rasterises itself, in numpy. That also makes it
seconds rather than the minutes a Blender render costs.

## What it hands back that nothing else does

Occlusion. A label whose corners land behind another fold is not degraded text,
it is ABSENT text -- and a record that still claims the string is the poisoned
data `tools/legibility.py` exists to keep out. `warp_regions` marks those boxes
`legible: false`, which is the input the `illegible_silence` assertion needs.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from .texture import _as_bgr, _restore

NAME = "simulated_paper"

DEFAULTS: dict[str, Any] = {
    "meshes": None,        # thư mục .obj đã mô phỏng sẵn; None -> no-op
    "frame": [0.15, 0.55],  # vị trí trong dãy frame, 0 = phẳng, 1 = vò nát nhất
    "elev": [-25.0, 25.0],  # góc camera, độ
    "azim": [-25.0, 25.0],
    "pad": 1.15,           # khoảng trống quanh tờ giấy trong khung
    "shade": 0.55,         # độ mạnh của đổ bóng Lambert
    "occluded_corners": 2,  # số góc bị che thì coi hộp là mất chữ
}


def names() -> list[str]:
    return [NAME]


def _draw(rng: random.Random, spec: Any) -> float:
    if isinstance(spec, (tuple, list)):
        return rng.uniform(float(spec[0]), float(spec[1]))
    return float(spec)


def frames(directory: Path) -> list[Path]:
    """Every simulated frame in `directory`, in simulation order.

    Obstacle meshes (`obs*.obj`) are what the sheet was crumpled AGAINST, not the
    sheet; they sit in the same directory and would otherwise be drawn as if they
    were pages.
    """
    if not directory.exists():
        return []
    return sorted(p for p in directory.glob("*.obj") if not p.name.startswith("obs"))


def read_mesh(path: Path):
    """`.obj` with ARCSim-style `ms` lines -> (verts 3D, material-space 2D, faces).

    `ms` is one line per vertex and comes BEFORE the `v` block, so the two are
    matched by order, not by index; a file whose counts disagree is rejected
    rather than silently zipped short.
    """
    verts, flat, faces = [], [], []
    for line in path.read_text().splitlines():
        if line.startswith("v "):
            verts.append([float(v) for v in line.split()[1:4]])
        elif line.startswith("ms "):
            flat.append([float(v) for v in line.split()[1:3]])
        elif line.startswith("f "):
            faces.append([int(tok.split("/")[0]) - 1 for tok in line.split()[1:4]])
    if len(flat) != len(verts):
        raise ValueError(
            f"{path.name}: {len(verts)} vertices but {len(flat)} material-space lines; "
            f"this engine needs one `ms` per vertex -- see the module docstring")
    return np.asarray(verts), np.asarray(flat), np.asarray(faces, dtype=np.int32)


def _view_axis(verts: np.ndarray, faces: np.ndarray) -> np.ndarray:
    """Which way a photographer would stand: square to the sheet, printed side up.

    A fixed world axis is wrong here and it shows immediately -- a simulator's own
    set-up transform can leave the sheet standing on edge (ARCSim's `crumple.json`
    rotates it 85 degrees before dropping it), and a camera on a fixed axis then
    photographs the sheet edge-on and calls two thirds of the page occluded. The
    sheet's own plane is what the angles should be measured FROM.

    Taken as the area-weighted sum of the face normals, which for a sheet still
    recognisably a sheet points out of its printed side -- and falls back to the
    smallest-variance principal axis once it has been crumpled into a ball, where
    no side is the front any more and either answer is as good.
    """
    centre = verts.mean(axis=0)
    tri = verts[faces]
    cross = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    total = float(np.linalg.norm(cross, axis=1).sum())
    net = cross.sum(axis=0)
    if total > 0 and float(np.linalg.norm(net)) > 0.1 * total:
        return net / np.linalg.norm(net)
    _, _, vh = np.linalg.svd(verts - centre, full_matrices=False)
    return vh[2] / np.linalg.norm(vh[2])


def _camera(verts: np.ndarray, faces: np.ndarray, elev: float, azim: float,
            pad: float, size):
    """Look at the mesh from (elev, azim) OFF ITS OWN PLANE, far enough to hold it all."""
    width, height = size
    centre = verts.mean(axis=0)
    radius = float(np.linalg.norm(verts - centre, axis=1).max())

    axis = _view_axis(verts, faces)
    helper = np.array([0.0, 0.0, 1.0]) if abs(axis[1]) > 0.9 else np.array([0.0, 1.0, 0.0])
    side = np.cross(helper, axis); side /= np.linalg.norm(side)
    up = np.cross(axis, side)
    e, a = np.radians(elev), np.radians(azim)
    direction = (np.cos(e) * np.cos(a) * axis + np.cos(e) * np.sin(a) * side
                 + np.sin(e) * up)
    direction /= np.linalg.norm(direction)

    eye = centre + direction * radius * 3.2
    forward = centre - eye
    distance = float(np.linalg.norm(forward))
    forward /= distance
    reference = np.array([0.0, 0.0, 1.0]) if abs(forward[1]) > 0.9 \
        else np.array([0.0, 1.0, 0.0])
    right = np.cross(forward, reference)
    right /= np.linalg.norm(right)
    basis = np.stack([right, np.cross(right, forward), forward])
    focal = min(width, height) / (2 * pad * radius / distance)
    return eye, basis, focal


def _project(points: np.ndarray, eye, basis, focal, size):
    width, height = size
    rel = (points - eye) @ basis.T
    depth = np.maximum(rel[:, 2], 1e-6)
    return np.stack([width / 2 + focal * rel[:, 0] / depth,
                     height / 2 - focal * rel[:, 1] / depth], axis=1), depth


def _rasterise(screen, depth, faces, texture, flat, sheet, shade, size):
    """Texture-mapped z-buffer rasteriser.

    Back faces are drawn as BLANK paper rather than culled: the reverse of a
    printed sheet is opaque and unprinted, so a fold showing its back must hide
    what is behind it. Culling would let the far side of the sheet read through
    the near side, which is the one artefact that would give this away instantly.
    """
    width, height = size
    out = np.full((height, width, 3), 246, np.uint8)
    zbuf = np.full((height, width), np.inf, np.float32)
    th, tw = texture.shape[:2]
    # Offset by the material-space MINIMUM, not just scaled by the span: a sheet
    # whose flat coordinates do not start at the origin (any simulator is free to
    # write them that way) would otherwise have the page slid off it by exactly
    # that offset, and the render would still look plausible.
    origin = flat.min(axis=0)
    uv = np.stack([(flat[:, 0] - origin[0]) / sheet[0] * (tw - 1),
                   (1.0 - (flat[:, 1] - origin[1]) / sheet[1]) * (th - 1)], axis=1)

    tri = faces
    a, b, c = screen[tri[:, 0]], screen[tri[:, 1]], screen[tri[:, 2]]
    # NEGATED because screen y points DOWN: the projection flips handedness, so a
    # triangle wound front-facing in 3D comes out clockwise here. Without the sign
    # the renderer paints the page on the BACK of every facet -- text mirrored,
    # printed side blank, and it reads as a texture bug rather than a winding one.
    facing = -((b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) -
               (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0]))
    # Lambert against the screen-space foreshortening: a facet turned away from
    # the camera catches less light, which is what makes a crease read as a crease.
    area = np.abs(facing)
    flatness = area / np.maximum(area.max(), 1e-9)
    lit = 1.0 - shade * (1.0 - np.clip(flatness ** 0.25, 0, 1))

    for fi in np.argsort(-depth[tri].mean(axis=1)):
        f = tri[fi]
        p = screen[f]
        x0, y0 = np.floor(p.min(axis=0)).astype(int)
        x1, y1 = np.ceil(p.max(axis=0)).astype(int)
        x0, y0 = max(int(x0), 0), max(int(y0), 0)
        x1, y1 = min(int(x1), width - 1), min(int(y1), height - 1)
        if x1 <= x0 or y1 <= y0 or (x1 - x0) * (y1 - y0) > 60000:
            continue
        xs, ys = np.meshgrid(np.arange(x0, x1 + 1), np.arange(y0, y1 + 1))
        v0, v1, v2 = p[0], p[1], p[2]
        det = (v1[1] - v2[1]) * (v0[0] - v2[0]) + (v2[0] - v1[0]) * (v0[1] - v2[1])
        if abs(det) < 1e-9:
            continue
        w0 = ((v1[1] - v2[1]) * (xs - v2[0]) + (v2[0] - v1[0]) * (ys - v2[1])) / det
        w1 = ((v2[1] - v0[1]) * (xs - v2[0]) + (v0[0] - v2[0]) * (ys - v2[1])) / det
        w2 = 1.0 - w0 - w1
        z = w0 * depth[f[0]] + w1 * depth[f[1]] + w2 * depth[f[2]]
        sel = (w0 >= 0) & (w1 >= 0) & (w2 >= 0) & (z < zbuf[y0:y1 + 1, x0:x1 + 1])
        if not sel.any():
            continue
        if facing[fi] < 0:                       # mặt sau tờ giấy: giấy trắng, không mực
            colour = np.full((int(sel.sum()), 3), 244.0)
        else:
            t = uv[f]
            tu = (w0 * t[0, 0] + w1 * t[1, 0] + w2 * t[2, 0]).clip(0, tw - 1).astype(int)
            tv = (w0 * t[0, 1] + w1 * t[1, 1] + w2 * t[2, 1]).clip(0, th - 1).astype(int)
            colour = texture[tv[sel], tu[sel]].astype(np.float32)
        patch = out[y0:y1 + 1, x0:x1 + 1]
        patch[sel] = np.clip(colour * lit[fi], 0, 255).astype(np.uint8)
        zb = zbuf[y0:y1 + 1, x0:x1 + 1]
        zb[sel] = z[sel]
    return out, zbuf


def _map_points(points, flat, faces, screen, depth, zbuf, sheet, size):
    """Page pixels -> where they ended up, and whether the sheet hid them.

    Each point is located in MATERIAL space (where the flat page is a plain
    rectangle and the search is a point-in-triangle test), then carried to 3D by
    the same barycentric weights. Going the other way -- searching the crumpled
    3D surface -- has no unique answer, which is exactly the occlusion this
    reports rather than resolves.
    """
    width, height = size
    origin = flat.min(axis=0)
    tri_flat = flat[faces]
    a, b, c = tri_flat[:, 0], tri_flat[:, 1], tri_flat[:, 2]
    det = (b[:, 1] - c[:, 1]) * (a[:, 0] - c[:, 0]) + (c[:, 0] - b[:, 0]) * (a[:, 1] - c[:, 1])
    det = np.where(np.abs(det) < 1e-12, 1e-12, det)

    out = []
    for (px, py) in points:
        u = origin[0] + float(px) / width * sheet[0]
        v = origin[1] + (1.0 - float(py) / height) * sheet[1]
        w0 = ((b[:, 1] - c[:, 1]) * (u - c[:, 0]) + (c[:, 0] - b[:, 0]) * (v - c[:, 1])) / det
        w1 = ((c[:, 1] - a[:, 1]) * (u - c[:, 0]) + (a[:, 0] - c[:, 0]) * (v - c[:, 1])) / det
        w2 = 1.0 - w0 - w1
        hit = np.flatnonzero((w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6))
        if not len(hit):
            out.append((None, True))
            continue
        i = hit[0]
        f = faces[i]
        xy = w0[i] * screen[f[0]] + w1[i] * screen[f[1]] + w2[i] * screen[f[2]]
        z = w0[i] * depth[f[0]] + w1[i] * depth[f[1]] + w2[i] * depth[f[2]]
        xi, yi = int(round(xy[0])), int(round(xy[1]))
        hidden = not (0 <= xi < width and 0 <= yi < height) or z > zbuf[yi, xi] + 1e-4
        out.append((xy, hidden))
    return out


def apply_warp(
    name: str, image: np.ndarray, quads: np.ndarray,
    params: dict[str, Any] | None = None, rng: random.Random | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Warp `image` and `quads` onto one simulated frame.

    Returns `(image, quads, hidden_corners)` -- one more value than the other two
    engines, because this is the only one where a label can be BEHIND the page.
    With no mesh directory it is a no-op on all three.
    """
    if name != NAME:
        raise KeyError(f"unknown simulated warp {name!r}; have {NAME}")
    rng = rng or random.Random(0)
    options = {**DEFAULTS, **(params or {})}
    quads = np.asarray(quads, dtype=np.float32).reshape(-1, 4, 2)
    zero = np.zeros(len(quads), dtype=np.int32)

    directory = options.get("meshes")
    available = frames(Path(directory)) if directory else []
    if not available:
        return image, quads, zero

    picked = available[min(int(_draw(rng, options["frame"]) * len(available)),
                           len(available) - 1)]
    verts, flat, faces = read_mesh(picked)
    # Sheet size comes from the MESH, not from a constant here: the simulator
    # already recorded how big the sheet was, and a letter-size run and an A4 run
    # must not both be told they were 216x279mm.
    sheet = (float(flat[:, 0].max() - flat[:, 0].min()) or 1.0,
             float(flat[:, 1].max() - flat[:, 1].min()) or 1.0)

    out, was_gray = _as_bgr(image)
    height, width = out.shape[:2]
    size = (width, height)
    eye, basis, focal = _camera(verts, faces, _draw(rng, options["elev"]),
                                _draw(rng, options["azim"]),
                                float(options["pad"]), size)
    screen, depth = _project(verts, eye, basis, focal, size)
    rendered, zbuf = _rasterise(screen, depth, faces, out, flat, sheet,
                                float(options["shade"]), size)

    moved = quads.copy()
    hidden = zero.copy()
    if len(quads):
        mapped = _map_points(quads.reshape(-1, 2), flat, faces, screen, depth,
                             zbuf, sheet, size)
        points = np.array([(p if p is not None else (0.0, 0.0)) for p, _ in mapped],
                          dtype=np.float32)
        flags = np.array([h for _, h in mapped], dtype=bool).reshape(-1, 4)
        moved = points.reshape(-1, 4, 2)
        hidden = flags.sum(axis=1).astype(np.int32)
    return _restore(rendered, was_gray), moved, hidden


def warp_regions(
    name: str, image: np.ndarray, params: dict[str, Any] | None, rng: random.Random,
    *region_lists: list[dict[str, Any]],
) -> tuple[Any, ...]:
    """Same contract as the other engines, plus `legible` on every region.

    A box with `occluded_corners` or more of its corners behind the sheet is
    marked `legible: false`. It keeps its text -- the record still knows what was
    printed there -- but a consumer that trains on the string as if it were
    visible is training the model to invent it.
    """
    counts = [len(regions) for regions in region_lists]
    flatlist = [box["quad"] for regions in region_lists for box in regions]
    quads = (np.asarray(flatlist, dtype=np.float32).reshape(-1, 4, 2)
             if flatlist else np.zeros((0, 4, 2), dtype=np.float32))

    new_image, new_quads, hidden = apply_warp(name, image, quads, params, rng)
    limit = int({**DEFAULTS, **(params or {})}["occluded_corners"])

    out: list[list[dict[str, Any]]] = []
    offset = 0
    for regions, count in zip(region_lists, counts):
        updated = []
        for box, quad, hid in zip(regions, new_quads[offset:offset + count].tolist(),
                                  hidden[offset:offset + count].tolist()):
            updated.append({**box,
                            "quad": [[round(x, 1), round(y, 1)] for x, y in quad],
                            "occluded_corners": int(hid),
                            "legible": bool(hid < limit)})
        out.append(updated)
        offset += count
    return (new_image, *out)


__all__ = ["DEFAULTS", "NAME", "apply_warp", "frames", "names", "read_mesh", "warp_regions"]
