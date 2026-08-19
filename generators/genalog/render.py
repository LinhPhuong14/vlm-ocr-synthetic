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
  none of which has a wheel for Python 3.9+. Its source is vendored in this
  directory instead of installed, so the pins never apply; the dependencies
  come from `requirements.txt` at versions that exist, and nothing genalog is
  used for here touches the pinned APIs.

Because this file lives beside the vendored tree, `generators/genalog/` is
`sys.path[0]` whenever it runs, so `import genalog` resolves to that tree and
not to anything pip installed.
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

import profiling  # noqa: E402
import rulebase  # noqa: E402
import worklist  # noqa: E402
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


def marks_for(grid, recipe, line_px: float, pad_ch: float) -> list[dict]:
    """`Grid.marks` in the units this template writes.

    The third renderer of the same primitive. A rule is degenerate on one axis,
    so it is given the pen's thickness there rather than a zero that WeasyPrint
    would draw as nothing.
    """
    ink = rulebase.inks(recipe)["ink"]
    hairline = max(1.0, line_px * 0.055)
    out = []
    for mark in getattr(grid, "marks", ()):
        span = max(mark.col1 - mark.col0, 0.0)
        height = max((mark.row1 - mark.row0) * line_px, 0.0)
        thick = hairline * mark.weight
        shade = _hex(tuple(int(round(255 - (255 - channel) * mark.tone))
                           for channel in ink))
        out.append({
            "left": f"{mark.col0 + pad_ch:.3f}",
            "top": f"{mark.row0 * line_px:.2f}px",
            "width": f"{span:.3f}ch" if span > 0 else f"{thick:.2f}px",
            "height": f"{max(height, thick):.2f}px",
            "shade": shade,
            # A frame is hollow: the border is the ink and the middle is paper,
            # or the box would black out everything it encloses.
            "paint": (f"border:{thick:.2f}px solid {shade};box-sizing:border-box"
                      if mark.kind == "frame" else f"background:{shade}"),
        })
    return out


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

    # WeasyPrint prints onto a @page of a stated size, so unlike the browser
    # this backend has to work the sheet out in pixels itself. `0.62 * font_px`
    # is this file's standing estimate of a monospace advance -- the same one
    # `page_width` has always used -- and the sheet's height follows from it.
    # A page that overflows its paper keeps its full height rather than being
    # cropped: `sheet_height` only ever grows the box.
    page_width = (grid.ncols + pad_ch * 2) * font_px * 0.62
    content_px = grid.nrows * line_px + pad_top + pad_bottom
    page_height = rulebase.sheet_height(grid, page_width, content_px)
    return {
        "font_family": visual.get("font_family", "monospace"),
        "font_size": f"{font_px:.2f}px",
        "line_height": f"{line_px:.2f}px",
        "sheet_width": f"{grid.ncols + pad_ch * 2:.3f}ch",
        "sheet_height": f"{page_height - pad_top - pad_bottom:.2f}px",
        "page_width": f"{page_width:.0f}px",
        "page_height": f"{page_height:.0f}px",
        "page_margin": f"{pad_top:.2f}px 0 {pad_bottom:.2f}px",
        "ink": _hex(palette["ink"]),
        "accent": _hex(palette["accent"]),
        "tint": _hex(palette["tint"]),
        "tint_alpha": f"{palette['tint_alpha']:.3f}",
        "hyphenate": False,
    }


def _normalise(text: str) -> str:
    return " ".join(text.split())


