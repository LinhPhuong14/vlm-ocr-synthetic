"""Turn a `Receipt` plus a layout spec into a grid of cells.

The grid is the contract between the rule-base and the three renderers. A cell
is a piece of text at (row, column range) with an alignment and a relative
size -- deliberately the coarsest description that still pins the text down,
because it has to survive being drawn three different ways:

    synthdog   one TextLayer per cell at row*line_height, col*char_width
    html       one absolutely-positioned span per cell, widths in `ch`
    genalog    the same HTML, printed through WeasyPrint

Columns are counted in characters, not pixels, which is what makes the three
agree: a thermal receipt really is a fixed-width grid, and every layout in
`layouts/*.yaml` was measured off a photograph in those units.

A page is a **sequence of sections**, and which sections in what order is the
layout's to say (`sections:` in the YAML). A till receipt is one particular
sequence -- header, meta, columns, items, totals, footer -- and stays the
default, so the five thermal layouts declare nothing. A VAT invoice is another:
letterhead, title, parties, a ruled table, totals, the amount in words,
signatures. Nothing here knows which is "normal"; both are lists.

Ruled tables are drawn with `+`, `-` and `|` rather than with box-drawing
characters. That is not nostalgia: `pipeline/preflight.py` checks every glyph
this rule-base can print against every font in `fonts/`, and two of those fonts
have no U+2500 block at all -- a frame drawn with `─` would render as a row of
empty boxes in a fifth of the dataset, with the label still claiming a table.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .content import Receipt
from .style import SHEETS
from .text import apply_case, fit, quantity, wrap

LAYOUTS_ROOT = Path(__file__).resolve().parent / "layouts"

SEPARATORS = ["-", "=", "*", ".", "~", "_"]


@dataclass
class Mark:
    """A line, a shaded box or a frame -- everything on a page that is not text.

    On the **same coordinate system as `Cell`**: rows measured in text lines,
    columns in character widths, fractions allowed so a rule can sit between two
    rows rather than on one. That is what makes it general. Every renderer
    already converts (row, column) to pixels in order to place text; a mark
    needs no new machinery in any of them, only the multiplication they are
    already doing.

    This is the seam that lets a printed form stop being drawn out of `+---+`.
    ASCII rules are honest on a thermal till roll, which really does draw them
    with characters, and wrong on an A4 invoice, which is ruled by the printer.
    A layout says which it wants; nothing here decides for it.

    `tone` is a fraction of the page's ink: 1.0 is a full-strength rule, 0.08 a
    shaded table header. `weight` is the line thickness in hairlines, so a
    renderer scales it with its own resolution rather than being handed pixels.
    """

    kind: str                 # 'rule' | 'fill' | 'frame'
    row0: float
    col0: float
    row1: float
    col1: float
    weight: float = 1.0
    tone: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "row0": round(self.row0, 3), "col0": round(self.col0, 3),
            "row1": round(self.row1, 3), "col1": round(self.col1, 3),
            "weight": round(self.weight, 3), "tone": round(self.tone, 3),
        }


@dataclass
class Cell:
    text: str
    role: str                 # where it belongs in the label: 'menu.nm', 'total.grand', ...
    row: int
    col0: int
    col1: int
    align: str = "left"       # left | right | center
    scale: float = 1.0        # relative to the body font size
    bold: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text, "role": self.role, "row": self.row,
            "col0": self.col0, "col1": self.col1,
            "align": self.align, "scale": round(self.scale, 3), "bold": self.bold,
        }


@dataclass
class Grid:
    cells: list[Cell]
    ncols: int
    nrows: int
    layout_id: str
    columns: list[dict[str, Any]] = field(default_factory=list)
    # Non-text primitives, empty for every layout that does not ask for them --
    # which is every thermal receipt, so their pixels are unchanged.
    marks: list[Mark] = field(default_factory=list)
    # The cut sheet this page is printed on, "" for a continuous roll. Names a
    # key of `style.SHEETS`; the renderers turn it into pixels with their own
    # character metrics.
    sheet: str = ""

    def to_dict(self) -> dict[str, Any]:
        out = {
            "layout": self.layout_id,
            "ncols": self.ncols,
            "nrows": self.nrows,
            "cells": [cell.to_dict() for cell in self.cells],
        }
        if self.marks:
            out["marks"] = [mark.to_dict() for mark in self.marks]
        if self.sheet:
            out["sheet"] = self.sheet
        return out


def load_layout(layout_id: str, root: Path | str = LAYOUTS_ROOT) -> dict[str, Any]:
    path = Path(root) / f"{layout_id}.yaml"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in Path(root).glob("*.yaml")))
        raise FileNotFoundError(f"no layout {layout_id!r} in {root}; have {available}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# A layout file may switch itself off with `enabled: false`. Written in the
# layout's own file because that is where a layout already declares everything
# about itself since `family:` moved there -- one place to read, one line to
# change back.
#
# `off:` would be the obvious spelling and is a trap: YAML 1.1 reads a bare
# `off` as the boolean false, so `off: true` parses to `{False: True}` and the
# key silently disappears.
ENABLED_KEY = "enabled"


def is_enabled(name: str, root: Path | str = LAYOUTS_ROOT) -> bool:
    path = Path(root) / f"{name}.yaml"
    if not path.exists():
        return False
    body = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return bool(body.get(ENABLED_KEY, True))


def every(root: Path | str = LAYOUTS_ROOT) -> list[str]:
    """Every layout FILE, switched off ones included.

    What the checks walk: a layout that is off is still committed, still has a
    sheet, still has to build, and `tests/test_sheets.py` still holds it to
    "what the label says the page prints". Off means "no run draws it", not
    "nobody looks at it any more" -- an unwatched file rots, and switching one
    back on should not be an archaeology exercise.
    """
    return sorted(path.stem for path in Path(root).glob("*.yaml"))


def available(root: Path | str = LAYOUTS_ROOT) -> list[str]:
    """Every layout a RUN may draw: the files, minus the ones switched off.

    `pipeline/run.py` takes this list when `run.layouts` is empty, and
    `per_backend: auto` counts it, so switching a layout off removes it from
    every future dataset without anybody editing `pipeline.yaml` -- and without
    deleting the file, which would stop `rulebase.make(force=...)` from
    redrawing the committed pages that already drew it.
    """
    return [name for name in every(root) if is_enabled(name, root)]


class _Builder:
    """Accumulates cells row by row. Every emitter below goes through this."""

    def __init__(self, ncols: int, ruled: bool = False):
        self.ncols = ncols
        self.row = 0
        self.cells: list[Cell] = []
        self.marks: list[Mark] = []
        # `rules: marks` in the layout. Off by default, so every layout that
        # does not ask draws exactly the characters it drew before.
        self.ruled = ruled

    def mark(self, kind, row0, col0, row1, col1, weight=1.0, tone=1.0) -> None:
        # Degenerate on *both* axes is a point: it draws nothing, and a table
        # with no body rows produces one per column boundary. Dropped rather
        # than emitted, so the label never carries a primitive with no extent.
        if row0 == row1 and col0 == col1:
            return
        self.marks.append(Mark(kind, row0, col0, row1, col1, weight, tone))

    def put(self, text, role, col0=0, col1=None, align="left", scale=1.0, bold=False):
        text = "" if text is None else str(text)
        if not text.strip():
            return
        col1 = self.ncols if col1 is None else col1
        self.cells.append(
            Cell(text, role, self.row, int(col0), int(col1), align, float(scale), bool(bold))
        )

    def newline(self, count: int = 1) -> None:
        self.row += count

    def rule(self, rng: random.Random, char: str | None = None) -> None:
        char = char or rng.choice(SEPARATORS)
        width = self.ncols if rng.random() < 0.8 else int(self.ncols * rng.uniform(0.4, 0.9))
        if self.ruled:
            # Both draws are made either way, so a layout that switches to drawn
            # rules does not shift every later sample by two numbers. `char` is
            # then thrown away: a drawn line is a drawn line whether the till
            # would have printed it with `-` or with `~`.
            width = max(width, 4)
            start = (self.ncols - width) // 2
            # Mid-row, and the row is still spent -- see `_full_rule`.
            self.mark("rule", self.row + 0.5, start, self.row + 0.5, start + width)
            self.newline()
            return
        self.put(char * max(width, 4), "sep", 0, self.ncols, "center")
        self.newline()


def _full_rule(builder, spec) -> None:
    """A rule from edge to edge, in the character the layout draws rules with.

    Not `_Builder.rule`: that one is a till's separator and draws a short
    centred dash one time in five. A ruling of a form is a ruling of the form.
    """
    if builder.ruled:
        # Drawn, not typed: a layout that says its lines are drawn should have
        # no line of `-` left anywhere on it.
        #
        # Unlike a table rule this one still spends its row, and sits in the
        # middle of it. A rule between two blocks is a gap with a line in it --
        # take the row away and the line lands on the shoulders of the next
        # line of type, which is how a strikethrough looks, not a separator.
        builder.mark("rule", builder.row + 0.5, 0, builder.row + 0.5, builder.ncols - 1)
        builder.newline()
        return
    char = str(spec.get("rule_char", "-"))[:1] or "-"
    builder.put(char * builder.ncols, "sep", 0, builder.ncols, "left")
    builder.newline()


def _resolve(columns: list[dict[str, Any]], ncols: int, gutter: int,
             inset: int) -> list[dict[str, Any]]:
    """Give every column a concrete [col0, col1) in characters.

    Widths in the spec are fixed; the ONE column written `width: 0` takes
    whatever is left. Doing it here rather than in the YAML means one layout
    works at 32 columns and at 48 without a second set of numbers.

    A framed table is inset by one character at each edge so the frame has
    somewhere to be, and the gutter between two columns is where the `|` goes
    -- which is why a framed layout wants `gutter: 3` and a thermal one is
    happy with 1.

    Taken as a function of a column list rather than of a layout because a page
    may carry two tables: a VAT form ends with a summary by tax rate, whose
    columns are its own and whose widths have to be resolved the same way.
    """
    columns = [dict(column) for column in columns]
    if not columns:
        return []
    usable = ncols - 2 * inset
    fixed = sum(int(column["width"]) for column in columns if int(column["width"]))
    cursor = inset
    for index, column in enumerate(columns):
        if not int(column["width"]):
            width = max(usable - fixed, 8)
        else:
            width = int(column["width"])
        column["col0"] = cursor
        cursor = min(cursor + width, ncols - inset)
        # Every column but the last gives up its last character, so a
        # right-aligned number never touches the column that follows it --
        # "112,000BUN BO HUE" is what happens without this.
        column["col1"] = cursor - gutter if index < len(columns) - 1 else cursor
    columns[-1]["col1"] = ncols - inset
    return columns


def _resolve_columns(spec: dict[str, Any], ncols: int) -> list[dict[str, Any]]:
    """The item table's columns, inset when the layout draws a frame."""
    # Two characters at each edge, not one: the frame takes the first and the
    # second is the space that keeps a column title off the `|` beside it.
    return _resolve(
        spec.get("columns", []),
        ncols,
        int(spec.get("gutter", 1)),
        2 if spec.get("table", {}).get("frame") else 0,
    )


