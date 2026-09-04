"""Newspaper and magazine pages: running prose, not a transaction.

Every other family in this package dresses a `Receipt` -- a store, a basket,
a total, sometimes two parties and a signature. This one dresses the four
`rulebase.periodical` dataclasses instead (`ArticlePage`, `ClassifiedsPage`,
`TocPage`, `QaPage`), which have none of that. `build()` reads `receipt`'s
typed attributes directly rather than re-parsing `parse` (`receipt.
ground_truth()`) the way `statement.py` reads `receipt.invoice`/`.store`
directly instead of going through `base`'s `Receipt`-shaped helpers -- the
label and the page come from the same object either way, this just skips
turning it into a dict and back.

None of the four compositions built so far needs a real `<table>`
(confirmed by reading all four target mockups in `samples/periodical-
templates/`), so every block here is a `<div>`/`<p>`/`<ul>` built from
`base.span()`/`base.esc()`, the same box contract (`data-kind` on every
labelled run) every other family keeps.

The grey halftone-dot photo placeholder every mockup uses is furniture, not
label, the same way `form.py::_photobox()` treats a portrait-photo corner:
no `span()`, no ground truth, because the box would print whether or not a
real photo were ever dropped in.
"""

from __future__ import annotations

from . import base
from .base import esc, span

# The mockups' own "no photo yet" marker -- see the module docstring.
_PHOTO_LABEL = "ẢNH"


def _photo_box(*, height: str = "40mm", label: str = _PHOTO_LABEL) -> str:
    return (f'<div class="ph" style="height:{height}">'
            f'<span class="phl">{span("photo.placeholder", label)}</span></div>')


# --------------------------------------------------------------- lead + rail


