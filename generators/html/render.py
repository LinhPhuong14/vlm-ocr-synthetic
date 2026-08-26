"""Render a rule-base receipt as HTML in a headless browser.

    generators/html/.venv/bin/python generators/html/render.py -o outputs -c 10

The same `Grid` the glyph renderer draws, laid out with CSS instead: one
absolutely-positioned span per cell, positioned in `ch` units so a column is a
character wide in the browser exactly as it is on the character grid. That is
what makes the two renderers comparable -- not "both produce a receipt", but
"both put this word in this column".

What differs, and is meant to differ, is everything a browser gives for free:
subpixel text shaping, real font fallback, `font-weight` synthesis. Those are
the artefacts an OCR model will actually meet in scanned HTML documents.

The page is then aged by the same `degradation.pipeline.apply_recipe` the other
two backends call, so the ageing is not a third implementation.
"""

from __future__ import annotations

import argparse
import html
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

# The browser, the fonts and the two box-reading snippets live in `page.py`:
# two producers sit on this backend now -- receipts here, tables in
# `tables.py` -- and both need all four.
import sheets  # noqa: E402
from page import (  # noqa: E402
    CELL_RECTS_JS,
    CELL_REGIONS_JS,
    find_chromium,
    font_faces,
    served,
)

import profiling  # noqa: E402
import rulebase  # noqa: E402
import worklist  # noqa: E402
from degradation.pipeline import apply_recipe  # noqa: E402
from pipeline import record, synthesis  # noqa: E402


def _sheet_css(grid, line_px: float, padding_px: float) -> str:
    """How tall the sheet is: its content, or the paper it is printed on.

    A cut sheet's height is decided before anything is printed, so a three-item
    invoice still fills an A4 page and the rest is paper. `aspect-ratio` does
    the arithmetic in the browser rather than here, because the width is in
    `ch` -- the font's own advance -- and only the browser knows what that is
    in pixels. `min-height` keeps it a floor: content that overflows its paper
    stays visible instead of being cropped into looking fine.
    """
    content = grid.nrows * line_px + padding_px
    ratio = rulebase.sheet_ratio(grid)
    if ratio is None:
        return f"height:{content:.2f}px;"
    return f"min-height:{content:.2f}px;aspect-ratio:{ratio:.6f};"


