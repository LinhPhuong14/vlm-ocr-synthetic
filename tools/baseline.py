"""Fingerprint what the generator produces, and check it still produces it.

    python tools/baseline.py --write     # capture  (make baseline-write)
    python tools/baseline.py             # verify   (make baseline-verify)

W1 replaces the sequential driver with a sharded, parallel one. "The parallel
path gives the same result as the sequential one" is only checkable against a
record of what the sequential one gave, taken *before* it was touched -- so this
is captured first and everything after has to reproduce it.

The fingerprint is sha256 of every image plus sha256 of every metadata line,
normalised. Not a count, not a spot check: a driver that quietly drops one image
or renumbers two of them passes a count.

**What normalisation does, exactly.** Each metadata line is parsed and re-dumped
with `sort_keys=True` and `ensure_ascii=False`, so key order and float spelling
cannot make an identical record hash differently. Nothing else is touched -- no
field is excluded. If a path or a timestamp ever enters `metadata.jsonl` this
verification starts failing on every machine, which is the correct outcome: both
belong in `timings.json`, not in a label.

Three fixed plans, because one is not enough:

* `n3` is the plan the W1 brief names, `--seed 2026 -n 3`.
* `n5` exists because `-n 3` gives the first three layouts one image each and
  the rest none. It was the smallest count reaching every layout when there
  were five of them.
* `n14` is that same intent at the current count: one image per layout, so the
  nine invoice layouts added after `n5` are covered too. `-n 5` now reaches
  five of fourteen, which is the sort of gap a baseline exists to close.

This needs all three renderer virtualenvs, so it is a hand-run command and not
part of the `tests` CI job. Keeping that job down to pytest and pyyaml is what
holds `rulebase/` to its one dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GOLDEN = REPO_ROOT / "tests" / "golden" / "baseline.json"

# (name, extra arguments). Fixed forever: a baseline whose plan drifts is not a
# baseline. Adding a plan is fine, editing one means recapturing.
PLANS: dict[str, list[str]] = {
    "n3": ["-n", "3", "--seed", "2026"],
    "n5": ["-n", "5", "--seed", "2026"],
    "n14": ["-n", "14", "--seed", "2026"],
}


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalise(line: str) -> str:
    """One metadata line, in a form that hashes the same everywhere."""
    return json.dumps(json.loads(line), sort_keys=True, ensure_ascii=False)


def fingerprint(root: Path) -> dict:
    """Hash every image and every metadata line under a generated dataset."""
    images: dict[str, str] = {}
    metadata: dict[str, list[str]] = {}
    by_backend: dict[str, int] = {}
    by_layout: dict[str, int] = {}

    for backend_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        backend = backend_dir.name
        for image in sorted(backend_dir.glob("*.jpg")):
            images[f"{backend}/{image.name}"] = _sha(image.read_bytes())

        index = backend_dir / "metadata.jsonl"
        if not index.exists():
            continue
        lines = [line for line in index.read_text(encoding="utf-8").splitlines() if line.strip()]
        metadata[backend] = [_sha(_normalise(line).encode("utf-8")) for line in lines]
        by_backend[backend] = len(lines)
        for line in lines:
            layout = json.loads(line).get("layout", "?")
            by_layout[layout] = by_layout.get(layout, 0) + 1

    summary = root / "dataset.json"
    return {
        "images": images,
        "metadata": metadata,
        "counts": {"by_backend": by_backend, "by_layout": by_layout},
        "dataset_json": _sha(
            json.dumps(json.loads(summary.read_text(encoding="utf-8")),
                       sort_keys=True, ensure_ascii=False).encode("utf-8")
        ) if summary.exists() else None,
    }


def generate(plan: list[str], out: Path, driver: list[str]) -> None:
    command = [sys.executable, *driver, "-o", str(out), *plan]
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()[-15:]
        raise SystemExit("generation failed:\n" + "\n".join(tail))


def capture(driver: list[str]) -> dict:
    """Run every plan into a throwaway directory and fingerprint the result."""
    captured: dict[str, dict] = {}
    for name, plan in PLANS.items():
        workspace = Path(tempfile.mkdtemp(prefix=f"baseline-{name}-"))
        try:
            out = workspace / "dataset"
            print(f"  [{name}] {' '.join(plan)}")
            generate(plan, out, driver)
            captured[name] = fingerprint(out)
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
    return {
        "plans": captured,
        "normalisation": (
            "each metadata line is json.loads then json.dumps(sort_keys=True, "
            "ensure_ascii=False); no field is excluded"
        ),
    }


def compare(expected: dict, actual: dict) -> list[str]:
    """Every difference, named precisely enough to act on."""
    problems: list[str] = []
    for name in sorted(set(expected["plans"]) | set(actual["plans"])):
        want = expected["plans"].get(name)
        have = actual["plans"].get(name)
        if want is None:
            problems.append(f"{name}: not in the baseline (recapture, or a plan was added)")
            continue
        if have is None:
            problems.append(f"{name}: plan missing from this run")
            continue

        for key in sorted(set(want["images"]) | set(have["images"])):
            if key not in have:
                pass
            if key not in want["images"]:
                problems.append(f"{name}: {key} is new")
            elif key not in have["images"]:
                problems.append(f"{name}: {key} was not produced")
            elif want["images"][key] != have["images"][key]:
                problems.append(f"{name}: {key} differs")

        for backend in sorted(set(want["metadata"]) | set(have["metadata"])):
            a = want["metadata"].get(backend, [])
            b = have["metadata"].get(backend, [])
            if len(a) != len(b):
                problems.append(
                    f"{name}/{backend}: {len(b)} metadata lines, baseline has {len(a)}")
                continue
            differing = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
            if differing:
                problems.append(
                    f"{name}/{backend}: metadata lines {differing[:8]} differ")

        if want["counts"] != have["counts"]:
            problems.append(f"{name}: counts differ\n      baseline {want['counts']}"
                            f"\n      now      {have['counts']}")
        if want.get("dataset_json") != have.get("dataset_json"):
            problems.append(f"{name}: dataset.json differs")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true",
                        help="capture and overwrite the golden file")
    parser.add_argument("--driver", default="tools/generate_dataset.py",
                        help="the generator to fingerprint")
    args = parser.parse_args()

    driver = args.driver.split()
    print(f"baseline via {' '.join(driver)}")
    actual = capture(driver)

    if args.write:
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        total = sum(len(plan["images"]) for plan in actual["plans"].values())
        print(f"\nwrote {GOLDEN.relative_to(REPO_ROOT)}: "
              f"{len(actual['plans'])} plans, {total} images")
        return 0

    if not GOLDEN.exists():
        raise SystemExit(f"no baseline at {GOLDEN}; capture one with --write")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    problems = compare(expected, actual)
    if problems:
        print(f"\nBASELINE: {len(problems)} khác biệt\n")
        for problem in problems[:40]:
            print(f"  - {problem}")
        if len(problems) > 40:
            print(f"  ... and {len(problems) - 40} more")
        return 1
    total = sum(len(plan["images"]) for plan in actual["plans"].values())
    print(f"\nbaseline khớp: {total} ảnh, {len(actual['plans'])} kế hoạch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
