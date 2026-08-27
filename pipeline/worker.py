"""Render one shard, completely or not at all.

    python pipeline/worker.py --plan data/run01/plan.json --shard 3 --out data/run01

A worker owns a directory and answers one question about it: is there a `DONE`
file? If there is, the shard is finished and is left alone -- that is resume. If
there is not, whatever is in the directory is **deleted** and the shard is
rendered from the start.

That deletion is the part worth arguing about, and it is not an optimisation
choice. A half-finished shard left in place is a directory whose images and
records do not agree about what it holds, and that is invisible: every file
parses, the count is plausible, and a model trains on a set that is not the one
the plan describes. Redoing a few images is cheap; finding that later is not.

Three details decide whether the resume story is true rather than approximate:

* **`DONE` is written last, and atomically.** A temporary file renamed into
  place, after every record is fsynced. If `DONE` could appear before the last
  record was on disk, resume would skip a shard that is short, and the run would
  quietly produce fewer images than it claims.
* **Records are written as they arrive**, one file per image, rather than
  collected and written at the end -- so a shard's memory does not grow with its
  size. The renderer writes its own the same way, which matters now that one
  invocation draws a whole shard rather than one layout.
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
from pipeline import drift, imagetimes, invariants, record, synthesis  # noqa: E402
from pipeline.config import RULES_ENV  # noqa: E402
from pipeline.plan import image_name  # noqa: E402

DONE = "DONE"

# What each shard writes down about its own content, beside its records.
# Separate from them because they are hashed by the golden baseline: a
# measurement added to a record would make every W1 verification fail for a
# reason that has nothing to do with what W1 verifies. `drift.json` sits beside
# it for the same reason.
INVARIANTS = invariants.INVARIANTS_NAME

# name -> (script, working directory). The interpreter is resolved at call time
# through `venv_python`, which knows that a virtualenv keeps it in `bin/` on
# POSIX and `Scripts\` on Windows -- hardcoding either is how this breaks on the
# other platform.
#
# `html` only. The glyph and WeasyPrint backends were removed from this table
# rather than left in it unused: a registry is what turns a name in a plan into
# a process, so a name still in here is a backend that still runs. Why each was
# retired is in `pipeline/config.RETIRED_BACKENDS`, which refuses them earlier
# and louder; this is the backstop for a plan that reached dispatch anyway.
BACKENDS = {
    "html": (REPO_ROOT / "generators" / "html" / "render.py", REPO_ROOT),
}

CLEAN_FORCES = invariants.CLEAN_FORCES


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
    start-up in full. Measured in `data/profile/README.md`, that was 29% of an
    html run -- the largest single cost in the generator, and in none of the
    renderers. (The same measurement put the two retired backends at 23% and
    44%; the numbers stay because they are what the fix was judged against.)

    `--jobs` takes the whole list instead, so the cost is paid once. Nothing
    about a page changes: see `worklist.py`, and the byte comparison in
    `tests/test_worklist.py`.
    """
    if backend not in BACKENDS:
        raise ShardError(
            f"{backend!r} is not a backend this repository draws with; "
            f"have {sorted(BACKENDS)}. See pipeline/config.RETIRED_BACKENDS."
        )
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
    if clean:
        # Every chain-bearing attribute, not just `augmentation`: since the
        # copier became `toner`/`drum`/`rollers`, pinning one of the four
        # leaves the other three free to draw a mark onto the "clean" set.
        # An explicit `--force` still wins -- pinning `drum=drum_streaked` on a
        # clean run is a strange thing to ask for, but it is an ask.
        already = {item.partition("=")[0] for item in forced}
        forced += [f"{attribute}={value}" for attribute, value in CLEAN_FORCES.items()
                   if attribute not in already]
    for item in forced:
        command += ["--force", item]
    # `--clean` used to ride along here as well: it switched off the glyph
    # backend's own geometry -- the paper curl and the re-photograph -- which
    # the ageing chain does not own. No drawable backend has geometry of that
    # kind, so a clean run is now exactly `augmentation=pristine`.
    if template:
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
    timed: list[imagetimes.Entry] = []
    staging = Path(tempfile.mkdtemp(prefix="shard-", dir=str(directory)))
    # A record per image, written beside it, and one `synthesis.json` for the
    # shard. The first is what a converted page looks like; the second is how
    # these ones were made, which no converter could return and which nothing
    # can redraw a committed image without.
    with synthesis.Writer(synthesis.beside(directory), backend) as notes:
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
                # Images PER PROCESS, which is the number W3b was about, and it
                # is the whole shard: one renderer process draws all of it. The
                # job count is a separate fact and is one job per image since
                # the layouts are dealt rather than blocked (`plan.py::deal`) --
                # printing images-per-JOB here would read as the 1.43 regression
                # this line was written to watch for.
                log.write(f"  {len(jobs)} job(s), {worklist.total(jobs)} image(s), "
                          f"1 process, {worklist.total(jobs)} per process\n")
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

            produced = record.read(staging)
            expected_total = sum(run["count"] for run in shard["runs"])
            if len(produced) != expected_total:
                raise ShardError(
                    f"shard {shard['index']} {backend}: asked for "
                    f"{expected_total} images, got {len(produced)}")

            # The renderer's own provenance, read back whole: it is small (one
            # entry per page plus one params block per option the rule-base
            # offers) and it is needed per page below, by the invariants and by
            # the rename.
            try:
                drew = synthesis.read(staging)
            except synthesis.SynthesisError as error:
                raise ShardError(
                    f"shard {shard['index']} {backend}: {error}") from error
            gaps = drew.problems(record.file_name(item) for item in produced)
            if gaps:
                raise ShardError(
                    f"shard {shard['index']} {backend}: " + "; ".join(gaps))

            # How long each page took, under the renderer's own names. Re-keyed
            # to the dataset's names in the loop below -- the same rename the
            # image gets, at the same moment, so the two can never drift apart.
            # Absent is not an error: `imagetimes.read` returns `{}` and the run
            # reports "no per-image timing" rather than refusing to finish.
            drawn_times = imagetimes.read(staging)

            cursor = 0
            for run in shard["runs"]:
                for offset in range(run["count"]):
                    item = produced[cursor]
                    cursor += 1
                    target = image_name(backend, run["first_index"] + offset)
                    drawn_name = record.file_name(item)
                    # The renderer's own provenance says which layout it drew.
                    # Checked against the job it was meant to be, because
                    # walking one list against another by position is exactly
                    # the arrangement where an off-by-one mislabels every image
                    # after it and nothing downstream notices.
                    drawn = drew.drawn_layout(drawn_name)
                    if drawn and drawn != run["layout"]:
                        raise ShardError(
                            f"shard {shard['index']} {backend}: record {cursor - 1} "
                            f"is {drawn!r} where the plan asked for "
                            f"{run['layout']!r}; the renderer returned its pages "
                            f"in a different order from the job list")
                    shutil.move(str(staging / drawn_name), str(directory / target))
                    clock = drawn_times.get(drawn_name)
                    if clock is not None:
                        # The plan's layout, not the renderer's, for the same
                        # reason the record takes it: they were just checked
                        # against each other, and every other file in this
                        # directory says the plan's name.
                        timed.append(imagetimes.Entry(
                            file=target, layout=run["layout"],
                            seconds=clock.seconds, stages=dict(clock.stages)))

                    page = dict(drew.entry(drawn_name))
                    recipe = drew.recipe(drawn_name)
                    # Four fields follow the dataset's own name for the page,
                    # and the `job_id` is a function of all four. The layout is
                    # the plan's here, not the renderer's: they were checked
                    # against each other a moment ago.
                    record.stamp(item, parser=backend, layout=run["layout"],
                                 seed=recipe.get("seed"), filename=target)
                    record.check(item, where=target)
                    try:
                        tally.inspect(item, recipe=recipe, layout=run["layout"],
                                      image=directory / target, where=target)
                    except invariants.InvariantError as error:
                        raise ShardError(
                            f"shard {shard['index']} {backend}/{run['layout']}: "
                            f"{error}") from error
                    # fsynced as it is written: the `DONE` below must not
                    # appear in front of a record that is not yet on disk, or
                    # resume would skip a shard that is short.
                    record.write_one(item, directory, fsync=True)
                    notes.add(target, job_id=item["job_id"], layout=run["layout"],
                              recipe=recipe,
                              text_sequence=str(page.pop("text_sequence", "")),
                              extra={key: value for key, value in page.items()
                                     if key not in ("job_id", "seed", "layout",
                                                    "attributes", "tags")})
                    written += 1
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        # Every record is on disk by here -- `record.write_one(fsync=True)` --
        # and `notes` is closed by its context manager immediately after. Its
        # last write is what makes `synthesis.json` parse at all, so a shard
        # killed here leaves a file that fails to load rather than one that
        # loads and is short.

    # The per-image times, under the dataset's names now, beside the images they
    # measure. Written here rather than left in the staging directory, which is
    # about to be gone, and written even when the budget check below stops the
    # shard: a shard that failed slowly is exactly the one somebody times.
    if timed:
        with imagetimes.Log(directory) as clock:
            for entry in timed:
                clock.add(entry)

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
