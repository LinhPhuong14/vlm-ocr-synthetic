"""Vietnamese insurance paperwork: certificates, a policy schedule, an
application form, a health-insurance ID card, a property contract.

Every one of the ten layouts here dresses a real `rulebase.content.Receipt`
-- unlike `periodical.py`'s sibling dataclasses, none of these documents
needed a new content shape (see the plan this root shipped from): a
certificate is `no_items: true` field block + signatures, a policy
schedule or a fire certificate is `items`/`totals` + `notes`, a benefit
schedule is `items` with `no_totals: true`. `build()` reads `receipt`'s
typed attributes directly (`receipt.invoice.left`, `receipt.items`, ...)
the same way every other family does, going through `base`'s shared
helpers (`party_pairs`, `items_table`, `signature_block`, `footer_block`,
`notes_blocks`) wherever a document's shape matches what they already draw.

New furniture this root needed and `base.py` now carries for anyone else to
reuse: `comb_box()` (a per-character boxed grid), `bilingual_field_line()`
(an English-over-Vietnamese stacked label), `stamp()` (the round rotated
seal eight of these ten layouts want -- every other family that wants one
still writes its own, per the plan's own "not worth migrating them" call).

No watermark or security-paper CSS anywhere in this file, on purpose: that
class of effect is `rulebase/rules/augmentation.yaml`'s job, applied after
the fact to whatever family drew the page -- see
`samples/insurance-templates/README.md`.
"""

from __future__ import annotations

import random

from . import base
from .base import Rows, esc, span

_TAG = 0x494E53  # "INS"

_INK = "#0d3b66"
_RED = "#c8102e"


def _stamp(*, size_mm: float = 30) -> str:
    return base.stamp("BẢO HIỂM\nMINH HOẠ", colour=_RED, size_mm=size_mm)


def _stamp_wrap(*, size_mm: float = 30) -> str:
    """`_stamp()` is `position:absolute`, so a caller that places it beside
    ordinary flow text (rather than through `signature_block(stamp=)`, which
    already reserves its own room) must reserve the space itself, or the
    circle floats free of layout and lands on whatever text happens to sit
    at its host's top edge. A plain block box the same size as the stamp
    does that -- `margin-left:auto` then pushes the reserved box (and the
    stamp centred inside it) to the right, matching every reference
    mockup's placement.
    """
    box = round(size_mm * 0.87, 2)  # a hair under `size_mm`: rotation trims
    return (f'<div style="position:relative;height:{box}mm;width:{box}mm;'
           f'margin-left:auto;">{_stamp(size_mm=size_mm)}</div>')


# --------------------------------------------------------------- shared bits


def _fields(pairs: list[tuple[str, str]]) -> str:
    return "".join(base.field_line(label, value) for label, value in pairs if value)


def _kv_block(receipt, parse: dict, which: str, *, title: str = "") -> str:
    pairs = base.party_pairs(receipt, parse, which)
    if not pairs:
        return ""
    heading = f'<div class="kvt">{esc(title)}</div>' if title else ""
    return f'<div class="kvb">{heading}{_fields(pairs)}</div>'


def _notes(receipt, *, boxed: bool = False) -> str:
    invoice = getattr(receipt, "invoice", None)
    lines = list(getattr(invoice, "notes", []) or [])
    if not lines:
        return ""
    out = []
    for block in base.notes_blocks(lines):
        for value in block:
            cls = "nh" if value.endswith(":") else ""
            out.append(f'<p class="{cls}">{span("note", value.rstrip(":"))}</p>')
    cls = "notes boxed" if boxed else "notes"
    return f'<div class="{cls}">{"".join(out)}</div>'


def _totals_rows(parse: dict) -> list[dict]:
    totals = parse.get("total") or {}
    if not totals:
        return []
    items = list(totals.items())
    return [{"label": label, "value": value, "grand": index == len(items) - 1}
            for index, (label, value) in enumerate(items)]


def _table(spec: dict, receipt, parse: dict, rows: Rows, *, with_totals: bool = True) -> str:
    totals = _totals_rows(parse) if with_totals else None
    return base.items_table(spec, receipt, parse, rows, totals=totals)


