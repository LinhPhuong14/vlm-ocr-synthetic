"""Layout axis: what the page *is* -- geometry, blocks, table shape.

A layout variant's value is a callable ``(rng) -> Document``. Anything that
changes the ground truth belongs here: page size, which blocks exist, how
many rows the table has, what the column headings say. Anything purely
visual (fonts, margins, colours) belongs on the style axis instead.

Layouts also declare the tags styles filter on -- ``thermal`` vs ``a4``,
``narrow`` for 58mm paper, ``pinned`` when the document carries bboxes.
"""

from __future__ import annotations

import random
from collections.abc import Callable

from ..corpus import INVOICE_COLUMNS_EN, INVOICE_COLUMNS_VI, LABELS_VI, MENU
from ..samples.invoice import build_invoice_document
from ..samples.receipt_vn import (
    OrderLine,
    build_receipt_document,
    order_total,
)
from ..schemas.document import Document, TableCell, TableRow
from .space import Axis, Variant

DocumentFactory = Callable[[random.Random], Document]


def sample_order(rng: random.Random, low: int, high: int) -> tuple[OrderLine, ...]:
    """A random order of between ``low`` and ``high`` distinct dishes."""
    size = rng.randint(low, min(high, len(MENU)))
    chosen = rng.sample(MENU, size)
    return tuple(
        OrderLine(name, rng.choice((1, 1, 1, 2, 2, 3, 4, 10)), price)
        for name, price in chosen
    )


def _compact_order_table(document: Document) -> Document:
    """Drop the quantity and unit-price columns.

    58mm paper has room for roughly 32 characters; five columns wrap the
    dish names into three lines each. Real narrow receipts print
    STT / Tên hàng / Thành tiền and leave the arithmetic implicit.
    """
    blocks = []
    for block in document.blocks:
        table = block.table
        if table is not None and table.n_columns == 5:
            rows = [
                TableRow(cells=[row.cells[0], row.cells[1], row.cells[4]])
                for row in table.rows
            ]
            table = table.model_copy(
                update={
                    "rows": rows,
                    "column_widths": (0.10, 0.55, 0.35),
                    "column_align": ("center", "left", "right"),
                }
            )
            block = block.model_copy(update={"table": table})
        blocks.append(block)
    return document.model_copy(update={"blocks": blocks})


def _receipt(
    width: int,
    items: tuple[int, int],
    *,
    register: bool = True,
    footer: bool = True,
    headings: tuple[str, ...] = INVOICE_COLUMNS_VI,
    change: bool = False,
    compact: bool = False,
) -> DocumentFactory:
    """Build a receipt factory with the pieces this layout keeps."""

    def factory(rng: random.Random) -> Document:
        order = sample_order(rng, *items)
        document = build_receipt_document(
            order=order,
            table_number=rng.randint(1, 60),
            bill_number=f"{rng.randrange(1_000_000):06d}",
        )

        blocks = list(document.blocks)
        if not register:
            blocks = [
                block
                for block in blocks
                if block.table is None or block.table.rows[0].cells[0].content != "REG"
            ]
        if not footer:
            blocks = blocks[:-1]

        document = document.model_copy(update={"page_width": width, "blocks": blocks})

        if headings != INVOICE_COLUMNS_VI:
            document = _relabel_headings(document, headings)
        if change:
            document = _add_change_row(document, order, rng)
        if compact:
            document = _compact_order_table(document)
        return document

    return factory


def _relabel_headings(document: Document, headings: tuple[str, ...]) -> Document:
    """Swap the order table's header row, keeping everything else."""
    blocks = []
    for block in document.blocks:
        table = block.table
        if table is not None and table.n_columns == len(headings):
            header = TableRow(
                cells=[
                    cell.model_copy(update={"content": title})
                    for cell, title in zip(table.rows[0].cells, headings)
                ]
            )
            block = block.model_copy(
                update={
                    "table": table.model_copy(update={"rows": [header, *table.rows[1:]]})
                }
            )
        blocks.append(block)
    return document.model_copy(update={"blocks": blocks})


def _add_change_row(
    document: Document, order: tuple[OrderLine, ...], rng: random.Random
) -> Document:
    """Cash tendered and change given, under the total."""
    total = order_total(order)
    tendered = ((total // 50_000) + rng.randint(1, 3)) * 50_000

    blocks = list(document.blocks)
    for position in range(len(blocks) - 1, -1, -1):
        table = blocks[position].table
        if table is None or table.n_columns != 2:
            continue

        rows = [
            *table.rows,
            TableRow(
                cells=[
                    TableCell(content=LABELS_VI["change"]),
                    TableCell(content=f"{tendered - total:,}"),
                ]
            ),
        ]
        blocks[position] = blocks[position].model_copy(
            update={"table": table.model_copy(update={"rows": rows})}
        )
        break

    return document.model_copy(update={"blocks": blocks})


def _invoice(pinned: bool) -> DocumentFactory:
    """The A4 invoice, with or without its pinned bboxes."""

    def factory(rng: random.Random) -> Document:
        document = build_invoice_document()
        if pinned:
            return document

        blocks = [block.model_copy(update={"bbox": None}) for block in document.blocks]
        return document.model_copy(update={"blocks": blocks})

    return factory


# 80mm paper can take a big font; 58mm cannot. Styles filter on these.
THERMAL = frozenset({"thermal", "wide_thermal"})
NARROW = frozenset({"thermal", "narrow"})
A4 = frozenset({"a4", "wide"})

LAYOUTS: tuple[Variant, ...] = (
    Variant("receipt_80mm", _receipt(576, (6, 10)), weight=5, tags=THERMAL),
    Variant("receipt_80mm_short", _receipt(576, (2, 4)), weight=2, tags=THERMAL),
    Variant("receipt_80mm_long", _receipt(576, (12, 16)), weight=2, tags=THERMAL),
    Variant(
        "receipt_80mm_minimal",
        _receipt(576, (3, 6), register=False, footer=False),
        weight=2,
        tags=THERMAL,
    ),
    Variant(
        "receipt_80mm_with_change",
        _receipt(576, (5, 9), change=True),
        weight=2,
        tags=THERMAL,
    ),
    Variant(
        "receipt_80mm_en",
        _receipt(576, (5, 9), headings=INVOICE_COLUMNS_EN),
        weight=1,
        tags=THERMAL,
    ),
    Variant("receipt_58mm", _receipt(384, (4, 7), compact=True), weight=3, tags=NARROW),
    Variant(
        "receipt_58mm_long",
        _receipt(384, (10, 14), compact=True),
        weight=1,
        tags=NARROW,
    ),
    Variant(
        "invoice_a4",
        _invoice(pinned=True),
        weight=3,
        tags=A4 | frozenset({"pinned"}),
    ),
    Variant("invoice_a4_flow", _invoice(pinned=False), weight=2, tags=A4),
)

LAYOUT_AXIS = Axis(name="layout", variants=LAYOUTS)
