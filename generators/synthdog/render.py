"""Render rule-base receipts with the glyph backend, one seed at a time.

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

sys.path.insert(0, str(Path(__file__).resolve().parent))

from template_receipt import SynthVNReceipt  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=Path("outputs"))
    parser.add_argument("-c", "--count", type=int, default=10)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--layout", help="pin one bố cục")
    parser.add_argument("--config", type=Path, default=Path("config_vi_receipt.yaml"))
    args = parser.parse_args()

    config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
    template = SynthVNReceipt(config)
    args.out.mkdir(parents=True, exist_ok=True)
    force = {"layout": args.layout} if args.layout else None

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
