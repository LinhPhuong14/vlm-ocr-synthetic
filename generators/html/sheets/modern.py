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


def _masthead_split(parse: dict, spec: dict) -> str:
    """Trading name on the left, the document's title on the right, one row.

    `header.align: split` in a layout file asks for this instead of the
    centred default above. The metadata rows (serial, date, due date...)
    print separately via `strip` in this mode -- printing them a second time
    here would put one string in two boxes, so the title goes up alone. See
    `invoice_logo_split.yaml`.
    """
    brand = _masthead(parse, spec)
    title = span("title", parse.get("title", ""), "doc")
    return (f'<div class="mast-split"><div class="mast-l">{brand}</div>'
            f'<div class="mast-r">{title}</div></div>')


def _masthead_corner(receipt, parse: dict, spec: dict) -> str:
    """Trading name top-left, a small numbered-stationery box top-right.

    `header.align: corner` asks for this instead of the centred default --
    the shape a standard VAT-invoice form's masthead actually has (logo one
    corner, "Mẫu số / Ký hiệu / Số" box the other), with the title still
    printed centred and full width below it via `_doctitle`, called
    separately. The box's rows are `strip`'s own pairs -- `party_fields.strip`
    on the document -- so a layout using this mode names no separate `strip`
    in `sections:`, the same way `split` folds the title into itself instead
    of leaving a `doctitle` to print it again. See `invoice_header_table.yaml`.
    """
    brand = _masthead(parse, spec)
    pairs = base.party_pairs(receipt, parse, "strip")
    rows = "".join(
        f'<div>{span("invoice.field.label", label, "k")} {span("invoice.field", value, "v")}</div>'
        for label, value in pairs)
    meta = f'<div class="cornermeta">{rows}</div>' if rows else ""
    return f'<div class="mast-corner"><div class="mc-l">{brand}</div><div class="mc-r">{meta}</div></div>'