def _lead_sidebar(receipt) -> str:
    flag = (
        '<div class="flag">'
        f'<div class="ear">{span("dateline", receipt.dateline_day, "d")}<br>'
        f'{span("issue_date", receipt.issue_date)}<br>{span("issue_no", receipt.issue_no)}</div>'
        f'<div class="name">{span("masthead", receipt.masthead, "nm")}'
        f'<div class="slogan">{span("slogan", receipt.slogan)}</div></div>'
        '<div class="ear r">'
        f'{span("price", receipt.price, "pr")}<br>{span("website", receipt.website)}<br>'
        f'{span("hotline", receipt.hotline)}</div>'
        '</div><div class="rule"></div>'
    )

    teasers = ""
    if receipt.teasers:
        items = "".join(
            f'<div class="t">{_photo_box(height="19mm")}<div>'
            f'<div class="k">{span("teaser.kicker", item.kicker)}</div>'
            f'<h4>{span("teaser.headline", item.headline)}</h4>'
            f'<p>{span("teaser.blurb", item.blurb)} '
            f'<b>{span("teaser.page", item.page_ref)}</b></p></div></div>'
            for item in receipt.teasers
        )
        teasers = f'<div class="teasers">{items}</div>'

    body = "".join(f'<p>{span("body", line)}</p>' for line in receipt.body)
    lead = (
        '<div class="lead">'
        f'<div class="kicker">{span("kicker", receipt.kicker)}</div>'
        f'<h2 class="head">{span("headline", receipt.headline)}</h2>'
        f'<div class="deck">{span("deck", receipt.deck)}</div>'
        f'<div class="byline">{span("byline", receipt.byline)}</div>'
        f'{_photo_box(height="70mm")}'
        f'<div class="cap">{span("caption", receipt.lead_caption)}</div>'
        f'<div class="body">{body}</div>'
        f'<div class="jump">{span("jump", receipt.jump_line)}</div>'
        '</div>'
    )

    box = ""
    if receipt.sidebar_title:
        items = "".join(
            f'<li>{span("sidebar.label", row.label, "l")} '
            f'{span("sidebar.text", row.text)}</li>'
            for row in receipt.sidebar_items
        )
        box = (f'<div class="box"><h3>{span("sidebar.title", receipt.sidebar_title)}</h3>'
              f'<ul>{items}</ul></div>')
    secondary = ""
    if receipt.sidebar_headline:
        sbody = "".join(f'<p>{span("sidebar.body", line)}</p>' for line in receipt.sidebar_body)
        secondary = (
            f'{_photo_box(height="34mm")}'
            f'<div class="cap">{span("caption", receipt.sidebar_caption)}</div>'
            f'<h4>{span("headline", receipt.sidebar_headline)}</h4>'
            f'<div class="body">{sbody}</div>'
            f'<div class="jump">{span("jump", receipt.sidebar_jump)}</div>'
        )
    rail = f'<div class="rail">{box}{secondary}</div>'

    bottom = ""
    if receipt.bottom_stories:
        cols = "".join(
            '<div class="s">'
            f'{_photo_box(height="26mm")}'
            f'<div class="cap">{span("bottom.caption", story.caption)}</div>'
            f'<h3>{span("bottom.headline", story.headline)}</h3>'
            '<div class="body">'
            + "".join(f'<p>{span("bottom.body", line)}</p>' for line in story.body)
            + '</div>'
            f'<div class="jump">{span("jump", story.jump_line)}</div></div>'
            for story in receipt.bottom_stories
        )
        bottom = f'<div class="bottom">{cols}</div>'

    footer = (f'<div class="colophon">{span("footer", receipt.footer_line)}'
             f'<span>{span("page_no", receipt.page_no, "pg")}</span></div>')

    body_html = flag + teasers + f'<div class="grid">{lead}{rail}</div>' + bottom + footer
    css = """
#sheet{padding:12mm 13mm 10mm;position:relative;}
.flag{display:grid;grid-template-columns:56mm 1fr 56mm;align-items:center;gap:6mm;
      border-bottom:.35mm solid #111;padding-bottom:2.5mm;}
.ear{font-size:8.5pt;line-height:1.5;}
.ear.r{text-align:right;}
.ear .d{font-weight:bold;}
.name{text-align:center;}
.name .nm{display:block;font-size:24mm;font-weight:bold;letter-spacing:-1mm;
          line-height:.92;text-transform:uppercase;color:#8a0d14;}
.slogan{font-size:9pt;letter-spacing:2mm;text-transform:uppercase;color:#333;margin-top:1.5mm;}
.rule{height:1.6mm;background:#111;margin-top:1.6mm;}
.teasers{display:grid;grid-template-columns:repeat(3,1fr);gap:6mm;padding:3mm 0;
         border-bottom:.35mm solid #111;}
.teasers .t{display:grid;grid-template-columns:26mm 1fr;gap:3mm;}
.teasers .k{font-size:7.4pt;letter-spacing:.9mm;text-transform:uppercase;color:#8a0d14;}
.teasers h4{font-size:11pt;line-height:1.2;margin-top:1mm;}
.teasers p{font-size:8.6pt;line-height:1.35;color:#444;margin-top:1mm;}
.grid{display:grid;grid-template-columns:repeat(6,1fr);gap:0 5mm;padding-top:4mm;}
.lead{grid-column:1 / 5;padding-right:4mm;border-right:.25mm solid #999;}
.rail{grid-column:5 / 7;}
.kicker{font-size:9.5pt;letter-spacing:1.6mm;text-transform:uppercase;color:#8a0d14;
        margin-bottom:2mm;}
.head{font-size:19mm;line-height:.98;letter-spacing:-.6mm;font-weight:bold;margin:0;}
.deck{font-size:14pt;line-height:1.35;color:#333;font-style:italic;margin-top:3mm;}
.byline{font-size:8.6pt;letter-spacing:.5mm;text-transform:uppercase;margin:3mm 0 2.5mm;
        padding:1.2mm 0;border-top:.25mm solid #111;border-bottom:.25mm solid #111;}
.lead .ph{margin-bottom:1mm;}
.lead .body{column-count:3;column-gap:5mm;column-rule:.2mm solid #bbb;margin-top:3mm;}
.rail .body{column-count:2;column-gap:5mm;column-rule:.2mm solid #bbb;margin-top:2mm;}
.body p{font-size:9pt;line-height:1.45;text-align:justify;margin-bottom:1.6mm;}
.jump{font-size:8.6pt;font-style:italic;color:#8a0d14;margin-top:1mm;}
.cap{font-size:8pt;line-height:1.4;color:#333;padding-top:1.2mm;border-top:.2mm solid #999;
     margin-top:1.5mm;}
.rail .box{border:.5mm solid #111;padding:3mm;margin-bottom:4mm;background:#efe9db;}
.rail .box h3{font-size:10pt;letter-spacing:1.2mm;text-transform:uppercase;
              border-bottom:.35mm solid #111;padding-bottom:1.4mm;margin:0 0 2mm;}
.rail .box ul{list-style:none;margin:0;padding:0;}
.rail .box li{font-size:9pt;line-height:1.35;padding:1.8mm 0;border-bottom:.2mm dotted #999;}
.rail .box li:last-child{border-bottom:0;}
.rail .box li .l{display:block;font-size:7.4pt;letter-spacing:.6mm;text-transform:uppercase;
                 color:#8a0d14;margin-bottom:.6mm;}
.rail h4{font-size:16pt;line-height:1.1;margin:2.5mm 0 1.5mm;}
.bottom{border-top:1.2mm solid #111;margin-top:5mm;padding-top:4mm;
        display:grid;grid-template-columns:1fr 1fr;gap:0 8mm;}
.bottom .s:first-child{padding-right:4mm;border-right:.25mm solid #999;}
.bottom h3{font-size:20pt;line-height:1.08;margin-bottom:2mm;}
.bottom .body{column-count:2;column-gap:5mm;column-rule:.2mm solid #bbb;}
.colophon{position:absolute;left:13mm;right:13mm;bottom:4mm;border-top:.25mm solid #111;
          padding-top:1.6mm;display:flex;justify-content:space-between;font-size:7.6pt;
          color:#444;}
.ph{position:relative;background:
    radial-gradient(circle at 50% 50%, rgba(0,0,0,.45) 0 .3mm, transparent .31mm) 0 0/1mm 1mm,
    linear-gradient(150deg,#c9c6bc 0%,#8e8b83 50%,#544f46 100%);}
.ph .phl{position:absolute;right:1.5mm;bottom:1.2mm;font-family:'DejaVuSans','LiberationSans',
         'DejaVu Sans',sans-serif;font-size:6.4pt;letter-spacing:.8mm;color:rgba(255,255,255,.85);}
"""
    return base.document(body_html, css, paper="BROADSHEET", padding="12mm 13mm 10mm",
                         font=base.SERIF, size="9pt", colour="#111", line_height="1.35")


