"""One rule-base, six attributes, three renderers.

Everything about *what* a synthetic page contains lives here; everything about
*how it is drawn* lives in `generators/`. A backend does three things:

    recipe  = rulebase.sample_recipe(seed=n)      # draw one point in the space
    receipt = rulebase.build_receipt(recipe)      # fill the fields in
    grid    = rulebase.build_grid(receipt, recipe.layout.id)

and then renders `grid`. Because all three backends take the same grid, the
same seed gives the same words in the same columns whether it was drawn with
glyphs, with HTML in a browser, or with WeasyPrint -- which is the only way a
comparison between them means anything.

Adding to the space is editing YAML: a new value in `rules/<attribute>.yaml`,
a new bố cục in `layouts/`, new lines in `corpus/vi/`. See README.md.
"""

from __future__ import annotations

import random

from .content import Item, Receipt, Store
from .content import build as build_receipt
from .corpus import CORPUS_ROOT
from .layout import LAYOUTS_ROOT, Cell, Grid, build_grid
from .layout import available as available_layouts
from .spec import (
    ATTRIBUTES,
    RULES_ROOT,
    Option,
    Recipe,
    RuleError,
    enumerate_valid,
    load_rules,
    sample_recipe,
    validate,
)
from .style import fade, hex_colour, inks

__all__ = [
    "ATTRIBUTES",
    "CORPUS_ROOT",
    "Cell",
    "Grid",
    "Item",
    "LAYOUTS_ROOT",
    "Option",
    "RULES_ROOT",
    "Receipt",
    "Recipe",
    "RuleError",
    "Store",
    "available_layouts",
    "build_grid",
    "build_receipt",
    "enumerate_valid",
    "fade",
    "hex_colour",
    "inks",
    "load_rules",
    "make",
    "sample_recipe",
    "validate",
]


def make(seed: int | None = None, force: dict[str, str] | None = None, attempts: int = 500):
    """Recipe, contents and grid in one call -- what every backend starts with.

    One `random.Random(seed)` is threaded through content and layout so a seed
    reproduces the page exactly, including which dish was picked and how wide
    the paper is.

    Pinning an attribute can clash with what an earlier attribute drew -- a
    supermarket bố cục on a seed that drew a quán nhậu. Rather than make every
    caller write the same retry, the seed is advanced until the pin fits, and
    the recipe reports the seed that actually produced it.
    """
    if not force:
        recipe = sample_recipe(seed=seed, force=force)
    else:
        start = random.randrange(2**31) if seed is None else seed
        for offset in range(attempts):
            try:
                recipe = sample_recipe(seed=start + offset, force=force)
                break
            except RuleError:
                continue
        else:
            raise RuleError(
                f"no seed within {attempts} of {start} satisfies {force}; the rules "
                f"may make that combination impossible"
            )
    rng = random.Random(recipe.seed)
    receipt = build_receipt(recipe, rng)
    grid = build_grid(receipt, recipe.layout.id, rng)
    return recipe, receipt, grid
