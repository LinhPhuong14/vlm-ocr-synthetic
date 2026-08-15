"""Render rule-base receipts with the glyph backend.

    generators/synthdog/.venv/bin/python generators/synthdog/render.py -o outputs -c 10

The same `SynthVNReceipt` template the synthtiger CLI runs -- `make receipts`
is still the way to produce a large training set -- driven directly so that a
seed can be chosen per image and a bố cục pinned. That is what the dataset
driver needs and what the synthtiger CLI, which owns its own loop and its own
train/validation/test split, does not offer.

Writes the same `metadata.jsonl` shape as `generators/html/render.py` and
`generators/genalog/render.py`, so the three are directly comparable.

Run it from `generators/synthdog/`: the paths in `config_vi_receipt.yaml` are
relative to that directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import yaml
from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO_ROOT))

from template_receipt import SynthVNReceipt  # noqa: E402

import rulebase  # noqa: E402


def make_clean(config: dict) -> dict:
    """Turn off everything this renderer does *after* the structure render.

    `--force augmentation=khong_lam_gi` empties the degradation chain, but this
    backend has a second source of distortion the other two do not: it curls
    the paper, warps it, drops it on a background and photographs it. A clean
    set has to switch that off too, or "not augmented" would only be true of
    two renderers out of three.

    What is left is the sheet as the grid describes it: no curl, no
    perspective, no lamp, and JPEG quality high enough not to matter.
    """
    config = {**config}
    config["quality"] = [93, 97]
    # Let the sheet fill the frame exactly, so no background shows at all.
    # `canvas_w = max(dw / fill, canvas_h / aspect)`, so an aspect above the
    # receipt's own height-to-width ratio (~2) makes the second term lose and
    # the canvas comes out the size of the document.
    config["canvas_fill"] = [1.0, 1.0]
    config["canvas_aspect"] = [4.0, 4.0]
    config["curl"] = {**config.get("curl", {}), "prob": 0.0}
    for stage in ("doc_effect", "effect"):
        block = config.get(stage) or {}
        config[stage] = {
            **block,
            "args": [{**entry, "prob": 0} for entry in block.get("args", [])],
        }
    return config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=Path("outputs"))
    parser.add_argument("-c", "--count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--layout", help="pin one bố cục")
    parser.add_argument(
        "--force", action="append", default=[], metavar="ATTR=ID",
        help="pin any attribute, repeatable: --force augmentation=khong_lam_gi",
    )
    parser.add_argument("--config", type=Path, default=Path("config_vi_receipt.yaml"))
    parser.add_argument(
        "--clean", action="store_true",
        help="no curl, no perspective, no camera effects -- the structure render only",
    )
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    if args.clean:
        config = make_clean(config)
    template = SynthVNReceipt(config)
    args.out.mkdir(parents=True, exist_ok=True)
    force = rulebase.parse_force(args.force, args.layout)

    records = []
    for index in range(args.count):
        # synthtiger seeds its own components from numpy's global state; seeding
        # it per image keeps the paper curl and the camera effects reproducible
        # as well as the contents.
        np.random.seed(args.seed + index)
        template.seed_base = args.seed + index
        template._counter = 0

        data = template.generate(force=force)
        name = f"synthdog_{index:03d}.jpg"
        Image.fromarray(data["image"].astype(np.uint8)).save(
            args.out / name, quality=data["quality"]
        )
        records.append({
            "file_name": name,
            "ground_truth": json.dumps({"gt_parse": data["gt_parse"]}, ensure_ascii=False),
            "text_sequence": data["text_sequence"],
            "recipe": data["recipe"],
            "boxes": data["boxes"],
        })
        print(f"[ok] {name}  {data['image'].shape[1]}x{data['image'].shape[0]}  "
              f"{data['recipe']['attributes']['layout']['id']}")

    with open(args.out / "metadata.jsonl", "w", encoding="utf-8") as fp:
        for record in records:
            json.dump(record, fp, ensure_ascii=False)
            fp.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