_SHARED_CSS = f"""
.kvb{{margin-bottom:3mm;}}
.kvt{{font-weight:700;font-size:8pt;color:{_INK};letter-spacing:.3pt;margin-bottom:1.5mm;
     text-transform:uppercase;}}
.f{{display:flex;gap:1.5mm;margin-bottom:.9mm;font-size:8.4pt;}}
.f .k{{color:#333;white-space:nowrap;}}
.f .v{{font-weight:700;color:#111;}}
.f.dot{{border-bottom:.2mm dotted #888;}}
.notes{{margin:3mm 0;font-size:8.2pt;line-height:1.5;text-align:justify;}}
.notes p{{margin:1mm 0;}}
.notes p.nh{{font-weight:700;margin-top:2mm;}}
.notes.boxed{{border-left:.9mm solid #d98b00;background:#fff8e9;padding:2.5mm 3mm;}}
.signs{{display:flex;justify-content:space-around;margin-top:8mm;text-align:center;
       font-size:8.2pt;}}
.signs .sign{{position:relative;width:48mm;}}
.signs .t{{font-weight:700;text-transform:uppercase;display:block;}}
.signs .n{{font-style:italic;color:#555;font-size:7.6pt;}}
.signs .who{{margin-top:14mm;border-top:.2mm solid #999;padding-top:1mm;font-weight:700;}}
.foot{{margin-top:4mm;font-size:7.4pt;color:#555;font-style:italic;border-top:.2mm solid #ccc;
      padding-top:1.5mm;}}
.foot div{{margin-bottom:.4mm;}}
h1.title{{text-align:center;font-weight:800;text-transform:uppercase;font-size:12.5pt;
         color:{_INK};margin:0 0 1mm;letter-spacing:.2pt;}}
.sub{{text-align:center;font-size:8.4pt;font-style:italic;color:#555;margin-bottom:4mm;}}
table.items{{width:100%;border-collapse:collapse;font-size:8pt;margin:2mm 0;}}
table.items th,table.items td{{border:.25mm solid #999;padding:1.4mm 1.8mm;vertical-align:top;}}
table.items thead th{{background:#eef2f6;font-weight:700;text-align:left;}}
table.items tr.grouprow td{{background:#f3f6fa;font-weight:700;}}
table.items tr.total td,table.items tr.grand td{{font-weight:700;border-top:.5mm solid {_INK};}}
"""


# ------------------------------------------------------------ moto_cert (LO-01)


