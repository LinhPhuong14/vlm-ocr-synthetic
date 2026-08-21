"""Do any two text boxes on a page sit on top of each other?

    python3 overlap.py /tmp/sweep/metadata.jsonl

Measured from the boxes the renderer itself wrote, so it checks what the engine
drew rather than what a reader thought they saw. Separators and column-number
rows are excluded: neither is a field, and a rule under a line of text is meant
to be near it.

Two numbers, because they mean different things. A pair overlapping by more than
30% of the smaller box is text on top of text and is a defect. A pair that
merely touches is normal typography -- adjacent cells in a ruled table share an
edge -- and is printed only as context.
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

SKIP = {"sep", "colnum"}


def rect(quad):
    xs = [point[0] for point in quad]
    ys = [point[1] for point in quad]
    return min(xs), min(ys), max(xs), max(ys)


def area(box):
    return max(box[2] - box[0], 0) * max(box[3] - box[1], 0)


def intersection(a, b):
    return area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))


def main(path: Path, threshold: float = 0.30) -> int:
    bad: dict[str, int] = defaultdict(int)
    touching: dict[str, int] = defaultdict(int)
    pages = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        item = json.loads(line)
        pages += 1
        layout = item["recipe"]["attributes"]["layout"]["id"]
        boxes = [box for box in (item.get("boxes") or [])
                 if box.get("kind") not in SKIP and (box.get("text") or "").strip()]
        rects = [(rect(box["quad"]), box) for box in boxes]
        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                (ra, ba), (rb, bb) = rects[i], rects[j]
                overlap = intersection(ra, rb)
                if not overlap:
                    continue
                if overlap / max(min(area(ra), area(rb)), 1) > threshold:
                    bad[layout] += 1
                    print(f"{layout}: {ba['text'][:34]!r} over {bb['text'][:34]!r}")
                else:
                    touching[layout] += 1
    print(f"\n{pages} pages")
    for layout in sorted(set(bad) | set(touching)):
        print(f"  {layout:24} over>{threshold:.0%}: {bad[layout]:3d}   touching: "
              f"{touching[layout]:4d}")
    print("OVERLAPPING" if bad else "no pair overlaps by more than %.0f%%" % (threshold * 100))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1])))