def _doctitle(parse: dict, meta: bool = True, keys: tuple = (
        "form_no", "serial", "number", "subtitle", "period")) -> str:
    """The document's name, and the serial block a numbered invoice carries.

    A self-designed invoice still has a number, a date and often a form code.
    The bakery's sheet puts them in a strip under the title; an English tax
    invoice has no `strip` in its `sections:` at all, and without this block its
    serial, its number and its date would be in the label and on no box.

    `keys` narrows which of those a caller still wants printed here -- the
    `corner` header mode draws form/serial/number itself, in its own box, and
    would double-print them given the full default tuple. See `_section_html`.
    """
    invoice = parse.get("invoice") or {} if meta else {}
    rows = "".join(
        f'<div>{span(f"invoice.{key}", invoice[key])}</div>'
        for key in keys
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
    settings = spec.get("parties") or {}
    split = float(settings.get("split", 0.38))
    boxed = " boxed" if settings.get("boxed") else ""

    def rows_of(pairs: list[tuple[str, str]]) -> str:
        return "".join(
            f'<div class="crow">{span("invoice.field.label", label, "k")} '
            f'{span("invoice.field", value, "v")}</div>'
            for label, value in pairs)

    left_pairs = base.party_pairs(receipt, parse, "left")
    right_pairs = base.party_pairs(receipt, parse, "right")

    if settings.get("columns") == "billing_shipping":
        # Two REAL columns -- who is billed, and who takes delivery -- not
        # the decorative-title default below. `left_label`/`right_label` are
        # a layout's own static captions ("BÊN MUA HÀNG" / "GIAO ĐẾN"), not
        # a value from the receipt, which is why they carry a `span()` of
        # their own rather than reusing `parties.title`. See
        # `invoice_two_column.yaml`.
        if not left_pairs and not right_pairs:
            return ""
        left_cap = span("parties.left_label", settings.get("left_label", ""), "capl")
        right_cap = span("parties.right_label", settings.get("right_label", ""), "capl")
        return (f'<div class="parties two{boxed}">'
                f'<div class="pleft2" style="width:{split * 100:.0f}%">{left_cap}{rows_of(left_pairs)}</div>'
                f'<div class="pright2">{right_cap}{rows_of(right_pairs)}</div></div>')

    pairs = left_pairs + right_pairs
    if not pairs:
        return ""

    if settings.get("columns") == "stacked":
        # One full-width column, no decorative left gutter. The bakery
        # reference this family is named for always has a left column --
        # its own title, if nothing else -- but a standard VAT-invoice
        # buyer block does not, and a `.pleft` cell with nothing in it
        # still claims `split` of the row's width. See
        # `invoice_header_table.yaml`.
        return f'<div class="parties stacked{boxed}">{rows_of(pairs)}</div>'

    # The left column stays empty unless the layout gave the block a title. On
    # the reference sheet that space holds a line of the shop's own design, and
    # the nearest real field -- the branch line -- is already in the masthead:
    # printing it twice would put one string in two boxes under two roles.
    title = getattr(getattr(receipt, "invoice", None), "left_title", "")
    return (f'<div class="parties{boxed}"><div class="pleft" style="width:{split * 100:.0f}%">'
            f'{span("parties.title", title)}</div>'
            f'<div class="pright">{rows_of(pairs)}</div></div>')


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
    boxed = " boxed" if settings.get("boxed") else ""
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
        return f'<div class="notes{boxed}">{column(blocks[0], "note.left", "nfull")}</div>'
    split = float(settings.get("split", 0.52))
    width = ' style="width:%.0f%%"' % (split * 100)
    return (f'<div class="notes{boxed}">'
            f'{column(blocks[0], "note.left", "nleft", width)}'
            f'{column(blocks[1], "note.right", "nright")}</div>')


def _section_html(name: str, receipt, spec: dict, parse: dict, sections: list,
                  table: str, header_mode: str) -> str:
    """One named block of `sections:`, the same dispatch for every page shape.

    Pulled out of `build()` so the plain top-to-bottom flow and the sidebar
    split (`page.style: sidebar`) can both ask for "the html of block X" and
    route it wherever their own layout puts it, rather than the dispatch
    being duplicated once per shape. `header_mode` is `header.align` off the
    spec, defaulted to `"center"` -- `"split"` and `"corner"` are the two
    alternatives, see `_masthead_split` and `_masthead_corner`.
    """
    if name in ("header", "letterhead"):
        if header_mode == "split":
            return _masthead_split(parse, spec)
        if header_mode == "corner":
            return _masthead_corner(receipt, parse, spec)
        return _masthead(parse, spec)
    if name == "doctitle":
        if header_mode == "split":
            # Already folded into the split header's right-hand side.
            return ""
        # A layout with a `strip` already prints the number and the date in
        # it; repeating them here would put one string in two boxes. Corner
        # mode is the same idea for form/serial/number specifically -- its
        # own box already drew them.
        keys = (("subtitle", "period") if header_mode == "corner" else
                ("form_no", "serial", "number", "subtitle", "period"))
        return _doctitle(parse, meta="strip" not in sections, keys=keys)
    if name == "strip":
        return base.key_strip(base.party_pairs(receipt, parse, "strip"))
    if name == "parties":
        return _customer(receipt, parse, spec)
    if name == "table":
        return table
    if name == "totals":
        settings = spec.get("totals") or {}
        return base.totals_block(parse, indent=float(settings.get("indent", 0.40)))
    if name == "notes":
        return _notes(receipt, spec)
    if name == "words":
        return base.words_block(receipt, parse)
    if name == "signatures":
        return base.signature_block(receipt, parse)
    if name == "footer":
        return base.footer_block(parse)
    return ""


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    rng = random.Random(recipe.seed ^ 0x5A4D)
    minimal = bool(spec.get("minimal"))
    # A minimalist sheet drops the house colour for a fixed neutral grey --
    # the point of `invoice_minimalist.yaml` is that nothing about the page
    # was designed, so nothing about it should look designed either.
    house = "#3a3a3a" if minimal else LIVERIES[rng.randrange(len(LIVERIES))]
    sections = spec.get("sections") or []
    narrow = "footer_columns" in recipe.layout.tags
    rows = Rows()
    header_spec = {**(spec.get("header") or {}), **(spec.get("letterhead") or {})}
    header_mode = header_spec.get("align") or "center"
    page = spec.get("page") or {}
    compact = bool((spec.get("table") or {}).get("compact"))

    table = base.items_table(spec, receipt, parse, rows)

    if page.get("style") == "sidebar":
        # A full-height coloured column instead of one flow down the page --
        # `sidebar_sections` says which named blocks go in it, the rest land
        # in the main column in their usual order. See `invoice_sidebar.yaml`.
        side_names = set(page.get("sidebar_sections") or ["header", "strip"])
        side_blocks, main_blocks = [], []
        for name in sections:
            piece = _section_html(name, receipt, spec, parse, sections, table, header_mode)
            if not piece:
                continue
            (side_blocks if name in side_names else main_blocks).append(piece)
        body = (f'<div class="sidebar-wrap"><div class="side">{"".join(side_blocks)}</div>'
                f'<div class="main">{"".join(main_blocks)}</div></div>')
    else:
        blocks = [_section_html(name, receipt, spec, parse, sections, table, header_mode)
                  for name in sections]
        if "doctitle" not in sections:
            # A layout that names no `doctitle` still has a title, and the
            # reference sheet prints it right under the shop's name.
            blocks.insert(1, _section_html("doctitle", receipt, spec, parse, sections, table, header_mode))
        body = "".join(block for block in blocks if block)

    marker = page.get("marker")
    if marker:
        # Furniture, not label: no `span()`, so it carries no `data-kind` and
        # is not a field `ground_truth()` could ever claim went unprinted --
        # see `invoice_multipage.yaml` for why this stands in for a second
        # page the renderer has no way to actually turn to.
        body += f'<div class="pagemark">{base.esc(marker)}</div>'

    compact_css = (".items tbody td{padding:1.1mm 1.4mm;}"
                   ".items thead th{padding:1.3mm 1.4mm;}") if compact else ""
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
.parties.stacked{{display:block;}}
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
{compact_css}
.mast-split{{display:table;width:100%;margin-bottom:6mm;}}
.mast-l{{display:table-cell;vertical-align:middle;text-align:left;}}
.mast-l .brand{{text-align:left;padding-bottom:0;}}
.mast-r{{display:table-cell;vertical-align:middle;text-align:right;width:44%;}}
.mast-r .doc{{margin:0;text-align:right;}}
.mast-corner{{display:table;width:100%;margin-bottom:2mm;}}
.mc-l{{display:table-cell;vertical-align:top;text-align:left;}}
.mc-l .brand{{text-align:left;padding-bottom:0;}}
.mc-r{{display:table-cell;vertical-align:top;text-align:right;width:34%;}}
.cornermeta{{font-size:6.6pt;color:#4a4a4a;}}
.cornermeta div{{margin-bottom:.6mm;}}
.cornermeta .k{{margin-right:1mm;}}
.capl{{display:block;font-weight:bold;font-size:6.6pt;letter-spacing:1pt;color:{house};margin-bottom:1.6mm;}}
.parties.two{{display:table;width:100%;margin-bottom:7mm;}}
.pleft2,.pright2{{display:table-cell;vertical-align:top;padding-right:6mm;}}
.pright2{{padding-right:0;padding-left:6mm;}}
.parties.boxed,.notes.boxed{{border:.3mm solid {house};border-radius:1mm;padding:4mm 5mm;}}
.notes.boxed{{margin-top:8mm;}}
.sidebar-wrap{{display:flex;margin:-16mm -15mm;min-height:calc(100% + 32mm);}}
.side{{width:36%;flex:none;background:{house};color:#f2f2f2;padding:16mm 9mm;box-sizing:border-box;}}
.side .brand .h1,.side .brand .tag,.side .pleft{{color:#fff;}}
.side .brand .cl,.side .strip,.side .docmeta,.side .crow .k{{color:#e6e6e6;}}
.side .strip .sep{{color:#cfcfcf;}}
.main{{flex:1;min-width:0;padding:16mm 15mm;box-sizing:border-box;}}
.pagemark{{margin-top:10mm;text-align:right;font-size:6.6pt;color:#888;font-style:italic;
   border-top:.2mm dashed #ccc;padding-top:2mm;}}
"""
    if narrow:
        return base.document(body, css, paper="A5", padding="12mm 11mm 10mm",
                             font=base.SANS, size="7.4pt", colour="#1c1c1c",
                             line_height="1.45")
    return base.document(body, css, paper="A4", padding="16mm 15mm",
                         font=base.SANS, size="8.4pt", colour="#1c1c1c",
                         line_height="1.45")


__all__ = ["LIVERIES", "build"]
