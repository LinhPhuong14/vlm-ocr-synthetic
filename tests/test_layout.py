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
    required = {"kind", "row0", "col0", "row1", "col1", "weight", "tone"}
    for mark in data["marks"]:
        # `colour` is the one optional key, and it is optional on purpose: a
        # mark that fades with the page's ink has no colour of its own, and
        # writing `"colour": null` on every mark of every layout would rewrite
        # every label that already exists to say so out loud.
        assert set(mark) in (required, required | {"colour"}), mark


RULED_LAYOUTS = [layout for layout in LAYOUTS
                 if rulebase.make(seed=11, force={"layout": layout})[2].marks]


@pytest.mark.parametrize("layout", RULED_LAYOUTS)
def test_the_verticals_of_a_frame_reach_the_rules_they_bound(layout):
    """A box open at both ends is not a box.

    The call sites count in ASCII rows, where a rule spends a row of its own and
    the first `|` goes one row inside it. Drawn, the rule sits *on* the boundary
    and a vertical that started one row in leaves a visible gap at the top and
    bottom of every frame on the page.

    A merge boundary closes a vertical too, and closes it by *not* drawing
    anything: the whole point of a merged cell is that the lines inside it are
    absent, so the segments of a vertical either side of one end on its edges.
    That is the only other way an end may be left open, and naming it here is
    what keeps this test able to say anything at all once merges exist.

    Over every ruled layout rather than one. Asked of `invoice_vat_form` alone
    it passed while the totals box of `invoice_export` and the "Số tiền bằng
    chữ" box of `invoice_vat_summary` were both drawn with no lid.
    """
    _plain, ruled = _ruled(layout)
    horizontals = [m for m in ruled.marks if m.kind == "rule" and m.row0 == m.row1]
    verticals = [m for m in ruled.marks if m.kind == "rule" and m.col0 == m.col1]
    assert horizontals, layout
    if not verticals:
        # `table: {frame: false}` -- a hotel bill rules its heading and leaves
        # the rest of the table open. There is no box here to be open at.
        pytest.skip(f"{layout} draws no framed box")

    edges = {merge.row0 for merge in ruled.merges} | {merge.row1 for merge in ruled.merges}
    for bar in verticals:
        # Something horizontal closes it off at each end, at the same row and
        # crossing the column the vertical stands in -- or a merge does.
        for row in (bar.row0, bar.row1):
            closed = any(rule.row0 == row and rule.col0 <= bar.col0 <= rule.col1
                         for rule in horizontals)
            assert closed or row in edges, (layout, bar, row)


def test_a_shaded_band_is_a_fill_under_the_column_titles():
    ruled = rulebase.make(seed=77, force={"layout": "invoice_vat_summary"})[2]
    fills = [m for m in ruled.marks if m.kind == "fill"]
    assert fills, "invoice_vat_summary asks for `shade:` on both of its tables"
    titles = [c.row for c in ruled.cells if c.role == "colhdr"]
    for fill in fills:
        assert 0 < fill.tone < 1, fill          # a tint, not ink
        assert fill.col1 > fill.col0 and fill.row1 > fill.row0, fill
        assert any(fill.row0 <= row < fill.row1 for row in titles), fill


def test_a_layout_that_does_not_ask_for_shading_gets_none():
    """`shade:` is opt-in twice over -- by the layout, and by being ruled.

    A till roll can print a line of `-`; it cannot print a grey box, so the
    ASCII half of a layout must not grow one however the YAML is written.

    The first half asks it of a page whose dice came up "no tint": `fill:` is
    one of the knobs `variation:` rolls, so "this layout does not shade" is now
    a fact about a *page* rather than about a layout file, and the page has to
    be found rather than named.
    """
    for seed in SEEDS:
        plain, ruled = _ruled("invoice_vat_form", seed=seed)
        if ruled.table_style.get("fill") is None and not ruled.table_style.get("zebra"):
            break
    else:
        pytest.skip("no seed in SEEDS drew an untinted invoice_vat_form")
    assert not [m for m in plain.marks if m.kind == "fill"]
    assert not [m for m in ruled.marks if m.kind == "fill"]

    import random

    import rulebase.layout as L
    receipt = rulebase.make(seed=77, force={"layout": "invoice_vat_summary"})[1]
    original = L.load_layout
    spec = dict(original("invoice_vat_summary"))
    spec["rules"] = "ascii"                     # keeps `shade:` in place
    L.load_layout = lambda lid, root=L.LAYOUTS_ROOT: (
        spec if lid == "invoice_vat_summary" else original(lid, root))
    try:
        ascii_grid = L.build_grid(receipt, "invoice_vat_summary", random.Random(77))
    finally:
        L.load_layout = original
    assert ascii_grid.marks == []


