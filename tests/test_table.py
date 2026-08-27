"""The general table component: every border shape, merges, nesting, labels.

No browser in sight, on purpose -- `render_table` is a pure function of a
`TableSpec`, and every claim this file makes (`Border.rows()` really does
mean "no line ever appears between two columns", a rowspan really does make
the row under it skip that column) is a fact about the HTML string, checkable
without a rasteriser. `tests/test_baseline.py` is where a claim about pixels
belongs; this is where a claim about markup does.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

from components import table as T  # noqa: E402


def cells(html: str, tag: str = "td") -> list[str]:
    """Every `<td ...>...</td>` (or `<th>`) as one string, in document order.

    A small hand-rolled splitter rather than an HTML parser: the markup this
    module writes is regular enough (no nested `<td>` at the top level of the
    split, since a nested table's own cells are never labelled the same way
    -- see `test_a_nested_table_does_not_leak_data_row_labels`) that a parser
    would only add a dependency for no real precision gained.
    """
    return re.findall(rf"<{tag}\b.*?</{tag}>", html, flags=re.DOTALL)


def attr(cell_html: str, name: str) -> str | None:
    match = re.search(rf'{name}="([^"]*)"', cell_html)
    return match.group(1) if match else None


def no_edge(style: str, side: str) -> bool:
    """True when `style` says nothing at all about `border-<side>`.

    Not "`border-<side>:none`" -- since the fix for `Cell.cls`/`Row.cls`
    coexisting with an external stylesheet, an absent edge is *omitted* from
    the inline style rather than forced to `none` (see `_edge` in
    `components/table.py`), so the property must not appear at all.
    """
    return f"border-{side}:" not in style


# --------------------------------------------------------------------- Line


def test_line_rejects_a_zero_or_negative_width():
    with pytest.raises(ValueError):
        T.Line(width=0)
    with pytest.raises(ValueError):
        T.Line(width=-1)


def test_line_rejects_an_unknown_style():
    with pytest.raises(ValueError):
        T.Line(style="groovy")


def test_line_css_uses_the_tables_unit():
    assert T.Line(0.5, "dashed", "#f00").css("mm") == "0.5mm dashed #f00"


# ------------------------------------------------------------------- Border
#
# Each case in the brief, checked as a fact about which of the six lines is
# `None` -- not yet about HTML, because the shape has to be right before the
# rendering of it is worth checking.


def test_grid_has_all_six_lines():
    border = T.Border.grid()
    assert all(getattr(border, edge) is not None for edge in T._ALL_EDGES)


def test_none_has_no_lines():
    border = T.Border.none()
    assert all(getattr(border, edge) is None for edge in T._ALL_EDGES)


def test_frame_is_outer_only():
    border = T.Border.frame()
    assert border.top and border.right and border.bottom and border.left
    assert border.inner_h is None and border.inner_v is None


def test_rows_preset_has_no_vertical_line_anywhere():
    """`Border.rows()`: "không viền dọc" -- never a rule between two columns."""
    border = T.Border.rows()
    assert border.inner_v is None and border.left is None and border.right is None
    assert border.inner_h is not None
    assert border.top is not None and border.bottom is not None


def test_rows_preset_without_outer_drops_the_top_and_bottom_too():
    border = T.Border.rows(outer=False)
    assert border.top is None and border.bottom is None
    assert border.inner_h is not None


def test_columns_preset_has_no_horizontal_line_anywhere():
    """`Border.columns()`: "không viền ngang" -- never a rule under a row."""
    border = T.Border.columns()
    assert border.inner_h is None and border.top is None and border.bottom is None
    assert border.inner_v is not None
    assert border.left is not None and border.right is not None


def test_without_removes_only_the_named_edges():
    border = T.Border.grid().without("left", "right")
    assert border.left is None and border.right is None
    assert border.top is not None and border.inner_h is not None and border.inner_v is not None


def test_without_rejects_an_unknown_edge_name():
    with pytest.raises(ValueError):
        T.Border.grid().without("diagonal")


def test_with_edges_can_both_set_and_clear():
    border = T.Border.none().with_edges(top=T.Line(0.6), inner_h=None)
    assert border.top is not None and border.inner_h is None and border.left is None


# --------------------------------------------------------------- validation


def test_a_cell_rejects_a_non_positive_span():
    with pytest.raises(ValueError):
        T.Cell(colspan=0)
    with pytest.raises(ValueError):
        T.Cell(rowspan=-1)


def test_a_cell_border_override_only_accepts_its_own_four_sides():
    with pytest.raises(ValueError):
        T.Cell(border={"inner_h": None})


def test_a_column_rejects_an_unknown_align():
    with pytest.raises(ValueError):
        T.Column(align="justify")


def test_a_table_rejects_a_row_that_overflows_its_declared_columns():
    with pytest.raises(ValueError):
        T.TableSpec(
            columns=[T.Column(), T.Column()],
            rows=[T.Row.of("a", "b", "c")],
        )


# ------------------------------------------------------------- basic shape


def test_an_empty_table_renders_without_crashing():
    assert "<table" in T.render_table(T.TableSpec())


def test_row_of_wraps_bare_strings_and_bolds_a_header_row():
    row = T.Row.of("A", "B", header=True)
    assert all(isinstance(c, T.Cell) for c in row.cells)
    assert all(c.bold for c in row.cells)
    assert row.header is True


def test_a_short_row_is_padded_to_the_full_column_count():
    spec = T.TableSpec(columns=[T.Column(), T.Column(), T.Column()],
                        rows=[T.Row.of("only one")])
    html = T.render_table(spec)
    row_cells = cells(html)
    assert len(row_cells) == 3
    assert attr(row_cells[1], "data-col") == "1"
    assert attr(row_cells[2], "data-col") == "2"


def test_header_rows_land_in_thead_and_body_rows_in_tbody():
    spec = T.TableSpec(rows=[T.Row.of("H1", "H2", header=True), T.Row.of("a", "b")])
    html = T.render_table(spec)
    assert "<thead>" in html and "</thead>" in html
    thead, _, tbody = html.partition("</thead>")
    assert "H1" in thead and "H2" in thead
    assert "a" in tbody and "b" in tbody


def test_in_thead_places_a_plain_row_in_thead_without_making_it_a_header():
    """The column-number row a VAT form prints under its titles: <td>, not

    bold, but still has to repeat with the header it sits under.
    """
    spec = T.TableSpec(rows=[
        T.Row.of("A", "B", header=True),
        T.Row([T.Cell("1"), T.Cell("2")], in_thead=True),
        T.Row.of("x", "y"),
    ])
    html = T.render_table(spec)
    thead, _, tbody = html.partition("</thead>")
    assert "1" in thead and "2" in thead      # placed in thead...
    colnum_cell = cells(thead, "td")[0]       # ...but as <td>, not <th>
    assert "font-weight:bold" not in attr(colnum_cell, "style")
    assert "x" in tbody and "y" in tbody


def test_in_thead_row_is_exempt_from_zebra():
    spec = T.TableSpec(
        zebra=("#fff", "#eee"),
        rows=[T.Row.of("H", header=True), T.Row([T.Cell("1")], in_thead=True),
              T.Row.of("a"), T.Row.of("b")],
    )
    html = T.render_table(spec)
    colnum_cell = cells(html.partition("</thead>")[0], "td")[0]
    assert "background" not in attr(colnum_cell, "style")
    first_body, second_body = cells(html.partition("<tbody>")[2])
    assert "background:#fff" in attr(first_body, "style")   # zebra restarts at 0 in tbody
    assert "background:#eee" in attr(second_body, "style")


def test_repeat_header_false_sets_table_row_group_inline():
    spec = T.TableSpec(rows=[T.Row.of("H", header=True)], repeat_header=False)
    html = T.render_table(spec)
    assert '<thead style="display:table-row-group">' in html


def test_valign_defaults_to_top_when_left_unset():
    spec = T.TableSpec(rows=[T.Row.of("a")])
    assert "vertical-align:top" in attr(cells(T.render_table(spec))[0], "style")


def test_valign_omitted_when_explicitly_none():
    """Unlike align, valign is this component's opinion, not the data's --

    passing `None` explicitly says "no opinion, defer to whatever CSS the
    page already has" rather than falling back to the "top" default.
    """
    spec = T.TableSpec(columns=[T.Column(valign=None)], rows=[T.Row.of("a")])
    style = attr(cells(T.render_table(spec))[0], "style")
    assert "vertical-align" not in style
    assert "text-align:left" in style   # align, unlike valign, is never omitted


def test_escaping_and_newlines():
    spec = T.TableSpec(rows=[T.Row.of("<b>&\nsecond line")])
    html = T.render_table(spec)
    assert "&lt;b&gt;&amp;<br>second line" in html
    assert "<b>" not in html.split(">", 1)[1]        # the literal tag was escaped, not rendered


def test_html_true_cell_is_inserted_unescaped():
    spec = T.TableSpec(rows=[T.Row([T.Cell("<em>hi</em>", html=True)])])
    assert "<em>hi</em>" in T.render_table(spec)


# --------------------------------------------------------- border rendering


def test_borderless_table_draws_no_line_on_any_cell():
    spec = T.TableSpec(border=T.Border.none(),
                        rows=[T.Row.of("a", "b"), T.Row.of("c", "d")])
    html = T.render_table(spec)
    for cell_html in cells(html):
        style = attr(cell_html, "style")
        assert no_edge(style, "top")
        assert no_edge(style, "right")
        assert no_edge(style, "bottom")
        assert no_edge(style, "left")


def test_no_vertical_borders_means_no_side_ever_carries_a_line():
    """The rendered fact behind `Border.rows()`: not one cell's left/right is ruled."""
    spec = T.TableSpec(border=T.Border.rows(0.4),
                        rows=[T.Row.of("a", "b", "c"), T.Row.of("d", "e", "f")])
    html = T.render_table(spec)
    for cell_html in cells(html):
        style = attr(cell_html, "style")
        assert no_edge(style, "left")
        assert no_edge(style, "right")
    # but a horizontal rule genuinely appears between the two rows
    first_row_cell, second_row_cell = cells(html)[0], cells(html)[3]
    assert "border-bottom:0.4mm solid #000" in attr(first_row_cell, "style")
    assert "border-top:0.4mm solid #000" in attr(second_row_cell, "style")


