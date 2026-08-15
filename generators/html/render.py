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
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import rulebase  # noqa: E402
from degradation.pipeline import apply_recipe  # noqa: E402

FONT_ROOT = REPO_ROOT / "fonts"
# Linux containers that ship a browser system-wide, this repository's own
# included. Elsewhere -- Windows, macOS, a plain `pip install playwright` --
# there is nothing here and Playwright resolves its own download instead.
CHROMIUM_CANDIDATES = [
    Path("/opt/pw-browsers/chromium/chrome-linux/chrome"),
    Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome"),
    Path("/usr/bin/chromium"),
    Path("/usr/bin/chromium-browser"),
]


def find_chromium() -> str | None:
    """A browser to launch, or None to let Playwright pick its own.

    Returning None is not a failure: `launch(executable_path=None)` is the
    normal path, and the only reason to override it is a container that already
    has a build and must not download a second one.
    """
    for path in CHROMIUM_CANDIDATES:
        if path.exists():
            return str(path)
    for path in sorted(Path("/opt/pw-browsers").glob("chromium*/chrome-linux/chrome")):
        return str(path)
    return None


def _font_faces() -> str:
    """Embed the repo's fonts so the browser cannot silently substitute.

    A CSS stack that falls through to whatever the container happens to have
    is how a receipt ends up rendered in a font with no Vietnamese diacritics,
    with the label still claiming they were printed.
    """
    faces = []
    for group in ("mono", "sans"):
        directory = FONT_ROOT / group
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.ttf")):
            family = path.stem.replace("-Regular", "").replace("-Bold", "")
            weight = "700" if path.stem.endswith("-Bold") else "400"
            faces.append(
                "@font-face{font-family:'%s';font-weight:%s;src:url('file://%s') format('truetype');}"
                % (family.replace("-", " "), weight, path)
            )
    return "\n".join(faces)


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
        spans.append(
            f'<span style="{style}"><i style="{inner}">{html.escape(cell.text)}</i></span>'
        )

    tint_layer = (
        f'<div id="tint" style="background:rgb({tint[0]},{tint[1]},{tint[2]});'
        f'opacity:{tint_alpha:.3f}"></div>'
        if tint_alpha > 0
        else ""
    )

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
{_font_faces()}
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
  height:{grid.nrows * line_px + pad_top + pad_bottom:.2f}px;
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
#tint{{position:absolute;inset:0;pointer-events:none;}}
</style></head>
<body><div id="sheet">{"".join(spans)}{tint_layer}</div></body></html>"""


class HtmlReceiptRenderer:
    """Keeps one browser alive across a run -- launching costs ~300 ms each time."""

    def __init__(self, scale: float = 2.0, short_size: tuple[int, int] = (960, 1400)):
        self.scale = scale
        self.short_size = short_size
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
        recipe, receipt, grid = rulebase.make(seed=seed, force=force)
        markup = build_html(grid, recipe, receipt)

        page = self._browser.new_page(device_scale_factor=self.scale)
        try:
            page.set_content(markup, wait_until="load")
            page.wait_for_timeout(60)  # let the embedded faces settle
            sheet = page.query_selector("#sheet")
            shot = sheet.screenshot(type="png")
        finally:
            page.close()

        image = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)

        # Render large and shrink, never the reverse: the text stays crisp, and
        # the result lands in the same size band as the glyph renderer, so the
        # two are comparable at the pixel level and not only in content.
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
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    force = rulebase.parse_force(args.force, args.layout)
    records = []

    with HtmlReceiptRenderer(scale=args.scale) as renderer:
        for index in range(args.count):
            recipe, receipt, _grid, image = renderer.render(args.seed + index, force)
            name = f"html_{index:03d}.jpg"
            cv2.imwrite(str(args.out / name), image, [cv2.IMWRITE_JPEG_QUALITY, 90])
            records.append({
                "file_name": name,
                "ground_truth": json.dumps({"gt_parse": receipt.ground_truth()},
                                           ensure_ascii=False),
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
