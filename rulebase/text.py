"""Text helpers the rule-base and every backend share.

Formatting lives here rather than in a renderer because the label and the pixels
must agree on the same string. When there were three renderers this was about
them agreeing with each other; with one it is about the renderer agreeing with
the record. Money formatted twice -- once on the way to the page, once on the
way to `text` -- drifts, and then the label stops matching the image with
nothing raising.
"""

from __future__ import annotations

import re
import unicodedata

# How a till prints an amount. Every style seen on the sample receipts:
#   dot        56.000        quán nhậu, VinCommerce
#   comma      20,200        WinMart, máy in nhiệt đời cũ
#   comma_2dp  33,600.00     Saigon Co.op
#   cents      128.30        an English tax invoice, whose corpus stores cents
MONEY_STYLES = ("dot", "comma", "comma_2dp", "cents")


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


def money(value: float, style: str = "dot", suffix: str = "", prefix: str = "") -> str:
    """Format an amount the way a Vietnamese till does.

    `prefix` goes after the sign and before the digits -- "-$8.30", which is
    where a dollar sign belongs and where a `đ` suffix cannot go.
    """
    negative = value < 0
    value = abs(value)
    if style == "comma_2dp":
        body = f"{value:,.2f}"
    elif style == "cents":
        # The English corpus prices in cents so a unit price is not forced to a
        # round dollar; the invoice prints dollars, so the division happens on
        # the way out and in exactly one place.
        body = f"{value / 100.0:,.2f}"
    elif style == "comma":
        body = f"{int(round(value)):,}"
    elif style == "dot":
        body = f"{int(round(value)):,}".replace(",", ".")
    else:
        raise ValueError(f"unknown money style {style!r}; have {', '.join(MONEY_STYLES)}")
    return ("-" if negative else "") + prefix + body + suffix


def quantity(value: float, style: str = "dot", decimals: int = 0) -> str:
    """Quantities follow the same separators as money.

    Weighed goods print a fractional quantity with the decimal comma the
    thousands separator is not using -- "0,950 KG" next to "157.500/KG".

    `cents` is a money style, not a number style: it divides by a hundred, and
    a quantity of 2 is 2, not 0.02. It borrows `comma`'s separators instead.
    """
    if style == "cents":
        style = "comma"
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


# ------------------------------------------------------- số tiền bằng chữ

# A VAT invoice always writes the amount out in words under the totals, and a
# reader is expected to check the two against each other -- which is why it is
# on the page at all. Generating it here rather than in a layout means the
# glyph render and the two HTML renders spell it identically.
_ONES = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
_SCALES = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ"]


def _read_group(value: int, lead: bool) -> str:
    """One group of three digits. `lead` reads the zeros: 005 -> "không trăm lẻ năm".

    A group after a larger one keeps its zeros -- 1.005.000 is "một triệu không
    trăm lẻ năm nghìn" -- while the leading group drops them, so 133.400 does
    not open with "không trăm".
    """
    hundred, rest = divmod(value, 100)
    ten, unit = divmod(rest, 10)
    parts: list[str] = []
    if hundred or lead:
        parts += [_ONES[hundred], "trăm"]
    if ten == 0:
        if unit and (hundred or lead):
            parts += ["lẻ", _ONES[unit]]
        elif unit:
            parts += [_ONES[unit]]
    elif ten == 1:
        parts.append("mười")
        # "mười lăm", never "mười năm" -- the second is a year.
        if unit == 5:
            parts.append("lăm")
        elif unit:
            parts.append(_ONES[unit])
    else:
        parts += [_ONES[ten], "mươi"]
        # 21 is "hai mươi mốt", 24 "hai mươi tư", 25 "hai mươi lăm": the unit
        # changes its name once it follows a ten.
        parts += [{1: "mốt", 4: "tư", 5: "lăm"}.get(unit, _ONES[unit])] if unit else []
    return " ".join(parts)


def words_vi(amount: float, unit: str = "đồng") -> str:
    """Write an amount out the way the "Số tiền bằng chữ" line does.

    >>> words_vi(133400)
    'Một trăm ba mươi ba nghìn bốn trăm đồng'
    """
    value = int(round(abs(amount)))
    sign = "Âm " if amount < 0 else ""
    if value == 0:
        return f"{sign}Không {unit}".strip()

    groups: list[int] = []
    while value:
        value, group = divmod(value, 1000)
        groups.append(group)
    if len(groups) > len(_SCALES):
        # Past a thousand billion this stops being a receipt; print the digits
        # rather than invent a scale word nobody writes.
        return f"{sign}{money(abs(amount), 'dot')} {unit}".strip()

    spoken: list[str] = []
    for index in range(len(groups) - 1, -1, -1):
        group = groups[index]
        if not group:
            continue
        spoken.append(_read_group(group, lead=index < len(groups) - 1))
        if _SCALES[index]:
            spoken.append(_SCALES[index])

    text = " ".join(" ".join(spoken).split())
    return f"{sign}{text[0].upper()}{text[1:]} {unit}".strip()