def test_the_outer_border_of_a_table_is_drawn_heavier_than_its_row_rules():
    _plain, ruled = _ruled("invoice_vat_form")
    frames = [m for m in ruled.marks if m.kind == "frame"]
    assert frames, "a framed table draws its boundary with a heavier pen"
    for frame in frames:
        assert frame.weight > 1.0, frame
        assert frame.col1 > frame.col0 and frame.row1 > frame.row0, frame
    assert all(m.weight == 1.0 for m in ruled.marks if m.kind == "rule")


def test_shading_is_listed_before_the_lines_that_bound_it():
    """Painter's order, decided once here instead of three times downstream.

    `marks` is back to front. A tint listed after the rule along its edge would
    be painted over that rule and rub it out.
    """
    ruled = rulebase.make(seed=77, force={"layout": "invoice_vat_summary"})[2]
    kinds = [m.kind for m in ruled.marks]
    assert "fill" in kinds and "rule" in kinds
    assert kinds.index("rule") > max(i for i, k in enumerate(kinds) if k == "fill")


def test_a_separator_between_blocks_still_spends_its_row():
    """A table rule costs no row; a separator does.

    Both are drawn lines, and the difference is what they separate: the rule
    between two rows of a table is the boundary those rows already share, while
    a rule between two blocks is a gap with a line in it. Take that row away and
    the line lands on the shoulders of the next line of type.
    """
    # Two layouts, because there are two separators: the till's (`_Builder.rule`,
    # under the footer of the power bill) and the form's (`_full_rule`, under the
    # strip of the export invoice). Only one of them is exercised by either page.
    for layout_id in ("invoice_power", "invoice_export"):
        _plain, ruled = _ruled(layout_id)
        strays = [m for m in ruled.marks if m.row0 == m.row1 and m.row0 != int(m.row0)]
        assert strays, f"{layout_id} separates two blocks with a drawn rule"
        for mark in strays:
            assert mark.row0 - int(mark.row0) == 0.5, (layout_id, mark)
            assert not [c for c in ruled.cells if c.row == int(mark.row0)], mark


# ---------------------------------------------------- the sheet it prints on


def test_a_thermal_layout_is_on_a_roll_and_an_invoice_is_on_a_sheet():
    """The distinction is a fact about the printer, not a preference.

    A till roll has no bottom edge until the cutter makes one, so its page
    really is as tall as the sale. A cut sheet's height is decided before
    anything is printed, which is why the whitespace under a three-item invoice
    is part of what the document looks like rather than something to crop.
    """
    for layout_id in LAYOUTS:
        grid = rulebase.make(seed=11, force={"layout": layout_id})[2]
        ratio = rulebase.sheet_ratio(grid)
        if layout_id.startswith("invoice_"):
            assert grid.sheet == "a4", layout_id
            assert ratio == pytest.approx(210 / 297), layout_id
        else:
            assert grid.sheet == "", layout_id
            assert ratio is None, layout_id


def test_the_sheet_reaches_the_serialised_grid():
    grid = rulebase.make(seed=11, force={"layout": "invoice_vat_form"})[2]
    assert grid.to_dict()["sheet"] == "a4"
    roll = rulebase.make(seed=11, force={"layout": "eatery_ascii"})[2]
    assert "sheet" not in roll.to_dict()


def test_an_unknown_sheet_is_refused_when_the_layout_is_built():
    """A typo has to stop the run, not silently print on a roll."""
    import random

    import rulebase.layout as L

    receipt = rulebase.make(seed=11, force={"layout": "invoice_vat_form"})[1]
    original = L.load_layout
    spec = dict(original("invoice_vat_form"))
    spec["sheet"] = "a4paper"
    L.load_layout = lambda lid, root=L.LAYOUTS_ROOT: (
        spec if lid == "invoice_vat_form" else original(lid, root))
    try:
        with pytest.raises(KeyError, match="unknown sheet"):
            L.build_grid(receipt, "invoice_vat_form", random.Random(11))
    finally:
        L.load_layout = original


