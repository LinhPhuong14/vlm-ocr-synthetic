"""One CSS sheet per layout family, chosen by `recipe.layout.id`.

    from sheets import build, structure_from_markup, labelled_runs
    markup = build(recipe, receipt)

This package replaces the single hard-coded `a4.py`, which drew the same VAT
invoice for all fourteen layouts because it never read the layout at all. The
shape it produces is the shape of the five hand-drawn references in
`samples/invoice-templates/`: ordinary flow, real `<table>`, real `colspan`,
millimetres, one page. Nothing is positioned absolutely, which is what lets the
same markup come out of a browser and out of WeasyPrint looking like the same
document -- and it is why two tables on one sheet have their column edges agree
without anybody computing them.

**A family, not a file per layout.** `invoice_hotel_stay` and
`invoice_hotel_compact` are one document at two sizes; `invoice_vat_form`,
`invoice_vat_summary` and the two utility bills are one printed form with
different columns. What differs between members of a family is read from the
layout file -- `sections:`, `columns:`, `item.rows:` -- so a sixth layout added
to a family is a line in `rules/layout.yaml` and a file in `rulebase/layouts/`,
not a sixth template here.

    layout family      draws                                  reference sheet
    ----------------   ------------------------------------   ----------------------
    statutory          printed form, serial block, 2 signs     invoice_vat_summary
                                                               invoice_export
    lodging            folio: booking block, a row per night   invoice_hotel_stay
                                                               invoice_hotel_compact
    modern             self-designed, totals right-aligned     invoice_brand
    medical            hospital bill: 12 columns, grouped       docs/mau/bang_ke_kcb.html
    statement          a form of fields, no table at all        docs/mau/giay_uy_quyen.html
    till               the thermal roll, so the flag is total  -- (grid is the model)

The box contract is unchanged and is `base.py`'s to keep: every labelled run is
a `<span data-kind="...">`, every `<td>` carries `data-cell`/`data-row`/
`data-col` and its spans. `CELL_RECTS_JS` and `CELL_REGIONS_JS` read those and
know nothing about which family drew the page.
"""

from __future__ import annotations

from html.parser import HTMLParser

from . import form, lodging, medical, modern, periodical, statement, statutory, till
from .base import structure_tokens

# Module name (as it appears in a layout file's own `family:` key) -> the
# module that dresses it. A brand-new family still needs one line here --
# Python has to import the module regardless -- but that is the only
# per-family registration step left; a layout that reuses an existing family
# needs nothing beyond its own `family: <name>` line in `rulebase/layouts/`.
_MODULES = {
    "form": form,
    "lodging": lodging,
    "medical": medical,
    "modern": modern,
    "periodical": periodical,
    "statement": statement,
    "statutory": statutory,
    "till": till,
}

_families_cache: dict | None = None


def _families() -> dict:
    """Layout id -> the module that dresses it, read from each layout's own
    `family:` key and cached.

    Used to be a hand-written dict here, one line per layout -- the exact
    kind of registration this package's own docstring above says a new
    layout should never need. A layout missing a family (an unset or
    unrecognised `family:` key) is still a failure with a list, not a silent
    fall-through to a VAT invoice: drawing a hotel folio as a tax form is
    exactly the defect this package exists to fix.

    Lazy and cached rather than built at import time: `import sheets` should
    not pay for a scan of every file in `rulebase/layouts/` before anyone has
    asked to render a page, and the layout files do not change mid-process.
    """
    global _families_cache
    if _families_cache is None:
        from rulebase import available_layouts, load_layout

        out = {}
        for layout_id in available_layouts():
            name = load_layout(layout_id).get("family")
            if name not in _MODULES:
                raise KeyError(
                    f"{layout_id}: family {name!r} is not one of "
                    f"{', '.join(sorted(_MODULES))}. Set `family:` in "
                    f"rulebase/layouts/{layout_id}.yaml to the module that "
                    "should dress it, adding a new one to sheets._MODULES "
                    "first if it is a genuinely new family."
                )
            out[layout_id] = _MODULES[name]
        _families_cache = out
    return _families_cache