def test_no_horizontal_borders_means_no_row_boundary_is_ever_ruled():
    spec = T.TableSpec(border=T.Border.columns(0.4),
                        rows=[T.Row.of("a", "b"), T.Row.of("c", "d")])
    html = T.render_table(spec)
    for cell_html in cells(html):
        style = attr(cell_html, "style")
        assert no_edge(style, "top")
        assert no_edge(style, "bottom")
    left_cell, right_cell = cells(html)[0], cells(html)[1]
    assert "border-right:0.4mm solid #000" in attr(left_cell, "style")
    assert "border-left:0.4mm solid #000" in attr(right_cell, "style")


def test_no_side_borders_bleeds_to_the_margin_but_keeps_everything_else():
    """`Border.grid().without("left", "right")`: "không viền hai bên"."""
    spec = T.TableSpec(border=T.Border.grid().without("left", "right"),
                        rows=[T.Row.of("a", "b"), T.Row.of("c", "d")])
    html = T.render_table(spec)
    left_col = [cells(html)[0], cells(html)[2]]
    right_col = [cells(html)[1], cells(html)[3]]
    for cell_html in left_col:
        assert no_edge(attr(cell_html, "style"), "left")
    for cell_html in right_col:
        assert no_edge(attr(cell_html, "style"), "right")
    # top/bottom and the inner rules are untouched
    assert "border-top:0.3mm solid #000" in attr(cells(html)[0], "style")
    assert "border-right:0.3mm solid #000" in attr(cells(html)[0], "style")  # inner_v, not the edge


