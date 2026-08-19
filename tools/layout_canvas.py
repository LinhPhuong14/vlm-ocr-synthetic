"""One contact sheet per renderer: every layout, clean above augmented.

    python3 tools/layout_canvas.py --clean data/run_clean --aug data/run_aug \
                                   -o data/layout_canvas

Two sheets per renderer, because they answer different questions:

* `canvas_data.jpg` -- two rows, one column per bố cục. The top row is the page
  with an empty degradation chain, the bottom row is the *same* page (same seed,
  same receipt) after its chain ran. Reading a column tells you what the ageing
  did; reading a row tells you whether a layout still looks like itself.
* `canvas_bbox.jpg` -- one row, the augmented page with its `boxes` drawn on.
  The boxes come from the label, not from the image, so this is the check that
  the labels still describe the pixels *after* the page was aged, curled and
  photographed. A quad that has slid off its text is visible here and nowhere
  else.

Only Pillow and the standard library: this runs on the bare system Python, so
looking at a run never depends on which renderer environment got built.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent

BACKENDS = ("synthdog", "html", "genalog")

FONT_DIR = REPO_ROOT / "fonts" / "sans"
FONT_REGULAR = FONT_DIR / "DejaVuSans.ttf"
FONT_BOLD = FONT_DIR / "DejaVuSans-Bold.ttf"

PAPER = (238, 238, 234)      # the sheet the contact sheet is printed on
CELL_BG = (255, 255, 255)
RULE = (198, 198, 192)
INK = (28, 28, 30)
FAINT = (110, 110, 114)

# One colour per top-level `kind` -- `menu.0.nm` and `menu.3.price` are the same
# family. Colouring every kind separately gives fourteen indistinguishable reds;
# colouring by family is what makes "the totals block slid" visible at a glance.
FAMILY_COLOURS = {
    "store": (0, 122, 204),
    "meta": (150, 90, 200),
    "menu": (220, 60, 60),
    "total": (0, 150, 80),
    "footer": (230, 140, 0),
    "title": (20, 20, 20),
}
OTHER_COLOUR = (120, 120, 130)


def font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(path), size)
    except OSError:
        return ImageFont.load_default()


def family(kind: str) -> str:
    return str(kind).split(".", 1)[0]


def colour_for(kind: str) -> tuple[int, int, int]:
    return FAMILY_COLOURS.get(family(kind), OTHER_COLOUR)


# --------------------------------------------------------------- reading a run


def read_records(directory: Path) -> dict[str, dict]:
    """`layout -> record` for one renderer's output directory.

    Keyed by layout because that is what pairs a clean page with its aged twin:
    the file *names* are positional and would still line up if one of the two
    runs planned its layouts in a different order, which is exactly the silent
    mispairing this avoids.
    """
    path = directory / "metadata.jsonl"
    if not path.exists():
        return {}
    records: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        layout = item.get("layout") or item["recipe"]["attributes"]["layout"]["id"]
        # First wins: a run with more images than layouts repeats them, and the
        # first of each is the one whose seed matches across the two runs.
        records.setdefault(layout, item)
    return records


# --------------------------------------------------------------- drawing a cell


def fit(image: Image.Image, width: int, height: int) -> tuple[Image.Image, float, int, int]:
    """Letterbox `image` into a cell. Returns the tile and how to map a box onto it.

    The scale and the offsets are returned rather than applied, because the
    boxes have to travel through exactly the same transform as the pixels did
    -- recomputing it at the call site is how a quad ends up half a cell away
    from its text.
    """
    scale = min(width / image.width, height / image.height)
    size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
    tile = image.resize(size, Image.LANCZOS)
    return tile, scale, (width - size[0]) // 2, (height - size[1]) // 2


def draw_boxes(tile: Image.Image, boxes: list[dict], scale: float) -> None:
    """Draw one polygon per labelled field, in the tile's own coordinates.

    Polygons, not rectangles: the glyph backend's quads follow the curl of the
    paper and are genuinely rotated. Drawing their bounding box instead would
    hide the one property this repository claims only that renderer has.
    """
    canvas = ImageDraw.Draw(tile, "RGBA")
    for box in boxes:
        quad = box.get("quad") or []
        if len(quad) < 3:
            continue
        points = [(x * scale, y * scale) for x, y in quad]
        red, green, blue = colour_for(box.get("kind", ""))
        canvas.polygon(points, fill=(red, green, blue, 38))
        canvas.line(points + [points[0]], fill=(red, green, blue, 255), width=2)


# -------------------------------------------------------------- the two sheets


def chain_of(record: dict) -> str:
    """Which degradation chain the rules drew for this page."""
    return record["recipe"]["attributes"]["augmentation"]["id"]


def cell_grid(rows: list[list[tuple[Path, dict, bool, str]]], columns: list[str], *,
              title: str, row_labels: list[str], cell: tuple[int, int],
              legend: bool) -> Image.Image:
    """The shared frame: a title, a column head per layout, a label per row."""
    cell_w, cell_h = cell
    gap = 10
    pad = 22
    gutter = 108          # room down the left for the row labels
    head_h = 62           # the title strip
    col_h = 30            # the layout name over each column
    legend_h = 44 if legend else 0

    width = pad * 2 + gutter + len(columns) * cell_w + (len(columns) - 1) * gap
    height = (pad * 2 + head_h + col_h + legend_h
              + len(rows) * cell_h + (len(rows) - 1) * gap)

    sheet = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(sheet)
    title_font = font(FONT_BOLD, 30)
    column_font = font(FONT_BOLD, 17)
    label_font = font(FONT_BOLD, 20)
    small_font = font(FONT_REGULAR, 15)

    draw.text((pad, pad + 4), title, font=title_font, fill=INK)

    top = pad + head_h
    if legend:
        x = pad
        draw.text((x, top + 12), "boxes:", font=small_font, fill=FAINT)
        x += 58
        for name, (red, green, blue) in list(FAMILY_COLOURS.items()) + [("other", OTHER_COLOUR)]:
            draw.rectangle([x, top + 12, x + 16, top + 27], fill=(red, green, blue))
            draw.text((x + 22, top + 12), name, font=small_font, fill=INK)
            x += 30 + int(draw.textlength(name, font=small_font))
        top += legend_h

    # Column heads, then the rows under them.
    for index, layout in enumerate(columns):
        x = pad + gutter + index * (cell_w + gap)
        text = layout
        while draw.textlength(text, font=column_font) > cell_w - 6 and len(text) > 4:
            text = text[:-1]
        draw.text((x + (cell_w - draw.textlength(text, font=column_font)) / 2,
                   top + 6), text, font=column_font, fill=INK)
    top += col_h

    for row_index, row in enumerate(rows):
        y = top + row_index * (cell_h + gap)
        draw.text((pad + 6, y + cell_h // 2 - 12), row_labels[row_index],
                  font=label_font, fill=INK)
        for column_index, entry in enumerate(row):
            x = pad + gutter + column_index * (cell_w + gap)
            draw.rectangle([x, y, x + cell_w - 1, y + cell_h - 1],
                           fill=CELL_BG, outline=RULE)
            if entry is None:
                draw.text((x + 12, y + cell_h // 2), "— missing —",
                          font=small_font, fill=FAINT)
                continue
            path, record, with_boxes, caption = entry
            with Image.open(path) as opened:
                image = opened.convert("RGB")
            # The caption strip is reserved out of the cell rather than drawn
            # over the tile: a chain name on top of the page is unreadable
            # exactly on the dark chains it matters most for.
            tile, scale, offset_x, offset_y = fit(image, cell_w - 8, cell_h - 8 - 20)
            if with_boxes:
                draw_boxes(tile, record.get("boxes") or [], scale)
            sheet.paste(tile, (x + 4 + offset_x, y + 4 + offset_y))
            if caption:
                draw.text((x + 6, y + cell_h - 18), caption, font=small_font, fill=FAINT)
    return sheet


def build(backend: str, clean_root: Path, aug_root: Path, out: Path,
          data_cell: tuple[int, int], bbox_cell: tuple[int, int],
          quality: int) -> list[str]:
    clean_dir = clean_root / backend
    aug_dir = aug_root / backend
    clean = read_records(clean_dir)
    aged = read_records(aug_dir)
    if not aged:
        return []

    # Column order follows the augmented run's file order, which is the plan's
    # layout order -- alphabetical here would reorder the families.
    columns = sorted(aged, key=lambda layout: aged[layout]["file_name"])
    written = []

    data_rows = [
        [(clean_dir / clean[layout]["file_name"], clean[layout], False,
          chain_of(clean[layout])) if layout in clean else None
         for layout in columns],
        [(aug_dir / aged[layout]["file_name"], aged[layout], False,
          chain_of(aged[layout])) for layout in columns],
    ]
    sheet = cell_grid(
        data_rows, columns,
        title=f"{backend} — {len(columns)} bố cục — clean (trên) / augmented (dưới)",
        row_labels=["clean", "augmented"], cell=data_cell, legend=False)
    out.mkdir(parents=True, exist_ok=True)
    sheet.save(out / "canvas_data.jpg", quality=quality, subsampling=1)
    written.append(str(out / "canvas_data.jpg"))

    bbox_rows = [[(aug_dir / aged[layout]["file_name"], aged[layout], True,
                   f"{chain_of(aged[layout])} · {len(aged[layout].get('boxes') or [])} boxes")
                  for layout in columns]]
    sheet = cell_grid(
        bbox_rows, columns,
        title=f"{backend} — {len(columns)} bố cục — augmented + bbox từ nhãn",
        row_labels=["bbox"], cell=bbox_cell, legend=True)
    sheet.save(out / "canvas_bbox.jpg", quality=quality, subsampling=1)
    written.append(str(out / "canvas_bbox.jpg"))
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clean", type=Path, required=True,
                        help="dataset built with --clean")
    parser.add_argument("--aug", type=Path, required=True,
                        help="the same seed, with its degradation chain")
    parser.add_argument("-o", "--out", type=Path,
                        default=REPO_ROOT / "data" / "layout_canvas")
    parser.add_argument("--backends", nargs="+", default=list(BACKENDS))
    # 1.3 is not a guess: the pages this rule-base draws run from 0.78 to 1.8
    # in height/width, clustered near 1.0, so a taller cell spends most of its
    # area on white margin and makes every page smaller for the sake of the one
    # long thermal roll.
    parser.add_argument("--data-cell", type=int, nargs=2, default=(640, 830),
                        metavar=("W", "H"))
    parser.add_argument("--bbox-cell", type=int, nargs=2, default=(900, 1170),
                        metavar=("W", "H"))
    parser.add_argument("--quality", type=int, default=88)
    args = parser.parse_args()

    total = 0
    for backend in args.backends:
        written = build(backend, args.clean, args.aug, args.out / backend,
                        tuple(args.data_cell), tuple(args.bbox_cell), args.quality)
        if not written:
            print(f"[skip] {backend}: nothing in {args.aug / backend}", file=sys.stderr)
            continue
        for path in written:
            size = Path(path).stat().st_size
            with Image.open(path) as image:
                print(f"[ok] {path}  {image.width}x{image.height}  {size // 1024} KB")
        total += len(written)
    return 0 if total else 1


if __name__ == "__main__":
    raise SystemExit(main())