# --------------------------------------------------------------- classifieds


def _classifieds(receipt) -> str:
    header = (
        f'<div class="running"><div class="sec">{span("section", receipt.section)}</div>'
        f'<div class="meta">{span("issue_date", receipt.issue_date)} · '
        f'{span("masthead", receipt.masthead)} · '
        f'{span("page_no", receipt.page_no, "pg")}</div></div>'
        '<div class="rate">'
        f'<span>{span("rate", receipt.rate_line_1)}</span>'
        f'<span>{span("rate", receipt.rate_line_2)}</span></div>'
    )

    def ad_html(ad) -> str:
        if ad.heading:
            return (f'<div class="ad boxed"><div class="h">{span("ad.heading", ad.heading)}</div>'
                    f'{span("ad.body", ad.body)}<span class="tel">{span("ad.phone", ad.phone)}'
                    f'</span></div>')
        lead = f'<b>{span("ad.lead", ad.lead_in)}</b> ' if ad.lead_in else ""
        return (f'<div class="ad">{lead}{span("ad.body", ad.body)}'
                f'<span class="tel">{span("ad.phone", ad.phone)}</span></div>')

    blocks = []
    for index, category in enumerate(receipt.categories):
        cls = "cat first" if index == 0 else "cat"
        blocks.append(f'<div class="{cls}">{span("category", category.name)}</div>')
        blocks.extend(ad_html(ad) for ad in category.ads)
    for notice in receipt.notices:
        body = "".join(f'<p>{span("notice.body", line)}</p>' for line in notice.body)
        signed = f'<div class="sg">{span("notice.signed", notice.signed)}</div>' if notice.signed else ""
        blocks.append(f'<div class="notice"><div class="t">{span("notice.title", notice.title)}'
                      f'</div>{body}{signed}</div>')
    for obituary in receipt.obituaries:
        body = "".join(f'<p>{span("obit.body", line)}</p>' for line in obituary.body)
        blocks.append(
            f'<div class="obit"><div class="t">{span("obit.title", obituary.title)}</div>'
            f'<div class="nm">{span("obit.name", obituary.name)}</div>{body}</div>'
        )
    if receipt.condolence:
        blocks.append(f'<div class="ad">{span("condolence", receipt.condolence)}</div>')

    footer = ""
    if receipt.footer_disclaimer:
        footer = f'<div class="foot"><span>{span("footer", receipt.footer_disclaimer)}</span></div>'

    body_html = f'<div class="page">{header}<div class="cols">{"".join(blocks)}</div>{footer}</div>'
    css = """
#sheet{padding:10mm 10mm 8mm;}
/* `.cols` below is `column-fill:auto` (fills column 1 top-to-bottom before
   starting column 2, like a real classifieds page) rather than the spec
   default `balance`. Chromium only sequences `auto` fill against a
   *definite* height -- `#sheet`'s own height is deliberately just a floor
   (see base.document()'s docstring), which is never "definite" for this
   purpose, so without a genuinely fixed height somewhere, every ad piles
   into column 1 alone, however tall that makes the page (confirmed by
   rendering: 18 ads still 0 overflow but 1 of 6 columns used). `.page`
   gives the header+rate+cols+footer stack that fixed height instead --
   412mm = TABLOID's 430mm minus the 10mm top / 8mm bottom padding passed
   to base.document() below; keep this in sync with both. */
.page{height:412mm;display:flex;flex-direction:column;}
.running{display:flex;justify-content:space-between;align-items:baseline;
         border-bottom:1.2mm solid #111;padding-bottom:1.6mm;}
.running .sec{font-size:15pt;font-weight:bold;letter-spacing:2.6mm;text-transform:uppercase;}
.running .meta{font-size:6.6pt;color:#444;}
.rate{border:.4mm solid #111;font-size:6.6pt;padding:1.6mm 2.4mm;margin:3mm 0;display:flex;
      justify-content:space-between;gap:6mm;background:#eae5d8;}
.cols{flex:1;min-height:0;column-count:6;column-gap:4mm;column-rule:.2mm solid #b5b0a2;
      column-fill:auto;}
.cat{break-inside:avoid;break-after:avoid;background:#111;color:#fff;font-size:7.4pt;
     font-weight:bold;letter-spacing:1mm;text-transform:uppercase;padding:1.2mm 1.8mm;
     margin:3.5mm 0 1.8mm;}
.cat.first{margin-top:0;}
.ad{break-inside:avoid;font-size:6.8pt;line-height:1.36;padding:1.4mm 0;
    border-bottom:.2mm dotted #a9a496;text-align:justify;}
.ad .tel{display:block;font-weight:bold;margin-top:.5mm;}
.ad.boxed{border:.4mm solid #111;padding:1.8mm;background:#fff;margin:1.4mm 0;}
.ad.boxed .h{font-size:8.4pt;font-weight:bold;text-transform:uppercase;margin-bottom:1mm;
             border-bottom:.25mm solid #111;padding-bottom:.8mm;}
.notice{break-inside:avoid;border:.35mm double #111;padding:2.2mm;margin:2mm 0;font-size:6.6pt;
        line-height:1.4;background:#fff;}
.notice .t{text-align:center;font-weight:bold;text-transform:uppercase;letter-spacing:.7mm;
           font-size:7.4pt;margin-bottom:1.4mm;}
.notice p{text-align:justify;margin-bottom:1mm;}
.notice .sg{text-align:right;font-style:italic;}
.obit{break-inside:avoid;border:1mm solid #111;padding:2.6mm;margin:2mm 0;background:#fff;
      text-align:center;}
.obit .t{font-size:8pt;font-weight:bold;letter-spacing:1.4mm;text-transform:uppercase;
         margin-bottom:1.6mm;}
.obit .nm{font-family:'LiberationSerif','DejaVu Serif',serif;font-size:12pt;font-weight:bold;
          line-height:1.2;}
.obit p{font-size:6.6pt;line-height:1.4;margin-top:1.4mm;text-align:center;}
.foot{border-top:.3mm solid #111;padding-top:2mm;font-size:6.6pt;color:#444;margin-top:3mm;}
"""
    return base.document(body_html, css, paper="TABLOID", padding="10mm 10mm 8mm",
                         font=base.SANS, size="6.8pt", colour="#111", line_height="1.42")


