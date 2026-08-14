"""Shared text, and the rule that keeps layout out of it."""

from .rules import (
    LAYOUT_WHITESPACE,
    assert_plain_text,
    iter_text,
    layout_whitespace_offenders,
)
from .vietnamese import (
    INVOICE_COLUMN_ALIGN,
    INVOICE_COLUMN_WIDTHS,
    INVOICE_COLUMNS_EN,
    INVOICE_COLUMNS_VI,
    LABELS_VI,
    MENU,
    format_dong,
)

__all__ = [
    "INVOICE_COLUMNS_EN",
    "INVOICE_COLUMNS_VI",
    "INVOICE_COLUMN_ALIGN",
    "INVOICE_COLUMN_WIDTHS",
    "LABELS_VI",
    "LAYOUT_WHITESPACE",
    "MENU",
    "assert_plain_text",
    "format_dong",
    "iter_text",
    "layout_whitespace_offenders",
]
