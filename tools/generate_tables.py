"""Table-structure images, from the html backend.

    python tools/generate_tables.py -o data/tables60 -n 60

The generator itself is `generators/html/tables.py`, next to the receipt
renderer, because it is the same renderer: Chromium, and boxes measured off the
laid-out DOM. It used to be a vendored generator driven through Selenium,
and this file was three workarounds for running that -- a `google-chrome` shim
on PATH, a chromedriver whose major version matched the browser, and a corpus
file to keep the cells out of Chinese. None of the three has anything to do
with generating a table; all three were the cost of a second copy of a browser
backend. See the module docstring in `generators/html/tables.py` for what
survived the move and what changed.

Run it with the html backend's interpreter -- it needs Playwright and OpenCV:

    generators/html/.venv/bin/python tools/generate_tables.py

or just `make tables`, which picks the right one.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))
sys.path.insert(0, str(REPO_ROOT))


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
    parser.add_argument("--colour-prob", type=float, default=0.3,
                        help="fraction of cells given a pale background")
    args = parser.parse_args()

    try:
        from tables import generate
    except ImportError as error:  # noqa: BLE001 -- re-raised with the fix
        raise SystemExit(
            f"{error}\n\nRun this with the html backend's interpreter:\n"
            "  generators/html/.venv/bin/python tools/generate_tables.py\n"
            "or `make tables`, which does that for you. `make setup-html` "
            "builds the environment."
        ) from error

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
