"""How `tools/check_boxes.py` decides a drawn run has a box.

Only the coverage half is exercised here. The other two checks -- every corner
inside the frame, every box on some ink -- need real pixels and are proved by
`make check-boxes` over the committed sets; this is about the comparison that
runs before the image is even opened, because that is the half that produced a
false alarm.

A CSS sheet wraps, so one labelled run can be several boxes. Rejoining them is
not as simple as putting the spaces back, and getting it wrong reports a field
as missing on a page where the box sits squarely on the word.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

# The tool imports both at module level, so the whole file sits out the
# dependency-free CI job rather than half-running.
pytest.importorskip("numpy", reason="check_boxes imports numpy")
pytest.importorskip("cv2", reason="check_boxes imports OpenCV")

import check_boxes  # noqa: E402

from pipeline import record as R  # noqa: E402

QUAD = [[10, 20], [110, 20], [110, 60], [10, 60]]

# The real one, from `invoice_export` at seed 2026: an English gloss in
# brackets, hyphenated, wide enough to wrap in the description column.
WRAPPED = "ÁO SƠ MI NAM DÀI TAY (MEN'S LONG-SLEEVE SHIRT)"


def page(*texts: str, kind: str = "menu.name") -> dict:
    """One record whose boxes are exactly `texts`, in order, all of one kind."""
    return R.build(
        filename="html_000.jpg", width=800, height=1200, parser="html",
        layout="invoice_export", seed=2026,
        boxes=[{"kind": kind, "text": text,
                "quad": [[x, y + 20 * n] for x, y in QUAD]}
               for n, text in enumerate(texts)],
        extracted={"menu": [{"name": texts[0]}]},
    )


def coverage(monkeypatch, item: dict, wanted: list[tuple[str, str]]) -> list[str]:
    """`check_image`'s coverage verdict, with the rebuild pinned to `wanted`.

    `expected_fields` re-runs the rule-base to rebuild what the page should
    say, which is the right thing for the tool and the wrong thing for a test
    about the comparison: it would tie this file to the shipped rules. The
    image is absent on purpose -- the coverage check runs before it is opened,
    and `image unreadable` is dropped from the verdict here.
    """
    monkeypatch.setattr(check_boxes, "expected_fields",
                        lambda recipe, template="": wanted)
    problems = check_boxes.check_image(Path("no-such-directory"), item,
                                       {"seed": 2026}, template="auto")
    return [problem for problem in problems if "unreadable" not in problem]


def test_a_run_broken_after_a_hyphen_is_not_reported_missing(monkeypatch):
    """The bug this file exists for.

    The browser breaks a line after a hyphen and consumes nothing, so the two
    boxes hold `...LONG-` and `SLEEVE SHIRT)` and the run's own text has no
    space between them. Rejoining the boxes with a space -- correct for a break
    at a space, which *is* consumed -- invented a character the page does not
    have, and the field reported itself missing.
    """
    item = page("ÁO SƠ MI NAM DÀI TAY (MEN'S LONG-", "SLEEVE SHIRT)")
    assert coverage(monkeypatch, item, [("menu.name", WRAPPED)]) == []


def test_a_run_broken_at_a_space_is_still_found(monkeypatch):
    """The other break, which was already right and has to stay right."""
    item = page("VẢI DỆT KIM KHỔ 1M6", "(KNITTED FABRIC)")
    assert coverage(monkeypatch, item,
                    [("menu.name", "VẢI DỆT KIM KHỔ 1M6 (KNITTED FABRIC)")]) == []


def test_a_field_with_no_box_at_all_is_still_reported(monkeypatch):
    """The check is looser about whitespace, not about coverage.

    Whatever the rejoining does, a run that nothing on the page drew has to
    come back named -- that is the failure the whole tool exists to catch.
    """
    item = page("ÁO KHOÁC GIÓ (WINDBREAKER JACKET)")
    problems = coverage(monkeypatch, item,
                        [("menu.name", "QUẦN JEAN NỮ (WOMEN'S JEANS)")])
    assert len(problems) == 1
    assert "no box for menu.name" in problems[0]


def test_a_run_is_looked_for_in_boxes_of_its_own_kind(monkeypatch):
    """Joining per kind, not over the page.

    Dropping the spaces makes the join looser, so the guard that stops an
    unrelated field matching by accident matters more, not less: the words are
    all on the page, and under the wrong kind they still do not count.
    """
    item = page("SLEEVE SHIRT)", kind="menu.price")
    item["blocks"] += R.build(
        filename="x.jpg", width=800, height=1200, parser="html",
        boxes=[{"kind": "menu.name", "text": "ÁO SƠ MI NAM DÀI TAY (MEN'S LONG-",
                "quad": QUAD}],
        extracted={"menu": [{"name": "x"}]},
    )["blocks"]
    problems = coverage(monkeypatch, item, [("menu.name", WRAPPED)])
    assert len(problems) == 1
    assert "no box for menu.name" in problems[0]
