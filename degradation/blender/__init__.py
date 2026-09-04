"""Page warps rendered through Blender -- see `render.py` for the why and the contract.

    from degradation.blender import warp_regions
    image, boxes = warp_regions("page_curl", image, {}, rng, boxes)

`meshes.names()` lists the scenarios (`page_curl`, `fold_crease`, `corner_bulge`); each is a
key of `rulebase.rules.augmentation.yaml`'s "HÌNH HỌC" options, read from there via
`augmentation.warp` -- see `generators/html/render.py`.
"""

from __future__ import annotations

from .meshes import names
from .render import BlenderWarpError, apply_warp, find_blender, warp_regions

__all__ = ["BlenderWarpError", "apply_warp", "find_blender", "names", "warp_regions"]