def test_no_top_bottom_borders_opens_the_table_vertically():
    """`Border.grid().without("top", "bottom")`: "không viền trên dưới"."""
    spec = T.TableSpec(border=T.Border.grid().without("top", "bottom"),
                        rows=[T.Row.of("a"), T.Row.of("b")])
    html = T.render_table(spec)
    top_row, bottom_row = cells(html)
    assert no_edge(attr(top_row, "style"), "top")
    assert no_edge(attr(bottom_row, "style"), "bottom")


def test_outer_frame_can_be_heavier_than_the_inner_rules():
    """A classic ruled-form look: thick box, thin rules inside it."""
    spec = T.TableSpec(
        border=T.Border(top=T.Line(1.5), right=T.Line(1.5), bottom=T.Line(1.5),
                         left=T.Line(1.5), inner_h=T.Line(0.25), inner_v=T.Line(0.25)),
        rows=[T.Row.of("a", "b"), T.Row.of("c", "d")],
    )
    html = T.render_table(spec)
    top_left = cells(html)[0]
    assert "border-top:1.5mm solid #000" in attr(top_left, "style")     # outer
    assert "border-right:0.25mm solid #000" in attr(top_left, "style")  # inner


def test_a_cell_border_override_wins_over_the_table_shape():
    spec = T.TableSpec(
        border=T.Border.none(),
        rows=[T.Row([T.Cell("total", border={"top": T.Line(0.8)})])],
    )
    style = attr(cells(T.render_table(spec))[0], "style")
    assert "border-top:0.8mm solid #000" in style
    assert no_edge(style, "left")            # untouched sides stay at the table's shape