def _column(columns: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    for column in columns:
        if column.get("key") == key:
            return column
    return None


def _case(receipt, text: str) -> str:
    """Put a string from the layout spec through the receipt's own spelling.

    Column titles, notes and the "KM" label live in the YAML, not in the
    corpus, so nothing else folds them -- and an ASCII thermal printer from
    2011 would then print "Số lượng" above items called "BUN RIEU CUA".
    """
    return apply_case(text, upper=receipt.upper, fold=receipt.folded)


def _emit_header(builder, spec, receipt, columns, rng) -> None:
    header = spec.get("header", {})
    scale_range = header.get("name_scale", [1.2, 1.6])
    name_scale = rng.uniform(*scale_range)
    builder.put(receipt.store.name, "store.name", align="center",
                scale=name_scale, bold=header.get("name_bold", True))
    builder.newline(2 if name_scale > 1.25 else 1)

    for attribute, role in (
        ("branch", "store.branch"),
        ("address", "store.address"),
        ("address2", "store.address2"),
        ("phone", "store.phone"),
        ("website", "store.website"),
    ):
        value = getattr(receipt.store, attribute)
        if value and header.get(attribute, True):
            # Narrow paper cuts a long address short, exactly as a real till
            # does -- but then the label has to say what was printed, not what
            # was sampled. Write the truncation back before the ground truth is
            # built from these same objects.
            shown = fit(value, builder.ncols)
            if shown != value:
                setattr(receipt.store, attribute, shown)
            builder.put(shown, role, align="center")
            builder.newline()

    if header.get("title", True):
        builder.newline()
        title_scale = rng.uniform(*header.get("title_scale", [1.1, 1.4]))
        builder.put(receipt.title, "title", align="center", scale=title_scale, bold=True)
        builder.newline(2 if title_scale > 1.25 else 1)

    # `header: notes:` and not a top-level `notes:` -- the notes SECTION reads
    # the top-level key for its own settings, and one key meaning a list of
    # printed lines in one place and a dict of settings in another is a trap
    # that prints the word "style" on the receipt.
    for line in header.get("notes", []):
        builder.put(_case(receipt, line), "note", align="center")
        builder.newline()


def _emit_meta(builder, spec, receipt, columns, rng) -> None:
    style = spec.get("meta", {}).get("style", "pairs")
    entries = list(receipt.meta)
    if not entries:
        return

    if style == "pipes":
        # WinMart prints its metadata as one run separated by '|'.
        text = "|".join(f"{label}{value}" for label, value in entries)
        for line in wrap(text, builder.ncols):
            builder.put(line, "meta", align="left")
            builder.newline()
    elif style == "two_column":
        # Two entries share a row only when both fit; otherwise each takes its
        # own, because half a line silently truncates a timestamp to "12-04-2".
        index = 0
        while index < len(entries):
            left = f"{entries[index][0]} {entries[index][1]}".strip()
            right = ""
            if index + 1 < len(entries):
                candidate = f"{entries[index + 1][0]} {entries[index + 1][1]}".strip()
                if len(left) + len(candidate) + 2 <= builder.ncols:
                    right = candidate
            builder.put(left, "meta", 0, builder.ncols - len(right) - 1, "left")
            if right:
                builder.put(right, "meta", builder.ncols - len(right), builder.ncols, "right")
                index += 1
            index += 1
            builder.newline()
    else:  # pairs: label left, value right
        for label, value in entries:
            split = max(builder.ncols - len(value) - 1, builder.ncols // 3)
            builder.put(fit(label, split), "meta.label", 0, split, "left")
            builder.put(value, "meta.value", split, builder.ncols, "right")
            builder.newline()

    if spec.get("meta", {}).get("rule_after", True):
        builder.rule(rng, spec.get("rule_char"))


def _emit_column_header(builder, spec, receipt, columns, rng=None) -> None:
    """The titles above the columns, wrapped inside the column they name.

    A thermal receipt's titles are one word and fit; an invoice's are a phrase
    -- "Số Đọc Tháng Trước" over a 14-character column -- and a real form sets
    them over two or three lines rather than letting them run into the next
    column. Wrapping keeps the header the same shape as the printed original
    and keeps every cell inside the columns it claims.
    """
    if not columns or not spec.get("column_header", True):
        return
    top = builder.row
    tallest = 1
    for column in columns:
        title = column.get("title")
        if not title:
            continue
        align = column.get("title_align", column.get("align", "left"))
        lines = wrap(_case(receipt, str(title)), column["col1"] - column["col0"])
        for offset, line in enumerate(lines):
            builder.row = top + offset
            builder.put(line, "colhdr", column["col0"], column["col1"], align,
                        bold=spec.get("column_header_bold", False))
        tallest = max(tallest, len(lines))
    builder.row = top + tallest



def item_values(item, receipt) -> dict[str, str]:
    """Every string one item can put in a column, keyed by the column's `from:`.

    Public because the CSS template path in `generators/html/sheets/` prints the
    same columns from the same layout file and must print the same strings. Two
    derivations of "tiền thuế của dòng này" that agree today are two that can
    disagree tomorrow, and nothing downstream would catch it.
    """
    shown_qty = item.display_qty()
    decimals = 3 if shown_qty % 1 else 0
    name = item.name
    barcode = item.barcode
    return {
        "stt": str(item.stt),
        "name": name,
        "qty": "" if item.is_group else quantity(shown_qty, receipt.money_style, decimals),
        "unit_price": receipt.cash(item.display_unit_price()),
        "amount": receipt.cash(item.amount),
        "barcode": barcode,
        # Saigon Co.op prints the barcode and the name on one line.
        "barcode_name": f"{barcode}  {name}".strip(),
        "vat": f"VAT {item.vat_rate}%" if item.vat_rate else "",
        "vat_rate": f"{item.vat_rate}%" if item.vat_rate else "",
        "unit": "" if item.is_group else item.unit,
        "note": item.note,
        # A stay invoice rules a column for the night a line covers and another
        # for the room it was slept in.
        "date": item.date,
        "ref": item.ref,
        # A utility bill: the two readings, the allowance the tariff is measured
        # against, and the tariff code that shares the price column with the
        # price itself ("DV 29.000" on the Nước sạch Hà Nội bill).
        "meter_now": str(item.meter_now) if item.meter_now else "",
        "meter_prev": str(item.meter_prev) if item.meter_prev else "",
        "quota": quantity(item.quota, receipt.money_style) if item.quota else "",
        "tier": item.tier,
        "tier_price": " ".join(
            part for part in (item.tier, receipt.cash(item.unit_price)) if part
        ),
        # ---- bảng kê KCB: the twelve columns of Mẫu số 01/KBCB.
        #
        # A heading row carries its block's sums and nothing else, so the
        # columns that describe a *line* -- unit, quantity, the two rates --
        # come out blank on it. That is what the form prints, and it is also
        # what stops the label claiming a quantity of zero for a heading.
        "price_bv": receipt.cash(item.price_bv) if item.price_bv else "",
        "price_bh": receipt.cash(item.price_bh) if item.price_bh else "",
        "rate_service": "" if item.is_group else f"{item.rate_service}",
        "rate_bhyt": "" if item.is_group else f"{item.rate_bhyt}",
        "amount_bv": receipt.cash(item.amount_bv()) if item.amount_bv() else "",
        "amount_bh": receipt.cash(item.amount_bh()) if item.amount_bh() else "",
        "fund": receipt.cash(item.fund_bhyt(item.benefit)) if item.amount_bh() else "",
        "copay": receipt.cash(item.copay(item.benefit)) if item.amount_bh() else "",
        "other_pay": receipt.cash(item.other_pay()) if item.other_pay() else "",
        "self_pay": receipt.cash(item.self_pay(item.benefit)) if item.self_pay(item.benefit) else "",
        "group": item.group,
        # Net of tax, and the tax on the line: the two right-hand columns of a
        # VAT invoice, which are derived rather than stored.
        "vat_amount": (
            receipt.cash(round(item.amount * item.vat_rate / 100.0))
            if item.vat_rate else ""
        ),
        "amount_with_vat": receipt.cash(
            item.amount + round(item.amount * item.vat_rate / 100.0)
        ),
    }


def _span(entry, columns, builder):
    """Where an item cell sits: an explicit span, a named column, or the width.

    A span is how a name gets to run across the numeric columns -- on the quán
    nhậu bill the dish name starts under "Số lượng" and runs to the end of
    "Tiền", even though those are separate columns on the row below.
    """
    if "span" in entry:
        first, last = entry["span"]
        start = _column(columns, first)
        end = _column(columns, last)
        if start and end:
            return start["col0"], end["col1"], entry.get("align", "left")
    column = _column(columns, entry.get("col")) if entry.get("col") else None
    if column:
        return column["col0"], column["col1"], entry.get("align", column.get("align", "left"))
    return 0, builder.ncols, entry.get("align", "left")


def _emit_items(builder, spec, receipt, columns, rng) -> None:
    """The item block of a till receipt: the rows, then a rule under them."""
    _emit_item_rows(builder, spec, receipt, columns)
    builder.rule(rng, spec.get("rule_char"))


def _emit_item_rows(builder, spec, receipt, columns, after_item=None) -> None:
    """Play back the layout's item template for each line of the bill.

    A template is a list of rows; a row is a list of `{col, from}` entries. A
    row whose fields are all empty is skipped, which is how one template
    covers both a weighed item (which has a second name line) and a packaged
    one (which does not).

    A wrapping name grows the row downwards, but the other cells of that row
    stay on its first line -- on the WinMart bill the price sits beside the
    first line of a three-line product name, not beside the last.
    """
    template = spec.get("item", {}).get("rows", [[{"col": "name", "from": "name"}]])
    wrap_name = spec.get("item", {}).get("wrap_name", True)

    for item in receipt.items:
        values = item_values(item, receipt)
        for row in template:
            base = builder.row
            extra = 0
            painted = False
            for entry in row:
                source = entry.get("from", entry.get("col"))
                text = values.get(source, "")
                if not text:
                    continue
                col0, col1, align = _span(entry, columns, builder)
                col0 += int(entry.get("indent", 0))
                width = max(col1 - col0, 4)
                role = f"menu.{source}"

                if source in ("name", "note", "barcode_name") and len(text) > width:
                    lines = wrap(text, width) if wrap_name else [fit(text, width)]
                    if not wrap_name and source in ("name", "note"):
                        # A layout that cuts rather than wraps -- the old thermal
                        # till -- must not leave the label claiming the full name.
                        setattr(item, source, lines[0])
                        values[source] = lines[0]
                    for offset, line in enumerate(lines):
                        builder.row = base + offset
                        builder.put(line, role, col0, col1, align)
                    extra = max(extra, len(lines) - 1)
                else:
                    builder.row = base
                    builder.put(fit(text, width), role, col0, col1, align)
                painted = True
            builder.row = base + extra
            if painted:
                builder.newline()
            else:
                builder.row = base

        if item.note and spec.get("item", {}).get("note_row"):
            entry = spec["item"]["note_row"]
            col0 = int(entry.get("indent", 2))
            for line in wrap(item.note, builder.ncols - col0):
                builder.put(line, "menu.note", col0, builder.ncols, "left")
                builder.newline()

        if item.original_price and spec.get("item", {}).get("original_price_row"):
            label = _case(receipt, spec["item"]["original_price_row"].get("label", "Giá gốc:"))
            builder.put(f"{label} {receipt.cash(item.original_price)}",
                        "menu.originalprice", 3, builder.ncols, "left")
            builder.newline()

        if item.discount:
            entry = spec.get("item", {}).get("discount_row", {})
            label = _case(receipt, entry.get("label", "KM"))
            builder.put(label, "menu.discount.label", 0, builder.ncols // 2, "left")
            builder.put(receipt.cash(-abs(item.discount)),
                        "menu.discountprice", builder.ncols // 2, builder.ncols, "right")
            builder.newline()

        # A printed form rules every row, not just the block of them; the
        # caller passes what to draw so this stays one loop over the items.
        if after_item is not None:
            after_item()


def _emit_totals(builder, spec, receipt, columns, rng) -> None:
    """Totals, with the grand total set larger when the layout says so.

    The grand total is the one `content.build` marked, not the last line: a
    receipt usually goes on to print what the customer handed over and what
    came back, and setting the change in 1.6x bold is not what a till does.
    """
    settings = spec.get("totals", {})
    # A till's totals run the width of the paper; a self-designed invoice sets
    # them in a block against the right margin with the table left empty
    # beneath it. `indent` is that left edge -- a fraction of the sheet, or a
    # character count if it is 1 or more.
    indent = float(settings.get("indent", 0))
    left = int(builder.ncols * indent) if 0 < indent < 1 else int(indent)
    left = max(min(left, builder.ncols - 12), 0)

    for index, (label, value) in enumerate(receipt.totals):
        is_grand = settings.get("emphasise_grand", True) and index == receipt.grand_index
        role = "total.grand" if is_grand else "total.line"
        scale = rng.uniform(*settings.get("grand_scale", [1.2, 1.6])) if is_grand else 1.0

        if is_grand and settings.get("grand_two_lines") and rng.random() < 0.5:
            builder.put(label, f"{role}.label", left, builder.ncols, "center",
                        scale=scale, bold=True)
            builder.newline(2)
            builder.put(value, role, left, builder.ncols, "right", scale=scale, bold=True)
            builder.newline(2)
            continue

        # Give the label whatever the amount does not need. Splitting at the
        # midpoint truncates "Ví điện tử của VinID Pay" to "Ví điện tử của VinID P".
        split = max(builder.ncols - len(value) - 1, left + (builder.ncols - left) // 3)
        builder.put(fit(label, split - left), f"{role}.label", left, split, "left",
                    scale=scale, bold=is_grand)
        builder.put(value, role, split, builder.ncols, "right",
                    scale=scale, bold=is_grand)
        builder.newline(2 if is_grand and scale > 1.3 else 1)


def _emit_footer(builder, spec, receipt, columns, rng) -> None:
    if not receipt.footer:
        return
    builder.newline()
    if spec.get("footer", {}).get("rule_before", False):
        builder.rule(rng, spec.get("rule_char"))
    for line in receipt.footer:
        for wrapped in wrap(line, builder.ncols):
            builder.put(wrapped, "footer", align="center")
            builder.newline()


# ----------------------------------------------------------- VAT invoices
#
# A till receipt is a column of text. An invoice is a form: a letterhead with
# the serial beside it, a block naming both parties, a ruled table, the total
# written out in words, and signatures. The sections below draw those, and
# `sections:` in a layout file decides which of them run and in what order.


def _leader(text: str, width: int, char: str) -> str:
    """Pad `text` out to `width` with the leader a printed form uses.

    The dotted run is the form itself: on a blank invoice it is all there is,
    and on a filled one it is what tells a reader the field ended where it did
    rather than being cut off by the edge of the box.
    """
    text = fit(text, width)
    if not char:
        return text
    pad = width - len(text) - (1 if text else 0)
    return f"{text}{' ' if text else ''}{char * pad}" if pad > 0 else text


def _put_field(builder, label: str, value: str, col0: int, col1: int,
               role: str, leader: str = "") -> str:
    """`Label: value` as two cells, and the value as it was actually printed.

    Two cells rather than one string, because the label has to quote the value
    exactly -- `tests/test_content.py` compares them for equality, and a cell
    reading "Địa chỉ: 44 Yên Phụ" is not equal to the address. Long values are
    cut rather than wrapped: in a two-column block the continuation of a left
    field lands after the right field in reading order, and a label built from
    a value that reassembles in the wrong order is worse than a short one.
    """
    label = fit(label, max(col1 - col0 - 4, 1))
    start = col0 + len(label) + (1 if label else 0)
    if label:
        builder.put(label, f"{role}.label", col0, start - 1, "left")
    shown = fit(value, max(col1 - start, 1))
    builder.put(_leader(shown, col1 - start, leader), role, start, col1, "left")
    return shown


def _emit_letterhead(builder, spec, receipt, columns, rng) -> None:
    """Who issued this, on the left; which invoice it is, on the right."""
    settings = spec.get("letterhead", {})
    labels = settings.get("labels", {})
    invoice = receipt.invoice
    right_width = int(settings.get("serial_width", 26))
    split = max(builder.ncols - right_width, builder.ncols // 2)
    # An e-invoice rendition boxes the seller's details -- name, address, tax
    # code, bank -- and prints a QR beside them. The frame is what survives
    # into a character grid; the QR is not text and is not drawn.
    framed = bool(settings.get("frame"))
    edges = [0, builder.ncols - 1]
    frame_top = builder.row
    # Inside a box the text starts at column 2, not at column 0: the frame owns
    # the first character, and a cell sitting on it would take the column that
    # `_paint_bars` needs for the `|` -- the box would then be drawn with three
    # sides and look like a mistake rather than like a form.
    left = 2 if framed else 0
    if framed:
        _rule_row(builder, edges)

    top = builder.row
    scale = rng.uniform(*settings.get("name_scale", [1.05, 1.25]))
    for line in wrap(receipt.store.name, split - 1 - left):
        builder.put(line, "store.name", left, split - 1, "left",
                    scale=scale, bold=settings.get("name_bold", True))
        builder.newline()
    for attribute, role in (
        ("address", "store.address"),
        ("tax_code", "store.tax_code"),
        ("branch", "store.branch"),
        ("phone", "store.phone"),
        ("account", "store.account"),
        # A letterhead had no way to print a website, so any document whose
        # issuer has one put a field in the label that no letterhead layout
        # could draw. Only `resort_stay` and the authorisation form set one,
        # and only the second uses a letterhead -- but the gap was in the
        # section, not in either document.
        ("website", "store.website"),
    ):
        value = getattr(receipt.store, attribute)
        if not value or not settings.get(attribute, True):
            continue
        shown = _put_field(builder, _case(receipt, labels.get(attribute, "")), value,
                           left, split - 1, role)
        if shown != value:
            setattr(receipt.store, attribute, shown)
        builder.newline()

    if invoice is None:
        if framed:
            _rule_row(builder, edges)
            _paint_bars(builder, edges, frame_top + 1, builder.row - 1,
                        span=(frame_top, builder.row))
        return
    # The serial block sits beside the letterhead, not under it, so it is
    # written back onto the rows the letterhead already used.
    bottom = builder.row
    builder.row = top
    for key, default, value, role in (
        ("form_no", "Mẫu số:", invoice.form_no, "invoice.form_no"),
        ("serial", "Ký hiệu:", invoice.serial, "invoice.serial"),
        ("number", "Số:", invoice.number, "invoice.number"),
    ):
        # `serial: false` drops the row: a modern invoice puts its number in
        # the strip across the top and nowhere else, and printing it twice
        # would leave the layout naming the same field in two places.
        if not value or not settings.get(key, True):
            continue
        label = labels.get(key, default)
        _put_field(builder, _case(receipt, label), value, split,
                   builder.ncols - (2 if framed else 0), role)
        builder.newline()
    builder.row = max(bottom, builder.row)
    if framed:
        _rule_row(builder, edges)
        _paint_bars(builder, edges, frame_top + 1, builder.row - 1,
                    span=(frame_top, builder.row))
    builder.newline()


def _emit_doctitle(builder, spec, receipt, columns, rng) -> None:
    """The centred title, what the document is a rendition of, and its period."""
    settings = spec.get("doctitle", {})
    invoice = receipt.invoice
    scale = rng.uniform(*settings.get("scale", [1.25, 1.5]))
    for line in wrap(receipt.title, builder.ncols):
        builder.put(line, "title", align="center", scale=scale, bold=True)
        builder.newline()
    if invoice and invoice.subtitle:
        # Wrapped, not cut. A subtitle is a sentence -- the authorisation form's
        # runs to 140 characters on a 98-column sheet -- and `fit` would leave
        # the label claiming the half of it nobody can read.
        for line in wrap(invoice.subtitle, builder.ncols):
            builder.put(line, "subtitle", align="center")
            builder.newline()
    if invoice and invoice.period:
        builder.put(fit(invoice.period, builder.ncols), "period", align="center", bold=True)
        builder.newline()
    builder.newline()


def _emit_parties(builder, spec, receipt, columns, rng) -> None:
    """Who is billed, and everything the invoice is keyed by.

    Two columns where the document has two -- a utility bill puts the customer
    on the left and the meter on the right -- and stacked where the field is a
    whole line of its own, which is what a blank form looks like.
    """
    invoice = receipt.invoice
    if invoice is None:
        return
    settings = spec.get("parties", {})
    leader = settings.get("leader", "")
    gap = int(settings.get("gap", 2))
    stacked = settings.get("style") == "stacked"
    split = builder.ncols if stacked else int(builder.ncols * float(settings.get("split", 0.55)))

    columns_of_fields = [
        # Stacked, the two blocks run one under the other and must be the same
        # width: a dotted field two characters longer than the one above it
        # reads as a fault in the printing, not as a second block.
        (invoice.left_title, invoice.left, 0, builder.ncols if stacked else split - gap),
        (invoice.right_title, invoice.right, 0 if stacked else split, builder.ncols),
    ]
    if any(title for title, *_ in columns_of_fields):
        top = builder.row
        for title, _fields, col0, col1 in columns_of_fields:
            if title:
                builder.row = top
                builder.put(fit(title, col1 - col0), "parties.title", col0, col1, "left",
                            bold=True)
        builder.row = top + 1

    top = builder.row
    lowest = top
    for _title, fields, col0, col1 in columns_of_fields:
        builder.row = top
        for index, (label, value) in enumerate(fields):
            shown = _put_field(builder, label, value, col0, col1, "invoice.field", leader)
            if shown != value:
                # Same rule the letterhead follows: the page cut it, so the
                # label says what the page shows.
                fields[index] = (label, shown)
            builder.newline()
        lowest = max(lowest, builder.row)
        if stacked:
            top = builder.row
    builder.row = lowest
    builder.newline()


def _emit_strip(builder, spec, receipt, columns, rng) -> None:
    """The run of keys a modern invoice sets across the top of the page.

    "Số hoá đơn: INV001421 | Ngày: 30/09/2024 17:11 | Mã đặt phòng: 001421" --
    the same (label, value) pairs the party block is made of, laid left to
    right instead of down a column. Label and value stay separate cells: the
    ground truth quotes the value alone, and a single cell reading
    "Số hoá đơn: INV001421" is not equal to "INV001421".
    """
    invoice = receipt.invoice
    if invoice is None or not invoice.strip:
        return
    settings = spec.get("strip", {})
    separator = str(settings.get("separator", "|"))
    cursor = 0
    top = builder.row
    for label, value in invoice.strip:
        label = fit(label, builder.ncols)
        value = fit(value, builder.ncols)
        width = len(value) + (len(label) + 1 if label else 0)
        if cursor and cursor + len(separator) + 2 + width > builder.ncols:
            builder.newline()
            cursor = 0
        elif cursor:
            builder.put(separator, "sep", cursor + 1, cursor + 1 + len(separator), "left")
            cursor += len(separator) + 2
        if label:
            builder.put(label, "invoice.field.label", cursor, cursor + len(label), "left")
            cursor += len(label) + 1
        builder.put(value, "invoice.field", cursor, cursor + len(value), "left")
        cursor += len(value)
    if builder.row > top or cursor:
        builder.newline()
    if settings.get("rule_after", True):
        _full_rule(builder, spec)


def _bar_positions(columns, ncols: int) -> list[int]:
    """Where the `|` of a ruled table goes: both edges, and each gutter."""
    positions = [0, ncols - 1]
    for left, right in zip(columns, columns[1:]):
        positions.append(left["col1"] + max((right["col0"] - left["col1"]) // 2, 0))
    return sorted(set(position for position in positions if 0 <= position < ncols))


def _rule_row(builder, positions, char: str = "-", junction: str = "+",
              col0: int = 0, col1: int | None = None) -> None:
    """One horizontal rule of a ruled table, as a single cell.

    `col0`/`col1` bound it: the signature stamp is a box in the right half of
    the sheet, and a rule drawn the full width would put a line through the
    buyer's empty signature space as well.
    """
    col1 = builder.ncols if col1 is None else col1
    if builder.ruled:
        # A ruled form draws the line *between* two rows and spends no line on
        # it, which is why a real form fits more on a page than its ASCII
        # rendering does. `_paint_bars` puts the verticals in.
        #
        # `col1 - 1`, not `col1`: the last character column is where the closing
        # vertical stands (`_bar_positions` ends at `ncols - 1`), and a rule
        # drawn to `col1` would stick a character's width out past the corner.
        builder.mark("rule", builder.row, col0, builder.row, col1 - 1)
        return
    line = [char] * (col1 - col0)
    for position in positions:
        if col0 <= position < col1:
            line[position - col0] = junction
    builder.put("".join(line), "sep", col0, col1, "left")
    builder.newline()


def _paint_bars(builder, positions, first: int, last: int,
                span: tuple[int, int] | None = None) -> None:
    """Drop the verticals down every row of the table, `first` to `last`.

    A position already covered by a cell is skipped rather than overwritten: a
    row of the table may legitimately span its columns -- a total that runs the
    width of the frame, an item name spilling into the next column -- and two
    cells on the same characters print on top of each other in all three
    renderers at once.

    `first`/`last` are the *text* rows to put a `|` on, which is not where a
    drawn vertical starts and stops: an ASCII rule spends a row of its own, so
    the caller counts from one row inside the frame, while a drawn rule sits on
    the boundary between two rows and the vertical has to reach it or the frame
    is left open at both ends. `span` is that pair of boundary rows -- every
    caller knows it, none of them can be guessed from `first`/`last`.
    """
    if builder.ruled:
        # One mark per boundary for the whole height, instead of one `|` cell
        # per row per boundary. It also removes the reason `_paint_bars` had to
        # dodge cells that span their columns: a drawn line passes behind text
        # instead of overwriting it.
        row0, row1 = span if span else (first, last)
        for position in positions:
            builder.mark("rule", row0, position, row1, position)
        return
    occupied: dict[int, list[tuple[int, int]]] = {}
    for cell in builder.cells:
        occupied.setdefault(cell.row, []).append((cell.col0, cell.col1))
    keep = builder.row
    for row in range(first, last):
        taken = occupied.get(row, ())
        builder.row = row
        for position in positions:
            if any(col0 <= position < col1 for col0, col1 in taken):
                continue
            builder.put("|", "sep", position, position + 1, "left")
    builder.row = keep


def _shade_band(builder, settings, top: int, col0: int, col1: int) -> None:
    """The tint a printed form lays under a band of rows.

    Under the column titles, and under the line the reader is meant to find
    first -- the amount owed. Both are the same primitive over a different band,
    which is the whole reason `Mark` has a `tone`.

    Off unless the layout asks (`shade:` is a fraction of the page's ink), and
    unavailable to an ASCII layout at all: a till roll can print a line of `-`
    and cannot print a grey box, so a thermal receipt that asked for one would
    be drawn something its real printer could not produce.
    """
    tone = float(settings.get("shade", 0) or 0)
    if not builder.ruled or tone <= 0 or builder.row <= top:
        return
    builder.mark("fill", top, col0, builder.row, col1, tone=tone)


def _outline(builder, settings, top: int, col0: int, bottom: int, col1: int) -> None:
    """The heavier border a form draws around a table, inside its hairlines.

    A printed form is not ruled with one pen. The outer boundary is drawn
    thicker than the row rules inside it -- which is most of what makes a table
    read as a table from across the room -- and `weight` is exactly the number a
    renderer needs to do that at its own resolution.
    """
    weight = float(settings.get("border", 1.8) or 0)
    if not builder.ruled or weight <= 1.0:
        return
    builder.mark("frame", top, col0, bottom, col1, weight=weight)


def _emit_column_numbers(builder, spec, receipt, columns) -> None:
    """The `1  2  3  4  5  6  7 = 4x6` row a blank VAT form prints under its titles."""
    for index, column in enumerate(columns):
        number = str(column.get("number", index + 1))
        builder.put(fit(_case(receipt, number), column["col1"] - column["col0"]),
                    "colnum", column["col0"], column["col1"], "center")
    builder.newline()


def _emit_table(builder, spec, receipt, columns, rng) -> None:
    """The item table, ruled if the layout says so.

    Unruled it is the thermal receipt's block of items with a rule under it.
    Ruled it is a printed form: a frame, titles, sometimes the numbered row a
    Vietnamese VAT form carries, then the items -- and then blank rows, because
    a form has as many rows as it was printed with and not as many as the sale
    happened to need.
    """
    table = spec.get("table", {})
    if not table.get("frame"):
        # An unruled table may still rule its heading: a designed invoice sets
        # the column titles between two lines and leaves the rest of the table
        # open.
        if table.get("header_rules"):
            _full_rule(builder, spec)
        head = builder.row
        _emit_column_header(builder, spec, receipt, columns)
        _shade_band(builder, table, head, 0, builder.ncols - 1)
        if table.get("header_rules"):
            _full_rule(builder, spec)
        _emit_items(builder, spec, receipt, columns, rng)
        return

    positions = _bar_positions(columns, builder.ncols)
    top = builder.row
    _rule_row(builder, positions)
    _emit_column_header(builder, spec, receipt, columns)
    if table.get("column_numbers"):
        _emit_column_numbers(builder, spec, receipt, columns)
    _shade_band(builder, table, top, positions[0], positions[-1])
    _rule_row(builder, positions)

    after = (lambda: _rule_row(builder, positions)) if table.get("row_rules") else None
    _emit_item_rows(builder, spec, receipt, columns, after_item=after)
    for _ in range(int(table.get("blank_rows", 0))):
        builder.newline()
        if table.get("row_rules"):
            _rule_row(builder, positions)
    if not table.get("row_rules"):
        _rule_row(builder, positions)
    _paint_bars(builder, positions, top + 1, builder.row - 1, span=(top, builder.row))
    _outline(builder, table, top, positions[0], builder.row, positions[-1])


def _emit_framed_totals(builder, spec, receipt, columns, rng) -> None:
    """Totals as rows of the table, which is where a VAT invoice prints them.

    One vertical only, before the money: the label runs the width of the sheet
    ("Phí BVMT đối với nước thải SH 10%") and a full set of columns under it
    would cut it in three.
    """
    settings = spec.get("totals", {})
    money_col = columns[-1] if columns else None
    split = money_col["col0"] if money_col else builder.ncols * 2 // 3
    positions = [0, split - 1, builder.ncols - 1]
    top = builder.row
    for index, (label, value) in enumerate(receipt.totals):
        is_grand = settings.get("emphasise_grand", True) and index == receipt.grand_index
        role = "total.grand" if is_grand else "total.line"
        band = builder.row
        builder.put(fit(label, split - 3), f"{role}.label", 2, split - 1, "left", bold=is_grand)
        builder.put(fit(value, builder.ncols - split - 3), role,
                    split, builder.ncols - 2, "right", bold=is_grand)
        builder.newline()
        # The amount owed carries the tint, not the whole block: shading every
        # total would make the emphasis mean nothing.
        if is_grand:
            _shade_band(builder, settings, band, positions[0], positions[-1])
        _rule_row(builder, positions)
    _paint_bars(builder, positions, top, builder.row - 1, span=(top, builder.row))
    _outline(builder, settings, top, positions[0], builder.row, positions[-1])


def _emit_vat_summary(builder, spec, receipt, columns, rng) -> None:
    """"Tổng hợp": the money by tax rate, in a ruled table of its own.

    A VAT form does not end with one tax line. It ends with a small table --
    what was sold exempt, what at each rate, what that came to in tax, and the
    amount owed -- because two lines of the same invoice may be taxed
    differently and a single "Thuế GTGT 10%" would be a lie about half of them.

    Its columns are not the item table's, so the layout declares them under
    `vat_summary:` and they are resolved on their own. `content.py` has already
    spelled the money; this only decides where each string sits.
    """
    invoice = receipt.invoice
    if invoice is None or not invoice.summary:
        return
    settings = spec.get("vat_summary", {})
    framed = settings.get("frame", True)
    resolved = _resolve(
        settings.get("columns") or [],
        builder.ncols,
        int(spec.get("gutter", 1)),
        2 if framed else 0,
    )
    if not resolved:
        return

    positions = _bar_positions(resolved, builder.ncols)
    top = builder.row
    if framed:
        _rule_row(builder, positions)
    head = builder.row
    _emit_column_header(builder, settings, receipt, resolved)
    _shade_band(builder, settings, head, positions[0], positions[-1])
    if framed:
        _rule_row(builder, positions)

    last = len(invoice.summary) - 1
    for index, row in enumerate(invoice.summary):
        # The closing row is the amount owed, and a form sets it in bold the
        # way it sets a grand total anywhere else.
        bold = settings.get("emphasise_total", True) and index == last
        for column in resolved:
            key = str(column.get("key", ""))
            text = row.get(key, "")
            if not text:
                continue
            width = column["col1"] - column["col0"]
            # Same rule the letterhead and the totals block already follow: a
            # narrow column cuts the text short, and the label then has to say
            # what was printed rather than what was sampled. Without this,
            # "HÀNG HOÁ KHÔNG CHỊU THUẾ GTGT:" is drawn as "...THUẾ GT" while
            # `ground_truth` keeps the full string -- a label describing text no
            # reader can see, on 145 of 300 pages of this layout.
            shown = fit(text, width)
            if shown != text:
                row[key] = shown
            builder.put(shown, f"summary.{column['key']}",
                        column["col0"], column["col1"],
                        column.get("align", "left"), bold=bold)
        builder.newline()
        if framed:
            _rule_row(builder, positions)
    if framed:
        _paint_bars(builder, positions, top + 1, builder.row - 1,
                    span=(top, builder.row))
        _outline(builder, settings, top, positions[0], builder.row, positions[-1])
    builder.newline()


def _emit_totals_section(builder, spec, receipt, columns, rng) -> None:
    if spec.get("totals", {}).get("frame"):
        _emit_framed_totals(builder, spec, receipt, columns, rng)
    else:
        _emit_totals(builder, spec, receipt, columns, rng)


def _emit_words(builder, spec, receipt, columns, rng) -> None:
    """"Số tiền bằng chữ" -- the total spelled out so the figure cannot be edited."""
    invoice = receipt.invoice
    if invoice is None or not invoice.words:
        return
    framed = spec.get("words", {}).get("frame")
    inset = 2 if framed else 0
    label = invoice.words_label
    text = f"{label} {invoice.words}".strip()
    top = builder.row
    for line in wrap(text, builder.ncols - 2 * inset - 1):
        builder.put(line, "invoice.words", inset, builder.ncols - inset, "left")
        builder.newline()
    if framed:
        _rule_row(builder, [0, builder.ncols - 1])
        _paint_bars(builder, [0, builder.ncols - 1], top, builder.row - 1,
                    span=(top, builder.row))
    builder.newline()


def _emit_notes(builder, spec, receipt, columns, rng) -> None:
    """The block an English invoice heads "Payment Options".

    A self-designed invoice ends in two of them side by side -- where to send
    the money on the left, how to reach the shop on the right. A blank line in
    `notes:` is the break between the two; with `style: two_column` it becomes
    the column boundary instead of an empty line.
    """
    invoice = receipt.invoice
    if invoice is None or not invoice.notes:
        return
    settings = spec.get("notes", {})
    if settings.get("style") == "two_column":
        builder.newline()
        blocks: list[list[str]] = [[]]
        for line in invoice.notes:
            if line.strip():
                blocks[-1].append(line)
            else:
                blocks.append([])
        blocks = [block for block in blocks if block][:2]
        split = int(builder.ncols * float(settings.get("split", 0.55)))
        top = builder.row
        lowest = top
        for index, block in enumerate(blocks):
            col0 = 0 if index == 0 else split
            col1 = split - 2 if index == 0 else builder.ncols
            # A role per column, not one for both. Cells are read in row order,
            # so a single role would interleave the two blocks and an address
            # wrapped over two lines could never be reassembled from it -- and
            # reassembling by role is how the label proves the page shows what
            # it claims.
            role = "note.left" if index == 0 else "note.right"
            builder.row = top
            for line in block:
                bold = line.endswith(":")
                for wrapped in wrap(line.rstrip(":"), col1 - col0):
                    builder.put(wrapped, role, col0, col1, "left", bold=bold)
                    builder.newline()
            lowest = max(lowest, builder.row)
        builder.row = lowest
        builder.newline()
        return

    for line in invoice.notes:
        if not line.strip():
            builder.newline()
            continue
        bold = line.endswith(":")
        for wrapped in wrap(line.rstrip(":"), builder.ncols):
            builder.put(wrapped, "note", 0, builder.ncols, "left", bold=bold)
            builder.newline()
    builder.newline()


def _emit_signatures(builder, spec, receipt, columns, rng) -> None:
    """The signature line, and the box an e-invoice stamps instead of signing."""
    invoice = receipt.invoice
    if invoice is None:
        return
    settings = spec.get("signatures", {})
    builder.newline()
    blocks = invoice.signatures
    if blocks:
        width = builder.ncols // len(blocks)
        top = builder.row
        for index, (title, instruction) in enumerate(blocks):
            col0 = index * width
            col1 = builder.ncols if index == len(blocks) - 1 else col0 + width
            builder.row = top
            builder.put(fit(title, col1 - col0), "sign.title", col0, col1, "center", bold=True)
            builder.newline()
            builder.put(fit(instruction, col1 - col0), "sign.note", col0, col1, "center")
        builder.newline()

        # A hotel bill leaves room for two signatures and then prints both
        # names under them, so the page says who signed even when nobody has.
        if invoice.signature_names:
            builder.newline(int(settings.get("name_gap", 3)))
            top = builder.row
            for index, name in enumerate(invoice.signature_names[:len(blocks)]):
                col0 = index * width
                col1 = builder.ncols if index == len(blocks) - 1 else col0 + width
                builder.row = top
                builder.put(fit(name, col1 - col0), "sign.name", col0, col1, "center")
            builder.newline()

    if not invoice.signed_by:
        return
    # The green box a Vietnamese e-invoice prints where the seller's wet
    # signature used to be. It sits under the seller's column, on the right.
    builder.newline(int(settings.get("stamp_gap", 2)))
    width = min(int(settings.get("stamp_width", 44)), builder.ncols)
    col0 = builder.ncols - width
    lines = [line for value in (invoice.signed_by, invoice.signed_at) if value
             for line in wrap(value, width - 4)]
    edges = [col0, builder.ncols - 1]
    signed_by_lines = len(wrap(invoice.signed_by, width - 4))
    top = builder.row
    _rule_row(builder, edges, col0=col0)
    for index, line in enumerate(lines):
        role = "sign.signedby" if index < signed_by_lines else "sign.signedat"
        builder.put(line, role, col0 + 2, builder.ncols - 2, "left")
        builder.newline()
    _rule_row(builder, edges, col0=col0)
    _paint_bars(builder, edges, top + 1, builder.row - 1, span=(top, builder.row))


# The sections a layout may ask for, and the order a till receipt uses when it
# asks for none. Adding a section is a function here and a name in `sections:`;
# nothing in this module decides which sequence is the normal one.
SECTIONS = {
    "header": _emit_header,
    "strip": _emit_strip,
    "vat_summary": _emit_vat_summary,
    "meta": _emit_meta,
    "columns": _emit_column_header,
    "items": _emit_items,
    "totals": _emit_totals_section,
    "footer": _emit_footer,
    "letterhead": _emit_letterhead,
    "doctitle": _emit_doctitle,
    "parties": _emit_parties,
    "table": _emit_table,
    "words": _emit_words,
    "notes": _emit_notes,
    "signatures": _emit_signatures,
}
DEFAULT_SECTIONS = ("header", "meta", "columns", "items", "totals", "footer")


def build_grid(receipt: Receipt, layout_id: str, rng: random.Random | None = None,
               root: Path | str = LAYOUTS_ROOT) -> Grid:
    """Lay `receipt` out per `layout_id`."""
    rng = rng or random.Random(0)
    spec = load_layout(layout_id, root)

    width_range = spec.get("width", [38, 46])
    ncols = rng.randint(int(width_range[0]), int(width_range[1]))
    columns = _resolve_columns(spec, ncols)

    # `rules: marks` asks for drawn lines instead of rows of `+---+`. Absent --
    # which is every layout that existed before this -- keeps the characters,
    # so no committed image moves.
    # `sheet:` names the paper. Checked here rather than at render time so a
    # typo stops the run before an image exists, and checked against the same
    # table all three renderers read.
    sheet = str(spec.get("sheet", "") or "")
    if sheet and sheet not in SHEETS:
        raise KeyError(
            f"{layout_id}: unknown sheet {sheet!r}; have {', '.join(sorted(SHEETS))}")

    builder = _Builder(ncols, ruled=str(spec.get("rules", "ascii")) == "marks")
    sections = spec.get("sections") or DEFAULT_SECTIONS
    unknown = [name for name in sections if name not in SECTIONS]
    if unknown:
        raise KeyError(
            f"{layout_id}: unknown section(s) {unknown}; have {', '.join(sorted(SECTIONS))}"
        )
    for name in sections:
        SECTIONS[name](builder, spec, receipt, columns, rng)

    return Grid(
        cells=builder.cells,
        ncols=ncols,
        nrows=builder.row + 1,
        layout_id=layout_id,
        columns=columns,
        # Paint order, once, here rather than three times in the renderers: the
        # shading is the ground, the lines go on it, the text goes on both. A
        # header tint emitted after the rule that bounds it would otherwise be
        # painted over that rule and rub it out.
        #
        # The list is back to front, which is what a DOM is; the glyph backend
        # composites the other way round and reverses it on the way in.
        marks=sorted(builder.marks, key=lambda mark: mark.kind != "fill"),
        sheet=sheet,
    )


__all__ = [
    "Cell", "DEFAULT_SECTIONS", "Grid", "LAYOUTS_ROOT", "SECTIONS",
    "available", "build_grid", "load_layout",
]
