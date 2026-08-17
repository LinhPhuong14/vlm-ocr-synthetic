"""Formatting: diacritic folding, money, wrapping, truncation.

These are the cheapest invariants in the repository and two of the bugs
`docs/huong-dan-va-giai-thich.md` §9 records were exactly here.
"""

from __future__ import annotations

import pytest

from rulebase.text import apply_case, ascii_fold, fit, money, quantity, wrap

# ---------------------------------------------------------------- folding


def test_folding_drops_tone_marks():
    assert ascii_fold("Hẹn gặp lại") == "Hen gap lai"
    assert ascii_fold("Phở bò tái") == "Pho bo tai"


def test_folding_handles_d_with_stroke():
    # Not a combining mark, so NFD does nothing for it -- it needs its own
    # substitution, and forgetting that leaves `đ` on an ASCII-only till.
    assert ascii_fold("Đường Đội Cấn") == "Duong Doi Can"
    assert ascii_fold("đ") == "d"


def test_folding_is_idempotent():
    for text in ("Hẹn gặp lại", "CỬA HÀNG", "Đ", "already ascii", ""):
        assert ascii_fold(ascii_fold(text)) == ascii_fold(text)


def test_folding_is_one_way_but_total():
    # Every folded string must be pure ASCII: anything left behind renders as a
    # box on a printer that has no such glyph, while the label still claims the
    # character was printed.
    for text in ("Phở", "GIẢM GIÁ", "Số 72A đường Hoàng Văn Thụ", "Ừ Ỡ Ẫ Ộ"):
        folded = ascii_fold(text)
        assert folded.isascii(), f"{text!r} folded to {folded!r}"


def test_uppercase_of_folded_stays_ascii():
    # The upper() happens after folding in `apply_case`; a Vietnamese capital
    # re-entering at that point would be the same silent failure.
    assert apply_case("Phở bò", upper=True, fold=True) == "PHO BO"
    assert apply_case("Phở bò", upper=False, fold=True) == "Pho bo"
    assert apply_case("Phở bò", upper=True, fold=False) == "PHỞ BÒ"


# ------------------------------------------------------------------ money


@pytest.mark.parametrize("style,expected", [
    ("comma", "537,000"),
    ("dot", "537.000"),
    ("comma_2dp", "537,000.00"),
])
def test_money_styles(style, expected):
    assert money(537000, style) == expected


def test_money_suffixes():
    assert money(537000, "dot", "đ") == "537.000đ"
    assert money(537000, "comma", " VND") == "537,000 VND"


def test_money_suffix_folds_with_the_rest_of_the_page():
    # A suffix appended after `apply_case` would put `đ` on a page whose every
    # other character had been folded. The rules happen to prevent that pairing
    # today; nothing structural does, so it is pinned here.
    assert ascii_fold(money(537000, "dot", "đ")) == "537.000d"


def test_money_rounds_rather_than_truncates():
    assert money(1499.6, "comma") == "1,500"
    assert money(1499.4, "comma") == "1,499"


def test_money_keeps_the_sign():
    assert money(-64125, "dot") == "-64.125"


def test_unknown_money_style_is_rejected():
    with pytest.raises(ValueError, match="unknown money style"):
        money(1000, "spaces")


def test_quantity_uses_the_other_separator():
    # A till prints "0,950 KG" beside "157.500/KG": whichever character is the
    # thousands separator, the decimal is the other one. Sharing one would make
    # the quantity unreadable.
    assert quantity(0.95, "dot", 3) == "0,950"
    assert quantity(0.95, "comma", 3) == "0.950"
    assert quantity(3, "dot", 0) == "3"


# ----------------------------------------------------------------- fitting


def test_wrap_never_exceeds_the_width():
    text = "Nho đỏ không hạt Mỹ nhập khẩu loại đặc biệt"
    for width in (6, 10, 18, 40):
        assert all(len(line) <= width for line in wrap(text, width))


def test_wrap_keeps_every_word():
    text = "Bún riêu cua đồng"
    assert "".join(wrap(text, 7)).replace(" ", "") == text.replace(" ", "")


def test_wrap_splits_a_word_longer_than_the_column():
    lines = wrap("ABCDEFGHIJKLMNOP", 5)
    assert all(len(line) <= 5 for line in lines)
    assert "".join(lines) == "ABCDEFGHIJKLMNOP"


def test_wrap_of_empty_text_is_one_empty_line():
    assert wrap("", 10) == [""]


def test_fit_truncates_to_the_column():
    assert fit("Ví điện tử của VinID Pay", 10) == "Ví điện tử"
    assert fit("ngắn", 10) == "ngắn"
    assert len(fit("x" * 50, 12)) == 12
