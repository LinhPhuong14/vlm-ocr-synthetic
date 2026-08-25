"""A general-purpose ruled table, driven entirely by attributes.

Every family in `sheets/` hand-writes its own table CSS today: `statutory.py`
carries `table.items th,table.items td{border:.3mm solid ...}` baked into an
f-string, `lodging.py` and `medical.py` each carry their own version of the
same idea. Adding a table with a different border shape means writing CSS,
not setting a field -- and "no vertical rules, thick outer frame, zebra body
rows" is not a shape any of them happen to draw. This module is that missing
piece: a table is a `TableSpec`, `render_table` turns it into a self-contained
`<table>` (inline styles, no external stylesheet to keep in sync), and every
shape below is a constructor call, not a CSS rule.

    from components.table import Border, Cell, Column, Row, TableSpec, render_table

    spec = TableSpec(
        columns=[Column(30), Column(), Column(25, align="right")],
        border=Border.rows(0.3),                       # no vertical rules at all
        zebra=("#fff", "#f4f4f4"),
        rows=[
            Row.of("Mặt hàng", "Ghi chú", "Thành tiền", header=True),
            Row.of("Phở bò", "", "45.000"),
            Row.of("Trà đá", "", "5.000"),
        ],
    )
    html = render_table(spec)

**The border model.** A ruled table draws at most six lines: its own four
edges (`top`, `right`, `bottom`, `left`) and two families of rule *inside*
it (`inner_h` between every pair of rows, `inner_v` between every pair of
columns). Every case the brief asks for is one or two of these six set to
`None`:

| wanted                                   | how                                    |
| ----------------------------------------- | --------------------------------------- |
| bordered (full grid)                      | `Border.grid()`                         |
| borderless                                | `Border.none()`                         |
| no vertical rules (ledger style)          | `Border.rows()`                         |
| no horizontal rules                       | `Border.columns()`                      |
| no left/right edge (bleeds to the margin) | `Border.grid().without("left","right")` |
| no top/bottom edge                        | `Border.grid().without("top","bottom")` |
| outer frame only, unruled inside          | `Border.frame()`                        |
| a rule under the header, nothing else     | `TableSpec(header_divider=Line(...))`   |

A cell may override any of its own four sides on top of the table's shape
(`Cell.border`), which is the escape hatch for the one row that needs a
heavier rule under it, or a stub column with no rule under its own name.

**Everything else a table is asked to do** -- merged cells, nested tables,
row/cell colour, zebra banding, per-column width and alignment, a header
that does or does not repeat when a print engine paginates -- is a field on
`TableSpec`/`Row`/`Cell`, listed where each dataclass is defined below.

**Compatibility, not a dependency.** `sheets/base.py` reads cell geometry off
`data-cell`/`data-row`/`data-col` (`page.CELL_REGIONS_JS`) and expects a
page-wide row counter so two tables on one sheet do not share `data-row`
numbers (`sheets.base.Rows`). This module emits the same three attributes
under the same names and accepts any counter object with a `.take() -> int`
method -- so a `sheets.base.Rows()` instance drops straight into `rows=`
-- without importing anything from `sheets`, so it stays usable standalone
(a preview page, a future non-A4 renderer, `tables.py`'s structure generator)
and a family module can adopt it without a new dependency edge.

**What this module deliberately does not do.** No existing `sheets/*.py`
family was rewired to use it -- each is backed by exact-pixel golden hashes
(`make baseline-verify`) and hundreds of passing tests, and swapping their
table CSS for this renderer's inline styles would move pixels for no
functional gain. This is the primitive a *new* layout reaches for, and the
one an existing family can migrate to deliberately, on its own diff, with a
baseline recapture. Rounded corners are also left out: CSS `border-radius`
on a collapsed table is unreliable across engines, and every reference form
in `samples/` is square-cornered anyway -- a real gap would be a `Border`
field, a fake one would be a feature nobody's paper has.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from html import escape
from typing import Protocol, Union

_ALIGN = {"left", "right", "center"}
_VALIGN = {"top", "middle", "bottom"}
_BORDER_STYLES = {"solid", "dashed", "dotted", "double"}
_CELL_EDGES = ("top", "right", "bottom", "left")
_ALL_EDGES = _CELL_EDGES + ("inner_h", "inner_v")


class RowCounter(Protocol):
    """What a page-wide row counter needs to provide -- `sheets.base.Rows` already does."""

    def take(self) -> int: ...


class _LocalCounter:
    """The row counter a standalone table gets when the caller supplies none."""

    def __init__(self) -> None:
        self._next = 0

    def take(self) -> int:
        row = self._next
        self._next += 1
        return row


# --------------------------------------------------------------------------
# the border model


@dataclass(frozen=True)
class Line:
    """One drawn edge: a width, a CSS border-style, and a colour.

    `width` is in the table's own `unit` (millimetres by default, matching
    every A4 sheet in `generators/html/sheets/`), the same reasoning
    `rulebase.layout.Mark.weight` follows for the character grid -- a
    renderer-agnostic physical size rather than a pixel count nobody chose.

    `style="double"` needs enough width to show two lines rather than one
    thick one; browsers generally want upwards of ~0.8mm (about 3px) before
    the gap is visible. Requested here, not enforced -- a hairline double
    rule collapsing to a single line is a rendering quirk to know about, not
    a reason to reject the value.
    """

    width: float = 0.3
    style: str = "solid"
    color: str = "#000"

    def __post_init__(self) -> None:
        if self.style not in _BORDER_STYLES:
            raise ValueError(f"unknown border style {self.style!r}; have {sorted(_BORDER_STYLES)}")
        if self.width <= 0:
            raise ValueError(f"a Line must have positive width, got {self.width!r}")

    def css(self, unit: str) -> str:
        return f"{self.width:g}{unit} {self.style} {self.color}"


@dataclass(frozen=True)
class Border:
    """The six lines a ruled table can draw -- see the module docstring's table.

    Each of the six is a `Line` or `None`. Building one from scratch almost
    always starts at a classmethod (`none`, `grid`, `frame`, `rows`,
    `columns`) and is refined with `.without(...)` or `replace(border,
    inner_v=Line(0.5))` for the one edge that needs to differ from the rest.
    """

    top: Line | None = None
    right: Line | None = None
    bottom: Line | None = None
    left: Line | None = None
    inner_h: Line | None = None   # a rule between every pair of rows
    inner_v: Line | None = None   # a rule between every pair of columns

    @classmethod
    def none(cls) -> "Border":
        """Không viền: no line anywhere."""
        return cls()

    @classmethod
    def grid(cls, width: float = 0.3, style: str = "solid", color: str = "#000") -> "Border":
        """Có viền đầy đủ: the outer frame and every inner rule, all one line."""
        line = Line(width, style, color)
        return cls(line, line, line, line, line, line)

    @classmethod
    def frame(cls, width: float = 0.3, style: str = "solid", color: str = "#000") -> "Border":
        """Chỉ viền ngoài: a box around the table, nothing ruled inside it."""
        line = Line(width, style, color)
        return cls(line, line, line, line, None, None)

    @classmethod
    def rows(cls, width: float = 0.3, style: str = "solid", color: str = "#000",
              *, outer: bool = True) -> "Border":
        """Không viền dọc: a rule under every row, never between two columns."""
        line = Line(width, style, color)
        edge = line if outer else None
        return cls(top=edge, bottom=edge, left=None, right=None, inner_h=line, inner_v=None)

    @classmethod
    def columns(cls, width: float = 0.3, style: str = "solid", color: str = "#000",
                 *, outer: bool = True) -> "Border":
        """Không viền ngang: a rule between every column, never under a row."""
        line = Line(width, style, color)
        edge = line if outer else None
        return cls(left=edge, right=edge, top=None, bottom=None, inner_h=None, inner_v=line)

    def without(self, *edges: str) -> "Border":
        """This border with the named edges removed.

        Composes with any of the constructors above -- `Border.grid().without
        ("left", "right")` is a fully ruled table that bleeds to the page
        margin, `Border.grid().without("top", "bottom")` opens the top and
        bottom instead. Names: top, right, bottom, left, inner_h, inner_v. An
        unknown name raises rather than silently keeping a line nobody meant
        to keep.
        """
        unknown = set(edges) - set(_ALL_EDGES)
        if unknown:
            raise ValueError(f"unknown border edge(s) {sorted(unknown)}; have {_ALL_EDGES}")
        return replace(self, **{edge: None for edge in edges})

    def with_edges(self, **edges: Line | None) -> "Border":
        """This border with the named edges set (or cleared, with `None`)."""
        unknown = set(edges) - set(_ALL_EDGES)
        if unknown:
            raise ValueError(f"unknown border edge(s) {sorted(unknown)}; have {_ALL_EDGES}")
        return replace(self, **edges)


# --------------------------------------------------------------------------
# the grid: columns, cells, rows


@dataclass
class Column:
    """One column's share of the table width and its default alignment.

    `width` is a percentage of the table; `None` shares whatever is left
    over equally with every other unset column, exactly as
    `sheets.base.columns_of` resolves a layout's character widths -- one
    column written with no width takes the rest, so a table works whether it
    has two columns or eight without a second set of numbers. Leaving every
    column unset (the default) leaves column widths to the browser entirely,
    which is the right choice for a small key/value table where a forced
    50/50 split would look wrong.

    `align` always resolves to something and is always written inline --
    every column's text-alignment is a real decision (money runs right, a
    name runs left) and never a thing to leave ambient, the same way
    `sheets.base.align_class` always picked a class before this module
    existed. `valign` is different: unlike alignment, "top" is this
    component's own opinion about what looks right, not a fact about the
    data, and a page with its own idea (a stylesheet already setting
    `vertical-align` on the class in `Cell.cls`/`Row.cls`, or wanting the
    browser's ordinary middle-of-the-cell default) needs a way to say so.
    Passed explicitly as `None`, it is *omitted* from the inline style
    -- the same "say nothing" `Border` uses -- rather than defaulting to
    `"top"` the way leaving it unset does.
    """

    width: float | None = None
    align: str = "left"
    valign: str | None = "top"
    nowrap: bool = False

    def __post_init__(self) -> None:
        if self.align not in _ALIGN:
            raise ValueError(f"unknown align {self.align!r}; have {sorted(_ALIGN)}")
        if self.valign is not None and self.valign not in _VALIGN:
            raise ValueError(f"unknown valign {self.valign!r}; have {sorted(_VALIGN)}")


CellContent = Union[str, "TableSpec"]


@dataclass
class Cell:
    """One `<td>`/`<th>`. `align`/`valign`/`bold`/`nowrap` are `None` = inherit.

    `content` is plain text by default (escaped, `\\n` becomes `<br>` so a
    wrapped address is one cell and not a paragraph of markup). Pass another
    `TableSpec` to nest a table inside this cell -- `render_table` recurses on
    it -- or set `html=True` to insert `content` as markup already trusted by
    the caller (both paths skip escaping; a nested `TableSpec` is never run
    through `escape`, only literal-string content is).

    `border` overrides this cell's own four sides on top of whatever the
    table's `Border` computes for its position -- only the sides *named* in
    the dict change; a key mapped to `None` explicitly removes that side
    rather than leaving it alone, which is why an unset key (not present at
    all) and an explicit `None` value mean different things here. Only
    top/right/bottom/left are valid keys: `inner_h`/`inner_v` describe the
    table, not one cell, and are rejected.

    `cls` is a plain CSS class, carried onto the `<td>`/`<th>` alongside
    everything above rather than instead of it -- the escape hatch for a page
    that already has a stylesheet targeting `.tlabel` or `.grand` and wants
    the geometry (spans, labels, computed borders) from this module without
    giving up a rule it already has. The two do not fight over borders: an
    unset side here is *omitted* from the inline style, not forced to `none`
    (see `Border`), so an external `border-bottom` on that class still shows.
    """

    content: CellContent = ""
    colspan: int = 1
    rowspan: int = 1
    align: str | None = None
    valign: str | None = None
    bold: bool | None = None
    italic: bool = False
    nowrap: bool | None = None
    bg: str | None = None
    color: str | None = None
    scale: float = 1.0
    kind: str = ""                              # data-cell label; "" is a valid, unlabelled cell
    cls: str = ""                                # a CSS class, in ADDITION to the inline style
    html: bool = False
    border: dict[str, Line | None] | None = None
    pad: tuple[float, float] | None = None       # (vertical, horizontal), table's unit

    def __post_init__(self) -> None:
        if self.colspan < 1 or self.rowspan < 1:
            raise ValueError(f"colspan/rowspan must be >= 1, got {self.colspan}/{self.rowspan}")
        if self.align is not None and self.align not in _ALIGN:
            raise ValueError(f"unknown align {self.align!r}; have {sorted(_ALIGN)}")
        if self.valign is not None and self.valign not in _VALIGN:
            raise ValueError(f"unknown valign {self.valign!r}; have {sorted(_VALIGN)}")
        if self.border:
            unknown = set(self.border) - set(_CELL_EDGES)
            if unknown:
                raise ValueError(
                    f"a cell border only names its own sides; unknown {sorted(unknown)}, "
                    f"have {_CELL_EDGES}")


@dataclass
class Row:
    """One `<tr>`.

    `header=True` makes every cell bold `<th>` by default, puts the row in
    `<thead>` instead of `<tbody>`, and marks it as part of the header band
    that `zebra` skips and `TableSpec.header_divider` draws its rule under
    (the *last* row of a leading run of header rows, if there is more than
    one).

    `in_thead` decouples *where a row lands* from *what its cells look
    like*, for the row `header=True` cannot express: a printed form's
    header band sometimes carries a row that is plain `<td>`, unbolded, and
    still has to sit in `<thead>` so it repeats with the titles above it --
    the "1 2 3 ... = 4x6" column-number row under a VAT form's headings, for
    one. Leave it `None` (the default) to follow `header`; set it to `True`
    or `False` to place the row regardless. A row placed in `<thead>` this
    way must still be *authored* immediately after the rows it belongs
    with: `<thead>` always precedes `<tbody>` in the DOM no matter what
    order `TableSpec.rows` lists them in, so a mistimed `in_thead=True`
    visually moves a row to the top of the table rather than leaving it
    where it was written.

    `cls` is a CSS class on the `<tr>`, same escape hatch as `Cell.cls`.
    """

    cells: list[Cell] = field(default_factory=list)
    bg: str | None = None
    header: bool = False
    min_height: float | None = None    # table's unit
    cls: str = ""
    in_thead: bool | None = None

    @classmethod
    def of(klass, *cells: "str | Cell", header: bool = False, **kwargs) -> "Row":
        """A row from plain strings (wrapped as `Cell(text)`) or ready-made cells.

        `Row.of("Mặt hàng", "Số lượng", "Thành tiền", header=True)` -- the
        common case needs no `Cell(...)` boilerplate at all; mix in a real
        `Cell` wherever one entry needs a colspan or a colour the rest don't.
        Extra keywords (`cls=`, `bg=`, ...) pass straight through to `Row` --
        named `klass` rather than the usual `cls` here so that `cls=` can mean
        the CSS class on the resulting row, not collide with the classmethod's
        own first argument.
        """
        made = [Cell(c, bold=True if header else None) if isinstance(c, str) else c
                for c in cells]
        return klass(made, header=header, **kwargs)


def blank_row(ncols: int, *, min_height: float | None = None, bg: str | None = None) -> Row:
    """An empty row of `ncols` cells -- a form's pre-printed blank line."""
    return Row([Cell() for _ in range(ncols)], bg=bg, min_height=min_height)


def header_group_rows(columns: list[Column], titles: list[str],
                       groups: list[tuple[int, int, str]]) -> list["Row"]:
    """Two header rows from flat column titles plus a run of grouped ones.

    `groups` is `(first_col, last_col, title)` triples -- `(3, 6, "Nguồn
    thanh toán")` for four columns sharing one heading, exactly the shape
    `header_groups:` names in a layout file. Every column outside a group
    reaches down through both rows instead (`rowspan=2`); working that out by
    hand is the fiddly part `sheets.base._header_rows` exists to avoid, and
    this is the same arithmetic generalised off one layout file.
    """
    ncols = len(columns)
    ordered = sorted(groups)
    grouped = {c for start, end, _ in groups for c in range(start, end + 1)}
    top: list[Cell] = []
    col = 0
    while col < ncols:
        here = next((g for g in ordered if g[0] == col), None)
        if here:
            start, end, title = here
            top.append(Cell(title, colspan=end - start + 1, align="center"))
            col = end + 1
        else:
            top.append(Cell(titles[col] if col < len(titles) else "", rowspan=2))
            col += 1
    bottom = [Cell(titles[c] if c < len(titles) else "") for c in sorted(grouped)]
    return [Row(top, header=True), Row(bottom, header=True)]


# --------------------------------------------------------------------------
# the table


@dataclass
class TableSpec:
    """A whole table: its rows, its columns, and how it is ruled and coloured.

    `zebra` is `(even, odd)` background colours applied to body rows only
    (never the header); a cell's own `bg`, then its row's `bg`, then zebra,
    in that order of precedence -- the same "most specific wins" rule
    `Cell.border` follows for edges.

    `header_divider` forces a bottom rule under the last consecutive header
    row regardless of what `border.inner_h`/`border.bottom` would otherwise
    draw there -- the shape a plain report table wants: no grid at all,
    just one line separating the titles from the body.

    `unit` is the physical unit every `Line.width`/`pad`/`Row.min_height` is
    written in; `"mm"` matches the A4 sheets in `sheets/`, `"px"` suits a
    screen-only preview. `width` is a raw CSS width for the `<table>` itself
    ("100%" to fill its container, "60mm" for a fixed-size table dropped
    inside a cell, "auto" to shrink to its content).
    """

    rows: list[Row] = field(default_factory=list)
    columns: list[Column] = field(default_factory=list)
    border: Border = field(default_factory=Border.grid)
    header_divider: Line | None = None
    zebra: tuple[str, str] | None = None
    bg: str | None = None
    width: str = "100%"
    unit: str = "mm"
    font_family: str | None = None
    font_size: str | None = None
    cls: str = ""
    caption: str = ""
    repeat_header: bool = True

    def __post_init__(self) -> None:
        if self.columns:
            ncols = len(self.columns)
            for r, row in enumerate(self.rows):
                span = sum(c.colspan for c in row.cells)
                if span > ncols:
                    raise ValueError(
                        f"row {r} claims {span} columns across {len(row.cells)} cells, "
                        f"but the table has {ncols}")


# --------------------------------------------------------------------------
# rendering


def _infer_ncols(rows: list[Row]) -> int:
    return max((sum(c.colspan for c in row.cells) for row in rows), default=0)


def _resolve_widths(columns: list[Column]) -> list[float | None]:
    """One percentage per column, or all-`None` to leave sizing to the browser."""
    if not columns or all(c.width is None for c in columns):
        return [None] * len(columns)
    fixed = sum(c.width for c in columns if c.width)
    flexible = [c for c in columns if c.width is None]
    spare = max(100.0 - fixed, 0.0)
    share = spare / len(flexible) if flexible else 0.0
    widths = [c.width if c.width is not None else share for c in columns]
    # The first flexible column (or the last column, if none is flexible)
    # absorbs the rounding, so the row sums to 100 and no engine has to
    # invent the remainder -- same fix `columns_of` applies.
    drift = 100.0 - sum(widths)
    target = columns.index(flexible[0]) if flexible else len(columns) - 1
    widths[target] += drift
    return widths


def _edge(line: Line | None, unit: str) -> str | None:
    """The inline `border-<side>` value for one edge, or `None` to say nothing.

    Saying nothing -- not `border-top:none` -- is what lets `Cell.cls`/
    `Row.cls` share a side with an external stylesheet: an inline `none`
    would win over any CSS rule on that class regardless of what drew it,
    because an inline style always outranks a selector. A `Border` with a
    genuinely absent line (`Border.none()`, an edge dropped by `.without()`)
    and a table with no surrounding stylesheet at all render identically
    either way -- the difference only matters, and only helps, when there
    *is* a class-based rule waiting to be deferred to.
    """
    return line.css(unit) if line else None


def _computed_border(border: Border, r: int, r1: int, c0: int, c1: int,
                      nrows: int, ncols: int) -> dict[str, Line | None]:
    """The four sides a cell gets from the table's shape alone, before any override.

    `r`/`r1` are the cell's row extent (`r1` exclusive, so a rowspan of 3
    starting at row 2 is `r=2, r1=5`); `c0`/`c1` its column extent the same
    way. Each side is computed on its own line rather than cleverly shared,
    so a reader can check one without tracing the other three.
    """
    return {
        "top": border.top if r == 0 else border.inner_h,
        "bottom": border.bottom if r1 == nrows else border.inner_h,
        "left": border.left if c0 == 0 else border.inner_v,
        "right": border.right if c1 == ncols else border.inner_v,
    }


def _style(*, top, right, bottom, left, unit, align, valign, bold, italic,
           nowrap, bg, color, scale, pad) -> str:
    parts = [f"text-align:{align}"]
    if valign is not None:
        parts.append(f"vertical-align:{valign}")
    for side, line in (("top", top), ("right", right), ("bottom", bottom), ("left", left)):
        value = _edge(line, unit)
        if value is not None:
            parts.append(f"border-{side}:{value}")
    if bold:
        parts.append("font-weight:bold")
    if italic:
        parts.append("font-style:italic")
    if nowrap:
        parts.append("white-space:nowrap")
    if bg:
        parts.append(f"background:{bg}")
    if color:
        parts.append(f"color:{color}")
    if scale != 1.0:
        parts.append(f"font-size:{scale * 100:.3g}%")
    if pad:
        parts.append(f"padding:{pad[0]:g}{unit} {pad[1]:g}{unit}")
    return ";".join(parts)


def _content_html(content: CellContent, is_html: bool) -> str:
    if isinstance(content, TableSpec):
        return render_table(content, rows=None, label_cells=False)
    text = "" if content is None else str(content)
    if is_html:
        return text
    return escape(text).replace("\n", "<br>")


def render_table(table: TableSpec, *, rows: RowCounter | None = None,
                  label_cells: bool = True) -> str:
    """Turn a `TableSpec` into a self-contained `<table>...</table>` string.

    Every visual choice is an inline `style=`, so the result needs no
    matching CSS rule anywhere else -- drop it into any page and it looks the
    same. `rows` is a page-wide `data-row` counter (anything with `.take()`,
    typically a shared `sheets.base.Rows()`); omit it for a standalone table,
    which then counts its own rows from zero. `label_cells=False` skips the
    `data-cell`/`data-row`/`data-col` attributes entirely -- the right choice
    for a nested table (see `Cell.content`), whose own cells are not a
    meaningful row of the *page* -- and is also how a purely decorative
    table opts out of the label-extraction contract altogether.
    """
    if not table.rows:
        return f'<table class="{table.cls}"></table>' if table.cls else "<table></table>"

    ncols = len(table.columns) if table.columns else _infer_ncols(table.rows)
    columns = table.columns or [Column() for _ in range(ncols)]
    widths = _resolve_widths(columns)
    nrows = len(table.rows)
    counter: RowCounter = rows if rows is not None else _LocalCounter()

    # The leading run of `header=True` rows, starting at row 0 -- a header
    # marked further down (bold styling on some other row, say) is not part
    # of this band. Its length decides two things: where `<thead>` ends and
    # `<tbody>` begins, and which row `header_divider` draws under.
    header_band = 0
    while header_band < nrows and table.rows[header_band].header:
        header_band += 1

    future: dict[int, set[int]] = {}
    thead_html: list[str] = []
    tbody_html: list[str] = []
    body_index = 0                          # body-row-only counter, for zebra parity

    for r, row in enumerate(table.rows):
        taken = future.pop(r, set())
        col = 0
        td_html: list[str] = []
        row_number = counter.take()
        in_thead = row.in_thead if row.in_thead is not None else (r < header_band)
        # Zebra follows where a row LANDS, not `header`: `in_thead=True` can
        # put a plain, unbolded row in the header band (a column-number row),
        # and that row is no more a body row for striping purposes than an
        # actual `<th>` is.
        zebra_index = None
        if not in_thead:
            zebra_index = body_index
            body_index += 1

        for cell_spec in row.cells:
            while col in taken:
                col += 1
            if col >= ncols:
                break                      # more cells than the table has room for; drop the rest
            c0 = col
            c1 = min(col + cell_spec.colspan, ncols)
            r1 = min(r + cell_spec.rowspan, nrows)
            for future_r in range(r + 1, r1):
                future.setdefault(future_r, set()).update(range(c0, c1))
            col = c1
            td_html.append(_render_cell(
                table, row, cell_spec, r=r, c0=c0, c1=c1, r1=r1, row_number=row_number,
                zebra_index=zebra_index, nrows=nrows, ncols=ncols, header_band=header_band,
                label_cells=label_cells))
            taken.update(range(c0, c1))

        while col < ncols:                 # pad a short row out to a full rectangle
            c0 = col
            col += 1
            taken.add(c0)
            td_html.append(_render_cell(
                table, row, Cell(), r=r, c0=c0, c1=col, r1=r + 1, row_number=row_number,
                zebra_index=zebra_index, nrows=nrows, ncols=ncols, header_band=header_band,
                label_cells=label_cells))

        tr_style = f' style="height:{row.min_height:g}{table.unit}"' if row.min_height else ""
        tr_cls = f' class="{escape(row.cls)}"' if row.cls else ""
        (thead_html if in_thead else tbody_html).append(
            f"<tr{tr_cls}{tr_style}>{''.join(td_html)}</tr>")

    colgroup = ""
    if any(w is not None for w in widths):
        colgroup = "<colgroup>" + "".join(
            f'<col style="width:{w:.3g}%">' if w is not None else "<col>" for w in widths
        ) + "</colgroup>"

    table_style_parts = [f"width:{table.width}", "border-collapse:collapse"]
    if table.bg:
        table_style_parts.append(f"background:{table.bg}")
    if table.font_family:
        table_style_parts.append(f"font-family:{table.font_family}")
    if table.font_size:
        table_style_parts.append(f"font-size:{table.font_size}")
    # No border-* here: every edge cell already computes its own outer side
    # (see `_computed_border`), so a table-level declaration would only ever
    # repeat what the edge cells already say -- border-collapse resolves
    # identical declarations to the one line, never a doubled one, but there
    # is no reason to say the same thing twice.

    cls_attr = f' class="{table.cls}"' if table.cls else ""
    caption = f"<caption>{escape(table.caption)}</caption>" if table.caption else ""
    # `display:table-row-group` inline, not a `.once` class: a class needs a
    # page-level rule to mean anything, and this module promises to need none.
    # It only matters for paginated output (print-to-PDF); a single
    # continuous screenshot -- what this renderer actually captures -- has no
    # page breaks for a header to repeat across in the first place.
    thead_style = "" if table.repeat_header else ' style="display:table-row-group"'
    thead = f"<thead{thead_style}>{''.join(thead_html)}</thead>" if thead_html else ""
    return (f'<table{cls_attr} style="{";".join(table_style_parts)}">{caption}{colgroup}'
            f'{thead}<tbody>{"".join(tbody_html)}</tbody></table>')


def _render_cell(table: TableSpec, row: Row, cell_spec: Cell, *, r: int, c0: int, c1: int,
                  r1: int, row_number: int, zebra_index: int | None, nrows: int, ncols: int,
                  header_band: int, label_cells: bool) -> str:
    column = table.columns[c0] if table.columns and c0 < len(table.columns) else Column()

    computed = _computed_border(table.border, r, r1, c0, c1, nrows, ncols)
    if table.header_divider is not None and header_band > 0 and r == header_band - 1:
        computed["bottom"] = table.header_divider
    if cell_spec.border:
        computed.update(cell_spec.border)

    align = cell_spec.align or column.align
    valign = cell_spec.valign or column.valign
    bold = cell_spec.bold if cell_spec.bold is not None else row.header
    nowrap = cell_spec.nowrap if cell_spec.nowrap is not None else column.nowrap
    bg = cell_spec.bg or row.bg
    if bg is None and table.zebra and zebra_index is not None:
        even, odd = table.zebra
        bg = even if zebra_index % 2 == 0 else odd

    style = _style(top=computed["top"], right=computed["right"], bottom=computed["bottom"],
                    left=computed["left"], unit=table.unit, align=align, valign=valign,
                    bold=bold, italic=cell_spec.italic, nowrap=nowrap, bg=bg,
                    color=cell_spec.color, scale=cell_spec.scale, pad=cell_spec.pad)

    inner = _content_html(cell_spec.content, cell_spec.html)
    tag = "th" if row.header else "td"
    attrs = [f'style="{style}"']
    if cell_spec.cls:
        attrs.append(f'class="{escape(cell_spec.cls)}"')
    if label_cells:
        attrs.append(f'data-cell="{escape(cell_spec.kind)}"')
        attrs.append(f'data-row="{row_number}"')
        attrs.append(f'data-col="{c0}"')
    if c1 - c0 > 1:
        attrs.append(f'colspan="{c1 - c0}"')
    if r1 - r > 1:
        attrs.append(f'rowspan="{r1 - r}"')
    return f"<{tag} {' '.join(attrs)}>{inner}</{tag}>"


__all__ = [
    "Border", "Cell", "Column", "Line", "Row", "RowCounter", "TableSpec",
    "blank_row", "header_group_rows", "render_table",
]
