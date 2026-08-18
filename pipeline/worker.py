"""Render one shard, completely or not at all.

    python pipeline/worker.py --plan data/run01/plan.json --shard 3 --out data/run01

A worker owns a directory and answers one question about it: is there a `DONE`
file? If there is, the shard is finished and is left alone -- that is resume. If
there is not, whatever is in the directory is **deleted** and the shard is
rendered from the start.

That deletion is the part worth arguing about, and it is not an optimisation
choice. Appending to a half-written `metadata.jsonl` produces duplicate records
for the images that were already there, and duplicates in a training set are
invisible: the file parses, the count is plausible, and a model sees some pages
twice. Redoing a few images is cheap; finding that later is not.

Three details decide whether the resume story is true rather than approximate:

* **`DONE` is written last, and atomically.** A temporary file renamed into
  place, after the metadata is flushed and fsynced. If `DONE` could appear
  before the last line was on disk, resume would skip a shard that is short, and
  the run would quietly produce fewer images than it claims.
* **Metadata is streamed.** Lines are appended as each render finishes rather
  than collected and written at the end, so a shard's memory does not grow with
  its size and a kill leaves a prefix rather than nothing.
* **One log per worker.** Eight workers interleaved on one stdout is unreadable
  exactly when it matters.

Since W2 a shard also checks what it drew -- `pipeline/invariants.py`, called
once, here -- and leaves the numbers in `invariants.json` beside its metadata.
An image whose label describes text no box printed does not reach `DONE`.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from paths import VENVS, venv_python  # noqa: E402

from pipeline import drift, invariants, record  # noqa: E402
from pipeline.config import RULES_ENV  # noqa: E402
from pipeline.plan import image_name  # noqa: E402

DONE = "DONE"

# What each shard writes down about its own content, beside its metadata.
# Separate from `metadata.jsonl` because that file is hashed by the golden
# baseline: a measurement added to it would make every W1 verification fail for
# a reason that has nothing to do with what W1 verifies. `drift.json` sits
# beside it for the same reason.
INVARIANTS = invariants.INVARIANTS_NAME

# name -> (script, working directory). The interpreter is resolved at call time
# through `venv_python`, which knows that a virtualenv keeps it in `bin/` on
# POSIX and `Scripts\` on Windows -- hardcoding either is how this breaks on the
# other platform.
BACKENDS = {
    "synthdog": (REPO_ROOT / "generators" / "synthdog" / "render.py",
                 REPO_ROOT / "generators" / "synthdog"),
    "html": (REPO_ROOT / "generators" / "html" / "render.py", REPO_ROOT),
    "genalog": (REPO_ROOT / "generators" / "genalog" / "render.py", REPO_ROOT),
}

CLEAN_AUGMENTATION = invariants.CLEAN_AUGMENTATION


class ShardError(RuntimeError):
    """This shard did not produce what the plan said it would."""


def shard_dir(out: Path, index: int) -> Path:
    return out / f"shard-{index:04d}"


def is_done(directory: Path) -> bool:
    return (directory / DONE).exists()


def mark_done(directory: Path, payload: dict) -> None:
    """Write `DONE` atomically, and only after everything else is on disk."""
    temporary = directory / f".{DONE}.tmp"
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n",
                         encoding="utf-8")
    with open(temporary, "rb") as handle:
        os.fsync(handle.fileno())
    os.replace(temporary, directory / DONE)


def renderer_command(backend: str, staging: Path, run: dict,
                     clean: bool, force: list[str]) -> list[str]:
    interpreter = venv_python(VENVS[backend])
    if not interpreter.exists():
        raise ShardError(
            f"{backend}: no interpreter at {interpreter}.\n"
            f"Build it with `python tasks.py setup-{backend}`."
        )
    script, _cwd = BACKENDS[backend]
    command = [
        str(interpreter), str(script),
        "-o", str(staging),               # absolute: see `render_shard`
        "-c", str(run["count"]),
        "--seed", str(run["seed"]),
        "--layout", run["layout"],
    ]
    forced = list(force)
    if clean and not any(item.startswith("augmentation=") for item in forced):
        forced.append(f"augmentation={CLEAN_AUGMENTATION}")
    for item in forced:
        command += ["--force", item]
    # Only the glyph backend has geometry of its own to switch off.
    if clean and backend == "synthdog":
        command.append("--clean")
    return command


def render_shard(shard: dict, out: Path, plan: dict, *, rules_root: Path | None = None,
                 log=None) -> dict:
    """Render one shard into `out/shard-NNNN/`. Returns what it produced."""
    backend = shard["backend"]
    if backend not in BACKENDS:
        raise ShardError(f"unknown backend {backend!r}; have {sorted(BACKENDS)}")

    directory = shard_dir(out, shard["index"])
    if is_done(directory):
        return {"shard": shard["index"], "backend": backend, "images": 0,
                "skipped": True, "reason": "already done"}

    # No DONE means whatever is here is a fragment. Start over rather than
    # append: appending duplicates the records that survived, and a duplicate in
    # a training set does not announce itself.
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)

    _script, cwd = BACKENDS[backend]
    environment = dict(os.environ)
    if rules_root is not None:
        environment[RULES_ENV] = str(rules_root)

    # One call site for the content checks, here rather than in each renderer.
    # Three copies of an invariant is three chances for one of them to be
    # quietly relaxed, and the renderer that skips it is the one to worry about.
    tally = invariants.Tally(invariants.attribute_names())

    written = 0
    metadata_path = directory / "metadata.jsonl"
    with open(metadata_path, "w", encoding="utf-8") as metadata:
        for run in shard["runs"]:
            staging = Path(tempfile.mkdtemp(prefix="shard-", dir=str(directory)))
            try:
                command = renderer_command(backend, staging, run,
                                           bool(plan.get("clean")),
                                           list(plan.get("force") or []))
                if log:
                    log.write(f"$ {' '.join(command)}\n")
                    log.flush()
                result = subprocess.run(command, cwd=cwd, env=environment,
                                        capture_output=True, text=True)
                if result.returncode != 0:
                    tail = (result.stderr or result.stdout).strip().splitlines()[-15:]
                    raise ShardError(
                        f"shard {shard['index']} {backend}/{run['layout']} failed:\n"
                        + "\n".join(tail))

                produced = record.read(staging / "metadata.jsonl")
                if len(produced) != run["count"]:
                    raise ShardError(
                        f"shard {shard['index']} {backend}/{run['layout']}: asked for "
                        f"{run['count']} images, got {len(produced)}")

                for offset, item in enumerate(produced):
                    target = image_name(backend, run["first_index"] + offset)
                    shutil.move(str(staging / item["file_name"]), str(directory / target))
                    item["file_name"] = target
                    item["framework"] = backend
                    item["layout"] = run["layout"]
                    record.check(item, where=target)
                    try:
                        tally.inspect(item, image=directory / target, where=target)
                    except invariants.InvariantError as error:
                        raise ShardError(
                            f"shard {shard['index']} {backend}/{run['layout']}: "
                            f"{error}") from error
                    json.dump(item, metadata, ensure_ascii=False)
                    metadata.write("\n")
                    written += 1
            finally:
                shutil.rmtree(staging, ignore_errors=True)
        # Flushed and fsynced before DONE can exist: a DONE in front of an
        # unwritten last line is a shard that resume would skip while short.
        metadata.flush()
        os.fsync(metadata.fileno())

    expected = sum(run["count"] for run in shard["runs"])
    if written != expected:
        raise ShardError(f"shard {shard['index']}: wrote {written} of {expected}")

    # Written before the verdict, so a shard that trips a budget still leaves
    # the numbers behind to argue with.
    (directory / INVARIANTS).write_text(
        json.dumps(tally.report(), indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    budget = tally.problems()
    if budget:
        raise ShardError(f"shard {shard['index']}: " + "; ".join(budget))

    # The quality vector, written here because this is where the shard's images
    # and metadata are. Comparing it against the plan's expectation needs the
    # whole plan and happens in `pipeline/run.py`; what cannot wait is the
    # content-source axis, which is not drift but a fault, and stops the shard.
    vector = drift.shard_vector(directory, shard)
    drift.write_vector(vector, directory)
    _warnings, stops, _notes = drift.compare(vector, {})
    if stops:
        raise ShardError(f"shard {shard['index']}: " + "; ".join(stops))

    mark_done(directory, {
        "shard": shard["index"],
        "backend": backend,
        "images": written,
        "seeds": [[run["seed"], run["seed"] + run["count"] - 1] for run in shard["runs"]],
    })
    return {"shard": shard["index"], "backend": backend, "images": written,
            "skipped": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--shard", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--rules-root", type=Path)
    args = parser.parse_args()

    # Absolute before anything else touches it. The glyph backend runs from its
    # own directory, so a relative path would land inside generators/synthdog/
    # -- silently, because the backend creates whatever it is given.
    out = args.out.resolve()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    shard = next((s for s in plan["shards"] if s["index"] == args.shard), None)
    if shard is None:
        raise SystemExit(f"no shard {args.shard} in {args.plan}")

    directory = shard_dir(out, args.shard)
    directory.parent.mkdir(parents=True, exist_ok=True)
    logs = out / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    with open(logs / f"shard-{args.shard:04d}.log", "w", encoding="utf-8") as log:
        try:
            result = render_shard(shard, out, plan,
                                  rules_root=args.rules_root, log=log)
        except ShardError as error:
            log.write(f"FAILED: {error}\n")
            print(f"shard {args.shard}: {error}", file=sys.stderr)
            return 1
        log.write(json.dumps(result) + "\n")
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
