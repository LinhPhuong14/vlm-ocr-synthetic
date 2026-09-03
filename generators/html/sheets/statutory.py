"""The printed-form family: a ruled sheet with a serial block and two signatures.

Drawn from two of the references. `samples/invoice-templates/invoice_vat_summary.html`
is the electronic invoice's rendition: a double border, the seller in a box with
a QR beside it, an eight-column item table and a second table that splits the
money by tax rate. `samples/invoice-templates/invoice_export.html` is the
bilingual export form: a violet rule, a watermark, party fields on dotted lines
and a single signature, because the buyer is abroad and does not sign this copy.

They are one family because the *structure* is one structure -- head, parties,
ruled table, amount in words, signatures, small print -- and differ in dress and
in which blocks the layout file asks for. Which blocks those are is read from
`sections:`, so a layout that drops the summary table drops it here too without
this module being told twice.

`invoice_vat_form` and the two utility bills come through here as well: they are
the same printed form with a different set of columns, and the columns come from
the layout file.
"""

from __future__ import annotations

from . import base
from .base import Rows, esc, span

# Ink a real form is printed in. Drawn by seed so a run varies, and only from
# this list so it never lands on a colour no printer would buy.
LIVERIES = [
    # frame, title, serial, wash (the pale border of the boxed rendition)
    ("#2b2b2b", "#d51a1a", "#d51a1a", "#c9dcf0"),
    ("#1f3864", "#1f3864", "#c0161d", "#dbe3f2"),
    ("#6f5aa8", "#16181d", "#d21f1f", "#e6e0f2"),
    ("#0b5c3f", "#0b5c3f", "#c0161d", "#d8ece1"),
    ("#7a1f2b", "#b3121a", "#b3121a", "#f0dcdf"),
]


def _serial_rows(receipt, parse: dict) -> list[tuple[str, str]]:
    """"Mẫu số / Ký hiệu / Số", from the strip when the layout has one.

    A statutory form carries these three in the top right corner whether the
    layout calls them a `strip` or leaves them to the letterhead, so both
    spellings end up in the same block rather than in two different ones.
    """
    invoice = parse.get("invoice") or {}
    strip = base.party_pairs(receipt, parse, "strip")
    if strip:
        return strip
    out = []
    for key, label in (("form_no", "Mẫu số:"), ("serial", "Ký hiệu:"),
                       ("number", "Số:")):
        if invoice.get(key):
            out.append((label, invoice[key]))
    return out


def _head(recipe, receipt, parse: dict, spec: dict, livery) -> str:
    frame, title_ink, serial_ink, _wash = livery
    store = parse.get("store") or {}
    invoice = parse.get("invoice") or {}
    mark = base.initials(store.get("name", ""))

    rows = _serial_rows(receipt, parse)
    serial = "".join(
        f'<tr><td class="k">{span("invoice.field.label", label)}</td>'
        f'<td class="v">{span("invoice.field", value)}</td></tr>'
        for label, value in rows)

    period = invoice.get("period", "")
    subtitle = invoice.get("subtitle", "")
    return f"""<div class="head">
<div class="hl"><div class="mk">{esc(mark)}</div>
<div class="ml">{span("store.branch", store.get("branch", ""))}</div></div>
<div class="hm">{span("title", parse.get("title", ""), "t1")}
<div class="t2">{span("subtitle", subtitle)}</div>
<div class="t3">{span("period", period)}</div></div>
<div class="hr"><table class="serial">{serial}</table></div>
</div>"""


def _letterhead(parse: dict, spec: dict, *, qr: bool) -> str:
    """The seller, in the box the rendition prints it in.

    The QR is a real code over the serial and the tax number, so anything that
    scans the page can be checked against the label rather than against a
    picture of a QR code.
    """
    store = parse.get("store") or {}
    invoice = parse.get("invoice") or {}
    labels = (spec.get("letterhead") or {}).get("labels") or {}
    lines = []
    for key, fallback in (("address", "Địa chỉ:"), ("address2", ""),
                          ("tax_code", "Mã số thuế:"), ("phone", "Điện thoại:"),
                          ("account", "Số tài khoản:"), ("website", "")):
        value = store.get(key)
        if not value:
            continue
        label = labels.get(key, fallback)
        lines.append(
            f'<p>{span(f"store.{key}.label", label, "lbl")} '
            f'{span(f"store.{key}", value)}</p>')
    code = ""
    if qr:
        payload = " ".join(part for part in (
            store.get("tax_code", ""), invoice.get("serial", ""),
            invoice.get("number", "")) if part)
        code = base.qr_svg(payload, 22.0)
    return f"""<div class="seller">
{f'<div class="qr">{code}</div>' if code else ''}
<div class="sbody">{span("store.name", store.get("name", ""), "sname")}
{"".join(lines)}</div></div>"""