def test_header_divider_draws_once_under_the_last_header_row_only():
    spec = T.TableSpec(
        border=T.Border.none(),
        header_divider=T.Line(0.5, color="#333"),
        rows=[T.Row.of("g1", "g2", header=True), T.Row.of("a", "b", header=True),
              T.Row.of("x", "y")],
    )
    html = T.render_table(spec)
    row0, row1 = cells(html, "th")[0:2], cells(html, "th")[2:4]
    body = cells(html, "td")
    for c in row0:
        assert no_edge(attr(c, "style"), "bottom")
    for c in row1:
        assert "border-bottom:0.5mm solid #333" in attr(c, "style")
    for c in body:
        assert no_edge(attr(c, "style"), "top")   # the divider is a bottom, not a shared line


# ------------------------------------------------------ class passthrough
#
# The escape hatch a family with its own stylesheet uses: geometry and labels
# from this module, visual styling from a `.grand`/`.tlabel`-style class the
# page already defines.


def test_cell_cls_is_emitted_alongside_the_inline_style():
    spec = T.TableSpec(rows=[T.Row([T.Cell("total", cls="tlabel", align="right")])])
    cell_html = cells(T.render_table(spec))[0]
    assert attr(cell_html, "class") == "tlabel"
    assert attr(cell_html, "style")            # geometry/label styling is still there


def test_row_cls_is_emitted_on_the_tr():
    spec = T.TableSpec(rows=[T.Row.of("a", "b", cls="grand")])
    html = T.render_table(spec)
    tr = re.search(r"<tr[^>]*>", html).group(0)
    assert 'class="grand"' in tr


def test_a_cell_with_no_border_says_nothing_about_border_at_all():
    """The fact that makes `cls` safe: an unset side is omitted, not `none`.

    A `none` inline border would outrank ANY external rule on `.grand`/
    `.tlabel` regardless of specificity; omitting the property lets that
    external rule -- if the page defines one -- be the only thing that draws.
    """
    spec = T.TableSpec(border=T.Border.none(),
                        rows=[T.Row([T.Cell("x", cls="tlabel")])])
    style = attr(cells(T.render_table(spec))[0], "style")
    assert "border" not in style


# --------------------------------------------------------------- colour


def test_zebra_stripes_body_rows_only_starting_from_the_first_body_row():
    spec = T.TableSpec(
        zebra=("#fff", "#eee"),
        rows=[T.Row.of("H", header=True), T.Row.of("a"), T.Row.of("b"), T.Row.of("c")],
    )
    html = T.render_table(spec)
    header, r1, r2, r3 = cells(html, "th")[0], *cells(html, "td")
    assert "background" not in attr(header, "style")
    assert "background:#fff" in attr(r1, "style")
    assert "background:#eee" in attr(r2, "style")
    assert "background:#fff" in attr(r3, "style")


def test_zebra_parity_does_not_depend_on_a_shared_pages_row_count():
    """A second table on a page must not inherit odd/even from the first one.

    Regression case: zebra used to key off the page-wide `data-row` number,
    so a table starting at `data-row=7` came out striped backwards purely
    because of an unrelated table earlier on the same sheet.
    """
    class OffsetCounter:
        def __init__(self, start):
            self._next = start

        def take(self):
            row = self._next
            self._next += 1
            return row

    spec = T.TableSpec(zebra=("#fff", "#eee"), rows=[T.Row.of("a"), T.Row.of("b")])
    fresh = T.render_table(spec, rows=OffsetCounter(0))
    offset = T.render_table(spec, rows=OffsetCounter(7))
    first_fresh, second_fresh = cells(fresh)
    first_offset, second_offset = cells(offset)
    assert attr(first_fresh, "style").split("background")[1] \
        == attr(first_offset, "style").split("background")[1]
    assert attr(second_fresh, "style").split("background")[1] \
        == attr(second_offset, "style").split("background")[1]
    # but the labels themselves really did shift with the shared counter
    assert attr(first_offset, "data-row") == "7"
    assert attr(second_offset, "data-row") == "8"


def test_precedence_cell_then_row_then_zebra():
    spec = T.TableSpec(
        zebra=("#fff", "#eee"),
        rows=[T.Row([T.Cell("a", bg="#f00")], bg="#00f"),
              T.Row([T.Cell("b")], bg="#00f"),
              T.Row.of("c")],
    )
    html = T.render_table(spec)
    a, b, c = cells(html)
    assert "background:#f00" in attr(a, "style")    # cell wins
    assert "background:#00f" in attr(b, "style")    # row wins over zebra
    assert "background:#fff" in attr(c, "style")    # zebra is what's left (3rd body row -> even)


