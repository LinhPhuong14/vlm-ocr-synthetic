"""A Vietnamese restaurant receipt, thermal-printer shaped.

Modelled on a real 80mm bill, with the column layout Vietnamese invoices
actually use: STT (line number), item, quantity, unit price, line total.
Only the item name is free text -- every number is derived, so a generated
bill always adds up:

    thành tiền = số lượng x đơn giá
    tổng cộng  = sum(thành tiền)

The text carries full diacritics on purpose: it is the cheapest end-to-end
check that font shaping (Pillow + raqm, and the browser) is not dropping or
mangling Vietnamese marks.
"""

from __future__ import annotations

from typing import NamedTuple

from ..schemas.document import (
    BlockType,
    Document,
    DocumentBlock,
    TableBlock,
    TableCell,
    TableRow,
)

# 80mm thermal paper at 203 dpi is 576 dots wide.
PAGE_WIDTH = 576
PAGE_HEIGHT = 1000

SHOP_NAME = "QUÁN ĂN THIÊN TÂN"
SHOP_ADDRESS = "17-19 Tôn Đản F13 Q4 TPHCM"
SHOP_PHONE = "ĐT: 9407863 - 8259956"

# STT | Tên hàng | SL | Đơn giá | Thành tiền
COLUMN_HEADERS = ("STT", "Tên hàng", "SL", "Đơn giá", "Thành tiền")


class OrderLine(NamedTuple):
    """One row of the bill; the line total is never stored, only derived."""

    name: str
    quantity: int
    unit_price: int

    @property
    def amount(self) -> int:
        return self.quantity * self.unit_price


ORDER: tuple[OrderLine, ...] = (
    OrderLine("Bún Sinh", 1, 42_000),
    OrderLine("Mì Giòn Xào Chay", 1, 37_000),
    OrderLine("Mì Xào Giòn Nhỏ", 2, 40_000),
    OrderLine("Cơm Bát Bửu", 4, 43_000),
    OrderLine("Sườn Chiên Kho Đỏ", 1, 65_000),
    OrderLine("Hủ Tiếu Nhỏ", 1, 40_000),
    OrderLine("Tôm Lăn Bột", 1, 65_000),
    OrderLine("Pepsi", 2, 8_000),
    OrderLine("Trà Đá", 10, 2_000),
)


def format_dong(amount: int) -> str:
    """Vietnamese money formatting: thousands separated by a comma."""
    return f"{amount:,}"


def order_total(order: tuple[OrderLine, ...] = ORDER) -> int:
    return sum(line.amount for line in order)


def build_order_table(order: tuple[OrderLine, ...] = ORDER) -> TableBlock:
    """Header row plus one row per line item, numbered from 1."""
    header = TableRow(
        cells=[TableCell(content=title, is_header=True) for title in COLUMN_HEADERS]
    )

    rows = [
        TableRow(
            cells=[
                TableCell(content=str(index)),
                TableCell(content=line.name),
                TableCell(content=str(line.quantity)),
                TableCell(content=format_dong(line.unit_price)),
                TableCell(content=format_dong(line.amount)),
            ]
        )
        for index, line in enumerate(order, start=1)
    ]

    return TableBlock(rows=[header, *rows])


def build_receipt_document(
    order: tuple[OrderLine, ...] = ORDER,
    table_number: int = 47,
    printed_at: str = "13-11-2011 20:54",
    bill_number: str = "000887",
) -> Document:
    return Document(
        page_width=PAGE_WIDTH,
        page_height=PAGE_HEIGHT,
        blocks=[
            DocumentBlock(block_type=BlockType.PAGE_HEADER, content=SHOP_NAME),
            DocumentBlock(block_type=BlockType.TEXT, content=SHOP_ADDRESS),
            DocumentBlock(block_type=BlockType.TEXT, content=SHOP_PHONE),
            DocumentBlock(block_type=BlockType.TEXT, content="* * * * * * * *"),
            DocumentBlock(
                block_type=BlockType.TEXT,
                content=f"REG        {printed_at}",
            ),
            DocumentBlock(
                block_type=BlockType.TEXT,
                content=f"CA 1        MC #01        {bill_number}",
            ),
            DocumentBlock(
                block_type=BlockType.SECTION_HEADER,
                content=f"BÀN SỐ: {table_number}",
            ),
            DocumentBlock(
                block_type=BlockType.TABLE,
                table=build_order_table(order),
            ),
            DocumentBlock(
                block_type=BlockType.SECTION_HEADER,
                content=f"TIỀN MẶT        {format_dong(order_total(order))}",
            ),
            DocumentBlock(
                block_type=BlockType.FOOTNOTE,
                content="CẢM ƠN QUÝ KHÁCH\nHẸN GẶP LẠI!",
            ),
        ],
    )
