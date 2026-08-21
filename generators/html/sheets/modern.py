"""The self-designed family: no frame, totals against the right margin.

`samples/invoice-templates/invoice_brand.html` is the reference — a bakery's own
sheet, A5, sans-serif, the trading name spaced out at the top, the item table
ruled only above and below its header, the totals hugging the right edge, and a
two-column footer with the bank on one side and the shop's address on the other.

What makes this family recognisable is mostly what is missing: no border round
the sheet, no column-number row, no signature box. That is not a stylistic
preference, it is the difference between a form somebody was issued and a sheet
somebody designed, and it is what `no_frame` in `rules/layout.yaml` records.

`invoice_tax_en` comes through here too: an English-language invoice from a
software house is the same kind of document, printed on A4.
"""

from __future__ import annotations

import random

from . import base
from .base import Rows, span

# House colours a small business actually picks for its stationery.
LIVERIES = ["#2f5233", "#1f3864", "#6b2f4a", "#8a4b1f", "#0f4c5c"]


def _masthead(parse: dict, spec: dict) -> str:
    """The trading name, the strapline, and whatever contact lines stay up here.

    `header.address: false` in a layout file means the shop's address belongs at
    the foot of the sheet rather than under its name -- the bakery's does -- so
    which keys appear is read from the layout rather than fixed here.
    """
    store = parse.get("store") or {}
    header = {**(spec.get("header") or {}), **(spec.get("letterhead") or {})}
    labels = header.get("labels") or {}
    lines = []
    for key in ("address", "address2", "phone", "website", "tax_code", "account"):
        if header.get(key) is False or not store.get(key):
            continue
        lines.append(f'<div class="cl">{span(f"store.{key}.label", labels.get(key, ""))} '
                     f'{span(f"store.{key}", store[key])}</div>')
    return (f'<div class="brand">{span("store.name", store.get("name", ""), "h1")}'
            f'{span("store.branch", store.get("branch", ""), "tag")}'
            f'{"".join(lines)}</div>')


def _doctitle(parse: dict, meta: bool = True) -> str:
    """The document's name, and the serial block a numbered invoice carries.

    A self-designed invoice still has a number, a date and often a form code.
    The bakery's sheet puts them in a strip under the title; an English tax
    invoice has no `strip` in its `sections:` at all, and without this block its
    serial, its number and its date would be in the label and on no box.
    """
    invoice = parse.get("invoice") or {} if meta else {}
    rows = "".join(
        f'<div>{span(f"invoice.{key}", invoice[key])}</div>'
        for key in ("form_no", "serial", "number", "subtitle", "period")
        if invoice.get(key))
    block = f'<div class="docmeta">{rows}</div>' if rows else ""
    return f'{span("title", parse.get("title", ""), "doc")}{block}'


def _customer(receipt, parse: dict, spec: dict) -> str:
    """The customer block, pushed into the right-hand part of the sheet.

    Both party columns, not one: the bakery names only the customer, while an
    English tax invoice fills `left` with the buyer and `right` with the terms,
    and printing whichever is non-empty would leave the other in the label with
    no box to show for it.
    """
    pairs = base.party_pairs(receipt, parse, "left") + \
        base.party_pairs(receipt, parse, "right")
    if not pairs:
        return ""
    settings = spec.get("parties") or {}
    split = float(settings.get("split", 0.38))
    rows = "".join(
        f'<div class="crow">{span("invoice.field.label", label, "k")} '
        f'{span("invoice.field", value, "v")}</div>'
        for label, value in pairs)
    # The left column stays empty unless the layout gave the block a title. On
    # the reference sheet that space holds a line of the shop's own design, and
    # the nearest real field -- the branch line -- is already in the masthead:
    # printing it twice would put one string in two boxes under two roles.
    title = getattr(getattr(receipt, "invoice", None), "left_title", "")
    return (f'<div class="parties"><div class="pleft" style="width:{split * 100:.0f}%">'
            f'{span("parties.title", title)}</div>'
            f'<div class="pright">{rows}</div></div>')


