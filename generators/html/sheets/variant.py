"""The dressing an agent puts on a sheet, and the line it may not cross.

A layout is a phôi: which columns exist, in what order, how wide. A *variant*
is what a print shop does to that phôi without redrawing it -- heavier rules,
a tinted header band, a different type stack, a corner flourish. Two shops
issuing the same statutory form produce pages that no model should read as the
same picture, and that difference is the whole reason this module exists.

    markup = variant.apply(family.build(...), recipe)

**What a variant may change: paint. What it may not: geometry that carries a
label.** Every box in the record is measured off the laid-out DOM, so a rule
that moves text moves its box with it and stays honest. Two rules do not, and
they are the reason this is a curated stylesheet fragment rather than free CSS:

* `text-transform` -- the DOM keeps the original string while the pixels show
  another, so the label would describe text the page does not print. Not used
  here, and `forbidden()` names it so a generated variant cannot smuggle it in.
* `content:` on a pseudo-element carrying words -- text with no box at all.

Everything else is fair game, and the decorative marks below are drawn on
`#sheet::before` / `#sheet::after`, which are out of flow: they add ink without
moving a single run. `#sheet` is already `position:relative;overflow:hidden`
in `base.document`, so they clip to the paper.

The CSS is appended after the family's own, inside the same `<style>`, so it
wins ties by document order without needing `!important` -- which would be a
sledgehammer that later stages could not undo.
"""

from __future__ import annotations

import re

CLOSE = "</style>"

# Declarations a variant must never carry. Checked rather than trusted: the
# catalogue is generated, an agent may extend it, and the failure these cause
# is a label that disagrees with its pixels -- silent, and fatal to the set.
FORBIDDEN = (
    "text-transform",
    "display:none",
    "visibility:hidden",
    "font-size:0",
)

# `content` is the one that needs looking at rather than matching. An empty
# string is how a decorative pseudo-element is switched on at all -- every mark
# in `agent/variants.py` needs it -- while a `content` carrying words puts
# glyphs on the page that no box describes and no label mentions. So the
# property is allowed and its value is not.
CONTENT = re.compile(r"content\s*:\s*([^;}]*)", re.IGNORECASE)
EMPTY_CONTENT = {"''", '""', "none", "normal"}


def forbidden(css: str) -> list[str]:
    """Declarations in `css` that would break the label/pixel contract."""
    flat = re.sub(r"\s+", "", css).lower()
    found = [name for name in FORBIDDEN
             if re.sub(r"\s+", "", name).lower() in flat]
    found += [f"content:{value.strip()}" for value in CONTENT.findall(css)
              if value.strip().lower() not in EMPTY_CONTENT]
    return found


def chosen(recipe):
    """The `variant` option this recipe drew, or None when it drew none.

    `Recipe.__getattr__` raises for an attribute the rules do not define, and
    the shipped rules do not define this one -- a run adds it by materialising
    its own rules root. So every reader goes through here and a sheet drawn
    from the shipped rules is unchanged, which is what keeps the committed
    datasets reproducible.
    """
    return (getattr(recipe, "choices", None) or {}).get("variant")


def css_of(recipe) -> str:
    option = chosen(recipe)
    return str((getattr(option, "params", None) or {}).get("css") or "")


def moves_of(recipe) -> tuple:
    option = chosen(recipe)
    raw = (getattr(option, "params", None) or {}).get("moves") or ()
    return tuple(tuple(move) for move in raw)


def restructure(spec: dict, recipe) -> dict:
    """The layout spec with this variant's block moves applied to `sections`.

    `sections:` is the list every sheet family loops over to decide which block
    of the phôi comes next, so reordering it is the one thing a variant can do
    that is a change of *layout* rather than of paint. Five of the six families
    read it and eleven of the sixteen layouts declare it.

    A move naming a block this layout does not have is a no-op, which is what
    lets one dressing be worn by a hotel folio and a hospital bill alike. The
    list is copied before it is touched: `load_layout` re-reads the YAML per
    call today, and a mutation that relied on that would break silently the day
    somebody put an `lru_cache` on it.
    """
    moves = moves_of(recipe)
    sections = list(spec.get("sections") or ())
    if not moves or not sections:
        return spec
    for move in moves:
        if len(move) != 3:
            raise ValueError(f"a section move is (kind, block, anchor), got {move!r}")
        kind, block, anchor = move
        if block not in sections or anchor not in sections or block == anchor:
            continue
        if kind == "swap":
            here, there = sections.index(block), sections.index(anchor)
            sections[here], sections[there] = sections[there], sections[here]
        elif kind in ("before", "after"):
            sections.remove(block)
            at = sections.index(anchor) + (1 if kind == "after" else 0)
            sections.insert(at, block)
        else:
            raise ValueError(f"unknown section move {kind!r}; have swap, before, after")
    return {**spec, "sections": sections}


def apply(markup: str, recipe) -> str:
    """The same page, wearing the variant this recipe drew."""
    option = chosen(recipe)
    css = css_of(recipe)
    if not css.strip():
        return markup
    bad = forbidden(css)
    if bad:
        raise ValueError(
            f"variant {getattr(option, 'id', '?')!r} uses {', '.join(bad)}, which "
            f"changes pixels without changing the DOM the boxes are measured off")
    index = markup.find(CLOSE)
    if index < 0:
        return markup
    head = f"\n/* variant: {getattr(option, 'id', '?')} */\n"
    return markup[:index] + head + css + "\n" + markup[index:]


__all__ = ["CLOSE", "FORBIDDEN", "apply", "chosen", "css_of", "forbidden",
           "moves_of", "restructure"]
