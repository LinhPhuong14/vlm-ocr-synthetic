"""Table-structure pages, drawn by the browser this backend already launches.

A generator used to be vendored for this job: it builds a random table and
labels it the way PubTabNet does -- the `<td>` token sequence, the row and
column spans, a box per cell. The label format is the right one and is kept
here byte for byte, so anything that reads PubTabNet or PP-Structure reads
this.

The *renderer* was never a second method. It is Selenium driving Chrome, with
boxes read from `element.location` and `element.size` -- the same engine and the
same DOM geometry `render.py` gets from `getBoundingClientRect`, reached a
slower way (one round trip per cell instead of one `evaluate` for the page).
Two browsers, two virtualenvs and a chromedriver version dance, for one
rasteriser. So the generator moved here.

The table model below is upstream's (TIES_DataGeneration, by way of PaddleOCR's
TableGeneration, Apache-2.0): the same seven border styles, the same first-row
column spans and first-column row spans, the same missing cells. Four things
are this repository's, and each fixes something that mattered:

* **Whole words, not character slices.** Upstream fills a cell with a random
  *character* slice of its corpus, so a cell reads `ình Thọ Ng`. That is a
  defensible choice for pure structure recognition and the wrong one here,
  where the point is Vietnamese a model can actually read.
* **The repo's fonts, embedded.** Upstream takes whatever the container has --
  which is how a Vietnamese dataset ends up with the tone marks missing and the
  label still claiming they were printed.
* **Money written by `rulebase.text.money`.** Upstream writes `$123.45`. The
  same function that spells money on every receipt spells it here.
* **Seeded per image.** Upstream seeds the global RNG once and puts a random
  suffix in each file name, so image 40 cannot be rebuilt without rebuilding
  0-39 first.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import dataclass, field
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# From `page.py`, not `render.py`: everything above the browser -- the table
# model, the markup, the label -- has to be importable without Playwright and
# OpenCV, or the tests would need a browser stack to check a token list.
from page import CELL_REGIONS_JS, find_chromium, font_faces, served  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from pipeline import record, synthesis  # noqa: E402
from rulebase import corpus  # noqa: E402
from rulebase.text import ascii_fold, money  # noqa: E402

# Upstream's seven, by the names it gives them: the file name of every image
# carries one, and a dataset built before this change stays comparable to one
# built after it.
BORDERS: dict[str, dict[str, str]] = {
    "border": {"table": "border:1px solid black;",
               "td": "border:1px solid black;",
               "th": "border:1px solid black;"},
    "border_top": {"table": "border-top:1px solid black;",
                   "td": "border-top:1px solid black;",
                   "th": "border-top:1px solid black;"},
    "border_bottom": {"table": "border-bottom:1px solid black;",
                      "td": "border-bottom:1px solid black;",
                      "th": "border-bottom:1px solid black;"},
    "head_border_bottom": {"th": "border-bottom:1px solid black;"},
    "no_border": {},
    "border_left": {"table": "border-left:1px solid black;",
                    "td": "border-left:1px solid black;",
                    "th": "border-left:1px solid black;"},
    "border_right": {"table": "border-right:1px solid black;",
                     "td": "border-right:1px solid black;",
                     "th": "border-right:1px solid black;"},
}

# Exactly as `_font_faces` names them -- it builds each family from the file
# stem, so "LiberationMono" and not "Liberation Mono". A name with a space in it
# matches no embedded face and falls through to whatever the container has.
FAMILIES = ("LiberationMono", "LiberationSans", "LiberationSerif", "Arimo", "NotoSans")
HEADER_ROWS = 2

_PHRASES: list[str] | None = None


def phrases() -> list[str]:
    """Every phrase the Vietnamese corpus owns, deduplicated, read once.

    The same lists the receipts draw from -- product names, shop names, streets,
    wards, payment methods, footers -- so a table's glyph distribution is the
    dataset's glyph distribution and not a second, accidental one.
    """
    global _PHRASES
    if _PHRASES is not None:
        return _PHRASES
    words: list[str] = [name for name, _lo, _hi in
                        corpus.items("eatery") + corpus.items("market")]
    for row in corpus.shops("market"):
        words.extend(row)
    words.extend(row[0] for row in corpus.shops("eatery"))
    words.extend(corpus.streets())
    words.extend(ward[0] for ward in corpus.wards())
    words.extend(payment[0] for payment in corpus.payments())
    words.extend(corpus.footers("eatery") + corpus.footers("market"))
    words.extend(corpus.people())

    seen: set[str] = set()
    unique: list[str] = []
    for word in words:
        word = " ".join(str(word).split())
        if word and word not in seen:
            seen.add(word)
            unique.append(word)
    _PHRASES = unique
    return unique


# ------------------------------------------------------------- the table


@dataclass
class Table:
    """A table as a pair of span matrices, before any of it is HTML.

    `colspan[r][c]` and `rowspan[r][c]` follow upstream: 0 is an ordinary cell,
    n > 1 spans that many, and -1 marks a cell swallowed by a span above or to
    the left of it, which is written out neither as HTML nor as a token.
    """

    rows: int
    cols: int
    border: str
    align: str
    family: str
    style: str                       # money separator: 'dot' or 'comma'
    col_types: list[str]
    colspan: list[list[int]]
    rowspan: list[list[int]]
    header_cols: int = 1
    missing: set[tuple[int, int]] = field(default_factory=set)
    tint: dict[tuple[int, int], str] = field(default_factory=dict)

    def is_header(self, row: int, col: int) -> bool:
        return row < HEADER_ROWS or col < self.header_cols


def _span_indices(rng: random.Random, extent: int, most: int,
                  longest: int) -> list[tuple[int, int]]:
    """Where spans start and how long they run, along one axis.

    Upstream's `agnostic_span_indices`, kept because its output distribution is
    what makes the vendored dataset look the way it does: a handful of spans,
    never overlapping, each at least two cells long.
    """
    count = rng.randint(1, most)
    if count >= extent:
        return []
    chosen = sorted(rng.sample(range(extent), count))
    spans: list[tuple[int, int]] = []
    after = 0
    for index in chosen:
        if after > index:
            continue
        room = extent - index
        if room < 2:
            break
        length = rng.randint(1, min(room, longest))
        if length > 1:
            spans.append((index, length))
            after = index + length
    return spans


def build_table(rng: random.Random, *, min_row: int, max_row: int,
                min_col: int, max_col: int, max_span_row: int, max_span_col: int,
                max_span: int, colour_prob: float) -> Table:
    rows = rng.randint(min_row, max_row)
    cols = rng.randint(min_col, max_col)
    table = Table(
        rows=rows,
        cols=cols,
        border=rng.choice(list(BORDERS)),
        align=rng.choices(["left", "right", "center"], weights=[0.25, 0.25, 0.5])[0],
        family=rng.choice(FAMILIES),
        style=rng.choice(["dot", "comma"]),
        col_types=rng.choices(["n", "m", "w", "a"], weights=[0.5, 0.1, 0.3, 0.1], k=cols),
        colspan=[[0] * cols for _ in range(rows)],
        rowspan=[[0] * cols for _ in range(rows)],
    )

    # First row: some columns merge, and the ones that do not run down through
    # the second header row instead. That pair is what a real table's head looks
    # like, and it is the reason a structure label is worth having at all.
    if max_span_col > 0:
        merged: set[int] = set()
        for _ in range(20):
            spans = _span_indices(rng, cols, max_span_col, max_span)
            if spans:
                break
        else:
            spans = []
        for start, length in spans:
            table.colspan[0][start] = length
            for col in range(start + 1, start + length):
                table.colspan[0][col] = -1
            merged.update(range(start, start + length))
        for col in range(cols):
            if col not in merged:
                table.rowspan[0][col] = 2
                table.rowspan[1][col] = -1

    # First column: a stub column whose cells run over several body rows.
    if max_span_row > 0 and rows > HEADER_ROWS:
        for start, length in _span_indices(rng, rows - HEADER_ROWS,
                                           max_span_row, max_span):
            start += HEADER_ROWS
            table.rowspan[start][0] = length
            for row in range(start + 1, start + length):
                table.rowspan[row][0] = -1

    # Empty cells, as many as the log of the area -- upstream's rule, and it
    # scales the way a hand-made table does: a big table has a few gaps, not a
    # proportional number of them.
    body_rows = max(rows - HEADER_ROWS, 1)
    body_cols = max(cols - table.header_cols, 1)
    for _ in range(int(math.log(rows * cols, 2))):
        table.missing.add((HEADER_ROWS + rng.randrange(body_rows),
                           table.header_cols + rng.randrange(body_cols)))

    for row in range(rows):
        for col in range(cols):
            if rng.random() < colour_prob:
                table.tint[(row, col)] = "#%02x%02x%02x" % (
                    rng.randint(200, 255), rng.randint(200, 255), rng.randint(200, 255))
    return table


def cell_text(rng: random.Random, table: Table, row: int, col: int) -> str:
    """What goes in one cell. Whole words in every case, never a slice."""
    if (row, col) in table.missing and table.colspan[row][col] == 0:
        return ""
    kind = "w" if row < HEADER_ROWS or col == 0 else table.col_types[col]
    if kind in ("n", "m"):
        ceiling = rng.choice([100, 1_000, 10_000, 1_000_000])
        value = rng.random() * ceiling
        if kind == "m":
            return money(round(value), table.style, suffix=rng.choice(["", " đ"]))
        if rng.random() < 0.4:
            return f"{value:.2f}"
        return money(round(value), table.style)
    words = rng.choice(phrases()).split()
    start = rng.randrange(len(words))
    text = " ".join(words[start:start + rng.randint(1, 3)])
    return ascii_fold(text) if kind == "a" else text


# --------------------------------------------------------------- the page


def build_page(table: Table, rng: random.Random, *, box_type: str = "cell") -> tuple[str, list[str]]:
    """The HTML, and the PPStructure tokens that describe it.

    Both are produced in one walk on purpose. A token list built separately
    from the markup is a label that can drift from the page it labels, which is
    exactly the failure a structure dataset cannot survive.
    """
    borders = BORDERS[table.border]
    rules = [
        "html,body{margin:0;padding:0;background:#fff;}",
        "#sheet{display:inline-block;background:#fff;padding:%dpx;}" % rng.randint(6, 18),
        "table{border-collapse:collapse;font-family:'%s',monospace;font-size:%dpx;"
        "text-align:%s;%s}" % (table.family, rng.randint(15, 22), table.align,
                               borders.get("table", "")),
        "td{word-break:break-all;padding:%dpx %dpx;%s}" % (
            rng.randint(2, 8), rng.randint(4, 14), borders.get("td", "")),
        "th{padding:6px 15px;%s}" % borders.get("th", ""),
    ]

    markup = ["<!doctype html><html><head><meta charset='utf-8'><style>",
              font_faces(), "\n", "\n".join(rules),
              "</style></head><body><div id='sheet'><table>"]
    tokens: list[str] = []

    for row in range(table.rows):
        markup.append("<tr>")
        tokens.append("<tr>")
        for col in range(table.cols):
            rowspan, colspan = table.rowspan[row][col], table.colspan[row][col]
            if rowspan == -1 or colspan == -1:
                continue
            tag = "th" if table.is_header(row, col) else "td"
            attrs = [f' data-row="{row}" data-col="{col}"']
            tokens.append("<td>" if rowspan <= 1 and colspan <= 1 else "<td")
            if rowspan > 1:
                attrs.append(f' rowspan="{rowspan}"')
                tokens.append(f' rowspan="{rowspan}"')
            if colspan > 1:
                attrs.append(f' colspan="{colspan}"')
                tokens.append(f' colspan="{colspan}"')
            if rowspan > 1 or colspan > 1:
                tokens.append(">")
            tint = table.tint.get((row, col))
            if tint:
                attrs.append(f' style="background-color:{tint};"')

            text = escape(cell_text(rng, table, row, col))
            # `data-cell` is what the box extractor selects on, and where it
            # sits is the whole difference between the two box types: on the
            # `<td>` the box is the cell, on a `<span>` inside it the box is the
            # text. Upstream calls the choice `cell_box_type`; it is the same
            # choice, made in the same place.
            if box_type == "text":
                inner = (f'<span data-cell="text" data-row="{row}" '
                         f'data-col="{col}">{text}</span>')
                markup.append(f"<{tag}{''.join(attrs)}>{inner}</{tag}>")
            else:
                attrs.insert(0, ' data-cell="cell"')
                markup.append(f"<{tag}{''.join(attrs)}>{text}</{tag}>")
            tokens.append("</td>")
        markup.append("</tr>")
        tokens.append("</tr>")

    markup.append("</table></div></body></html>")
    return "".join(markup), tokens


# -------------------------------------------------------------- the label


def ppstructure_label(file_name: str, tokens: list[str], cells: list[dict]) -> dict:
    """Upstream's label, unchanged -- including the bbox nesting.

    `bbox` is a list holding one quad rather than the quad itself. That is an
    upstream quirk and it is kept: the format's only value is that other tools
    already read it, and a tidier one nobody reads is worth nothing.
    """
    label = {
        "filename": file_name,
        "html": {
            "structure": {"tokens": tokens},
            "cells": [{"tokens": list(cell["text"]), "bbox": [cell["quad"]]}
                      for cell in cells],
        },
    }
    label["gt"] = rebuild_html(label)
    return label


def rebuild_html(label: dict) -> str:
    """The tokens and the cell texts, woven back into one HTML string."""
    code = list(label["html"]["structure"]["tokens"])
    slots = [i for i, token in enumerate(code) if token in ("<td>", ">")]
    for slot, cell in zip(slots[::-1], label["html"]["cells"][::-1]):
        if cell["tokens"]:
            text = "".join(escape(token) if len(token) == 1 else token
                           for token in cell["tokens"])
            code.insert(slot + 1, text)
    return "<html><body><table>{}</table></body></html>".format("".join(code))


def metadata_record(label: dict, width: int, height: int, seed: int = 0,
                    border: str = "") -> dict:
    """The same label in this repository's index shape.

    The *envelope* is the one every other page is written in -- the converter's
    schema, built by `pipeline/record.py` -- and the `task` is what says this
    one is not a document: `table_structure`, not `convert`. So one loader finds
    both, which is what the index is for, and neither label pretends to be the
    other.

    Inside that envelope a table's label is still its own thing. A document's
    `extracted` is a parsed receipt; a table has no fields to extract and the
    key is `null`. A document's `html` is its text laid out; a table's *is* the
    structure, so `gt` goes there verbatim. And there is no honest markdown for
    a table with merged cells, so `markdown` is left empty rather than filled
    with something a reader would have to un-guess.

    The structure tokens and the cell boxes are the *label*, not provenance, so
    they stay where PP-Structure readers already look: `gt.txt`, beside the
    index. What goes in `synthesis.json` is what made the page.
    """
    cells = label["html"]["cells"]
    built = record.build(
        filename=label["filename"], width=width, height=height, parser="html",
        task=record.TASK_TABLE,
        boxes=[{"kind": "cell", "text": "".join(cell["tokens"]),
                "quad": (cell["bbox"] or [None])[0]} for cell in cells],
        extracted=None, seed=seed, layout=border,
    )
    built["html"] = label["gt"]
    built["markdown"] = ""
    return built


# ------------------------------------------------------------ the renderer


class TableRenderer:
    """One browser for the whole run, exactly as `HtmlReceiptRenderer` does."""

    def __init__(self, scale: float = 2.0, max_side: int = 1200,
                 box_type: str = "cell", **shape):
        self.scale = scale
        self.max_side = max_side
        self.box_type = box_type
        self.shape = shape
        self._playwright = None
        self._browser = None

    def __enter__(self):
        from playwright.sync_api import sync_playwright

        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(executable_path=find_chromium())
        return self

    def __exit__(self, *exc):
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()

    def render(self, seed: int):
        rng = random.Random(seed)
        table = build_table(rng, **self.shape)
        markup, tokens = build_page(table, rng, box_type=self.box_type)

        page = self._browser.new_page(device_scale_factor=self.scale)
        try:
            # Served from a file, not `set_content`: see `page.served`.
            with served(markup) as uri:
                page.goto(uri, wait_until="load")
            page.wait_for_timeout(60)          # let the embedded faces settle
            rects = page.evaluate(CELL_REGIONS_JS)
            shot = page.query_selector("#sheet").screenshot(type="png")
        finally:
            page.close()

        import cv2
        import numpy as np

        image = cv2.imdecode(np.frombuffer(shot, np.uint8), cv2.IMREAD_COLOR)
        # The LONG side, not the short one. A table is often wide and only a
        # few rows tall, so capping the short side leaves it at full raster
        # size -- 1912 x 342 for a three-row table, and a dataset four times
        # the weight it needs to be.
        factor = min(self.max_side / max(image.shape[:2]), 1.0)
        if factor < 1.0:
            image = cv2.resize(image,
                               (max(int(image.shape[1] * factor), 1),
                                max(int(image.shape[0] * factor), 1)),
                               interpolation=cv2.INTER_AREA)

        ratio = self.scale * factor
        cells = []
        for rect in rects:
            x0, y0 = rect["x"] * ratio, rect["y"] * ratio
            x1, y1 = x0 + rect["w"] * ratio, y0 + rect["h"] * ratio
            cells.append({
                "text": rect["text"],
                "quad": [[round(x0, 1), round(y0, 1)], [round(x1, 1), round(y0, 1)],
                         [round(x1, 1), round(y1, 1)], [round(x0, 1), round(y1, 1)]],
            })
        return table, markup, tokens, cells, image


# ------------------------------------------------------------------- main


def generate(out: Path, count: int, seed: int, *, box_type: str = "cell",
             scale: float = 2.0, max_side: int = 1200, **shape) -> int:
    import cv2

    (out / "img").mkdir(parents=True, exist_ok=True)
    (out / "html").mkdir(parents=True, exist_ok=True)

    records, labels, notes = [], [], []
    with TableRenderer(scale=scale, max_side=max_side,
                       box_type=box_type, **shape) as renderer:
        for index in range(count):
            table, markup, tokens, cells, image = renderer.render(seed + index)
            stem = f"{table.border}_{index:04d}"
            name = f"img/{stem}.jpg"
            cv2.imwrite(str(out / name), image, [int(cv2.IMWRITE_JPEG_QUALITY), 92])
            (out / "html" / f"{stem}.html").write_text(markup, encoding="utf-8")

            label = ppstructure_label(name, tokens, cells)
            labels.append(label)
            item = metadata_record(label, image.shape[1], image.shape[0],
                                   seed + index, table.border)
            records.append(item)
            # A table has no rule-base recipe: what made this page is its seed
            # and the border style it drew, and `border` is the nearest thing it
            # has to a layout.
            notes.append((name, {
                "job_id": item["job_id"], "layout": table.border,
                "recipe": {"seed": seed + index, "attributes": {}, "tags": []},
                "extra": {"rows": table.rows, "cols": table.cols,
                          "n_cells": len(cells)},
            }))
            print(f"[ok] {name}  {image.shape[1]}x{image.shape[0]}  "
                  f"{table.rows}x{table.cols}  {table.border}  {len(cells)} cells")

    with open(out / "gt.txt", "w", encoding="utf-8") as handle:
        for label in labels:
            json.dump(label, handle, ensure_ascii=False)
            handle.write("\n")
    with open(out / "metadata.jsonl", "w", encoding="utf-8") as handle:
        for item in records:
            json.dump(item, handle, ensure_ascii=False)
            handle.write("\n")
    synthesis.write(synthesis.beside(out), "html", notes)
    return len(records)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--out", type=Path, default=REPO_ROOT / "data" / "tables60")
    parser.add_argument("-n", "--count", type=int, default=60)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--box", choices=["cell", "text"], default="cell",
                        help="cell: the box is the <td>. text: the box is the text in it")
    parser.add_argument("--scale", type=float, default=2.0)
    parser.add_argument("--max-side", type=int, default=1200,
                        help="cap on the longer side of the image, in pixels")
    parser.add_argument("--min-row", type=int, default=3)
    parser.add_argument("--max-row", type=int, default=12)
    parser.add_argument("--min-col", type=int, default=3)
    parser.add_argument("--max-col", type=int, default=7)
    parser.add_argument("--max-span-row", type=int, default=3)
    parser.add_argument("--max-span-col", type=int, default=3)
    parser.add_argument("--max-span", type=int, default=10)
    parser.add_argument("--colour-prob", type=float, default=0.3)
    args = parser.parse_args()

    written = generate(
        args.out, args.count, args.seed,
        box_type=args.box, scale=args.scale, max_side=args.max_side,
        min_row=args.min_row, max_row=args.max_row,
        min_col=args.min_col, max_col=args.max_col,
        max_span_row=args.max_span_row, max_span_col=args.max_span_col,
        max_span=args.max_span, colour_prob=args.colour_prob,
    )
    print(f"\n{written} bảng -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