def _build_moto_cert(recipe, receipt, spec: dict, parse: dict, rng: random.Random) -> str:
    invoice = receipt.invoice
    body = (
        '<div class="frame"><div class="inner">'
        '<div class="head">'
        f'<div class="logo">MH</div><div class="co">'
        f'{span("store.name", receipt.store.name, "nm")}'
        f'<div class="sub2">Bảo hiểm bắt buộc trách nhiệm dân sự</div></div>'
        f'<div class="serial">Số GCN<div class="no">{span("invoice.number", invoice.number)}</div></div>'
        '</div>'
        f'<div class="title2"><h1 class="title2h">{span("title", receipt.title)}</h1>'
        f'<div class="sub2b">{span("invoice.subtitle", invoice.subtitle)}</div></div>'
        f'<div class="grid2">{_fields(base.party_pairs(receipt, parse, "left"))}</div>'
        '<div class="foot2">'
        f'{_notes(receipt)}'
        '<div class="sign2">'
        f'<div class="date">{span("invoice.field", invoice.period)}</div>'
        '<div class="role">Doanh nghiệp bảo hiểm</div>'
        f'{_stamp_wrap(size_mm=20)}'
        '</div></div>'
        f'{base.footer_block(parse)}'
        '</div></div>'
    )
    css = _SHARED_CSS + f"""
.frame{{position:absolute;inset:3mm;border:.6mm solid {_INK};border-radius:1.2mm;box-sizing:border-box;}}
.inner{{position:absolute;inset:5mm;display:flex;flex-direction:column;}}
.head{{display:flex;align-items:flex-start;gap:2.5mm;border-bottom:.35mm solid {_INK};padding-bottom:1.4mm;}}
.logo{{width:9mm;height:9mm;border-radius:50%;border:.4mm solid {_INK};display:flex;
      align-items:center;justify-content:center;font-weight:800;color:{_INK};flex:none;}}
.co{{flex:1;font-size:7.6pt;}}
.co .nm{{font-weight:700;color:{_INK};text-transform:uppercase;}}
.sub2{{font-size:6.6pt;color:#555;}}
.serial{{text-align:right;font-size:6.6pt;color:#555;}}
.serial .no{{font-family:"Courier New",monospace;font-size:8pt;font-weight:700;color:{_RED};}}
.title2{{text-align:center;margin:1.5mm 0;}}
.title2h{{font-size:8.4pt;font-weight:700;color:{_INK};text-transform:uppercase;margin:0;line-height:1.25;}}
.sub2b{{font-size:6.4pt;font-style:italic;color:#555;margin-top:.5mm;}}
.grid2{{flex:1;display:grid;grid-template-columns:1fr 1fr;column-gap:3mm;font-size:6.6pt;}}
.grid2 .f{{font-size:6.6pt;margin-bottom:.6mm;}}
.foot2{{position:relative;border-top:.35mm solid {_INK};padding-top:1mm;}}
.foot2 .notes{{font-size:6.2pt;margin:0;}}
.sign2{{position:relative;text-align:right;margin-top:1mm;}}
.sign2 .date{{font-size:6.2pt;font-style:italic;}}
.sign2 .role{{font-size:6.6pt;font-weight:700;}}
"""
    return base.document(body, css, paper="A6_LANDSCAPE", padding="0", size="7pt", font=base.SANS)


# ------------------------------------------------------------ auto_cert (LO-02)


def _build_auto_cert(recipe, receipt, spec: dict, parse: dict, rng: random.Random, rows: Rows) -> str:
    invoice = receipt.invoice
    pairs = base.party_pairs(receipt, parse, "left")
    table_rows = "".join(
        f'<tr><td class="idx">{index + 1}</td><th>{esc(label)}</th>'
        f'<td>{span("invoice.field", value)}</td></tr>'
        for index, (label, value) in enumerate(pairs)
    )
    body = (
        '<div class="head">'
        f'<div class="mark">MH</div><div class="org">'
        f'<div class="n">{span("store.name", receipt.store.name)}</div></div>'
        f'<div class="lien">Số Giấy chứng nhận<div class="code">{span("invoice.number", invoice.number)}</div></div>'
        '</div>'
        f'<h1 class="title">{span("title", receipt.title)}</h1>'
        f'<div class="sub">{span("invoice.subtitle", invoice.subtitle)}</div>'
        f'<table class="items"><tbody>{table_rows}</tbody></table>'
        f'<div class="bottom">{_notes(receipt)}<div class="sign">{_stamp_wrap()}'
        f'<div class="role">Doanh nghiệp bảo hiểm</div></div></div>'
        f'{base.footer_block(parse)}'
    )
    css = _SHARED_CSS + f"""
.head{{display:flex;align-items:center;gap:4mm;border-bottom:.8mm solid {_INK};padding-bottom:2mm;}}
.mark{{width:14mm;height:14mm;background:{_INK};color:#fff;display:flex;align-items:center;
      justify-content:center;font-size:6mm;font-weight:800;border-radius:1mm;flex:none;}}
.org{{flex:1;}} .org .n{{font-size:11pt;font-weight:800;color:{_INK};text-transform:uppercase;}}
.lien{{text-align:right;font-size:8pt;color:#444;}}
.lien .code{{font-family:"Courier New",monospace;font-size:11pt;font-weight:700;color:#111;}}
table.items .idx{{width:7mm;text-align:center;background:#f4f7fa;color:#555;}}
table.items th{{width:40mm;background:#e8f0f7;text-align:left;color:{_INK};}}
.bottom{{position:relative;margin-top:4mm;}}
.sign{{position:relative;text-align:right;margin-top:2mm;}}
"""
    return base.document(body, css, paper="A5_LANDSCAPE", padding="8mm 10mm", font=base.SANS)


