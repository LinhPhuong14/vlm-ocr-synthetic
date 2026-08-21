"""DOCUMENTATION CODE — builds the figures the README embeds.

    python docs/figures/make_figures.py
    python docs/figures/make_figures.py --families data/ds14   # see below

Not part of the generation pipeline. Nothing here renders a page or ages one:
every pixel comes from a dataset that already exists on disk, and every box
comes from the `metadata.jsonl` a renderer wrote beside it. The script only
crops, scales, labels and tiles, so a figure cannot show anything the generator
did not produce.

Four figures, each answering a question prose alone cannot:

    families.jpg    one page per layout family — what the rule-base covers
    renderers.jpg   one receipt drawn by all three engines
    ageing.jpg      one page with and without its degradation chain
    boxes.jpg       the labelled quads, drawn on the pixels they describe

`ageing.jpg` is a genuine before/after: the aged and the clean set are built
from the same seeds, and the script asserts the two recipes differ in exactly
one attribute -- `augmentation` -- before it draws them.

`families.jpg` needs a dataset that covers more than one family. The committed
sets predate the invoice layouts and hold receipts only, so point `--families`
at a set built with at least one image per layout:

    python tools/generate_dataset.py -o data/ds14 -n 14
    python docs/figures/make_figures.py --families data/ds14

Requires numpy, opencv and PyYAML (`pip install numpy opencv-python-headless
PyYAML`).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import record  # noqa: E402

AGED = REPO_ROOT / "data" / "dataset60"
CLEAN = REPO_ROOT / "data" / "dataset60_clean"
LAYOUT_RULES = REPO_ROOT / "rulebase" / "rules" / "layout.yaml"
FRAMEWORKS = ("synthdog", "html", "genalog")

WHITE = (255, 255, 255)
PANEL_H = 760          # panels are scaled to a common height before tiling
CAPTION_H = 30


def families() -> dict[str, str]:
    """layout id -> family id, read from the parent nodes in the rules.

    Read rather than hard-coded: a family added to `rules/layout.yaml` should
    appear in the figure without anyone remembering to edit this file.
    """
    raw = yaml.safe_load(LAYOUT_RULES.read_text(encoding="utf-8")) or {}
    mapping = {}
    for group in raw.get("groups") or []:
        for option in group.get("options") or []:
            mapping[option["id"]] = group["id"]
    for option in raw.get("options") or []:      # a flat file has no families
        mapping[option["id"]] = ""
    return mapping


def records(root: Path, framework: str) -> list[dict]:
    path = root / framework / "metadata.jsonl"
    if not path.exists():
        raise SystemExit(
            f"missing {path} -- this script draws from a dataset that already "
            f"exists; build one with `make dataset` or point --dataset elsewhere"
        )
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def read(root: Path, framework: str, name: str) -> np.ndarray:
    image = cv2.imread(str(root / framework / name), cv2.IMREAD_COLOR)
    if image is None:
        raise SystemExit(f"cannot read {root / framework / name}")
    return image


def caption(image: np.ndarray, text: str) -> np.ndarray:
    """A titled panel, scaled to a common height so panels tile without gaps.

    Height rather than width: a till roll and an A4 invoice have very different
    aspect, and matching the width leaves the short one in a field of padding.
    """
    factor = PANEL_H / image.shape[0]
    width = max(int(image.shape[1] * factor), 1)
    body = cv2.resize(image, (width, PANEL_H),
                      interpolation=cv2.INTER_AREA if factor < 1 else cv2.INTER_LINEAR)
    # cv2's Hershey fonts are ASCII-only -- anything else renders as "??", so
    # captions stay ASCII even though everything they describe is Vietnamese.
    strip = np.full((CAPTION_H, width, 3), 240, dtype=np.uint8)
    cv2.putText(strip, text, (6, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (25, 25, 25), 1,
                cv2.LINE_AA)
    return np.vstack([strip, body])


def tile(panels: list[np.ndarray], gap: int = 8) -> np.ndarray:
    height = max(panel.shape[0] for panel in panels)
    return np.hstack([
        cv2.copyMakeBorder(panel, 0, height - panel.shape[0], 0, gap,
                           cv2.BORDER_CONSTANT, value=WHITE)
        for panel in panels
    ])


def stack(rows: list[np.ndarray], gap: int = 8) -> np.ndarray:
    width = max(row.shape[1] for row in rows)
    return np.vstack([
        cv2.copyMakeBorder(row, 0, gap, 0, width - row.shape[1], cv2.BORDER_CONSTANT,
                           value=WHITE)
        for row in rows
    ])


def save(image: np.ndarray, path: Path) -> None:
    cv2.imwrite(str(path), image, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"[ok] {path.name}  {image.shape[1]}x{image.shape[0]}")


# ------------------------------------------------------------------ figures


def figure_families(source: Path, out: Path, framework: str = "html") -> None:
    """One page per layout family — the shape of the space, not a sample of it."""
    by_family: dict[str, dict] = {}
    mapping = families()
    for row in records(source, framework):
        family = mapping.get(record.layout(row), "")
        by_family.setdefault(family, row)
    if len(by_family) < 2:
        print(f"[skip] families.jpg: {source} covers {len(by_family)} family; "
              f"see this file's docstring for how to build a set that covers more")
        return
    panels = [
        caption(read(source, framework, record.file_name(row)),
                f"{family}  |  {record.layout(row)}")
        for family, row in sorted(by_family.items())
    ]
    save(tile(panels), out / "families.jpg")


def figure_renderers(aged: Path, out: Path, index: int = 0) -> None:
    """One page, three engines. Paired sets, so it really is the same receipt."""
    panels = []
    for framework in FRAMEWORKS:
        row = records(aged, framework)[index]
        image = read(aged, framework, record.file_name(row))
        panels.append(caption(image, f"{framework}  {record.layout(row)}  "
                                     f"{image.shape[1]}x{image.shape[0]}"))
    save(tile(panels), out / "renderers.jpg")


def figure_ageing(aged: Path, clean: Path, out: Path, index: int = 0) -> None:
    """Before and after the recipe's degradation chain, on the same page."""
    rows = []
    for framework in FRAMEWORKS:
        clean_row = records(clean, framework)[index]
        aged_row = records(aged, framework)[index]
        clean_ids = {k: v["id"] for k, v in record.attributes(clean_row).items()}
        aged_ids = {k: v["id"] for k, v in record.attributes(aged_row).items()}
        differing = {k for k in aged_ids if aged_ids[k] != clean_ids.get(k)}
        # The whole claim of this figure. If the two sets ever stop differing in
        # exactly the augmentation, it is not a before/after any more.
        if differing != {"augmentation"} or clean_ids["augmentation"] != "pristine":
            raise SystemExit(
                f"{framework}: the clean and aged records differ in {sorted(differing)}, "
                f"not in augmentation alone -- this pair is not a before/after"
            )
        rows.append(tile([
            caption(read(clean, framework, record.file_name(clean_row)),
                    f"{framework}  augmentation=pristine"),
            caption(read(aged, framework, record.file_name(aged_row)),
                    f"{framework}  augmentation={aged_ids['augmentation']}"),
        ]))
    save(stack(rows), out / "ageing.jpg")


