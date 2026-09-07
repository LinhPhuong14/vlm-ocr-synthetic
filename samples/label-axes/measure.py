#!/usr/bin/env python3
"""Run the label-axes fixtures through the real renderer's box-reading path.

    generators/html/.venv/bin/python samples/label-axes/measure.py

Each fixture in this directory (`page.html`, `page2.html`, `page3.html`) is a
FIXTURE, not a real document -- see `page.html`'s own header comment. This
script is the "đo được bằng máy" half that comment promises: it serves each
one through the same Chromium + `CELL_RECTS_JS` that `generators/html/page.py`
already uses for every rendered page, then checks three things a fixture
author cannot fully check by eye:

1. **Every `data-kind` in the source got exactly one box.** `CELL_RECTS_JS`
   drops a run silently if its measured text is empty -- a `data-text` typo'd
   as `data-Text`, say -- and a missing box is invisible on the rendered page.
2. **No box came out a fraction of its text's real width.** The bug this
   repository already measured once: a `<sub>` nested inside a labelled span
   made `CELL_RECTS_JS` measure `span.firstElementChild` -- the subscript
   alone -- while `text` stayed the whole formula, so the equation's box came
   out 5.3px wide instead of ~400. Caught here as "width per character" far
   below what the page's own font could produce.
3. **Every `data-region` is one of the 19 labels `pipeline.record` actually
   defines.** A fixture can drift from the schema it is meant to exercise
   without either side raising: nothing renders wrong, nothing crashes, the
   name is simply not the one `layout_class_for` will ever produce.

Exit code is non-zero if anything above fails, so this can gate a commit the
way `make check-boxes` gates a dataset.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from page import CELL_RECTS_JS, find_chromium, font_faces, served  # noqa: E402
from pipeline.record import DOCSYNTH_LABELS  # noqa: E402

FIXTURES = ("page.html", "page2.html", "page3.html")
HERE = Path(__file__).resolve().parent

# A generous floor, not a real advance estimate: `preflight.py::ADVANCE` (0.62
# of font-size) is measured for monospace body text at ~13px. This script
# covers headings, code and dotmatrix ink at several sizes, so it uses a
# fraction of that -- 0.20 em-equivalent px per character at the page's own
# smallest plausible size (11px) -- loose enough that only a box that measured
# the WRONG ELEMENT (a collapsed nested tag), not just a tight font, trips it.
MIN_PX_PER_CHAR = 11 * 0.20


def wrap(fixture_html: str) -> str:
    """The fixture's fragment, in the minimal document Chromium needs.

    Fixtures ship `<style>` + `<div id="sheet">` only -- no `<!doctype>`, no
    `<head>` -- because they are meant to be read as markup, not as a full
    page. `font_faces()` goes in a real `<head>` here for the same reason
    `sheets/base.py::document()` puts it in one: a `<style>` block dropped
    into a bare fragment still works in Chromium, but nothing here should
    depend on an implicit-head quirk when finding out later that a real page
    doesn't have it, would.
    """
    return f"<!doctype html><html><head><meta charset=\"utf-8\"><style>{font_faces()}</style></head><body>{fixture_html}</body></html>"


def kinds_in_source(html: str) -> set[str]:
    import re

    return set(re.findall(r'data-kind="([^"]+)"', html))


def regions_in_source(html: str) -> set[str]:
    import re

    return set(re.findall(r'data-region="([^"]+)"', html))


def measure(page, fixture_html: str) -> list[dict]:
    with served(wrap(fixture_html)) as uri:
        page.goto(uri, wait_until="load")
        rects = page.evaluate(CELL_RECTS_JS)
    return rects["cells"]


def check_fixture(page, path: Path) -> tuple[list[str], set[str]]:
    """One fixture's problems, and the `data-region` values it exercises."""
    html = path.read_text(encoding="utf-8")
    problems: list[str] = []

    cells = measure(page, html)
    measured_kinds = {cell["kind"] for cell in cells}

    missing = kinds_in_source(html) - measured_kinds
    for kind in sorted(missing):
        problems.append(f"data-kind={kind!r} is in the source but got no box "
                        f"at all -- CELL_RECTS_JS dropped it")

    for cell in cells:
        text = cell["text"]
        width = cell["w"]
        floor = len(text) * MIN_PX_PER_CHAR
        if width < floor:
            problems.append(
                f"{cell['kind']!r} measured {width:.1f}px wide for "
                f"{len(text)} characters ({text[:40]!r}) -- below the "
                f"{floor:.1f}px floor for that length; a nested tag likely "
                f"became the measured element instead of the whole run")

    regions = regions_in_source(html)
    unknown = regions - DOCSYNTH_LABELS
    for region in sorted(unknown):
        problems.append(
            f"data-region={region!r} is not one of the 19 labels "
            f"pipeline.record.DOCSYNTH_LABELS defines")

    return problems, regions


def main() -> int:
    from playwright.sync_api import sync_playwright

    all_problems: dict[str, list[str]] = {}
    all_regions: set[str] = set()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=find_chromium())
        try:
            browser_page = browser.new_page()
            for name in FIXTURES:
                path = HERE / name
                if not path.exists():
                    all_problems[name] = [f"{path} does not exist"]
                    continue
                problems, regions = check_fixture(browser_page, path)
                all_problems[name] = problems
                all_regions |= regions
        finally:
            browser.close()

    ok = True
    for name in FIXTURES:
        problems = all_problems.get(name, [])
        print(f"\n{name}: {'OK' if not problems else f'{len(problems)} problem(s)'}")
        for problem in problems:
            print(f"  - {problem}")
        ok = ok and not problems

    uncovered = DOCSYNTH_LABELS - all_regions
    print(f"\ndata-region values seen across all fixtures: {len(all_regions)}/19")
    if uncovered:
        print(f"  still zero: {', '.join(sorted(uncovered))}")

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