# --------------------------------------------------------- life_schedule (LO-03)


def _build_life_schedule(recipe, receipt, spec: dict, parse: dict, rng: random.Random, rows: Rows) -> str:
    invoice = receipt.invoice
    body = (
        '<div class="band">'
        f'<div class="brow"><div class="brand">{span("store.name", receipt.store.name)}</div>'
        f'<div class="pol">Số hợp đồng<b>{span("invoice.number", invoice.number)}</b></div></div>'
        f'<h1 class="btitle">{span("title", receipt.title)}</h1>'
        f'<div class="bsub">{span("invoice.subtitle", invoice.subtitle)}</div>'
        '</div>'
        '<main>'
        f'<section>{_kv_block(receipt, parse, "left", title="Bên mua bảo hiểm")}</section>'
        f'{_table(spec, receipt, parse, rows)}'
        f'{_notes(receipt, boxed=True)}'
        f'<div class="signs">{base.signature_block(receipt, parse, stamp=_stamp())}</div>'
        '</main>'
        f'{base.footer_block(parse)}'
    )
    css = _SHARED_CSS + f"""
.band{{background:linear-gradient(100deg,{_INK},#1a6fb0);color:#fff;padding:6mm 10mm 5mm;}}
.brow{{display:flex;justify-content:space-between;font-size:8pt;}}
.brand{{font-size:11pt;font-weight:800;}}
.pol{{text-align:right;}} .pol b{{display:block;font-family:"Courier New",monospace;font-size:10pt;}}
.btitle{{color:#fff;font-size:12pt;margin-top:4mm;}}
.bsub{{color:#dbe7f2;font-size:7.6pt;font-style:italic;margin-top:1.5mm;max-width:150mm;}}
main{{padding:6mm 10mm;}}
.signs{{margin-top:6mm;}}
"""
    return base.document(body, css, paper="A4", padding="0", font=base.SANS)


# ----------------------------------------------------- application_form (LO-04)


def _checks_table(receipt) -> str:
    invoice = receipt.invoice
    if not invoice.checks:
        return ""
    rows_html = []
    for question, answer, detail in invoice.checks:
        # The answer word itself ("Có"/"Không") is real, checkable ground
        # truth (content.py's checks-drawing block, unlike the decorative
        # mark `form.py::_checklist()` uses) -- so it must be printed
        # somewhere, not just implied by an abstract bullet. It lands in
        # whichever column it names; the other column has nothing to claim.
        is_yes = answer.strip().lower().startswith("c")
        yes_cell = span("invoice.checks.answer", answer) if is_yes else ""
        no_cell = span("invoice.checks.answer", answer) if not is_yes else ""
        rows_html.append(
            "<tr>"
            f'<td>{span("invoice.checks.question", question)}</td>'
            f'<td class="yn">{yes_cell}</td><td class="yn">{no_cell}</td>'
            f'<td>{span("invoice.checks.detail", detail)}</td>'
            "</tr>"
        )
    return (
        '<table class="items"><thead><tr><th>Câu hỏi</th><th class="yn">Có</th>'
        '<th class="yn">Không</th><th>Chi tiết</th></tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody></table>'
    )