def match_boxes(grid, spans: list[dict]) -> list[dict]:
    """Give each grid cell the PDF span that drew it.

    Matching is by text in document order, not by index. WeasyPrint emits the
    cells in the order the template lists them, so the two sequences line up --
    but it is free to break one cell into several spans when the shaper changes
    font mid-string, which a positional match would silently misalign for every
    cell after it. Walking forwards and *concatenating* spans until they equal
    the cell's text absorbs that.

    **Separators are matched, then discarded.** They are not fields -- a
    detector taught to find a row of dashes fires on every rule on the page --
    but they *are* drawn, so skipping them in this walk leaves their span in
    front of the cursor. That is what desynchronised the first version: from
    the first separator onwards every cell matched against the previous cell's
    span, and coverage fell to 82% with the losses all after the item list.

    A cell whose text cannot be found is dropped rather than guessed at: a box
    on the wrong words is worse than a missing one, and nothing downstream would
    catch it.
    """
    boxes: list[dict] = []
    cursor = 0
    for cell in grid.cells:
        wanted = _normalise(cell.text)
        if not wanted:
            continue
        found = _consume(spans, cursor, wanted)
        if found is None:
            continue
        cursor, box = found
        if cell.role == "sep":
            continue
        x0, y0, x1, y1 = box
        boxes.append({
            "kind": cell.role,
            "text": cell.text,
            # Four corners, axis-aligned, matching the schema the glyph renderer
            # writes -- its quads are genuinely rotated by the paper curl, so one
            # loader reads both.
            "quad": [[round(x0, 1), round(y0, 1)], [round(x1, 1), round(y0, 1)],
                     [round(x1, 1), round(y1, 1)], [round(x0, 1), round(y1, 1)]],
        })
    return boxes


