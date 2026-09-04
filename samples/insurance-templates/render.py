#!/usr/bin/env python3
"""Screenshot each reference sheet with Chromium: a JPG to look at.

    python samples/insurance-templates/render.py        # or: make templates

Same idea as `samples/invoice-templates/render.py` and `samples/form-
templates/render.py`, on a different engine. Those two print with WeasyPrint,
which arrived with a renderer this repository has since deleted -- so
this script instead launches the same Chromium build
`generators/html/render.py` uses for the real pipeline (`find_chromium()`,
shared from `generators/html/page.py`) and screenshots each `.sheet` element
directly, one full-resolution JPG per printed page. No PDF, no PyMuPDF: an
element screenshot is already clipped to that element's box, which is what a
printed page is here -- these sheets size `.sheet` in real mm, not in
viewport units, so nothing about the shot depends on window size.

Most of these are one page. `EXPECTED_SHEETS` below is how many `.sheet`
elements a file must have, checked the same way the sibling scripts check
page count -- a mismatch is a failure rather than a note, because it means
the sheet has silently grown a page the layout was not built to have.
`insurance_health_id_card.html` has no `.sheet` at all: front and back sit
side by side on one `.stage`, so that whole stage is screenshotted instead.
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

# Số phần tử `.sheet` mỗi tờ phải có. Một tờ, một `.sheet` -- trừ hợp đồng tài
# sản, sinh sẵn thành hai trang trong cùng file.
EXPECTED_SHEETS = {
    "insurance_property_contract": 2,
}


def main() -> None:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=find_chromium())
        try:
            for source in sorted(HERE.glob("*.html")):
                page = browser.new_page(device_scale_factor=SCALE)
                page.goto(source.resolve().as_uri(), wait_until="load")
                sheets = page.query_selector_all(".sheet")
                if sheets:
                    expected = EXPECTED_SHEETS.get(source.stem, 1)
                    if len(sheets) != expected:
                        raise SystemExit(
                            f"{source.name}: found {len(sheets)} .sheet, "
                            f"expected {expected}")
                    for index, sheet in enumerate(sheets, start=1):
                        name = (f"{source.stem}.jpg" if len(sheets) == 1
                                else f"{source.stem}-p{index}.jpg")
                        jpg_path = HERE / name
                        sheet.screenshot(path=str(jpg_path), type="jpeg",
                                         quality=JPEG_QUALITY)
                        print(f"{name:40} {jpg_path.stat().st_size / 1024:.0f} KB")
                else:
                    # The health-card sheet: no `.sheet`, front and back are
                    # two `.card` side by side on one `.stage` -- that whole
                    # view is the thing worth looking at, in one image.
                    jpg_path = HERE / f"{source.stem}.jpg"
                    page.screenshot(path=str(jpg_path), type="jpeg",
                                     quality=JPEG_QUALITY, full_page=True)
                    print(f"{jpg_path.name:40} {jpg_path.stat().st_size / 1024:.0f} KB")
                page.close()
        finally:
            browser.close()


if __name__ == "__main__":
    main()