# ------------------------------------------------------------------------ toc


def _toc(receipt) -> str:
    header = (f'<header><h1>{span("title", "Mục lục")}</h1><div class="meta">'
             f'{span("masthead", receipt.masthead)}<b>{span("issue_label", receipt.issue_label)}'
             f'</b></div></header>')

    hero = (
        '<div class="hero">'
        f'{_photo_box(height="56mm")}<div>'
        f'<div class="k">{span("hero.kicker", receipt.hero_kicker)}</div>'
        f'<div class="n">{span("hero.page_no", receipt.hero_page_no, "n")}</div>'
        f'<h2>{span("hero.headline", receipt.hero_headline)}</h2>'
        f'<p>{span("hero.teaser", receipt.hero_teaser)}</p>'
        f'<div class="by">{span("hero.byline", receipt.hero_byline)}</div>'
        '</div></div>'
    )

    def entry_html(entry) -> str:
        return (f'<div class="it"><span class="pg">{span("entry.page_no", entry.page_no)}</span>'
                f'<div><h3>{span("entry.title", entry.title)}</h3>'
                f'<p>{span("entry.teaser", entry.teaser)}</p></div></div>')

    columns = ["", ""]
    for index, section in enumerate(receipt.sections):
        entries = "".join(entry_html(entry) for entry in section.entries)
        block = (f'<div class="sec"><div class="h">{span("section.name", section.name)}</div>'
                f'{entries}</div>')
        columns[index % 2] += block
    cols = (f'<div class="cols"><div class="col">{columns[0]}</div>'
           f'<div class="col">{columns[1]}</div></div>')

    footer = (f'<div class="foot"><span>{span("footer_left", receipt.footer_left)}</span>'
             f'<span>{span("footer_right", receipt.footer_right)}</span></div>')

    body_html = header + hero + cols + footer
    css = """
#sheet{padding:14mm 14mm 12mm;display:flex;flex-direction:column;}
header{display:flex;justify-content:space-between;align-items:flex-end;gap:8mm;
       border-bottom:1mm solid #1c1b18;padding-bottom:3mm;}
header h1{font-family:'LiberationSerif','DejaVu Serif',serif;font-size:16mm;font-weight:bold;letter-spacing:-.6mm;
          line-height:.9;text-transform:uppercase;}
header .meta{text-align:right;font-size:7.4pt;letter-spacing:1.2mm;text-transform:uppercase;
             color:#6a6558;line-height:1.8;}
header .meta b{display:block;font-family:'LiberationSerif','DejaVu Serif',serif;font-size:13pt;letter-spacing:0;
               text-transform:none;color:#1c1b18;}
.hero{display:grid;grid-template-columns:1fr 62mm;gap:7mm;padding:6mm 0;
      border-bottom:.3mm solid #cfc8b8;}
.hero .n{font-family:'LiberationSerif','DejaVu Serif',serif;font-size:24mm;font-weight:bold;line-height:.85;color:#b8532f;}
.hero .k{font-size:6.8pt;letter-spacing:1.6mm;text-transform:uppercase;color:#b8532f;
         margin-bottom:1.6mm;}
.hero h2{font-family:'LiberationSerif','DejaVu Serif',serif;font-size:9.4mm;line-height:1.08;margin:0 0 2.5mm;}
.hero p{font-size:8.8pt;line-height:1.5;color:#4a463c;}
.hero .by{font-size:7.2pt;letter-spacing:.8mm;text-transform:uppercase;color:#6a6558;
          margin-top:2.5mm;}
.cols{flex:1;min-height:0;display:grid;grid-template-columns:1fr 1fr;gap:0 8mm;padding-top:5mm;}
.col+.col{border-left:.25mm solid #cfc8b8;padding-left:8mm;}
.sec{margin-bottom:5mm;}
.sec .h{font-size:7.4pt;letter-spacing:2.2mm;text-transform:uppercase;color:#b8532f;
        border-bottom:.35mm solid #1c1b18;padding-bottom:1.4mm;margin-bottom:2.5mm;}
.it{display:grid;grid-template-columns:11mm 1fr;gap:3mm;padding:2.2mm 0;
    border-bottom:.2mm dotted #b9b1a0;align-items:baseline;}
.it:last-child{border-bottom:0;}
.it .pg{font-family:'LiberationSerif','DejaVu Serif',serif;font-size:17pt;font-weight:bold;color:#b8532f;line-height:1;}
.it h3{font-family:'LiberationSerif','DejaVu Serif',serif;font-size:12.5pt;line-height:1.2;margin:0 0 .8mm;}
.it p{font-size:7.6pt;line-height:1.4;color:#5c574c;margin:0;}
.foot{border-top:.3mm solid #1c1b18;padding-top:2.5mm;display:flex;justify-content:space-between;
      font-size:7pt;letter-spacing:.6mm;color:#6a6558;}
.ph{position:relative;height:56mm;background:
    radial-gradient(circle at 50% 50%, rgba(0,0,0,.42) 0 .24mm, transparent .25mm) 0 0/.85mm .85mm,
    linear-gradient(150deg,#c9c2b2 0%,#8f887a 52%,#544f46 100%);}
.ph .phl{position:absolute;right:1.4mm;bottom:1mm;font-family:'DejaVuSans','LiberationSans','DejaVu Sans',sans-serif;font-size:6pt;
         letter-spacing:.7mm;color:rgba(255,255,255,.8);}
"""
    return base.document(body_html, css, paper="A4", padding="14mm 14mm 12mm",
                         font=base.SANS, size="8.4pt", colour="#1c1b18", line_height="1.3")