def build_html(grid, recipe, receipt) -> str:
    """One span per cell, positioned on the character grid."""
    visual = recipe.visual.params
    # Ink comes from the shared palette, so `visual.ink_gray` fades the text
    # here exactly as it does in the glyph renderer. Reading `color.ink`
    # directly -- which this used to do -- silently dropped the attribute and
    # made every HTML page crisper than the recipe asked for.
    palette = rulebase.inks(recipe)
    ink, accent = palette["ink"], palette["accent"]
    tint, tint_alpha = palette["tint"], palette["tint_alpha"]

    # Mid-range of the recipe's font size: the browser scales the whole sheet,
    # so the absolute number only sets the raster resolution.
    size_lo, size_hi = visual.get("font_size", [22, 30])
    font_px = (size_lo + size_hi) / 2.0
    spacing_lo, spacing_hi = visual.get("line_spacing", [1.05, 1.35])
    line_px = font_px * (spacing_lo + spacing_hi) / 2.0
    # Padding comes from the rule-base, so the glyph renderer leaves the same
    # margin. `padding` already guarantees the top clears the tallest cell:
    # a header set at 1.7em overflows its fixed-height line box, and an element
    # screenshot clips at the element's edge, decapitating the shop name.
    pad = rulebase.padding(recipe, grid)
    pad_ch = pad["columns"]
    width_ch = grid.ncols + pad_ch * 2
    pad_top = line_px * pad["top"]
    pad_bottom = line_px * pad["bottom"]

    spans = []
    for cell in grid.cells:
        left = cell.col0 + pad_ch
        width = max(cell.col1 - cell.col0, 1)
        colour_hex = "#%02x%02x%02x" % tuple(accent if cell.role in ("store.name", "title") else ink)
        # The box is positioned in `ch`, which is the *element's own* character
        # width -- so scaling the outer span would scale the grid with it and a
        # 1.5em total would be right-aligned against a box 1.5 columns too wide,
        # pushing the amount off the sheet. The outer span keeps the sheet's
        # font-size and stays on the grid; only the inner one grows.
        style = (
            f"left:{left:.3f}ch;top:{pad_top + cell.row * line_px:.2f}px;"
            f"width:{width}ch;text-align:{cell.align};color:{colour_hex};"
        )
        # Same clamp the glyph renderer applies: an enlarged cell may not grow
        # past its column, or a 1.6em grand total runs off the edge of the paper.
        scale = min(cell.scale, width / max(len(cell.text), 1))
        inner = f"font-size:{scale:.3f}em;" + ("font-weight:700;" if cell.bold else "")
        # `data-kind` rides along so the box extractor does not have to re-derive
        # the role from the grid and risk drifting out of step with it.
        spans.append(
            f'<span data-kind="{html.escape(cell.role)}" style="{style}">'
            f'<i style="{inner}">{html.escape(cell.text)}</i></span>'
        )

    # Non-text primitives on the same character grid the spans use. A `Mark` is
    # a rectangle in (row, column) units, so it needs the two numbers already in
    # hand and nothing else -- which is the point of putting it on that grid
    # rather than inventing a second coordinate system for decoration.
    hairline = max(1.0, line_px * 0.055)
    marks = []
    for mark in getattr(grid, "marks", ()):
        x0 = (mark.col0 + pad_ch)
        span_ch = max(mark.col1 - mark.col0, 0.0)
        top = pad_top + mark.row0 * line_px
        height = max((mark.row1 - mark.row0) * line_px, 0.0)
        thick = hairline * mark.weight
        shade = "#%02x%02x%02x" % tuple(
            int(round(255 - (255 - channel) * mark.tone)) for channel in ink)
        if mark.kind == "rule":
            # Degenerate on one axis: give it the pen's thickness there.
            style = (f"left:{x0:.3f}ch;top:{top:.2f}px;"
                     f"width:{span_ch:.3f}ch;height:{max(height, thick):.2f}px;"
                     if span_ch > 0 else
                     f"left:{x0:.3f}ch;top:{top:.2f}px;"
                     f"width:{thick:.2f}px;height:{max(height, thick):.2f}px;")
            if span_ch > 0 and height <= 0:
                style = (f"left:{x0:.3f}ch;top:{top:.2f}px;"
                         f"width:{span_ch:.3f}ch;height:{thick:.2f}px;")
        else:
            style = (f"left:{x0:.3f}ch;top:{top:.2f}px;"
                     f"width:{span_ch:.3f}ch;height:{max(height, thick):.2f}px;")
        # A frame is hollow: the border is the ink and the middle is paper, or
        # the box would black out everything it encloses.
        paint = (f"border:{thick:.2f}px solid {shade};box-sizing:border-box;"
                 if mark.kind == "frame" else f"background:{shade};")
        marks.append(f'<div class="mark" style="{style}{paint}"></div>')

    tint_layer = (
        f'<div id="tint" style="background:rgb({tint[0]},{tint[1]},{tint[2]});'
        f'opacity:{tint_alpha:.3f}"></div>'
        if tint_alpha > 0
        else ""
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
{font_faces()}
html,body{{margin:0;padding:0;background:#fff;}}
#sheet{{
  position:relative;
  font-family:{visual.get("font_family", "monospace")};
  font-size:{font_px:.2f}px;
  line-height:{line_px:.2f}px;
  width:{width_ch:.3f}ch;
  /* Every cell is absolutely positioned, so the sheet has no content to be
     sized by and collapses to a sliver unless the height is stated. The
     padding is baked into that height and into each cell's `top`, NOT set as
     a `padding` property: an absolutely positioned child is laid out against
     its ancestor's *padding box*, so CSS padding does not move it, and the
     shop name ends up hard against the top edge however large the padding is. */
  {_sheet_css(grid, line_px, pad_top + pad_bottom)}
  background:#fff;
  -webkit-font-smoothing:antialiased;
}}
#sheet span{{
  position:absolute;
  white-space:pre;
  height:{line_px:.2f}px;
  line-height:{line_px:.2f}px;
}}
#sheet i{{font-style:normal;}}
/* Behind the text: a printed rule is drawn by the press and the words sit in
   the cell it makes, so a line across a word would be wrong. */
