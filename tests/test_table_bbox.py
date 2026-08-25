"""The claim `tests/test_table.py` cannot make: the boxes over real pixels.

Everything in `test_table.py` is a fact about the HTML string -- correct by
construction if Chromium lays out `border-collapse` tables the way every
other page in this repository already assumes it does (`sheets/base.py` has
relied on exactly that since before this component existed). This file is
where that assumption gets checked instead of trusted: render a table
through the same browser and the same `CELL_REGIONS_JS` the pipeline reads
boxes with, and confirm what comes back actually describes the pixels --
one box per rendered cell, nothing overlapping, a merged cell's box sized
like the columns it spans, a nested table's own cells never leaking into the
outer page's boxes, and non-empty cells actually sitting on ink.

`slow`: needs Chromium. Skipped outright rather than failing when Playwright
or the browser is not available, same as every other renderer-backed test.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))


def _browser_ready() -> bool:
    try:
        import playwright.sync_api  # noqa: F401
    except ImportError:
        return False
    from page import find_chromium

    return find_chromium() is not None


pytestmark = pytest.mark.slow


def _build_table():
    """A table exercising every case the boxes have to get right at once."""
    from components.table import Border, Cell, Column, Row, TableSpec

    breakdown = TableSpec(
        border=Border.rows(0.2), width="auto",
        rows=[Row.of("hàng", "35.000"), Row.of("thuế", "10.000")],
    )
    columns = [Column(12, align="center"), Column(), Column(20, align="right"),
              Column(20, align="right")]
    rows = [
        Row.of("STT", "Tên món", "Đơn giá", "Thành tiền", header=True),
        Row.of("1", "Phở bò tái", "45.000", "45.000"),
        Row([Cell("2"), Cell("Trà đá x2", bg="#fff3cd"), Cell("10.000"), Cell("20.000")]),
        Row([Cell("Tổng cộng", colspan=3, align="right", bold=True),
             Cell("80.000", align="right", bold=True)]),
        Row([Cell("3", rowspan=2), Cell("Combo trưa"), Cell(breakdown), Cell("")]),
        Row([Cell("Trà đá kèm")]),          # col 0 skipped: swallowed by the rowspan above
    ]
    return TableSpec(columns=columns, border=Border.grid(0.3), rows=rows)


def _render_and_extract(tmp_path: Path):
    from components.table import render_table
    from page import CELL_REGIONS_JS, find_chromium, font_faces, served
    from playwright.sync_api import sync_playwright
    from sheets import base

    table = _build_table()
    markup = base.document(render_table(table), "table{font-family:%s;}" % base.SANS)
    # `document()` leaves a literal "{FONT_FACES}" token in its <style> block;
    # `render.py` is the one that substitutes it, so this test does the same
    # substitution it does rather than embedding fonts itself and drifting
    # from how a real page actually gets served.
    markup = markup.replace("{FONT_FACES}", font_faces())
    assert "@font-face" in markup             # sanity: the substitution actually ran

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=find_chromium())
        try:
            page = browser.new_page(device_scale_factor=2.0)
            try:
                with served(markup) as uri:
                    page.goto(uri, wait_until="load")
                page.wait_for_timeout(60)
                boxes = page.evaluate(CELL_REGIONS_JS)
                sheet_el = page.query_selector("#sheet")
                sheet = sheet_el.bounding_box()
                shot = tmp_path / "bbox.png"
                # The `#sheet` element, not the full page: the viewport is wider
                # than an A4 sheet, and a full-page screenshot's width then has
                # no fixed relationship to `sheet["width"]` (only to the
                # viewport's) -- exactly the ratio bug this comment replaced,
                # which silently pointed every "on ink" crop a few hundred
                # pixels off to the right of the cell it was supposed to check.
                sheet_el.screenshot(path=str(shot))
            finally:
                page.close()
        finally:
            browser.close()
    return table, boxes, sheet, shot


@pytest.mark.skipif(not _browser_ready(), reason="no Chromium/Playwright available")
def test_coverage_one_box_per_rendered_cell_no_more_no_less(tmp_path):
    """As many boxes as `<td data-cell>`/`<th data-cell>` elements were drawn.

    Counted independently of `CELL_REGIONS_JS` -- straight off the HTML
    string with a regex -- so a bug that made the JS silently drop or
    duplicate elements would not also make this count agree with it by
    construction.
    """
    from components.table import render_table
    from sheets import base

    table = _build_table()
    markup = render_table(table)
    # `data-cell=`, not `<t[dh]\b`: the outer table's nested cell (see
    # `Cell.content`) also writes `<td>` elements, but with `label_cells=
    # False` -- they carry no `data-cell` and `CELL_REGIONS_JS` selects on
    # exactly that attribute, so counting bare tags would count 4 cells the
    # query never sees (this is `test_a_nested_tables_cells_do_not_leak_...`'s
    # claim, made a second, independent way).
    written = markup.count("data-cell=")
    _table, boxes, _sheet, _shot = _render_and_extract(tmp_path)
    del base
    assert len(boxes) == written
    # The table has 6 rows x 4 columns = 24 grid positions; two colspans (3
    # cells fused into 1, twice: the totals row) and one rowspan (2 cells
    # fused into 1) remove 2 + 1 = 3 cells from that count.
    assert written == 6 * 4 - 3


@pytest.mark.skipif(not _browser_ready(), reason="no Chromium/Playwright available")
def test_every_box_is_inside_the_sheet(tmp_path):
    _table, boxes, sheet, _shot = _render_and_extract(tmp_path)
    for box in boxes:
        assert -1 <= box["x"] <= sheet["width"] + 1
        assert -1 <= box["y"] <= sheet["height"] + 1
        assert box["x"] + box["w"] <= sheet["width"] + 1
        assert box["y"] + box["h"] <= sheet["height"] + 1


@pytest.mark.skipif(not _browser_ready(), reason="no Chromium/Playwright available")
def test_no_two_boxes_overlap(tmp_path):
    """Disjoint rectangles -- the geometric fact a merge exists to preserve.

    A colspan/rowspan cell replaces several boxes with one *larger* one; it
    must never coexist with a smaller box underneath it. `pipeline/
    invariants.py` has no equivalent check today because no template-path
    document nests tables or reaches this many simultaneous merges -- which
    is exactly why this component needs its own.
    """
    _table, boxes, _sheet, _shot = _render_and_extract(tmp_path)

    def overlaps(a, b) -> bool:
        margin = 0.5  # px of AA/rounding slack, not a real overlap
        return not (a["x"] + a["w"] <= b["x"] + margin or b["x"] + b["w"] <= a["x"] + margin
                   or a["y"] + a["h"] <= b["y"] + margin or b["y"] + b["h"] <= a["y"] + margin)

    for i, a in enumerate(boxes):
        for b in boxes[i + 1:]:
            assert not overlaps(a, b), f"{a['kind']!r}@({a['row']},{a['col']}) overlaps " \
                                       f"{b['kind']!r}@({b['row']},{b['col']})"


@pytest.mark.skipif(not _browser_ready(), reason="no Chromium/Playwright available")
def test_a_nested_tables_cells_do_not_leak_into_the_pages_boxes(tmp_path):
    """The outer table has 21 boxes (24 grid cells - 3 merged away); the

    breakdown table nested in row 4 has 4 cells of its own (2x2) that must
    NOT appear among them -- `render_table(..., label_cells=False)` is what
    the outer cell's content is built with (see `Cell.content`), and this is
    the end-to-end proof that promise holds through a real render, not just
    through the string this component returns.
    """
    _table, boxes, _sheet, _shot = _render_and_extract(tmp_path)
    assert len(boxes) == 21
    assert all(box["kind"] == "" for box in boxes)   # this component never sets `kind` here


@pytest.mark.skipif(not _browser_ready(), reason="no Chromium/Playwright available")
def test_row_numbers_increase_top_to_bottom_and_share_a_y_within_a_row(tmp_path):
    _table, boxes, _sheet, _shot = _render_and_extract(tmp_path)
    by_row: dict[int, list[dict]] = {}
    for box in boxes:
        by_row.setdefault(box["row"], []).append(box)
    rows_in_order = sorted(by_row)
    assert rows_in_order == list(range(len(rows_in_order)))   # dense, starting at 0
    tops = {row: min(box["y"] for box in cells) for row, cells in by_row.items()}
    ordered_tops = [tops[row] for row in rows_in_order]
    assert ordered_tops == sorted(ordered_tops), "a later data-row sat higher on the page"
    for row, cells in by_row.items():
        ys = [round(box["y"]) for box in cells]
        assert max(ys) - min(ys) <= 2, f"row {row}: cells do not share a top edge ({ys})"


@pytest.mark.skipif(not _browser_ready(), reason="no Chromium/Playwright available")
def test_a_colspan_cells_box_is_as_wide_as_the_columns_it_spans(tmp_path):
    """The "Tổng cộng" cell (colspan=3, row 3) against the same three columns

    measured from the un-merged header row -- not a fixed pixel number, which
    would just be this test's own guess restated.
    """
    _table, boxes, _sheet, _shot = _render_and_extract(tmp_path)
    header_cols = {box["col"]: box for box in boxes if box["row"] == 0}
    three_cols_width = (header_cols[2]["x"] + header_cols[2]["w"]) - header_cols[0]["x"]
    total_label = next(box for box in boxes if box["row"] == 3 and box["col"] == 0)
    assert total_label["colspan"] == 3
    assert total_label["w"] == pytest.approx(three_cols_width, abs=1.5)
    assert total_label["x"] == pytest.approx(header_cols[0]["x"], abs=1.5)


@pytest.mark.skipif(not _browser_ready(), reason="no Chromium/Playwright available")
def test_a_rowspan_cells_box_is_as_tall_as_the_rows_it_spans(tmp_path):
    """The stub "3" cell (rowspan=2, rows 4-5) against those two rows' own height."""
    _table, boxes, _sheet, _shot = _render_and_extract(tmp_path)
    stub = next(box for box in boxes if box["row"] == 4 and box["col"] == 0)
    assert stub["rowspan"] == 2
    row5_cell = next(box for box in boxes if box["row"] == 5)
    span_bottom = row5_cell["y"] + row5_cell["h"]
    assert stub["y"] == pytest.approx(
        next(box for box in boxes if box["row"] == 4 and box["col"] == 1)["y"], abs=1.5)
    assert stub["y"] + stub["h"] == pytest.approx(span_bottom, abs=1.5)


