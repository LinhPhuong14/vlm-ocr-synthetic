"""The form family: fields in a block, not a party either side of a table.

Root 3 of `docs/root-document-taxonomy.md` (Form / Application) is a
different genre from every invoice this repo already draws: "who is
buying what" is not the question these ten layouts answer. A
questionnaire asks a handful of fields and one paragraph; a timesheet asks
a grid; a marriage declaration asks the same fields twice, side by side; a
budget request asks which of seven boxes are ticked. What they share is
this repo's own `sections:`/flag vocabulary -- read from the layout file,
dispatched here -- the same shape `modern.py` settled on for root 1's ten,
not a new family per layout.

`generators/html/components/table.py` draws every ruled grid in this module (the
activity table, the timesheet roster) the same way `modern.py`'s
`_grid_items_table` does for INV-01: full borders, real `span()` content
inside cells `table.py` only frames.

Checkboxes are new furniture this family introduces (`_checklist`): a
glyph, not a ground-truth field. The item beside it -- one line of
`invoice.notes` -- is real, printed text; whether its box reads ☐ or ☑ is
decided fresh at render time and never claimed as something the document
"said", the same reasoning `invoice_multipage`'s page marker and this
family's own government masthead and photo placeholder already follow.
"""

from __future__ import annotations

import random

from . import base
from .base import Rows, esc, span

# A civil-service palette -- muted, not a shop's house colour.
LIVERIES = ["#2c3e50", "#374a3d", "#4a3728", "#3d3d3d"]

# The masthead every real Vietnamese official form carries, word for word,
# on every one of them -- furniture, not a sampled field. See `_govt_masthead`.
NATIONAL_MASTHEAD = ("CỘNG HÒA XÃ HỘI CHỦ NGHĨA VIỆT NAM", "Độc lập - Tự do - Hạnh phúc")


def _govt_masthead() -> str:
    return (f'<div class="govt"><div class="g1">{esc(NATIONAL_MASTHEAD[0])}</div>'
            f'<div class="g2">{esc(NATIONAL_MASTHEAD[1])}</div><div class="grule"></div></div>')


def _photobox() -> str:
    """A blank corner for a portrait photo -- furniture, never `span()`.

    Real registration forms print the box whether or not a photo is glued
    in; the box itself carries no field of the document's own.
    """
    return '<div class="photobox">Ảnh<br>4x6</div>'


def _orgname(parse: dict) -> str:
    """The issuing organisation's own line -- name, and whatever contact
    fields the store happens to carry.

    Every receipt has a `store`, whatever the document -- an insurer issues
    `authorisation_letter`, a hospital issues `medical_statement`, and a form
    root document has one too, print-if-present the same way `modern.py::
    _masthead` reads it. Without this, `store.name` sits in the label with
    no run to show for it on every one of this family's ten layouts, which
    is exactly the failure that surfaced when this line was still missing.
    """
    store = parse.get("store") or {}
    lines = "".join(
        f'<div class="orgc">{span(f"store.{key}", store[key])}</div>'
        for key in ("address", "address2", "phone", "website", "tax_code", "account")
        if store.get(key))
    branch = span("store.branch", store.get("branch", ""), "orgb")
    return f'<div class="org">{span("store.name", store.get("name", ""), "on")}{branch}{lines}</div>'


def _doctitle(parse: dict) -> str:
    invoice = parse.get("invoice") or {}
    rows = "".join(
        f'<div>{span(f"invoice.{key}", invoice[key])}</div>'
        for key in ("serial", "subtitle") if invoice.get(key))
    meta = f'<div class="docmeta">{rows}</div>' if rows else ""
    return f'{span("title", parse.get("title", ""), "doc")}{meta}'


def _fields_block(pairs: list[tuple[str, str]], *, title: str = "") -> str:
    if not pairs:
        return ""
    rows = "".join(
        f'<div class="frow">{span("invoice.field.label", label, "k")} '
        f'{span("invoice.field", value, "v")}</div>'
        for label, value in pairs)
    head = f'<div class="fcap">{esc(title)}</div>' if title else ""
    return f'<div class="fields">{head}{rows}</div>'


