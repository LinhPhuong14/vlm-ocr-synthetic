"""Which boxes a `by_box` chain picks, and why that is a data question.

`degradation/regions.py` has two halves. The lower half draws -- masks, blends,
detects ink -- and needs numpy and OpenCV. The upper half decides **which of a
page's label boxes an effect gets to touch**, and that answer does not depend
on a single pixel: it depends on the boxes' coordinates, their roles, and the
policy the chain asked for.

So these tests run in the plain suite environment, alongside the rule-base
tests, rather than in a renderer virtualenv. The module is loaded by path
because importing `degradation.regions` the normal way runs
`degradation/__init__.py`, which pulls in the whole registry and with it numpy.

What is under test is the *shape* of a selection. A dead printer pin does not
hit a random 30% of the boxes -- it hits a horizontal band, every box that band
crosses, and nothing else. A highlighter does not skip lines. Getting those
shapes right is the difference between damage that reads as real and damage
that reads as `random.sample`.
"""

from __future__ import annotations

import importlib.util
import random
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location(
        "degradation_regions", REPO_ROOT / "degradation" / "regions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


regions = _load()


def box(x0, y0, x1, y1, kind="menu.nm"):
    return {"kind": kind, "text": "x",
            "quad": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}


def receipt():
    """Twelve lines of two columns, plus a totals row -- a page in miniature."""
    out = [box(40, 10, 300, 26, "store.name")]
    for index in range(12):
        top = 50 + index * 30
        out.append(box(40, top, 260, top + 16, "menu.nm"))
        out.append(box(400, top, 520, top + 16, "menu.price"))
    out.append(box(40, 420, 200, 440, "total.grand"))
    out.append(box(400, 420, 520, 440, "total.line"))
    return out


# ------------------------------------------------------------ reading boxes


def test_normalise_reads_every_box_shape_the_repo_produces():
    """Quads, browser rects, bare tuples and lists of corners are all boxes."""
    mixed = [
        {"kind": "a", "quad": [[0, 0], [10, 0], [10, 8], [0, 8]]},
        {"kind": "b", "x": 5, "y": 5, "w": 20, "h": 10},
        (0, 30, 40, 44),
        [[1, 60], [9, 60], [9, 70], [1, 70]],
    ]
    got = regions.normalise_boxes(mixed)
    assert [rect for rect, _ in got] == [
        (0.0, 0.0, 10.0, 8.0), (5.0, 5.0, 25.0, 15.0),
        (0.0, 30.0, 40.0, 44.0), (1.0, 60.0, 9.0, 70.0)]
    assert [kind for _, kind in got] == ["a", "b", "", ""]


def test_normalise_drops_boxes_with_no_area():
    """A separator rule is a line, not a field. Padding one bloats the mask."""
    assert regions.normalise_boxes([box(0, 0, 200, 0), box(10, 10, 10, 40)]) == []


def test_normalise_survives_junk_instead_of_guessing():
    assert regions.normalise_boxes([None, 7, {}, {"kind": "x"}, []]) == []
    assert regions.normalise_boxes(None) == []


def test_reading_order_groups_a_line_by_its_centre_not_its_top():
    """Two cells of one row rarely share a `y0` -- different type sizes do that.

    Sorting on `y0` chops one row into two, and then `run` picks half a line.
    """
    boxes = [box(400, 12, 520, 26), box(40, 8, 260, 30)]     # right cell smaller
    order = regions._reading_order(regions.normalise_boxes(boxes))
    assert order == [1, 0]                                   # same line, left first


# ------------------------------------------------------------------ policies


@pytest.mark.parametrize("policy", sorted(regions.POLICIES))
def test_every_policy_returns_a_subset_of_the_page(policy):
    boxes = receipt()
    picked = regions.select_regions(boxes, (500, 600), policy=policy,
                                    rng=random.Random(4), kinds=["menu"])
    known = {rect for rect, _ in regions.normalise_boxes(boxes)}
    assert set(picked) <= known


def test_run_picks_consecutive_lines():
    """A highlighter swipe covers lines in a row. Three every-other lines is
    not a swipe, it is `random.sample` wearing one."""
    boxes = receipt()
    picked = regions.select_regions(boxes, (500, 600), policy="run", length=6,
                                    rng=random.Random(1), kinds=["menu"])
    order = regions._reading_order(regions.normalise_boxes(boxes))
    rects = [regions.normalise_boxes(boxes)[i][0] for i in order]
    positions = sorted(rects.index(rect) for rect in picked)
    assert len(positions) == 6
    assert positions == list(range(positions[0], positions[0] + 6))


def test_band_takes_every_box_it_crosses_and_stops_there():
    """A dead pin cuts a stripe across the sheet: the stripe decides, not a die."""
    boxes = receipt()
    picked = regions.select_regions(boxes, (500, 600), policy="band",
                                    thickness=0.05, count=1, rng=random.Random(2))
    assert picked, "a band across a full page should cross something"
    tops = [rect[1] for rect in picked]
    spread = max(rect[3] for rect in picked) - min(tops)
    assert spread <= 0.05 * 500 + 40          # one stripe, not a scatter
    # Boxes sharing a line come as a set: a stripe cannot cut between columns.
    for rect in picked:
        siblings = [r for r, _ in regions.normalise_boxes(boxes) if r[1] == rect[1]]
        assert all(sibling in picked for sibling in siblings)


def test_column_is_the_same_idea_turned_ninety_degrees():
    boxes = receipt()
    picked = regions.select_regions(boxes, (500, 600), policy="column",
                                    thickness=0.15, count=1, rng=random.Random(6))
    if picked:
        spread = max(r[2] for r in picked) - min(r[0] for r in picked)
        assert spread <= 0.15 * 600 + 280     # one column of cells, not the page


def test_kind_matches_a_dotted_prefix_but_not_a_word_that_starts_the_same():
    """`kinds: [total]` means the totals block. It must not mean `totally`."""
    boxes = [box(0, 0, 90, 14, "total.grand"), box(0, 20, 90, 34, "total.line"),
             box(0, 40, 90, 54, "totally.unrelated"), box(0, 60, 90, 74, "menu.nm")]
    picked = regions.select_regions(boxes, (100, 100), policy="kind",
                                    kinds=["total"], rng=random.Random(0))
    assert len(picked) == 2
    assert {rect[1] for rect in picked} == {0.0, 20.0}


def test_kind_can_still_name_one_role_exactly():
    boxes = [box(0, 0, 90, 14, "total.grand"), box(0, 20, 90, 34, "total.line")]
    picked = regions.select_regions(boxes, (100, 100), policy="kind",
                                    kinds=["total.grand"], rng=random.Random(0))
    assert len(picked) == 1


def test_scatter_honours_count_and_fraction():
    boxes = receipt()
    assert len(regions.select_regions(boxes, (500, 600), policy="scatter",
                                      count=5, rng=random.Random(0))) == 5
    half = regions.select_regions(boxes, (500, 600), policy="scatter",
                                  fraction=0.5, rng=random.Random(0))
    assert len(half) == round(len(boxes) * 0.5)


def test_count_larger_than_the_page_is_capped_not_repeated():
    boxes = receipt()
    picked = regions.select_regions(boxes, (500, 600), policy="scatter",
                                    count=9999, rng=random.Random(0))
    assert len(picked) == len(boxes) == len(set(picked))


def test_selection_is_reproducible_from_the_seed():
    boxes = receipt()
    args = dict(policy="scatter", fraction=0.3)
    first = regions.select_regions(boxes, (500, 600), rng=random.Random(12), **args)
    again = regions.select_regions(boxes, (500, 600), rng=random.Random(12), **args)
    other = regions.select_regions(boxes, (500, 600), rng=random.Random(13), **args)
    assert first == again
    assert first != other


def test_min_area_drops_the_boxes_too_small_to_mark():
    boxes = [box(0, 0, 200, 20), box(0, 40, 8, 48)]
    picked = regions.select_regions(boxes, (100, 300), policy="all", min_area=100)
    assert len(picked) == 1


def test_an_unknown_policy_names_the_ones_that_exist():
    with pytest.raises(KeyError) as raised:
        regions.select_regions(receipt(), (500, 600), policy="sprinkle")
    assert "sprinkle" in str(raised.value)
    for known in regions.POLICIES:
        assert known in str(raised.value)


def test_no_boxes_and_no_match_are_empty_rather_than_errors():
    """A tờ with no totals row is not a broken chain; it is a receipt."""
    assert regions.select_regions([], (500, 600), policy="all") == []
    assert regions.select_regions(receipt(), (500, 600), policy="kind",
                                  kinds=["nonexistent"], rng=random.Random(0)) == []


# ---------------------------------------------------- the guard that matters


def test_by_box_refuses_to_run_without_boxes():
    """The whole point of `by_box` is NOT ageing the whole page.

    Falling back to the whole sheet when the boxes are missing would make a
    chain that says `by_box` do the one thing it says it does not, and nothing
    downstream would ever notice. So it raises, and the message says how to
    get boxes for an image that has no labels.
    """
    with pytest.raises(ValueError) as raised:
        regions.by_box(object(), effect="hollow", regions=None)
    assert "boxes_from_ink" in str(raised.value)


def test_by_box_rejects_an_empty_effect_and_itself():
    for effect in ("", "by_box"):
        with pytest.raises(ValueError):
            regions.by_box(object(), effect=effect, regions=receipt())
