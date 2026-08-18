"""The grid: every layout, several seeds, geometry that must always hold.

Not a pixel in sight. The grid is a character lattice, so overlap and overflow
are integer facts -- and they are the facts a renderer cannot recover from,
because two cells claiming the same columns print on top of each other in all
three backends at once.
"""

from __future__ import annotations

import pytest

import rulebase
from rulebase.layout import available as available_layouts

SEEDS = (1, 7, 42, 2026, 90210)
LAYOUTS = available_layouts()


# Built once and reused. `rulebase.make` with a pinned layout retries seeds
# until the pin fits, so a grid is not cheap; rebuilding the same 25 for each
# test took the suite from 2 s to 21 s.
_GRIDS: list | None = None


def grids():
    global _GRIDS
    if _GRIDS is None:
        _GRIDS = [
            (layout, seed) + rulebase.make(seed=seed, force={"layout": layout})[1:]
            for layout in LAYOUTS
            for seed in SEEDS
        ]
    return _GRIDS


def test_there_are_layouts():
    assert LAYOUTS, "no layout files found"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_declared_layout_builds(layout):
    _recipe, _receipt, grid = rulebase.make(seed=3, force={"layout": layout})
    assert grid.cells
    assert grid.layout_id == layout


def test_no_two_cells_overlap_on_a_row():
    for layout, seed, _receipt, grid in grids():
        rows: dict[int, list] = {}
        for cell in grid.cells:
            rows.setdefault(cell.row, []).append(cell)
        for row, cells in rows.items():
            spans = sorted((cell.col0, cell.col1, cell.text) for cell in cells)
            for (_a0, a1, a_text), (b0, _b1, b_text) in zip(spans, spans[1:]):
                assert a1 <= b0, (
                    f"{layout} seed={seed} row {row}: {a_text!r} ends at {a1} "
                    f"but {b_text!r} starts at {b0}"
                )


def test_no_cell_runs_past_the_paper():
    for layout, seed, _receipt, grid in grids():
        for cell in grid.cells:
            assert cell.col0 >= 0, f"{layout} seed={seed}: {cell.text!r} starts left of 0"
            assert cell.col1 <= grid.ncols, (
                f"{layout} seed={seed}: {cell.text!r} ends at {cell.col1} "
                f"on {grid.ncols}-column paper"
            )


def test_text_fits_the_columns_it_claims():
    for layout, seed, _receipt, grid in grids():
        for cell in grid.cells:
            width = cell.col1 - cell.col0
            assert len(cell.text) <= width, (
                f"{layout} seed={seed}: {cell.text!r} is {len(cell.text)} chars "
                f"in {width} columns"
            )


def test_nrows_matches_the_rows_actually_used():
    for layout, seed, _receipt, grid in grids():
        highest = max(cell.row for cell in grid.cells)
        assert highest < grid.nrows, f"{layout} seed={seed}: row {highest} >= nrows"
        assert grid.nrows - highest <= 2, (
            f"{layout} seed={seed}: nrows={grid.nrows} but nothing past row {highest}"
        )


def test_every_printed_cell_has_a_role():
    # A cell with no role cannot be labelled or boxed; it would be ink the
    # ground truth never mentions.
    for layout, seed, _receipt, grid in grids():
        for cell in grid.cells:
            if cell.text.strip():
                assert cell.role, f"{layout} seed={seed}: {cell.text!r} has no role"


def test_scale_and_alignment_stay_in_range():
    for layout, seed, _receipt, grid in grids():
        for cell in grid.cells:
            assert cell.align in ("left", "right", "center"), f"{layout} seed={seed}"
            assert 0.5 <= cell.scale <= 3.0, (
                f"{layout} seed={seed}: {cell.text!r} scale={cell.scale}"
            )


# ------------------------------------------------- marks: the non-text layer


def _ruled(layout_id: str, seed: int = 2026):
    """The same layout built both ways, so the difference is only the flag."""
    import random

    import rulebase.layout as L

    receipt = rulebase.make(seed=seed, force={"layout": layout_id})[1]
    original = L.load_layout

    def built(mode):
        spec = dict(original(layout_id))
        spec["rules"] = mode
        L.load_layout = lambda lid, root=L.LAYOUTS_ROOT: (
            spec if lid == layout_id else original(lid, root))
        try:
            return L.build_grid(receipt, layout_id, random.Random(seed))
        finally:
            L.load_layout = original

    # Both modes stated, neither inherited: the layout on disk may already ask
    # for one of them, and a test that read the default would silently compare
    # a thing with itself.
    return built("ascii"), built("marks")


def test_a_layout_that_does_not_ask_gets_no_marks():
    """The whole reason `rules:` is opt-in.

    Five thermal layouts draw their separators with characters because a till
    really does print them that way, and every committed image depends on it.
    """
    for layout_id in ("eatery_ascii", "eatery_indexed", "market_barcode",
                      "market_compact", "market_vat"):
        grid = rulebase.make(seed=7, force={"layout": layout_id})[2]
        assert grid.marks == [], layout_id
        assert "marks" not in grid.to_dict()


def test_asking_for_marks_replaces_the_ascii_rules_with_drawn_ones():
    plain, ruled = _ruled("invoice_vat_form")
    assert not plain.marks and ruled.marks

    # Every `+---+` and `|` cell is gone, and the same lines are marks instead.
    assert sum(1 for c in plain.cells if c.role == "sep") > 100
    assert sum(1 for c in ruled.cells if c.role == "sep") == 0

    # A drawn rule sits between two rows and costs no row, so the page is
    # shorter -- which is why a real printed form fits more on a page than its
    # ASCII rendering of the same fields does.
    assert ruled.nrows < plain.nrows


def test_the_text_of_a_page_is_the_same_either_way():
    """Marks change how the page is ruled, never what it says."""
    plain, ruled = _ruled("invoice_vat_form")
    said = lambda grid: [(c.role, c.text) for c in grid.cells if c.role != "sep"]  # noqa: E731
    assert said(plain) == said(ruled)


def test_a_mark_stays_on_the_grid_it_is_measured_in():
    _plain, ruled = _ruled("invoice_vat_form")
    for mark in ruled.marks:
        assert mark.kind in ("rule", "fill", "frame")
        assert 0 <= mark.col0 <= mark.col1 <= ruled.ncols, mark
        assert 0 <= mark.row0 <= mark.row1 <= ruled.nrows, mark
        # A rule is degenerate on exactly one axis; a mark that is degenerate on
        # both is a point and draws nothing.
        assert (mark.col1 > mark.col0) or (mark.row1 > mark.row0), mark


def test_marks_reach_the_serialised_grid():
    _plain, ruled = _ruled("invoice_vat_form")
    data = ruled.to_dict()
    assert len(data["marks"]) == len(ruled.marks)
    assert set(data["marks"][0]) == {"kind", "row0", "col0", "row1", "col1",
                                     "weight", "tone"}
