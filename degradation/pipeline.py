"""Run a recipe's augmentation attribute over a rendered page.

All three renderers call `apply_recipe` at the same point -- once the sheet
has been drawn and before it is placed on a background -- so a receipt is aged
the same way whether it was drawn with glyphs or with HTML. Keeping this in one
function is the difference between comparing three renderers and comparing
three ageing implementations that happen to share a name.

    from degradation.pipeline import apply_recipe
    aged = apply_recipe(image, recipe, seed=recipe.seed)
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np

from . import apply_one


def chain_of(recipe) -> list[tuple[str, dict[str, Any]]]:
    """The (name, options) pairs the recipe's augmentation attribute asks for."""
    raw = recipe.get("augmentation", "chain", []) or []
    chain = []
    for entry in raw:
        if isinstance(entry, (list, tuple)):
            name = entry[0]
            options = dict(entry[1]) if len(entry) > 1 and entry[1] else {}
        elif isinstance(entry, dict):  # {name: {...}} is the other natural YAML shape
            (name, options), = entry.items()
            options = dict(options or {})
        else:
            name, options = str(entry), {}
        chain.append((name, options))
    return chain


def apply_recipe(image: np.ndarray, recipe, seed: int | None = None) -> np.ndarray:
    """Age `image` per `recipe`, filling in the paper the visual attribute chose.

    `paper_texture` in the chain never names a sheet; the sheet comes from
    `visual.paper`, so the same recipe puts the same paper under a glyph render
    and an HTML render. A chain entry may still override it explicitly.
    """
    rng = random.Random(recipe.seed if seed is None else seed)
    paper = recipe.get("visual", "paper", "auto")
    alpha_range = recipe.get("visual", "paper_alpha")

    out = image
    for name, options in chain_of(recipe):
        if name == "paper_texture":
            options.setdefault("paper", paper)
            if alpha_range and "alpha" in options:
                # The chain says how aged the sheet is; the visual attribute
                # says how much that sheet shows through this printer's stock.
                low, high = alpha_range
                options["alpha"] = float(options["alpha"]) * rng.uniform(low, high) / 0.2
        out = apply_one(out, name, options, rng)
    return out


__all__ = ["apply_recipe", "chain_of"]
