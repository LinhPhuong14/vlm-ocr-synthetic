"""Preflight: the gate every job passes through.

Only the parts that need no font library live here; glyph coverage is checked
by running the tool, because it needs fontTools and the point of the pytest
suite is that it needs nothing.
"""

from __future__ import annotations

import pipeline.preflight as preflight


def test_printable_text_includes_the_uppercase_forms():
    """The expansion that makes the font check worth running.

    A corpus entry is stored lowercase and printed upper roughly half the time,
    and `Ậ Ầ Ế Ộ Ữ` are different codepoints from their lowercase forms. Checked
    against lowercase only, a font missing every uppercase accent passes -- and
    prints boxes for exactly the characters most often absent. Measured: 33
    characters in this rule-base are reachable *only* through `.upper()`.
    """
    characters = preflight.printable_text()
    for upper in "ẦẨẪẮẰẴẺỂỄỈỌỎỒỖỚỞỠỢỤỦỪỬỮỰỲỶỸ":
        assert upper in characters, f"{upper!r} is printable but not checked"


def test_printable_text_includes_the_folded_forms():
    characters = preflight.printable_text()
    for plain in "AEIOUDaeioud":
        assert plain in characters


def test_printable_text_includes_layout_and_rule_strings():
    # Column titles and total labels live in the YAML, not the corpus. A 2011
    # ASCII till once printed "Số lượng" over a folded page because these were
    # not going through the same treatment.
    characters = preflight.printable_text()
    for character in "SốlượngGiáTiền":
        assert character in characters, f"{character!r} from a layout title is unchecked"


def test_printable_text_covers_money_and_separators():
    characters = preflight.printable_text()
    for character in "0123456789.,-đĐ":
        assert character in characters


def test_font_coverage_never_shrugs(monkeypatch, tmp_path):
    """Empty font directory, or no font library: either way it reports."""
    monkeypatch.setattr(preflight, "FONT_ROOT", tmp_path)
    problems = preflight.font_coverage({"a"})
    assert problems, "an empty assets/fonts/ produced no problem at all"


def test_the_shipped_repository_is_clean():
    """Nothing wrong -- excluding checks this interpreter could not run.

    The pytest environment deliberately has neither numpy nor fontTools, so the
    chain and glyph checks report themselves as `unchecked:`. Those are filtered
    here and nowhere else: `make preflight` still exits non-zero on them, which
    is what stops a job starting half-verified.
    """
    problems = preflight.check()
    real = [p for p in problems if p not in preflight.unchecked(problems)]
    assert real == [], "\n".join(real)