def _fields_two(receipt, parse: dict) -> str:
    """The same field shape, twice, side by side -- see `form_two_column.yaml`."""
    left = base.party_pairs(receipt, parse, "left")
    right = base.party_pairs(receipt, parse, "right")
    if not left and not right:
        return ""
    invoice = getattr(receipt, "invoice", None)
    left_title = getattr(invoice, "left_title", "") if invoice else ""
    right_title = getattr(invoice, "right_title", "") if invoice else ""

    def rows_of(pairs):
        return "".join(
            f'<div class="frow">{span("invoice.field.label", label, "k")} '
            f'{span("invoice.field", value, "v")}</div>'
            for label, value in pairs)

    lcap = span("parties.left_title", left_title, "fcap") if left_title else ""
    rcap = span("parties.right_title", right_title, "fcap") if right_title else ""
    return (f'<div class="fields-two"><div class="fcol">{lcap}{rows_of(left)}</div>'
            f'<div class="fcol">{rcap}{rows_of(right)}</div></div>')


def _sectioned(letter: str, title: str, body: str) -> str:
    if not body:
        return ""
    return (f'<div class="section"><div class="shead">'
            f'<span class="sl">{esc(letter)}.</span> {esc(title)}</div>{body}</div>')


def _checklist(receipt, spec: dict, rng: random.Random) -> str:
    """`invoice.notes`, one line per checkbox row.

    The text is real -- the same `notes` a paragraph-style block prints
    elsewhere -- and gets the same `span()`. The mark in front of it does
    not: `checked` is drawn fresh here, per row, and carries no `data-kind`,
    for the reason this module's own docstring gives.
    """
    invoice = getattr(receipt, "invoice", None)
    lines = list(getattr(invoice, "notes", []) or [])
    if not lines:
        return ""
    settings = spec.get("checklist") or {}
    rate = float(settings.get("checked_rate", 0.4))
    rows = []
    for line in lines:
        mark = "☑" if rng.random() < rate else "☐"
        rows.append(f'<div class="crow"><span class="box">{mark}</span>'
                    f'{span("note", line)}</div>')
    return f'<div class="checklist">{"".join(rows)}</div>'


def _notes_block(receipt, spec: dict) -> str:
    """Declaration-style paragraphs -- `invoice.notes`, split on blank lines.

    `base.notes_blocks` does the splitting (shared with `modern.py::_notes`);
    turning a block into `<p>` tags, and a line ending in ":" into a heading,
    is this family's own.
    """
    invoice = getattr(receipt, "invoice", None)
    lines = list(getattr(invoice, "notes", []) or [])
    if not lines:
        return ""
    blocks = base.notes_blocks(lines)
    out = []
    for block in blocks:
        for value in block:
            cls = "nh" if value.endswith(":") else ""
            out.append(f'<p class="{cls}">{span("note", value.rstrip(":"))}</p>')
    return f'<div class="notes">{"".join(out)}</div>'


def _item_table(spec: dict, receipt, parse: dict, rows) -> str:
    """A small ruled table -- activity records, project data, technical
    parameters -- on the shared `table` component. See `modern.py::
    _grid_items_table`, the same recipe: `table.py` frames it, `span()`
    still carries every value's ground truth.
    """
    from components.table import Border, Cell, Column, Row, TableSpec, render_table
    from rulebase.layout import item_values

    columns = base.columns_of(spec, base.ncols_of(spec))
    if not columns:
        return ""
    plan = base.item_rows(spec)
    template = plan[0] if plan else [{"col": c["key"], "from": c["key"]} for c in columns]
    by_col = {entry["col"]: entry["from"] for entry in template}

    header = Row([Cell(span("colhdr", c.get("title", "")), html=True,
                       align=c.get("title_align", "center")) for c in columns],
                header=True, bg="#eef0f2")
    table_rows = [header]
    for item in receipt.items:
        values = item_values(item, receipt)
        cells = []
        for column in columns:
            source = by_col.get(column["key"], column["key"])
            text = values.get(source, "")
            cells.append(Cell(span(f"menu.{source}", text), html=True,
                              align=column.get("align", "left")))
        table_rows.append(Row(cells))

    table_spec = TableSpec(
        rows=table_rows,
        columns=[Column(width=c["pct"], align=c.get("align", "left")) for c in columns],
        border=Border.grid(0.2, color="#9aa3ab"),
    )
    return render_table(table_spec, rows=rows)