def _notes(receipt, spec: dict) -> str:
    """Where to send the money, and how to reach the shop.

    The lines are `invoice.notes` -- the same list the character grid prints --
    and a blank line inside it is the break between the two blocks, exactly as
    `_emit_notes` in `rulebase/layout.py` reads it. Roles are per column, not one
    for both: cells are read in row order, so a single role would interleave the
    two and an address wrapped over two lines could never be put back together.
    """
    invoice = getattr(receipt, "invoice", None)
    notes = list(getattr(invoice, "notes", []) or [])
    if not notes:
        return ""
    settings = spec.get("notes") or {}
    blocks: list[list[str]] = [[]]
    for line in notes:
        if line.strip():
            blocks[-1].append(line)
        else:
            blocks.append([])
    blocks = [block for block in blocks if block][:2]
    if not blocks:
        return ""

    def column(values, role, cls, style=""):
        body = "".join(
            f'<div class="{"h" if value.endswith(":") else ""}">'
            f'{span(role, value.rstrip(":"))}</div>' for value in values)
        return f'<div class="{cls}"{style}>{body}</div>'

    if settings.get("style") != "two_column" or len(blocks) < 2:
        return f'<div class="notes">{column(blocks[0], "note.left", "nfull")}</div>'
    split = float(settings.get("split", 0.52))
    width = ' style="width:%.0f%%"' % (split * 100)
    return (f'<div class="notes">'
            f'{column(blocks[0], "note.left", "nleft", width)}'
            f'{column(blocks[1], "note.right", "nright")}</div>')


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    rng = random.Random(recipe.seed ^ 0x5A4D)
    house = LIVERIES[rng.randrange(len(LIVERIES))]
    sections = spec.get("sections") or []
    narrow = "footer_columns" in recipe.layout.tags
    rows = Rows()
    settings = spec.get("totals") or {}

    table = base.items_table(spec, receipt, parse, rows)
    blocks = []
    for name in sections:
        if name in ("header", "letterhead"):
            blocks.append(_masthead(parse, spec))
        elif name == "doctitle":
            # A layout with a `strip` already prints the number and the date in
            # it; repeating them here would put one string in two boxes.
            blocks.append(_doctitle(parse, meta="strip" not in sections))
        elif name == "strip":
            blocks.append(base.key_strip(base.party_pairs(receipt, parse, "strip")))
        elif name == "parties":
            blocks.append(_customer(receipt, parse, spec))
        elif name == "table":
            blocks.append(table)
        elif name == "totals":
            blocks.append(base.totals_block(
                parse, indent=float(settings.get("indent", 0.40))))
        elif name == "notes":
            blocks.append(_notes(receipt, spec))
        elif name == "words":
            blocks.append(base.words_block(receipt, parse))
        elif name == "signatures":
            blocks.append(base.signature_block(receipt, parse))
        elif name == "footer":
            blocks.append(base.footer_block(parse))

    if "doctitle" not in sections:
        # A layout that names no `doctitle` still has a title, and the reference
        # sheet prints it right under the shop's name.
        blocks.insert(1, _doctitle(parse, meta="strip" not in sections))
    body = "".join(block for block in blocks if block)
    css = f"""
.brand{{text-align:center;padding-bottom:6mm;}}
.brand .h1{{display:block;color:{house};font-size:15pt;font-weight:bold;letter-spacing:1.4pt;}}
.brand .tag{{display:block;margin-top:1.6mm;color:{house};font-size:6.4pt;letter-spacing:3.4pt;}}
.brand .cl{{font-size:6.6pt;color:#4a4a4a;margin-top:.8mm;}}
.doc{{display:block;text-align:center;margin:0 0 2mm;font-size:15pt;letter-spacing:.6pt;}}
.docmeta{{text-align:center;font-size:6.8pt;color:#4a4a4a;margin-bottom:6mm;}}
.docmeta div{{margin-bottom:.5mm;}}
.strip{{text-align:center;font-size:6.8pt;color:#4a4a4a;margin-bottom:5mm;}}
.strip .sep{{padding:0 1.2mm;color:#aaa;}}
.parties{{display:table;width:100%;margin-bottom:7mm;}}
.pleft,.pright{{display:table-cell;vertical-align:top;}}
.pleft{{font-weight:bold;font-size:7pt;line-height:1.6;color:{house};}}
.crow{{margin-bottom:.8mm;}}
.crow .k{{color:#4a4a4a;}}
table.items thead th{{font-weight:normal;color:#4a4a4a;font-size:6.8pt;text-align:left;
   padding:2mm 1.5mm;border-top:.4mm solid {house};border-bottom:.4mm solid {house};}}
table.items th.r{{text-align:right;}} table.items th.c{{text-align:center;}}
table.items tbody td{{padding:2.4mm 1.5mm;vertical-align:top;}}
table.items tbody tr + tr td{{border-top:.15mm solid #d8d8d8;}}
table.items tbody tr:last-child td{{border-bottom:.4mm solid {house};}}
.totals{{margin-top:6mm;}}
.trow{{display:table;width:100%;padding:.8mm 0;}}
.trow .lab{{display:table-cell;text-align:right;padding-right:4mm;}}
.trow .amt{{display:table-cell;text-align:right;width:34%;}}
.trow.grand{{font-weight:bold;margin-top:3mm;border-top:.3mm solid {house};padding-top:1.6mm;}}
.notes{{display:table;width:100%;margin-top:14mm;font-size:6.8pt;}}
.nleft,.nright,.nfull{{display:table-cell;vertical-align:top;}}
.notes .h{{font-weight:bold;margin-bottom:1mm;}}
.nright{{text-align:right;color:#2a2a2a;}}
.notes div div{{margin-bottom:.7mm;}}
.signs{{display:table;width:100%;margin-top:14mm;}}
.sign{{display:table-cell;text-align:center;}}
.sign .t{{font-weight:bold;color:{house};}}
.sign .n{{font-size:6.4pt;font-style:italic;color:#555;}}
.sign .who{{margin-top:14mm;}}
.words{{margin-top:4mm;font-weight:bold;font-size:7pt;}}
.words .wl{{margin-right:1.5mm;color:{house};}}
.foot{{margin-top:10mm;text-align:center;font-size:6.6pt;font-style:italic;color:#444;}}
"""
    if narrow:
        return base.document(body, css, paper="A5", padding="12mm 11mm 10mm",
                             font=base.SANS, size="7.4pt", colour="#1c1c1c",
                             line_height="1.45")
    return base.document(body, css, paper="A4", padding="16mm 15mm",
                         font=base.SANS, size="8.4pt", colour="#1c1c1c",
                         line_height="1.45")


__all__ = ["LIVERIES", "build"]
