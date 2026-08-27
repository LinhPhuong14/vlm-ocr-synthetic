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

import profiling

from . import periodical
from .content import Item, Receipt, Store
from .content import build as build_receipt
from .corpus import CORPUS_ROOT
from .layout import LAYOUTS_ROOT, Cell, Grid, build_grid, item_values, load_layout
from .layout import available as available_layouts
from .layout import every as every_layout
from .spec import (
    ATTRIBUTES,
    RULES_ROOT,
    Group,
    Option,
    Recipe,
    RuleError,
    attribute_order,
    enumerate_valid,
    load_groups,
    load_rules,
    parse_force,
    sample_recipe,
    validate,
)
from .style import (
    SHEETS,
    fade,
    hex_colour,
    inks,
    padding,
    sheet_height,
    sheet_ratio,
)

__all__ = [
    "ATTRIBUTES",
    "SHEETS",
    "attribute_order",
    "CORPUS_ROOT",
    "Cell",
    "Grid",
    "Group",
    "Item",
    "LAYOUTS_ROOT",
    "Option",
    "RULES_ROOT",
    "Receipt",
    "Recipe",
    "RuleError",
    "Store",
    "available_layouts",
    "every_layout",
    "build_grid",
    "build_receipt",
    "enumerate_valid",
    "fade",
    "hex_colour",
    "inks",
    "item_values",
    "load_groups",
    "load_layout",
    "load_rules",
    "make",
    "make_content",
    "padding",
    "parse_force",
    "sample_recipe",
    "sheet_height",
    "sheet_ratio",
    "validate",
]


def make(seed: int | None = None, force: dict[str, str] | None = None, attempts: int = 500):
    """Recipe, contents and grid in one call -- what every backend starts with.

    One `random.Random(seed)` is threaded through content and layout so a seed
    reproduces the page exactly, including which dish was picked and how wide
    the paper is.

    Pinning an attribute can clash with what an earlier attribute drew -- a
    supermarket layout on a seed that drew a street eatery. `sample_recipe`
    re-draws from the same rng stream until the pin fits, so `recipe.seed` is
    always the seed that was asked for and two different seeds give two
    different recipes.

    Until W1b this walked to `seed + 1`, `seed + 2`, ... instead, which made
    `make` many-to-one: whole runs of consecutive seeds returned one recipe, and
    half of a "twenty image" dataset was duplicates. See `sample_recipe`.
    """
    recipe, receipt, rng = make_content(seed=seed, force=force, attempts=attempts)
    # A periodical page has no character-grid shape of its own (see
    # `make_content`'s docstring on why the CSS path never builds one at
    # all) -- `as_grid_receipt()` stands in a minimal, valid `Receipt` so
    # `build_grid` has something to draw, purely for `tests/test_layout.py`
    # and `pipeline/preflight.py::sheet_overflow()`, which call `make()` on
    # every layout unconditionally. Neither ever reads `.ground_truth()` off
    # what they build here, so the shim is never checked against a label --
    # only the real `receipt` is returned below.
    grid_source = receipt if isinstance(receipt, Receipt) else receipt.as_grid_receipt()
    with profiling.stage("layout"):
        grid = build_grid(grid_source, recipe.layout.id, rng)
    return recipe, receipt, grid


def make_content(seed: int | None = None, force: dict[str, str] | None = None,
                 attempts: int = 500):
    """Recipe and contents, with no character grid laid over them.

    `(recipe, receipt, rng)` -- the rng too, so a caller that does want a grid
    can build one on the same stream and get the page `make` would have given.

    This exists because `build_grid` does not only read the `Receipt`: a value
    too wide for its character column is cut to fit and the cut is **written
    back**, so `ground_truth()` describes what was drawn rather than what was
    sampled (`_emit_vat_summary` in `layout.py` says why). That is right for a
    page made of character cells and wrong for one made of CSS: the sheets in
    `generators/html/sheets/` have no character columns, so a sheet built after
    a grid would print "Hàng hoá không chịu thuế GTG" on a line with room for
    the whole label. The CSS backends take this entry point instead.
    """
    with profiling.stage("sampling"):
        recipe = sample_recipe(seed=seed, force=force, attempts=attempts)
    rng = random.Random(recipe.seed)
    with profiling.stage("content"):
        # `kind: periodical` is an opaque params flag, read the same
        # ungoverned way every other document param already is (`spec.py`
        # never schema-checks `params`) -- set on the four periodical
        # documents in rulebase/documents/, nowhere else. A newspaper page
        # has no store/items/totals/invoice-parties shape at all, so it gets
        # its own builder (`rulebase.periodical`) rather than a stretched
        # corner of `Receipt`/`Invoice`. See rulebase/periodical.py's module
        # docstring for why this is a sibling, not a subclass.
        document = recipe.choices["document"].params
        if document.get("kind") == "periodical":
            receipt = periodical.build(recipe, rng)
        else:
            receipt = build_receipt(recipe, rng)
    return recipe, receipt, rng
