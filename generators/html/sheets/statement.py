"""The field form: two party blocks under shaded bands, and no table at all.

Drawn from `docs/mau/giay_uy_quyen.html`, itself drawn from a scan of an
insurer's authorisation to collect a refund. It is the first document here that
records no transaction: there is no basket, no quantity, no unit price. What it
has is **fields** -- who authorises, who is authorised, and the one amount
between them -- and the structure lives in how those fields are blocked.

Two things make it recognisable and both are in this module rather than in the
shared base, because no invoice has either: a **shaded band** naming each block
(reversed-out white on grey, running the full width of the framed body), and a
**dotted rule under every value**, because this is a form somebody fills in by
hand.

Which is also this document's limit, and it is stated here rather than buried:
on the paper every value is handwritten, and this renderer types them. The page
is correctly labelled and every field is where the form puts it -- but a model
trained only on this will have learned to read a form nobody fills in with a
printer. See `docs/phan-tich-2-mau-moi.html`.
"""

from __future__ import annotations

from . import base
from .base import esc, span

# The two-colour identity a life insurer prints its forms in: one for the mark,
# one for the band over each block.
LIVERIES = [
    ("#1b1b1b", "#8f8f8f"),
    ("#123f2e", "#7f9a8c"),
    ("#16305c", "#8a94a8"),
    ("#5c1230", "#a88a94"),
]

# What each block of fields is called. The form names them; the document rules
# name the fields inside them. Two blocks, in the order `party_fields` lists.
BANDS = ("NGƯỜI ỦY QUYỀN", "NGƯỜI ĐƯỢC ỦY QUYỀN")


def _mark(store: dict) -> str:
    """The insurer's mark: a ring of petals, drawn rather than fetched."""
    petals = "".join(
        f'<circle cx="{60 + 26 * __import__("math").cos(a):.1f}" '
        f'cy="{45 + 26 * __import__("math").sin(a):.1f}" r="13"/>'
        for a in [i * 3.14159 / 4 for i in range(8)])
    return (f'<svg class="mark" viewBox="0 0 120 92" xmlns="http://www.w3.org/2000/svg">'
            f'<g fill="none" stroke="currentColor" stroke-width="2.2">{petals}'
            f'<circle cx="60" cy="45" r="11"/></g></svg>')