@pytest.mark.skipif(not _browser_ready(), reason="no Chromium/Playwright available")
def test_every_box_with_text_sits_on_visible_ink(tmp_path):
    """Right-sized and right-placed is not enough -- there has to be something

    drawn under it. `_has_ink` mirrors `tools/check_boxes.py`'s own check:
    contrast against the *local* median rather than the page's, so a coloured
    cell (row 2's `bg="#fff3cd"`) is judged against its own background and
    not against the white of the rest of the sheet.
    """
    import numpy as np
    from PIL import Image

    table, boxes, sheet, shot = _render_and_extract(tmp_path)
    image = np.array(Image.open(shot).convert("L"))
    ratio = image.shape[1] / sheet["width"]

    checked = 0
    for box in boxes:
        if not box["text"].strip():
            continue
        x0, y0 = int(box["x"] * ratio) + 1, int(box["y"] * ratio) + 1
        x1 = int((box["x"] + box["w"]) * ratio) - 1
        y1 = int((box["y"] + box["h"]) * ratio) - 1
        if x1 <= x0 or y1 <= y0:
            continue
        patch = image[y0:y1, x0:x1]
        middle = float(np.median(patch))
        contrast = max(middle - float(patch.min()), float(patch.max()) - middle)
        assert contrast > 20, f"{box['kind']!r} row={box['row']} col={box['col']} " \
                              f"{box['text']!r}: no ink under its own box (contrast={contrast:.1f})"
        checked += 1
    assert checked >= 15   # the fixture is rich enough that this catches a real regression
