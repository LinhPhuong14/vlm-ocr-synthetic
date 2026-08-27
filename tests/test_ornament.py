"""The seal, the watermark and the QR: where they land, and what they may not do.

`generators/html/ornament.py` is the half of the `ornament` attribute that was
missing for the repository's whole life -- 21 values, 27 PNGs, a preflight check
in both directions, and no renderer that printed any of it. These are the rules
that half has to keep.

No browser here: `stamp` needs an image and boxes, and both can be made. What
cannot be made without Chromium -- that a real page's `sign.` boxes are where
the signature block is -- is what `tests/test_sheets.py` already covers.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

import ornament  # noqa: E402

WIDTH, HEIGHT = 1000, 1400


def box(kind: str, x0: float, y0: float, x1: float, y1: float) -> dict:
    return {"kind": kind, "text": "x",
            "quad": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}


PAGE = [
    box("store.name", 60, 40, 500, 80),
    box("store.address", 60, 90, 520, 120),
    box("menu.name", 60, 300, 400, 330),
    box("total.grand", 600, 700, 900, 730),
    box("sign.title", 100, 1100, 300, 1130),      # người mua, left
    box("sign.name", 100, 1180, 300, 1210),
    box("sign.title", 620, 1100, 880, 1130),      # người bán, right
    box("sign.name", 620, 1180, 880, 1210),
    box("footer", 60, 1320, 900, 1350),
]


# ---------------------------------------------------------------- anchors


def test_a_seal_lands_on_the_sellers_signature_block_not_the_buyers():
    """Người mua bên trái, người bán bên phải, and the seal is the seller's."""
    x0, _y0, x1, _y1, how = ornament.anchor("signature_seller", PAGE, WIDTH, HEIGHT)

    assert how == "boxes"
    assert x0 >= 600, "the seal went to the buyer's column"
    assert x1 <= 900


def test_one_signature_block_is_the_sellers_by_default():
    """A form with a single block still gets its seal on it."""
    only = [b for b in PAGE if b["kind"].startswith("sign.") and b["quad"][0][0] < 400]
    x0, _y0, x1, _y1, how = ornament.anchor("signature_seller", only, WIDTH, HEIGHT)

    assert how == "boxes"
    assert (x0, x1) == (100, 300)


def test_each_anchor_reads_the_blocks_it_names():
    assert ornament.anchor("letterhead", PAGE, WIDTH, HEIGHT)[:2] == (60, 40)
    assert ornament.anchor("footer_band", PAGE, WIDTH, HEIGHT)[1] == 1320
    assert ornament.anchor("totals", PAGE, WIDTH, HEIGHT)[0] == 600
    assert ornament.anchor("table_back", PAGE, WIDTH, HEIGHT)[0] == 60


def test_a_page_with_no_such_block_falls_back_and_says_so():
    """A till roll has no signature block. The seal still goes somewhere a seal
    belongs, and the page records that the place was a guess."""
    till = [box("menu.name", 20, 200, 300, 230)]
    x0, y0, x1, y1, how = ornament.anchor("signature_seller", till, WIDTH, HEIGHT)

    assert how == "fallback"
    assert (x0, x1) == (0.55 * WIDTH, 0.95 * WIDTH)
    assert y0 > HEIGHT / 2, "the fallback for a signature is the foot of the page"
    assert y1 <= HEIGHT


def test_a_geometric_anchor_never_reads_the_boxes():
    """A ribbon across the top is a place on the paper, not a block."""
    for name in ("header_band", "page_full", "corner_tr", "page_edge_left"):
        assert ornament.anchor(name, PAGE, WIDTH, HEIGHT)[4] == "fallback"


def test_page_full_is_the_whole_sheet():
    assert ornament.anchor("page_full", PAGE, WIDTH, HEIGHT)[:4] == (0, 0, WIDTH, HEIGHT)


# ------------------------------------------------------------------ rules


def test_every_anchor_the_shipped_rules_name_is_one_this_file_resolves():
    """The check preflight runs, run here too where it names the file.

    An unknown anchor does not fail a render -- the mark lands in the middle of
    the page, which looks like a decision -- so nothing downstream would catch
    it.
    """
    assert ornament.problems() == []


