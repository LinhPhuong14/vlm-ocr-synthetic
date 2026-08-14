"""Shared corpus: the text and the rules every sample follows.

**Content carries no layout.** A cell or a block holds the words and
nothing else -- no padding spaces to line columns up, no tabs, no manual
right-alignment. Alignment is structural: it lives in the table's
``column_widths`` / ``column_align``, which both backends read.

That rule exists because the two backends disagree about whitespace.
Pillow lays out glyph runs; a browser collapses or preserves runs of spaces
depending on ``white-space``, and a proportional font makes "aligned"
padding drift anyway. A string like ``"TIỀN MẶT        537,000"`` therefore
renders as two different documents. Structure renders as one.

``assert_plain_text`` enforces it, and ``tests/test_corpus.py`` runs it over
every shipped sample.
"""

from __future__ import annotations

import re

from ..schemas.document import Document

# Two or more spaces, or any tab -- someone laying out with whitespace.
LAYOUT_WHITESPACE = re.compile(r"[ ]{2,}|\t")

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


def iter_text(document: Document):
    """Every piece of content in a document, block text and table cells."""
    for block in document.blocks:
        if block.content:
            yield block.content
        if block.table is not None:
            for row in block.table.rows:
                for cell in row.cells:
                    if cell.content:
                        yield cell.content


def layout_whitespace_offenders(document: Document) -> list[str]:
    """Content strings that try to lay themselves out with whitespace."""
    return [text for text in iter_text(document) if LAYOUT_WHITESPACE.search(text)]


def assert_plain_text(document: Document) -> None:
    """Raise if any content string encodes layout instead of words."""
    offenders = layout_whitespace_offenders(document)
    if offenders:
        raise ValueError(
            "content must not encode layout as whitespace; use table "
            f"column_widths/column_align instead. Offending strings: {offenders}"
        )
