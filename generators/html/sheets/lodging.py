"""The folio family: a booking block, one row per night, two signatures.

Two references, and they are the same document at two sizes.
`samples/invoice-templates/invoice_hotel_stay.html` is the resort's: no frame at
all, hairline rules under each row, the key strip running across the top and the
totals folded into the night table as rows spanning six columns.
`samples/invoice-templates/invoice_hotel_compact.html` is the small hotel's A5
sheet, and it is the one with an identity -- a teal band across the head, a
guilloche washed in behind the signatures, a corner bracket, a wave under the
band and a round seal struck over the receptionist's name.

The ornaments are the files in `textures/ornament/`, the same ones the
`ornament` attribute draws from, so a change to `make ornaments` reaches this
sheet too rather than a private copy of it going stale.

What tells the two apart is `narrow_sheet` on the layout, not the id: a third
compact folio added later gets the compact dress by saying so in the rules.
"""

from __future__ import annotations

from . import base
from .base import Rows, esc, span

# Hotel liveries: band, deep tone, the metal used on exactly one line, and the
# ornament stem that carries the same colour.
LIVERIES = [
    ("#0f4c5c", "#1c7a8c", "#b0872b", "teal"),
    ("#1d5e3a", "#2f8054", "#b0872b", "green"),
    ("#4b2a6b", "#6f5aa8", "#b0872b", "violet"),
]


def _booking(receipt, parse: dict) -> str:
    """The booking block: two label/value pairs a row, hairline between rows.

    A plain `<table>` rather than a grid of positioned spans, so the four
    columns line up because the engine made them line up.
    """
    left = base.party_pairs(receipt, parse, "left")
    right = base.party_pairs(receipt, parse, "right")
    if not left and not right:
        return ""
    rows = []
    for index in range(max(len(left), len(right))):
        cells = []
        for source in (left, right):
            if index < len(source):
                label, value = source[index]
                cells.append(f'<td class="k">{span("invoice.field.label", label)}</td>'
                             f'<td class="v">{span("invoice.field", value)}</td>')
            else:
                cells.append('<td class="k"></td><td class="v"></td>')
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table class="booking">{"".join(rows)}</table>'


def _band(receipt, parse: dict, compact: bool, livery) -> str:
    band, deep, metal, stem = livery
    store = parse.get("store") or {}
    strip = base.party_pairs(receipt, parse, "strip")
    if compact:
        # The head is a coloured band with the hotel on the left and the
        # document on the right -- the small sheet has no room for a centred
        # masthead and a strip underneath it. Only the first two keys fit in the
        # band; the rest run along under the wave, which is where the reference
        # sheet keeps them too.
        keys = "".join(
            f'<div>{span("invoice.field.label", label, "k")} '
            f'{span("invoice.field", value, "v")}</div>'
            for label, value in strip[:2])
        return f"""<div class="band">
<div class="bl"><div class="logo"><span class="glyph"><i></i></span>
<span class="ltext">{span("store.name", store.get("name", ""), "n")}
{span("store.branch", store.get("branch", ""), "s")}</span></div></div>
<div class="br">{span("title", parse.get("title", ""), "h1")}{keys}</div>
</div>"""
    meta = "".join(
        f'<div class="meta">{span(f"store.{key}", store.get(key, ""))}</div>'
        for key in ("branch", "address", "address2", "phone", "website")
        if store.get(key))
    # Two table cells rather than an absolutely positioned logo over a centred
    # block. Same picture, and it keeps the head unpositioned -- WeasyPrint
    # paints positioned boxes *after* the in-flow ones, so a positioned head is
    # a head whose text lands at the end of the PDF's character stream, out of
    # step with the markup the boxes are matched against.
    return f"""<div class="head">
<div class="hlogo"><div class="l1">{esc(base.initials(store.get("name", "")))}</div></div>
<div class="hbody">{span("store.name", store.get("name", ""), "name")}{meta}</div>
</div>
{span("title", parse.get("title", ""), "doc")}
{base.key_strip(strip)}"""


