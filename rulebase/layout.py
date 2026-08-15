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
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .content import Receipt
from .text import apply_case, fit, money, quantity, wrap

LAYOUTS_ROOT = Path(__file__).resolve().parent / "layouts"

SEPARATORS = ["-", "=", "*", ".", "~", "_"]


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "layout": self.layout_id,
            "ncols": self.ncols,
            "nrows": self.nrows,
            "cells": [cell.to_dict() for cell in self.cells],
        }


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

    def __init__(self, ncols: int):
        self.ncols = ncols
        self.row = 0
        self.cells: list[Cell] = []

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
        self.put(char * max(width, 4), "sep", 0, self.ncols, "center")
        self.newline()


def _resolve_columns(spec: dict[str, Any], ncols: int) -> list[dict[str, Any]]:
    """Give every column a concrete [col0, col1) in characters.

    Widths in the spec are relative weights; the name column takes whatever is
    left. Doing it here rather than in the YAML means one layout works at 32
    columns and at 48 without a second set of numbers.
    """
    columns = [dict(column) for column in spec.get("columns", [])]
    if not columns:
        return []
    gutter = int(spec.get("gutter", 1))
    fixed = sum(int(column["width"]) for column in columns if column.get("key") != "name")
    cursor = 0
    for index, column in enumerate(columns):
        if column.get("key") == "name":
            width = max(ncols - fixed, 8)
        else:
            width = int(column["width"])
        column["col0"] = cursor
        cursor = min(cursor + width, ncols)
        # Every column but the last gives up its last character, so a
        # right-aligned number never touches the column that follows it --
        # "112,000BUN BO HUE" is what happens without this.
        column["col1"] = cursor - gutter if index < len(columns) - 1 else cursor
    columns[-1]["col1"] = ncols
    return columns


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


def _emit_header(builder, spec, receipt, rng) -> None:
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

    for line in spec.get("notes", []):
        builder.put(_case(receipt, line), "note", align="center")
        builder.newline()


def _emit_meta(builder, spec, receipt, rng) -> None:
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


def _emit_column_header(builder, spec, receipt, columns) -> None:
    if not columns or not spec.get("column_header", True):
        return
    for column in columns:
        title = column.get("title")
        if title:
            builder.put(_case(receipt, title), "colhdr", column["col0"], column["col1"],
                        column.get("align", "left"), bold=spec.get("column_header_bold", False))
    builder.newline()


def _item_values(item, receipt) -> dict[str, str]:
    shown_qty = item.display_qty()
    decimals = 3 if shown_qty % 1 else 0
    name = item.name
    barcode = item.barcode
    return {
        "stt": str(item.stt),
        "name": name,
        "qty": quantity(shown_qty, receipt.money_style, decimals),
        "unit_price": money(item.display_unit_price(), receipt.money_style),
        "amount": money(item.amount, receipt.money_style),
        "barcode": barcode,
        # Saigon Co.op prints the barcode and the name on one line.
        "barcode_name": f"{barcode}  {name}".strip(),
        "vat": f"VAT {item.vat_rate}%" if item.vat_rate else "",
        "unit": item.unit,
        "note": item.note,
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
            builder.put(f"{label} {money(item.original_price, receipt.money_style)}",
                        "menu.originalprice", 3, builder.ncols, "left")
            builder.newline()

        if item.discount:
            entry = spec.get("item", {}).get("discount_row", {})
            label = _case(receipt, entry.get("label", "KM"))
            builder.put(label, "menu.discount.label", 0, builder.ncols // 2, "left")
            builder.put(money(-abs(item.discount), receipt.money_style),
                        "menu.discountprice", builder.ncols // 2, builder.ncols, "right")
            builder.newline()

    builder.rule(rng, spec.get("rule_char"))


def _emit_totals(builder, spec, receipt, rng) -> None:
    """Totals, with the grand total set larger when the layout says so.

    The grand total is the one `content.build` marked, not the last line: a
    receipt usually goes on to print what the customer handed over and what
    came back, and setting the change in 1.6x bold is not what a till does.
    """
    settings = spec.get("totals", {})
    for index, (label, value) in enumerate(receipt.totals):
        is_grand = settings.get("emphasise_grand", True) and index == receipt.grand_index
        role = "total.grand" if is_grand else "total.line"
        scale = rng.uniform(*settings.get("grand_scale", [1.2, 1.6])) if is_grand else 1.0

        if is_grand and settings.get("grand_two_lines") and rng.random() < 0.5:
            builder.put(label, f"{role}.label", align="center", scale=scale, bold=True)
            builder.newline(2)
            builder.put(value, role, align="right", scale=scale, bold=True)
            builder.newline(2)
            continue

        # Give the label whatever the amount does not need. Splitting at the
        # midpoint truncates "Ví điện tử của VinID Pay" to "Ví điện tử của VinID P".
        split = max(builder.ncols - len(value) - 1, builder.ncols // 3)
        builder.put(fit(label, split), f"{role}.label", 0, split, "left",
                    scale=scale, bold=is_grand)
        builder.put(value, role, split, builder.ncols, "right",
                    scale=scale, bold=is_grand)
        builder.newline(2 if is_grand and scale > 1.3 else 1)


def _emit_footer(builder, spec, receipt, rng) -> None:
    if not receipt.footer:
        return
    builder.newline()
    if spec.get("footer", {}).get("rule_before", False):
        builder.rule(rng, spec.get("rule_char"))
    for line in receipt.footer:
        for wrapped in wrap(line, builder.ncols):
            builder.put(wrapped, "footer", align="center")
            builder.newline()


def build_grid(receipt: Receipt, layout_id: str, rng: random.Random | None = None,
               root: Path | str = LAYOUTS_ROOT) -> Grid:
    """Lay `receipt` out per `layout_id`."""
    rng = rng or random.Random(0)
    spec = load_layout(layout_id, root)

    width_range = spec.get("width", [38, 46])
    ncols = rng.randint(int(width_range[0]), int(width_range[1]))
    columns = _resolve_columns(spec, ncols)

    builder = _Builder(ncols)
    _emit_header(builder, spec, receipt, rng)
    _emit_meta(builder, spec, receipt, rng)
    _emit_column_header(builder, spec, receipt, columns)
    _emit_items(builder, spec, receipt, columns, rng)
    _emit_totals(builder, spec, receipt, rng)
    _emit_footer(builder, spec, receipt, rng)

    return Grid(
        cells=builder.cells,
        ncols=ncols,
        nrows=builder.row + 1,
        layout_id=layout_id,
        columns=columns,
    )


__all__ = ["Cell", "Grid", "LAYOUTS_ROOT", "available", "build_grid", "load_layout"]
