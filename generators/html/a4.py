"""An A4 invoice drawn as a real page, not as a grid of characters.

    from a4 import build
    markup = build(recipe, receipt, theme="brand")

Everything else in this repository lays a document out on a **character grid**:
`rulebase/layout.py` places each field at a row and a column range measured in
character widths, and all three renderers draw that grid. It is the right model
for a thermal till roll, which really is a monospace device, and it is why the
three backends can be compared at all.

It is the wrong model for a printed VAT invoice. A real one has a logo, a red
serial block, ruled table cells, a watermark, proportional type at four
different sizes and a signature stamp -- none of which is text on a grid, and
none of which a character cell can express. Widening the grid does not help;
the limit is the model, not its parameters.

So this module is a second render path. It takes the same `Receipt` and puts it
through CSS instead: real table borders, real font sizes, real colour. The only
thing it keeps from the grid path is the **box contract** -- every labelled
piece of text is a `<span data-kind="...">`, so `CELL_RECTS_JS` in `render.py`
extracts quads from it without knowing anything about templates, and the
`{kind, text, quad}` records that come out are the ones every existing tool
already reads.

What is printed comes from `receipt.ground_truth()` rather than from the
`Receipt` fields directly. That is deliberate: the label and the page are then
the same strings by construction, and cannot drift apart the way a truncated
address once did. `pipeline/invariants.py` still checks it, and still would
catch a field the template forgets to draw.

**Only the browser backends can render this.** The glyph backend composites
individual glyphs onto a canvas and has no way to draw a table rule or a
watermark; WeasyPrint can, and wiring it up is a separate piece of work because
it recovers boxes from a PDF text layer rather than from the DOM. Until then a
template document is a one-backend document, which is a real consequence for
`pairing` and is reported rather than papered over.
"""

from __future__ import annotations

import html
import random
from typing import Any

# Corporate colours that actually appear on Vietnamese invoices: a navy or a
# red masthead with the serial block picked out in red. Chosen by seed so a run
# varies, and only from this list so it never lands on something no printer
# would use.
BRANDS = [
    ("#1a3a6b", "#c0161d"),   # navy on white, red serial -- the common form
    ("#b3121a", "#b3121a"),   # all red, older forms
    ("#0b5c3f", "#c0161d"),   # green, utility companies
    ("#1f3864", "#1f3864"),   # dark blue throughout
    ("#7a1f2b", "#b3121a"),   # maroon
]

# How wide the sheet is in CSS pixels. A4 at 96 dpi is 794; the renderer
# screenshots at device_scale_factor 2 and downscales afterwards, so this only
# sets the raster resolution and the ratio, not the final size.
SHEET_W = 820
SHEET_H = 1160


def _e(text: Any) -> str:
    return html.escape(str(text if text is not None else ""))


def _span(kind: str, text: Any, cls: str = "") -> str:
    """One labelled run. Anything without `data-kind` is decoration, not a field."""
    text = "" if text is None else str(text)
    if not text.strip():
        return ""
    attr = f' class="{cls}"' if cls else ""
    return f'<span data-kind="{_e(kind)}"{attr}>{_e(text)}</span>'


def _initials(name: str) -> str:
    """Two letters for the logo mark, from the words a Vietnamese name starts with.

    "CÔNG TY CỔ PHẦN ĐIỆN MÁY VÀ GIA DỤNG HỒNG HÀ" -> "HH": the trailing words
    are the trading name, and the leading ones say only that it is a company.
    """
    skip = {"CONG", "TY", "CO", "PHAN", "TNHH", "MTV", "DOANH", "NGHIEP",
            "TAP", "DOAN", "CHI", "NHANH", "VA", "-"}
    import unicodedata

    words = []
    for word in name.replace("-", " ").split():
        plain = "".join(c for c in unicodedata.normalize("NFD", word)
                        if not unicodedata.combining(c)).upper()
        plain = plain.replace("Đ", "D").replace("đ", "d")
        if plain and plain not in skip:
            words.append(word)
    picked = words[-2:] if len(words) >= 2 else (words or [name])
    return "".join(w[0] for w in picked).upper()[:2] or "VN"


def _logo(mark: str, colour: str) -> str:
    """An inline SVG so the page needs no file and no network.

    A real letterhead has a real logo; what matters for a reader and for a model
    is that *something* graphical sits there and the text has to flow around it.
    """
    return (
        f'<svg class="mark" viewBox="0 0 64 64" width="52" height="52" aria-hidden="true">'
        f'<rect x="1" y="1" width="62" height="62" rx="9" fill="none" '
        f'stroke="{colour}" stroke-width="3"/>'
        f'<path d="M8 46 L32 10 L56 46 Z" fill="{colour}" opacity="0.14"/>'
        f'<text x="32" y="42" text-anchor="middle" font-size="26" font-weight="700" '
        f'fill="{colour}" font-family="Liberation Serif, serif">{_e(mark)}</text>'
        f"</svg>"
    )