def test_the_sheet_only_ever_grows_the_page():
    """Never a crop: a page that overflowed its paper has to stay visible.

    Cropping it to A4 would turn a layout bug into a page that looks right and
    is missing its last three lines -- which nothing downstream would catch,
    because the boxes would still be inside the frame.
    """
    grid = rulebase.make(seed=11, force={"layout": "invoice_vat_form"})[2]
    a4 = 210 / 297
    # Content shorter than the paper: the paper wins.
    assert rulebase.sheet_height(grid, 1000, 100) == pytest.approx(1000 / a4)
    # Content taller than the paper: the content wins.
    assert rulebase.sheet_height(grid, 1000, 9000) == 9000

    roll = rulebase.make(seed=11, force={"layout": "eatery_ascii"})[2]
    assert rulebase.sheet_height(roll, 1000, 100) == 100


# ------------------------------------------------------------------ merges


FRAMED_LAYOUTS = [
    layout for layout in RULED_LAYOUTS
    if any(m.kind == "rule" and m.col0 == m.col1
           for m in rulebase.make(seed=11, force={"layout": layout})[2].marks)
]


@pytest.mark.parametrize("layout", FRAMED_LAYOUTS)
def test_a_merged_cell_has_no_rules_inside_it(layout):
    """What "merged" means on paper, stated as the only thing it means.

    Before this, the water bill's tariff name ran across all six meter columns
    and the frame drew five verticals straight through the words -- "Tiền nước
    sin|h hoạt bậc 1 |(0-10m3)" on every page of that layout.
    """
    for seed in SEEDS:
        _plain, ruled = _ruled(layout, seed=seed)
        verticals = [m for m in ruled.marks if m.kind == "rule" and m.col0 == m.col1]
        horizontals = [m for m in ruled.marks if m.kind == "rule" and m.row0 == m.row1]
        for merge in ruled.merges:
            for bar in verticals:
                inside = (merge.col0 < bar.col0 < merge.col1
                          and bar.row0 < merge.row1 and merge.row0 < bar.row1)
                assert not inside, (layout, seed, merge, bar)
            for rule in horizontals:
                inside = (merge.row0 < rule.row0 < merge.row1
                          and rule.col0 < merge.col1 and merge.col0 < rule.col1)
                assert not inside, (layout, seed, merge, rule)


def test_an_item_row_that_spans_its_columns_is_declared_a_merge():
    """The water bill names its tariff band across the whole table."""
    _plain, ruled = _ruled("invoice_water")
    names = [c for c in ruled.cells if c.role == "menu.name"]
    assert names, "invoice_water names every tariff band"
    for cell in names:
        assert any(m.row0 <= cell.row < m.row1
                   and m.col0 <= cell.col0 and cell.col1 <= m.col1
                   for m in ruled.merges), cell


def test_a_merge_is_recorded_even_where_nothing_is_drawn():
    """An ASCII till roll rules nothing, and its spans are merges all the same.

    The label describes the table, not the ink: `eatery_indexed` puts the dish
    name across the numeric columns whether or not a line would have divided
    them, and a structure label that appeared only on ruled layouts would
    describe two different tables under one layout id.
    """
    grid = rulebase.make(seed=7, force={"layout": "eatery_indexed"})[2]
    assert grid.marks == []
    assert grid.merges


# ------------------------------------------------------- two-level headings


def test_a_two_level_head_puts_one_title_over_several_columns():
    for seed in range(0, 400):
        grid = rulebase.make(seed=seed, force={"layout": "invoice_vat_form"})[2]
        if grid.table_style.get("column_groups"):
            break
    else:
        pytest.skip("no seed drew invoice_vat_form with its groups on")

    parents = [c for c in grid.cells if c.role == "colgroup"]
    assert parents, "the group was drawn on, so its title is on the page"
    parent = parents[0]
    covered = [c for c in grid.cells if c.role == "colhdr"
               and parent.col0 <= c.col0 and c.col1 <= parent.col1
               and c.row > parent.row]
    assert len(covered) >= 2, "a parent stands over at least two children"

    # A child stops repeating its parent's words once the parent is there.
    # Joined, because a title narrower than its column arrives wrapped: the
    # `vat_rate` column is ten characters wide and a `gutter: 3` leaves seven
    # of them, so "Thuế suất" is set over two lines.
    joined = " ".join(c.text for c in sorted(covered, key=lambda c: (c.row, c.col0)))
    assert "GTGT" in parent.text.upper(), parent.text
    assert "GTGT" not in joined.upper(), joined

    # A column with no parent runs the whole height of the head instead.
    tall = [c for c in grid.cells if c.role == "colhdr" and c.rowspan > 1]
    assert tall, "the ungrouped columns span both bands of the head"


