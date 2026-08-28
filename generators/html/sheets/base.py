"""What every sheet is built from: the box contract, the page box, the tables.

The five hand-drawn references in `samples/invoice-templates/` are the shape
this package produces. They have one thing in common under the styling, and it
is the thing the old single-template `a4.py` did not have: **ordinary flow with
real tables**. A cell spans columns with `colspan`, a stub runs down rows with
`rowspan`, and the engine works the column edges out. Nothing is positioned
absolutely, so two tables on one page line up without anybody computing a
boundary, and the same markup prints the same way in a browser and in
WeasyPrint.

What lives here is what is genuinely the same between the five: the labelled
run, the table cell, the page skeleton, the item table, the totals, the party
blocks. What does not live here is what makes a sheet recognisable -- the
letterhead, the colours, the paper size. Each family module supplies those.

Three contracts this module is responsible for keeping:

* **Every labelled run is `<span data-kind="...">`** and nothing else is.
  `CELL_RECTS_JS` reads quads off exactly those, and knows nothing about which
  template drew them.
* **Every `<td>` carries `data-cell`, `data-row`, `data-col`** and its spans.
  `CELL_REGIONS_JS` reads the cell extents, which is the half of the label a
  text box cannot carry: "Tổng tiền thanh toán" says nothing about the six
  columns its cell covers.
* **`data-row` is numbered across the whole page, not per table.** An invoice
  has two tables -- the items and the tax summary -- and `structure_from_cells`
  groups cells by that number. Restarting it at zero in the second table welds
  the two together into one nonsense row.

Values printed come from `receipt.ground_truth()`, so the label and the page
are the same strings by construction. The furniture around them -- column
titles, signature captions -- comes from the layout spec and the `Receipt`,
because it is not in the label and never was.
"""

from __future__ import annotations

import html
import random
import unicodedata
from pathlib import Path
from typing import Any, Sequence

from components.table import Border, Cell, Column, Row, TableSpec, render_table

REPO_ROOT = Path(__file__).resolve().parents[3]
ORNAMENT_DIR = REPO_ROOT / "textures" / "ornament"

# What a family sets its own `HAND_KINDS` to when a pen reaches the whole page
# rather than the fields of a printed form. Only `notebook` does: a school
# exercise book has no press run, so there is no printed furniture for the
# writing to sit inside.
#
# It is the same string as `handwriting.ALL_KINDS`, and `tests/test_sheets.py`
# asserts they are, because the two modules must not be made to import each
# other -- `handwriting` is renderer machinery and knows nothing about which
# families exist, and a family knows nothing about ink.
EVERY_RUN = "*"

# Paper, in the units a print engine thinks in. `@page` gets the name and the
# sheet gets the millimetres, so the browser -- which has no `@page` -- lays out
# the same box the PDF does.
PAPERS: dict[str, tuple[str, str]] = {
    "A4": ("210mm", "297mm"),
    "A5": ("148mm", "210mm"),
    "BROADSHEET": ("375mm", "597mm"),
    "TABLOID": ("280mm", "430mm"),
    # Landscape is not a flag anywhere in this file -- it is just the same
    # two lengths, swapped. Added for the insurance root: a travel-insurance
    # "ticket" page and a health-insurance ID card's two-faces-on-one-sheet
    # stage (A4_LANDSCAPE), an auto-liability certificate table (A5_LANDSCAPE),
    # and a motorcycle-liability certificate small enough to be its own class
    # (A6_LANDSCAPE).
    "A4_LANDSCAPE": ("297mm", "210mm"),
    "A5_LANDSCAPE": ("210mm", "148mm"),
    "A6_LANDSCAPE": ("148mm", "105mm"),
}

# Font families as `page.font_faces()` names them: the file stem, so a stack
# asking for "Liberation Serif" with a space matches nothing and falls through
# to whatever the container happens to have.
SERIF = "'LiberationSerif','DejaVu Serif',serif"
SANS = "'DejaVuSans','LiberationSans','DejaVu Sans',sans-serif"
MONO = "'LiberationMono','Cousine',monospace"


def rng_for(recipe, tag: int = 0x5A4D) -> random.Random:
    """The family's own independent random stream, seeded off the recipe.

    `tag` keeps one family's coin flips (a livery, a watermark, a checkbox
    mark) from ever landing in step with another's, even when both draw from
    the same `recipe.seed` for the same page. `0x5A4D` is not a magic
    constant chosen here -- it is the one five families (`lodging`,
    `medical`, `modern`, `statement`, `statutory`) already happened to XOR
    with, unnamed, before this helper existed; keeping it as the default
    reproduces every one of them bit-for-bit. A family with its own tag
    (`form.py` uses `0x46524D`, "FRM") passes it explicitly.
    """
    return random.Random(recipe.seed ^ tag)