#sheet .mark{{position:absolute;pointer-events:none;}}
#tint{{position:absolute;inset:0;pointer-events:none;}}
</style></head>
<body><div id="sheet">{"".join(marks)}{"".join(spans)}{tint_layer}</div></body></html>"""


def regions_from_rects(rects, scale: float, factor: float) -> list[dict]:
    """Cell rects, keeping the grid position and the span with each one."""
    ratio = scale * factor
    cells = []
    for rect in rects:
        if rect["w"] <= 0 or rect["h"] <= 0:
            continue
        x0, y0 = rect["x"] * ratio, rect["y"] * ratio
        x1, y1 = x0 + rect["w"] * ratio, y0 + rect["h"] * ratio
        cells.append({
            "kind": rect["kind"], "text": rect["text"],
            "row": rect["row"], "col": rect["col"],
            "colspan": rect["colspan"], "rowspan": rect["rowspan"],
            "quad": [[round(x0, 1), round(y0, 1)], [round(x1, 1), round(y0, 1)],
                     [round(x1, 1), round(y1, 1)], [round(x0, 1), round(y1, 1)]],
        })
    return cells


def quads_from_rects(rects, scale: float, factor: float) -> list[dict]:
    """Browser rects -> the same `{kind, text, quad}` the glyph renderer writes.

    Two multiplications, and both are easy to forget. `scale` is the page's
    device scale factor: the screenshot is taken at that resolution while
    `getBoundingClientRect` reports CSS pixels. `factor` is the downscale
    applied afterwards to land in the glyph renderer's size band.

    Separators are dropped, as they are in `template_receipt.py` -- a row of
    dashes is not a field, and a detector trained to find one learns to fire on
    every rule on the page.
    """
    ratio = scale * factor
    quads = []
    for rect in rects:
        if rect["kind"] == "sep" or rect["w"] <= 0 or rect["h"] <= 0:
            continue
        x0, y0 = rect["x"] * ratio, rect["y"] * ratio
        x1, y1 = x0 + rect["w"] * ratio, y0 + rect["h"] * ratio
        quads.append({
            "kind": rect["kind"],
            "text": rect["text"],
            # Axis-aligned, but written as four corners so the schema matches
            # the glyph renderer's, whose quads are genuinely rotated by the
            # paper curl. One loader reads both.
            "quad": [[round(x0, 1), round(y0, 1)], [round(x1, 1), round(y0, 1)],
                     [round(x1, 1), round(y1, 1)], [round(x0, 1), round(y1, 1)]],
        })
    return quads


class HtmlReceiptRenderer:
    """Keeps one browser alive across a run -- launching costs ~300 ms each time."""

    def __init__(self, scale: float = 2.0, short_size: tuple[int, int] = (960, 1400),
                 template: str | None = None, hand=None,
                 sign: str | None = None):
        self.scale = scale
        self.short_size = short_size
        # An open `handwriting.Hand`, or None to type every value as before.
        # It is passed in rather than built here because it holds a WriteViT
        # process that costs 11 s to start and must outlive one page, exactly
        # like the browser below.
        self.hand = hand
        # Which ink signs, or None. A name rather than an object, unlike
        # `hand`: the font source opens and closes a face per page, which costs
        # a parse and no process. The model source needs a worker, and rather
        # than stand up a second one it borrows `hand` when that is already a
        # WriteViT worker -- see `render`.
        self.sign = sign
        # None keeps the character-grid page every layout has used until now.
        # "auto" switches to `sheets/`, which lays the same receipt out with CSS
        # and picks the sheet from `recipe.layout.id`; a layout id in its place
        # forces one particular dress, which is for looking at a sheet on demand
        # rather than for a run.
        self.template = template
        self._playwright = None
        self._browser = None

    def __enter__(self):
        self._playwright = sync_playwright().start()
        executable = find_chromium()
        try:
            self._browser = self._playwright.chromium.launch(executable_path=executable)
        except Exception as error:  # noqa: BLE001 -- re-raised with a fix
            raise RuntimeError(
                f"could not launch Chromium ({error}).\n"
                "On Windows and macOS, install one first:\n"
                "  generators/html/.venv/Scripts/python -m playwright install chromium\n"
                "In this repository's Linux container a build already exists under "
                "/opt/pw-browsers, so do NOT run `playwright install` there."
            ) from error
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def render(self, seed: int, force: dict[str, str] | None = None):
        # A sheet is built from the contents alone: laying a character grid over
        # them first would trim a value to a column this page does not have.
        # See `rulebase.make_content`.
        if self.template:
            recipe, receipt, _rng = rulebase.make_content(seed=seed, force=force)
            grid = None
        else:
            recipe, receipt, grid = rulebase.make(seed=seed, force=force)
        with profiling.stage("render"):
            hand_report = sign_report = None
            if self.template:
                from sheets import build as build_sheet

                override = None if self.template == "auto" else self.template
                markup = build_sheet(recipe, receipt, override)
                if self.sign:
                    # Signed BEFORE the fields are filled in, which is not the
                    # order a person does it in but is the order the markup
                    # requires: `handwriting.fill` can replace a `sign.name`
                    # run with an `<img>` of ink, and `signature.WHO` will not
                    # match a run containing markup. See `signature.fill`.
                    import signature

                    markup, sign_report = signature.fill(
                        markup, seed=seed, names=signers(seed),
                        source=self.sign,
                        # The same worker `--handwriting model` already keeps
                        # alive, when both are on: one checkpoint load a run,
                        # not one per signature block.
                        hand=self.hand if getattr(
                            self.hand, "source", "") == "model" else None)
                if self.hand is not None:
                    # After the sheet is built and before a pixel is drawn:
                    # the form is printed first and filled in second, which is
                    # also the order that keeps every family able to be
                    # hand-filled without one of them knowing about ink.
                    import handwriting

                    markup, hand_report = handwriting.fill(
                        markup, self.hand, seed=seed)
                markup = markup.replace("{FONT_FACES}", font_faces())
            else:
                markup = build_html(grid, recipe, receipt)

            page = self._browser.new_page(device_scale_factor=self.scale)
        try:
            with profiling.stage("render"):
                # Served from a file, not `set_content`: see `page.served`.
                with served(markup) as uri:
                    page.goto(uri, wait_until="load")
                page.wait_for_timeout(60)  # let the embedded faces settle
                sheet = page.query_selector("#sheet")
            # Measured before the screenshot and from the same laid-out page, so
            # the boxes describe the pixels that were captured rather than a
            # second, re-measured layout.
            with profiling.stage("geometry"):
                rects = page.evaluate(CELL_RECTS_JS)
                regions = page.evaluate(CELL_REGIONS_JS) if self.template else []
            with profiling.stage("render"):
                shot = sheet.screenshot(type="png")
        finally:
            with profiling.stage("render"):
                page.close()

        with profiling.stage("render"):
            image = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)

            # Render large and shrink, never the reverse: the text stays crisp,
            # and the result lands in the same size band as the glyph renderer,
            # so the two are comparable at the pixel level and not only in
            # content.
            target = random.Random(seed).randint(*self.short_size)
            factor = target / min(image.shape[:2])
            if factor < 1.0:
                image = cv2.resize(
                    image,
                    (max(int(image.shape[1] * factor), 1),
                     max(int(image.shape[0] * factor), 1)),
                    interpolation=cv2.INTER_AREA,
                )
            else:
                factor = 1.0

        with profiling.stage("geometry"):
            boxes = quads_from_rects(rects, self.scale, factor)
            cells = regions_from_rects(regions, self.scale, factor)

        # Ageing runs after the boxes are computed and must not move a pixel --
        # every model in `degradation/` filters or composites in place. Asserted
        # rather than assumed: a resize slipped into the chain would shift every
        # box without changing anything visible about the image.
        before = image.shape[:2]
        with profiling.stage("degradation"):
            # The boxes go in as well as the image: `by_box` puts a model on a
            # few text boxes rather than on the whole sheet, and the boxes are
            # the only thing that says where those are. Computed just above, so
            # they describe THIS page rather than the one before ageing shifted
            # anything -- which is also why nothing in the chain may move a
            # pixel. See degradation/regions.py.
            aged = apply_recipe(image, recipe, seed=seed, boxes=boxes)
        if aged.shape[:2] != before:
            raise RuntimeError(
                f"a degradation resized the page ({before} -> {aged.shape[:2]}); "
                "the boxes no longer describe it"
            )
        return recipe, receipt, grid, aged, boxes, cells, hand_report, sign_report


def signers(seed: int, count: int = 6) -> list[str]:
    """Who signs the blocks that print no name.

    Most signature blocks in the rule space print none: only a document with
    `signature_names` puts a name under the caption, and the rest carry a bare
    *(Ký, ghi rõ họ tên)* and a blank. Somebody signs those, and the names come
    from `rulebase.corpus.people` -- the same corpus the documents draw their
    buyers from -- rather than from a list invented in the renderer.

    Drawn from the page's own seed, so a page is signed by the people its seed
    has always been signed by.
    """
    from rulebase import corpus  # noqa: PLC0415 -- a corpus read, not a rule

    people = corpus.people()
    rng = random.Random(seed ^ 0x5349474E)
    return [rng.choice(people) for _ in range(count)] if people else []


def structure_from_cells(cells: list[dict]) -> list[str]:
    """PPStructure tokens for the cells, in row order.

    Same format `tables.py` and PP-Structure write, so anything that reads those
    reads this. Built from the measured cells rather than from the template, so
    it describes the table the browser actually laid out.
    """
    from sheets import structure_tokens

    rows: dict[int, list[dict]] = {}
    for cell in cells:
        rows.setdefault(cell["row"], []).append(cell)
    ordered = [sorted(rows[row], key=lambda c: c["col"]) for row in sorted(rows)]
    return structure_tokens(ordered)


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
    parser.add_argument("--scale", type=float, default=2.0)
    parser.add_argument(
        "--template", metavar="MODEL", nargs="?", const="auto", default="auto",
        help="which page model to draw: `grid` is the character grid, `auto` is the CSS sheet for this recipe's layout, or name a layout id to force its dress. Defaults to `auto` -- every layout has a sheet, and the grid is now the thing you ask for. See generators/html/sheets/",
    )
    parser.add_argument(
        "--handwriting", nargs="?", const="model", default=None,
        choices=["model", "font"], metavar="SOURCE",
        help="fill the fields a person fills in with handwriting instead of "
             "type. `model` (the default) is the WriteViT checkpoint -- real "
             "generated ink, but it cannot write digits or ALL-CAPS and so "
             "reaches 42%% of the fields at best. `font` is a licensed "
             "handwriting typeface from fonts/hand/, which fills every field "
             "but repeats: one hand per face, every `a` the same `a`. Only "
             "with --template. See generators/html/handwriting.py",
    )
    parser.add_argument(
        "--signature", nargs="?", const="font", default=None,
        choices=["font", "model"], metavar="SOURCE",
        help="draw a signature above each printed name in a signature block: "
             "an enlarged initial, a body that degenerates into a scrawl, a "
             "lifted terminal and a paraph. `font` (the default) stretches "
             "outlines from fonts/hand/; `model` traces WriteViT's own ink, "
             "which is thin and joined-up and different every time, and draws "
             "only the styles the checkpoint can write, so a name signs as a "
             "name rather than as a monogram it would have to refuse. "
             "Unlabelled on purpose, so a reader has to learn to "
             "leave it alone. Only with --template. See "
             "generators/html/signature.py",
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

    # Resolved once, here: `grid` becomes None so every `if self.template:`
    # below keeps meaning "draw a sheet", and an unknown value stops the run
    # instead of quietly drawing the grid.
    try:
        args.template = sheets.resolve(args.template)
    except KeyError as error:
        parser.error(str(error))

    if args.handwriting and not args.template:
        parser.error(
            "--handwriting needs --template: the character grid draws one glyph "
            "per cell and has no field for a person to fill in.")
    if args.signature and not args.template:
        parser.error(
            "--signature needs --template: the character grid has no signature "
            "block to sign, only cells.")

    args.out.mkdir(parents=True, exist_ok=True)
    jobs = worklist.load(args)
    # One parse per job rather than one per page: `parse_force` reads the rules
    # to validate the pin, and a job list is many pages over few distinct pins.
    forces = {job: rulebase.parse_force(job.pins(args.force), job.layout)
              for job in jobs}

    hand = None
    if args.handwriting:
        import handwriting

        with profiling.stage("startup"):
            # Opened before the browser and closed after it, so a failure to
            # find the checkpoint costs nothing: there is no fallback that
            # draws letters, so a run asking for ink and not getting it must
            # stop rather than quietly produce printed pages. A missing clone
            # is a setup mistake and reads as one -- the traceback above it
            # says nothing a person needs.
            try:
                hand = handwriting.source(args.handwriting).open()
            except RuntimeError as error:
                parser.error(str(error))
        print(f"[hand] {args.handwriting} on {hand.device}")

    with profiling.stage("startup"):
        renderer = HtmlReceiptRenderer(scale=args.scale, template=args.template,
                                       hand=hand, sign=args.signature)
        renderer.__enter__()
    try:
        # Streamed, not collected: a job list may be a whole shard, and a record
        # carries every box on the page. Written in page order, which is the
        # order the caller listed the jobs in -- `pipeline/worker.py` walks the
        # runs in that order to name the files.
        with synthesis.Writer(synthesis.beside(args.out), "html") as notes:
            for index, job, seed in worklist.pages(jobs):
                recipe, receipt, _grid, image, boxes, cells, hand_report, sign_report = (
                    renderer.render(seed, forces[job]))
                name = f"html_{index:03d}.jpg"
                with profiling.stage("export"):
                    cv2.imwrite(str(args.out / name), image,
                                [cv2.IMWRITE_JPEG_QUALITY, 90])
                with profiling.stage("annotation"):
                    # Which page model drew THIS image. At set level in
                    # `dataset.json` it could not say whether a set was mixed;
                    # per image it can, and a reader no longer has to infer it
                    # from the pixels.
                    extra = {"page_model": args.template or sheets.GRID}
                    if hand_report is not None:
                        # What was written and what refused, per page. A sheet
                        # that asked for handwriting and got two inked fields
                        # is a fact about the checkpoint, and it belongs in the
                        # record beside the blocks rather than in a log nobody
                        # keeps -- see docs/handwriting-html.md.
                        extra["handwriting"] = hand_report
                    if sign_report is not None:
                        # The style of every mark on the page, and every block
                        # that went unsigned. A signature carries no box and no
                        # text, so this record is the only place it exists in
                        # the label at all -- and a set that wanted signatures
                        # and drew none should say so here.
                        extra["signature"] = sign_report
                    if cells:
                        # Additive, and only for a template render: the
                        # structure half of the label, so a merged cell is
                        # recoverable. The blocks are untouched, so every
                        # existing loader keeps working.
                        extra["cells"] = cells
                        extra["structure"] = structure_from_cells(cells)
                    item = record.build(
                        filename=name, width=image.shape[1], height=image.shape[0],
                        parser="html", boxes=boxes,
                        extracted=receipt.ground_truth(),
                        seed=seed, layout=recipe.layout.id)
                with profiling.stage("export"):
                    # The record beside its image, and the provenance streamed
                    # into the one file for the set -- so a shard's memory does
                    # not grow with its size and the two stay in step page for
                    # page.
                    record.write_one(item, args.out, strict=False)
                    notes.add(name, job_id=item["job_id"], layout=recipe.layout.id,
                              recipe=recipe.to_dict(),
                              text_sequence=receipt.text_sequence(), extra=extra)
                inked = len(hand_report["inked"]) if hand_report else 0
                signed = len(sign_report["marks"]) if sign_report else 0
                print(f"[ok] {name}  {image.shape[1]}x{image.shape[0]}  "
                      f"{recipe.layout.id}  {len(boxes)} boxes"
                      + (f"  {inked} inked" if hand_report is not None else "")
                      + (f"  {signed} signed" if sign_report is not None else ""))
    finally:
        with profiling.stage("startup"):
            renderer.__exit__(None, None, None)
            if hand is not None:
                hand.close()

    if profile:
        profiling.dump(profile, {"backend": "html", "images": worklist.total(jobs),
                                 "jobs": len(jobs)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
