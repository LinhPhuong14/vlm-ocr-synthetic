"""The grid: every layout, several seeds, geometry that must always hold.

Not a pixel in sight. The grid is a character lattice, so overlap and overflow
are integer facts -- and they are the facts a renderer cannot recover from,
because two cells claiming the same columns print on top of each other in all
three backends at once.
"""

from __future__ import annotations

import pytest
from conftest import force_for

import rulebase
from rulebase.layout import every as every_layout

# `every_layout`, not `available_layouts`: a layout switched off with
# `enabled: false` means no RUN draws it, not that nobody checks it any more.
# An unwatched file rots, and switching one back on should not be archaeology.

SEEDS = (1, 7, 42, 2026, 90210)
LAYOUTS = every_layout()


# Built once and reused. `rulebase.make` with a pinned layout retries seeds
# until the pin fits, so a grid is not cheap; rebuilding the same 25 for each
# test took the suite from 2 s to 21 s.
_GRIDS: list | None = None


def grids():
    global _GRIDS
    if _GRIDS is None:
        _GRIDS = [
            (layout, seed) + rulebase.make(seed=seed, force=force_for(layout))[1:]
            for layout in LAYOUTS
            for seed in SEEDS
        ]
    return _GRIDS


def test_there_are_layouts():
    assert LAYOUTS, "no layout files found"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_declared_layout_builds(layout):
    _recipe, _receipt, grid = rulebase.make(seed=3, force=force_for(layout))
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

    receipt = rulebase.make(seed=seed, force=force_for(layout_id))[1]
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
        grid = rulebase.make(seed=7, force=force_for(layout_id))[2]
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


def test_the_verticals_of_a_frame_reach_the_rules_they_bound():
    """A box open at both ends is not a box.

    The call sites count in ASCII rows, where a rule spends a row of its own and
    the first `|` goes one row inside it. Drawn, the rule sits *on* the boundary
    and a vertical that started one row in leaves a visible gap at the top and
    bottom of every frame on the page.
    """
    _plain, ruled = _ruled("invoice_vat_form")
    horizontals = [m for m in ruled.marks if m.kind == "rule" and m.row0 == m.row1]
    verticals = [m for m in ruled.marks if m.kind == "rule" and m.col0 == m.col1]
    assert horizontals and verticals

    for bar in verticals:
        # Something horizontal closes it off at each end, at the same row and
        # crossing the column the vertical stands in.
        for row in (bar.row0, bar.row1):
            assert any(rule.row0 == row and rule.col0 <= bar.col0 <= rule.col1
                       for rule in horizontals), (bar, row)


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
    """
    plain, ruled = _ruled("invoice_vat_form")   # ruled, and asks for no shade
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
    # Which layouts are on a roll is read from the layout files rather than
    # from their names. It used to be `id.startswith("invoice_")`, and that
    # stopped being true the day a cut-sheet document arrived that is not an
    # invoice -- a hospital bill and an authorisation form are both A4, and
    # neither is called `invoice_anything`.
    rolls = {layout for layout in LAYOUTS
             if not rulebase.load_layout(layout).get("sheet")}
    assert rolls, "every layout claims a cut sheet; the roll case is untested"
    for layout_id in LAYOUTS:
        grid = rulebase.make(seed=11, force=force_for(layout_id))[2]
        ratio = rulebase.sheet_ratio(grid)
        if layout_id in rolls:
            assert grid.sheet == "", layout_id
            assert ratio is None, layout_id
        else:
            assert grid.sheet == "a4", layout_id
            assert ratio == pytest.approx(210 / 297), layout_id


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


# ---------------------------------------------------- switching one off


ROOT_FORM = ("form_activity_signature", "form_checkbox_heavy",
             "form_dense_registration", "form_government_app",
             "form_multi_section", "form_project_kv", "form_questionnaire",
             "form_table_based", "form_timesheet_grid", "form_two_column")


def test_the_two_lists_agree_when_nothing_is_switched_off():
    """`enabled: false` means "no run draws it", not "it is gone".

    The two lists are the whole mechanism: `available()` is what a run takes
    when `run.layouts` is empty, `every()` is what the checks walk. A layout
    that left both would take its committed pages with it -- nothing could
    redraw them, because `rulebase.make(force=...)` needs the rules entry and
    `sheets.FAMILIES` needs the file.

    Root 3 is back on at the owner's request, so nothing is switched off today
    and the two lists coincide. The assertion is the *difference*, not a fixed
    list: whichever way the switch goes, a layout that leaves `available()`
    without leaving the disk is the thing being checked, and a layout that
    leaves both is the failure.
    """
    drawable = set(rulebase.available_layouts())
    on_disk = set(every_layout())

    assert set(ROOT_FORM) <= on_disk
    assert drawable <= on_disk, "a run can draw a layout that is not on disk"
    for switched_off in sorted(on_disk - drawable):
        assert rulebase.load_layout(switched_off), (
            f"{switched_off} left the drawable list AND the disk")


def test_a_root_form_layout_draws_when_it_is_named():
    """The pages that drew one have to stay drawable, switch or no switch.

    With its DOCUMENT named too, which is what a redraw does anyway --
    `tools/check_boxes.py` forces every attribute off the record. `form_two_column`
    requires a tag only the `doc_form` documents set, so naming the layout alone
    is refused loudly rather than quietly drawing something else; that half of
    the behaviour is unchanged by root 3 coming back on.
    """
    recipe, _receipt, grid = rulebase.make(
        seed=11, force={"document": "form_symmetric", "layout": "form_two_column"})
    assert grid.layout_id == "form_two_column"
    assert recipe.layout.id == "form_two_column"


def test_a_switched_off_layout_still_has_a_sheet_to_be_dressed_in():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "generators" / "html"))
    import sheets

    assert sheets.FAMILIES["form_two_column"] is sheets.family_of("form_two_column")


def test_the_switch_is_read_from_the_layouts_own_file(tmp_path):
    from rulebase import layout as L

    (tmp_path / "on.yaml").write_text("id: on\nname: x\n", encoding="utf-8")
    (tmp_path / "off.yaml").write_text("enabled: false\nid: off\nname: x\n",
                                       encoding="utf-8")

    assert L.every(tmp_path) == ["off", "on"]
    assert L.available(tmp_path) == ["on"]
    assert L.is_enabled("on", tmp_path) and not L.is_enabled("off", tmp_path)
    # `off:` as the key would be YAML 1.1's boolean and vanish. Spelled
    # `enabled:` for that reason -- and this is the test that says so.
    assert "enabled" in (tmp_path / "off.yaml").read_text(encoding="utf-8")