def _cell(tag: str, row: int, col: int, inner: str, *, cls: str = "",
          kind: str = "", colspan: int = 1, rowspan: int = 1) -> str:
    """One table cell, carrying where it sits and how far it spans.

    Borrowed from the vendored `generators/html-table`, which labels each `<td>`
    rather than only the text inside it. The distinction is the whole point for
    a merged cell: the totals row of an invoice spans six columns, and the text
    box round "Tổng tiền thanh toán" says nothing about that. A model asked to
    reconstruct the table needs the *cell* extent and the span; a model asked to
    read the text needs the text box. Both are emitted, and `data-cell` is what
    tells the extractor which elements are cells.
    """
    attrs = [f'data-cell="{_e(kind)}"', f'data-row="{row}"', f'data-col="{col}"']
    if colspan > 1:
        attrs.append(f'colspan="{colspan}"')
    if rowspan > 1:
        attrs.append(f'rowspan="{rowspan}"')
    if cls:
        attrs.append(f'class="{cls}"')
    return f"<{tag} {' '.join(attrs)}>{inner}</{tag}>"


def structure_tokens(rows: list[list[dict]]) -> list[str]:
    """The table as PPStructure tokens: `<tr>`, `<td`, ` colspan="6"`, `>`, ...

    The same shape `html-table` writes, so a dataset built here can be read by
    anything that already reads that format, and so the structure survives
    independently of the text. Splicing the cell text back between the tokens
    reconstructs the table -- which is the check that the two halves describe
    one thing.
    """
    tokens: list[str] = []
    for row in rows:
        tokens.append("<tr>")
        for cell in row:
            span = []
            if cell.get("colspan", 1) > 1:
                span.append(f' colspan="{cell["colspan"]}"')
            if cell.get("rowspan", 1) > 1:
                span.append(f' rowspan="{cell["rowspan"]}"')
            if span:
                tokens.append("<td")
                tokens.extend(span)
                tokens.append(">")
            else:
                tokens.append("<td>")
            tokens.append("</td>")
        tokens.append("</tr>")
    return tokens


def _party_rows(pairs: dict[str, str] | list, kind_label: str, kind_value: str) -> str:
    rows = pairs.items() if isinstance(pairs, dict) else pairs
    out = []
    for label, value in rows:
        out.append(
            f'<div class="prow">{_span(kind_label, label, "plabel")}'
            f'{_span(kind_value, value, "pvalue")}</div>'
        )
    return "".join(out)