# ------------------------------------------------------------------------- qa


def _qa(receipt) -> str:
    header = (
        f'<div class="top">{_photo_box(height="118mm", label="ẢNH CHÂN DUNG")}'
        '<div class="veil"></div><div class="id">'
        f'<div class="sec">{span("section", receipt.section)}</div>'
        f'<h1>{span("headline", receipt.headline)}</h1>'
        f'<div class="who">{span("subject_name", receipt.subject_name)} · '
        f'{span("subject_role", receipt.subject_role)}</div></div></div>'
    )

    deck_byline = (
        f'<div class="deck">{span("deck", receipt.deck)}</div>'
        f'<div class="byline"><span>{span("byline_by", receipt.byline_by)}</span>'
        f'<span>{span("byline_photo", receipt.byline_photo)}</span></div>'
    )

    bio = ""
    if receipt.bio_rows:
        rows = "".join(
            f'<div class="r"><b>{span("bio.year", row.year)}</b>'
            f'<span>{span("bio.text", row.text)}</span></div>'
            for row in receipt.bio_rows
        )
        bio = f'<div class="bio"><h4>{span("bio_title", receipt.bio_title)}</h4>{rows}</div>'

    pull = (f'<div class="pull">{span("pull_quote", receipt.pull_quote)}</div>'
           if receipt.pull_quote else "")

    pairs_html = []
    for index, pair in enumerate(receipt.qa_pairs):
        pairs_html.append(f'<p class="q">{span("qa.question", pair.question)}</p>')
        pairs_html.append(f'<p class="a">{span("qa.answer", pair.answer)}</p>')
        if index == 2 and pull:
            pairs_html.append(pull)
            pull = ""
        if index == 1 and bio:
            pairs_html.append(bio)
            bio = ""
    qa_html = f'<div class="qa">{"".join(pairs_html)}{pull}{bio}</div>'

    footer = (f'<div class="foot"><span>{span("footer_note", receipt.footer_note)}</span>'
             f'<span>{span("footer_right", receipt.footer_right)}</span></div>')

    body_html = f'<main>{header}{deck_byline}{qa_html}</main>{footer}'
    css = """
#sheet{display:flex;flex-direction:column;padding:0;}
.top{position:relative;height:118mm;flex:0 0 auto;}
.top .ph{position:absolute;inset:0;height:auto;}
.top .veil{position:absolute;left:0;right:0;bottom:0;height:78mm;
           background:linear-gradient(180deg,rgba(0,0,0,0),rgba(0,0,0,.8) 76%);}
.top .id{position:absolute;left:16mm;right:16mm;bottom:9mm;color:#fff;}
.top .sec{font-size:7pt;letter-spacing:2.6mm;text-transform:uppercase;color:#f0c96a;
          margin-bottom:3mm;}
.top h1{font-family:'LiberationSerif','DejaVu Serif',serif;font-size:15mm;line-height:1.02;font-weight:bold;
        letter-spacing:-.5mm;}
.top .who{font-size:8.4pt;letter-spacing:.8mm;margin-top:3mm;color:rgba(255,255,255,.85);}
main{flex:1;min-height:0;padding:8mm 16mm 0;display:flex;flex-direction:column;}
.deck{font-family:'LiberationSerif','DejaVu Serif',serif;font-size:11.6pt;line-height:1.42;font-style:italic;color:#4a463c;
      border-left:1.2mm solid #8a3324;padding-left:5mm;margin-bottom:5mm;}
.byline{display:flex;justify-content:space-between;font-size:7.2pt;letter-spacing:1mm;
        text-transform:uppercase;color:#6a6558;border-top:.25mm solid #1c1b18;
        border-bottom:.25mm solid #1c1b18;padding:1.6mm 0;margin-bottom:5mm;}
.qa{column-count:2;column-gap:8mm;column-rule:.2mm solid #cfc8b8;flex:1;min-height:0;
    font-family:'LiberationSerif','DejaVu Serif',serif;}
.qa .q{font-family:'DejaVuSans','LiberationSans','DejaVu Sans',sans-serif;font-weight:bold;font-size:9pt;line-height:1.38;color:#8a3324;
       margin:0 0 1.6mm;break-after:avoid;}
.qa .q::before{content:"— ";}
.qa .a{font-size:9pt;line-height:1.5;text-align:justify;margin-bottom:4mm;}
.pull{break-inside:avoid;margin:4mm 0;padding:3.5mm 0;border-top:.8mm solid #8a3324;
      border-bottom:.8mm solid #8a3324;font-size:13pt;line-height:1.3;font-style:italic;
      color:#8a3324;}
.bio{break-inside:avoid;background:#efe9db;padding:3.5mm 4mm;margin:4mm 0;
     font-family:'DejaVuSans','LiberationSans','DejaVu Sans',sans-serif;}
.bio h4{font-size:7.2pt;letter-spacing:1.6mm;text-transform:uppercase;color:#8a3324;
        border-bottom:.3mm solid #8a3324;padding-bottom:1.2mm;margin:0 0 2mm;}
.bio .r{display:grid;grid-template-columns:14mm 1fr;gap:2.5mm;font-size:7.2pt;line-height:1.45;
        padding:.9mm 0;border-bottom:.2mm dotted #b9b1a0;}
.bio .r:last-child{border-bottom:0;}
.bio .r b{color:#8a3324;}
.foot{padding:3mm 16mm 8mm;display:flex;justify-content:space-between;font-family:'DejaVuSans','LiberationSans','DejaVu Sans',sans-serif;
      font-size:6.6pt;letter-spacing:1mm;color:#6a6558;border-top:.25mm solid #cfc8b8;
      margin-top:4mm;}
.ph{position:relative;background:
    radial-gradient(circle at 50% 50%, rgba(0,0,0,.35) 0 .22mm, transparent .23mm) 0 0/.8mm .8mm,
    linear-gradient(150deg,#c6bfaf 0%,#8d8678 50%,#4e4a42 100%);}
.ph .phl{position:absolute;right:3mm;bottom:2mm;font-family:'DejaVuSans','LiberationSans','DejaVu Sans',sans-serif;font-size:6.4pt;
         letter-spacing:1mm;color:rgba(255,255,255,.8);}
"""
    return base.document(body_html, css, paper="A4", padding="0",
                         font=base.SERIF, size="9pt", colour="#1c1b18", line_height="1.3")


# ---------------------------------------------------------------- dispatch

_COMPOSITIONS = {
    "lead_sidebar": _lead_sidebar,
    "classifieds": _classifieds,
    "toc": _toc,
    "qa_pairs": _qa,
}


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    """The whole page, for whichever of the four compositions this layout is.

    `spec.get("composition")` is the same tag `rulebase.periodical.build()`
    reads off the document's own params to build `receipt` in the first
    place -- one composition tag, stated on both the document (which
    content shape to build) and the layout (which markup to dress it in),
    the same redundant-on-purpose pattern `blanks.yaml` already uses for
    "this layout is deliberately meant for this document."
    """
    composition = spec.get("composition")
    renderer = _COMPOSITIONS.get(composition)
    if renderer is None:
        raise KeyError(
            f"unknown periodical composition {composition!r}; "
            f"have {', '.join(sorted(_COMPOSITIONS))}"
        )
    return renderer(receipt)


__all__ = ["build"]