def _roster_table(spec: dict, receipt, parse: dict, rows, rng: random.Random) -> str:
    """The timesheet grid: one real row per person, decorative day columns.

    `receipt.items` supplies the rows -- `item.name` read as a person's
    name, `item.qty` as their total -- exactly the columns `columns:` in
    `form_timesheet_grid.yaml` names, both real `span()` content. The day
    columns after them are furniture: `grid.days` names how many, plain
    marks, not `span()`, for the reason `_checklist` above gives for its
    own marks -- there is no per-day attendance value sampled anywhere to
    be true or false about. `rng` is `build()`'s own, seeded off
    `recipe.seed`, so the marks are as reproducible as everything else on
    the page rather than drifting between two runs of the same seed.
    """
    from components.table import Border, Cell, Column, Row, TableSpec, render_table
    from rulebase.layout import item_values

    columns = base.columns_of(spec, base.ncols_of(spec))
    if not columns:
        return ""
    plan = base.item_rows(spec)
    template = plan[0] if plan else [{"col": c["key"], "from": c["key"]} for c in columns]
    by_col = {entry["col"]: entry["from"] for entry in template}
    settings = spec.get("grid") or {}
    days = list(settings.get("days") or ["T2", "T3", "T4", "T5", "T6", "T7", "CN"])

    head_cells = [Cell(span("colhdr", c.get("title", "")), html=True,
                       align=c.get("title_align", "center")) for c in columns]
    head_cells += [Cell(esc(day), align="center") for day in days]
    table_rows = [Row(head_cells, header=True, bg="#eef0f2")]
    for item in receipt.items:
        values = item_values(item, receipt)
        cells = []
        for column in columns:
            source = by_col.get(column["key"], column["key"])
            text = values.get(source, "")
            cells.append(Cell(span(f"menu.{source}", text), html=True,
                              align=column.get("align", "left")))
        for _ in days:
            mark = "x" if rng.random() < 0.75 else ""
            cells.append(Cell(mark, align="center", color="#888"))
        table_rows.append(Row(cells))

    # `columns_of`'s own `pct` only sums to 100 when the layout leaves one
    # column flexible (`width: 0`) to absorb the rest -- this table's three
    # real columns are all fixed-width, so that field is left partly
    # unaccounted for here and the split is done directly instead: the real
    # columns share a fixed 42% of the table in proportion to their own
    # declared widths, the day columns split what is left evenly.
    real_total = float(sum(int(c.get("width") or 1) for c in columns)) or 1.0
    real_share = 42.0
    day_share = (100.0 - real_share) / max(len(days), 1)
    table_spec = TableSpec(
        rows=table_rows,
        columns=([Column(width=real_share * (int(c.get("width") or 1) / real_total),
                         align=c.get("align", "left")) for c in columns]
                 + [Column(width=day_share, align="center") for _ in days]),
        border=Border.grid(0.2, color="#9aa3ab"),
    )
    return render_table(table_spec, rows=rows)


