"""The till roll, drawn as a page rather than as a grid of characters.

There is no hand-drawn reference for this one, and that is the point: a thermal
receipt really is a monospace device, so the character grid is the *right* model
for it and this path is not an improvement. It exists so that `--template` is
total -- a run mixes layouts, and a flag that renders nine of fourteen and
crashes on the rest is a flag nobody can put in a pipeline.

So it is deliberately plain: a narrow roll, one monospace family, rules where
the layout asks for rules. What it does gain from being HTML is the same thing
the invoices gain -- the item table is a real table, so the columns are the
engine's problem and the totals row spans them with `colspan` instead of
happening to be wide.
"""

from __future__ import annotations

from . import base
from .base import Rows, span

# A roll is 80mm or 58mm across and as long as it needs to be. The height is a
# floor rather than a size: a roll has no bottom edge until the cutter makes one.
ROLL = {"wide": ("80mm", "150mm"), "narrow": ("58mm", "120mm")}


def _meta(receipt) -> str:
    entries = list(getattr(receipt, "meta", []) or [])
    if not entries:
        return ""
    rows = "".join(
        f'<div class="mrow">{span("meta.label", label, "k")}'
        f'{span("meta.value", value, "v")}</div>'
        for label, value in entries)
    return f'<div class="meta">{rows}</div>'


def _header(parse: dict) -> str:
    store = parse.get("store") or {}
    lines = "".join(
        f'<div>{span(f"store.{key}", store[key])}</div>'
        for key in ("branch", "address", "address2", "phone", "tax_code", "website")
        if store.get(key))
    return (f'<div class="head">{span("store.name", store.get("name", ""), "n")}'
            f'{lines}{span("title", parse.get("title", ""), "doc")}</div>')


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    rows = Rows()
    entries = list((parse.get("total") or {}).items())
    totals = [{"label": label, "value": value, "grand": index == len(entries) - 1}
              for index, (label, value) in enumerate(entries)]
    table = base.items_table(spec, receipt, parse, rows, totals=totals)
    body = (_header(parse) + _meta(receipt) + table + base.footer_block(parse))

    width, height = ROLL["narrow" if base.ncols_of(spec) < 36 else "wide"]
    css = f"""
#sheet{{width:{width};min-height:{height};padding:5mm 3mm;}}
.head{{text-align:center;margin-bottom:2mm;}}
.head .n{{display:block;font-weight:bold;font-size:1.25em;line-height:1.2;}}
.head .doc{{display:block;font-weight:bold;margin-top:1.5mm;}}
.meta{{border-top:.2mm dashed #333;border-bottom:.2mm dashed #333;
       padding:1mm 0;margin:1.5mm 0;}}
.mrow{{display:table;width:100%;}}
.mrow .k{{display:table-cell;}} .mrow .v{{display:table-cell;text-align:right;}}
table.items th{{border-bottom:.2mm dashed #333;text-align:left;padding:.8mm .4mm;}}
table.items th.r{{text-align:right;}} table.items th.c{{text-align:center;}}
table.items td{{padding:.6mm .4mm;vertical-align:top;}}
tr.total td,tr.grand td{{border-top:.2mm dashed #333;}}
tr.grand td{{font-weight:bold;font-size:1.1em;}}
td.tlabel{{text-align:right;}}
.foot{{margin-top:3mm;text-align:center;}}
"""
    # The roll is not one of `PAPERS`, so the page box is set here and the
    # skeleton's A4 default is overridden by the rule above -- last one wins,
    # which is the whole reason `#sheet` is restated in every family's CSS.
    return base.document(body, css, paper="A4", padding="5mm 3mm",
                         font=base.MONO, size="8pt", colour="#111",
                         line_height="1.25").replace(
        "@page{size:A4 portrait;margin:0;}",
        f"@page{{size:{width} {height};margin:0;}}")


__all__ = ["ROLL", "build"]