def __getattr__(name: str):
    # PEP 562: makes `sheets.FAMILIES` keep working as a plain dict lookup
    # (`layout in sheets.FAMILIES`, `sheets.FAMILIES[layout]`) for every
    # existing caller and test, without eagerly building it at import time.
    if name == "FAMILIES":
        return _families()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def names() -> list[str]:
    return sorted(_families())


def family_of(layout_id: str):
    try:
        return _families()[layout_id]
    except KeyError:
        raise KeyError(
            f"no CSS sheet for layout {layout_id!r}; have {', '.join(names())}. "
            f"Set `family:` in rulebase/layouts/{layout_id}.yaml to the "
            "family it belongs to."
        ) from None


def build(recipe, receipt, template: str | None = None) -> str:
    """The whole page, for the layout this recipe drew.

    `template` overrides the choice with another layout's dress, which is for
    looking at one sheet on demand -- `--template invoice_brand` -- and not for
    a run. Left None, the layout decides, which is the whole point.
    """
    from rulebase import load_layout

    layout_id = template or recipe.layout.id
    spec = load_layout(layout_id)
    return family_of(layout_id).build(recipe, receipt, spec, receipt.ground_truth())


class _Cells(HTMLParser):
    """Every `<td>`/`<th>` on the page, in document order, with its span.

    For WeasyPrint. The browser measures the laid-out DOM and gets the cell
    rects with it; a PDF has no DOM, so the structure half of the label has to
    come from the markup that was printed. Reading it here rather than
    remembering it while building keeps one source of truth -- the page.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.cells: list[dict] = []

    def handle_starttag(self, tag, attrs):
        if tag not in ("td", "th"):
            return
        attributes = dict(attrs)
        if "data-cell" not in attributes:
            return
        self.cells.append({
            "kind": attributes.get("data-cell", ""),
            "row": int(attributes.get("data-row", 0)),
            "col": int(attributes.get("data-col", 0)),
            "colspan": int(attributes.get("colspan", 1) or 1),
            "rowspan": int(attributes.get("rowspan", 1) or 1),
        })


class _Runs(HTMLParser):
    """`(kind, text)` for every labelled run, in document order.

    The order is what matters: WeasyPrint's PDF carries its text spans in the
    order the markup listed them, so walking the two sequences together gives
    each run the box that drew it without any geometry being guessed at.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.runs: list[tuple[str, str]] = []
        self._kind: str | None = None
        self._buffer: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "span" and "data-kind" in attributes:
            self._flush()
            self._kind = attributes["data-kind"]
            self._depth = 1
            # A hand-filled field carries an <img> of ink and no text node, so
            # its text is on `data-text`. Seeded into the buffer here, the run
            # is recovered in document order like every other one and the PDF
            # path needs no special case of its own.
            if "data-text" in attributes:
                self._buffer.append(attributes["data-text"])
        elif self._kind is not None and tag == "span":
            self._depth += 1

    def handle_endtag(self, tag):
        if self._kind is None or tag != "span":
            return
        self._depth -= 1
        if self._depth <= 0:
            self._flush()

    def handle_data(self, data):
        if self._kind is not None:
            self._buffer.append(data)

    def _flush(self):
        if self._kind is not None:
            text = "".join(self._buffer).strip()
            if text:
                self.runs.append((self._kind, text))
        self._kind, self._buffer, self._depth = None, [], 0

    def close(self):
        super().close()
        self._flush()


def labelled_runs(markup: str) -> list[tuple[str, str]]:
    parser = _Runs()
    parser.feed(markup)
    parser.close()
    return parser.runs


def structure_from_markup(markup: str) -> list[str]:
    """PPStructure tokens for the page, read off the markup that was printed."""
    parser = _Cells()
    parser.feed(markup)
    parser.close()
    rows: dict[int, list[dict]] = {}
    for item in parser.cells:
        rows.setdefault(item["row"], []).append(item)
    ordered = [sorted(rows[row], key=lambda c: c["col"]) for row in sorted(rows)]
    return structure_tokens(ordered)


def cells_from_markup(markup: str) -> list[dict]:
    parser = _Cells()
    parser.feed(markup)
    parser.close()
    return parser.cells


__all__ = [
    "FAMILIES", "build", "cells_from_markup", "family_of", "labelled_runs",
    "names", "structure_from_markup", "structure_tokens",
]
