"""One before/after pair per degradation, on the same page.

    python tools/degradation_showcase.py -o samples/degradation

Every model in `degradation/` applied on its own to one rendered receipt, so
each effect can be judged for what it does rather than for what a chain does.
The three texture models are the point of the exercise -- a paper composite, a
Poisson-blended stain and pasted ink residue look nothing alike, and a chain
hides that.

`by_box` gets a tile too, although it is a wrapper rather than a model. Its
tile is the one that shows the difference this catalogue otherwise cannot: the
same highlighter, on a few consecutive lines instead of on the whole sheet.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from degradation import apply_one, names  # noqa: E402
from degradation.regions import boxes_from_ink  # noqa: E402

# Settings chosen to make each model visible on a receipt-sized page rather
# than to be realistic -- this is a catalogue, not a dataset.
SHOWCASE = {
    "paper_texture": {"paper": "recycled", "alpha": 0.55, "grain": 0.8, "creases": 3},
    "gradient_domain": {"count": 6, "strength": 0.9},
    "phantom_character": {"frequency": "very_frequent"},
    "ink_degradation": {"level": 5},
    "bleed_through": {"intensity": 0.65, "nb_iter": 8},
    "blur_zones": {"radius": 2.2, "zones": 3, "coverage": 0.25},
    "blur": {"radius": 1.6},
    "shadow_binding": {"border": "left", "distance_ratio": 0.14, "intensity": 0.5},
    "holes": {"count": 2, "placement": "border", "size_ratio": 0.18, "fill": "black"},
    # the Augraphy ports
    "bad_photocopy": {"blotch": 0.55, "wash": 0.3, "contrast": 0.35},
    "dirty_drum": {"lines": 7, "intensity": 0.7, "line_width": 4},
    "dirty_rollers": {"intensity": 0.5, "period": 70},
    "letterpress": {"clusters": 400, "strength": 0.85},
    "hollow": {"strength": 0.95},
    "dot_matrix": {"cell": 3.0, "coverage": 0.8, "strength": 0.95, "dead_pins": 3},
    "markup": {"style": "highlight", "count": 4},
    "scribbles": {"count": 4},
    "voronoi_tessellation": {"scale": 30, "alpha": 0.3, "edges": 0.1},
    "delaunay_tessellation": {"scale": 42, "alpha": 0.28, "edges": 0.1},
    "color_shift": {"shift": 3.0, "blur": 0.6},
    "glitch_effect": {"bands": 10, "max_shift": 0.012},
    # `by_box` is the only entry that is not a model, so its catalogue tile
    # shows what it is FOR: one effect, on a run of consecutive lines only.
    "by_box": {"effect": "markup", "params": {"style": "highlight"},
               "select": {"policy": "run", "fraction": 0.12}},
}


def label(image: np.ndarray, text: str) -> np.ndarray:
    strip = np.full((34, image.shape[1], 3), 245, dtype=np.uint8)
    cv2.putText(strip, text, (8, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 1,
                cv2.LINE_AA)
    return np.vstack([strip, image])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=REPO_ROOT / "samples" / "degradation")
    parser.add_argument("--source", type=Path, help="a rendered page; default picks one from data/")
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    source = args.source
    if source is None:
        candidates = sorted((REPO_ROOT / "data").rglob("html_0*.jpg"))
        if not candidates:
            raise SystemExit(
                "no page to degrade: pass --source, or build the dataset first with "
                "`make dataset`"
            )
        source = candidates[0]

    page = cv2.imread(str(source), cv2.IMREAD_COLOR)
    if page is None:
        raise SystemExit(f"cannot read {source}")

    args.out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(args.out / "showcase-before.jpg"), page, [cv2.IMWRITE_JPEG_QUALITY, 90])

    # `by_box` needs to know where the text is, and a finished JPEG carries no
    # labels. Detected, not read -- and named `boxes_from_ink` so a reader of
    # this file knows the difference. A dataset run passes the real ones.
    detected = boxes_from_ink(page)

    manifest = []
    tiles = [label(page, "before")]
    for index, name in enumerate(names()):
        options = dict(SHOWCASE.get(name, {}))
        aged = apply_one(page, name, options, random.Random(args.seed + index),
                         regions=detected)
        cv2.imwrite(str(args.out / f"showcase-{name}.jpg"), aged,
                    [cv2.IMWRITE_JPEG_QUALITY, 90])
        tiles.append(label(aged, name))
        manifest.append({"degradation": name, "options": options,
                         "file": f"showcase-{name}.jpg"})
        print(f"[ok] {name}")

    width = 300
    scaled = []
    for tile in tiles:
        factor = width / tile.shape[1]
        scaled.append(cv2.resize(tile, (width, int(tile.shape[0] * factor))))
    height = max(tile.shape[0] for tile in scaled)
    scaled = [
        cv2.copyMakeBorder(tile, 0, height - tile.shape[0], 0, 6, cv2.BORDER_CONSTANT,
                           value=(255, 255, 255))
        for tile in scaled
    ]
    half = (len(scaled) + 1) // 2
    rows = [np.hstack(scaled[:half]), np.hstack(scaled[half:])]
    span = max(row.shape[1] for row in rows)
    rows = [
        cv2.copyMakeBorder(row, 0, 0, 0, span - row.shape[1], cv2.BORDER_CONSTANT,
                           value=(255, 255, 255))
        for row in rows
    ]
    cv2.imwrite(str(args.out / "showcase-contact.jpg"), np.vstack(rows),
                [cv2.IMWRITE_JPEG_QUALITY, 86])

    (args.out / "showcase.json").write_text(
        json.dumps({"source": str(source.relative_to(REPO_ROOT)), "seed": args.seed,
                    "images": manifest}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n{len(manifest)} degradations -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
