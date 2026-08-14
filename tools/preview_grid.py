"""Print a sampled receipt as monospace text -- no rendering, no dependencies.

    python tools/preview_grid.py --layout quan_nhau_stt --seed 3

The grid is what all three renderers draw, so if a bố cục is wrong it is wrong
here first, and this is far quicker to look at than a JPEG. `--all` walks every
layout once, which is the fastest check after editing `layouts/*.yaml`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rulebase import RuleError, available_layouts, make  # noqa: E402


def to_text(grid) -> str:
    """Paint the cells onto a character canvas, the way a till would."""
    canvas = [[" "] * grid.ncols for _ in range(grid.nrows)]
    for cell in sorted(grid.cells, key=lambda c: (c.row, c.col0)):
        width = max(cell.col1 - cell.col0, 1)
        text = cell.text[:width]
        if cell.align == "right":
            start = cell.col1 - len(text)
        elif cell.align == "center":
            start = cell.col0 + (width - len(text)) // 2
        else:
            start = cell.col0
        start = max(0, min(start, grid.ncols - len(text)))
        while cell.row >= len(canvas):
            canvas.append([" "] * grid.ncols)
        for offset, char in enumerate(text):
            canvas[cell.row][start + offset] = char
    return "\n".join("".join(row).rstrip() for row in canvas)


def show(layout: str | None, seed: int) -> None:
    force = {"layout": layout} if layout else None
    if layout:
        # Not every document kind can carry every bố cục; walk seeds until one
        # draws a compatible document rather than reporting a false failure.
        for attempt in range(seed, seed + 200):
            try:
                recipe, receipt, grid = make(seed=attempt, force=force)
                break
            except RuleError:
                continue
        else:
            raise SystemExit(f"no document kind in the rules can use layout {layout!r}")
    else:
        recipe, receipt, grid = make(seed=seed)

    bar = "=" * max(grid.ncols, 40)
    print(bar)
    print(f"seed={recipe.seed}  " + "  ".join(f"{k}={v}" for k, v in recipe.ids().items()))
    print(bar)
    print(to_text(grid))
    print(bar)
    print(f"{len(receipt.items)} mặt hàng, {grid.nrows} dòng, {grid.ncols} cột\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--layout", help="pin one bố cục; default lets the rules choose")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--all", action="store_true", help="one sample per layout")
    parser.add_argument("-n", "--count", type=int, default=1)
    args = parser.parse_args()

    if args.all:
        for index, layout in enumerate(available_layouts()):
            show(layout, args.seed + index * 17)
        return 0

    for index in range(args.count):
        show(args.layout, args.seed + index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
