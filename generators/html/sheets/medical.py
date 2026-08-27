"""The hospital bill: twelve columns, grouped rows, four payment sources.

Drawn from `docs/mau/bang_ke_kcb.html`, which was drawn from a scan of Mẫu số
01/KBCB -- the statement of treatment costs every Vietnamese hospital gives a
patient at discharge, and the form the social insurance fund settles against.

It is the widest document in this repository and the one that most needs a real
table. Every line is priced twice, once at the hospital's rate and once at what
the insurance schedule allows, and the money is then split four ways: the fund,
the patient's share of a covered service, whatever was waived, and what the
patient pays outright. Those four sit under one heading spanning four columns
while the nine columns beside them reach down through both header bands. That
is `colspan` and `rowspan`, and nothing else expresses it.

The administrative half above the table is the other half of the document, and
it is not a party block: twenty numbered fields, several to a line, with values
boxed where the form rules a box -- the insurance card number is four boxes
because it is four fields.
"""

from __future__ import annotations

from . import base
from .base import Rows, cell, esc, span

# The pale wash a hospital form is printed with: near-black rules on white, and
# one tint for the header band. Kept sober on purpose -- this is a settlement
# document, not stationery.
LIVERIES = ["#1a1a1a", "#16305c", "#123f2e"]

# The form's own two section captions. Printed, and therefore boxed: text on a
# page with no box is text a reader can see and the label cannot account for --
# and, on the WeasyPrint path, a hundred and thirty characters of unlabelled
# ink for `match_runs` to step over between the last field and the first column
# title, which is more than any sane look-ahead should have to cover.
SECTION_I = "I. Phần hành chính:"
SECTION_II = "II. Phần chi phí khám bệnh, chữa bệnh:"
SECTION_II_NOTE = ("(Mỗi mã thẻ BHYT thống kê phần chi phí khám bệnh, chữa bệnh "
                   "phát sinh tương ứng theo mã thẻ đó).")

# Fields the form rules a box round: a code, a rate, a state. Everything else
# is a value on a line.
BOXED = ("(6) Mã:", "(10) Tình trạng ra viện:", "(16) Mã bệnh:",
         "(18) Mã bệnh kèm theo:", "Mức hưởng:", "(4) Mã thẻ BHYT:")


def _head(receipt, parse: dict, spec: dict) -> str:
    store = parse.get("store") or {}
    strip = base.party_pairs(receipt, parse, "strip")
    keys = "".join(
        f'<div>{span("invoice.field.label", label, "k")} '
        f'{span("invoice.field", value)}</div>'
        for label, value in strip)
    invoice = parse.get("invoice") or {}
    payload = " ".join(part for part in (
        invoice.get("serial", ""), store.get("tax_code", ""),
        next((value for _label, value in strip), "")) if part)
    code = base.qr_svg(payload, 17.0)
    labels = (spec.get("letterhead") or {}).get("labels") or {}
    lines = "".join(
        f'<div>{span(f"store.{key}.label", labels.get(key, ""), "k")} '
        f'{span(f"store.{key}", store[key])}</div>'
        for key in ("branch", "address", "phone", "website") if store.get(key))
    return f"""<div class="head">
<div class="hl"><div class="logo"><span class="g"><b>{esc(base.initials(store.get("name", "")))}</b>
<i>HOSPITAL</i></span><span class="n">{span("store.name", store.get("name", ""))}</span></div>
{lines}</div>
<div class="hm">{keys}</div>
<div class="hr">{code}</div>
</div>"""