def test_a_flat_head_gets_no_row_spans_and_no_parents():
    """Off, the head is exactly the one band it was before groups existed."""
    for seed in range(0, 400):
        grid = rulebase.make(seed=seed, force={"layout": "invoice_vat_form"})[2]
        if grid.table_style.get("column_groups") is False:
            break
    else:
        pytest.skip("no seed drew invoice_vat_form with its groups off")
    assert not [c for c in grid.cells if c.role == "colgroup"]
    assert all(c.rowspan == 1 for c in grid.cells)


# ------------------------------------------------------------------ colour


def test_a_coloured_fill_carries_its_colour_instead_of_a_tone():
    for seed in range(0, 400):
        grid = rulebase.make(seed=seed, force={"layout": "invoice_water"})[2]
        if grid.table_style.get("fill"):
            break
    else:
        pytest.skip("no seed drew a tinted invoice_water")
    coloured = [m for m in grid.marks if m.kind == "fill" and m.colour]
    assert coloured, "the page drew a colour, so a fill carries one"
    for mark in coloured:
        assert mark.colour.startswith("#") and len(mark.colour) == 7, mark
        assert mark.tone == 1.0, "a colour is not also diluted"
        assert mark.to_dict()["colour"] == mark.colour


def test_a_page_that_draws_no_colour_serialises_no_colour_key():
    grid = rulebase.make(seed=7, force={"layout": "eatery_indexed"})[2]
    for mark in grid.marks:
        assert "colour" not in mark.to_dict()


# --------------------------------------------------------------- variation


def test_the_variation_is_recorded_and_a_seed_repeats_it():
    first = rulebase.make(seed=285, force={"layout": "invoice_water"})[2]
    again = rulebase.make(seed=285, force={"layout": "invoice_water"})[2]
    assert first.table_style
    assert first.table_style == again.table_style
    assert first.to_dict() == again.to_dict()


def test_the_variation_actually_varies():
    seen = {frozenset(rulebase.make(seed=s, force={"layout": "invoice_water"})[2]
                      .table_style.items())
            for s in range(0, 60)}
    assert len(seen) > 5, "sixty pages of one layout should not be one table"


@pytest.mark.parametrize("layout", ["eatery_ascii", "eatery_indexed",
                                    "market_barcode", "market_compact", "market_vat"])
def test_a_layout_with_no_variation_block_rolls_no_dice(layout):
    """The till receipts must draw exactly the page they drew before.

    `_sample_variation` returns without touching the rng when the layout
    declares nothing, which is the only reason every committed thermal image
    still hashes the same: a single extra draw here shifts the whole stream and
    moves every later decision on the page.
    """
    grid = rulebase.make(seed=7, force={"layout": layout})[2]
    assert grid.table_style == {}


def test_the_table_label_says_what_the_picture_cannot():
    grid = rulebase.make(seed=285, force={"layout": "invoice_water"})[2]
    label = grid.table_label()
    assert set(label) <= {"style", "merges"}
    assert label["style"] == grid.table_style
    assert len(label["merges"]) == len(grid.merges)
    # A layout with neither has nothing to say and says nothing.
    plain = rulebase.make(seed=7, force={"layout": "eatery_ascii"})[2]
    assert plain.table_label() is None


# -------------------------------------------------------------- alignment


@pytest.mark.parametrize("layout", FRAMED_LAYOUTS)
def test_no_vertical_steps_sideways_where_two_blocks_meet(layout):
    """The item table and the totals under it are one frame, or they look wrong.

    `_emit_framed_totals` used to place its one vertical at `money_col - 1`
    while the table above placed its bars with `_bar_positions`. With `gutter:
    3` -- which every ruled invoice here has -- those are one character apart,
    so the right-hand rule of the frame visibly stepped sideways at the row
    where the items ended. Six of the nine framed layouts did it.
    """
    for seed in SEEDS:
        _plain, ruled = _ruled(layout, seed=seed)
        verticals = [m for m in ruled.marks if m.kind == "rule" and m.col0 == m.col1]
        for above in verticals:
            for below in verticals:
                if above is below or abs(above.row1 - below.row0) > 1e-9:
                    continue
                step = abs(above.col0 - below.col0)
                assert not 0 < step <= 2, (
                    f"{layout} seed={seed}: a vertical at column {above.col0} "
                    f"ends at row {above.row1} and the next starts at column "
                    f"{below.col0} -- the frame steps sideways by {step}"
                )
