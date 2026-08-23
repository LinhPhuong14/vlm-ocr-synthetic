"""Check that every renderer's boxes still describe its pixels.

    python tools/check_boxes.py data/dataset60

Box coverage is the kind of thing that breaks silently. The first version of
the genalog extractor lost every field after the first separator row -- the
images were fine, the labels were fine, `metadata.jsonl` was well-formed, and
coverage was 82% instead of 100%. Nothing but counting the cells would have
said so.

Three things are checked per image, and each catches a different failure:

* **coverage** -- one box per drawn field. Catches a desynchronised match. What
  counts as a drawn field depends on the page model: the character grid's cells,
  or, for a set drawn with `--template`, the labelled runs of the CSS sheet
  (`dataset.json` says which).
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

# `record` is the name of a metadata line all over this file, so the module that
# defines their shape comes in under a name that cannot shadow one.
from pipeline import record as schema  # noqa: E402
from pipeline import synthesis  # noqa: E402

# Frameworks that emit boxes. The table generator writes per-cell bboxes in a
# different schema and against a different task, so `data/tables60/` is checked
# by `tests/test_tables.py` and by its own generator rather than here.
FRAMEWORKS = ("synthdog", "html", "genalog")


def expected_fields(recipe: dict, template: str = "") -> list[tuple[str, str]] | None:
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
    seed = (recipe or {}).get("seed")
    attributes = (recipe or {}).get("attributes") or {}
    if seed is None or not attributes:
        return None

    force = {name: value["id"] for name, value in attributes.items() if "id" in value}
    try:
        if template:
            # A CSS sheet has no character grid, and building one would not only
            # be the wrong list of fields -- `build_grid` cuts a value that will
            # not fit a character column and writes the cut back, so the
            # rebuilt "expected" text would be shorter than what was printed.
            sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))
            import sheets  # noqa: PLC0415 -- optional, and only on this path

            rebuilt, receipt, _rng = rulebase.make_content(seed=seed, force=force)
            if rebuilt.seed != seed:
                return None
            override = None if template == "auto" else template
            return sheets.labelled_runs(sheets.build(rebuilt, receipt, override))
        rebuilt, _receipt, grid = rulebase.make(seed=seed, force=force)
    except Exception:  # noqa: BLE001 - a rule that no longer exists lands here
        return None
    if rebuilt.seed != seed:
        return None
    return [(cell.role, cell.text) for cell in grid.cells
            if cell.text.strip() and cell.role != "sep"]


def _has_ink(image: np.ndarray, quad, margin: int = 25) -> bool:
    """Is there anything clearly standing out from the paper inside this box?

    Contrast is measured against the median *inside the box*, not against the
    page. A global median works for a flat scan and fails for the glyph
    renderer, whose pages are photographs: the dark room behind the sheet drags
    the whole-image median down to roughly the ink's own level, and every box
    on the receipt then reads as empty. That false alarm is what this local
    comparison exists to avoid.

    **In either direction**, and that is not symmetry for its own sake. A
    branded invoice reverses its masthead out of a colour bar -- white type on
    teal -- and type lighter than its background is still type. Looking only
    downwards reported 15 of 61 boxes on `invoice_hotel_compact` as sitting on
    blank paper, in both HTML renderers, on a page where every one of them was
    squarely on a word.
    """
    xs = [point[0] for point in quad]
    ys = [point[1] for point in quad]
    x0, x1 = int(max(min(xs), 0)), int(min(max(xs), image.shape[1]))
    y0, y1 = int(max(min(ys), 0)), int(min(max(ys), image.shape[0]))
    if x1 <= x0 or y1 <= y0:
        return False
    patch = image[y0:y1, x0:x1]
    middle = float(np.median(patch))
    return max(middle - float(patch.min()), float(patch.max()) - middle) > margin


def check_image(directory: Path, item: dict, recipe: dict,
                template: str = "") -> list[str]:
    problems: list[str] = []
    name = schema.file_name(item)
    boxes = schema.boxes(item)
    if not boxes:
        return [f"{name}: no boxes at all"]

    fields = expected_fields(recipe, template)
    if fields is None:
        problems.append(f"{name}: recipe does not rebuild; coverage unchecked")
    elif template:
        # A sheet wraps, and a run that wrapped is several boxes -- one per
        # line, so the quad is round the words and not round the blank paper
        # between two ragged ends. So the run is looked for in the boxes of its
        # own kind joined together, not as one box. Joining per kind rather than
        # over the page is what stops an unrelated field matching by accident.
        joined: dict[str, str] = {}
        for box in boxes:
            joined[box["kind"]] = " ".join(
                (joined.get(box["kind"], "") + " " + box.get("text", "")).split())
        for role, text in fields:
            wanted = " ".join(text.split())
            if wanted and wanted not in joined.get(role, ""):
                problems.append(f"{name}: no box for {role} {text[:30]!r}")
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

    # Which page model drew this set. Written by `pipeline/run.py`; absent on
    # every set built before `generators/html/sheets/` existed, which is the
    # character grid and is what this tool has always assumed.
    template = ""
    manifest = args.dataset / "dataset.json"
    if manifest.exists():
        template = str(json.loads(manifest.read_text(encoding="utf-8"))
                       .get("template", "") or "")

    total_problems = 0
    for framework in FRAMEWORKS:
        directory = args.dataset / framework
        metadata = directory / "metadata.jsonl"
        if not metadata.exists():
            print(f"[skip] {framework}: no metadata.jsonl")
            continue

        records = schema.read(metadata)
        # The recipe is what this file rebuilds a page from, and it is beside
        # the index rather than in it. Without it there is nothing to check the
        # boxes *against*, so a missing file is reported and the framework
        # skipped -- not quietly scored as clean.
        try:
            drew = synthesis.read(directory)
        except synthesis.SynthesisError as error:
            print(f"[PROBLEM] {framework}: {error}")
            total_problems += 1
            continue
        problems: list[str] = []
        boxes = 0
        for item in records:
            boxes += len(schema.boxes(item))
            problems += check_image(directory, item,
                                    drew.recipe(schema.file_name(item)), template)

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
