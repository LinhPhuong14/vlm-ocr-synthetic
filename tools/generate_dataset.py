"""Build a labelled dataset with all three renderers.

    python tools/generate_dataset.py -o data/dataset60 -n 20

Each renderer needs its own interpreter -- synthtiger pins Pillow 9.5,
WeasyPrint wants a modern one -- so this drives them as subprocesses through
the venv each one owns, rather than importing all three into one process that
cannot exist.

The `-n` images per renderer are spread evenly over the bố cục available, so a
comparison between renderers is not confounded by one of them having drawn
more supermarket receipts than another. Within a bố cục everything else is
still sampled from the rules.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from rulebase import available_layouts  # noqa: E402

# name -> (interpreter, script, working directory)
BACKENDS = {
    "synthdog": (
        REPO_ROOT / "generators/synthdog/.venv/bin/python",
        REPO_ROOT / "generators/synthdog/render.py",
        REPO_ROOT / "generators/synthdog",
    ),
    "html": (
        REPO_ROOT / "generators/html/.venv/bin/python",
        REPO_ROOT / "generators/html/render.py",
        REPO_ROOT,
    ),
    "genalog": (
        REPO_ROOT / "generators/genalog/.venv/bin/python",
        REPO_ROOT / "generators/genalog/render.py",
        REPO_ROOT,
    ),
}


def plan(count: int, layouts: list[str]) -> list[tuple[str, int]]:
    """(layout, how many) so the count divides as evenly as the layouts allow."""
    base, extra = divmod(count, len(layouts))
    return [(layout, base + (1 if index < extra else 0))
            for index, layout in enumerate(layouts)]


def run_backend(name: str, out: Path, count: int, seed: int, layouts: list[str]) -> list[dict]:
    interpreter, script, cwd = BACKENDS[name]
    if not interpreter.exists():
        raise SystemExit(
            f"{name}: no interpreter at {interpreter}. Build it with `make setup-{name}`."
        )

    out.mkdir(parents=True, exist_ok=True)
    records: list[dict] = []
    offset = 0
    for layout, quota in plan(count, layouts):
        if quota == 0:
            continue
        staging = out / f".{layout}"
        if staging.exists():
            shutil.rmtree(staging)
        command = [
            str(interpreter), str(script),
            "-o", str(staging),
            "-c", str(quota),
            "--seed", str(seed + offset * 1000),
            "--layout", layout,
        ]
        print(f"  [{name}/{layout}] {quota} ảnh")
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
        if result.returncode != 0:
            tail = (result.stderr or result.stdout).strip().splitlines()[-12:]
            raise SystemExit(f"{name}/{layout} failed:\n" + "\n".join(tail))

        metadata = staging / "metadata.jsonl"
        for line in metadata.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            # Rename into a flat, collision-free namespace across layouts.
            source = staging / record["file_name"]
            target_name = f"{name}_{len(records):03d}.jpg"
            shutil.move(str(source), str(out / target_name))
            record["file_name"] = target_name
            record["framework"] = name
            record["layout"] = layout
            records.append(record)
        shutil.rmtree(staging)
        offset += 1

    with open(out / "metadata.jsonl", "w", encoding="utf-8") as fp:
        for record in records:
            json.dump(record, fp, ensure_ascii=False)
            fp.write("\n")
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=REPO_ROOT / "data" / "dataset60")
    parser.add_argument("-n", "--per-framework", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument(
        "--frameworks", nargs="+", default=list(BACKENDS),
        choices=list(BACKENDS), help="subset to build",
    )
    args = parser.parse_args()

    # Absolute: the glyph backend is run from `generators/synthdog/`, because
    # the paths in its config are relative to that directory, so a relative
    # output path would land inside the generator instead of where it was asked
    # for -- and silently, since it creates the directory it writes to.
    args.out = args.out.resolve()

    layouts = available_layouts()
    args.out.mkdir(parents=True, exist_ok=True)
    summary = {"per_framework": args.per_framework, "layouts": layouts, "frameworks": {}}

    for index, name in enumerate(args.frameworks):
        print(f"[{name}]")
        records = run_backend(
            name, args.out / name, args.per_framework, args.seed + index * 100000, layouts
        )
        counts: dict[str, int] = {}
        for record in records:
            counts[record["layout"]] = counts.get(record["layout"], 0) + 1
        summary["frameworks"][name] = {"images": len(records), "by_layout": counts}
        print(f"  -> {len(records)} ảnh vào {args.out / name}\n")

    (args.out / "dataset.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    total = sum(entry["images"] for entry in summary["frameworks"].values())
    print(f"{total} ảnh -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
