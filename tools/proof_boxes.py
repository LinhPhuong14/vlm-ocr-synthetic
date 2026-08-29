"""One proof image per generated image: the page with its own label drawn on it.

    python tools/proof_boxes.py --dataset data/5k_llm

`tools/check_boxes.py` answers "do the boxes land on ink" with a number, which
is the right shape for a gate and the wrong shape for a person. This writes the
picture instead: every labelled run outlined on the page it was read off,
coloured by what the label calls it, with a legend. Two minutes with a handful
of these says more about whether a set is usable than any coverage percentage,
and at 5000 images the ones worth looking at are the ones you can only find by
looking.

Deliberately not part of the renderer. A proof is a *reading* of a finished
dataset -- it uses only the image and the record beside it, exactly what a
consumer of the set has -- so it cannot accidentally prove itself right by
sharing state with the thing that drew the page.

Colours group by the family a `kind` belongs to rather than by the kind itself:
`menu.name`, `menu.qty` and `menu.amount` are one table and read as one colour,
which is what makes a missing column visible at a glance.
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pipeline import record as schema  # noqa: E402

# BGR, because OpenCV. Ordered widest-family-first; `family` takes the first
# prefix that matches, so `total.grand.label` lands on `total` and not on a
# catch-all.
FAMILIES: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("menu", (60, 170, 60)),          # the item table
    ("total", (40, 90, 220)),         # money at the bottom
    ("invoice", (200, 120, 40)),      # serial block and form fields
    ("store", (190, 60, 180)),        # who issued it
    ("colhdr", (150, 150, 150)),      # column titles
    ("sign", (30, 190, 220)),         # signature captions
    ("title", (30, 30, 210)),         # the doc title and subtitle
    ("subtitle", (30, 30, 210)),
    ("period", (120, 90, 200)),
    ("note", (110, 110, 110)),
    ("footer", (110, 110, 110)),
)
OTHER = (80, 80, 80)
LEGEND_HEIGHT = 26


def family(kind: str) -> tuple[str, tuple[int, int, int]]:
    head = str(kind or "").split(".")[0]
    for name, colour in FAMILIES:
        if head == name:
            return name, colour
    return "khác", OTHER


def _tag(overlay, text: str, x: int, y: int, colour, scale: float = 0.32) -> None:
    """The box's own `kind`, written where it will still be readable on ink.

    Drawn on a filled chip rather than straight onto the page: a proof sheet is
    read over printed text and half of these labels would otherwise land on a
    table rule. The chip is the box's own colour so the tag and its outline are
    obviously the same thing.
    """
    import cv2

    (width, height), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, 1)
    top = max(0, y - height - 4)
    cv2.rectangle(overlay, (x, top), (x + width + 4, top + height + 4), colour, -1)
    cv2.putText(overlay, text, (x + 2, top + height + 1),
                cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 1, cv2.LINE_AA)


def draw(image_path: Path, record_path: Path, out_path: Path,
         legend: bool = True, tags: bool = True) -> bool:
    """Write the proof for one page. False when the image could not be read."""
    import cv2
    import numpy as np

    image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
    if image is None:
        return False
    try:
        item = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False

    overlay = image.copy()
    seen: dict[str, tuple[int, int, int]] = {}
    labels: list[tuple[str, int, int, tuple]] = []
    for box in schema.boxes(item):
        quad = box.get("quad")
        kind = str(box.get("kind", "") or "?")
        name, colour = family(kind)
        seen[name] = colour
        if isinstance(quad, list) and len(quad) >= 4:
            points = np.array([[int(round(x)), int(round(y))] for x, y in quad[:4]],
                              dtype=np.int32)
            cv2.polylines(overlay, [points], True, colour, 1, cv2.LINE_AA)
            labels.append((kind, int(points[:, 0].min()), int(points[:, 1].min()), colour))
            continue
        bbox = box.get("bbox") or {}
        if {"x1", "y1", "x2", "y2"} <= set(bbox):
            cv2.rectangle(overlay, (int(bbox["x1"]), int(bbox["y1"])),
                          (int(bbox["x2"]), int(bbox["y2"])), colour, 1)
            labels.append((kind, int(bbox["x1"]), int(bbox["y1"]), colour))

    # Tags last, so a chip is never overdrawn by the outline of the next box.
    # A page carries hundreds of runs and most of them repeat a kind down a
    # column, so only the first of each kind in a neighbourhood is written:
    # labelling all 431 of a hospital bill's cells makes the sheet unreadable
    # and says nothing the first one did not.
    if tags:
        written: dict[str, list[tuple[int, int]]] = {}
        for kind, x, y, colour in labels:
            near = written.setdefault(kind, [])
            if any(abs(x - px) < 140 and abs(y - py) < 34 for px, py in near):
                continue
            near.append((x, y))
            _tag(overlay, kind, x, y, colour)

    # The boxes stay legible over dark ink without hiding the ink itself: the
    # whole point is to see whether the outline sits on the glyphs.
    proof = cv2.addWeighted(overlay, 0.88, image, 0.12, 0)

    if legend and seen:
        strip = np.full((LEGEND_HEIGHT, proof.shape[1], 3), 245, dtype=np.uint8)
        x = 8
        for name, colour in sorted(seen.items()):
            cv2.rectangle(strip, (x, 8), (x + 14, 18), colour, -1)
            cv2.putText(strip, name, (x + 19, 18), cv2.FONT_HERSHEY_SIMPLEX,
                        0.38, (40, 40, 40), 1, cv2.LINE_AA)
            x += 34 + 8 * len(name)
            if x > proof.shape[1] - 60:
                break
        proof = np.vstack([proof, strip])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), proof, [cv2.IMWRITE_JPEG_QUALITY, 86])
    return True


def _one(job: tuple) -> bool:
    image, item, out = job[:3]
    tags = job[3] if len(job) > 3 else True
    return draw(Path(image), Path(item), Path(out), tags=tags)


def pairs(dataset: Path, framework: str = "html") -> list[tuple[Path, Path]]:
    """(image, record) for every page of a framework, in file order."""
    directory = dataset / framework
    out = []
    for image in sorted(directory.glob("*.jpg")):
        item = image.with_suffix(".json")
        if item.exists():
            out.append((image, item))
    return out


def run(dataset: Path, framework: str = "html", workers: int = 1,
        out_dir: Path | None = None, tags: bool = True) -> tuple[int, int]:
    """Draw every proof. Returns (written, attempted)."""
    out_dir = out_dir or dataset / "proof"
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(str(image), str(item), str(out_dir / image.name), tags)
            for image, item in pairs(dataset, framework)]
    if not jobs:
        return 0, 0
    if workers <= 1:
        return sum(_one(job) for job in jobs), len(jobs)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return sum(pool.map(_one, jobs, chunksize=16)), len(jobs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--framework", default="html")
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--out", type=Path, default=None,
                        help="default: <dataset>/proof")
    parser.add_argument("--no-tags", action="store_true",
                        help="outline the boxes without writing each one's kind")
    args = parser.parse_args()
    written, total = run(args.dataset, args.framework, args.workers, args.out,
                         tags=not args.no_tags)
    print(f"{written}/{total} ảnh proof -> {args.out or args.dataset / 'proof'}")
    return 0 if written == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