def _build_application_form(recipe, receipt, spec: dict, parse: dict,
                            rng: random.Random, rows: Rows) -> str:
    invoice = receipt.invoice
    left = base.party_pairs(receipt, parse, "left")
    combable = {"applicant_name", "applicant_dob", "applicant_id"}
    field_html = []
    for key, (label, value) in zip((spec.get("field_keys") or []), left):
        if not value:
            continue
        if key in combable:
            groups = (2, 2, 4) if key == "applicant_dob" else None
            field_html.append(
                f'<div class="line"><span class="lab">{esc(label)}</span>'
                f'{base.comb_box("invoice.field", value, groups=groups)}</div>'
            )
        else:
            field_html.append(f'<div class="line">{base.field_line(label, value)}</div>')
    body = (
        f'<div class="issuer">{span("store.name", receipt.store.name)}'
        f' &middot; Số hồ sơ: {span("invoice.number", invoice.number)}</div>'
        f'<h1 class="title">{span("title", receipt.title)}</h1>'
        '<div class="sub">Vui lòng viết chữ IN HOA · Đánh dấu vào ô lựa chọn</div>'
        f'<div class="sec"><div class="t">A</div><div class="b">{"".join(field_html)}</div></div>'
        f'<div class="sec"><div class="t">B</div><div class="b">'
        f'{_table(spec, receipt, parse, rows, with_totals=False)}</div></div>'
        f'<div class="sec"><div class="t">C</div><div class="b">{_checks_table(receipt)}</div></div>'
        f'{_notes(receipt, boxed=True)}'
        f'<div class="signs">{base.signature_block(receipt, parse)}</div>'
        f'{base.footer_block(parse)}'
    )
    css = _SHARED_CSS + f"""
.issuer{{text-align:right;font-size:7.4pt;font-weight:700;color:{_INK};
        text-transform:uppercase;margin-bottom:2mm;}}
.sec{{margin:3mm 0;}}
.sec .t{{background:{_INK};color:#fff;font-size:8pt;font-weight:700;padding:1mm 2mm;
        display:inline-block;}}
.sec .b{{border:.25mm solid {_INK};border-top:0;padding:2.5mm 3mm;}}
.line{{margin-bottom:1.8mm;display:flex;align-items:center;gap:2mm;flex-wrap:wrap;}}
.line .lab{{font-size:8pt;color:#222;white-space:nowrap;}}
table.items .yn{{width:16mm;text-align:center;font-size:7.6pt;}}
"""
    return base.document(body, css, paper="A4", padding="10mm 12mm")


# ----------------------------------------------------- health_id_card (LO-05)


def _build_health_id_card(recipe, receipt, spec: dict, parse: dict, rng: random.Random) -> str:
    invoice = receipt.invoice
    front_fields = "".join(
        f'<div class="cf">{base.field_line(label, value)}</div>'
        for label, value in base.party_pairs(receipt, parse, "left") if value
    )
    front = (
        '<div class="card"><div class="edge"></div><div class="cface">'
        f'<div class="corg">{span("store.name", receipt.store.name)}</div>'
        f'<div class="ctitle">{span("title", receipt.title)}</div>'
        f'<div class="cno">{span("invoice.number", invoice.number)}</div>'
        f'{front_fields}</div></div>'
    )
    back = (
        '<div class="card"><div class="edge"></div><div class="cface">'
        f'{_notes(receipt)}</div></div>'
    )
    body = (
        '<div class="stage">'
        f'<div class="wrap"><div class="cap">Mặt trước</div>{front}</div>'
        f'<div class="wrap"><div class="cap">Mặt sau</div>{back}</div>'
        '</div>'
        f'{base.footer_block(parse)}'
    )
    css = _SHARED_CSS + f"""
.stage{{display:flex;gap:10mm;justify-content:center;padding-top:6mm;}}
.wrap{{display:flex;flex-direction:column;align-items:center;gap:2mm;}}
.cap{{font-size:7pt;color:#666;letter-spacing:.4mm;text-transform:uppercase;}}
.card{{width:85.6mm;height:53.98mm;border-radius:3.18mm;background:#fff;position:relative;
      overflow:hidden;border:.3mm solid #c9d3dc;box-shadow:0 1mm 3mm rgba(0,0,0,.25);}}
.edge{{position:absolute;inset:1.3mm;border:.25mm solid #9fc0d8;border-radius:2.2mm;
      pointer-events:none;}}
.cface{{position:absolute;inset:3mm;display:flex;flex-direction:column;font-size:6.6pt;}}
.corg{{font-weight:700;color:{_INK};text-transform:uppercase;border-bottom:.3mm solid {_INK};
      padding-bottom:.5mm;}}
.ctitle{{font-weight:700;color:{_RED};text-transform:uppercase;font-size:7.6pt;margin:.8mm 0;}}
.cno{{font-family:"Courier New",monospace;font-size:9pt;font-weight:700;letter-spacing:1mm;
     margin-bottom:1mm;}}
.cf{{font-size:6.4pt;margin-bottom:.5mm;}}
.cface .notes{{font-size:6pt;margin:0;}}
"""
    return base.document(body, css, paper="A4_LANDSCAPE", padding="0", font=base.SANS)


