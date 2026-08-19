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

    `colour` is the exception to `tone`. A tint mixed from the page's ink can
    only ever be grey-of-the-ink, and a form printed in two colours -- a blue
    header band over black type, the pink of a carbon copy -- is not that. When
    it is set it is an absolute `#rrggbb` and `tone` no longer applies; left
    unset, every mark fades with the ink exactly as it did before, so no page
    that does not ask for colour moves.
    """

    kind: str                 # 'rule' | 'fill' | 'frame'
    row0: float
    col0: float
    row1: float
    col1: float
    weight: float = 1.0
    tone: float = 1.0
    colour: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out = {
            "kind": self.kind,
            "row0": round(self.row0, 3), "col0": round(self.col0, 3),
            "row1": round(self.row1, 3), "col1": round(self.col1, 3),
            "weight": round(self.weight, 3), "tone": round(self.tone, 3),
        }
        # Only when asked. A key that appears on every mark of every layout
        # would rewrite every committed label to say "no colour" out loud.
        if self.colour:
            out["colour"] = self.colour
        return out


@dataclass
class Cell:
    """One run of text, on the character grid.

    `col0`/`col1` have always been the cell's horizontal span; `rowspan` is the
    other half of the same idea, and it is what a table means by a merged cell.
    A cell with `rowspan > 1` is drawn CENTRED in the band it covers rather than
    sitting on the top row of it, because that is where a reader looks for the
    label of a group of rows -- and it is one addition in each renderer, since
    all three already multiply `row` by a line height.
    """

    text: str
    role: str                 # where it belongs in the label: 'menu.nm', 'total.grand', ...
    row: int
    col0: int
    col1: int
    align: str = "left"       # left | right | center
    scale: float = 1.0        # relative to the body font size
    bold: bool = False
    rowspan: int = 1          # rows covered; > 1 is a vertically merged cell

    def to_dict(self) -> dict[str, Any]:
        out = {
            "text": self.text, "role": self.role, "row": self.row,
            "col0": self.col0, "col1": self.col1,
            "align": self.align, "scale": round(self.scale, 3), "bold": self.bold,
        }
        if self.rowspan > 1:
            out["rowspan"] = self.rowspan
        return out


@dataclass
class Merge:
    """A rectangle of the table that is ONE cell, however many it covers.

    Declared rather than inferred. A ruled table draws a vertical at every
    column boundary and a rule between every pair of rows; a merged cell is the
    statement that some of those lines are not there, and the only thing that
    can make that statement is the emitter that decided to span the columns in
    the first place. Inferring it from a wide cell instead would guess -- an
    item name that happens to run long is not a merged cell, and a merged cell
    holding no text is still one.

    Rows and columns are the grid's own, half-open: rows `[row0, row1)` and
    columns `[col0, col1)`. `_paint_bars` drops the verticals strictly inside
    it and `_rule_row` drops the horizontals, which between them is the whole
    of what a merge looks like on paper.
    """

    row0: int
    col0: int
    row1: int
    col1: int

    def holds_column(self, position: float) -> bool:
        """Is a vertical at `position` swallowed by this merge?

        Strictly inside: the boundaries a merge stands between are still drawn,
        or the cell would have no left and right edge of its own.
        """
        return self.col0 < position < self.col1

    def holds_row(self, row: float) -> bool:
        """Is a horizontal along `row` swallowed by this merge?"""
        return self.row0 < row < self.row1

    def to_dict(self) -> dict[str, Any]:
        return {"row0": self.row0, "col0": self.col0,
                "row1": self.row1, "col1": self.col1}


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
    # Which rectangles of the ruled table are single cells. Empty for a layout
    # that merges nothing; carried into the label because "these six columns
    # are one cell" is a fact about the table's structure that no reader can
    # recover from the pixels once the lines that would have divided them were
    # never drawn.
    merges: list[Merge] = field(default_factory=list)
    # What this page's dice gave the table -- see `_sample_variation`. Recorded
    # so a run can be read back by the variant it drew rather than by eye.
    table_style: dict[str, Any] = field(default_factory=dict)
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
        if self.merges:
            out["merges"] = [merge.to_dict() for merge in self.merges]
        if self.table_style:
            out["table_style"] = dict(self.table_style)
        if self.sheet:
            out["sheet"] = self.sheet
        return out

    def table_label(self) -> dict[str, Any] | None:
        """What the table is, for the label -- `None` when there is nothing to say.

        Two things a reader of the image cannot recover and a training target
        needs. Which rectangles are one cell: once the lines inside a merge are
        not drawn, no amount of looking at the pixels says whether six columns
        were merged or the words simply ran long. And what the page's dice gave
        the table, so a run can be sliced by "the pages with a two-level head"
        without re-deriving it from the picture.

        Returned as its own key rather than folded into `ground_truth`: that is
        a CORD-style parse of the *document*, and the structure of the table is
        not part of what the document says.
        """
        label: dict[str, Any] = {}
        if self.table_style:
            label["style"] = dict(self.table_style)
        if self.merges:
            label["merges"] = [merge.to_dict() for merge in self.merges]
        return label or None


def load_layout(layout_id: str, root: Path | str = LAYOUTS_ROOT) -> dict[str, Any]:
    path = Path(root) / f"{layout_id}.yaml"
    if not path.exists():
        available = ", ".join(sorted(p.stem for p in Path(root).glob("*.yaml")))
        raise FileNotFoundError(f"no layout {layout_id!r} in {root}; have {available}")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def available(root: Path | str = LAYOUTS_ROOT) -> list[str]:
    return sorted(path.stem for path in Path(root).glob("*.yaml"))


class _Builder:
    """Accumulates cells row by row. Every emitter below goes through this."""

    def __init__(self, ncols: int, ruled: bool = False):
        self.ncols = ncols
        self.row = 0
        self.cells: list[Cell] = []
        self.marks: list[Mark] = []
        self.merges: list[Merge] = []
        # `rules: marks` in the layout. Off by default, so every layout that
        # does not ask draws exactly the characters it drew before.
        self.ruled = ruled

    def mark(self, kind, row0, col0, row1, col1, weight=1.0, tone=1.0,
             colour=None) -> None:
        # Degenerate on *both* axes is a point: it draws nothing, and a table
        # with no body rows produces one per column boundary. Dropped rather
        # than emitted, so the label never carries a primitive with no extent.
        if row0 == row1 and col0 == col1:
            return
        self.marks.append(Mark(kind, row0, col0, row1, col1, weight, tone, colour))

    def merge(self, row0: int, col0: int, row1: int, col1: int) -> None:
        """Declare `[row0, row1) x [col0, col1)` to be one cell of the table.

        Recorded even on an ASCII layout, where it draws nothing: the merge is
        a fact about the table, and a label that described the structure only
        when the lines happened to be drawn would describe two different tables
        under one layout id.
        """
        if row1 <= row0 or col1 <= col0:
            return
        self.merges.append(Merge(int(row0), int(col0), int(row1), int(col1)))

    def swallowed_column(self, position: float, row0: float, row1: float) -> bool:
        """Does a merge cover the whole of a vertical's run at `position`?"""
        return any(m.holds_column(position) and m.row0 <= row0 and row1 <= m.row1
                   for m in self.merges)

    def put(self, text, role, col0=0, col1=None, align="left", scale=1.0,
            bold=False, rowspan=1):
        text = "" if text is None else str(text)
        if not text.strip():
            return
        col1 = self.ncols if col1 is None else col1
        self.cells.append(
            Cell(text, role, self.row, int(col0), int(col1), align, float(scale),
                 bool(bold), max(int(rowspan), 1))
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


def _resolve_column_groups(spec, columns) -> list[dict[str, Any]]:
    """`column_groups:` turned into concrete spans over the resolved columns.

    A group names the columns it covers and gets one title over the lot:

        column_groups:
          - title: "Thuế GTGT"
            over: [vat_rate, vat_amount]
            titles: {vat_amount: "Tiền thuế"}

    `titles:` is what a printed form does once a parent is there: the column
    stops repeating the parent's words. "Thuế GTGT" over "Thuế suất" and "Tiền
    thuế" is a real invoice head; "Thuế GTGT" over "Thuế suất GTGT" and "Tiền
    thuế GTGT" is the same head with the point of it missed. It applies only
    while the group is drawn, so the flat head keeps the full titles it was
    measured with.

    Groups that name a column the layout does not have, or that cover only one
    column, are dropped -- a "group" of one is an ordinary title written twice.
    """
    keys = [column.get("key") for column in columns]
    groups: list[dict[str, Any]] = []
    for raw in spec.get("column_groups") or []:
        over = [key for key in (raw.get("over") or []) if key in keys]
        if len(over) < 2:
            continue
        first, last = _column(columns, over[0]), _column(columns, over[-1])
        if not first or not last or last["col1"] <= first["col0"]:
            continue
        groups.append({
            "title": str(raw.get("title", "")),
            "align": raw.get("align", "center"),
            "keys": set(over),
            "titles": dict(raw.get("titles") or {}),
            "col0": first["col0"],
            "col1": last["col1"],
        })
    return groups


def _emit_column_header(builder, spec, receipt, columns, rng=None) -> None:
    """The titles above the columns, wrapped inside the column they name.

    A thermal receipt's titles are one word and fit; an invoice's are a phrase
    -- "Số Đọc Tháng Trước" over a 14-character column -- and a real form sets
    them over two or three lines rather than letting them run into the next
    column. Wrapping keeps the header the same shape as the printed original
    and keeps every cell inside the columns it claims.

    `column_groups:` adds the other thing a printed head does: a title over
    several columns at once, with the columns' own titles under it and a rule
    between the two. The parent is a cell merged ACROSS its columns and every
    column outside it is a cell merged DOWN both bands, which is the pair of
    merges a two-level header is made of -- and is why this had to wait for
    `_Builder.merge`.
    """
    if not columns or not spec.get("column_header", True):
        return
    groups = _resolve_column_groups(spec, columns)
    bold = spec.get("column_header_bold", False)
    top = builder.row
    # Rows the parent titles take. Wrapped, because "Thuế giá trị gia tăng"
    # over two 12-character columns is not a one-line title.
    band = 0
    for group in groups:
        band = max(band, len(wrap(_case(receipt, group["title"]),
                                  group["col1"] - group["col0"])))

    for group in groups:
        for offset, line in enumerate(wrap(_case(receipt, group["title"]),
                                           group["col1"] - group["col0"])):
            builder.row = top + offset
            builder.put(line, "colgroup", group["col0"], group["col1"],
                        group["align"], bold=bold)
        # No verticals inside the parent: that is what makes it one title over
        # several columns rather than the same words repeated in each of them.
        builder.merge(top, group["col0"], top + band, group["col1"])

    grouped = set().union(*(group["keys"] for group in groups)) if groups else set()
    under: dict[str, str] = {}
    for group in groups:
        under.update(group["titles"])

    # Wrapped first, placed second. The height of the head is the tallest
    # column in it, and a column with no parent is centred against that height
    # -- which cannot be known until every column has been broken into lines.
    laid: list[tuple[dict[str, Any], list[str], int]] = []
    tallest = 1
    for column in columns:
        key = column.get("key")
        title = under.get(key, column.get("title")) if key in grouped else column.get("title")
        if not title:
            continue
        lines = wrap(_case(receipt, str(title)), column["col1"] - column["col0"])
        start = band if key in grouped else 0
        laid.append((column, lines, start))
        tallest = max(tallest, start + len(lines))

    for column, lines, start in laid:
        align = column.get("title_align", column.get("align", "left"))
        # A column with no parent runs the full height of the head and its
        # title is set in the middle of that -- which is where a reader looks
        # for it, and which `Cell.rowspan` is for.
        #
        # The span is `tallest - len(lines) + 1`, not `tallest`: every line of a
        # wrapped title carries the same span, so the block moves down by half
        # the slack and keeps its own line spacing. Giving each line the full
        # height instead centres each line separately, and "Thành tiền chưa có
        # thuế GTGT" comes out as its two lines printed on top of each other.
        rowspan = tallest - len(lines) + 1 if (groups and not start) else 1
        for offset, line in enumerate(lines):
            builder.row = top + start + offset
            builder.put(line, "colhdr", column["col0"], column["col1"], align,
                        bold=bold, rowspan=rowspan)

    if groups:
        for column in columns:
            if column.get("key") not in grouped:
                builder.merge(top, column["col0"], top + tallest, column["col1"])
        # The rule that separates a parent from its children, over the group
        # and nowhere else -- a form does not rule under a column that has no
        # parent, because there is nothing there to separate. It runs bar to
        # bar, taken from the same function the frame's verticals come from so
        # the three meet exactly.
        if builder.ruled:
            bars = _bar_positions(columns, builder.ncols)
            for group in groups:
                left = max([bar for bar in bars if bar <= group["col0"]],
                           default=group["col0"])
                right = min([bar for bar in bars if bar >= group["col1"]],
                            default=group["col1"])
                builder.row = top + band
                builder.mark("rule", top + band, left, top + band, right)

    builder.row = top + tallest



def _item_values(item, receipt) -> dict[str, str]:
    shown_qty = item.display_qty()
    decimals = 3 if shown_qty % 1 else 0
    name = item.name
    barcode = item.barcode
    return {
        "stt": str(item.stt),
        "name": name,
        "qty": quantity(shown_qty, receipt.money_style, decimals),
        "unit_price": receipt.cash(item.display_unit_price()),
        "amount": receipt.cash(item.amount),
        "barcode": barcode,
        # Saigon Co.op prints the barcode and the name on one line.
        "barcode_name": f"{barcode}  {name}".strip(),
        "vat": f"VAT {item.vat_rate}%" if item.vat_rate else "",
        "vat_rate": f"{item.vat_rate}%" if item.vat_rate else "",
        "unit": item.unit,
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


def _spans_columns(entry, columns) -> bool:
    """Does this entry's `span:` really cross a column boundary?

    `span: [amount, amount]` is a one-column cell written the long way and must
    not claim to be a merge -- the boundaries beside it are still its own edges.
    """
    if "span" not in entry:
        return False
    first, last = entry["span"]
    keys = [column.get("key") for column in columns]
    return first in keys and last in keys and keys.index(last) > keys.index(first)


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
        values = _item_values(item, receipt)
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
                    tall = len(lines)
                else:
                    builder.row = base
                    builder.put(fit(text, width), role, col0, col1, align)
                    tall = 1
                # An entry that runs across the columns IS a merged cell, and a
                # framed table has to be told so or it rules the words through.
                if _spans_columns(entry, columns):
                    builder.merge(base, col0, base + tall, col1)
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
        builder.put(fit(invoice.subtitle, builder.ncols), "subtitle", align="center")
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


def _segments(lo: float, hi: float,
              blocked: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """`[lo, hi]` with `blocked` taken out of it -- the line a merge leaves.

    Merging cells is subtraction, not addition: the table already has a line at
    every boundary and a merge is the statement that some of them are missing.
    Doing the subtraction on intervals here means both axes get it from one
    place, and a rule that survives intact comes back as the one interval it
    started as -- so a table that merges nothing emits exactly the marks it
    always did.
    """
    out = [(lo, hi)]
    for cut0, cut1 in sorted(blocked):
        kept: list[tuple[float, float]] = []
        for start, end in out:
            if cut1 <= start or cut0 >= end:
                kept.append((start, end))
                continue
            if cut0 > start:
                kept.append((start, cut0))
            if cut1 < end:
                kept.append((cut1, end))
        out = kept
    return [(start, end) for start, end in out if end > start]


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
        #
        # A cell merged DOWN the table swallows the row rules that would
        # otherwise cross it -- that is what makes it one cell rather than
        # several holding the same word.
        blocked = [(m.col0, min(m.col1, col1 - 1))
                   for m in builder.merges if m.holds_row(builder.row)]
        for start, end in _segments(col0, col1 - 1, blocked):
            builder.mark("rule", builder.row, start, builder.row, end)
        return
    line = [char] * (col1 - col0)
    for position in positions:
        if col0 <= position < col1:
            line[position - col0] = junction
    builder.put("".join(line), "sep", col0, col1, "left")
    builder.newline()


def _close_block_top(builder, top: float, col0: float, col1: float) -> None:
    """The rule a framed block hangs from, unless the block above already drew it.

    A framed block used to assume it: the totals box on the water bill starts
    on the very row the item table's closing rule sits on, so its top was that
    rule and nothing had to be drawn. The assumption is false wherever a blank
    row separates the two -- the totals box of `invoice_export` and the "Số
    tiền bằng chữ" box of `invoice_vat_summary` were both drawn open at the
    top, two verticals and a bottom rule with no lid, on every page of those
    layouts.

    Checked rather than always drawn, because where the assumption does hold a
    second rule on the same row is a second mark for one line -- twice the ink
    at that boundary in every renderer, and a duplicate in the label.
    """
    if not builder.ruled:
        return
    if any(mark.kind == "rule" and mark.row0 == mark.row1 == top
           and mark.col0 <= col0 and col1 <= mark.col1 for mark in builder.marks):
        return
    builder.mark("rule", top, col0, top, col1)


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
        # One mark per boundary per unbroken run, instead of one `|` cell per
        # row per boundary.
        #
        # The run is broken by a merge. A drawn line passes BEHIND text rather
        # than overwriting it, which is why this used to paint each vertical
        # over the table's whole height and call the job done -- and it is
        # exactly wrong for a cell that spans its columns. The water bill names
        # its tariff band across all six meter columns, and the frame drew five
        # verticals straight through the words: "Tiền nước sin|h hoạt bậc 1
        # |(0-10m3)". A merged cell has no lines inside it; that is what merged
        # means.
        row0, row1 = span if span else (first, last)
        for position in positions:
            blocked = [(max(m.row0, row0), min(m.row1, row1))
                       for m in builder.merges if m.holds_column(position)]
            for start, end in _segments(row0, row1, blocked):
                builder.mark("rule", start, position, end, position)
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


def _shade_band(builder, settings, top: int, col0: int, col1: int,
                bottom: int | None = None) -> None:
    """The tint a printed form lays under a band of rows.

    Under the column titles, and under the line the reader is meant to find
    first -- the amount owed. Both are the same primitive over a different band,
    which is the whole reason `Mark` has a `tone`.

    Off unless the layout asks (`shade:` is a fraction of the page's ink), and
    unavailable to an ASCII layout at all: a till roll can print a line of `-`
    and cannot print a grey box, so a thermal receipt that asked for one would
    be drawn something its real printer could not produce.

    `fill:` is the same band in a colour of its own rather than in a dilution of
    the page's ink. It is a separate key because it means something different:
    `shade:` is how heavily the press inked the band, `fill:` is which ink it
    used, and a bill printed with a blue header over black type is the second.
    Given both, the colour wins -- there is no sense in which a band is 8% blue.
    """
    bottom = builder.row if bottom is None else bottom
    if not builder.ruled or bottom <= top:
        return
    colour = settings.get("fill") or None
    tone = float(settings.get("shade", 0) or 0)
    if colour:
        builder.mark("fill", top, col0, bottom, col1, tone=1.0, colour=str(colour))
    elif tone > 0:
        builder.mark("fill", top, col0, bottom, col1, tone=tone)


def _zebra_band(builder, settings, top: int, col0: int, bottom: int,
                col1: int) -> None:
    """Every other body row in a tint -- what a long printed table does.

    Not decoration: a table of twenty ruled rows is read across, and the band
    is what stops the eye dropping a line. It is the third caller of the same
    `fill`, over a different rectangle again.
    """
    stripe = settings.get("zebra") or None
    if not builder.ruled or not stripe or bottom <= top:
        return
    builder.mark("fill", top, col0, bottom, col1, tone=1.0, colour=str(stripe))


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

    row_rules = table.get("row_rules")
    # One item is one band of the zebra, however many rows its template spends:
    # striping by row would cut a two-line item in half and stripe nothing.
    band = {"top": builder.row, "index": 0}

    def after_item() -> None:
        if band["index"] % 2:
            _zebra_band(builder, table, band["top"], positions[0],
                        builder.row, positions[-1])
        band["top"] = builder.row
        band["index"] += 1
        if row_rules:
            _rule_row(builder, positions)

    after = after_item if (row_rules or table.get("zebra")) else None
    _emit_item_rows(builder, spec, receipt, columns, after_item=after)
    for _ in range(int(table.get("blank_rows", 0))):
        builder.newline()
        if row_rules:
            _rule_row(builder, positions)
    if not row_rules:
        _rule_row(builder, positions)
    _paint_bars(builder, positions, top + 1, builder.row - 1, span=(top, builder.row))
    _outline(builder, table, top, positions[0], builder.row, positions[-1])


def _totals_divider(builder, columns) -> int:
    """The one vertical the totals block keeps, in the item table's own units.

    It has to be the *same* character column the table above rules, and the
    only way to guarantee that is to ask the same function. Computing it here
    as `money_col["col0"] - 1` -- which is what this did -- lands one character
    to the right of `_bar_positions` for any layout with a gutter wider than 1,
    and every ruled invoice here has `gutter: 3`. The result was a table whose
    right-hand rule visibly stepped sideways where the items ended and the
    totals began, on six of the nine framed layouts.
    """
    if len(columns) >= 2:
        return _bar_positions(columns, builder.ncols)[-2]
    return builder.ncols * 2 // 3


def _emit_framed_totals(builder, spec, receipt, columns, rng) -> None:
    """Totals as rows of the table, which is where a VAT invoice prints them.

    One vertical only, before the money: the label runs the width of the sheet
    ("Phí BVMT đối với nước thải SH 10%") and a full set of columns under it
    would cut it in three. That label is a cell merged across every column the
    table above it rules, and it is declared as one.
    """
    settings = spec.get("totals", {})
    money_col = columns[-1] if columns else None
    divider = _totals_divider(builder, columns)
    positions = [0, divider, builder.ncols - 1]
    # The amount sits in the item table's money column, not in "whatever is
    # left of the sheet", so a total lines up with the amounts above it.
    money0 = money_col["col0"] if money_col else divider + 1
    money1 = money_col["col1"] if money_col else builder.ncols - 2
    top = builder.row
    _close_block_top(builder, top, positions[0], positions[-1])
    for index, (label, value) in enumerate(receipt.totals):
        is_grand = settings.get("emphasise_grand", True) and index == receipt.grand_index
        role = "total.grand" if is_grand else "total.line"
        band = builder.row
        builder.put(fit(label, divider - 3), f"{role}.label", 2, divider, "left",
                    bold=is_grand)
        builder.put(fit(value, money1 - money0), role, money0, money1, "right",
                    bold=is_grand)
        builder.merge(band, 0, band + 1, divider)
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
    if framed:
        _close_block_top(builder, top, 0, builder.ncols - 1)
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


def _draw_knob(knob: Any, rng: random.Random) -> Any:
    """One value out of one knob of a `variation:` block.

    Two shapes, because there are two kinds of thing to vary:

    * `{range: [lo, hi]}` -- a number. Integer bounds give an integer, so
      `blank_rows` stays a row count and `border` stays a pen width.
    * a weighted list, `[{value: ..., weight: n}, ...]` -- anything else,
      including `value: ~` for "this page does not have one". Weights are the
      same currency as the rest of the rule-base, so the mix is tuned by
      editing numbers and nothing else.
    """
    if isinstance(knob, dict) and "range" in knob:
        lo, hi = knob["range"]
        if isinstance(lo, int) and isinstance(hi, int):
            return rng.randint(lo, hi)
        return round(rng.uniform(float(lo), float(hi)), 3)
    if isinstance(knob, list) and knob and isinstance(knob[0], dict):
        values = [entry.get("value") for entry in knob]
        weights = [float(entry.get("weight", 1)) for entry in knob]
        if sum(weights) <= 0:
            return values[0]
        return rng.choices(values, weights=weights)[0]
    return knob


VARIATION_PRESETS = Path(__file__).resolve().parent / "rules" / "_table_variation.yaml"

_PRESETS: dict[str, dict[str, Any]] | None = None


def _preset(name: str) -> dict[str, Any]:
    """A named block of knobs from `rules/_table_variation.yaml`.

    Shared rather than copied into each layout file. Nine ruled forms want the
    same answer to "how much does a printed table vary", and nine copies of it
    is nine places to edit and eight places to forget -- the same reason the
    weights live in one rules file and not in the sampler.

    Named with a leading underscore so `load_rules` steps over it: this varies
    how a table is ruled, not what the page is, and it is not a seventh
    attribute however much it looks like one.
    """
    global _PRESETS
    if _PRESETS is None:
        raw = yaml.safe_load(VARIATION_PRESETS.read_text(encoding="utf-8")) or {}
        _PRESETS = raw.get("presets") or {}
    if name not in _PRESETS:
        raise KeyError(
            f"no table variation preset {name!r} in {VARIATION_PRESETS.name}; "
            f"have {', '.join(sorted(_PRESETS))}"
        )
    return _PRESETS[name]


def _sample_variation(spec: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Roll this page's table style, and fold it into the spec it overrides.

    A layout file measured off one photograph describes one printed form. Two
    hundred pages of that form differ only in the words, and a model trained on
    them learns the form rather than the reading of it -- so `variation:` says
    which parts of the ruling are the layout and which are that day's printer:
    the weight of the frame, how many blank rows were left, whether the head
    was tinted and in what colour, whether the body was striped, whether the
    two-level head was used at all.

    The dice are the page's own `rng`, so a seed still reproduces its page
    exactly -- the variation is part of what the seed decides, not noise on top
    of it. And they are only rolled for a layout that declares the block, which
    is why the five thermal receipts draw identically to before: they consume
    no numbers from the stream.

    `column_groups` is the one knob that is not a table setting; it turns the
    two-level head off by emptying the list the header emitter reads.
    """
    knobs = (spec.get("table") or {}).get("variation")
    if not knobs:
        return {}
    if isinstance(knobs, str):
        knobs = _preset(knobs)
    drawn = {key: _draw_knob(knob, rng) for key, knob in sorted(knobs.items())}
    # The knob is rolled for every layout that shares the preset, but most of
    # them declare no groups for it to turn off. Recording the roll anyway puts
    # `column_groups: true` in the label of a page that has a one-level head,
    # which is a label saying something the picture does not. Dropped after the
    # draw, never before it: skipping the draw would move the rng stream for
    # those layouts and change pages that have nothing to do with groups.
    if not spec.get("column_groups"):
        drawn.pop("column_groups", None)

    table = dict(spec.get("table") or {})
    for key, value in drawn.items():
        if key == "column_groups":
            if not value:
                spec["column_groups"] = []
            continue
        table[key] = value
    table.pop("variation", None)
    spec["table"] = table

    # `border` is the pen the outer boundary is drawn with, and the totals block
    # is the same boundary continued. Left out, a page would draw a 2.4-hairline
    # table and hang a 1.8-hairline totals box off the bottom of it.
    if "border" in drawn:
        for section in ("totals", "vat_summary"):
            if isinstance(spec.get(section), dict):
                spec[section] = {**spec[section], "border": drawn["border"]}
    return drawn


def build_grid(receipt: Receipt, layout_id: str, rng: random.Random | None = None,
               root: Path | str = LAYOUTS_ROOT) -> Grid:
    """Lay `receipt` out per `layout_id`."""
    rng = rng or random.Random(0)
    spec = load_layout(layout_id, root)
    table_style = _sample_variation(spec, rng)

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
        merges=builder.merges,
        table_style=table_style,
        sheet=sheet,
    )


__all__ = [
    "Cell", "DEFAULT_SECTIONS", "Grid", "LAYOUTS_ROOT", "Mark", "Merge",
    "SECTIONS", "available", "build_grid", "load_layout",
]