def _parties(receipt, parse: dict, spec: dict) -> str:
    settings = spec.get("parties") or {}
    stacked = settings.get("style") == "stacked"
    leader = bool(settings.get("leader"))
    left = base.party_pairs(receipt, parse, "left")
    right = base.party_pairs(receipt, parse, "right")
    if not left and not right:
        return ""
    if stacked:
        # One field a line, running the full width: on the printed form the
        # dotted rule has to be long enough to look like a rule.
        blocks = []
        for group in (left, right):
            if not group:
                continue
            blocks.append('<div class="block">' + "".join(
                base.field_line(label, value, leader=leader)
                for label, value in group) + "</div>")
        return "".join(blocks)
    split = float(settings.get("split", 0.5))
    return f"""<div class="parties">
<div class="pcol" style="width:{split * 100:.0f}%">{"".join(
    base.field_line(label, value, leader=leader) for label, value in left)}</div>
<div class="pcol" style="width:{(1 - split) * 100:.0f}%">{"".join(
    base.field_line(label, value, leader=leader) for label, value in right)}</div>
</div>"""


def _summary_table(parse: dict, spec: dict, rows: Rows) -> str:
    """The "Tổng hợp" table: the money split by tax rate.

    A second table on the same sheet, and the reason the row counter is shared
    -- `base.items_table` took the same `rows` for the item table above it, and
    `render_table(table, rows=rows)` here just keeps advancing the one counter
    both tables draw their `data-row` numbers from. Its columns are its own --
    five, not eight -- and it is precisely because the browser resolves each
    table's columns independently that the two can sit on one page without
    anybody working out where the edges should fall.
    """
    from components.table import Border, Cell, Column, Row, TableSpec, render_table

    summary = (parse.get("invoice") or {}).get("summary") or []
    settings = spec.get("vat_summary") or {}
    columns = settings.get("columns") or []
    if not summary or not columns:
        return ""
    ncols = base.ncols_of(spec)
    resolved = base.columns_of({"columns": columns, "width": [ncols, ncols]}, ncols)

    table_columns = [
        Column(width=column["pct"], align=base.safe_align(column.get("align", "left")),
              valign=None)
        for column in resolved
    ]
    header = Row([
        Cell(span("colhdr", column.get("title", "")), html=True, kind="colhdr",
            align=base.safe_align(column.get("title_align", "center")),
            cls=base.align_class(column.get("title_align", "center")))
        for column in resolved
    ], header=True)

    body_rows = []
    for position, entry in enumerate(summary):
        last = position == len(summary) - 1
        body_rows.append(Row([
            Cell(span(f"summary.{column['key']}", entry.get(column["key"], "")), html=True,
                kind=f"summary.{column['key']}",
                align=base.safe_align(column.get("align", "left")),
                cls=base.align_class(column.get("align", "left")))
            for column in resolved
        ], cls="grand" if last else ""))

    table = TableSpec(rows=[header, *body_rows], columns=table_columns,
                      border=Border.none(), cls="items sum")
    return render_table(table, rows=rows)