def _fields(receipt, parse: dict, spec: dict) -> str:
    """The administrative block: numbered fields, boxed where the form boxes.

    Two columns, because the form is two columns -- the descriptive fields run
    down the left and the codes are ruled into boxes on the right. Which fields
    those are is the document's business (`party_fields` in `rules/document.yaml`),
    not this module's.
    """
    settings = spec.get("parties") or {}
    split = float(settings.get("split", 0.66))
    left = base.party_pairs(receipt, parse, "left")
    right = base.party_pairs(receipt, parse, "right")

    def line(label: str, value: str) -> str:
        box = ' class="boxed"' if label in BOXED else ""
        return (f'<div class="f">{span("invoice.field.label", label, "k")} '
                f'<span{box}>{span("invoice.field", value)}</span></div>')

    return (f'<div class="admin"><div class="al" style="width:{split * 100:.0f}%">'
            + "".join(line(label, value) for label, value in left)
            + '</div><div class="ar">'
            + "".join(line(label, value) for label, value in right)
            + "</div></div>")


def _settlement(parse: dict) -> str:
    """How the total was met, as the form sets it: a list, indented by depth.

    A row whose label starts with "+" is a breakdown of the row above it, so the
    indent is read off the label rather than declared twice. The amounts stay
    `total.line`/`total.grand`, which is what every other sheet calls them and
    what `pipeline/invariants.py` counts.
    """
    totals = list((parse.get("total") or {}).items())
    if not totals:
        return ""
    out = []
    for index, (label, value) in enumerate(totals):
        grand = index == 0
        kind = "total.grand" if grand else "total.line"
        depth = "d2" if label.lstrip().startswith("+") else ("d1" if index else "d0")
        out.append(f'<div class="srow {depth}{" grand" if grand else ""}">'
                   f'{span(f"{kind}.label", label, "lab")}'
                   f'{span(kind, value, "amt")}</div>')
    return f'<div class="settle">{"".join(out)}</div>'


