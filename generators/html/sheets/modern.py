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
    of leaving a `doctitle` to print it again. `header.logo: true` adds a
    generic round mark beside the name -- an initial on a house-coloured
    disc, not any real business's mark, since nothing in this rule-base draws
    from actual logo artwork. See `invoice_header_table.yaml`.
    """
    header = {**(spec.get("header") or {}), **(spec.get("letterhead") or {})}
    store = parse.get("store") or {}
    brand = _masthead(parse, spec)
    badge = ""
    if header.get("logo"):
        # Plain text, not `span()`: the letter is a decoration derived from
        # the name, not a field of its own -- the name itself is already a
        # box, in `brand`. Same reasoning as the `.wm` watermark and
        # `insurance.py`'s `"MH"`/`base.stamp()` marks: a monogram/logo
        # badge is decorative brand art, not content a reader extracts, even
        # though (unlike those two) this one is typeset text rather than a
        # background layer.
        initial = ((store.get("name") or "").strip()[:1] or "•").upper()
        badge = f'<div class="logo">{base.esc(initial)}</div>'
    pairs = base.party_pairs(receipt, parse, "strip")
    rows = "".join(
        f'<div>{span("invoice.field.label", label, "k")} {span("invoice.field", value, "v")}</div>'
        for label, value in pairs)
    meta = f'<div class="cornermeta">{rows}</div>' if rows else ""
    return (f'<div class="mast-corner"><div class="mc-l"><div class="mc-l-inner">{badge}{brand}</div></div>'
            f'<div class="mc-r">{meta}</div></div>')


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

    if settings.get("columns") == "stacked":
        # One full-width column, no decorative left gutter. The bakery
        # reference this family is named for always has a left column --
        # its own title, if nothing else -- but a standard VAT-invoice
        # buyer block does not, and a `.pleft` cell with nothing in it
        # still claims `split` of the row's width. `parties.seller: true`
        # prints the seller's own fields first, in the same box -- see
        # `_seller_rows` -- because the reference sheet's border runs
        # around both blocks together, not just the buyer's. See
        # `invoice_header_table.yaml`.
        seller = _seller_rows(parse) if settings.get("seller") else ""
        body = seller + rows_of(pairs)
        if not body:
            return ""
        return f'<div class="parties stacked{boxed}">{body}</div>'

    if not pairs:
        return ""

    # The left column stays empty unless the layout gave the block a title. On
    # the reference sheet that space holds a line of the shop's own design, and
    # the nearest real field -- the branch line -- is already in the masthead:
    # printing it twice would put one string in two boxes under two roles.
    title = getattr(getattr(receipt, "invoice", None), "left_title", "")
    return (f'<div class="parties{boxed}"><div class="pleft" style="width:{split * 100:.0f}%">'
            f'{span("parties.title", title)}</div>'
            f'<div class="pright">{rows_of(pairs)}</div></div>')


def _seller_rows(parse: dict) -> str:
    """The seller's own registration block, labelled like the buyer's below it.

    Leads with the trading name again under its own "Đơn vị bán hàng:" label
    -- the reference sheet does, even though the same string is already the
    masthead's big heading above; the two are different roles (`store.name`
    on two boxes is not a problem `ground_truth()` cares about, only whether
    each string is on *some* box). The rest are the same keys and fallback
    labels as `statutory.py`'s letterhead lines. `parties.seller: true` turns
    this on; a layout using it is expected to turn the masthead's own contact
    lines off (`header.address/phone/tax_code/account/website: false`) so
    each store field draws exactly once. See `invoice_header_table.yaml` and
    `_customer`.
    """
    store = parse.get("store") or {}
    fields = (
        ("name", "store.name", "Đơn vị bán hàng:"),
        ("address", "store.address", "Địa chỉ:"),
        ("address2", "store.address2", ""),
        ("tax_code", "store.tax_code", "Mã số thuế:"),
        ("phone", "store.phone", "Điện thoại:"),
        ("account", "store.account", "Số tài khoản:"),
        ("website", "store.website", ""),
    )
    return "".join(
        f'<div class="crow">{span(f"{kind}.label", label, "k")} '
        f'{span(kind, store[key], "v")}</div>'
        for key, kind, label in fields if store.get(key))


def _notes(receipt, spec: dict) -> str:
    """Where to send the money, and how to reach the shop.

    The lines are `invoice.notes` -- the same list the character grid prints --
    and `base.notes_blocks` splits them exactly as `_emit_notes` in
    `rulebase/layout.py` does, at most two blocks (`limit=2`: this masthead has
    room for two columns, not more). Roles are per column, not one for both:
    cells are read in row order, so a single role would interleave the two and
    an address wrapped over two lines could never be put back together.
    """
    invoice = getattr(receipt, "invoice", None)
    notes = list(getattr(invoice, "notes", []) or [])
    if not notes:
        return ""
    settings = spec.get("notes") or {}
    boxed = " boxed" if settings.get("boxed") else ""
    blocks = base.notes_blocks(notes, limit=2)
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


def _grid_items_table(spec: dict, receipt, parse: dict, rows) -> str:
    """The item table for INV-01, on the shared `table` component.

    The reference sheet's table is one ruled grid running straight into its
    totals -- three more rows of the same table, not a second block
    underneath it with its own edges to keep lined up by hand. `table.
    component: true` in the layout file asks for this instead of
    `base.items_table`'s own ruled-above-and-below-the-header look (and the
    lighter `table.grid` CSS-only version of a full grid); every other
    modern layout is untouched -- see `generators/html/components/table.py`'s own
    docstring for why nothing already shipping was rewired onto it.

    Column titles carry an optional English subtitle (`columns: [{title_en:
    ...}]` in the layout file) as a second, sibling `span()` -- `span()` is
    text-only by contract (see its docstring: a nested element would become
    the measured box instead of the run), so the two languages are two
    boxes joined by a literal `<br>`, never one span holding markup.
    """
    from components.table import Border, Cell, Column, Row, TableSpec, render_table
    from rulebase.layout import item_values

    columns = base.columns_of(spec, base.ncols_of(spec))
    if not columns:
        return ""
    plan = base.item_rows(spec)
    template = plan[0] if plan else [{"col": c["key"], "from": c["key"]} for c in columns]
    by_col = {entry["col"]: entry["from"] for entry in template}
    ncols = len(columns)

    def header_cell(column: dict) -> Cell:
        title = span("colhdr", column.get("title", ""))
        title_en = column.get("title_en")
        if title_en:
            title += f'<br>{span("colhdr", f"({title_en})", "hen")}'
        return Cell(title, html=True, align=column.get("title_align", "center"))

    table_rows = [Row([header_cell(c) for c in columns], header=True, bg="#f4f4f4")]

    for item in receipt.items:
        values = item_values(item, receipt)
        cells = []
        for column in columns:
            source = by_col.get(column["key"], column["key"])
            text = values.get(source, "")
            cells.append(Cell(span(f"menu.{source}", text), html=True,
                               align=column.get("align", "left")))
        table_rows.append(Row(cells))

    # Merged into the same grid, not a block below it: three rows whose
    # label spans every column but the last, exactly the shape the
    # reference sheet's own table ends on.
    total_pairs = list((parse.get("total") or {}).items())
    for index, (label, value) in enumerate(total_pairs):
        grand = index == len(total_pairs) - 1
        kind = "total.grand" if grand else "total.line"
        table_rows.append(Row([
            Cell(span(f"{kind}.label", label), html=True, colspan=ncols - 1,
                 align="right", bold=grand),
            Cell(span(kind, value), html=True, align="right", bold=grand),
        ]))

    table_spec = TableSpec(
        rows=table_rows,
        columns=[Column(width=c["pct"], align=c.get("align", "left")) for c in columns],
        border=Border.grid(0.22, color="#b7b7b7"),
    )
    return render_table(table_spec, rows=rows)


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    rng = base.rng_for(recipe)
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
    table_settings = spec.get("table") or {}
    compact = bool(table_settings.get("compact"))
    grid = bool(table_settings.get("grid"))

    if table_settings.get("component"):
        # The `table` component (`generators/html/components/table.py`), totals merged
        # in as its last three rows -- see `_grid_items_table`.
        table = _grid_items_table(spec, receipt, parse, rows)
    else:
        table = base.items_table(spec, receipt, parse, rows, cls="items grid" if grid else "items")

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
        # Not a field `ground_truth()` claims went unprinted -- see
        # `invoice_multipage.yaml` for why this stands in for a second page
        # the renderer has no way to actually turn to -- but it is real ink
        # ON THIS page regardless, the same continuation notice a real
        # multi-page form prints, so it still gets a box. `"page_no"` is
        # already `Page-Footer`, which is where this sits.
        body += f'<div class="pagemark">{span("page_no", marker)}</div>'

    if page.get("watermark"):
        # A faint, once-only diagonal repeat of the seller's own name --
        # plain text, not `span()`, for the same reason as `marker` above:
        # it is a second, decorative appearance of a string that already has
        # its own box in the seller block, not a field of its own. The tax
        # code rather than the name -- short and close to fixed-width, so it
        # sits inside the page at any house colour's font size instead of
        # running off the edge the way a forty-character trading name would.
        # Kept very light on purpose -- this is training data for reading
        # text, and a watermark strong enough to compete with the content it
        # sits behind would work against the one thing the page is for.
        wm_store = parse.get("store") or {}
        wm_text = wm_store.get("tax_code") or wm_store.get("name", "")
        if wm_text:
            body = f'<div class="wm">{base.esc(wm_text)}</div>' + body

    compact_css = (".items tbody td{padding:1.1mm 1.4mm;}"
                   ".items thead th{padding:1.3mm 1.4mm;}") if compact else ""
    # `table.grid: true` -- a full ruled grid (outer frame and every column
    # divider), the shape a printed VAT-invoice form's table has, in place of
    # the family's usual ruled-above-and-below-the-header look. Scoped to
    # `.grid` so the two pre-existing modern layouts, and the nine other new
    # ones, keep their own table untouched. See `invoice_header_table.yaml`.
    grid_css = (f"""
