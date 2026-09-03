"""Shared fixtures.

The rule these tests follow: anything testing a *mechanism* builds its own
options; only tests about the shipped rule-base read `rulebase/rules/`. Testing
`requires`/`excludes` against the real files would tie the suite to editorial
decisions -- someone re-weights a YAML and a test about constraint logic goes
red for no reason.

The synthetic rule-bases reuse the six real attribute *names* while inventing
every option. The names are not the thing under test; the options are. Reusing
them also means these tests neither depend on nor block the move to
auto-discovered attributes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def build_rules(spec: dict[str, list[dict]]):
    """`{attribute: [raw option, ...]}` -> what `sample_recipe(rules=...)` wants."""
    from rulebase.spec import Option

    return {
        attribute: [Option.from_dict(raw, attribute) for raw in options]
        for attribute, options in spec.items()
    }


def write_rules_dir(root: Path, spec: dict[str, list[dict]], order=None) -> Path:
    """Write a rules directory on disk, `_order.yaml` included."""
    root.mkdir(parents=True, exist_ok=True)
    for attribute, options in spec.items():
        (root / f"{attribute}.yaml").write_text(
            yaml.safe_dump({"options": options}, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
    order = list(spec) if order is None else list(order)
    (root / "_order.yaml").write_text(
        yaml.safe_dump({"order": order}, allow_unicode=True), encoding="utf-8"
    )
    return root


# One drawable option per attribute, so a recipe always completes. `document`
# and `layout` carry the constraint under test; the rest are inert padding.
FILLER = {
    "content": [{"id": "c1", "weight": 1}],
    "visual": [{"id": "v1", "weight": 1}],
    "color": [{"id": "k1", "weight": 1}],
    "augmentation": [{"id": "a1", "weight": 1}],
}


@pytest.fixture
def constraint_spec() -> dict[str, list[dict]]:
    """A rule-base whose constraints have known, checkable consequences.

    `layout/needs_x` is drawable only after `document/sets_x`; `layout/hates_x`
    only when that tag is absent. Between them exactly one is legal whichever
    way `document` falls, so a mis-implemented constraint cannot pass by luck.
    """
    return {
        "document": [
            {"id": "sets_x", "weight": 1, "tags": ["x"]},
            {"id": "sets_y", "weight": 1, "tags": ["y"]},
        ],
        "layout": [
            {"id": "needs_x", "weight": 1, "requires": ["x"]},
            {"id": "hates_x", "weight": 1, "excludes": ["x"]},
        ],
        **FILLER,
    }


@pytest.fixture
def constraint_rules(constraint_spec):
    return build_rules(constraint_spec)


@pytest.fixture
def real_rules():
    from rulebase.spec import load_rules

    return load_rules()


def force_for(layout_id: str) -> dict[str, str]:
    """The `force` that draws this layout, switched off or not.

    A layout with `enabled: false` is never drawn by chance and its DOCUMENT is
    switched off with it -- eight `doc_form` documents went with the ten root-3
    layouts, because a document whose every layout is off cannot be drawn at
    all. So pinning such a layout alone leaves the sampler with no document
    that produces the tag it requires, and it clashes on every seed.

    Pinning both is what a redraw does anyway: `tools/check_boxes.py` forces
    every attribute off the committed record, which is why a page drawn before
    the switch is still reproducible. This helper is that, for the tests that
    walk every layout file rather than every drawable one.
    """
    from rulebase.spec import load_rules

    rules = load_rules()
    option = next(o for o in rules["layout"] if o.id == layout_id)
    if option.enabled:
        return {"layout": layout_id}
    document = next(d for d in rules["document"] if option.requires <= d.tags)
    return {"document": document.id, "layout": layout_id}
