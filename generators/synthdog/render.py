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

import synthtiger  # noqa: E402
from template_receipt import SynthVNReceipt  # noqa: E402

import profiling  # noqa: E402
import rulebase  # noqa: E402
import worklist  # noqa: E402


def make_clean(config: dict) -> dict:
    """Turn off everything this renderer does *after* the structure render.

    `--force augmentation=pristine` empties the degradation chain, but this
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
        help="pin any attribute, repeatable: --force augmentation=pristine",
    )
    parser.add_argument("--config", type=Path, default=Path("config_vi_receipt.yaml"))
    parser.add_argument(
        "--clean", action="store_true",
        help="no curl, no perspective, no camera effects -- the structure render only",
    )
    parser.add_argument(
        "--profile", metavar="JSON",
        help="time every stage and write the breakdown here. Off by default, "
             "and off costs nothing: see profiling.py",
    )
    worklist.add_argument(parser)
    args = parser.parse_args()

    profile = Path(args.profile) if args.profile else profiling.enable_from_env()
    if args.profile:
        profiling.enable()

    with profiling.stage("startup"):
        config = yaml.safe_load(args.config.read_text(encoding="utf-8"))
        if args.clean:
            config = make_clean(config)
        template = SynthVNReceipt(config)
    args.out.mkdir(parents=True, exist_ok=True)
    jobs = worklist.load(args)
    # One parse per job rather than one per page: `parse_force` reads the rules
    # to validate the pin, and a job list is many pages over few distinct pins.
    forces = {job: rulebase.parse_force(job.pins(args.force), job.layout)
              for job in jobs}

    # Streamed, not collected: a job list may be a whole shard, and a record
    # carries every box on the page. Written in page order, which is the order
    # the caller listed the jobs in -- `pipeline/worker.py` walks the runs in
    # that order to name the files.
    with open(args.out / "metadata.jsonl", "w", encoding="utf-8") as metadata:
        for index, job, seed in worklist.pages(jobs):
            # ALL THREE global generators, not just numpy's.
            #
            # This line used to be `np.random.seed(seed)`, and that was a bug
            # with no symptom: the image effects in `config_vi_receipt.yaml`
            # -- elastic distortion, gaussian noise, motion blur, gaussian
            # blur -- are imgaug augmenters, and imgaug keeps a global RNG of
            # its own that numpy's seed does not touch. So a page depended on
            # how many pages the process had already drawn. The same seed drew
            # one image as the first page of a process and a visibly different
            # one as the second: same label, same boxes' worth of text,
            # different pixels and different quads.
            #
            # Nothing caught it because the worker started a fresh process per
            # layout, so the positions were always the same and the golden
            # baseline was stable -- deterministic, but not a function of the
            # seed. Drawing a whole shard in one process is what made it
            # visible, and `tests/test_worklist.py` now renders the same seeds
            # split and joined and compares the bytes.
            #
            # `synthtiger.set_global_random_seed` is synthtiger's own call,
            # used rather than reimplemented: it seeds `random`, `np.random`
            # and `imgaug` together, which is also what the synthtiger CLI
            # (`make receipts`) does, so the two paths finally agree.
            synthtiger.set_global_random_seed(seed)
            template.seed_base = seed
            template._counter = 0

            data = template.generate(force=forces[job])
            name = f"synthdog_{index:03d}.jpg"
            with profiling.stage("export"):
                Image.fromarray(data["image"].astype(np.uint8)).save(
                    args.out / name, quality=data["quality"]
                )
            with profiling.stage("annotation"):
                record = {
                    "file_name": name,
                    "ground_truth": json.dumps({"gt_parse": data["gt_parse"]},
                                               ensure_ascii=False),
                    "text_sequence": data["text_sequence"],
                    "recipe": data["recipe"],
                    "boxes": data["boxes"],
                }
                # Additive, and only when the layout has a table to describe --
                # the same key the other two backends write, from the same grid.
                if data.get("table"):
                    record["table"] = data["table"]
            with profiling.stage("export"):
                json.dump(record, metadata, ensure_ascii=False)
                metadata.write("\n")
            print(f"[ok] {name}  {data['image'].shape[1]}x{data['image'].shape[0]}  "
                  f"{data['recipe']['attributes']['layout']['id']}")

    if profile:
        profiling.dump(profile, {"backend": "synthdog", "images": worklist.total(jobs),
                                 "jobs": len(jobs)})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