def _section_html(name: str, receipt, spec: dict, parse: dict, sections: list,
                  rng: random.Random, rows: Rows) -> str:
    if name in ("header", "letterhead"):
        pieces = [_orgname(parse)]
        if (spec.get("header") or {}).get("masthead") == "govt":
            pieces.append(_govt_masthead())
        if (spec.get("page") or {}).get("photobox"):
            pieces.append(_photobox())
        pieces.append(_doctitle(parse))
        return f'<div class="head">{"".join(pieces)}</div>'
    # Section *names* are the character grid's own vocabulary
    # (`rulebase.layout.SECTIONS`) throughout, on purpose: `build_grid` --
    # used by `preflight.sheet_overflow` and by every geometry test in
    # `tests/test_layout.py` -- raises on a name it does not recognise, and
    # every other layout in this rule-base builds on the grid whether or not
    # a real dataset run ever takes that path. This family's own shapes
    # (a two-column field block, a checkbox list, a lettered A/B split, a
    # roster grid) are read from a second, family-specific key under the
    # *same* section instead of inventing new section names for them --
    # `fields`, `checklist`, `sectioned`, `grid` below are all spec keys, not
    # entries in `sections:`.
    if name == "parties":
        settings = spec.get("fields") or {}
        if settings.get("columns") == "two":
            block = _fields_two(receipt, parse)
        else:
            # `left` and `right` both flow into the single column in order --
            # `form_brief.yaml` gives every one of its layouts a `right` list
            # too (a manager, a phone number), and printing only `left` would
            # leave those in the label with no run.
            pairs = base.party_pairs(receipt, parse, "left") + base.party_pairs(receipt, parse, "right")
            block = _fields_block(pairs)
        sectioned = spec.get("sectioned")
        if sectioned:
            titles = sectioned.get("titles") or ["Thông tin chung", "Số liệu"]
            return _sectioned("A", titles[0], block)
        return block
    if name == "table":
        table = (_roster_table(spec, receipt, parse, rows, rng) if spec.get("grid")
                else _item_table(spec, receipt, parse, rows))
        sectioned = spec.get("sectioned")
        if sectioned:
            titles = sectioned.get("titles") or ["Thông tin chung", "Số liệu"]
            return _sectioned("B", titles[1] if len(titles) > 1 else "Số liệu", table)
        return table
    if name == "notes":
        if spec.get("checklist"):
            return _checklist(receipt, spec, rng)
        return _notes_block(receipt, spec)
    if name == "totals":
        return base.totals_block(parse, indent=0.55)
    if name == "signatures":
        return base.signature_block(receipt, parse)
    if name == "footer":
        return base.footer_block(parse)
    return ""


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    rng = base.rng_for(recipe, 0x46524D)  # "FRM"
    ink = LIVERIES[rng.randrange(len(LIVERIES))]
    sections = spec.get("sections") or []
    rows = Rows()

    blocks = [_section_html(name, receipt, spec, parse, sections, rng, rows) for name in sections]
    body = "".join(block for block in blocks if block)

    css = f"""
.head{{margin-bottom:5mm;}}
.org{{text-align:center;margin-bottom:2mm;}}
.org .on{{display:block;font-weight:bold;font-size:9.4pt;letter-spacing:.3pt;color:{ink};}}
.org .orgb{{display:block;font-size:6.8pt;letter-spacing:1.6pt;color:{ink};margin-top:.6mm;}}
.orgc{{font-size:7pt;color:#4a4a4a;margin-top:.4mm;}}
.govt{{text-align:center;margin-bottom:4mm;}}
.g1{{font-weight:bold;font-size:9pt;}}
.g2{{font-size:8.4pt;margin-top:.5mm;}}
.grule{{width:26mm;border-top:.3mm solid #333;margin:1.4mm auto 0;}}
.photobox{{float:right;width:24mm;height:32mm;border:.25mm solid #666;
   text-align:center;font-size:6.6pt;color:#888;padding-top:12mm;margin-left:4mm;}}
.doc{{display:block;text-align:center;font-size:14pt;font-weight:bold;
   letter-spacing:.4pt;margin:2mm 0 0;}}
.docmeta{{text-align:center;font-size:7.4pt;color:#444;margin-top:1.4mm;}}
.docmeta div{{margin-bottom:.4mm;}}
.fields{{margin:4mm 0;}}
.fcap{{font-weight:bold;font-size:7.6pt;letter-spacing:.6pt;color:{ink};margin-bottom:1.6mm;}}
.frow{{margin-bottom:1.4mm;}}
.frow .k{{font-weight:bold;margin-right:1.2mm;}}
.fields-two{{display:table;width:100%;margin:4mm 0;border-top:.3mm solid #ccc;padding-top:3mm;}}
.fcol{{display:table-cell;width:50%;vertical-align:top;padding-right:5mm;}}
.section{{margin:4mm 0;}}
.shead{{font-weight:bold;font-size:8.6pt;color:{ink};margin-bottom:2mm;
   border-bottom:.25mm solid #ccc;padding-bottom:1mm;}}
.shead .sl{{font-size:10pt;}}
.checklist{{margin:4mm 0;}}
.crow{{margin-bottom:1.8mm;}}
.crow .box{{display:inline-block;width:5mm;font-size:9pt;text-align:center;}}
.notes{{margin:4mm 0;}}
.notes p{{margin:1.6mm 0;}}
.notes p.nh{{font-weight:bold;margin-top:3mm;}}
.totals{{margin:5mm 0;}}
.trow{{display:table;width:100%;padding:.6mm 0;}}
.trow .lab{{display:table-cell;text-align:right;padding-right:4mm;}}
.trow .amt{{display:table-cell;text-align:right;width:32%;}}
.trow.grand{{font-weight:bold;border-top:.3mm solid {ink};margin-top:1.6mm;padding-top:1.6mm;}}
.signs{{display:table;width:100%;margin-top:12mm;}}
.sign{{display:table-cell;text-align:center;vertical-align:top;}}
.sign .t{{font-weight:bold;color:{ink};}}
.sign .n{{font-size:6.6pt;font-style:italic;color:#555;}}
.sign .who{{margin-top:14mm;}}
.foot{{margin-top:8mm;text-align:center;font-size:6.6pt;font-style:italic;color:#444;}}
table.items thead th{{font-weight:bold;font-size:7.2pt;}}
table.items tbody td{{padding:1.6mm 1.8mm;}}
"""
    return base.document(body, css, paper="A4", padding="15mm 15mm",
                         font=base.SERIF, size="8.6pt", colour="#1a1a1a",
                         line_height="1.4")


__all__ = ["LIVERIES", "NATIONAL_MASTHEAD", "build"]
