#!/usr/bin/env python3
"""Print each reference form with WeasyPrint: a PDF, and a JPG per page.

    python samples/form-templates/render.py        # or: make templates

Needs `weasyprint` and `pymupdf`. They came with the genalog renderer's
requirements while that backend existed; it is deleted, so install them into
whatever interpreter you run this with:

    pip install weasyprint pymupdf

Same idea as `samples/invoice-templates/render.py`, with one difference these
sheets force: a form is not always one page. `bang kê chi phí` is three, and
each of them is laid out by hand, so the page count is part of what the sheet
is claiming. EXPECTED_PAGES below is that claim, and a mismatch is a failure
rather than a note -- if a row grew and pushed the settlement block onto a
fourth page, the fix is in the sheet, not here.
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from weasyprint import HTML

HERE = Path(__file__).resolve().parent
PDF_DIR = HERE / "out"
DPI = 150
QUALITY = 88

# Số trang mỗi tờ phải in ra. Sai số trang = bố cục đã trôi.
EXPECTED_PAGES = {
    "authorisation_letter": 1,
    "medical_statement": 3,
}


def main() -> None:
    PDF_DIR.mkdir(exist_ok=True)
    for source in sorted(HERE.glob("*.html")):
        pdf_path = PDF_DIR / f"{source.stem}.pdf"
        HTML(filename=str(source)).write_pdf(str(pdf_path))
        document = fitz.open(pdf_path)
        expected = EXPECTED_PAGES.get(source.stem)
        if expected is not None and len(document) != expected:
            raise SystemExit(
                f"{source.name}: rendered {len(document)} pages, "
                f"expected {expected}")
        for index, page in enumerate(document, start=1):
            pixmap = page.get_pixmap(dpi=DPI)
            name = (f"{source.stem}.jpg" if len(document) == 1
                    else f"{source.stem}-p{index}.jpg")
            jpg_path = HERE / name
            pixmap.pil_save(jpg_path, format="JPEG", quality=QUALITY,
                            optimize=True)
            print(f"{name:34} {pixmap.width}x{pixmap.height}px  "
                  f"{jpg_path.stat().st_size / 1024:.0f} KB")
        document.close()


if __name__ == "__main__":
    main()
