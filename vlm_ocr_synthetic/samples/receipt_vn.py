"""A Vietnamese restaurant receipt, thermal-printer shaped.

Modelled on a real 80mm bill: narrow sheet, centred shop block, a
borderless quantity/item/price table, cash total, thank-you footer.  The
text carries full diacritics on purpose -- it is the cheapest end-to-end
check that font shaping (Pillow + raqm, and the browser) is not dropping
or mangling Vietnamese marks.
"""

from __future__ import annotations

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

# (quantity, dish, line total in dong)
ORDER: tuple[tuple[int, str, int], ...] = (
    (1, "Bún Sinh", 42_000),
    (1, "Mì Giòn Xào Chay", 37_000),
    (2, "Mì Xào Giòn Nhỏ", 80_000),
    (4, "Cơm Bát Bửu", 172_000),
    (1, "Sườn Chiên Kho Đỏ", 65_000),
    (1, "Hủ Tiếu Nhỏ", 40_000),
    (1, "Tôm Lăn Bột", 65_000),
    (2, "Pepsi", 16_000),
    (10, "Trà Đá", 20_000),
)


def format_dong(amount: int) -> str:
    """Vietnamese money formatting: thousands separated by a comma."""
    return f"{amount:,}"


def build_order_table(
    order: tuple[tuple[int, str, int], ...] = ORDER,
) -> TableBlock:
    """Quantity / dish / price, with no header row -- like the paper bill."""
    return TableBlock(
        rows=[
            TableRow(
                cells=[
                    TableCell(content=str(quantity)),
                    TableCell(content=dish),
                    TableCell(content=format_dong(price)),
                ]
            )
            for quantity, dish, price in order
        ]
    )


def build_receipt_document(
    order: tuple[tuple[int, str, int], ...] = ORDER,
    table_number: int = 47,
    printed_at: str = "13-11-2011 20:54",
    bill_number: str = "000887",
) -> Document:
    total = sum(price for _, _, price in order)

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
                content=f"TIỀN MẶT        {format_dong(total)}",
            ),
            DocumentBlock(
                block_type=BlockType.FOOTNOTE,
                content="CẢM ƠN QUÝ KHÁCH\nHẸN GẶP LẠI!",
            ),
        ],
    )