def test_an_unknown_anchor_is_reported_rather_than_quietly_centred():
    class FakeOption:
        id = "invented"
        params = {"marks": [["seal_round_company", {"anchor": "on_the_dog"}]]}

    problems = ornament.problems({"ornament": [FakeOption()]})
    assert len(problems) == 1
    assert "on_the_dog" in problems[0]


def test_the_renderer_actually_calls_this_file():
    """A source-level check, and the only kind that can catch this defect.

    The bug being prevented is not "the stamp is wrong" -- it is "nothing
    stamps", which is what was true here for the repository's whole life. Every
    unit test in this file passed against a renderer that never called `stamp`,
    because they call it themselves; and the checks that could have noticed --
    preflight's two-way asset audit, `rules_report --check` -- were all looking
    at whether the rules and the FILES agree, never at whether a page got one.

    Reading the renderer's source is crude. It is also the cheapest thing that
    fails when somebody removes the call, and the dependency-free CI job cannot
    start Chromium to check the pixels instead.
    """
    source = (REPO_ROOT / "generators" / "html" / "render.py").read_text(encoding="utf-8")
    assert "import ornament" in source
    assert "ornament.stamp(" in source, (
        "the html renderer no longer strikes the ornament; the attribute would "
        "be recorded on every page and printed on none")


def test_a_range_in_the_rules_becomes_one_number_inside_it():
    """`opacity: [0.72, 0.9]` is a statement about variety, made by the rules."""
    import random

    rng = random.Random(1)
    for _ in range(20):
        assert 0.72 <= ornament._number([0.72, 0.9], rng, 0.5) <= 0.9
    assert ornament._number(0.4, rng, 0.5) == 0.4
    assert ornament._number(None, rng, 0.5) == 0.5


# ----------------------------------------------------------------- stamping


@pytest.fixture
def drawn():
    """A recipe that draws a seal, and a blank page to strike it on."""
    np = pytest.importorskip("numpy")
    pytest.importorskip("cv2")
    import rulebase

    recipe, _receipt, _grid = rulebase.make(seed=4242, force={"ornament": "seller_seal"})
    page = np.full((HEIGHT, WIDTH, 3), 255, dtype=np.uint8)
    return recipe, page


def test_a_struck_page_is_darker_where_the_seal_is_and_the_same_size(drawn):
    recipe, page = drawn
    out, report = ornament.stamp(page, recipe, PAGE, seed=7)

    assert out.shape == page.shape, (
        "the boxes were measured before this and still describe the image")
    assert report["ornament"] == "seller_seal"
    assert [mark["pattern"] for mark in report["marks"]] == ["seal_round_company"]
    assert out.mean() < page.mean(), "nothing was struck onto the page"


def test_the_seal_does_not_replace_what_is_under_it(drawn):
    """Multiply, not paint over. A label claiming text under an opaque seal is
    exactly the mismatch `pipeline/invariants.py` exists to stop."""
    np = pytest.importorskip("numpy")
    recipe, page = drawn
    page = page.copy()
    page[1150:1160, 700:760] = 0            # a line of "text" under the seal
    out, _report = ornament.stamp(page, recipe, PAGE, seed=7)

    assert np.array_equal(out[1150:1160, 700:760], np.zeros((10, 60, 3), np.uint8))


def test_the_mark_adds_no_box_to_the_label(drawn):
    recipe, page = drawn
    before = [dict(b) for b in PAGE]
    ornament.stamp(page, recipe, PAGE, seed=7)

    assert PAGE == before, "stamping changed the label"


def test_no_ornament_draws_nothing_and_still_reports(drawn):
    import rulebase

    _recipe, page = drawn
    bare, _receipt, _grid = rulebase.make(seed=11, force={"ornament": "no_ornament"})
    out, report = ornament.stamp(page, bare, PAGE, seed=7)

    assert out is page
    assert report["marks"] == []
    assert report["ornament"] == "no_ornament"


def test_the_same_seed_strikes_the_same_page(drawn):
    np = pytest.importorskip("numpy")
    recipe, page = drawn
    once, _ = ornament.stamp(page.copy(), recipe, PAGE, seed=7)
    twice, _ = ornament.stamp(page.copy(), recipe, PAGE, seed=7)
    other, _ = ornament.stamp(page.copy(), recipe, PAGE, seed=8)

    assert np.array_equal(once, twice)
    # The rules give the seal a rotation range, so another seed is another
    # strike. If this ever ties, the range collapsed.
    assert not np.array_equal(once, other)