# ------------------------------------------------------------- health_cert (LO-06)


def _build_health_cert(recipe, receipt, spec: dict, parse: dict, rng: random.Random, rows: Rows) -> str:
    invoice = receipt.invoice
    sidebar = (
        '<aside>'
        f'<div class="brand">{span("store.name", receipt.store.name)}</div>'
        '<div class="memcard">'
        f'<div class="lbl">Số thẻ hội viên</div><div class="no">{span("invoice.number", invoice.number)}</div>'
        f'<div class="nm">{span("invoice.field", (base.party_pairs(receipt, parse, "left") or [("", "")])[0][1])}</div>'
        '</div>'
        f'{_fields(base.party_pairs(receipt, parse, "right"))}'
        '</aside>'
    )
    main = (
        '<main>'
        f'<h1 class="title" style="text-align:left">{span("title", receipt.title)}</h1>'
        f'{_table(spec, receipt, parse, rows, with_totals=False)}'
        f'{_notes(receipt, boxed=True)}'
        f'<div class="signs">{base.signature_block(receipt, parse, stamp=_stamp())}</div>'
        '</main>'
    )
    body = f'<div class="sidebar-wrap">{sidebar}{main}</div>{base.footer_block(parse)}'
    css = _SHARED_CSS + """
.sidebar-wrap{display:flex;margin:-14mm -14mm 0;min-height:calc(100% + 14mm);}
aside{width:34%;flex:none;background:#06584f;color:#eafaf6;padding:14mm 8mm;box-sizing:border-box;}
aside .brand{font-size:11pt;font-weight:800;margin-bottom:6mm;}
aside .f{font-size:7.6pt;color:#eafaf6;}
aside .f .k{color:#bfe3da;} aside .f .v{color:#fff;}
.memcard{background:linear-gradient(140deg,#0b7a6c,#0f9a86);border-radius:2.5mm;padding:4mm;
         margin-bottom:6mm;}
.memcard .lbl{font-size:6.4pt;letter-spacing:.5mm;text-transform:uppercase;opacity:.85;}
.memcard .no{font-family:"Courier New",monospace;font-size:9pt;font-weight:700;margin:1mm 0;}
.memcard .nm{font-size:8pt;font-weight:700;text-transform:uppercase;}
main{flex:1;padding:14mm;box-sizing:border-box;}
"""
    return base.document(body, css, paper="A4", padding="14mm", font=base.SANS)


# -------------------------------------------------------------- cargo_policy (LO-07)


def _build_cargo_policy(recipe, receipt, spec: dict, parse: dict, rng: random.Random) -> str:
    invoice = receipt.invoice
    bilingual_labels = spec.get("bilingual_left") or []
    rows_html = []
    pairs = base.party_pairs(receipt, parse, "left")
    for (label, value), (label_en, label_vn) in zip(pairs, bilingual_labels):
        if not value:
            continue
        rows_html.append(f'<div class="fr">{base.bilingual_field_line(label_en, label_vn, value)}</div>')
    body = (
        '<header>'
        f'<div class="org">{span("store.name", receipt.store.name)}</div>'
        f'<div class="polno">Policy No.<b>{span("invoice.number", invoice.number)}</b></div>'
        '</header>'
        f'<h1 class="title">{span("title", receipt.title)}</h1>'
        f'<div class="fields">{"".join(rows_html)}</div>'
        f'{_notes(receipt, boxed=True)}'
        f'<div class="signs">{base.signature_block(receipt, parse, stamp=_stamp())}</div>'
        f'{base.footer_block(parse)}'
    )
    css = _SHARED_CSS + f"""
header{{display:flex;justify-content:space-between;border-bottom:.9mm solid {_INK};padding-bottom:2mm;}}
.org{{font-size:11pt;font-weight:800;color:{_INK};text-transform:uppercase;}}
.polno{{text-align:right;font-size:8pt;}} .polno b{{display:block;font-family:"Courier New",monospace;
       color:{_RED};font-size:10pt;}}
.fields{{border:.4mm solid {_INK};margin:4mm 0;}}
.fields .fr{{border-bottom:.25mm solid #ccd6e0;padding:1.5mm 2.5mm;}}
.fields .fr:last-child{{border-bottom:0;}}
.f .k{{display:flex;flex-direction:column;width:56mm;flex:none;}}
.f .en{{font-size:6.8pt;font-weight:700;text-transform:uppercase;color:{_INK};}}
.f .vn{{font-size:7.4pt;font-style:italic;color:#555;}}
"""
    return base.document(body, css, paper="A4", padding="12mm 14mm", font=base.SANS)


