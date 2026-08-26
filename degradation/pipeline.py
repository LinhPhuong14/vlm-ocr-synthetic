"""Run a recipe's augmentation attribute over a rendered page.

All three renderers call `apply_recipe` at the same point -- once the sheet
has been drawn and before it is placed on a background -- so a receipt is aged
the same way whether it was drawn with glyphs or with HTML. Keeping this in one
function is the difference between comparing three renderers and comparing
three ageing implementations that happen to share a name.

    from degradation.pipeline import apply_recipe
    aged = apply_recipe(image, recipe, seed=recipe.seed, boxes=boxes)

`boxes` is the page's label quads, and it is optional only because callers
without labels exist -- `tools/augment_samples.py` runs over directories of
finished images. A chain that asks for `by_box` and gets no boxes fails loudly
rather than quietly ageing the whole sheet; see `degradation/regions.py`.
"""

from __future__ import annotations

import random
from typing import Any

import numpy as np

import profiling

from . import apply_one


def chain_of(recipe) -> list[tuple[str, dict[str, Any]]]:
    """Every (name, options) pair the recipe asks for, in the order drawn.

    **Any attribute may carry a `chain`, not only `augmentation`.** That was the
    shape from the start -- `augmentation` was simply the only one that used it
    -- and it stopped being a hypothetical when the copier split into `toner`,
    `drum` and `rollers`: three parts of one machine, drawn independently so a
    page can have a scored drum without a spent cartridge, instead of getting
    all three or none from whichever hand-written scenario happened to be drawn.

    Concatenated in DRAW ORDER, which `rules/_order.yaml` fixes and
    `Recipe.choices` preserves. That is what puts the machine's marks after the
    sheet has been aged rather than under it, and it is the only thing that
    decides the order -- so moving a line in `_order.yaml` moves the step.
    """
    chain = []
    for option in recipe.choices.values():
        for entry in option.params.get("chain") or []:
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


def apply_recipe(
    image: np.ndarray, recipe, seed: int | None = None, boxes=None
) -> np.ndarray:
    """Age `image` per `recipe`, filling in the paper the visual attribute chose.

    `paper_texture` in the chain never names a sheet; the sheet comes from
    `visual.paper`, so the same recipe puts the same paper under a glyph render
    and an HTML render. A chain entry may still override it explicitly.

    `boxes` are the page's label quads, passed straight through to `by_box` --
    the only chain entry that acts on part of the page rather than all of it.
    """
    rng = random.Random(recipe.seed if seed is None else seed)
    paper = recipe.get("visual", "paper", "auto")
    if isinstance(paper, (list, tuple)):
        # `visual.paper` may name a shortlist rather than one sheet. Drawn here
        # rather than left to `_pick_texture`, because that helper's fallback is
        # "any file in the directory" -- a shortlist has to stay a shortlist, or
        # an impact printer offered three coarse stocks would also be handed the
        # glossy thermal roll.
        paper = rng.choice(list(paper))
    alpha_range = recipe.get("visual", "paper_alpha")

    out = image
    for name, options in chain_of(recipe):
        if name == "paper_texture":
            options.setdefault("paper", paper)
            if alpha_range and "alpha" in options:
                # Two attributes have a say. The chain's `alpha` is how aged
                # this scenario's sheet is; `visual.paper_alpha` is how much
                # paper shows through *this printer's stock* -- fresh thermal
                # roll hides its own texture, recycled stock does not.
                #
                # NEUTRAL is the paper_alpha at which the chain's number is
                # used unchanged, so a scenario tuned by eye against ordinary
                # paper keeps looking the way it was tuned.
                neutral = 0.2
                low, high = alpha_range
                options["alpha"] = float(options["alpha"]) * rng.uniform(low, high) / neutral
        # Timed one model at a time: the chain's cost is not evenly spread, and
        # which model dominates is exactly the thing a suspect list gets wrong.
        with profiling.stage(name):
            out = apply_one(out, name, options, rng, boxes)
    return out


__all__ = ["apply_recipe", "chain_of"]