def esc(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def span(kind: str, text: Any, cls: str = "") -> str:
    """One labelled run, or nothing at all.

    Text-only on purpose: `CELL_RECTS_JS` measures `span.firstElementChild ||
    span`, so a nested element would silently become the box and the quad would
    describe a fragment of the run instead of the run.
    """
    text = "" if text is None else str(text)
    if not text.strip():
        return ""
    attr = f' class="{cls}"' if cls else ""
    return f'<span data-kind="{esc(kind)}"{attr}>{esc(text)}</span>'


class Rows:
    """Row numbers for `data-row`, handed out across the whole page.

    Two tables on one sheet must not share them. `structure_from_cells` in
    `render.py` groups measured cells by `data-row`, and a second table that
    restarts at zero has its first row spliced onto the item table's first row
    -- one row of eleven cells that exists nowhere on the paper.
    """

    def __init__(self) -> None:
        self._next = 0

    def take(self) -> int:
        row = self._next
        self._next += 1
        return row


def cell(tag: str, row: int, col: int, inner: str, *, cls: str = "",
         kind: str = "", colspan: int = 1, rowspan: int = 1,
         style: str = "") -> str:
    """One table cell, carrying where it sits and how far it spans.

    The convention is PaddleOCR's TableGeneration: label the `<td>`, not only
    the text in it. For a merged cell that distinction is the whole point -- the
    text box round "Tổng tiền thanh toán" cannot say that its cell covers six
    columns, and a model asked to rebuild the table needs exactly that.
    """
    attrs = [f'data-cell="{esc(kind)}"', f'data-row="{row}"', f'data-col="{col}"']
    if colspan > 1:
        attrs.append(f'colspan="{colspan}"')
    if rowspan > 1:
        attrs.append(f'rowspan="{rowspan}"')
    if cls:
        attrs.append(f'class="{cls}"')
    if style:
        attrs.append(f'style="{style}"')
    return f"<{tag} {' '.join(attrs)}>{inner}</{tag}>"


def structure_tokens(rows: list[list[dict]]) -> list[str]:
    """The table as PPStructure tokens: `<tr>`, `<td`, ` colspan="6"`, `>`, ...

    Same format `tables.py` writes, so anything that already reads those reads
    this. Splicing the cell text back between the tokens rebuilds the table,
    which is the check that the structure half and the text half describe one
    thing.
    """
    tokens: list[str] = []
    for row in rows:
        tokens.append("<tr>")
        for item in row:
            spans = []
            if item.get("colspan", 1) > 1:
                spans.append(f' colspan="{item["colspan"]}"')
            if item.get("rowspan", 1) > 1:
                spans.append(f' rowspan="{item["rowspan"]}"')
            if spans:
                tokens.append("<td")
                tokens.extend(spans)
                tokens.append(">")
            else:
                tokens.append("<td>")
            tokens.append("</td>")
        tokens.append("</tr>")
    return tokens


def initials(name: str) -> str:
    """Two letters for a logo mark, from the words a Vietnamese name ends with.

    "CÔNG TY CỔ PHẦN ĐIỆN MÁY VÀ GIA DỤNG HỒNG HÀ" -> "HH": the trailing words
    are the trading name and the leading ones say only that it is a company.
    """
    skip = {"CONG", "TY", "CO", "PHAN", "TNHH", "MTV", "DOANH", "NGHIEP",
            "TAP", "DOAN", "CHI", "NHANH", "VA", "-"}
    words = []
    for word in name.replace("-", " ").split():
        plain = "".join(c for c in unicodedata.normalize("NFD", word)
                        if not unicodedata.combining(c)).upper()
        plain = plain.replace("Đ", "D").replace("đ", "d")
        if plain and plain not in skip:
            words.append(word)
    picked = words[-2:] if len(words) >= 2 else (words or [name])
    return "".join(word[0] for word in picked).upper()[:2] or "VN"


def ornament_url(stem: str) -> str:
    """A `file://` URL for one of `textures/ornament/`, or "" if it is missing.

    Absolute rather than relative because the two engines resolve differently:
    the browser serves the markup from a temporary directory (see
    `page.served`) and genalog hands WeasyPrint a bare string with no base URL.
    An absolute URL is the only form both of them find.
    """
    path = ORNAMENT_DIR / f"{stem}.png"
    return path.as_uri() if path.exists() else ""


def qr_svg(text: str, size_mm: float) -> str:
    """A real QR code as inline SVG, or "" when `segno` is not installed.

    Inline so the page needs no file and no network, and real rather than drawn
    because a scanner that reads it is the cheapest possible check that the
    serial on the page is the serial in the label.
    """
    try:
        import segno
    except ImportError:
        return ""
    if not text:
        return ""
    import io

    code = segno.make(text, error="m")
    modules = code.symbol_size(scale=1, border=0)[0] or 1
    buffer = io.BytesIO()
    # segno writes bytes; `unit="mm"` makes the SVG size a physical one, which
    # is what both engines need -- a QR sized in pixels lands at a different
    # size on a 210mm page than it does in a 794px viewport.
    code.save(buffer, kind="svg", scale=size_mm / modules, border=0, unit="mm",
              xmldecl=False, svgns=True, omitsize=False)
    return buffer.getvalue().decode("utf-8")


# --------------------------------------------------------------------------
# the layout spec, read the same way the character grid reads it


def columns_of(spec: dict, ncols: int) -> list[dict]:
    """The layout's own columns, with the character widths turned into percent.

    Read from the layout file rather than restated here, so the template path
    and the character grid print the same columns in the same order. A width of
    0 means "take what is left", exactly as it does on the grid.
    """
    columns = [dict(column) for column in spec.get("columns", [])]
    if not columns:
        return []
    fixed = sum(int(column.get("width") or 0) for column in columns)
    flexible = [column for column in columns if not int(column.get("width") or 0)]
    spare = max(ncols - fixed, len(flexible) * 8)
    for column in columns:
        width = int(column.get("width") or 0)
        if width:
            column["pct"] = 100.0 * width / max(ncols, 1)
        else:
            column["pct"] = 100.0 * (spare / len(flexible)) / max(ncols, 1)
        column.setdefault("align", "left")
        column.setdefault("title_align", column["align"])
    # The flexible column absorbs the rounding, so the widths sum to 100 and no
    # engine has to invent the remainder.
    drift = 100.0 - sum(column["pct"] for column in columns)
    if flexible:
        flexible[0]["pct"] += drift
    return columns


def ncols_of(spec: dict) -> int:
    """The middle of the layout's declared width, in characters."""
    width = spec.get("width") or [96, 96]
    if isinstance(width, (int, float)):
        return int(width)
    return int((int(width[0]) + int(width[-1])) / 2)


def item_rows(spec: dict) -> list[list[dict]]:
    """`item.rows` from the layout file: which column each value goes in."""
    rows = (spec.get("item") or {}).get("rows") or []
    return [[dict(entry) for entry in row] for row in rows]


def align_class(align: str) -> str:
    return {"right": "r", "center": "c"}.get(align, "")


def safe_align(align: str) -> str:
    """A layout's `align:`/`title_align:`, normalised the way `align_class` already is.

    A layout's align string only ever had to survive being *compared* --
    `align_class` has always mapped anything unrecognised to plain left
    rather than rejecting it. `components.table.Cell`/`Column` are stricter
    on purpose (an unrecognised `align` raises, for a value a *caller of the
    component* chose deliberately), so this is the seam: normalise once,
    here, to the same three buckets `align_class` already sorts into, rather
    than let a stray value from a layout file crash table rendering outright.
    """
    return {"right": "right", "center": "center"}.get(align, "left")


# --------------------------------------------------------------------------
# the blocks every family draws the same way


def party_rows(pairs: dict[str, str] | Sequence[tuple[str, str]]) -> list[tuple[str, str]]:
    return list(pairs.items()) if isinstance(pairs, dict) else [tuple(p) for p in pairs]


def party_pairs(receipt, parse: dict, which: str) -> list[tuple[str, str]]:
    """One party block as (label, value) pairs, in print order.

    From `receipt.invoice`, not from the label, and this is the one place where
    that is the *more* faithful source rather than the less. `_invoice_label`
    turns each block into a **dict**, so two rows sharing a label collapse into
    one -- and an export invoice really does carry two "Địa chỉ (Address):"
    rows, the exporter's and the importer's. Printing from the dict drops the
    first, and the address it drops is the one the label reports under
    `store.address`. These are the very tuples the label is built from, so there
    is nothing here for the page and the label to drift apart over.
    """
    invoice = getattr(receipt, "invoice", None)
    entries = getattr(invoice, which, None) if invoice is not None else None
    if entries:
        return [(label, value) for label, value in entries if value]
    return party_rows((parse.get("invoice") or {}).get(which) or {})


def field_line(label: str, value: str, *, cls: str = "f", leader: bool = False) -> str:
    """A label and its value on one line, optionally on a dotted rule.

    Two labelled runs, not one: `invoice.field.label` and `invoice.field` are
    what the character grid emits, and a reader that learns to find the value
    should not have to split it off the label first.

    The inner run carries **no class**. It used to be given `v`, the same one as
    the table-cell wrapping it, and `.f.dot .v` then matched both: the form drew
    its dotted leader across the whole cell *and* a second one hugging the value,
    two rules under every field on `invoice_vat_form` and `invoice_export`. The
    bold comes from the cell by inheritance, so nothing else needed changing.
    """
    body = span("invoice.field", value)
    dots = " dot" if leader else ""
    return (f'<div class="{cls}{dots}"><span class="k">'
            f'{span("invoice.field.label", label)}</span>'
            f'<span class="v">{body}</span></div>')


def bilingual_field_line(label_en: str, label_vn: str, value: str, *, cls: str = "f") -> str:
    """`field_line()`'s single-label contract, doubled: English stacked over
    Vietnamese beside one value.

    A bilingual insurance policy (a cargo policy, a travel certificate)
    prints both languages as equally real fields on the paper, not one as a
    gloss on the other -- so both label runs carry `data-kind`, the same as
    the value, rather than only the Vietnamese one.
    """
    body = span("invoice.field", value)
    return (f'<div class="{cls}"><span class="k">'
            f'{span("invoice.field.label", label_en, "en")}'
            f'{span("invoice.field.label", label_vn, "vn")}'
            f'</span><span class="v">{body}</span></div>')


def comb_box(kind: str, text: Any, *, groups: Sequence[int] | None = None) -> str:
    """A per-character boxed grid -- the Vietnamese government-form input
    where a citizen writes one glyph to a square (an application form's
    name/date/ID-number fields), one bordered `<i>` per character.

    Every labelled run in this package is `<span data-kind="...">TEXT</span>`
    with **no nested element** (`tests/test_sheets.py::
    test_every_labelled_run_is_a_span_with_a_kind` enforces this by regex,
    repo-wide, with no per-layout exemption) -- so the boxes cannot be one
    span wrapping a dozen `<i>` cells. Instead each *character* gets its own
    trivial, unnested `data-kind` span, inside its own `<i>` cell; all of
    them share the same `kind`, so `pipeline/invariants.py`'s box-rejoining
    (already written to reassemble one value split across several same-kind
    boxes, e.g. a line-wrapped run) reassembles the character run the same
    way. A blank cell (a space in "Tạ Thị") carries no span at all --
    `span()` already drops blank text -- which the same whitespace-
    insensitive rejoin fallback tolerates.

    `groups`, given, is how many characters each group holds before a
    borderless gap cell -- `groups=(2, 2, 4)` for a date "12"+"05"+"1988".
    Omit it for one unbroken run of boxes.
    """
    text = "" if text is None else str(text)
    if not text.strip():
        return ""
    chunks = []
    if groups:
        pos = 0
        for size in groups:
            chunks.append(text[pos:pos + size])
            pos += size
        if pos < len(text):
            chunks.append(text[pos:])
    else:
        chunks = [text]
    cells = []
    for index, chunk in enumerate(chunks):
        if index:
            cells.append('<i class="sp"></i>')
        cells.extend(f"<i>{span(kind, ch)}</i>" for ch in chunk)
    return f'<span class="comb">{"".join(cells)}</span>'


def stamp(text: str, *, colour: str = "#c8102e", size_mm: float = 30,
         rotate_deg: float = -13) -> str:
    """A round, rotated, translucent ink stamp -- decorative furniture, never
    ground truth (no `span()`, no `data-kind`): the org name it repeats is
    already printed elsewhere on the page in a real labelled run, the same
    way every existing family's own stamp already works.

    Every family that wants a red circular seal today writes its own:
    `statutory.py`'s is a green e-invoice tick box, `lodging.py`'s is a
    background-image PNG -- neither is this shape, and neither is shared.
    Since most of the insurance root's ten layouts want the same round
    rotated seal, this is the one shared version. Inline-styled throughout
    (two nested rings instead of one element plus a `::before`), so a family
    that wants one needs no matching CSS of its own -- only a
    `position:relative` ancestor, the same contract `signature_block(stamp=)`
    already slots a stamp fragment into.
    """
    ring = round(size_mm * 0.08, 2)
    border = round(size_mm * 0.022, 2)
    inner_border = round(size_mm * 0.01, 2)
    font = round(size_mm * 0.075, 2)
    return (
        f'<div style="position:absolute;left:50%;top:0;'
        f'transform:translateX(-50%) rotate({rotate_deg}deg);'
        f'width:{size_mm}mm;height:{size_mm}mm;box-sizing:border-box;'
        f'border:{border}mm solid {colour};border-radius:50%;opacity:.65;'
        f'display:flex;align-items:center;justify-content:center;text-align:center;">'
        f'<div style="position:absolute;inset:{ring}mm;border:{inner_border}mm solid {colour};'
        f'border-radius:50%;"></div>'
        f'<span style="position:relative;color:{colour};'
        f'font-family:Arial,Helvetica,sans-serif;font-weight:800;'
        f'font-size:{font}mm;line-height:1.15;">{esc(text)}</span>'
        f"</div>"
    )


def key_strip(strip, separator: str = "|") -> str:
    """The one-line run of keys across the top of a modern invoice."""
    pairs = party_rows(strip) if not isinstance(strip, list) else list(strip)
    if not pairs:
        return ""
    parts = []
    for index, (label, value) in enumerate(pairs):
        if index:
            parts.append(f'<span class="sep">{esc(separator)}</span>')
        parts.append(span("invoice.field.label", label, "k"))
        parts.append(span("invoice.field", value, "v"))
    return f'<div class="strip">{" ".join(parts)}</div>'


def items_table(spec: dict, receipt, parse: dict, rows: Rows, *,
                cls: str = "items", column_numbers: bool | None = None,
                blank_rows: int | None = None,
                totals: list[dict] | None = None,
                totals_label_span: int | None = None) -> str:
    """The item table, with the totals folded in as merged rows when asked.

    The merge is the reason this is one function and not two. A totals line is
    one cell covering every column but the last, which is only expressible if
    the totals are rows of the same table; drawn as a separate block underneath
    they would be a second table whose column edges have to be made to agree
    with the first by hand. That agreement is exactly what `colspan` is for.

    `totals` entries are `{label, value, grand, lead}`; `lead` is an optional
    `(kind, text, colspan)` cell placed to the left of the label in that row.

    Built as a `components.table.TableSpec` and handed to `render_table` --
    but `border=Border.none()`, deliberately: every family still styles
    `.items`/`.grand`/`.tlabel`/etc. in its own `<style>` block exactly as
    before, reached through `cls`/`Cell.cls` on every element this function
    writes, and an inline border would silently outrank those rules rather
    than cooperate with them (see `Cell.cls` in `components/table.py`). What
    moved here is the geometry: column resolution, colspan/rowspan occupancy,
    the `data-cell`/`data-row`/`data-col` labels and the `<thead>`/`<tbody>`
    split now come from one tested primitive instead of being hand-rolled in
    this function and four private ones beside it.
    """
    from rulebase.layout import item_values

    settings = spec.get("table") or {}
    if column_numbers is None:
        column_numbers = bool(settings.get("column_numbers"))
    if blank_rows is None:
        blank_rows = int(settings.get("blank_rows") or 0)

    columns = columns_of(spec, ncols_of(spec))
    if not columns:
        return ""
    keys = [column["key"] for column in columns]
    table_columns = [
        Column(width=column["pct"], align=safe_align(column.get("align", "left")),
              valign=None)                     # None: defer to `table.items td{...}`
        for column in columns
    ]

    table_rows = _header_rows(columns, spec)
    if column_numbers:
        table_rows.append(Row([
            Cell(span("colnum", column.get("number", "")), html=True,
                kind="colnum", cls="c", align="center")
            for column in columns
        ], cls="colnum", in_thead=True))

    plan = [_placements(row, keys) for row in item_rows(spec)]
    first = plan[0] if plan else []
    # A continuation row that names one column, and a column the first row
    # already fills, is a second LINE of that cell rather than a row of its own:
    # "Tiền phòng / Bao gồm bữa sáng" is one cell on every reference sheet.
    # Anything wider is a real row -- a till prints the quantity, the price and
    # the amount under the dish name, and those are three cells, not a footnote.
    folded = [row for row in plan[1:]
              if len(row) == 1 and row[0][0] == row[0][1]
              and any(place[0] <= row[0][0] <= place[1] for place in first)]
    stacked = [row for row in plan[1:] if row not in folded]

    for item in receipt.items:
        values = item_values(item, receipt)
        extra: dict[int, list[tuple[str, str]]] = {}
        for row in folded:
            start, _end, source, _align = row[0]
            text = values.get(source, "")
            if text:
                extra.setdefault(start, []).append((f"menu.{source}", text))
        if getattr(item, "is_group", False):
            # A block heading is a row of the table, not a caption above it: it
            # carries the block's column sums. Its name runs across the columns
            # that describe a line -- unit, quantity, the two unit prices --
            # because a heading has none of those.
            table_rows.append(_group_row(columns, keys, values, spec, item))
            continue
        table_rows.append(_item_row(columns, first, values, extra))
        for row in stacked:
            if any(values.get(place[2]) for place in row):
                table_rows.append(_item_row(columns, row, values, {}))
        table_rows.extend(_item_extras(spec, item, receipt, values, columns))

    for _ in range(blank_rows):
        table_rows.append(Row([Cell() for _ in columns], cls="blank"))

    for entry in totals or []:
        grand = bool(entry.get("grand"))
        kind = "total.grand" if grand else "total.line"
        total_cells: list[Cell] = []
        used = 0
        # An export invoice puts the exchange rate in the same row as the total,
        # in its own merged cell: `Tỉ giá (Rate)` over three columns, then the
        # total's label over two, then the amount. Two spans in one row is what
        # the reference sheet does and what a grid of characters cannot say.
        lead = entry.get("lead")
        if lead:
            lead_kind, lead_text, lead_span = lead
            total_cells.append(Cell(span(lead_kind, lead_text), html=True,
                                    kind=lead_kind, cls="tlead", colspan=lead_span))
            used = lead_span
        width = totals_label_span if totals_label_span else len(columns) - 1 - used
        width = max(1, min(width, len(columns) - 1 - used))
        total_cells.append(Cell(span(f"{kind}.label", entry.get("label", "")), html=True,
                                kind=f"{kind}.label", cls="tlabel", colspan=width))
        used += width
        total_cells.extend(Cell() for _ in range(len(columns) - used - 1))
        total_cells.append(Cell(span(kind, entry.get("value", "")), html=True,
                                kind=kind, cls="r", align="right"))
        table_rows.append(Row(total_cells, cls="grand" if grand else "total"))

    # A print engine repeats `<thead>` on every page a table runs onto, and
    # that is usually right. It is wrong for a form whose paper says otherwise:
    # the hospital bill's second page continues its table with no header at
    # all, and the repeat also puts a hundred glyphs of column titles into the
    # PDF's character stream that the markup lists once -- which is exactly the
    # noise `match_runs` has to step over to find the next field.
    repeat = bool((spec.get("table") or {}).get("repeat_header", True))
    table = TableSpec(rows=table_rows, columns=table_columns, border=Border.none(),
                      cls=cls, repeat_header=repeat)
    return render_table(table, rows=rows)


def _item_extras(spec: dict, item, receipt, values: dict[str, str],
                 columns: list[dict]) -> list[Row]:
    """The rows a layout hangs under an item: its name, its old price, a discount.

    Three of them, and each is a full-width row, which is where `colspan` earns
    its keep a second time: a supermarket bill puts the barcode on the priced
    line and the product name on its own line underneath, running the whole
    width of the paper. On the grid that is a cell nobody ruled; here it is a
    cell that says how many columns it covers.
    """
    settings = spec.get("item") or {}
    width = len(columns)
    out: list[Row] = []

    def full(kind: str, text: str, css_cls: str = "") -> Row:
        return Row([Cell(span(kind, text), html=True, kind=kind, cls=css_cls,
                         colspan=width)], cls="extra")

    if item.note and settings.get("note_row"):
        out.append(full("menu.note", item.note, "indent"))
    if getattr(item, "original_price", 0) and settings.get("original_price_row"):
        label = settings["original_price_row"].get("label", "Giá gốc:")
        out.append(full("menu.originalprice",
                        f"{label} {receipt.cash(item.original_price)}", "indent"))
    if item.discount:
        label = (settings.get("discount_row") or {}).get("label", "KM")
        left = max(1, width - 1)
        out.append(Row([
            Cell(span("menu.discount.label", label), html=True,
                kind="menu.discount.label", colspan=left),
            Cell(span("menu.discountprice", receipt.cash(-abs(item.discount))), html=True,
                kind="menu.discountprice", cls="r", align="right"),
        ], cls="extra"))
    return out


def _header_rows(columns: list[dict], spec: dict) -> list[Row]:
    """The column titles, in one band or two.

    `header_groups:` in a layout file names a run of columns that share a
    heading -- "Nguồn thanh toán (đồng)" over the four columns a hospital bill
    splits its money into. The columns outside every group then have to reach
    down through both bands, which is `rowspan=2`, and `components.table`
    works the edges out. There is no arithmetic here and that is the point: the
    same statement drawn on a character grid would be a wide cell that happens to
    have no rule under half of it.
    """
    groups = (spec.get("table") or {}).get("header_groups") or []
    keys = [column["key"] for column in columns]
    resolved_spans: list[tuple[int, int, str]] = []
    for entry in groups:
        first, last = str(entry.get("from", "")), str(entry.get("to", ""))
        if first not in keys or last not in keys:
            continue
        resolved_spans.append(
            (keys.index(first), keys.index(last), str(entry.get("title", ""))))
    resolved_spans.sort()

    if not resolved_spans:
        return [Row([
            Cell(span("colhdr", column.get("title", "")), html=True, kind="colhdr",
                align=safe_align(column.get("title_align", "center")),
                cls=align_class(column.get("title_align", "center")))
            for column in columns
        ], header=True)]

    grouped = {index for start, end, _ in resolved_spans for index in range(start, end + 1)}
    top: list[Cell] = []
    index = 0
    while index < len(columns):
        here = next((s for s in resolved_spans if s[0] == index), None)
        if here:
            start, end, title = here
            top.append(Cell(span("colhdr", title), html=True, kind="colhdr",
                            cls="c", align="center", colspan=end - start + 1))
            index = end + 1
            continue
        column = columns[index]
        top.append(Cell(span("colhdr", column.get("title", "")), html=True, kind="colhdr",
                        rowspan=2, align=safe_align(column.get("title_align", "center")),
                        cls=align_class(column.get("title_align", "center"))))
        index += 1
    lower = [
        Cell(span("colhdr", columns[index].get("title", "")), html=True, kind="colhdr",
            align=safe_align(columns[index].get("title_align", "center")),
            cls=align_class(columns[index].get("title_align", "center")))
        for index in sorted(grouped)
    ]
    return [Row(top, header=True), Row(lower, header=True)]


def _group_row(columns: list[dict], keys: list[str], values: dict[str, str],
              spec: dict, item) -> Row:
    """A block heading: its name over the descriptive columns, then its sums."""
    width = int((spec.get("table") or {}).get("group_span") or 0)
    if width < 1:
        # No declaration: run the name up to the first column that has a number
        # on this row, which is where the sums begin.
        width = next((index for index, key in enumerate(keys) if values.get(key)), 1)
        width = max(width, 1)
    width = min(width, len(columns))
    cells = [Cell(span("menu.name", values.get("name", "")), html=True,
                 kind="menu.name", cls="gname", colspan=width)]
    for index in range(width, len(columns)):
        key = keys[index]
        cells.append(Cell(span(f"menu.{key}", values.get(key, "")), html=True,
                          kind=f"menu.{key}",
                          cls=align_class(columns[index].get("align", "left"))))
    return Row(cells, cls="grouprow")


def _placements(row: list[dict], keys: list[str]) -> list[tuple[int, int, str, str]]:
    """`(first_col, last_col, source, align)` for each entry of an item row.

    `span: [qty, amount]` in a layout file means one cell running from one named
    column to another -- a dish name laid across the three money columns of a
    till receipt. On the character grid that is a wide cell that happens to have
    no rule through it; here it is a `colspan`, which is the same statement made
    where a reader of the label can see it.
    """
    out = []
    for entry in row:
        names = entry.get("span")
        if names:
            edges = [keys.index(str(name)) for name in names if str(name) in keys]
            if not edges:
                continue
            start, end = min(edges), max(edges)
        else:
            column = entry.get("col")
            if column not in keys:
                continue
            start = end = keys.index(column)
        source = str(entry.get("from", entry.get("col", "")))
        out.append((start, end, source, str(entry.get("align", ""))))
    return sorted(out)


def _item_row(columns: list[dict], places: list[tuple[int, int, str, str]],
              values: dict[str, str], extra: dict[int, list[tuple[str, str]]]) -> Row:
    """One row: the placed cells, and an empty cell for every column between.

    A gap cell's `align` is left unset rather than restated: it carries no
    text, and an unset `Cell.align`/`Cell.valign` already inherits the
    column's own default (see `components.table._render_cell`) -- the same
    outcome `cls=align_class(...)` alone produced before, one fewer thing
    computed twice.
    """
    cells: list[Cell] = []
    column = 0
    for start, end, source, align in places:
        while column < start:
            cells.append(Cell(cls=align_class(columns[column].get("align", "left"))))
            column += 1
        if column > end:
            continue                  # two entries claimed the same column
        inner = span(f"menu.{source}", values.get(source, ""))
        for kind, text in extra.get(start, []):
            inner += f'<div class="sub">{span(kind, text)}</div>'
        resolved_align = safe_align(align or columns[start].get("align", "left"))
        cells.append(Cell(inner, html=True, kind=f"menu.{source}",
                          colspan=end - start + 1, align=resolved_align,
                          cls=align_class(align or columns[start].get("align", "left"))))
        column = end + 1
    while column < len(columns):
        cells.append(Cell(cls=align_class(columns[column].get("align", "left"))))
        column += 1
    return Row(cells)


def totals_block(parse: dict, *, indent: float = 0.4, grand: int = -1) -> str:
    """Totals nudged into the right-hand part of the sheet, not in a table.

    What an invoice that designed its own paper does: the block stops short of
    the left margin and the emphasised line is the one being asked for.

    `grand` is which line that is, and it is not always the last. A shop's
    invoice ends on the amount due, so the emphasis falls at the bottom; a hotel
    folio *opens* with the total and then lists what was paid against it, so the
    emphasis falls on the first line and the lines under it are the settlement.
    Pass -1 for the last, 0 for the first, None for none.
    """
    totals = parse.get("total") or {}
    if not totals:
        return ""
    lines = list(totals.items())
    picked = None if grand is None else (grand % len(lines))
    out = []
    for index, (label, value) in enumerate(lines):
        emphasis = index == picked
        kind = "total.grand" if emphasis else "total.line"
        out.append(
            f'<div class="trow{" grand" if emphasis else ""}">'
            f'{span(f"{kind}.label", label, "lab")}'
            f'{span(kind, value, "amt")}</div>')
    return (f'<div class="totals" style="margin-left:{indent * 100:.0f}%">'
            f'{"".join(out)}</div>')


def signature_block(receipt, parse: dict, *, stamp: str = "") -> str:
    """The signature captions, and the names under them when the sheet has any.

    The captions come from `receipt.invoice.signatures` rather than being
    written out here: they are furniture, not label, but they are the *same*
    furniture the character grid prints, and a document that says "Người bán
    hàng" on one renderer and "Bên bán" on the other is two documents.
    """
    invoice = getattr(receipt, "invoice", None)
    if invoice is None or not invoice.signatures:
        return ""
    names = list((parse.get("invoice") or {}).get("signed_names") or [])
    columns = []
    for index, (title, note) in enumerate(invoice.signatures):
        who = names[index] if index < len(names) else ""
        columns.append(
            f'<div class="sign">'
            f'{span("sign.title", title, "t")}'
            f'<div class="n">{span("sign.note", note)}</div>'
            f'<div class="who">{span("sign.name", who)}</div>'
            f'{stamp if index == len(invoice.signatures) - 1 else ""}'
            f"</div>")
    return f'<div class="signs">{"".join(columns)}</div>'


def notes_blocks(lines: Sequence[str], *, limit: int | None = None) -> list[list[str]]:
    """`invoice.notes` split into blocks on blank lines.

    The same convention `_emit_notes` in `rulebase/layout.py` reads: a blank
    entry ends a block, so one document can print a "who to pay" block and a
    "how to reach us" block from the same flat list without either family
    inventing its own key for the second one. `modern.py::_notes` and
    `form.py::_notes_block` used to each parse this by hand, identically down
    to the loop -- `limit` is the one place they differed (`modern.py` shows
    at most two blocks side by side; `form.py` prints as many as the document
    gives it), so it is the one parameter here rather than two functions.

    Returns the *lines*, not markup: each family still turns a block into its
    own shape (columns, boxes, `<p>` tags, an "h" class on a heading line),
    which is the part that is genuinely different between them.
    """
    blocks: list[list[str]] = [[]]
    for line in lines:
        if line.strip():
            blocks[-1].append(line)
        else:
            blocks.append([])
    blocks = [block for block in blocks if block]
    return blocks[:limit] if limit else blocks


def footer_block(parse: dict) -> str:
    lines = parse.get("footer") or []
    if not lines:
        return ""
    return ('<div class="foot">'
            + "".join(f'<div>{span("footer", line)}</div>' for line in lines)
            + "</div>")


def words_block(receipt, parse: dict) -> str:
    invoice = parse.get("invoice") or {}
    words = invoice.get("words", "")
    if not words:
        return ""
    label = getattr(getattr(receipt, "invoice", None), "words_label", "")
    return (f'<div class="words">{span("invoice.words.label", label, "wl")}'
            f'{span("invoice.words", words)}</div>')


# --------------------------------------------------------------------------
# the page box


def document(body: str, css: str, *, paper: str = "A4", padding: str = "10mm",
            font: str = SERIF, size: str = "8.6pt", colour: str = "#111",
            line_height: str = "1.3") -> str:
    """The page skeleton both engines lay out identically.

    `@page` gets `margin: 0` and the padding goes on `#sheet` rather than the
    other way round, because the browser has no `@page`: putting the margin
    there would give WeasyPrint a white border the browser's element screenshot
    does not have, and the two renderers would disagree about where the paper
    ends. `min-height` is a floor, not a height -- a page whose content grew
    past its paper stays visible rather than being cropped into looking fine.

    `paper` must be a `PAPERS` key. It used to fall back to A4 silently on
    a miss -- harmless while every caller only ever passed "A4"/"A5"
    (confirmed: every `sheets/*.py` call site did, at the time this was
    tightened), but a real risk once a family needs several non-A4 sizes
    (`periodical.py` uses four): a typo would render a wrong-sized page
    with no error at all.
    """
    if paper not in PAPERS:
        raise KeyError(f"paper={paper!r} is not one of {', '.join(sorted(PAPERS))}")
    width, height = PAPERS[paper]
    return f"""<!doctype html><html lang="vi"><head><meta charset="utf-8"><style>
{{FONT_FACES}}
@page{{size:{paper} portrait;margin:0;}}
*{{box-sizing:border-box;}}
html,body{{margin:0;padding:0;background:#fff;}}
#sheet{{
  position:relative;width:{width};min-height:{height};padding:{padding};
  background:#fff;color:{colour};font-family:{font};font-size:{size};
  line-height:{line_height};overflow:hidden;-webkit-font-smoothing:antialiased;
}}
table{{width:100%;border-collapse:collapse;}}
thead.once{{display:table-row-group;}}
td.r,th.r,.r{{text-align:right;}}
td.c,th.c,.c{{text-align:center;}}
.sub{{font-style:italic;color:#3a3a3a;}}
.foot div{{margin-top:.4mm;}}
{css}
</style></head><body><div id="sheet">{body}</div></body></html>"""


__all__ = [
    "EVERY_RUN",
    "MONO", "ORNAMENT_DIR", "PAPERS", "REPO_ROOT", "SANS", "SERIF", "Rows",
    "align_class", "bilingual_field_line", "cell", "columns_of", "comb_box",
    "document", "esc", "field_line",
    "footer_block", "initials", "item_rows", "items_table", "key_strip",
    "ncols_of", "notes_blocks", "ornament_url", "party_pairs", "party_rows",
    # No `signed_lines` -- 459dfd4 deleted the function (zero callers) and
    # took it out of this list; a later rewrite of the list put the name
    # back without the function, so `from base import *` raised.
    "qr_svg", "rng_for", "safe_align", "signature_block",
    "span", "stamp", "structure_tokens",
    "totals_block", "words_block",
]