def figure_boxes(aged: Path, out: Path, index: int = 0) -> None:
    """The `blocks` of metadata.jsonl, drawn on the image they describe."""
    panels = []
    for framework in FRAMEWORKS:
        row = records(aged, framework)[index]
        image = read(aged, framework, record.file_name(row))
        blocks = record.boxes(row)
        for box in blocks:
            quad = np.array(box["quad"], dtype=np.int32).reshape(-1, 1, 2)
            # Amounts in a different colour: they are the fields the OCR proof
            # scores separately, and the ones a wrong scale factor moves first.
            money = box["kind"].startswith("total") or box["kind"].endswith("price")
            cv2.polylines(image, [quad], True, (0, 140, 255) if money else (0, 190, 0),
                          2, cv2.LINE_AA)
        panels.append(caption(image, f"{framework}  {len(blocks)} boxes"))
    save(tile(panels), out / "boxes.jpg")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--dataset", type=Path, default=AGED, help="the aged set")
    parser.add_argument("--clean", type=Path, default=CLEAN, help="the un-aged set")
    parser.add_argument("--families", type=Path,
                        help="a set covering more than one layout family "
                             "(default: --dataset)")
    parser.add_argument("--index", type=int, default=0, help="which image of the set")
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    figure_families(args.families or args.dataset, args.out)
    figure_renderers(args.dataset, args.out, args.index)
    figure_ageing(args.dataset, args.clean, args.out, args.index)
    figure_boxes(args.dataset, args.out, args.index)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
