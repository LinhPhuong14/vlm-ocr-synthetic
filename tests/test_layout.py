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
