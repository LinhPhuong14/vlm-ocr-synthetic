"""The signature engine's output, in the two ways it is worth looking at.

    generators/html/.venv/bin/python tools/signature_showcase.py \\
        -o samples/signatures

**A grid of marks**, to see the parameter ranges doing their job -- one
signature is not evidence of anything, and a range that has been pushed too
hard shows up in eighteen of them at a glance. And **two signed pages**, one
from a layout that prints a name under the caption and one from a layout that
leaves the line blank, because those are the two shapes of signature block in
the rule space and the second is the majority.

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
    ("signed-folio", "invoice_hotel_stay", 0),
    ("signed-form", "invoice_vat_form", 3),
)


def grid(out: Path, columns: int = 3, cell: float = 150.0) -> dict:
    """The contact sheet, as SVG. `raster` turns it into the JPG beside it."""
    body = signature.sheet(list(NAMES), list(SEEDS), columns=columns, cell=cell)
    (out / "styles.svg").write_text(body, encoding="utf-8")

    report = []
    for index, seed in enumerate(SEEDS):
        with signature.Signer(seed) as signer:
            report.append(signer.sign(NAMES[index % len(NAMES)]).report())
    return {"names": list(NAMES), "seeds": list(SEEDS), "marks": report}


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


def pages(out: Path) -> list:
    """Two real sheets, signed, through `render.py` rather than around it."""
    python = venv_python(VENVS["html"])
    python = python if python.exists() else Path(sys.executable)
    drawn = []
    for name, layout, seed in PAGES:
        work = out / ("_" + name)
        subprocess.run(
            [str(python), str(REPO_ROOT / "generators" / "html" / "render.py"),
             "--template", "auto", "--signature", "--layout", layout,
             "--force", "augmentation=pristine", "--seed", str(seed),
             "-c", "1", "-o", str(work)],
            check=True)
        (work / "html_000.jpg").replace(out / f"{name}.jpg")
        record = json.loads((work / "metadata.jsonl").read_text(encoding="utf-8"))
        drawn.append({"file": f"{name}.jpg", "layout": layout, "seed": seed,
                      "signature": record.get("signature")})
        for leftover in sorted(work.iterdir()):
            leftover.unlink()
        work.rmdir()
    return drawn


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path,
                        default=REPO_ROOT / "samples" / "signatures")
    parser.add_argument("--no-pages", action="store_true",
                        help="only the grid; skips the two renders")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    report = grid(args.out)
    raster(args.out / "styles.svg", args.out / "styles.jpg")
    print(f"[ok] {args.out / 'styles.jpg'}  {len(SEEDS)} marks")

    report["pages"] = [] if args.no_pages else pages(args.out)
    for entry in report["pages"]:
        marks = len((entry["signature"] or {}).get("marks", []))
        print(f"[ok] {args.out / entry['file']}  {entry['layout']}  {marks} signed")

    (args.out / "signatures.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
