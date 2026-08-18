"""One rule-base, six attributes, three renderers, one hierarchy.

Everything about *what* a synthetic page contains lives here; everything about
*how it is drawn* lives in `generators/`. A backend does three things:

    recipe  = rulebase.sample_recipe(seed=n)      # draw one point in the space
    receipt = rulebase.build_receipt(recipe)      # fill the fields in
    grid    = rulebase.build_grid(receipt, recipe.layout.id)

and then renders `grid`. Because all three backends take the same grid, the
same seed gives the same words in the same columns whether it was drawn with
glyphs, with HTML in a browser, or with WeasyPrint -- which is the only way a
comparison between them means anything.

Which *kind* of document a recipe is comes from `taxonomy/`, not from here:
every value in `rules/document/` names the leaf of that tree it realises, and
`recipe.doc_type` is what ends up in the label and what a run is balanced over.

    rulebase.make(seed=n, doc_type="retail")      # pin a type from the tree
    rulebase.make(seed=n, force={"layout": ...})  # pin a rules value

Adding to the space is editing YAML: a new value in `rules/<attribute>.yaml` or
`rules/document/<family>.yaml`, a new bố cục in `layouts/`, new lines in
`corpus/vi/`. See README.md and taxonomy/README.md.
"""

from __future__ import annotations

import random

from . import documents
from .content import LABEL_SCHEMA, Item, Receipt, Store
from .content import build as build_receipt
from .corpus import CORPUS_ROOT
from .documents import NoBuilder
from .documents import build as build_document
from .layout import LAYOUTS_ROOT, Cell, Grid, build_grid
from .layout import available as available_layouts
from .spec import (
    ATTRIBUTES,
    RULES_ROOT,
    Option,
    Recipe,
    RuleError,
    attribute_order,
    enumerate_valid,
    load_rules,
    parse_force,
    reachable_options,
    resolve_doc_type,
    sample_recipe,
    validate,
    validate_doc_types,
)
from .style import fade, hex_colour, inks, padding

__all__ = [
    "ATTRIBUTES",
    "LABEL_SCHEMA",
    "attribute_order",
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
    "NoBuilder",
    "build_document",
    "build_grid",
    "build_receipt",
    "documents",
    "enumerate_valid",
    "fade",
    "hex_colour",
    "inks",
    "load_rules",
    "make",
    "padding",
    "parse_force",
    "reachable_options",
    "resolve_doc_type",
    "sample_recipe",
    "validate",
    "validate_doc_types",
]


def make(seed: int | None = None, force: dict[str, str] | None = None,
         attempts: int = 500, doc_type: str | None = None):
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

    `doc_type` asks for a document type from `taxonomy/` -- `retail`,
    `receipt.retail` or the full `business.receipt.retail` -- rather than for a
    rules value. That is what a dataset is balanced over, so it is what the
    planner and all three renderers pass down.
    """
    recipe = sample_recipe(seed=seed, force=force, attempts=attempts, doc_type=doc_type)
    rng = random.Random(recipe.seed)
    receipt = build_document(recipe, rng)
    grid = build_grid(receipt, recipe.layout.id, rng)
    return recipe, receipt, grid
