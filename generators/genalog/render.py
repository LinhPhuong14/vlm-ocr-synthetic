"""Render a rule-base receipt through genalog's document generator.

    generators/genalog/.venv/bin/python generators/genalog/render.py -o outputs -c 10

Microsoft's `genalog <https://github.com/microsoft/genalog>`_ builds a document
by handing a Jinja2 template to WeasyPrint. That is a genuinely different path
from a browser -- a print engine with a page box, real pagination and its own
text shaper -- so a model trained on browser screenshots alone has not seen it.

genalog's own templates are for prose, so the template here is a receipt one
(`templates/receipt.html.jinja`); everything else is genalog's:
`DocumentGenerator` loads it, `Document` renders it, WeasyPrint paints it.

`--template` switches page models. Instead of the character grid it prints one
of the CSS sheets in `generators/html/sheets/` -- the same markup string the
browser backend loads, through `templates/sheet.html.jinja`, which does nothing
but hand it over. The boxes then come from the PDF's own **character** stream
rather than its spans, because one WeasyPrint span can hold two table cells;
`match_runs` says how, and what happens without it.

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
import unicodedata
from pathlib import Path

import cv2
import fitz  # PyMuPDF
import numpy as np
from genalog.generation.document import Document, DocumentGenerator

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
# The CSS sheets are the browser backend's, imported rather than copied, so the
# two engines print one markup and a change reaches both. `sheets/` pulls in
# nothing heavier than `rulebase`, and `page.py` is the half of the browser
# backend that deliberately has no browser in it.
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

import sheets  # noqa: E402
from page import font_faces  # noqa: E402

import profiling  # noqa: E402
import rulebase  # noqa: E402
import worklist  # noqa: E402
from degradation.pipeline import apply_recipe  # noqa: E402

TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
TEMPLATE = "receipt.html.jinja"
SHEET_TEMPLATE = "sheet.html.jinja"
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
            # Merged down: set in the middle of the band, as in the other two.
            "top": f"{(cell.row + (cell.rowspan - 1) / 2.0) * line_px:.2f}px",
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
        # The mark's own colour when it has one, else the page's ink faded by
        # `tone` -- the same rule the other two backends follow.
        shade = mark.colour or _hex(tuple(int(round(255 - (255 - channel) * mark.tone))
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


def match_runs(runs: list[tuple[str, str]], glyphs: list[dict]) -> list[dict]:
    """Give each labelled run of a CSS sheet the glyphs that drew it.

    Glyphs, not spans, and that is the whole difference from `match_boxes`. A
    character-grid page puts every field in its own absolutely positioned
    element, so a PDF span is a field. A CSS sheet does not: two `<td>` on one
    line in one font come out of WeasyPrint as **one span** -- `"3 BÁNH CANH
    CUA"` is the quantity cell and the name cell welded together -- and no
    amount of concatenating spans forwards can take them apart again. Measured
    before this was written: a till-roll sheet recovered 58% of its runs that
    way, and the losses were every quantity and every dish on the page.

    So the walk runs over the PDF's own character boxes, which PyMuPDF reports
    exactly. A run is the next N non-space characters; its box is the union of
    theirs. Nothing is interpolated and nothing is estimated.

    `window` is how much unlabelled ink the walk may step over to find the next
    run -- a watermark, a separator pipe, the tick in a signature box. Small on
    purpose: a wide window lets a one-character run such as a quantity match a
    digit further down the page and desynchronise everything after it.

    The walk also looks *behind* the cursor, and that is not belt and braces.
    PyMuPDF groups a page's text geometrically, so two blocks side by side come
    back interleaved by line: a signature block prints "Lễ tân" and "Khách
    hàng" together, then both names, while the markup lists each caption with
    its own name. The reordering is local -- one line -- so a bounded look back
    recovers it, and the cursor never moves backwards, which is what keeps the
    walk from re-reading a page it has already passed.
    """
    boxes: list[dict] = []
    cursor = 0
    for kind, text in runs:
        wanted = _squeeze(text)
        if not wanted:
            continue
        found = _consume_glyphs(glyphs, cursor, wanted)
        if found is None:
            continue
        end, matched = found
        cursor = max(cursor, end)
        if kind == "sep":
            continue
        # One box per LINE, not one per run. A run that wrapped has glyphs on
        # two lines, and their union is a rectangle round both *and the blank
        # paper between their ragged ends* -- which on a full-width block
        # swallows whatever starts the first line. The browser backend splits
        # the same way, for the same reason; see `CELL_RECTS_JS`.
        lines = _lines(matched)
        for line, shown in zip(lines, _split_like(text, [len(part) for part in lines])):
            x0 = min(glyph["bbox"][0] for glyph in line)
            y0 = min(glyph["bbox"][1] for glyph in line)
            x1 = max(glyph["bbox"][2] for glyph in line)
            y1 = max(glyph["bbox"][3] for glyph in line)
            boxes.append({
                "kind": kind,
                "text": shown,
                "quad": [[round(x0, 1), round(y0, 1)], [round(x1, 1), round(y0, 1)],
                         [round(x1, 1), round(y1, 1)], [round(x0, 1), round(y1, 1)]],
            })
    return boxes


def _split_like(text: str, counts: list[int]) -> list[str]:
    """`text` cut into pieces of `counts` non-space characters each.

    The box text has to be the words, not the glyphs. Spaces carry no ink so
    they are not in the glyph stream at all, and a box labelled
    "QUÁNNHẬUBÚNBÒOHOA" is a box whose text no reader would produce and no
    check would match. So the pieces are cut out of the original string, which
    still has its spaces, using the glyph counts only to say where to cut.
    """
    pieces, index = [], 0
    for count in counts:
        taken = 0
        start = index
        while index < len(text) and taken < count:
            if not text[index].isspace():
                taken += 1
            index += 1
        pieces.append(text[start:index].strip())
    return pieces


def _lines(glyphs: list[dict]) -> list[list[dict]]:
    """The glyphs grouped into the lines they were set on.

    By vertical position rather than by index: a wrap is where the baseline
    moves, and nothing in the character stream marks it.
    """
    lines: list[list[dict]] = []
    top = None
    for glyph in glyphs:
        y0 = glyph["bbox"][1]
        if top is None or abs(y0 - top) > 1.0:
            lines.append([])
            top = y0
        lines[-1].append(glyph)
    return lines


# How far the glyph walk may look ahead for the next labelled run: past a
# watermark or a separator for a short one, past a repeated table header for a
# long one. See `_consume_glyphs`.
SHORT_RUN_WINDOW = 24
LONG_RUN_WINDOW = 200


def _squeeze(text: str) -> str:
    """Text with every space removed, in NFC.

    Whitespace goes because it is not ink: the markup says "Đơn vị tính (Unit)"
    on one line and WeasyPrint breaks it over two, and the space that was
    between the words becomes a line break that no glyph carries. NFC because
    the corpus is composed and a PDF may not be, and "ệ" written two ways is one
    letter on the page and two strings in Python.
    """
    return unicodedata.normalize("NFC", "".join(text.split()))


def _consume_glyphs(glyphs: list[dict], cursor: int, wanted: str,
                    back: int = 64):
    """`(end_index, matched_glyphs)` for the glyphs that spell `wanted`, or None.

    Forwards from the cursor first, then backwards from it -- nearest first in
    both directions, so the run is given the closest occurrence rather than the
    first one anywhere on the page.

    How far forward depends on how long the run is, and that is not a fudge. A
    long run can be searched for over a wide stretch because a false positive is
    not credible: nothing else on the page spells "Tổng tiền giảm giá". A
    one-character run cannot, because every quantity column is full of `1`s and
    the first one found would be the wrong one. The wide case is what a page
    break needs -- WeasyPrint repeats a table's `<thead>` on the next page, so
    about thirty glyphs of column titles that the markup lists once appear in
    the stream twice, and a window that cannot step over them loses the whole
    tail of the page.
    """
    window = SHORT_RUN_WINDOW if len(wanted) < 4 else LONG_RUN_WINDOW
    forwards = range(cursor, min(cursor + window, len(glyphs)))
    backwards = range(cursor - 1, max(cursor - back, 0) - 1, -1)
    for start in list(forwards) + list(backwards):
        found = _spell(glyphs, start, wanted)
        if found is not None:
            return found
    return None


def _spell(glyphs: list[dict], start: int, wanted: str):
    """`(end_index, matched_glyphs)` if the glyphs from `start` spell `wanted`."""
    index, used = start, []
    while index < len(glyphs) and len(used) < len(wanted):
        glyph = glyphs[index]
        if not glyph["text"].strip():
            index += 1
            continue              # a space carries no ink and no position
        if glyph["text"] != wanted[len(used)]:
            return None
        used.append(glyph)
        index += 1
    return (index, used) if len(used) == len(wanted) else None


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
    """WeasyPrint, through genalog, over either page model.

    Two page models, one engine. Without `template` the receipt is the character
    grid every backend has drawn until now, laid out with absolutely positioned
    spans. With it the page is one of the CSS sheets in
    `generators/html/sheets/` -- the same markup the browser backend loads, so
    the two renderers are finally comparable on the *document* and not only on
    the roll of paper.

    The boxes come from different places accordingly: the grid path walks its
    own cells, the sheet path walks the labelled runs it can read back out of
    the markup. Both end at the PDF's own text layer, which is exact -- this is
    not OCR of our own output.
    """

    def __init__(self, dpi: int = 150, short_size: tuple[int, int] = (960, 1400),
                 template: str | None = None):
        self.generator = DocumentGenerator(template_path=str(TEMPLATE_DIR))
        wanted = SHEET_TEMPLATE if template else TEMPLATE
        if wanted not in self.generator.template_list:
            raise RuntimeError(
                f"{wanted} not visible to genalog; it lists {self.generator.template_list}"
            )
        self.dpi = dpi
        self.short_size = short_size
        self.template = template

    def render(self, seed: int, force: dict[str, str] | None = None):
        if self.template:
            return self._render_sheet(seed, force)
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
        return recipe, receipt, grid, aged, boxes, []

    def _render_sheet(self, seed: int, force: dict[str, str] | None = None):
        """One of the CSS sheets, printed by WeasyPrint instead of a browser."""
        # No grid: it would trim a value to a character column this page does
        # not have, and write the trim back. See `rulebase.make_content`.
        recipe, receipt, _rng = rulebase.make_content(seed=seed, force=force)
        grid = None
        with profiling.stage("render"):
            override = None if self.template == "auto" else self.template
            markup = sheets.build(recipe, receipt, override)
            markup = markup.replace("{FONT_FACES}", font_faces())
            template = self.generator.template_env.get_template(SHEET_TEMPLATE)
            # No styles: the sheet carries its own, and genalog's prose defaults
            # have nothing to say about a table of goods. `update_style` still
            # runs, which is what compiles the WeasyPrint document.
            document = Document(markup, template)
            pdf = document.render_pdf()
            image, glyphs = self._rasterise(pdf, glyphs=True)
        with profiling.stage("geometry"):
            boxes = match_runs(sheets.labelled_runs(markup), glyphs)
            structure = sheets.structure_from_markup(markup)

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

        before = image.shape[:2]
        with profiling.stage("degradation"):
            aged = apply_recipe(image, recipe, seed=seed)
        if aged.shape[:2] != before:
            raise RuntimeError(
                f"a degradation resized the page ({before} -> {aged.shape[:2]}); "
                "the boxes no longer describe it"
            )
        return recipe, receipt, grid, aged, boxes, structure

    def _rasterise(self, pdf: bytes, *, glyphs: bool = False
                   ) -> tuple[np.ndarray, list[dict]]:
        """PDF bytes to one BGR image plus its text, in image pixels.

        The text comes out of the PDF's own layer, so it is exact -- this is not
        OCR of our own output. It is collected in the same loop as the raster
        because both need the same two transforms: PDF points to pixels at
        `dpi`, and, when WeasyPrint has split the page in two, the y-offset of
        the page each piece sits on.

        `glyphs` picks the granularity. Spans are what the character grid wants:
        one element per field, so one span is one cell. A CSS sheet needs single
        characters, because there one span can hold two fields -- see
        `match_runs`. Same loop, same transforms, one parameter.
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

                kind = "rawdict" if glyphs else "dict"
                for block in page.get_text(kind)["blocks"]:
                    for line in block.get("lines", []):
                        for span in line["spans"]:
                            if glyphs:
                                for char in span.get("chars", []):
                                    if not char["c"].strip():
                                        continue
                                    x0, y0, x1, y1 = char["bbox"]
                                    spans.append({
                                        "text": unicodedata.normalize("NFC", char["c"]),
                                        "bbox": (x0 * scale, y0 * scale + offset,
                                                 x1 * scale, y1 * scale + offset),
                                    })
                                continue
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
        "--template", metavar="LAYOUT", nargs="?", const="auto", default=None,
        help="print the CSS sheet for this recipe's layout instead of the "
             "character grid; see generators/html/sheets/. Bare, the sheet "
             "follows the layout the recipe drew; give a layout id to force one",
    )
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
        renderer = GenalogReceiptRenderer(dpi=args.dpi, template=args.template)

    # Streamed, not collected: a job list may be a whole shard, and a record
    # carries every box on the page. Written in page order, which is the order
    # the caller listed the jobs in -- `pipeline/worker.py` walks the runs in
    # that order to name the files.
    with open(args.out / "metadata.jsonl", "w", encoding="utf-8") as metadata:
        for index, job, seed in worklist.pages(jobs):
            recipe, receipt, grid, image, boxes, structure = renderer.render(
                seed, forces[job])
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
                # Additive, and only when the layout has a table to describe --
                # the same key the other two backends write, from the same grid.
                table = grid.table_label() if grid else None
                if table:
                    record["table"] = table
                if structure:
                    # Additive, and only for a sheet render: the structure half
                    # of the label, in the same PPStructure tokens the browser
                    # backend writes. `boxes` is untouched, so every existing
                    # loader keeps working.
                    record["structure"] = structure
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