def _stamp(parse: dict) -> str:
    """The green box a Vietnamese e-invoice prints where a signature would be."""
    invoice = parse.get("invoice") or {}
    if not invoice.get("signed_by"):
        return ""
    # The tick is floated rather than positioned, and comes first so the float
    # has a line to sit on. Positioning it would mean positioning the box, and a
    # positioned box has its text painted after everything else on the page --
    # which is how `sign.signedby` stopped being findable in the PDF's character
    # stream the first time this was written.
    return (f'<div class="signbox"><span class="tick">&#10004;</span>'
            f'<div>{span("sign.signedby", invoice.get("signed_by", ""))}</div>'
            f'<div>{span("sign.signedat", invoice.get("signed_at", ""))}</div>'
            f'</div>')


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    rng = base.rng_for(recipe)
    livery = LIVERIES[rng.randrange(len(LIVERIES))]
    frame, title_ink, serial_ink, wash = livery
    sections = spec.get("sections") or []
    rows = Rows()

    totals = []
    entries = list((parse.get("total") or {}).items())
    notes = list(getattr(getattr(receipt, "invoice", None), "notes", []) or [])
    for index, (label, value) in enumerate(entries):
        entry = {"label": label, "value": value,
                 "grand": index == len(entries) - 1}
        if index == 0 and notes and "notes" in sections:
            entry["lead"] = ("invoice.field", notes[0], 3)
        totals.append(entry)

    table = base.items_table(spec, receipt, parse, rows,
                             totals=totals if "totals" in sections else None)
    blocks = []
    for name in sections:
        # The title and the serial block are the head, and the head is drawn
        # once above the loop -- on a printed form they are one band across the
        # top of the sheet, not two blocks that happen to follow each other.
        if name in ("doctitle", "strip"):
            continue
        if name == "letterhead":
            blocks.append(_letterhead(parse, spec, qr="summary_table" in recipe.layout.tags
                                      or bool((spec.get("letterhead") or {}).get("frame"))))
        elif name == "parties":
            blocks.append(_parties(receipt, parse, spec))
        elif name == "table":
            blocks.append(table)
        elif name == "vat_summary":
            blocks.append('<div class="gap"></div>')
            blocks.append(_summary_table(parse, spec, rows))
        elif name == "words":
            blocks.append(base.words_block(receipt, parse))
        elif name == "signatures":
            block = base.signature_block(receipt, parse, stamp=_stamp(parse))
            if block.count('class="sign"') == 1:
                block = block.replace('<div class="signs">', '<div class="signs one">', 1)
            blocks.append(block)
        elif name == "footer":
            blocks.append(base.footer_block(parse))

    watermark = (f'<div class="wm">{esc(base.initials((parse.get("store") or {}).get("name", "")))}</div>')
    body = (f'<div class="frame"><div class="inner">{watermark}'
            f'{_head(recipe, receipt, parse, spec, livery)}<div class="rule"></div>'
            f'{"".join(block for block in blocks if block)}</div></div>')

    css = f"""
#sheet{{padding:8mm;}}
.frame{{border:2.2mm solid {wash};padding:1.2mm;}}
.inner{{border:.35mm solid {frame};padding:3mm 3.5mm 2mm;position:relative;
        overflow:hidden;z-index:0;}}
/* Behind everything, and behind it by `z-index`, not by positioning its
   siblings. A negative z-index paints in the step before in-flow content, so
   the rest of the sheet stays unpositioned -- and unpositioned content is what
   keeps WeasyPrint's character stream in the order the markup is in. */
.wm{{position:absolute;left:0;right:0;top:38%;text-align:center;font-family:{base.SANS};
     font-weight:bold;font-size:52pt;color:{wash};letter-spacing:3pt;z-index:-1;}}
.head{{display:table;width:100%;}}
.head > div{{display:table-cell;vertical-align:top;}}
.hl{{width:27%;}}
.hm{{width:46%;text-align:center;}}
.hr{{width:27%;}}
.mk{{font-family:{base.SANS};font-weight:bold;font-size:17pt;color:{title_ink};letter-spacing:-.4pt;}}
.ml{{font-size:6.4pt;letter-spacing:1.6pt;color:#444;}}
.t1{{display:block;color:{title_ink};font-weight:bold;font-size:16pt;line-height:1.12;}}
.t2{{font-style:italic;font-size:8.4pt;padding-top:.8mm;}}
.t3{{font-size:8.6pt;padding-top:1mm;}}
/* `max-width` and a break opportunity, or a long value runs off the sheet.
   The serial block sits in the header's right-hand cell with no width of its
   own, so `TECHCOMBANK - CN HOÀN KIẾM` in a bank-account row widened the table
   until the box ended 10px past the trim -- on the bare phôi, no dressing
   involved. `pipeline/invariants.py` refuses to assemble a shard containing
   that page, which is how a 250-page run came back FAIL. */
table.serial{{font-size:8.4pt;max-width:100%;}}
table.serial td{{padding:.5mm 0;vertical-align:top;}}
table.serial .k{{font-weight:bold;white-space:nowrap;padding-right:2mm;width:1%;}}
table.serial .v{{font-weight:bold;color:{serial_ink};overflow-wrap:anywhere;}}
.rule{{border-top:.35mm solid {frame};margin:2mm 0 0;}}
.seller{{display:table;width:100%;padding:2mm 0 1.5mm;}}
.seller > div{{display:table-cell;vertical-align:top;}}
.seller .qr{{width:26mm;padding-right:4mm;}}
.seller .sname{{display:block;font-weight:bold;font-size:11pt;padding-bottom:.8mm;}}
.seller p{{margin:.5mm 0;}}
.seller .lbl{{font-weight:bold;}}
/* `table-layout:fixed` and an explicit half each, or the two party columns
   size to their content: a nowrap label plus a long value made the right-hand
   column wider than half the sheet and pushed `TẠI NGÂN HÀNG: TECHCOMBANK -
   CN HOÀN KIẾM` 10px past the trim. On the bare phôi, with no dressing
   involved -- `pipeline/invariants.py` refused the shard that contained it. */
.parties{{display:table;table-layout:fixed;width:100%;padding:1.5mm 0 1mm;}}
.pcol{{display:table-cell;vertical-align:top;padding-right:3mm;width:50%;}}
.block{{padding:1mm 0 1.5mm;}}
.f{{display:table;width:100%;margin-bottom:.9mm;}}
.f > span{{display:table-cell;}}
.f .k{{width:1%;white-space:nowrap;padding-right:1.5mm;font-weight:bold;}}
.f .v{{width:99%;font-weight:bold;overflow-wrap:anywhere;}}
.f.dot .v{{border-bottom:.3mm dotted #555;padding-bottom:.4mm;}}
table.items{{margin-top:1mm;}}
table.items th,table.items td{{border:.3mm solid {frame};padding:1mm 1.2mm;vertical-align:top;}}
table.items th{{text-align:center;font-weight:bold;font-size:7.8pt;line-height:1.16;background:#f0f0f0;}}
tr.colnum td{{text-align:center;font-size:7pt;color:#555;padding:.5mm;}}
tr.blank td{{height:5.4mm;}}
tr.total td,tr.grand td{{background:#fafafa;}}
tr.grand td{{font-weight:bold;background:#f0f0f0;}}
td.tlabel{{text-align:right;font-weight:bold;}}
td.tlead{{font-weight:bold;}}
.gap{{height:2mm;}}
table.sum{{margin-top:0;}}
table.sum td{{height:4.6mm;}}
.words{{border:.3mm solid {frame};border-top:0;padding:1.4mm 1.2mm;font-weight:bold;}}
.words .wl{{margin-right:1.5mm;}}
/* One signature or two. The export form has only the seller's -- the buyer is
   abroad and never signs this copy -- and on the reference sheet that block sits
   in the right-hand half rather than centred across the page. */
.signs{{display:table;width:100%;padding-top:3mm;}}
.signs.one{{width:52%;margin-left:auto;}}
.sign{{display:table-cell;text-align:center;vertical-align:top;}}
.sign .t{{font-weight:bold;}}
.sign .n{{font-size:7.4pt;font-style:italic;}}
.sign .who{{margin-top:14mm;}}
.signbox{{margin:8mm 0 0 auto;width:62mm;min-height:13mm;border:.5mm solid #17a44b;
          color:#17a44b;text-align:left;padding:1.4mm 2mm;font-size:6.8pt;
          line-height:1.3;word-wrap:break-word;overflow-wrap:break-word;}}
.signbox .tick{{float:right;font-size:13pt;line-height:1;padding-left:1.5mm;}}
.foot{{text-align:center;font-size:7pt;font-style:italic;padding-top:4mm;}}
"""
    return base.document(body, css, paper="A4", padding="8mm",
                         font=base.SERIF, size="8.6pt", colour="#000")


__all__ = ["LIVERIES", "build"]