def _consume(spans: list[dict], cursor: int, wanted: str, lookahead: int = 4):
    """`(next_cursor, bbox)` for the spans that spell `wanted`, or None.

    Tries each start within `lookahead` of the cursor rather than the cursor
    alone, so one unexpected span costs one cell instead of every cell after it.
    Spans are concatenated forwards because WeasyPrint may split a cell when the
    shaper changes font mid-string.
    """
    for start in range(cursor, min(cursor + lookahead, len(spans))):
        merged, box = "", None
        for probe in range(start, len(spans)):
            span = spans[probe]
            merged = _normalise(merged + span["text"])
            sx0, sy0, sx1, sy1 = span["bbox"]
            box = (sx0, sy0, sx1, sy1) if box is None else (
                min(box[0], sx0), min(box[1], sy0), max(box[2], sx1), max(box[3], sy1)
            )
            if merged == wanted:
                return probe + 1, box
            if len(merged) >= len(wanted):
                break  # overshot: this start cannot spell it
    return None


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
        with profiling.stage("render"):
            visual = recipe.visual.params

            size_lo, size_hi = visual.get("font_size", [22, 30])
            font_px = (size_lo + size_hi) / 2.0
            spacing_lo, spacing_hi = visual.get("line_spacing", [1.05, 1.35])
            line_px = font_px * (spacing_lo + spacing_hi) / 2.0
            pad_ch = rulebase.padding(recipe, grid)["columns"]

            cells = cells_for_template(grid, recipe, line_px, pad_ch)
            marks = marks_for(grid, recipe, line_px, pad_ch)
            # Build the Document straight from genalog's template environment
            # rather than via create_generator(): that yields a Document already
            # compiled against genalog's *default* prose styles, and this
            # template has no meaning for them -- it fails on the first render,
            # before update_style() gets a chance to supply the real ones.
            template = self.generator.template_env.get_template(TEMPLATE)
            document = Document(cells, template, marks=marks,
                                **styles_for(recipe, grid, line_px, pad_ch))

            # render_png() is gone from modern WeasyPrint; go through PDF.
            pdf = document.render_pdf()
            image, spans = self._rasterise(pdf)
        with profiling.stage("geometry"):
            boxes = match_boxes(grid, spans)

        target = random.Random(seed).randint(*self.short_size)
        factor = target / min(image.shape[:2])
        if factor < 1.0:
            with profiling.stage("render"):
                image = cv2.resize(
                    image,
                    (max(int(image.shape[1] * factor), 1),
                     max(int(image.shape[0] * factor), 1)),
                    interpolation=cv2.INTER_AREA,
                )
            with profiling.stage("geometry"):
                for box in boxes:
                    box["quad"] = [[round(x * factor, 1), round(y * factor, 1)]
                                   for x, y in box["quad"]]

        # Ageing composites and filters in place; nothing in `degradation/`
        # resizes. Checked rather than trusted -- a resize slipped into the
        # chain would shift every box while the image still looked right.
        before = image.shape[:2]
        with profiling.stage("degradation"):
            aged = apply_recipe(image, recipe, seed=seed)
        if aged.shape[:2] != before:
            raise RuntimeError(
                f"a degradation resized the page ({before} -> {aged.shape[:2]}); "
                "the boxes no longer describe it"
            )
        return recipe, receipt, grid, aged, boxes

    def _rasterise(self, pdf: bytes) -> tuple[np.ndarray, list[dict]]:
        """PDF bytes to one BGR image plus the text spans, in image pixels.

        The spans come out of the PDF's own text layer, so they are exact --
        this is not OCR of our own output. They are collected in the same loop
        as the raster because both need the same two transforms: PDF points to
        pixels at `dpi`, and, when WeasyPrint has split the receipt across
        pages, the y-offset of the page each span sits on.
        """
        scale = self.dpi / 72.0        # PDF user space is 72 points per inch
        pages: list[np.ndarray] = []
        spans: list[dict] = []
        offset = 0.0

        with fitz.open(stream=io.BytesIO(pdf), filetype="pdf") as document:
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

                for block in page.get_text("dict")["blocks"]:
                    for line in block.get("lines", []):
                        for span in line["spans"]:
                            # WeasyPrint emits whitespace-only spans between
                            # cells. They carry no ink, but they carry a bbox,
                            # and letting them into the sequence both inflates
                            # the box they get merged into and desynchronises
                            # the walk in `match_boxes`.
                            if not span["text"].strip():
                                continue
                            x0, y0, x1, y1 = span["bbox"]
                            spans.append({
                                "text": span["text"],
                                "bbox": (x0 * scale, y0 * scale + offset,
                                         x1 * scale, y1 * scale + offset),
                            })
                offset += array.shape[0]
                pages.append(array)

        if len(pages) == 1:
            return pages[0], spans
        width = max(page.shape[1] for page in pages)
        padded = [
            cv2.copyMakeBorder(p, 0, 0, 0, width - p.shape[1], cv2.BORDER_CONSTANT,
                               value=(255, 255, 255))
            for p in pages
        ]
        return np.vstack(padded), spans


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=Path("outputs"))
    parser.add_argument("-c", "--count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--layout", help="pin one bố cục")
    parser.add_argument(
        "--force", action="append", default=[], metavar="ATTR=ID",
        help="pin any attribute, repeatable: --force augmentation=pristine",
    )
    parser.add_argument("--dpi", type=int, default=150)
    parser.add_argument(
        "--profile", metavar="JSON",
        help="time every stage and write the breakdown here. Off by default, "
             "and off costs nothing: see profiling.py",
    )
    worklist.add_argument(parser)
    args = parser.parse_args()

    profile = Path(args.profile) if args.profile else profiling.enable_from_env()
    if args.profile:
        profiling.enable()

    args.out.mkdir(parents=True, exist_ok=True)
    jobs = worklist.load(args)
    # One parse per job rather than one per page: `parse_force` reads the rules
    # to validate the pin, and a job list is many pages over few distinct pins.
    forces = {job: rulebase.parse_force(job.pins(args.force), job.layout)
              for job in jobs}
    with profiling.stage("startup"):
        renderer = GenalogReceiptRenderer(dpi=args.dpi)

    # Streamed, not collected: a job list may be a whole shard, and a record
    # carries every box on the page. Written in page order, which is the order
    # the caller listed the jobs in -- `pipeline/worker.py` walks the runs in
    # that order to name the files.
    with open(args.out / "metadata.jsonl", "w", encoding="utf-8") as metadata:
        for index, job, seed in worklist.pages(jobs):
            recipe, receipt, _grid, image, boxes = renderer.render(seed, forces[job])
            name = f"genalog_{index:03d}.jpg"
            with profiling.stage("export"):
                cv2.imwrite(str(args.out / name), image, [cv2.IMWRITE_JPEG_QUALITY, 90])
            with profiling.stage("annotation"):
                record = {
                    "file_name": name,
                    "ground_truth": json.dumps({"gt_parse": receipt.ground_truth()},
                                               ensure_ascii=False),
                    "text_sequence": receipt.text_sequence(),
                    "recipe": recipe.to_dict(),
                    "boxes": boxes,
                }
            with profiling.stage("export"):
                json.dump(record, metadata, ensure_ascii=False)
                metadata.write("\n")
            print(f"[ok] {name}  {image.shape[1]}x{image.shape[0]}  "
                  f"{recipe.layout.id}  {len(boxes)} boxes")

    if profile:
        profiling.dump(profile, {"backend": "genalog", "images": worklist.total(jobs),
                                 "jobs": len(jobs)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
