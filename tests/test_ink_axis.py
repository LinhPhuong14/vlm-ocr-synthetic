"""Axis 3 — how the mark got onto the paper.

`agent/prompts/regions.md` defines three axes for every run on a page: it IS a
region (axis 1), it DOES a role (axis 2), and it was PUT THERE somehow (axis
3). The record carried the first two -- `layout_class` and `field_role` -- and
not the third, so a reader could tell a heading from a table cell and a key
from a value, and could not tell printed text from a stamp impression or from
something a person wrote by hand.

That distinction is the entire reason `generators/html/handwriting.py` and
`generators/html/signature.py` exist, and it was reaching the dataset only as
pixels.

Six values, and they are known in three different places, which is why the
answer is assembled rather than looked up:

* **the renderer** knows `hand`, `stamp` and `reversed` -- all three are
  decided while drawing and leave no trace in `kind`. It says so with
  `data-ink` on the span;
* **the kind** knows `stamp` on its own (`seal.` is always an impression),
  which is the belt to that braces;
* **the recipe** knows `thermal` and `dotmatrix`, because those are properties
  of the whole sheet rather than of one run -- a thermal roll prints every run
  thermally.

`print` is what is left, and it is most of every page.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from pipeline import record  # noqa: E402


def _box(kind: str, ink: str = "", text: str = "x"):
    return {"kind": kind, "ink": ink, "text": text,
            "quad": [[0, 0], [10, 0], [10, 10], [0, 10]]}


# --------------------------------------------------------------- the vocabulary


def test_the_six_values_are_the_ones_the_axis_document_defines():
    """Fixed by what reads these records, the same way `DOCSYNTH_LABELS` is."""
    assert record.INK_VALUES == {"print", "hand", "stamp", "dotmatrix",
                                 "thermal", "reversed"}


def test_the_axis_document_and_the_code_name_the_same_six():
    """`agent/prompts/regions.md` is what a labelling model is handed. Two
    lists of six that drift apart is a model told one vocabulary and judged
    against another."""
    text = (REPO_ROOT / "agent" / "prompts" / "regions.md").read_text(encoding="utf-8")
    section = text.split("## Ink")[1].split("##")[0]
    for value in record.INK_VALUES:
        assert f"`{value}`" in section, value


# ------------------------------------------------------------- what decides it


def test_the_renderer_wins_because_it_is_the_only_one_that_can_know():
    """`hand` and `reversed` are invisible to `kind` and to the recipe: a
    hand-filled `store.name` and a printed one are the same field."""
    assert record.ink_for("store.name", "hand", "thermal") == "hand"
    assert record.ink_for("colhdr", "reversed", "print") == "reversed"


def test_a_seal_is_a_stamp_even_on_a_page_that_says_nothing():
    """The belt to the renderer's braces: a set drawn before `data-ink`
    existed still classifies its seals correctly."""
    assert record.ink_for("seal.round_company", "", "print") == "stamp"
    assert record.ink_for("seal.round_company", "", "thermal") == "stamp"


def test_the_page_default_covers_everything_else():
    assert record.ink_for("store.name", "", "thermal") == "thermal"
    assert record.ink_for("total.grand", "", "dotmatrix") == "dotmatrix"
    assert record.ink_for("store.name", "", "print") == "print"


def test_a_value_outside_the_vocabulary_is_dropped_not_trusted():
    """The set is closed. A typo in a family module must not put a seventh ink
    in a dataset a consumer has six classes for."""
    assert record.ink_for("store.name", "crayon", "print") == "print"
    assert record.ink_for("store.name", "", "crayon") == "print"


# ------------------------------------------------------------- the page default


def test_the_page_ink_is_read_off_tags_the_recipe_already_carries():
    """Not a new attribute: `thermal` and `impact` are decided by
    `document`/`visual`, and both already tag themselves. Measured over 300
    draws: `thermal` on 54, `impact` on 97 -- so neither branch is dead."""
    from render import page_ink

    class _Recipe:
        def __init__(self, *tags):
            self.tags = frozenset(tags)

    assert page_ink(_Recipe("thermal", "till_receipt")) == "thermal"
    assert page_ink(_Recipe("impact")) == "dotmatrix"
    assert page_ink(_Recipe("doc_invoice", "a4")) == "print"
    # A roll that is both is thermal: the paper decides before the print head.
    assert page_ink(_Recipe("thermal", "impact")) == "thermal"


def test_both_tags_are_ones_the_shipped_rules_actually_draw():
    """A mapping onto a tag no recipe carries is dead code that looks alive."""
    from rulebase import sample_recipe
    from render import INK_BY_TAG

    seen: set[str] = set()
    for seed in range(120):
        try:
            seen |= set(sample_recipe(seed=seed).tags)
        except Exception:                      # noqa: BLE001 -- a refused draw
            continue
    for tag, _ink in INK_BY_TAG:
        assert tag in seen, f"no recipe carries {tag!r}"


# ------------------------------------------------------------------ the record


def test_every_word_carries_an_ink():
    words = record.words_from_boxes(
        [_box("store.name"), _box("seal.round", ""), _box("sign.name", "hand")],
        "thermal")
    assert [w["ink"] for w in words] == ["thermal", "stamp", "hand"]


def test_the_record_refuses_a_word_with_no_ink():
    """A key nothing requires is a key that silently goes missing -- which is
    the failure this whole axis was added after."""
    built = record.build(filename="x.jpg", width=600, height=800, parser="html",
                         boxes=[], words=[_box("store.name")], ink="print")
    del built["word_annotations"][0]["ink"]
    assert any("ink" in problem for problem in record.validate(built))


def test_the_record_refuses_an_ink_outside_the_vocabulary():
    built = record.build(filename="x.jpg", width=600, height=800, parser="html",
                         boxes=[], words=[_box("store.name")], ink="print")
    built["word_annotations"][0]["ink"] = "crayon"
    assert any("ink must be one of" in problem for problem in record.validate(built))


def test_a_record_built_with_no_ink_argument_is_still_valid():
    """Additive: every existing caller keeps working and gets `print`."""
    built = record.build(filename="x.jpg", width=600, height=800, parser="html",
                         boxes=[], words=[_box("store.name")],
                         extracted={"store": {"name": "x"}})
    assert built["word_annotations"][0]["ink"] == "print"
    assert record.validate(built) == []


# ----------------------------------------------------- what the renderer marks


@pytest.mark.parametrize("source,marker", [
    ("generators/html/sheets/base.py", 'data-ink="stamp"'),
    ("generators/html/handwriting.py", 'data-ink="hand"'),
])
def test_the_renderer_says_so_where_only_it_can_know(source, marker):
    assert marker in (REPO_ROOT / source).read_text(encoding="utf-8"), source


def test_the_measurement_reads_the_nearest_marked_ancestor():
    """`closest`, not the span's own dataset: a family marks a whole reversed
    BAND once rather than every run inside it, and a hand-filled field wraps
    its ink in an element of its own."""
    page = (REPO_ROOT / "generators" / "html" / "page.py").read_text(encoding="utf-8")
    assert "closest('[data-ink]')" in page
