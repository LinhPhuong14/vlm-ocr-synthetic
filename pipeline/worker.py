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
* **Metadata is streamed.** Lines are appended as each record arrives rather
  than collected and written at the end, so a shard's memory does not grow with
  its size. The renderer streams its own file the same way, which matters now
  that one invocation draws a whole shard rather than one layout.
* **One log per worker.** Eight workers interleaved on one stdout is unreadable
  exactly when it matters.

Since W2 a shard also checks what it drew -- `pipeline/invariants.py`, called
once, here -- and leaves the numbers in `invariants.json` beside its metadata.
An image whose label describes text no box printed does not reach `DONE`.

Since W3b a shard is **one renderer process**, not one per layout. It used to
be one per layout because that is the shape a command line has, and with five
layouts nobody noticed; at fourteen it meant fourteen processes drawing one and
a half images each, and start-up was 23% to 44% of a run -- the largest single
cost in the generator, measured in `data/profile/README.md` and in none of the
renderers. The runs go over as a job list (`worklist.py`) and come back in the
same order, which is checked here against the layout each record says it drew
rather than assumed.
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

import worklist  # noqa: E402
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


def renderer_command(backend: str, staging: Path, jobs: Path,
                     clean: bool, force: list[str], template: str = "") -> list[str]:
    """One invocation for the whole shard, not one per layout.

    A shard used to be rendered by one process per run, and a run is one
    layout: twenty images over fourteen layouts meant fourteen processes of
    about one and a half images each, each paying interpreter and backend
    start-up in full. Measured in `data/profile/README.md`, that was 23% of a
    synthdog run, 29% of an html one and 44% of a genalog one -- the largest
    single cost in the generator, and in none of the renderers.

    `--jobs` takes the whole list instead, so the cost is paid once. Nothing
    about a page changes: see `worklist.py`, and the byte comparison in
    `tests/test_worklist.py`.
    """
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
        "--jobs", str(jobs),
    ]
    forced = list(force)
    if clean and not any(item.startswith("augmentation=") for item in forced):
        forced.append(f"augmentation={CLEAN_AUGMENTATION}")
    for item in forced:
        command += ["--force", item]
    # Only the glyph backend has geometry of its own to switch off.
    if clean and backend == "synthdog":
        command.append("--clean")
    # ...and only the two HTML backends have a second page model. `Config`
    # refuses a run that asks for one and includes the glyph backend, so
    # reaching here with both is a bug rather than a fall-through.
    if template and backend != "synthdog":
        command += ["--template", template]
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
    staging = Path(tempfile.mkdtemp(prefix="shard-", dir=str(directory)))
    with open(metadata_path, "w", encoding="utf-8") as metadata:
        try:
            # One renderer process for the whole shard. The runs are handed
            # over as a job list in the order the plan put them, and the
            # renderer draws them in that order, so the records come back in
            # it too -- checked below rather than trusted.
            jobs = [worklist.Job(layout=run["layout"], seed=run["seed"],
                                 count=run["count"]) for run in shard["runs"]]
            jobs_path = worklist.write(staging / "jobs.json", jobs)
            command = renderer_command(backend, staging, jobs_path,
                                       bool(plan.get("clean")),
                                       list(plan.get("force") or []),
                                       str(plan.get("template") or ""))
            if log:
                log.write(f"$ {' '.join(command)}\n")
                log.write(f"  {len(jobs)} job(s), {worklist.total(jobs)} image(s), "
                          f"{worklist.total(jobs) / len(jobs):.2f} per process\n")
                log.flush()
            result = subprocess.run(command, cwd=cwd, env=environment,
                                    capture_output=True, text=True)
            if result.returncode != 0:
                # The exit code, always. A renderer that dies *after* writing
                # its image prints `[ok] ...` as its last line, so a message
                # made only of the tail reads as a success followed by the
                # word "failed" and says nothing about what went wrong.
                # Negative means a signal: -11 is a segfault in a native
                # library, which is a very different thing to debug from a
                # traceback.
                how = (f"killed by signal {-result.returncode}"
                       if result.returncode < 0 else f"exit {result.returncode}")
                tail = "\n".join(
                    (result.stderr.strip() + "\n" + result.stdout.strip())
                    .strip().splitlines()[-15:])
                raise ShardError(
                    f"shard {shard['index']} {backend} failed ({how}):\n" + tail)

            produced = record.read(staging / "metadata.jsonl")
            expected_total = sum(run["count"] for run in shard["runs"])
            if len(produced) != expected_total:
                raise ShardError(
                    f"shard {shard['index']} {backend}: asked for "
                    f"{expected_total} images, got {len(produced)}")

            cursor = 0
            for run in shard["runs"]:
                for offset in range(run["count"]):
                    item = produced[cursor]
                    cursor += 1
                    target = image_name(backend, run["first_index"] + offset)
                    # The renderer's own record says which layout it drew.
                    # Checked against the job it was meant to be, because
                    # walking one list against another by position is exactly
                    # the arrangement where an off-by-one mislabels every image
                    # after it and nothing downstream notices.
                    drawn = record.drawn_layout(item)
                    if drawn and drawn != run["layout"]:
                        raise ShardError(
                            f"shard {shard['index']} {backend}: record {cursor - 1} "
                            f"is {drawn!r} where the plan asked for "
                            f"{run['layout']!r}; the renderer returned its pages "
                            f"in a different order from the job list")
                    shutil.move(str(staging / record.file_name(item)),
                                str(directory / target))
                    # `rename` moves the three fields that follow the file name
                    # -- `filename`, `source_files` and the `job_id` derived
                    # from both -- and `attach` writes down what the plan knows
                    # and the renderer did not.
                    record.attach(item, framework=backend, layout=run["layout"])
                    record.rename(item, target)
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
        # How many renderer processes this shard cost, and how much work each
        # got. One, since W3b -- recorded rather than left to be inferred from
        # the code, because that ratio is the whole point of the change and a
        # reader a year from now should be able to see it went from 1.43 to a
        # shard without re-deriving it.
        "processes": 1,
        "images_per_process": written,
        "seeds": [[run["seed"], run["seed"] + run["count"] - 1] for run in shard["runs"]],
    })
    return {"shard": shard["index"], "backend": backend, "images": written,
            "processes": 1, "images_per_process": written, "skipped": False}


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
