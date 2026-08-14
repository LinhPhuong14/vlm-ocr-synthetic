"""Render a rule-base receipt through genalog's document generator.

    generators/genalog/.venv/bin/python generators/genalog/render.py -o outputs -c 10

Microsoft's `genalog <https://github.com/microsoft/genalog>`_ builds a document
by handing a Jinja2 template to WeasyPrint. That is a genuinely different path
from a browser -- a print engine with a page box, real pagination and its own
text shaper -- so a model trained on browser screenshots alone has not seen it.

genalog's own templates are for prose, so the template here is a receipt one
(`templates/receipt.html.jinja`); everything else is genalog's:
`DocumentGenerator` loads it, `Document` renders it, WeasyPrint paints it.

Two things had to be worked around, both from genalog being pinned to 2020:

* `Document.render_png()` calls WeasyPrint's `write_png()`, removed in
  WeasyPrint 53. The PDF is rasterised with PyMuPDF instead.
* genalog pins `numpy==1.18.1`, `WeasyPrint==51` and `scikit-image==0.16.2`,
  none of which has a wheel for Python 3.9+. It is installed with `--no-deps`
  and the dependencies are supplied at versions that exist; nothing genalog is
  used for here touches the pinned APIs.
"""

from __future__ import annotations

import argparse
import io
import json
import random
import sys
from pathlib import Path

import cv2
import fitz  # PyMuPDF
import numpy as np
from genalog.generation.document import Document, DocumentGenerator

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import rulebase  # noqa: E402
from degradation.pipeline import apply_recipe  # noqa: E402

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE = "receipt.html.jinja"
FONT_ROOT = REPO_ROOT / "fonts"


def _hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def cells_for_template(grid, recipe, line_px: float, pad_ch: float) -> list[dict]:
    """The grid, flattened into what the Jinja2 template iterates over."""
    accent_roles = {"store.name", "title"}
    cells = []
    for cell in grid.cells:
        width = max(cell.col1 - cell.col0, 1)
        cells.append({
            "text": cell.text,
            "left": f"{cell.col0 + pad_ch:.3f}",
            "top": f"{cell.row * line_px:.2f}px",
            "width": width,
            "align": cell.align,
            # Clamped exactly as in the other two backends, so an enlarged
            # total cannot run off the paper in one renderer and not another.
            "scale": f"{min(cell.scale, width / max(len(cell.text), 1)):.3f}",
            "bold": cell.bold,
            "accent": cell.role in accent_roles,
        })
    return cells


def styles_for(recipe, grid, line_px: float, pad_ch: float) -> dict:
    visual = recipe.visual.params
    # Shared palette, so `visual.ink_gray` fades this backend's text the same
    # amount it fades the other two backends'.
    palette = rulebase.inks(recipe)
    pad = rulebase.padding(recipe, grid)
    size_lo, size_hi = visual.get("font_size", [22, 30])
    font_px = (size_lo + size_hi) / 2.0
    pad_top = line_px * pad["top"]
    pad_bottom = line_px * pad["bottom"]
    return {
        "font_family": visual.get("font_family", "monospace"),
        "font_size": f"{font_px:.2f}px",
        "line_height": f"{line_px:.2f}px",
        "sheet_width": f"{grid.ncols + pad_ch * 2:.3f}ch",
        "sheet_height": f"{grid.nrows * line_px:.2f}px",
        "page_width": f"{(grid.ncols + pad_ch * 2) * font_px * 0.62:.0f}px",
        "page_height": f"{grid.nrows * line_px + pad_top + pad_bottom:.0f}px",
        "page_margin": f"{pad_top:.2f}px 0 {pad_bottom:.2f}px",
        "ink": _hex(palette["ink"]),
        "accent": _hex(palette["accent"]),
        "tint": _hex(palette["tint"]),
        "tint_alpha": f"{palette['tint_alpha']:.3f}",
        "hyphenate": False,
    }