def _contact(receipt, parse: dict) -> str:
    """The small sheet's foot: how to reach the hotel, and the rest of the keys.

    The band above has room for two of the booking keys and no room for the
    address, so everything that did not fit lands here. Nothing is dropped: a
    field in the label with no box on the page is what
    `pipeline/invariants.py` calls an error, and it is right to.
    """
    store = parse.get("store") or {}
    left = "".join(
        f'<div>{span(f"store.{key}", store[key])}</div>'
        for key in ("address", "address2", "phone", "website") if store.get(key))
    right = "".join(
        f'<div>{span("invoice.field.label", label, "k")} '
        f'{span("invoice.field", value)}</div>'
        for label, value in base.party_pairs(receipt, parse, "strip")[2:])
    if not left and not right:
        return ""
    return (f'<div class="contact"><div class="cl">{left}</div>'
            f'<div class="cr">{right}</div></div>')


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    rng = base.rng_for(recipe)
    band, deep, metal, stem = LIVERIES[rng.randrange(len(LIVERIES))]
    compact = "narrow_sheet" in recipe.layout.tags
    sections = spec.get("sections") or []
    rows = Rows()

    entries = list((parse.get("total") or {}).items())
    settings = spec.get("totals") or {}
    indent = float(settings.get("indent", 0.42))

    # The resort sheet keeps its totals in the night table, spanning every
    # column but the last; the small sheet lifts them out into a block against
    # the right margin. Both are in the references, and which one a layout gets
    # follows the same flag that picks the dress.
    in_table = not compact
    totals = [{"label": label, "value": value, "grand": index == 0}
              for index, (label, value) in enumerate(entries)] if in_table else None
    table = base.items_table(spec, receipt, parse, rows, totals=totals)
    money = "" if in_table else base.totals_block(parse, indent=indent, grand=0)

    seal_css = ""
    if compact:
        url = base.ornament_url("seal_round_hotel")
        if url:
            # A background, not an `<img>`. The seal has to sit *behind* the
            # signature block, and the only way to do that with an element is to
            # position it -- which would push every name in the block to the end
            # of the PDF's character stream. A background paints behind the
            # content it belongs to and needs no positioning at all.
            seal_css = (f".signs{{background:url('{url}') no-repeat "
                        f"left 0 top 1mm;background-size:22mm 22mm;}}")

    blocks = []
    for name in sections:
        if name in ("header", "strip"):
            continue
        if name == "parties":
            blocks.append(_booking(receipt, parse))
        elif name == "table":
            blocks.append(table)
        elif name == "totals":
            blocks.append(money)
        elif name == "signatures":
            blocks.append(base.signature_block(receipt, parse))
        elif name == "footer":
            blocks.append(_contact(receipt, parse) if compact else "")
            blocks.append(base.footer_block(parse))

    ornaments = ""
    if compact:
        for cls, name in (("corner", f"corner_bracket_{stem}"),
                          ("rosette", f"guilloche_{stem}"),
                          ("gridpat", f"rect_grid_{stem}")):
            url = base.ornament_url(name)
            if url:
                ornaments += f'<img class="{cls}" src="{url}" alt="">'
        wave = base.ornament_url(f"wave_band_{stem}")
        wave = f'<img class="wave" src="{wave}" alt="">' if wave else ""
    else:
        wave = ""

    head = _band(receipt, parse, compact, (band, deep, metal, stem))
    inner = "".join(block for block in blocks if block)
    if compact:
        body = (f'{ornaments}<div class="page">{head}{wave}'
                f'<div class="inner">{inner}</div></div>')
    else:
        body = f"{head}{inner}"

    common = f"""
.strip{{font-size:6.9pt;margin-bottom:4mm;}}
.strip .k{{font-weight:bold;}}
.strip .sep{{color:#999;padding:0 1.2mm;}}
table.booking td{{padding:1.8mm 1.6mm;border-bottom:.2mm solid #e7eef0;}}
table.booking tr:first-child td{{border-top:.3mm solid #d3dde1;}}
table.booking td.k{{width:22%;color:#63707a;}}
table.booking td.v{{width:28%;font-weight:bold;}}
table.items{{margin-top:5mm;}}
table.items td{{padding:2mm 1.6mm;border-bottom:.2mm solid #e7eef0;vertical-align:top;}}
table.items th{{text-align:left;font-weight:bold;padding:2mm 1.6mm;}}
table.items th.r{{text-align:right;}} table.items th.c{{text-align:center;}}
.sub{{font-style:italic;color:#63707a;}}
.signs{{display:table;width:100%;margin-top:12mm;}}
.sign{{display:table-cell;width:50%;text-align:center;}}
.sign .t{{font-weight:bold;color:{band};}}
.sign .n{{font-size:6pt;font-style:italic;color:#63707a;}}
.sign .who{{margin-top:13mm;}}
"""
    if compact:
        css = common + f"""
#sheet{{padding:0;}}
.page{{position:relative;padding-bottom:8mm;}}
.corner{{position:absolute;left:0;bottom:0;width:20mm;height:20mm;transform:scaleY(-1);opacity:.38;}}
.rosette{{position:absolute;right:26mm;bottom:44mm;width:42mm;height:42mm;opacity:.34;}}
.gridpat{{position:absolute;left:0;bottom:0;width:148mm;height:22mm;opacity:.16;}}
.band{{background:{band};color:#fff;padding:8mm 10mm 6.5mm;display:table;width:100%;}}
.band > div{{display:table-cell;vertical-align:middle;}}
.bl{{width:56%;}} .br{{width:44%;text-align:right;}}
.logo{{display:table;}}
.logo > span{{display:table-cell;vertical-align:middle;}}
.logo .glyph{{padding-right:3mm;}}
.logo .glyph i{{display:block;width:8.5mm;height:8.5mm;border:.45mm solid #fff;
                border-bottom-width:1.3mm;position:relative;}}
.logo .glyph i::before,.logo .glyph i::after{{content:"";position:absolute;top:1.7mm;
   width:1.2mm;height:3.2mm;background:#fff;}}
.logo .glyph i::before{{left:1.7mm;}} .logo .glyph i::after{{right:1.7mm;}}
.logo .n{{display:block;font-weight:bold;font-size:9.6pt;letter-spacing:.5pt;}}
.logo .s{{display:block;font-size:5.4pt;letter-spacing:2pt;color:#a9ccd4;}}
.band .h1{{display:block;font-size:15pt;letter-spacing:1pt;font-weight:bold;margin-bottom:1.6mm;}}
.band .k{{color:#a9ccd4;}} .band .v{{font-weight:bold;}}
.wave{{display:block;width:100%;height:4.5mm;}}
.inner{{padding:6mm 10mm 0;position:relative;}}
table.items th{{background:{band};color:#fff;font-size:6.2pt;}}
table.items tbody tr:nth-child(odd) td{{background:#f2f7f8;}}
.totals{{margin-top:5mm;}}
.trow{{display:table;width:100%;padding:1.2mm 0;border-left:.9mm solid {metal};padding-left:2.2mm;}}
.trow .lab{{display:table-cell;color:#63707a;}}
.trow .amt{{display:table-cell;text-align:right;font-weight:bold;}}
.trow.grand{{background:{band};color:#fff;padding:2.4mm 2.6mm;border-left:0;margin-bottom:1.5mm;}}
.trow.grand .lab{{color:#a9ccd4;font-weight:bold;letter-spacing:.4pt;}}
.trow.grand .amt{{font-size:9pt;color:#fff;}}
/* The hotel's own seal, struck on the RECEPTIONIST's half -- whoever signs
   stamps their own block. Painted as a background so it sits behind the names
   without the block having to be positioned, and clear of them rather than
   over them: a stamp across printed words is realistic and unreadable, and this
   page has to be legible enough to be a label. */
{seal_css}
.contact{{display:table;width:100%;margin-top:9mm;padding-top:2.6mm;
          border-top:.3mm solid #d3dde1;font-size:5.8pt;color:#63707a;}}
.contact .cl,.contact .cr{{display:table-cell;width:50%;vertical-align:top;}}
.contact .cr{{text-align:right;}}
.contact .k{{color:{band};font-weight:bold;}}
.foot{{margin-top:4mm;font-size:5.8pt;color:#63707a;text-align:center;}}
"""
        return base.document(body, css, paper="A5", padding="0",
                             font=base.SANS, size="6.4pt", colour="#1a1d21",
                             line_height="1.45")

    css = common + f"""
#sheet{{padding:14mm 15mm;}}
.head{{display:table;width:100%;padding-bottom:7mm;}}
.hlogo,.hbody{{display:table-cell;vertical-align:top;}}
.hlogo{{width:32mm;text-align:left;}}
.hbody{{text-align:center;padding-right:32mm;}}
.hlogo .l1{{font-family:{base.SERIF};font-weight:bold;font-size:15pt;line-height:1;}}
.head .name{{display:block;font-weight:bold;font-size:10.5pt;}}
.head .meta{{font-size:7pt;margin-top:1.2mm;}}
.doc{{display:block;text-align:center;font-size:13pt;letter-spacing:.8pt;
      margin:2mm 0 5mm;font-weight:bold;}}
table.items th{{border-top:.2mm solid #d9d9d9;border-bottom:.2mm solid #d9d9d9;font-size:7.2pt;}}
table.items td{{border-bottom:.2mm solid #d9d9d9;}}
tr.total td,tr.grand td{{font-weight:bold;}}
td.tlabel{{text-align:right;}}
.foot{{margin-top:8mm;font-size:6.6pt;font-style:italic;color:#444;text-align:center;}}
"""
    return base.document(body, css, paper="A4", padding="14mm 15mm",
                         font=base.SANS, size="7.6pt", colour="#111",
                         line_height="1.4")


__all__ = ["LIVERIES", "build"]
