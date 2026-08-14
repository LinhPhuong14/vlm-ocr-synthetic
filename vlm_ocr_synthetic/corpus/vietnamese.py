"""Vietnamese document vocabulary: headings, labels, money, a menu.

Everything a Vietnamese receipt or invoice says, in one place, so a sample
and a generated layout cannot drift apart. Content here is words only --
see :mod:`vlm_ocr_synthetic.corpus.rules` for why.
"""

from __future__ import annotations

# Column headings used by Vietnamese invoices and receipts.
INVOICE_COLUMNS_VI = ("STT", "Tên hàng", "SL", "Đơn giá", "Thành tiền")
INVOICE_COLUMNS_EN = ("No.", "Item", "Qty", "Unit price", "Amount")

# Sensible layout for those five columns: a narrow line number, a wide item
# name, money on the right.
# The last column has to fit "Thành tiền" without wrapping in either
# backend; bold headings in a browser are wider than the glyph run Pillow
# measures, so the width is set for the wider of the two.
INVOICE_COLUMN_WIDTHS = (0.08, 0.37, 0.08, 0.21, 0.26)
INVOICE_COLUMN_ALIGN = ("center", "left", "center", "right", "right")

LABELS_VI = {
    "table_no": "BÀN SỐ",
    "cash": "TIỀN MẶT",
    "total": "TỔNG CỘNG",
    "change": "TIỀN THỐI",
    "thanks": "CẢM ƠN QUÝ KHÁCH",
    "see_you": "HẸN GẶP LẠI!",
}


def format_dong(amount: int) -> str:
    """Vietnamese money formatting: thousands separated by a comma."""
    return f"{amount:,}"


# Dishes to draw from when generating an order. Prices are realistic
# per-unit amounts in dong.
MENU: tuple[tuple[str, int], ...] = (
    ("Bún Sinh", 42_000),
    ("Mì Giòn Xào Chay", 37_000),
    ("Mì Xào Giòn Nhỏ", 40_000),
    ("Cơm Bát Bửu", 43_000),
    ("Sườn Chiên Kho Đỏ", 65_000),
    ("Hủ Tiếu Nhỏ", 40_000),
    ("Tôm Lăn Bột", 65_000),
    ("Phở Bò Tái", 55_000),
    ("Gỏi Cuốn Tôm Thịt", 35_000),
    ("Chả Giò Hải Sản", 48_000),
    ("Canh Chua Cá Lóc", 72_000),
    ("Rau Muống Xào Tỏi", 30_000),
    ("Cơm Chiên Dương Châu", 58_000),
    ("Pepsi", 8_000),
    ("Trà Đá", 2_000),
    ("Bia Sài Gòn", 22_000),
)
