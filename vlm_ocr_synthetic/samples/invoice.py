"""A small invoice page used as the smoke-test document for every backend."""

from __future__ import annotations

from ..schemas.document import (
    BBox,
    BlockType,
    Document,
    DocumentBlock,
    TableBlock,
    TableCell,
    TableRow,
)


def build_invoice_table() -> TableBlock:
    return TableBlock(
        rows=[
            TableRow(
                cells=[
                    TableCell(content="Item", is_header=True),
                    TableCell(content="Qty", is_header=True),
                    TableCell(content="Price", is_header=True),
                ]
            ),
            TableRow(
                cells=[
                    TableCell(content="Apple"),
                    TableCell(content="2"),
                    TableCell(content="$10"),
                ]
            ),
            TableRow(
                cells=[
                    TableCell(content="Banana"),
                    TableCell(content="3"),
                    TableCell(content="$15"),
                ]
            ),
        ],
        column_widths=(0.5, 0.2, 0.3),
        column_align=("left", "center", "right"),
        bbox=BBox(x1=100, y1=300, x2=900, y2=700),
    )


def build_invoice_document() -> Document:
    return Document(
        page_width=1000,
        page_height=1400,
        blocks=[
            DocumentBlock(
                block_type=BlockType.PAGE_HEADER,
                content="INVOICE",
                bbox=BBox(x1=100, y1=50, x2=900, y2=120),
            ),
            DocumentBlock(
                block_type=BlockType.TEXT,
                content="Invoice No: INV-001",
                bbox=BBox(x1=100, y1=180, x2=500, y2=230),
            ),
            DocumentBlock(
                block_type=BlockType.TABLE,
                table=build_invoice_table(),
                bbox=BBox(x1=100, y1=300, x2=900, y2=700),
            ),
            DocumentBlock(
                block_type=BlockType.FOOTNOTE,
                content="* Prices include tax.",
                bbox=BBox(x1=100, y1=1200, x2=900, y2=1250),
            ),
        ],
    )
