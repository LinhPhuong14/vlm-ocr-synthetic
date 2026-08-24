"""The signature engine's output, in the two ways it is worth looking at.

    generators/html/.venv/bin/python tools/signature_showcase.py \\
        -o samples/signatures

**A grid of marks per ink source**, to see the parameter ranges doing their job
-- one signature is not evidence of anything, and a range that has been pushed
too hard shows up in eighteen of them at a glance. And **two signed pages**, one
from a layout that prints a name under the caption and one from a layout that
leaves the line blank, because those are the two shapes of signature block in
the rule space and the second is the majority.

The model grid is skipped, with a line saying so, when WriteViT is not cloned:
it is 1.7 GB beside the repository and `styles.jpg` should still be
regenerable without it. `--source model` demands it instead of skipping.

Pages are drawn with `augmentation=pristine`: this is a catalogue of ink, and a
heavy chain over the top would be judging the degradations instead. What the
set looks like aged is `make dataset` and is not this.

Needs the html renderer's virtualenv -- Chromium rasterises the SVG here for
the same reason it draws the pages, which is that it is the renderer the set
is actually built with.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

import signature  # noqa: E402

from tools.paths import VENVS, venv_python  # noqa: E402

# Names from the corpus the documents draw their own buyers from, so the grid
# is signed with the same kind of name a page is. Five, against eighteen seeds,
# so a style can be compared across names and a name across styles.
NAMES = ("Nguyễn Thị Bích Ngọc", "Lê Quang Đạo", "Trần Văn Hùng",
         "Phạm Minh Tuấn", "Đặng Đình Đức")
SEEDS = tuple(range(1, 19))

# One layout of each shape. `invoice_hotel_stay` sets `signature_names`, so it
# prints "Lễ tân" and "Khách hàng" with a name under each; `invoice_vat_form`
# prints the caption, the instruction "(Ký, ghi rõ họ tên)" and a blank -- and
# a blank is what most of the rule space has.
PAGES = (
    ("signed-folio", "invoice_hotel_stay", 0, "font"),
    ("signed-form", "invoice_vat_form", 3, "font"),
    ("signed-model", "invoice_vat_form", 4, "model"),
)


def grid(out: Path, stem: str, source: str = "font",
         columns: int = 3, cell: float = 150.0) -> dict:
    """One contact sheet, as SVG. `raster` turns it into the JPG beside it.

    Built here rather than through `signature.sheet` for the model, because
    that opens a signer per seed and the model source would then stand up a
    WriteViT worker eighteen times. One worker, eighteen marks.
    """
    marks = []
    hand = None
    try:
        if source == "model":
            import handwriting  # noqa: PLC0415

            hand = handwriting.Hand().open()
        for index, seed in enumerate(SEEDS):
            signer = signature._signer(seed, source, signature.HAND_FONT_DIR, hand)
            try:
                marks.append((seed, signer.sign(NAMES[index % len(NAMES)])))
            except (ValueError, RuntimeError) as error:
                # The checkpoint has no ALL-CAPS, so about a third of the
                # styles are monograms it cannot write. On a page `fill` falls
                # back to the font; on a catalogue of THIS source's ink, saying
                # so is more useful than quietly substituting the other one.
                print(f"     seed {seed}: {str(error)[:60]}")
            finally:
                signer.close()
                signer.ink.close()
    finally:
        if hand is not None:
            hand.close()

    (out / f"{stem}.svg").write_text(
        _sheet(marks, columns=columns, cell=cell), encoding="utf-8")
    return {"source": source, "names": list(NAMES), "seeds": list(SEEDS),
            "marks": [mark.report() for _seed, mark in marks]}


def _sheet(marks: list, columns: int = 3, cell: float = 150.0) -> str:
    """`signature.sheet`'s layout over marks that are already drawn."""
    row_h, ink_h = cell * 0.66, cell * 0.44
    tiles = []
    for index, (seed, mark) in enumerate(marks):
        x0, y0, x1, y1 = mark.box
        scale = min(cell * 0.86 / max(x1 - x0, 1e-6), ink_h / max(y1 - y0, 1e-6))
        flipped = signature.mapped(
            mark.path, lambda point: ((point[0] - x0) * scale, (y1 - point[1]) * scale))
        left, top = (index % columns) * cell, (index // columns) * row_h
        cx = left + (cell - (x1 - x0) * scale) / 2.0
        cy = top + (ink_h - (y1 - y0) * scale) / 2.0 + cell * 0.06
        tiles.append(
            f'<g transform="translate({cx:.1f},{cy:.1f})">'
            f'<path d="{signature.d(flipped, 1)}" fill="{signature.PEN}" '
            f'fill-rule="nonzero"/></g>'
            f'<text x="{left + cell / 2:.0f}" y="{top + row_h - 7:.0f}" '
            f'text-anchor="middle" font-family="monospace" font-size="7.5" '
            f'fill="#8a8a92">{signature.seed_label(mark, seed)}</text>')
    rows = (len(marks) + columns - 1) // columns
    height = rows * row_h + 8
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{columns * cell:.0f}" height="{height:.0f}" '
            f'viewBox="0 0 {columns * cell:.0f} {height:.0f}">'
            f'<rect width="100%" height="100%" fill="#fbfbf7"/>'
            f'{"".join(tiles)}</svg>')