def _sum_row(receipt, spec: dict, columns: list[dict], rows: Rows) -> str:
    """The "Cộng:" line: every money column added down, in the table itself.

    Not in `totals` and deliberately so. `total` in the label is keyed by the
    drawn label, and one row carrying six different sums would have to pick one
    of them to be "the" amount. The six are on the page, they are checkable by
    adding the column up, and the settlement block underneath states the ones a
    reader is meant to take away.
    """
    from rulebase.layout import item_values

    lines = [item for item in receipt.items if not item.is_group]
    if not lines:
        return ""
    benefit = lines[0].benefit
    sums = {
        "amount_bv": sum(item.amount_bv() for item in lines),
        "amount_bh": sum(item.amount_bh() for item in lines),
        "fund": sum(item.fund_bhyt(benefit) for item in lines),
        "copay": sum(item.copay(benefit) for item in lines),
        "other_pay": sum(item.other_pay() for item in lines),
        "self_pay": sum(item.self_pay(benefit) for item in lines),
    }
    del item_values
    keys = [column["key"] for column in columns]
    width = int((spec.get("table") or {}).get("group_span") or 6)
    width = min(max(width, 1), len(columns))
    row = rows.take()
    cells = [cell("td", row, 0, span("total.grand.label", "Cộng:"),
                  kind="total.grand.label", cls="gname", colspan=width)]
    for index in range(width, len(columns)):
        key = keys[index]
        text = receipt.cash(sums[key]) if key in sums else ""
        cells.append(cell("td", row, index, span("total.grand", text) if text else "",
                          kind="total.grand" if text else "",
                          cls=base.align_class(columns[index].get("align", "left"))))
    return '<tr class="sumrow">' + "".join(cells) + "</tr>"


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    rng = base.rng_for(recipe)
    ink = LIVERIES[rng.randrange(len(LIVERIES))]
    sections = spec.get("sections") or []
    rows = Rows()

    columns = base.columns_of(spec, base.ncols_of(spec))
    table = base.items_table(spec, receipt, parse, rows)
    if table and columns:
        table = table.replace("</tbody></table>",
                              _sum_row(receipt, spec, columns, rows) + "</tbody></table>")

    blocks = []
    for name in sections:
        if name in ("letterhead", "strip"):
            continue                  # both are the head, drawn once
        if name == "doctitle":
            blocks.append(span("title", parse.get("title", ""), "doc"))
        elif name == "parties":
            blocks.append(f'<div class="sec">{span("note", SECTION_I)}</div>')
            blocks.append(_fields(receipt, parse, spec))
        elif name == "table":
            blocks.append(f'<div class="sec">{span("note", SECTION_II)}'
                          f'<span class="reg"> {span("note", SECTION_II_NOTE)}</span></div>')
            blocks.append(table)
        elif name == "totals":
            blocks.append(_settlement(parse))
        elif name == "words":
            blocks.append(base.words_block(receipt, parse))
        elif name == "signatures":
            blocks.append(base.signature_block(receipt, parse))
        elif name == "footer":
            blocks.append(base.footer_block(parse))

    body = _head(receipt, parse, spec) + "".join(block for block in blocks if block)
    css = f"""
#sheet{{padding:9mm 8mm;}}
.head{{display:table;width:100%;}}
.head > div{{display:table-cell;vertical-align:top;}}
.hl{{width:46%;}} .hm{{width:38%;}} .hr{{width:16%;text-align:right;}}
.logo{{display:table;margin-bottom:.6mm;}}
.logo > span{{display:table-cell;vertical-align:middle;}}
.logo .g{{padding-right:2mm;}}
.logo .g b{{font-family:{base.SANS};font-weight:bold;font-size:12pt;letter-spacing:-.6pt;
            display:block;border-bottom:.5mm solid {ink};}}
.logo .g i{{font-style:normal;font-size:4.6pt;letter-spacing:1.4pt;display:block;}}
.logo .n{{font-size:10pt;}}
.head .k{{color:#333;}}
.doc{{display:block;text-align:center;font-size:13.5pt;font-weight:bold;
      margin:3mm 0 2mm;letter-spacing:.2pt;color:{ink};}}
.sec{{font-weight:bold;margin:1.4mm 0 .6mm;}}
.sec .reg{{font-weight:normal;}}
.admin{{display:table;width:100%;}}
.al,.ar{{display:table-cell;vertical-align:top;}}
.f{{margin:.8mm 0;}}
.f .k{{font-weight:normal;}}
.boxed{{display:inline-block;border:.3mm solid #111;padding:0 1.8mm;min-width:16mm;
        text-align:center;}}
table.items{{margin-top:2mm;}}
table.items th,table.items td{{border:.25mm solid #111;padding:.7mm 1mm;vertical-align:top;}}
table.items th{{text-align:center;font-weight:bold;font-size:7.2pt;line-height:1.16;
                vertical-align:middle;background:#f2f2f2;}}
tr.colnum td{{text-align:center;font-size:6.8pt;padding:.3mm;color:#444;}}
tr.grouprow td{{font-weight:bold;background:#fafafa;}}
tr.sumrow td{{font-weight:bold;background:#f0f0f0;}}
td.gname{{text-align:left;}}
.settle{{margin-top:2mm;}}
.srow{{margin:.8mm 0;}}
.srow .lab{{padding-right:3mm;}}
.srow .amt{{font-style:italic;}}
.srow.grand .lab{{font-weight:bold;}}
.srow.grand .amt{{font-style:normal;font-weight:bold;}}
.srow.d1{{padding-left:5mm;}} .srow.d2{{padding-left:10mm;}}
.words{{margin-top:1.5mm;font-weight:bold;}}
.words .wl{{margin-right:2mm;}}
.signs{{display:table;width:100%;margin-top:5mm;}}
.sign{{display:table-cell;text-align:center;vertical-align:top;}}
.sign .t{{font-weight:bold;font-size:8pt;}}
.sign .n{{font-style:italic;font-size:7.2pt;}}
.sign .who{{margin-top:14mm;}}
.foot{{margin-top:4mm;text-align:center;font-size:7pt;font-style:italic;color:#444;}}
"""
    return base.document(body, css, paper="A4", padding="9mm 8mm",
                         font=base.SERIF, size="7.8pt", colour="#111",
                         line_height="1.34")


__all__ = ["BOXED", "LIVERIES", "SECTION_I", "SECTION_II", "SECTION_II_NOTE", "build"]
