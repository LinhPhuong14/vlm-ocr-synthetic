"""Which code fills in which document type.

    from rulebase import documents
    document = documents.build(recipe, rng)      # a Receipt today
    documents.covered()                          # {'business.receipt.retail', ...}

One registry, keyed by node id from `taxonomy/`. A builder claims a node and
everything under it, so `@register("business.receipt")` covers all four kinds of
receipt, and a later `@register("business.receipt.atm")` takes the ATM slip back
without disturbing the other three. Longest claim wins.

**Why a registry and not an `if`.** The hierarchy has ninety-eight types in it.
A dispatch table that lives in one function is a merge conflict every time two
people add a family, and -- worse -- it makes "which types can this repository
actually produce" a question you answer by reading code. Here it is a set, so
`make taxonomy` can print it, `make check-rules` can cross-check it against the
`ready` flags in the tree, and a type nobody has built fails with a sentence
that says what is missing rather than with a `KeyError`.

**What a builder owes its caller.** An object the renderers can use: it must
carry `ground_truth()` and `text_sequence()`, and `rulebase.layout` must know
how to turn it into a grid. Today that means a `Receipt`, and `layout.py` is
still written against a receipt's parts -- header, meta pairs, item rows,
totals, footer. Those parts generalise (a prescription is a header, meta pairs,
drug rows and a signature), but the generalisation has not been done, so the
second grid-engine document is the one that will do it. That is a known,
sized piece of work rather than a surprise: see taxonomy/README.md.
"""

from __future__ import annotations

import random
from typing import Any, Callable

from .content import Receipt
from .content import build as build_receipt

# node id -> builder. Insertion order is irrelevant; lookup is longest-prefix.
BUILDERS: dict[str, Callable[[Any, random.Random], Any]] = {}


class NoBuilder(LookupError):
    """The hierarchy names this type, and nothing here can produce it."""


def register(*node_ids: str) -> Callable:
    """Claim one or more nodes of the hierarchy for a builder function."""

    def decorate(function: Callable[[Any, random.Random], Any]):
        import taxonomy

        tree = taxonomy.tree()
        for node_id in node_ids:
            node = tree.node(node_id)          # raises on a name that is not in the tree
            if node.id in BUILDERS:
                raise ValueError(
                    f"{node.id} is already built by {BUILDERS[node.id].__name__}; "
                    f"a node has one builder"
                )
            BUILDERS[node.id] = function
        return function

    return decorate


def builder_for(doc_type: str) -> Callable[[Any, random.Random], Any]:
    """The builder that claims `doc_type`, or the nearest ancestor that does."""
    parts = str(doc_type).split(".")
    for cut in range(len(parts), 0, -1):
        claim = ".".join(parts[:cut])
        if claim in BUILDERS:
            return BUILDERS[claim]
    raise NoBuilder(_missing(doc_type))


def _missing(doc_type: str) -> str:
    """Why this type cannot be built, in the terms someone would fix it in."""
    import taxonomy

    tree = taxonomy.tree()
    if doc_type not in tree:
        return (
            f"{doc_type!r} is not a document type in taxonomy/; "
            f"nothing can build it because nothing declares it"
        )
    node = tree.node(doc_type)
    engine = tree.engines[node.engine]
    built = " (built)" if engine.get("built") else " -- which does not exist yet"
    return (
        f"no builder for {node.id} ({' / '.join(node.names)}). It is marked "
        f"{node.status} and needs the {node.engine!r} engine{built}. "
        f"Register one with @rulebase.documents.register({node.id!r}); "
        f"taxonomy/README.md has the five steps"
    )


def build(recipe, rng: random.Random | None = None):
    """Fill in the contents of whatever document `recipe` describes."""
    rng = rng or random.Random(recipe.seed)
    return builder_for(recipe.doc_type)(recipe, rng)


def covered() -> set[str]:
    """Every leaf a builder can produce -- the claims expanded over the tree.

    The counterpart to the `ready` flag in `taxonomy/`: that field is a claim
    about the repository, this set is the fact. `make check-rules` compares them.
    """
    import taxonomy

    tree = taxonomy.tree()
    found: set[str] = set()
    for claim in BUILDERS:
        found.update(node.id for node in tree.leaves(under=claim))
    return found


def coverage(rules: dict | None = None) -> dict[str, dict[str, Any]]:
    """Per leaf: what the tree claims, and what the repository can actually do.

    Three independent facts have to line up before an image of a given type can
    exist, and each is stored in a different place on purpose:

        declared   `status:` in taxonomy/families/  -- the claim
        rules      a value in rules/ naming it      -- something to draw
        builder    a function registered here       -- something to fill in

    A type is generatable when the last two are both true. The first is
    editorial, and the point of returning all three side by side is that a
    disagreement between them is visible: `ready` with no builder is a lie about
    the repository, and a builder with no rules is code nothing reaches. Both
    show up in `make taxonomy` and in `make check-rules`.
    """
    import taxonomy

    from .spec import load_rules

    rules = rules if rules is not None else load_rules()
    tree = taxonomy.tree()
    with_rules = {
        option.doc_type
        for options in rules.values() for option in options
        if option.doc_type and option.weight > 0
    }
    built = covered()

    report: dict[str, dict[str, Any]] = {}
    for node in tree.leaves():
        has_rules = node.id in with_rules
        has_builder = node.id in built
        report[node.id] = {
            "declared": node.status,
            "engine": node.engine,
            "rules": has_rules,
            "builder": has_builder,
            "generatable": has_rules and has_builder,
        }
    return report


@register("business.receipt")
def receipt(recipe, rng: random.Random) -> Receipt:
    """Vietnamese tills: supermarket, convenience store, eatery, restaurant.

    Claims the whole `receipt` branch rather than the two leaves it really
    covers, so that adding `business.receipt.payment` is a rules edit plus a
    corpus, not a Python edit -- the fields are the same shape. `payment` and
    `atm` stay `planned` in the tree until they have rules of their own, and
    `make taxonomy` is what reports the gap.
    """
    return build_receipt(recipe, rng)


__all__ = ["BUILDERS", "NoBuilder", "build", "builder_for", "coverage", "covered",
           "register"]
