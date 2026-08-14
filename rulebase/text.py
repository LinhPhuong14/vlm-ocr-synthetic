"""Text helpers every backend shares.

Formatting lives here rather than in a renderer because the same receipt has
to come out identical whether it is drawn glyph by glyph or laid out in HTML.
If money were formatted twice -- once in the synthdog element, once in a
Jinja filter -- the two would drift and the labels would stop matching one of
the images.
"""

from __future__ import annotations

import re
import unicodedata

# How a till prints an amount. Every style seen on the sample receipts:
#   dot        56.000        quán nhậu, VinCommerce
#   comma      20,200        WinMart, máy in nhiệt đời cũ
#   comma_2dp  33,600.00     Saigon Co.op
MONEY_STYLES = ("dot", "comma", "comma_2dp")


def ascii_fold(text: str) -> str:
    """Drop Vietnamese diacritics -- old thermal printers only had ASCII.

    One-way on purpose: the corpus is stored with diacritics and folded at
    render time, never the reverse, because "Hen gap lai" has no unique
    accented original.
    """
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", text)


def money(value: float, style: str = "dot", suffix: str = "") -> str:
    """Format an amount the way a Vietnamese till does."""
    negative = value < 0
    value = abs(value)
    if style == "comma_2dp":
        body = f"{value:,.2f}"
    elif style == "comma":
        body = f"{int(round(value)):,}"
    elif style == "dot":
        body = f"{int(round(value)):,}".replace(",", ".")
    else:
        raise ValueError(f"unknown money style {style!r}; have {', '.join(MONEY_STYLES)}")
    return ("-" if negative else "") + body + suffix


def quantity(value: float, style: str = "dot", decimals: int = 0) -> str:
    """Quantities follow the same separators as money.

    Weighed goods print a fractional quantity with the decimal comma the
    thousands separator is not using -- "0,950 KG" next to "157.500/KG".
    """
    if decimals == 0:
        return money(int(round(value)), style)
    text = f"{value:.{decimals}f}"
    whole, _, frac = text.partition(".")
    whole = money(int(whole), style)
    return f"{whole},{frac}" if style == "dot" else f"{whole}.{frac}"


def wrap(text: str, width: int) -> list[str]:
    """Break `text` to `width` columns, keeping the original spacing.

    Deliberately not `textwrap.fill`: that collapses runs of spaces, so the
    glyph backend and the HTML backend would disagree about where a line
    starts. Splitting on the separators and keeping them means both put the
    same characters in the same columns.
    """
    if width < 1:
        return [text]
    lines: list[str] = []
    current = ""
    for token in re.split(r"(\s+)", text):
        if not token:
            continue
        if len(current) + len(token) <= width:
            current += token
            continue
        if token.isspace():
            lines.append(current.rstrip())
            current = ""
            continue
        if current.strip():
            lines.append(current.rstrip())
            current = ""
        while len(token) > width:  # a single word longer than the column
            lines.append(token[:width])
            token = token[width:]
        current = token
    if current.strip():
        lines.append(current.rstrip())
    return lines or [""]


def fit(text: str, width: int) -> str:
    """Hard-truncate to `width`. Use where wrapping would break the grid."""
    return text if len(text) <= width else text[:width]


def apply_case(text: str, upper: bool, fold: bool) -> str:
    if fold:
        text = ascii_fold(text)
    return text.upper() if upper else text
