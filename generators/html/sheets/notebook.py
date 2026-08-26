"""A school exercise book, kept by hand: ruled paper, biro, no printing at all.

Every other family here draws a document some machine printed, and the person
only ever fills in the blanks -- `statement.py` says so about itself, and
`docs/handwriting-html.md` measures how little of a printed form a hand can
reach. This one inverts that. There is no press run: the shopkeeper ruled the
page by buying the book, and wrote the rest.

That makes it the only page in the set where **the whole of the text is the
handwriting**, which is why it is worth having. A model that has only seen
hand-filled forms has seen handwriting in the two places a form leaves for it;
it has not seen a page where the heading, the labels, the numbers and the total
are all somebody's hand at the same slant.

Three things make it read as a notebook rather than as a font choice:

* **The writing sits on the rules.** The rules are a repeating gradient at the
  same pitch as `line-height`, so a line of writing lands on a line of the page
  instead of floating between two. Get that wrong and it reads as a handwriting
  font on striped paper, which is a different and much less useful image.
* **There is a red margin rule, and the writing respects it.** The body starts
  to the right of it, which is what a Vietnamese exercise book looks like when
  somebody is keeping a ledger rather than writing prose -- the margin is where
  the date or a running number goes, and it is left empty here because this
  page has neither.
* **Every line is nudged.** A hand does not return to the same x, and it drifts
  off the horizontal over a line. Each line gets a small offset and rotation
  from the page's own seed, so the same seed writes the same page.

The label contract is the shared one: the values are `span()`s with the same
`kind` they carry on a printed sheet, so a reader of the boxes cannot tell the
difference and does not have to.

Drawn on its own this family sets the page in a handwriting **typeface**, which
is the cheap end of the trade and repeats: one face is one hand, the same `a`
every time. `--handwriting both` is the expensive end -- `HAND_KINDS` below
tells `handwriting.fill` that every run here is a person's to write, and the
WriteViT checkpoint then takes whatever it can of them. On a sales book that is
about 8 %, because a ledger is amounts and dates; the rest stays typeface. See
`docs/handwriting-html.md` for what that costs and what it does not buy.
"""

from __future__ import annotations

import random

from . import base
from .base import EVERY_RUN, Rows, span

# Which runs a pen reaches on this page: all of them.
#
# Every other family here leaves `handwriting.HAND_KINDS` alone, and that is
# the right answer for a printed form -- a letterhead and a column title were
# printed before anybody picked up a pen. This page has no press run at all, so
# a heading left in type would be a heading nobody typed. `sheets.hand_kinds`
# reads this and `handwriting.fill` honours it.
HAND_KINDS = EVERY_RUN

# The faces in `fonts/hand/`, by the family name `page.font_faces` gives them
# (the file stem, minus `-Regular`). Listed rather than globbed so a face
# arriving in the directory does not silently change every page in the set.
HANDS = ("IndieFlower", "PatrickHand")

# Biro and gel, as people actually buy them. Not black: a black pen on a scan
# is nearly the same pixel as printing, and the point of this page is that a
# reader can tell.
INKS = ("#1c2f6b", "#16225a", "#232323", "#2a1e5c", "#123a2e")

# The pitch of the ruling, and the two paper tints a cheap exercise book comes
# in. `RULE_MM` is also the line-height: see the module docstring.
RULE_MM = 8.2
PAPERS = ("#fdfcf5", "#fbfaf2", "#fcfbf6")
RULE_COLOUR = "#9fb6d6"
MARGIN_COLOUR = "#d08a90"


def _line(rng: random.Random, text: str, kind: str, classes: str = "") -> str:
    """One written line, nudged off true the way a hand leaves it."""
    shift = rng.uniform(-1.1, 1.1)
    tilt = rng.uniform(-0.5, 0.5)
    size = rng.uniform(0.97, 1.05)
    style = (f"margin-left:{shift:.2f}mm;transform:rotate({tilt:.2f}deg);"
             f"font-size:{size:.3f}em;")
    return (f'<div class="ln {classes}" style="{style}">'
            f'{span(kind, text)}</div>')


def _written(rng: random.Random, left: str, right: str, classes: str = "") -> str:
    """A line of already-marked-up halves, the right one against the margin."""
    shift = rng.uniform(-0.9, 0.9)
    tilt = rng.uniform(-0.45, 0.45)
    style = f"margin-left:{shift:.2f}mm;transform:rotate({tilt:.2f}deg);"
    return (f'<div class="ln row {classes}" style="{style}">'
            f'<span class="l">{left}</span><span class="r">{right}</span></div>')


def _entry(rng: random.Random, left: str, right: str,
           left_kind: str, right_kind: str, classes: str = "") -> str:
    """A label and its value, the value pushed to the right margin.

    The two halves are separate `span()`s, so the label and its value are two
    boxes rather than one wide one -- which is what a reader of the labels
    expects from every other family here.
    """
    return _written(rng, span(left_kind, left), span(right_kind, right), classes)


