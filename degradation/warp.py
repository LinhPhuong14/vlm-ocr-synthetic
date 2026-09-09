"""The one door for `augmentation.warp` -- pick the engine by the name it asks for.

Two engines bend a page, and a rule names one of them the same way either way:

``degradation.blender``   a real Blender render of a real 3D sheet. Seconds to
                          a minute a page; every rule naming it is `enabled: false`.
``degradation.paper_warp``a displacement field read out of a photograph of paper.
                          Milliseconds, and the fold you see is the fold that moved.
``degradation.simulated_warp``
                          a page projected onto a mesh a cloth simulator deformed.
                          The only one that can destroy text -- and the only one
                          that says WHICH labels it destroyed. Reads meshes a rule
                          points it at; a no-op with no directory.

Both expose the same `warp_regions(name, image, params, rng, *region_lists)`, so
`generators/html/render.py` calls this and stays out of the choice. Adding an
engine means adding it to `ENGINES` here, not touching the renderer.

Importing `degradation.blender` costs nothing until it shells out, so both are
imported eagerly -- a missing `blender` executable is reported by that module
when a page actually asks for it, not by an import failing at start-up.
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np

from . import blender, paper_warp, simulated_warp

ENGINES = (paper_warp, simulated_warp, blender)


def names() -> list[str]:
    """Every warp scenario a rule may name, across engines."""
    return sorted(name for engine in ENGINES for name in engine.names())


def engine_for(name: str):
    for engine in ENGINES:
        if name in engine.names():
            return engine
    raise KeyError(f"unknown warp {name!r}; have {', '.join(names())}")


def warp_regions(
    name: str, image: np.ndarray, params: dict[str, Any] | None, rng: random.Random,
    *region_lists: list[dict[str, Any]],
) -> tuple[Any, ...]:
    return engine_for(name).warp_regions(name, image, params, rng, *region_lists)


__all__ = ["ENGINES", "engine_for", "names", "warp_regions"]
