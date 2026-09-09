"""The `ornament` attribute has to reach the paper, in every family.

It did not. `base.render_ornament_marks()` shipped alongside `lodging.py` and
**only `lodging.py` ever called it**, so nine of the ten sheet families sampled
an `ornament` value, wrote it into `synthesis.json` and `agent_plan.json`, and
put no ink on the page. Measured before the fix: the same seed with
`ornament=no_ornament` and with `ornament=seal_with_name_block` produced two
byte-identical JPEGs.

That is the failure mode this repository is built to refuse -- a label
promising something the paper does not carry -- and nothing caught it, because
every existing test asks whether a page draws, not whether an attribute
CHANGES what it draws. This file asks the second question, per family, and it
is the reason a tenth family can no longer be added without one.

No browser here: an ornament is markup by the time `sheets.build()` returns, so
comparing two builds of the same recipe is enough and costs milliseconds.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def _families() -> dict[str, str]:
    """One committed layout per sheet family, so every family is exercised.

    Read off the layouts rather than listed: a family added tomorrow brings its
    own layouts with it and lands in this test without anybody remembering to
    add it -- which is exactly the kind of remembering that produced the bug.
    """
    import yaml

    picked: dict[str, str] = {}
    for path in sorted((REPO_ROOT / "rulebase" / "layouts").glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        family = str(spec.get("family", "") or "")
        if family and family not in picked:
            picked[family] = path.stem
    return picked


FAMILIES = _families()


def _marks_of(option_id: str) -> list:
    import yaml

    rules = yaml.safe_load(
        (REPO_ROOT / "rulebase" / "rules" / "ornament.yaml").read_text(encoding="utf-8"))
    options = rules.get("options") or [o for g in (rules.get("groups") or [])
                                       for o in g.get("options", [])]
    entry = next(o for o in options if o["id"] == option_id)
    return (entry.get("params") or {}).get("marks") or []


def _build(layout_id: str, marks: list) -> str:
    """The page markup for `layout_id` with `marks` as its ornament.

    The marks are pushed onto the recipe directly rather than drawn through
    the sampler: an option's `requires`/`excludes` decide WHICH document may
    wear it, and this test is about whether a family DRAWS what it was handed,
    which is a different question and one every family must answer yes to.
    """
    import dataclasses

    import rulebase
    import sheets
    from rulebase.spec import Option

    recipe, receipt, _grid = rulebase.make(seed=7, force={"layout": layout_id})
    # `Recipe` is frozen and reads an attribute's settings through
    # `recipe.get(attribute, key)`, so the ornament is swapped by replacing the
    # whole `Option` rather than by poking at a dict. Same shape the sampler
    # would have produced, which is the point: the family must not be able to
    # tell this apart from a real draw.
    chosen = recipe.choices.get("ornament")
    params = {**(chosen.params if chosen else {}), "marks": marks}
    option = (dataclasses.replace(chosen, params=params) if chosen else
              Option(id="test_marks", attribute="ornament", weight=1.0,
                     params=params))
    return sheets.build(dataclasses.replace(
        recipe, choices={**recipe.choices, "ornament": option}), receipt)


@pytest.mark.parametrize("family,layout_id", sorted(FAMILIES.items()))
def test_every_family_draws_a_page_anchored_seal(family, layout_id):
    """21 of the 31 marks the rules define are page-anchored, and those need no
    hook inside a family's own DOM -- `sheets/__init__.py::_page_ornaments`
    strikes them for all ten at once."""
    plain = _build(layout_id, [])
    stamped = _build(layout_id, _marks_of("copy_stamp"))
    assert stamped != plain, (
        f"{family} ({layout_id}) draws the same page with and without a "
        f"page-anchored seal -- the ornament attribute is recorded in the "
        f"label and absent from the paper")
    assert 'data-kind="seal.' in stamped, family


@pytest.mark.parametrize("family,layout_id", sorted(FAMILIES.items()))
def test_a_family_with_a_signature_block_draws_the_seller_seal(family, layout_id):
    """The other 10 marks are `signature_seller`/`signature_buyer`/`totals`,
    which DO need the block. A family whose layout draws no signatures has
    nowhere to put one and is skipped rather than failed -- a till roll has no
    signature column, and inventing one to satisfy a test would be the test
    changing the paper."""
    plain = _build(layout_id, [])
    # `class="signs"`, not `"signs"`: every family's stylesheet carries a
    # `.signs{...}` rule whether or not the page draws the block, and matching
    # the bare word skipped nothing and failed on the CSS instead.
    if 'class="signs"' not in plain:
        pytest.skip(f"{family} draws no signature block on {layout_id}")
    stamped = _build(layout_id, _marks_of("seller_seal"))
    assert stamped != plain, (
        f"{family} ({layout_id}) ignores a signature-anchored seal")


def test_the_seal_is_positioned_inside_the_column_it_was_anchored_to():
    """`seal_mark` places a slot seal with `position:absolute;top:0;left:50%`,
    which resolves against the nearest POSITIONED ancestor. A family whose
    `.sign` was static sent it to `#sheet`'s own top-centre instead -- straight
    across the letterhead, which is a `che_box` finding rather than a seal.
    So `signature_block` sets the containing block itself, inline, rather than
    leaving it to ten stylesheets that each have to remember."""
    from sheets import base

    class _Invoice:
        signatures = [("Người mua hàng", "(Ký)"), ("Người bán hàng", "(Ký)")]

    class _Receipt:
        invoice = _Invoice()

    block = base.signature_block(_Receipt(), {}, stamp="<img id=seal>")
    assert 'class="sign" style="position:relative;"' in block
    # ...and the stamp lands in the last column, which is where the issuer signs.
    assert block.rindex("<img id=seal>") > block.rindex("Người bán hàng")


def test_no_mark_is_drawn_twice():
    """The overlay is struck centrally and the slots per family. Both halves
    call the same pure function of `(recipe, receipt)`, and each must take only
    its own half -- a family that also took the overlay would draw those marks
    on top of the central ones."""
    layout_id = FAMILIES.get("modern") or next(iter(FAMILIES.values()))
    marks = _marks_of("copy_stamp")          # one mark, `page_center`
    assert len(marks) == 1
    markup = _build(layout_id, marks)
    assert markup.count('data-kind="seal.') == 1, "the page-centre seal is doubled"