# --------------------------------------------------------------- fire_cert (LO-08)


def _build_fire_cert(recipe, receipt, spec: dict, parse: dict, rng: random.Random, rows: Rows) -> str:
    invoice = receipt.invoice
    body = (
        f'<div class="issuer">{span("store.name", receipt.store.name)}'
        f' &middot; Số: {span("invoice.number", invoice.number)}</div>'
        f'<h1 class="title">{span("title", receipt.title)}</h1>'
        f'<div class="sub">{span("invoice.subtitle", invoice.subtitle)}</div>'
        f'<div class="sec2"><div class="cap">I. Bên mua bảo hiểm và đối tượng bảo hiểm</div>'
        f'{_kv_block(receipt, parse, "left")}</div>'
        f'<div class="sec2"><div class="cap">II. Danh mục tài sản và số tiền bảo hiểm</div>'
        f'{_table(spec, receipt, parse, rows)}</div>'
        f'<div class="sec2"><div class="cap">III. Phí bảo hiểm và thời hạn</div>'
        f'{_notes(receipt)}</div>'
        f'<div class="signs">{base.signature_block(receipt, parse, stamp=_stamp())}</div>'
        f'{base.footer_block(parse)}'
    )
    css = _SHARED_CSS + f"""
.issuer{{text-align:right;font-size:7.4pt;font-weight:700;color:{_INK};
        text-transform:uppercase;margin-bottom:2mm;}}
.sec2{{margin:3.5mm 0;}}
.sec2 .cap{{font-weight:700;font-size:8.6pt;color:{_INK};text-transform:uppercase;
           margin-bottom:1.5mm;letter-spacing:.2pt;}}
"""
    return base.document(body, css, paper="A4", padding="14mm 16mm")


# ------------------------------------------------------------- travel_cert (LO-09)


def _build_travel_cert(recipe, receipt, spec: dict, parse: dict, rng: random.Random, rows: Rows) -> str:
    invoice = receipt.invoice
    bilingual_labels = spec.get("bilingual_left") or []
    left_html = []
    pairs = base.party_pairs(receipt, parse, "left")
    for (label, value), (label_en, label_vn) in zip(pairs, bilingual_labels):
        if value:
            left_html.append(base.bilingual_field_line(label_en, label_vn, value))
    body = (
        '<header>'
        f'<div class="org">{span("store.name", receipt.store.name)}</div>'
        f'<div class="polno">Certificate No.<b>{span("invoice.number", invoice.number)}</b></div>'
        '</header>'
        f'<h1 class="title">{span("title", receipt.title)}</h1>'
        '<div class="grid3">'
        f'<div class="left">{"".join(left_html)}</div>'
        '<div class="perf"></div>'
        f'<div class="right">{_table(spec, receipt, parse, rows, with_totals=False)}'
        f'{_notes(receipt, boxed=True)}</div>'
        '</div>'
        f'<div class="signs">{base.signature_block(receipt, parse, stamp=_stamp())}</div>'
        f'{base.footer_block(parse)}'
    )
    css = _SHARED_CSS + f"""
header{{display:flex;justify-content:space-between;border-bottom:.9mm solid {_INK};padding-bottom:2mm;}}
.org{{font-size:11pt;font-weight:800;color:{_INK};text-transform:uppercase;}}
.polno{{text-align:right;font-size:8pt;}} .polno b{{display:block;font-family:"Courier New",monospace;
       color:{_RED};font-size:10pt;}}
.grid3{{display:grid;grid-template-columns:1fr 3mm 1.2fr;margin-top:5mm;}}
.perf{{border-left:.4mm dashed #bbb;}}
.left{{padding-right:6mm;}} .right{{padding-left:6mm;}}
table.items th.r,table.items td.r{{text-align:right;}}
"""
    return base.document(body, css, paper="A4_LANDSCAPE", padding="10mm 12mm", font=base.SANS)


