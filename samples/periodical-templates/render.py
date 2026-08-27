#!/usr/bin/env python3
"""Screenshot each reference sheet with Chromium: a JPG to look at.

    python samples/periodical-templates/render.py        # or: make templates

Same idea as `samples/invoice-templates/render.py`, `samples/form-
templates/render.py` and `samples/insurance-templates/render.py`: launch the
same Chromium build `generators/html/render.py` uses for the real pipeline
(`find_chromium()`, shared from `generators/html/page.py`) and screenshot the
one page element each file actually has, at full resolution. No PDF, no
PyMuPDF: an element screenshot is already clipped to that element's box,
which is what a printed page is here -- these sheets size themselves in real
mm, not in viewport units, so nothing about the shot depends on window size.

Nine of the ten files carry their page as `.sheet`, same as every other
template directory. `newspaper_front_broadsheet.html` is normal here too --
"broadsheet" names the paper size (375x597mm), not a second page. The one
real exception is `magazine_feature_spread.html`: a two-page magazine spread
drawn as ONE physical sheet (420x297mm, two A4 pages side by side across a
shared gutter), so its page element is named `.spread` instead of `.sheet` --
there is still exactly one image to take, just of a wider box.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
sys.path.insert(0, str(REPO_ROOT))

from playwright.sync_api import sync_playwright  # noqa: E402

from generators.html.page import find_chromium  # noqa: E402

SCALE = 2.0
JPEG_QUALITY = 88


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=find_chromium())
        try:
            for source in sorted(HERE.glob("*.html")):
                page = browser.new_page(device_scale_factor=SCALE)
                page.goto(source.resolve().as_uri(), wait_until="load")
                pages = page.query_selector_all(".sheet") or page.query_selector_all(".spread")
                if len(pages) != 1:
                    raise SystemExit(
                        f"{source.name}: found {len(pages)} .sheet/.spread, expected 1")
                jpg_path = HERE / f"{source.stem}.jpg"
                pages[0].screenshot(path=str(jpg_path), type="jpeg", quality=JPEG_QUALITY)
                print(f"{jpg_path.name:40} {jpg_path.stat().st_size / 1024:.0f} KB")
                page.close()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
