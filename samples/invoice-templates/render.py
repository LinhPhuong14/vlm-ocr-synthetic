#!/usr/bin/env python3
"""Print each reference sheet with WeasyPrint: a PDF, and a JPG to look at.

    python samples/invoice-templates/render.py        # or: make templates

Needs `weasyprint` and `pymupdf`. They came with the genalog renderer's
requirements while that backend existed; it is deleted, so install them into
whatever interpreter you run this with:

    pip install weasyprint pymupdf

The PDF is the authority: these are print documents, and WeasyPrint is a print
engine with a page box and its own text shaper. The JPG beside each source is
that PDF rasterised, committed so the sheets can be looked at without building
anything -- which is what `samples/` is for.
"""
from __future__ import annotations

from pathlib import Path

import fitz  # PyMuPDF
from weasyprint import HTML

HERE = Path(__file__).resolve().parent
PDF_DIR = HERE / "out"
DPI = 150
QUALITY = 88


def main() -> None:
    PDF_DIR.mkdir(exist_ok=True)
    for source in sorted(HERE.glob("*.html")):
        pdf_path = PDF_DIR / f"{source.stem}.pdf"
        HTML(filename=str(source)).write_pdf(str(pdf_path))
        document = fitz.open(pdf_path)
        if len(document) != 1:
            # A reference sheet is one sheet. Two pages means the content grew
            # past the paper, and the fix is in the CSS, not in this script.
            raise SystemExit(
                f"{source.name}: rendered {len(document)} pages, expected 1")
        pixmap = document[0].get_pixmap(dpi=DPI)
        jpg_path = HERE / f"{source.stem}.jpg"
        pixmap.pil_save(jpg_path, format="JPEG", quality=QUALITY, optimize=True)
        document.close()
        print(f"{source.name:32} {pixmap.width}x{pixmap.height}px  "
              f"{jpg_path.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