table.items.grid{{border-collapse:collapse;}}
table.items.grid th,table.items.grid td{{border:.2mm solid #b7b7b7;}}
table.items.grid thead th{{border-top:.4mm solid {house};border-bottom:.4mm solid {house};}}
table.items.grid tbody tr:last-child td{{border-bottom:.4mm solid {house};}}
""") if grid else ""
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
.crow .k{{color:#3a3a3a;font-weight:bold;}}
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
{grid_css}
.mast-split{{display:table;width:100%;margin-bottom:6mm;}}
.mast-l{{display:table-cell;vertical-align:middle;text-align:left;}}
.mast-l .brand{{text-align:left;padding-bottom:0;}}
.mast-r{{display:table-cell;vertical-align:middle;text-align:right;width:44%;}}
.mast-r .doc{{margin:0;text-align:right;}}
.mast-corner{{display:table;width:100%;margin-bottom:2mm;}}
.mc-l{{display:table-cell;vertical-align:top;text-align:left;}}
.mc-l-inner{{display:flex;align-items:center;gap:3mm;}}
.mc-l .brand{{text-align:left;padding-bottom:0;}}
.logo{{flex:none;width:10mm;height:10mm;border-radius:50%;background:{house};color:#fff;
   font-weight:bold;font-size:11pt;text-align:center;line-height:10mm;}}
.mc-r{{display:table-cell;vertical-align:top;text-align:right;width:34%;}}
.cornermeta{{font-size:6.6pt;color:#4a4a4a;}}
.cornermeta div{{margin-bottom:.6mm;}}
.cornermeta .k{{margin-right:1mm;}}
.wm{{position:fixed;top:46%;left:50%;transform:translate(-50%,-50%) rotate(-30deg);
   font-size:46pt;font-weight:bold;color:{house};opacity:.05;white-space:nowrap;}}
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
    # `font: serif` -- a printed VAT-invoice form's own face, not the sheet
    # this family is named for and otherwise always sets sans. `base.SERIF`
    # already ships (statutory.py's own default), so this is a font this
    # renderer already embeds and every other family already exercises, not
    # a new one to source and test.
    font = base.SERIF if spec.get("font") == "serif" else base.SANS
    if narrow:
        return base.document(body, css, paper="A5", padding="12mm 11mm 10mm",
                             font=font, size="7.4pt", colour="#1c1c1c",
                             line_height="1.45")
    return base.document(body, css, paper="A4", padding="16mm 15mm",
                         font=font, size="8.4pt", colour="#1c1c1c",
                         line_height="1.45")


__all__ = ["LIVERIES", "build"]