# --------------------------------------------------------- merges & nesting


def test_colspan_and_rowspan_attributes_are_written():
    spec = T.TableSpec(rows=[T.Row([T.Cell("wide", colspan=2, rowspan=2)]),
                             T.Row([]), T.Row.of("x", "y")])
    html = T.render_table(spec)
    wide = cells(html)[0]
    assert attr(wide, "colspan") == "2"
    assert attr(wide, "rowspan") == "2"


def test_a_rowspan_makes_the_row_below_skip_its_columns():
    """Column 0, spanned from row 0, must not get a second `<td>` in row 1."""
    spec = T.TableSpec(
        columns=[T.Column(), T.Column(), T.Column()],
        rows=[T.Row([T.Cell("stub", rowspan=2), T.Cell("a"), T.Cell("b")]),
              T.Row([T.Cell("c"), T.Cell("d")])],
    )
    html = T.render_table(spec)
    row2 = cells(html)[3:]                     # 3 cells in row 0, then row 1's own
    assert [attr(c, "data-col") for c in row2] == ["1", "2"]
    assert "c" in row2[0] and "d" in row2[1]


def test_a_nested_table_renders_inside_its_cell_and_does_not_label_its_own_cells():
    inner = T.TableSpec(rows=[T.Row.of("x", "y")])
    outer = T.TableSpec(rows=[T.Row([T.Cell(inner)])])
    html = T.render_table(outer)
    outer_cell = cells(html)[0]
    assert "<table" in outer_cell                  # the nested table is inside the outer <td>
    assert "data-cell" in outer_cell.split("<table", 1)[0] or attr(outer_cell, "data-cell") == ""
    inner_start = outer_cell.index("<table", 1)
    assert "data-cell" not in outer_cell[inner_start:]
    assert "data-row" not in outer_cell[inner_start:]


# --------------------------------------------------------------- labelling


def test_data_row_col_kind_match_the_sheets_base_contract():
    spec = T.TableSpec(rows=[T.Row([T.Cell("v", kind="invoice.field")])])
    cell_html = cells(T.render_table(spec))[0]
    assert attr(cell_html, "data-cell") == "invoice.field"
    assert attr(cell_html, "data-row") == "0"
    assert attr(cell_html, "data-col") == "0"


def test_label_cells_false_omits_the_data_attributes_entirely():
    spec = T.TableSpec(rows=[T.Row.of("a")])
    html = T.render_table(spec, label_cells=False)
    assert "data-cell" not in html and "data-row" not in html and "data-col" not in html


# --------------------------------------------------------------- widths


def test_resolve_widths_leaves_a_fully_unset_table_to_the_browser():
    assert T._resolve_widths([T.Column(), T.Column()]) == [None, None]


def test_resolve_widths_shares_the_remainder_and_absorbs_rounding_drift():
    widths = T._resolve_widths([T.Column(30), T.Column(), T.Column(), T.Column()])
    assert widths[0] == 30
    assert sum(widths) == pytest.approx(100.0)
    assert widths[1] == pytest.approx(widths[2]) == pytest.approx(widths[3], abs=0.01)


def test_explicit_widths_produce_a_colgroup():
    spec = T.TableSpec(columns=[T.Column(40), T.Column(60)], rows=[T.Row.of("a", "b")])
    html = T.render_table(spec)
    assert "<colgroup>" in html
    assert 'width:40' in html and 'width:60' in html


def test_no_widths_at_all_produce_no_colgroup():
    spec = T.TableSpec(rows=[T.Row.of("a", "b")])
    assert "<colgroup>" not in T.render_table(spec)


# --------------------------------------------------------------- helpers


def test_blank_row_makes_ncols_empty_cells():
    row = T.blank_row(4, min_height=6.0)
    assert len(row.cells) == 4
    assert row.min_height == 6.0


def test_header_group_rows_spans_the_group_and_rowspans_the_rest():
    columns = [T.Column() for _ in range(4)]
    titles = ["STT", "Tên", "SL", "Tiền"]
    top, bottom = T.header_group_rows(columns, titles, [(2, 3, "Nguồn thanh toán")])
    # column 0 and 1 reach down through both rows; columns 2-3 merge under one title
    assert top.cells[0].rowspan == 2 and top.cells[1].rowspan == 2
    assert top.cells[2].colspan == 2
    assert [c.content for c in bottom.cells] == ["SL", "Tiền"]