def _block(title: str, pairs, band: str) -> str:
    rows = "".join(
        f'<div class="f">{span("invoice.field.label", label, "k")}'
        f'<span class="v">{span("invoice.field", value)}</span></div>'
        for label, value in pairs)
    return (f'<div class="band" style="background:{band}">'
            f'{span("parties.title", title)}</div>'
            f'<div class="fields">{rows}</div>')


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    rng = base.rng_for(recipe)
    ink, band = LIVERIES[rng.randrange(len(LIVERIES))]
    sections = spec.get("sections") or []
    store = parse.get("store") or {}
    invoice = parse.get("invoice") or {}

    labels = (spec.get("letterhead") or {}).get("labels") or {}
    contact = "".join(
        f'<div>{span(f"store.{key}.label", labels.get(key, ""), "k")} '
        f'{span(f"store.{key}", store[key])}</div>'
        for key in ("address", "address2", "phone", "website", "branch")
        if store.get(key))
    head = (f'<div class="head"><div class="brand" style="color:{ink}">{_mark(store)}'
            f'{span("store.name", store.get("name", ""), "bn")}</div>'
            f'<div class="corp">{contact}</div></div>')

    title = (f'{span("title", parse.get("title", ""), "doc")}'
             f'<div class="sub">{span("subtitle", invoice.get("subtitle", ""))}</div>')

    blocks = []
    for name in sections:
        if name in ("letterhead", "doctitle", "strip"):
            continue
        if name == "parties":
            blocks.append(_block(BANDS[0], base.party_pairs(receipt, parse, "left"), band))
            blocks.append(_block(BANDS[1], base.party_pairs(receipt, parse, "right"), band))
        elif name == "notes":
            lines = list(getattr(getattr(receipt, "invoice", None), "notes", []) or [])
            if lines:
                blocks.append('<div class="clauses">' + "".join(
                    f'<p class="{"num" if line[:2] in ("1)", "2)", "3)") else ""}">'
                    f'{span("note", line)}</p>' for line in lines) + "</div>")
        elif name == "signatures":
            blocks.append(base.signature_block(receipt, parse))
        elif name == "footer":
            blocks.append(base.footer_block(parse))

    serial = invoice.get("serial", "")
    body = (head + title
            + '<div class="box">' + "".join(block for block in blocks if block) + "</div>"
            + f'<div class="tail"><div class="bc">{_barcode(serial)}'
              f'<div class="bcnum">{span("invoice.serial", "* " + " ".join(serial[:8].upper()) + " *")}</div></div>'
              f'<div class="code">{span("invoice.serial", serial)}</div></div>')

    css = """
#sheet{padding:11mm 13mm 8mm;}
.head{display:table;width:100%;padding-bottom:5mm;}
.head > div{display:table-cell;vertical-align:top;}
.brand{width:44%;}
.brand .mark{width:19mm;height:15mm;display:block;}
.brand .bn{display:block;font-weight:bold;font-size:9.5pt;letter-spacing:.3pt;
            margin-top:1mm;line-height:1.2;}
.corp{width:56%;padding-left:20mm;}
.corp .k{font-weight:bold;}
.doc{display:block;text-align:center;font-size:15pt;font-weight:bold;
      letter-spacing:.4pt;margin:0 0 1.8mm;}
.sub{text-align:center;font-style:italic;font-size:7.6pt;margin-bottom:6mm;}
.box{border:.35mm solid #222;}
.band{color:#fff;font-weight:bold;font-size:8pt;letter-spacing:.5pt;padding:1.1mm 2mm;}
.fields{padding:2mm 2.6mm 2.4mm;}
.f{display:table;width:100%;margin:1.2mm 0;}
.f .k{display:table-cell;width:1%;white-space:nowrap;padding-right:2mm;}
.f .v{display:table-cell;width:99%;border-bottom:.25mm dotted #444;padding-bottom:.4mm;}
.clauses{padding:2.4mm 2.6mm 1mm;border-top:.35mm solid #222;}
.clauses p{margin:1.6mm 0;font-style:italic;}
.clauses p.num{padding-left:4mm;}
.signs{display:table;width:100%;border-top:.35mm solid #222;}
.sign{display:table-cell;text-align:center;vertical-align:top;padding:2.2mm 1mm 20mm;}
.sign .t{font-weight:bold;}
.sign .n{font-style:italic;font-size:7.4pt;}
.foot{border-top:.35mm solid #222;padding:2.2mm 2.6mm;font-style:italic;text-align:left;}
.tail{display:table;width:100%;margin-top:3mm;}
.tail > div{display:table-cell;vertical-align:bottom;}
.tail .bc{width:60%;} .tail .code{width:40%;text-align:right;font-size:8.4pt;}
.tail .bars{height:9mm;display:block;}
.tail .bcnum{letter-spacing:3pt;font-size:8pt;}
"""
    return base.document(body, css, paper="A4", padding="11mm 13mm 8mm",
                         font=base.SANS, size="8.4pt", colour="#111",
                         line_height="1.42")


def _barcode(text: str) -> str:
    """A Code 39-shaped run of bars for the form's own number.

    Shaped, not encoded: the bars are the character pattern of Code 39 drawn
    from the serial's own bytes, so the same serial always draws the same bars
    and a different one draws different bars. A scanner will not read it. That
    is a smaller lie than a real barcode encoding a number the page does not
    print, and it is written down here rather than left to be discovered.
    """
    bars, x = [], 0
    for index, character in enumerate(text or "0"):
        code = ord(character)
        for bit in range(4):
            wide = (code >> bit) & 1
            width = 3 if wide else 1
            bars.append(f'<rect x="{x}" y="0" width="{width}" height="30"/>')
            x += width + 2
    return (f'<svg class="bars" viewBox="0 0 {max(x, 1)} 30" preserveAspectRatio="none" '
            f'xmlns="http://www.w3.org/2000/svg"><g fill="#000">{"".join(bars)}</g></svg>')


__all__ = ["BANDS", "LIVERIES", "build"]