class GenalogReceiptRenderer:
    def __init__(self, dpi: int = 150, short_size: tuple[int, int] = (960, 1400)):
        self.generator = DocumentGenerator(template_path=str(TEMPLATE_DIR))
        if TEMPLATE not in self.generator.template_list:
            raise RuntimeError(
                f"{TEMPLATE} not visible to genalog; it lists {self.generator.template_list}"
            )
        self.dpi = dpi
        self.short_size = short_size

    def render(self, seed: int, force: dict[str, str] | None = None):
        recipe, receipt, grid = rulebase.make(seed=seed, force=force)
        visual = recipe.visual.params

        size_lo, size_hi = visual.get("font_size", [22, 30])
        font_px = (size_lo + size_hi) / 2.0
        spacing_lo, spacing_hi = visual.get("line_spacing", [1.05, 1.35])
        line_px = font_px * (spacing_lo + spacing_hi) / 2.0
        pad_ch = rulebase.padding(recipe, grid)["columns"]

        cells = cells_for_template(grid, recipe, line_px, pad_ch)
        # Build the Document straight from genalog's template environment
        # rather than via create_generator(): that yields a Document already
        # compiled against genalog's *default* prose styles, and this template
        # has no meaning for them -- it fails on the first render, before
        # update_style() gets a chance to supply the real ones.
        template = self.generator.template_env.get_template(TEMPLATE)
        document = Document(cells, template, **styles_for(recipe, grid, line_px, pad_ch))

        # render_png() is gone from modern WeasyPrint; go through PDF.
        pdf = document.render_pdf()
        image = self._rasterise(pdf)

        target = random.Random(seed).randint(*self.short_size)
        factor = target / min(image.shape[:2])
        if factor < 1.0:
            image = cv2.resize(
                image,
                (max(int(image.shape[1] * factor), 1), max(int(image.shape[0] * factor), 1)),
                interpolation=cv2.INTER_AREA,
            )

        aged = apply_recipe(image, recipe, seed=seed)
        return recipe, receipt, grid, aged

    def _rasterise(self, pdf: bytes) -> np.ndarray:
        """PDF bytes to one BGR image, stacking pages if WeasyPrint split them."""
        with fitz.open(stream=io.BytesIO(pdf), filetype="pdf") as document:
            pages = []
            for page in document:
                pixmap = page.get_pixmap(dpi=self.dpi)
                buffer = np.frombuffer(pixmap.samples, dtype=np.uint8)
                array = buffer.reshape(pixmap.height, pixmap.width, pixmap.n)
                if pixmap.n == 4:
                    array = cv2.cvtColor(array, cv2.COLOR_RGBA2BGR)
                elif pixmap.n == 3:
                    array = cv2.cvtColor(array, cv2.COLOR_RGB2BGR)
                else:
                    array = cv2.cvtColor(array, cv2.COLOR_GRAY2BGR)
                pages.append(array)
        if len(pages) == 1:
            return pages[0]
        width = max(page.shape[1] for page in pages)
        padded = [
            cv2.copyMakeBorder(p, 0, 0, 0, width - p.shape[1], cv2.BORDER_CONSTANT,
                               value=(255, 255, 255))
            for p in pages
        ]
        return np.vstack(padded)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=Path("outputs"))
    parser.add_argument("-c", "--count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--layout", help="pin one bố cục")
    parser.add_argument(
        "--force", action="append", default=[], metavar="ATTR=ID",
        help="pin any attribute, repeatable: --force augmentation=khong_lam_gi",
    )
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    force = rulebase.parse_force(args.force, args.layout)
    renderer = GenalogReceiptRenderer(dpi=args.dpi)
    records = []

    for index in range(args.count):
        recipe, receipt, _grid, image = renderer.render(args.seed + index, force)
        name = f"genalog_{index:03d}.jpg"
        cv2.imwrite(str(args.out / name), image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        records.append({
            "file_name": name,
            "ground_truth": json.dumps({"gt_parse": receipt.ground_truth()}, ensure_ascii=False),
            "text_sequence": receipt.text_sequence(),
            "recipe": recipe.to_dict(),
        })
        print(f"[ok] {name}  {image.shape[1]}x{image.shape[0]}  {recipe.layout.id}")

    with open(args.out / "metadata.jsonl", "w", encoding="utf-8") as fp:
        for record in records:
            json.dump(record, fp, ensure_ascii=False)
            fp.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
