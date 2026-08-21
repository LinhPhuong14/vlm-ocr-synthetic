"""Build a labelled dataset with all three renderers.

    python tools/generate_dataset.py -o data/dataset60 -n 20

A thin shell over `pipeline/run.py` since W1. The flags are unchanged and mean
what they always meant, so `make dataset`, `make dataset-clean` and every
committed invocation keep working; what changed underneath is that the work is
now planned into shards, rendered by a pool of processes, and resumable.

The old loop is gone rather than kept beside the new one. Two drivers that are
supposed to produce identical datasets is precisely the arrangement where one of
them drifts and nobody notices for a month -- and the golden baseline in
`tests/golden/baseline.json` exists to prove this shell still produces what that
loop produced.

For a long job, prefer `pipeline.yaml` and `make run`: it takes shard size,
worker count and per-run rule overrides, none of which fit sensibly on a command
line.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# The augmentation value whose chain is empty. Named here rather than inlined
# so renaming it in rules/augmentation.yaml fails loudly instead of silently
# producing an aged "clean" set.
CLEAN_AUGMENTATION = "pristine"

BACKENDS = ("synthdog", "html", "genalog")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=REPO_ROOT / "data" / "dataset60")
    parser.add_argument("-n", "--per-framework", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--frameworks", nargs="+", default=list(BACKENDS),
        choices=list(BACKENDS), help="subset to build",
    )
    parser.add_argument(
        "--clean", action="store_true",
        help="no ageing at all: empties the degradation chain, and switches off "
             "the glyph backend's curl, perspective and camera effects too",
    )
    parser.add_argument(
        "--force", action="append", default=[], metavar="ATTR=ID",
        help="pin any attribute for the whole run, repeatable",
    )
    parser.add_argument(
        "--layouts", nargs="+", metavar="NAME",
        help="draw from these layouts, by name, instead of every layout in "
             "rulebase/layouts/. A fixed comparison should name them: the "
             "quota walks the list in order, so an unnamed set changes the "
             "day someone adds a layout",
    )
    parser.add_argument(
        "--template", nargs="?", const="auto", default=None, metavar="LAYOUT",
        help="draw the CSS sheets in generators/html/sheets/ instead of the "
             "character grid. Bare, each page follows the layout its recipe "
             "drew; a layout id forces one dress. Only the two HTML backends "
             "can print a sheet, so name them with --frameworks",
    )
    parser.add_argument("--workers", type=int, default=1,
                        help="processes to render with; 1 keeps the old behaviour")
    parser.add_argument(
        "--pairing", choices=["paired", "independent"], default="paired",
        help="paired: every renderer draws the same receipts, so a difference "
             "between two of them is a difference in drawing. independent: "
             "separate seed blocks, three times the distinct pages, no basis "
             "for comparing renderers",
    )
    args = parser.parse_args()

    from pipeline.config import Config
    from pipeline.run import execute

    config = Config.from_dict({
        "run": {
            # Absolute: the glyph backend runs from `generators/synthdog/`
            # because the paths in its config are relative to that directory, so
            # a relative output path would land inside the generator instead --
            # silently, since it creates the directory it writes to.
            "out": str(args.out.resolve()),
            "per_backend": args.per_framework,
            "seed": args.seed,
            "workers": args.workers,
            "clean": bool(args.clean),
            "layouts": list(args.layouts or []),
            "force": list(args.force),
            "pairing": args.pairing,
            "template": args.template or "",
        },
        "backends": list(args.frameworks),
        # One shard per backend. This is the small-job path -- `make dataset
        # N=20` is twenty images -- and splitting further would only add process
        # startup. `pipeline.yaml` is where a long job sets a real shard size.
        "shard": {"size": max(args.per_framework, 1)},
    })
    return execute(config)


if __name__ == "__main__":
    raise SystemExit(main())
