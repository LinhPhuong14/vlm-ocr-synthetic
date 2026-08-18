"""Check that every renderer's boxes still describe its pixels.

    python tools/check_boxes.py data/dataset60

Box coverage is the kind of thing that breaks silently. The first version of
the genalog extractor lost every field after the first separator row -- the
images were fine, the labels were fine, `metadata.jsonl` was well-formed, and
coverage was 82% instead of 100%. Nothing but counting the cells would have
said so.

Three things are checked per image, and each catches a different failure:

* **coverage** -- one box per drawn field. Catches a desynchronised match.
* **inside the frame** -- every corner within the image. Catches a missed
  scale factor: boxes measured before a resize are systematically too large,
  and the ones near the right edge fall off it.
* **on some ink** -- the darkest pixel under the box is clearly darker than
  the median under the same box. Catches boxes that are the right size in the
  wrong place, which the first two tests pass happily.

Separators are expected to have no box: a row of dashes is not a field, and a
detector taught to find one fires on every rule on the page.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

import rulebase  # noqa: E402

# Frameworks that emit boxes. The table generator writes per-cell bboxes in a
# different schema and against a different task, so `data/tables60/` is checked
# by `tests/test_tables.py` and by its own generator rather than here.
FRAMEWORKS = ("synthdog", "html", "genalog")


def expected_fields(record: dict) -> list[tuple[str, str]] | None:
    """The (role, text) pairs this image should have a box for.

    Rebuilt from the recipe rather than trusted from the record, which is the
    whole point -- a label that agreed with itself would prove nothing.

    **The seed alone does not reproduce the page.** `generate_dataset.py` pins
    the layout so each renderer draws every one equally often, and a pin does
    not merely filter: with `layout` restricted to one value, the tags it sets
    differ, and every attribute drawn afterwards diverges. Rebuilding from the
    bare seed therefore yields a different receipt, and the check reports every
    field of every image as missing -- which is exactly what it did first.

    So all six attributes are pinned back to what was recorded, and the result
    is required to land on the recorded seed. Anything else means the rules
    changed since the dataset was generated, which is reported rather than
    quietly passed.
    """
    recipe = record.get("recipe") or {}
    seed = recipe.get("seed")
    attributes = recipe.get("attributes") or {}
    if seed is None or not attributes:
        return None

    force = {name: value["id"] for name, value in attributes.items() if "id" in value}
    try:
        rebuilt, _receipt, grid = rulebase.make(seed=seed, force=force)
    except Exception:  # noqa: BLE001 - a rule that no longer exists lands here
        return None
    if rebuilt.seed != seed:
        return None
    return [(cell.role, cell.text) for cell in grid.cells
            if cell.text.strip() and cell.role != "sep"]


def _has_ink(image: np.ndarray, quad, margin: int = 25) -> bool:
    """Is there something clearly darker than the paper inside this box?

    Contrast is measured against the median *inside the box*, not against the
    page. A global median works for a flat scan and fails for the glyph
    renderer, whose pages are photographs: the dark room behind the sheet drags
    the whole-image median down to roughly the ink's own level, and every box
    on the receipt then reads as empty. That false alarm is what this local
    comparison exists to avoid.
    """
    xs = [point[0] for point in quad]
    ys = [point[1] for point in quad]
    x0, x1 = int(max(min(xs), 0)), int(min(max(xs), image.shape[1]))
    y0, y1 = int(max(min(ys), 0)), int(min(max(ys), image.shape[0]))
    if x1 <= x0 or y1 <= y0:
        return False
    patch = image[y0:y1, x0:x1]
    return float(np.median(patch)) - float(patch.min()) > margin


def check_image(directory: Path, record: dict) -> list[str]:
    problems: list[str] = []
    name = record["file_name"]
    boxes = record.get("boxes")
    if not boxes:
        return [f"{name}: no boxes at all"]

    fields = expected_fields(record)
    if fields is None:
        problems.append(f"{name}: recipe does not rebuild; coverage unchecked")
    else:
        have = {(box["kind"], box["text"]) for box in boxes}
        for role, text in fields:
            if (role, text) not in have:
                problems.append(f"{name}: no box for {role} {text[:30]!r}")

    image = cv2.imread(str(directory / name), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return problems + [f"{name}: image unreadable"]
    height, width = image.shape[:2]

    outside = 0
    blank = 0
    for box in boxes:
        quad = box["quad"]
        if any(not (-1 <= x <= width + 1 and -1 <= y <= height + 1) for x, y in quad):
            outside += 1
        elif not _has_ink(image, quad):
            blank += 1
    if outside:
        problems.append(f"{name}: {outside}/{len(boxes)} boxes fall outside the image")
    # A few blanks are legitimate -- a hole or a heavy stain can erase the text
    # under a box, and that is the label still being right about a page that
    # lost its ink. A large share is a placement bug.
    if blank > max(2, len(boxes) // 5):
        problems.append(f"{name}: {blank}/{len(boxes)} boxes sit on blank paper")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset", type=Path, nargs="?",
                        default=REPO_ROOT / "data" / "dataset60")
    args = parser.parse_args()

    total_problems = 0
    for framework in FRAMEWORKS:
        directory = args.dataset / framework
        metadata = directory / "metadata.jsonl"
        if not metadata.exists():
            print(f"[skip] {framework}: no metadata.jsonl")
            continue

        records = [json.loads(line) for line in
                   metadata.read_text(encoding="utf-8").splitlines() if line.strip()]
        problems: list[str] = []
        boxes = 0
        for record in records:
            boxes += len(record.get("boxes") or [])
            problems += check_image(directory, record)

        total_problems += len(problems)
        state = "ok" if not problems else "PROBLEM"
        print(f"[{state}] {framework}: {len(records)} images, {boxes} boxes")
        for problem in problems[:12]:
            print(f"    - {problem}")
        if len(problems) > 12:
            print(f"    ... and {len(problems) - 12} more")

    if total_problems:
        raise SystemExit(f"\n{total_problems} problems")
    print("\nmọi box đều khớp ảnh")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