def build(recipe, receipt, theme: str = "brand") -> str:
    """The whole page. `theme` is reserved for a second look; only one so far."""
    parse = receipt.ground_truth()
    invoice = parse.get("invoice") or {}
    store = parse.get("store") or {}
    menu = parse.get("menu") or []
    totals = parse.get("total") or {}
    footer = parse.get("footer") or []

    # Deterministic in the seed, like everything else the renderers do: two runs
    # of one plan have to produce the same pixels.
    rng = random.Random(recipe.seed ^ 0x5A4D)
    brand, serial_colour = BRANDS[rng.randrange(len(BRANDS))]
    mark = _initials(store.get("name", ""))

    # ---- masthead
    contact = " · ".join(x for x in (store.get("phone"), store.get("website")) if x)
    masthead = f"""
<div class="masthead">
  <div class="brand">
    {_logo(mark, brand)}
    <div class="brandtext">
      {_span("store.name", store.get("name"), "coname")}
      {_span("store.branch", store.get("branch"), "cobranch")}
      <div class="coline">{_span("store.phone", store.get("phone"))}</div>
    </div>
  </div>
  <div class="serialbox">
    <div>{_span("invoice.form_no.label", "Mẫu số:", "sk")}{_span("invoice.form_no", invoice.get("form_no"), "sv")}</div>
    <div>{_span("invoice.serial.label", "Ký hiệu:", "sk")}{_span("invoice.serial", invoice.get("serial"), "sv")}</div>
    <div>{_span("invoice.number.label", "Số:", "sk")}{_span("invoice.number", invoice.get("number"), "sv")}</div>
  </div>
</div>""" if contact or True else ""

    # ---- title block
    title = f"""
<div class="titleblock">
  {_span("title", parse.get("title"), "doctitle")}
  {_span("invoice.subtitle", invoice.get("subtitle"), "subtitle")}
  {_span("period", invoice.get("period"), "period")}
</div>"""

    # ---- the two parties. The seller repeats its identifying fields here
    # because that is what the form asks for -- and because `store.address`,
    # `store.tax_code` and `store.account` have to appear somewhere or the
    # label describes text no reader can see.
    seller = {
        "Đơn vị bán hàng:": store.get("name", ""),
        "Mã số thuế:": store.get("tax_code", ""),
        "Địa chỉ:": store.get("address", ""),
        "Số tài khoản:": store.get("account", ""),
    }
    parties = f"""
<div class="parties">
  <div class="pblock">
    <div class="ptitle">Bên bán</div>
    {_party_rows({k: v for k, v in seller.items() if v}, "invoice.field.label", "invoice.field")}
  </div>
  <div class="pblock">
    <div class="ptitle">Bên mua</div>
    {_party_rows(invoice.get("left") or {}, "invoice.field.label", "invoice.field")}
    {_party_rows(invoice.get("right") or {}, "invoice.field.label", "invoice.field")}
  </div>
</div>"""

    # ---- the item table, with the blank ruled rows a printed form always has
    titles = ["STT", "Tên hàng hoá, dịch vụ", "ĐVT", "Thuế suất", "SL",
              "Đơn giá", "Thành tiền"]
    classes = ["c-stt", "c-name", "c-unit", "c-vat", "c-qty", "c-price", "c-amt"]
    head = "<tr>" + "".join(
        _cell("th", 0, column, f'<span data-kind="colhdr">{_e(text)}</span>',
              cls=cls, kind="colhdr")
        for column, (text, cls) in enumerate(zip(titles, classes))) + "</tr>"
    head += "<tr class='colnum'>" + "".join(
        _cell("td", 1, column, _e(text), kind="colnum")
        for column, text in enumerate(["1", "2", "3", "4", "5", "6", "7=5x6"])) + "</tr>"

    rows = []
    row_no = 2
    for index, entry in enumerate(menu, start=1):
        fields = [("menu.stt", index), ("menu.name", entry.get("nm")),
                  ("menu.unit", entry.get("unit")), ("menu.vat_rate", entry.get("vatrate")),
                  ("menu.qty", entry.get("cnt")), ("menu.unit_price", entry.get("unitprice")),
                  ("menu.amount", entry.get("price"))]
        rows.append("<tr>" + "".join(
            _cell("td", row_no, column, _span(kind, value), cls=cls, kind=kind)
            for column, ((kind, value), cls) in enumerate(zip(fields, classes))) + "</tr>")
        row_no += 1
    # A printed form is ruled to a fixed depth, so the rows below the last item
    # are empty and still boxed. Two to four of them, by seed.
    for _ in range(rng.randint(2, 4)):
        rows.append("<tr class='blank'>" + "".join(
            _cell("td", row_no, column, "", kind="blank")
            for column in range(7)) + "</tr>")
        row_no += 1

    total_rows = []
    for label, value in totals.items():
        last = label == list(totals)[-1]
        total_rows.append(
            f"<tr class='total{' grand' if last else ''}'>"
            + _cell("td", row_no, 0, _span("total.line.label", label),
                    cls="tlabel", kind="total.line.label", colspan=6)
            + _cell("td", row_no, 6, _span("total.line", value),
                    cls="c-amt", kind="total.line")
            + "</tr>"
        )
        row_no += 1

    table = f"<table class='items'>{head}{''.join(rows)}{''.join(total_rows)}</table>"

    words = (f'<div class="words">{_span("invoice.words.label", "Số tiền bằng chữ:", "wlabel")}'
             f'{_span("invoice.words", invoice.get("words"))}</div>')

    # ---- signatures, with the stamp an electronic invoice carries
    stamp = ""
    if invoice.get("signed_by") or invoice.get("signed_at"):
        stamp = f"""
<div class="stamp" style="border-color:{serial_colour};color:{serial_colour}">
  <div class="tick">&#10004;</div>
  <div>{_span("sign.signedby", invoice.get("signed_by"))}</div>
  <div>{_span("sign.signedat", invoice.get("signed_at"))}</div>
</div>"""
    signatures = f"""
<div class="signs">
  <div class="sign">{_span("sign.title", "Người mua hàng", "stitle")}
    <div class="shint">(Ký, ghi rõ họ tên)</div></div>
  <div class="sign">{_span("sign.title", "Người bán hàng", "stitle")}
    <div class="shint">(Ký, đóng dấu, ghi rõ họ tên)</div>{stamp}</div>
</div>"""

    notes = "".join(f'<div class="note">{_span("footer", line)}</div>' for line in footer)

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
{{FONT_FACES}}
html,body{{margin:0;padding:0;background:#fff;}}
#sheet{{
  position:relative; width:{SHEET_W}px; min-height:{SHEET_H}px; background:#fff;
  font-family:'Liberation Serif',serif; font-size:13.5px; color:#111;
  padding:34px 40px 26px; box-sizing:border-box; -webkit-font-smoothing:antialiased;
}}
#sheet span{{white-space:pre-wrap;}}
.watermark{{
  position:absolute; inset:0; display:flex; align-items:center; justify-content:center;
  font-size:170px; font-weight:700; color:{brand}; opacity:.055;
  transform:rotate(-24deg); pointer-events:none; letter-spacing:.08em;
}}
.masthead{{display:flex; justify-content:space-between; align-items:flex-start; gap:16px;}}
.brand{{display:flex; gap:12px; align-items:flex-start; max-width:66%;}}
.mark{{flex:0 0 auto;}}
.brandtext{{display:flex; flex-direction:column; align-items:flex-start;}}
.coname{{display:inline-block; font-weight:700; font-size:15px; color:{brand}; line-height:1.25;}}
.cobranch{{display:inline-block; font-size:12.5px; color:#333;}}
.coline{{font-size:12.5px; color:#333;}}
.serialbox{{text-align:right; font-size:12.5px; line-height:1.7; white-space:nowrap;}}
.serialbox .sk{{color:#444;}}
.serialbox .sv{{color:{serial_colour}; font-weight:700; margin-left:6px;}}
.titleblock{{text-align:center; margin:14px 0 12px;}}
.doctitle{{display:block; width:fit-content; margin-left:auto; margin-right:auto; font-size:22px; font-weight:700; letter-spacing:.03em;}}
.subtitle{{display:block; width:fit-content; margin-left:auto; margin-right:auto; font-size:12.5px; font-style:italic; color:#333;}}
.period{{display:block; width:fit-content; margin-left:auto; margin-right:auto; font-size:13px; margin-top:3px;}}
.parties{{display:flex; gap:0; border:1px solid #222; margin-bottom:10px;}}
.pblock{{flex:1; padding:7px 10px; min-width:0;}}
.pblock + .pblock{{border-left:1px solid #222;}}
.ptitle{{font-weight:700; font-size:12px; text-transform:uppercase;
        letter-spacing:.06em; color:{brand}; margin-bottom:3px;}}
.prow{{display:flex; gap:6px; font-size:12.5px; line-height:1.5;}}
.plabel{{flex:0 0 auto; color:#333;}}
.pvalue{{flex:0 1 auto; font-weight:700; min-width:0; word-break:break-word;}}
table.items{{width:100%; border-collapse:collapse; font-size:12.5px;}}
table.items th, table.items td{{border:1px solid #222; padding:3px 5px; vertical-align:top;}}
table.items th{{background:#f0f0f0; text-align:center; font-weight:700; font-size:12px;}}
tr.colnum td{{text-align:center; font-size:11px; color:#555; padding:1px 4px;}}
tr.blank td{{height:19px;}}
.c-stt{{width:30px; text-align:center;}}
.c-unit{{width:56px; text-align:center;}}
.c-vat{{width:48px; text-align:center;}}
.c-qty{{width:42px; text-align:right;}}
.c-price{{width:96px; text-align:right;}}
.c-amt{{width:106px; text-align:right;}}
tr.total td{{background:#fafafa;}}
tr.total .tlabel{{text-align:right; padding-right:9px;}}
tr.grand td{{font-weight:700; background:#f0f0f0;}}
.words{{margin-top:8px; font-size:12.5px; border:1px solid #222; padding:5px 8px;}}
.wlabel{{font-weight:700; margin-right:6px;}}
.signs{{display:flex; margin-top:20px; text-align:center;}}
.sign{{flex:1; position:relative;}}
.stitle{{display:inline-block; font-weight:700; font-size:13px;}}
.shint{{font-size:11.5px; font-style:italic; color:#444;}}
.stamp{{margin:14px auto 0; width:78%; border:1.5px solid; border-radius:2px;
       padding:6px 8px; font-size:10.5px; line-height:1.45; text-align:left;}}
.stamp .tick{{float:right; font-size:17px; line-height:1;}}
.note{{text-align:center; font-size:11.5px; font-style:italic; color:#333; margin-top:4px;}}
.notes{{margin-top:16px;}}
</style></head><body><div id="sheet">
<div class="watermark">{_e(mark)}</div>
{masthead}{title}{parties}{table}{words}{signatures}
<div class="notes">{notes}</div>
</div></body></html>"""


__all__ = ["BRANDS", "SHEET_H", "SHEET_W", "build"]