# --------------------------------------------------------- property_contract (LO-10)


def _build_property_contract(recipe, receipt, spec: dict, parse: dict,
                             rng: random.Random, rows: Rows) -> str:
    invoice = receipt.invoice
    parties = (
        f'<div class="party"><div class="t">Bên mua bảo hiểm (Bên A)</div>'
        f'{_fields(base.party_pairs(receipt, parse, "left"))}</div>'
        f'<div class="party"><div class="t">Doanh nghiệp bảo hiểm (Bên B)</div>'
        f'{_fields(base.party_pairs(receipt, parse, "right"))}</div>'
    )
    body = (
        f'<div class="issuer">Số: {span("invoice.number", invoice.number)}</div>'
        f'<h1 class="title">{span("title", receipt.title)}</h1>'
        f'<div class="sub">{span("invoice.subtitle", invoice.subtitle)}</div>'
        f'{parties}'
        f'<div class="sec2"><div class="cap">Đối tượng bảo hiểm và số tiền bảo hiểm</div>'
        f'{_table(spec, receipt, parse, rows)}</div>'
        f'{_notes(receipt)}'
        f'<div class="signs">{base.signature_block(receipt, parse, stamp=_stamp())}</div>'
        f'{base.footer_block(parse)}'
    )
    css = _SHARED_CSS + f"""
.issuer{{text-align:right;font-size:7.4pt;font-weight:700;color:{_INK};margin-bottom:2mm;}}
.party{{margin-bottom:3mm;}}
.party .t{{font-weight:700;text-transform:uppercase;margin-bottom:1mm;color:{_INK};font-size:8.4pt;}}
.sec2{{margin:3.5mm 0;}}
.sec2 .cap{{font-weight:700;font-size:8.6pt;color:{_INK};text-transform:uppercase;
           margin-bottom:1.5mm;}}
"""
    return base.document(body, css, paper="A4", padding="16mm 18mm")


_COMPOSITIONS = {
    "moto_cert": _build_moto_cert,
    "auto_cert": _build_auto_cert,
    "life_schedule": _build_life_schedule,
    "application_form": _build_application_form,
    "health_id_card": _build_health_id_card,
    "health_cert": _build_health_cert,
    "cargo_policy": _build_cargo_policy,
    "fire_cert": _build_fire_cert,
    "travel_cert": _build_travel_cert,
    "property_contract": _build_property_contract,
}

# Compositions whose renderer needs a page-wide `Rows()` counter (anything
# that draws a `base.items_table()`) versus those that never draw a table.
_NEEDS_ROWS = {
    "auto_cert", "life_schedule", "application_form", "health_cert",
    "fire_cert", "travel_cert", "property_contract",
}


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    """The whole page, for whichever of the ten insurance compositions this
    layout is -- see the module docstring for why each one still dresses a
    plain `Receipt` rather than a shape of its own.
    """
    composition = spec.get("composition")
    renderer = _COMPOSITIONS.get(composition)
    if renderer is None:
        raise KeyError(
            f"unknown insurance composition {composition!r}; "
            f"have {', '.join(sorted(_COMPOSITIONS))}"
        )
    rng = base.rng_for(recipe, _TAG)
    if composition in _NEEDS_ROWS:
        return renderer(recipe, receipt, spec, parse, rng, Rows())
    return renderer(recipe, receipt, spec, parse, rng)


__all__ = ["build"]