def build(recipe, receipt, spec: dict, parse: dict) -> str:
    rng = random.Random(recipe.seed ^ 0x4E4F)
    Rows()                       # no <table> on this page: a book has no columns

    hand = HANDS[rng.randrange(len(HANDS))]
    ink = INKS[rng.randrange(len(INKS))]
    paper = PAPERS[rng.randrange(len(PAPERS))]
    store = parse.get("store") or {}

    lines: list[str] = []
    if store.get("name"):
        lines.append(_line(rng, store["name"], "store.name", "title"))
    # Every store key the label can carry, not a chosen few: a value in the
    # ground truth with no run on the page is a box a reader is promised and
    # does not get. `tests/test_sheets.py` is what caught `branch` missing.
    for key in ("branch", "address", "address2", "phone", "tax_code", "website"):
        if store.get(key):
            lines.append(_line(rng, store[key], f"store.{key}", "small"))
    if parse.get("title"):
        lines.append(_line(rng, parse["title"], "title", "doc"))

    for label, value in list(getattr(receipt, "meta", []) or []):
        lines.append(_entry(rng, label, value, "meta.label", "meta.value", "small"))

    lines.append('<div class="ln sep"></div>')

    # The basket, one item to a line, the amount against the right margin --
    # which is how a ledger kept by hand is laid out and why it needs no table.
    #
    # The quantity and the unit price are written into the line the way a
    # person writes them, `3 x 27.000`, rather than given columns. They are
    # separate `span()`s all the same, because the label carries them
    # separately and a value in the label with no run on the page is a box a
    # reader is promised and does not get -- which `tests/test_sheets.py`
    # caught twice while this family was being written.
    for item in parse.get("menu") or []:
        left = span("menu.name", item.get("nm", ""))
        weight = str(item.get("weight", "") or "").strip()
        rate = str(item.get("unitprice_per_unit", "") or "").strip()
        if weight:
            # Loose goods are weighed, and the book carries both the weight and
            # the price per kilo -- `1,688 KG x 160,500`, which is exactly how
            # somebody writes it before working out the line.
            left += " " + span("menu.weight", weight)
            if rate:
                left += " x " + span("menu.unitprice_per_unit", rate)
        qty = str(item.get("cnt", "") or "").strip()
        unit = str(item.get("unitprice", "") or "").strip()
        if qty and qty != "1":
            left += " " + span("menu.qty", qty)
            if unit:
                left += " x " + span("menu.unit_price", unit)
        elif unit and unit != item.get("price"):
            left += " @ " + span("menu.unit_price", unit)
        lines.append(_written(rng, left, span("menu.amount", item.get("price", ""))))

    lines.append('<div class="ln sep"></div>')

    entries = list((parse.get("total") or {}).items())
    for index, (label, value) in enumerate(entries):
        grand = index == len(entries) - 1
        lines.append(_entry(rng, label, value,
                            "total.grand.label" if grand else "total.line.label",
                            "total.grand" if grand else "total.line",
                            "grand" if grand else ""))

    # All of the footer, not the first two: the same promise as the store keys.
    for line in (parse.get("footer") or []):
        if line:
            lines.append(_line(rng, line, "note", "small"))

    # The punched holes are drawn, not photographed: three of them, down the
    # left, inside the margin the red rule marks.
    holes = "".join(f'<div class="hole" style="top:{top}mm"></div>'
                    for top in (58, 148, 238))

    body = holes + '<div class="page">' + "".join(lines) + "</div>"

    css = f"""
#sheet{{
  padding:14mm 12mm 12mm 26mm;
  background:
    linear-gradient(to bottom, transparent {RULE_MM - 0.25}mm,
                    {RULE_COLOUR} {RULE_MM - 0.25}mm, {RULE_COLOUR} {RULE_MM}mm)
      0 14mm / 100% {RULE_MM}mm repeat-y,
    {paper};
}}
.page{{position:relative;}}
.ln{{
  height:{RULE_MM}mm;line-height:{RULE_MM}mm;
  white-space:nowrap;overflow:hidden;transform-origin:left center;
}}
.ln.row{{display:flex;justify-content:space-between;align-items:baseline;}}
.ln .l{{overflow:hidden;text-overflow:clip;padding-right:3mm;}}
.ln .r{{flex:0 0 auto;}}
.ln.title{{font-size:1.5em;line-height:{RULE_MM}mm;}}
.ln.doc{{font-size:1.25em;text-decoration:underline;}}
.ln.small{{font-size:.86em;opacity:.9;}}
.ln.grand{{font-size:1.2em;font-weight:bold;}}
.ln.sep{{position:relative;}}
.ln.sep::after{{
  content:"";position:absolute;left:0;right:22%;top:50%;
  border-top:.4mm solid {ink};opacity:.75;transform:rotate(-.3deg);
}}
/* The margin rule, and the holes punched inside it. Both belong to the book
   rather than to the writing, so neither carries a box. */
#sheet::before{{
  content:"";position:absolute;top:0;bottom:0;left:21mm;width:.45mm;
  background:{MARGIN_COLOUR};opacity:.85;
}}
.hole{{
  position:absolute;left:7mm;width:5.5mm;height:5.5mm;border-radius:50%;
  background:#eceae0;box-shadow:inset 0 0 0 .3mm #d7d4c8;
}}
"""
    return base.document(
        body, css, paper="A4", padding="14mm 12mm 12mm 26mm",
        # The whole page is the hand: heading, labels, numbers, total.
        font=f"'{hand}','PatrickHand',cursive",
        size="11pt", colour=ink, line_height=f"{RULE_MM}mm")


__all__ = ["HANDS", "HAND_KINDS", "INKS", "MARGIN_COLOUR", "PAPERS",
           "RULE_COLOUR", "RULE_MM", "build"]