def raster(svg: Path, jpg: Path, scale: float = 2.0) -> None:
    """SVG -> JPG through the renderer's own Chromium.

    A second rasteriser would be a second answer to how a curve is filled, and
    the whole point of this sample is to show what the page will look like.

    JPG rather than PNG, and that is `.gitignore`'s decision rather than a
    graphics one: `samples/**/*.jpg` is let back in and PNG is not, so a PNG
    here would be a sample nobody outside this working copy ever sees. The SVG
    beside it is the vector original, for anyone who wants to zoom.
    """
    from page import find_chromium  # noqa: PLC0415 -- html venv only
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as play:
        browser = play.chromium.launch(executable_path=find_chromium())
        page = browser.new_page(device_scale_factor=scale)
        page.goto(svg.resolve().as_uri())
        page.locator("svg").first.screenshot(path=str(jpg), type="jpeg",
                                             quality=94)
        browser.close()


def pages(out: Path, model: bool) -> list:
    """Real sheets, signed, through `render.py` rather than around it."""
    python = venv_python(VENVS["html"])
    python = python if python.exists() else Path(sys.executable)
    drawn = []
    for name, layout, seed, source in PAGES:
        if source == "model" and not model:
            print(f"[skip] {name}: WriteViT is not cloned")
            continue
        work = out / ("_" + name)
        subprocess.run(
            [str(python), str(REPO_ROOT / "generators" / "html" / "render.py"),
             "--template", "auto", "--signature", source, "--layout", layout,
             "--force", "augmentation=pristine", "--seed", str(seed),
             "-c", "1", "-o", str(work)],
            check=True)
        (work / "html_000.jpg").replace(out / f"{name}.jpg")
        record = json.loads((work / "metadata.jsonl").read_text(encoding="utf-8"))
        drawn.append({"file": f"{name}.jpg", "layout": layout, "seed": seed,
                      "source": source, "signature": record.get("signature")})
        for leftover in sorted(work.iterdir()):
            leftover.unlink()
        work.rmdir()
    return drawn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path,
                        default=REPO_ROOT / "samples" / "signatures")
    parser.add_argument("--no-pages", action="store_true",
                        help="only the grids; skips the renders")
    parser.add_argument("--source", choices=["font", "model", "both"],
                        default="both",
                        help="which ink to catalogue. `both` (the default) "
                             "quietly leaves the model out when WriteViT is "
                             "not cloned; `model` fails instead")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    import handwriting  # noqa: PLC0415

    have_model = Path(handwriting.WRITEVIT_DIR).is_dir()
    if args.source == "model" and not have_model:
        raise SystemExit(f"WriteViT is not at {handwriting.WRITEVIT_DIR}; "
                         "run tools/writevit/setup.py")
    model = have_model and args.source in ("model", "both")

    report = {"grids": []}
    wanted = [("styles", "font")] if args.source != "model" else []
    if model:
        wanted.append(("styles-model", "model"))
    for stem, source in wanted:
        print(f"[..] {stem}: {source}")
        report["grids"].append(grid(args.out, stem, source))
        raster(args.out / f"{stem}.svg", args.out / f"{stem}.jpg")
        print(f"[ok] {args.out / (stem + '.jpg')}  "
              f"{len(report['grids'][-1]['marks'])} marks")
    if not model:
        print("[skip] styles-model: WriteViT is not cloned")

    report["pages"] = [] if args.no_pages else pages(args.out, model)
    for entry in report["pages"]:
        marks = len((entry["signature"] or {}).get("marks", []))
        print(f"[ok] {args.out / entry['file']}  {entry['layout']}  {marks} signed")

    (args.out / "signatures.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
