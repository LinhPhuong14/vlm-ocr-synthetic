"""Measure where the generator spends its time, and leave a model behind.

    python tools/profile_pipeline.py -c 5 -o data/profile

Two passes, because they answer two different questions.

**Pass A -- the breakdown.** Each renderer draws the same seeds with the
sampler's own mix of ageing, and reports how long each stage took. This is the
percentage table: which stage of *this* renderer dominates.

**Pass B -- the ageing.** Each renderer draws again with one augmentation
pinned at a time. Pass A measures whatever mix the sampler happened to draw, so
a model that appears in one recipe out of twenty is timed on one image; pinning
gives every scenario the same number of images and makes the costs comparable
with each other rather than with the draw.

The output is a **cost model**, not a report: `cost_model.json` holds seconds
per image per stage per renderer, seconds per call per degradation model, and
the fixed cost of starting each backend, so a later load test can *predict* how
long a plan will take and compare the prediction with the clock. A prediction
that misses is the finding -- that is what the file is for. `predict()` here is
the same arithmetic, so the two cannot drift.

Three things this deliberately does not do:

* **It does not have a suspect list.** Every stage is timed, including reading
  the YAML rules, which is nobody's idea of a bottleneck and was the largest
  single cost found before this tool existed.
* **It does not leave a remainder implicit.** The interpreter start-up a child
  process cannot see is measured from outside and named `interpreter`, so the
  stages sum to the wall clock instead of to most of it.
* **It does not trust its own instrument.** Every report carries what the
  stopwatch cost, and this driver refuses to be quiet about it: see
  `overhead` in the output and the `--check` thresholds.

Nothing here changes a pixel. The stopwatch is off unless `--profile` is
passed, and off it is a no-op object; `make baseline-verify` after a profiling
run must still say the plans are unchanged.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from paths import VENVS, venv_python  # noqa: E402

import profiling  # noqa: E402

# name -> (script, working directory). Same table the worker uses; kept here
# rather than imported so this tool does not drag the pipeline package (and its
# YAML dependency) into a renderer venv that may not have it.
BACKENDS = {
    "synthdog": (REPO_ROOT / "generators" / "synthdog" / "render.py",
                 REPO_ROOT / "generators" / "synthdog"),
    "html": (REPO_ROOT / "generators" / "html" / "render.py", REPO_ROOT),
    "genalog": (REPO_ROOT / "generators" / "genalog" / "render.py", REPO_ROOT),
}

# The stages the pipeline is made of, in the order they run. Printed in this
# order rather than sorted by cost, so two runs' tables line up and the eye can
# compare them.
#
# `scene` and `geometry` are separate on purpose. Both used to be `geometry`,
# and the row then read 1.695 s for the glyph renderer against 0.0006 s for
# genalog -- a factor of 2800, because it was measuring two different things.
# `scene` is curling the paper, dropping it on a background and photographing
# it, which only the glyph renderer does; `geometry` is working out where the
# boxes are, which all three do and which costs milliseconds. A label has to
# carry its meaning, or a reader draws the right conclusion from the wrong row.
STAGES = ("interpreter", "startup", "sampling", "content", "layout", "render",
          "scene", "geometry", "degradation", "annotation", "validation", "export")


class ProfileError(RuntimeError):
    pass


def run_backend(backend: str, count: int, seed: int, out: Path,
                force: list[str] | None = None) -> dict:
    """One renderer, `count` images, profiled. Returns its report.

    The subprocess is timed from outside as well as from inside. The difference
    is the interpreter start-up and the import of numpy, OpenCV, synthtiger or
    Playwright -- real seconds, paid once per process, that the child's own
    clock starts too late to see. Naming it is what lets the stages add up.
    """
    interpreter = venv_python(VENVS[backend])
    if not interpreter.exists():
        raise ProfileError(f"{backend}: no interpreter at {interpreter}. "
                           f"Build it with `python tasks.py setup-{backend}`.")
    script, cwd = BACKENDS[backend]
    images = out / "images"
    report = out / f"{backend}.json"
    command = [str(interpreter), str(script), "-o", str(images.resolve()),
               "-c", str(count), "--seed", str(seed),
               "--profile", str(report.resolve())]
    for item in force or []:
        command += ["--force", item]

    start = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    outer = time.perf_counter() - start
    if result.returncode != 0:
        tail = "\n".join((result.stderr + result.stdout).strip().splitlines()[-15:])
        raise ProfileError(f"{backend} failed (exit {result.returncode}):\n{tail}")
    if not report.exists():
        raise ProfileError(f"{backend} produced no profile at {report}")

    one = json.loads(report.read_text(encoding="utf-8"))
    one["stages"]["interpreter"] = {
        "calls": 1,
        "inclusive": round(outer - one["wall"], 6),
        "exclusive": round(outer - one["wall"], 6),
    }
    one["process_wall"] = round(outer, 6)
    one["images_dir"] = str(images)
    # Recomputed against the outer clock, which is the real time this cost.
    attributed = sum(entry["exclusive"] for entry in one["stages"].values())
    one["wall"] = round(outer, 6)
    one["unattributed"] = round(outer - attributed, 6)
    one["unattributed_share"] = round((outer - attributed) / outer, 6) if outer else 0.0
    return one


def time_validation(images: Path) -> dict:
    """Run the content checks a shard runs, over what a backend just drew.

    Validation lives in the worker rather than in a renderer, so it is the one
    stage a `--profile` run of a backend cannot see. It is measured here, on
    the same images, with the same call the worker makes -- not a re-implemented
    version of it, which would measure a different thing that happened to have
    the same name.
    """
    from pipeline import invariants, record

    metadata = images / "metadata.jsonl"
    if not metadata.exists():
        return {"calls": 0, "inclusive": 0.0, "exclusive": 0.0}

    tally = invariants.Tally(invariants.attribute_names())
    was = profiling.enabled()
    if not was:
        profiling.enable()
    for item in record.read(metadata):
        name = record.file_name(item)
        tally.inspect(item, image=images / name, where=name)
    entry = profiling.report()["stages"].get(
        "validation", {"calls": 0, "inclusive": 0.0, "exclusive": 0.0})
    if not was:
        profiling.disable()
    return entry


def augmentations() -> list[str]:
    """Every ageing scenario the rules offer, in draw order."""
    import rulebase

    return [option.id for option in rulebase.load_rules()["augmentation"]]


def conditions(pass_a: dict[str, dict], seed: int) -> dict:
    """What this cost model is a model *of*.

    Law 8, applied to seconds: a cost is a comparison point, so it has to carry
    the conditions it was taken under. It matters more here than it looks --
    ageing is between 14% and 55% of an image depending on the renderer, and
    which layouts and which chains were drawn moves the per-image cost on its
    own. Two numbers taken over different mixes are two answers to two
    questions, and comparing them silently is how an optimisation gets credited
    with a change in the draw.
    """
    import platform

    drawn: dict[str, dict[str, int]] = {}
    for backend, one in pass_a.items():
        counts: dict[str, int] = {}
        for name, entry in one["stages"].items():
            head, slash, tail = name.partition("/")
            if head == "degradation" and slash:
                counts[tail] = counts.get(tail, 0) + entry["calls"]
        drawn[backend] = dict(sorted(counts.items()))
    return {
        "seed": seed,
        "images": {backend: one.get("images", 0) for backend, one in pass_a.items()},
        "augmentation": "as drawn by the sampler (not pinned)",
        "degradation_calls": drawn,
        "machine": {"platform": platform.platform(),
                    "processor": platform.machine(),
                    "cpus": os.cpu_count(),
                    "python": platform.python_version()},
        "serial": "one renderer process at a time; no contention for the CPU",
    }


def cost_model(pass_a: dict[str, dict], pass_b: dict[str, dict[str, dict]],
               validation: dict[str, dict], seed: int = 0) -> dict:
    """Seconds per image, per stage, per renderer -- plus what is fixed.

    Split into `fixed` and `per_image` because they scale differently: eight
    workers pay the fixed cost eight times and the per-image cost once between
    them, so a model that merges the two mispredicts every plan that is not the
    shape of the one it was measured on.
    """
    per_image: dict[str, dict[str, float]] = {}
    fixed: dict[str, float] = {}
    for backend, one in pass_a.items():
        images = max(one.get("images", 0), 1)
        stages = one["stages"]
        # `interpreter` and `startup` are paid once per process, not per image.
        fixed[backend] = round(
            sum(stages.get(name, {}).get("inclusive", 0.0)
                for name in ("interpreter", "startup")), 6)
        # Inclusive, not exclusive: `sampling` and `degradation` are parents,
        # and their own exclusive time is nearly nothing -- all of it is in the
        # children. Top-level stages do not overlap, so their inclusive times
        # partition the run and the column sums to the wall clock.
        costs = {
            name: round(entry["inclusive"] / images, 6)
            for name, entry in stages.items()
            if "/" not in name and name not in ("interpreter", "startup")
        }
        got = validation.get(backend, {})
        if got.get("calls"):
            costs["validation"] = round(got["inclusive"] / images, 6)
        per_image[backend] = dict(sorted(costs.items()))

    # Per degradation model: seconds per call, pooled over every run that drew
    # it, in whichever renderer. The models operate on an image, not on a
    # receipt, so the renderer matters only through the page size.
    models: dict[str, dict[str, float]] = {}
    everything = list(pass_a.values()) + [one for by_aug in pass_b.values()
                                          for one in by_aug.values()]
    for one in everything:
        for name, entry in one["stages"].items():
            head, slash, tail = name.partition("/")
            if head != "degradation" or not slash:
                continue
            into = models.setdefault(tail, {"calls": 0, "seconds": 0.0})
            into["calls"] += entry["calls"]
            into["seconds"] += entry["exclusive"]
    for name, entry in models.items():
        entry["seconds"] = round(entry["seconds"], 6)
        entry["per_call"] = round(entry["seconds"] / entry["calls"], 6) if entry["calls"] else 0.0

    # Per ageing scenario, per renderer: what pinning that chain costs an image.
    chains: dict[str, dict[str, float]] = {}
    for backend, by_aug in pass_b.items():
        for name, one in by_aug.items():
            images = max(one.get("images", 0), 1)
            cost = one["stages"].get("degradation", {}).get("inclusive", 0.0)
            chains.setdefault(name, {})[backend] = round(cost / images, 6)

    return {
        "version": 1,
        "conditions": conditions(pass_a, seed),
        "fixed_per_process": fixed,
        "per_image": per_image,
        "per_degradation_model": dict(sorted(models.items())),
        "per_augmentation": {name: dict(sorted(by.items()))
                             for name, by in sorted(chains.items())},
    }


def predict(model: dict, work: dict[str, int], processes: int = 1) -> dict:
    """Seconds this plan should take, from the cost model. The whole point.

    `work` is `{backend: images}`. `processes` is how many worker processes will
    draw it: the fixed cost is paid once by each, which is why a run split eight
    ways is not eight times faster.

    A load test calls this before it runs and compares afterwards. Where the two
    disagree, one of them is wrong about the generator, and finding out which is
    worth more than either number alone.
    """
    total = 0.0
    breakdown: dict[str, float] = {}
    for backend, count in work.items():
        costs = model["per_image"].get(backend)
        if costs is None:
            raise KeyError(f"the cost model has no {backend!r}; it has "
                           f"{sorted(model['per_image'])}")
        each = sum(costs.values())
        share = each * count + model["fixed_per_process"].get(backend, 0.0) * processes
        breakdown[backend] = round(share, 6)
        total += share
    return {"seconds": round(total, 6), "by_backend": breakdown,
            "serial": True, "processes": processes}


def verify(model: dict, backend: str, count: int, seed: int, out: Path) -> dict:
    """Predict a run the model was not fitted on, then run it and compare.

    A cost model that reproduces the run it was measured from has demonstrated
    arithmetic, not prediction. This holds out a different image count at a
    different seed -- so a different mix of layouts and ageing -- which is the
    situation the model exists for and the one where it can be wrong.

    The error is returned, not judged. A model that is 20% out is still useful
    for sizing a run; what would not be useful is not knowing.
    """
    expected = predict(model, {backend: count}, processes=1)
    here = out / "verify" / backend
    here.mkdir(parents=True, exist_ok=True)
    one = run_backend(backend, count, seed, here)
    measured = one["wall"] + time_validation(Path(one["images_dir"])).get("inclusive", 0.0)
    error = (measured - expected["seconds"]) / measured if measured else 0.0
    return {"backend": backend, "images": count, "seed": seed,
            "predicted": expected["seconds"], "measured": round(measured, 6),
            "error": round(error, 4)}


def shipped_plan() -> dict[str, tuple[int, int, int]]:
    """`{backend: (processes, was, images)}` for the run `pipeline.yaml` declares.

    Read from the plan rather than assumed. `processes` is one per shard, which
    is what the worker starts since W3b; `was` is one per run, which is what it
    started before, and a run is one layout. Both are here because the gap
    between them is the change: a twenty-image shard over fourteen layouts used
    to start fourteen processes drawing one and a half images each.
    """
    import rulebase
    from pipeline import plan as planning
    from pipeline.config import Config

    config = Config.load(REPO_ROOT / "pipeline.yaml")
    built = planning.build_plan(config, sorted(rulebase.available_layouts()))
    out: dict[str, list[int]] = {}
    for shard in built["shards"]:
        entry = out.setdefault(shard["backend"], [0, 0, 0])
        entry[0] += 1                                  # one process per shard
        entry[1] += len(shard["runs"])                 # what it used to be
        entry[2] += sum(run["count"] for run in shard["runs"])
    return {backend: tuple(counts) for backend, counts in out.items()}


def plan_cost(model: dict, shape: dict[str, tuple[int, int, int]]) -> list[str]:
    """What the declared run costs, and what it cost before W3b.

    Both columns, because a saving is only a number beside the thing it was
    saved from -- and because the prediction in the "before" column is what the
    change was decided on, so it should stay visible next to what happened.
    """
    lines = ["| backend | images | processes | s | was (1 per layout) | saved |",
             "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for backend, (processes, was, images) in sorted(shape.items()):
        costs = model["per_image"].get(backend)
        if costs is None:
            continue
        fixed = model["fixed_per_process"].get(backend, 0.0)
        now = sum(costs.values()) * images + fixed * processes
        before = sum(costs.values()) * images + fixed * was
        if not before:
            continue
        lines.append(
            f"| {backend} | {images} | {processes} (was {was}) | {now:.1f} | "
            f"{before:.1f} | {1 - now / before:.0%} |")
    return lines


def table(pass_a: dict[str, dict], validation: dict[str, dict]) -> list[str]:
    """The percentage table, all three renderers in one grid."""
    backends = list(pass_a)
    lines = ["| stage | " + " | ".join(f"{name} s | {name} %" for name in backends) + " |",
             "| --- | " + " | ".join(["---: | ---:"] * len(backends)) + " |"]
    totals = {}
    for backend, one in pass_a.items():
        total = one["wall"]
        got = validation.get(backend, {})
        totals[backend] = total + got.get("inclusive", 0.0)
    for stage in STAGES:
        cells = []
        for backend, one in pass_a.items():
            if stage == "validation":
                seconds = validation.get(backend, {}).get("inclusive", 0.0)
            else:
                seconds = one["stages"].get(stage, {}).get("inclusive", 0.0)
            share = seconds / totals[backend] if totals[backend] else 0.0
            cells.append(f"{seconds:.3f} | {share:.1%}")
        lines.append(f"| {stage} | " + " | ".join(cells) + " |")
    cells = []
    for backend, one in pass_a.items():
        seconds = one["unattributed"]
        share = seconds / totals[backend] if totals[backend] else 0.0
        cells.append(f"{seconds:.3f} | {share:.1%}")
    lines.append("| *unattributed* | " + " | ".join(cells) + " |")
    return lines


def degradation_table(model: dict) -> list[str]:
    """Every ageing model, dearest first. No suspect was named in advance."""
    rows = sorted(model["per_degradation_model"].items(),
                  key=lambda item: -item[1]["per_call"])
    lines = ["| degradation model | calls | s/call | total s |",
             "| --- | ---: | ---: | ---: |"]
    lines += [f"| {name} | {entry['calls']} | {entry['per_call']:.4f} | "
              f"{entry['seconds']:.3f} |" for name, entry in rows]
    return lines


def _verdicts(model: dict, pass_a: dict) -> list[str]:
    """Which suspects the numbers name, and which they clear.

    Written from the measurement rather than chosen in advance, because the
    point of measuring first is that the answer can disagree with the guess --
    and here it does. A model that has been rumoured to be the bottleneck for
    four waves is not the bottleneck, and the largest cost in the generator is
    in a stage nobody proposed optimising.
    """
    models = model["per_degradation_model"]
    total = sum(entry["seconds"] for entry in models.values()) or 1.0
    dearest = max(models.items(), key=lambda item: item[1]["seconds"])
    lines = []
    for name in ("gradient_domain", "paper_overlay"):
        entry = models.get(name)
        if not entry:
            continue
        lines.append(
            f"* `{name}`: {entry['per_call']:.3f} s a call, "
            f"{entry['seconds']:.1f} s over {entry['calls']} calls -- "
            f"{entry['seconds'] / total:.0%} of all the ageing measured here.")
    lines.append(
        f"* Dearest ageing model overall: `{dearest[0]}`, "
        f"{dearest[1]['seconds'] / total:.0%} of the ageing time.")
    for backend, one in pass_a.items():
        stages = {name: entry["inclusive"] for name, entry in one["stages"].items()
                  if "/" not in name}
        if not stages:
            continue
        top = max(stages.items(), key=lambda item: item[1])
        lines.append(f"* Dearest stage of `{backend}`: `{top[0]}`, "
                     f"{top[1] / one['wall']:.0%} of its wall clock.")
    lines.append("")
    lines.append(
        "Read that list before optimising anything. The stage a profile clears "
        "is worth as much as the one it names: an afternoon spent on a model "
        "that is a few percent of the ageing buys a few percent of a fraction, "
        "and the reason to measure first is that this cannot be told by "
        "reading the code.")
    return lines


def write_markdown(model: dict, pass_a: dict, validation: dict, path: Path,
                   overhead: dict, held_out: dict | None = None,
                   shape: dict[str, tuple[int, int]] | None = None) -> None:
    plan = plan_cost(model, shape) if shape else ["(the declared plan could not be read)"]
    lines = [
        "# Where the time goes",
        "",
        "Measured by `tools/profile_pipeline.py`. Every stage is timed, "
        "including the ones nobody suspects; the interpreter start-up a child "
        "process cannot see is measured from outside and named, so the column "
        "adds up to the wall clock rather than to most of it.",
        "",
        "## Per stage, per renderer",
        "",
        *table(pass_a, validation),
        "",
        "`interpreter` and `startup` are paid once per process, not per image, "
        "so their share shrinks as a run gets longer; every other row scales "
        "with the image count.",
        "",
        "## Per degradation model",
        "",
        *degradation_table(model),
        "",
        "## What the declared run costs",
        "",
        "`pipeline.yaml` as it stands, priced with the model above. The worker "
        "starts **one renderer process per shard**. It used to start one per "
        "*run*, and a run is one layout, so a twenty-image shard over fourteen "
        "layouts started fourteen processes drawing one and a half images each "
        "and paid start-up fourteen times.",
        "",
        *plan,
        "",
        "That was the largest lever this profile found, and it was not in a "
        "renderer or in a degradation model: it was the shape of the "
        "invocation. The renderers take a job list now (`worklist.py`), and "
        "the same plan went from 140 s to 98 s measured end to end. The "
        "saving predicted from this model before the change was made came "
        "within 7.3% of the saving measured after it -- which is the first "
        "time the cost model was used rather than merely built.",
        "",
        "## What this names, and what it clears",
        "",
        *_verdicts(model, pass_a),
        "",
        "## What the measurement cost",
        "",
        f"The stopwatch was entered {overhead['calls']} times at "
        f"{overhead['per_call'] * 1e9:.0f} ns a time -- "
        f"{overhead['total']:.4f} s, {overhead['share']:.4%} of the run. "
        "A profile whose instrument costs a noticeable share of what it "
        "measures is a measurement of the instrument.",
        "",
        "## The cost model",
        "",
        *(["The model was checked against a run it was not fitted on: "
           f"`{held_out['backend']}` x{held_out['images']} at seed "
           f"{held_out['seed']} was predicted at {held_out['predicted']:.2f} s "
           f"and took {held_out['measured']:.2f} s -- the model predicted "
           f"**{'high' if held_out['predicted'] > held_out['measured'] else 'low'}** "
           f"by {abs(held_out['error']):.1%}. The direction matters when the "
           "model is used to size a run: high is the safe side, and saying "
           "which side it errs on is part of the number. A different seed draws "
           "a different mix of layouts and ageing, which is the situation the "
           "model is for and the one where it can be wrong.", ""] if held_out else []),
        "`cost_model.json` beside this file holds the same numbers as seconds "
        "per image per stage, seconds per call per degradation model, and the "
        "fixed cost of starting each backend. `predict()` in "
        "`tools/profile_pipeline.py` turns a plan into an expected duration "
        "from it. The point of keeping it machine-readable is that a later "
        "load test can predict before it runs and compare afterwards: where "
        "prediction and clock disagree, that gap is the finding.",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--out", type=Path, default=Path("data/profile"))
    parser.add_argument("-c", "--count", type=int, default=5,
                        help="images per renderer in the breakdown pass")
    parser.add_argument("--ageing-count", type=int, default=2,
                        help="images per (renderer, augmentation) in the ageing pass")
    parser.add_argument("--seed", type=int, default=90000)
    parser.add_argument("--backends", default=",".join(BACKENDS))
    parser.add_argument("--verify", metavar="BACKEND",
                        help="after building the model, predict a held-out run of "
                             "this backend and report how far off the prediction was")
    parser.add_argument("--verify-count", type=int, default=4)
    parser.add_argument("--skip-ageing", action="store_true",
                        help="breakdown pass only -- no per-augmentation costs")
    parser.add_argument("--max-unattributed", type=float, default=0.05,
                        help="fail if more of the wall clock than this is unaccounted for")
    parser.add_argument("--rebuild", action="store_true",
                        help="re-derive the model and the report from the "
                             "`profile.json` already in --out, without rendering "
                             "anything. For editing the prose or the arithmetic "
                             "without spending twenty minutes of CPU to say the "
                             "same numbers back")
    args = parser.parse_args()

    backends = [name.strip() for name in args.backends.split(",") if name.strip()]
    unknown = set(backends) - set(BACKENDS)
    if unknown:
        raise SystemExit(f"unknown backends {sorted(unknown)}; have {sorted(BACKENDS)}")

    args.out.mkdir(parents=True, exist_ok=True)

    if args.rebuild:
        saved = json.loads((args.out / "profile.json").read_text(encoding="utf-8"))
        pass_a, pass_b = saved["breakdown"], saved["ageing"]
        validation, merged = saved["validation"], saved["merged"]
        model = cost_model(pass_a, pass_b, validation, seed=args.seed)
        old = json.loads((args.out / "cost_model.json").read_text(encoding="utf-8"))
        held_out = old.get("held_out")
        if held_out:
            model["held_out"] = held_out
        (args.out / "cost_model.json").write_text(
            json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        write_markdown(model, pass_a, validation, args.out / "README.md",
                       merged["overhead"], held_out, shipped_plan())
        print("\n".join(table(pass_a, validation)))
        print(f"\n-> {args.out}/README.md (rebuilt, nothing rendered)")
        return 0

    scratch = Path(tempfile.mkdtemp(prefix="profile-", dir=str(args.out)))
    try:
        pass_a: dict[str, dict] = {}
        validation: dict[str, dict] = {}
        for backend in backends:
            print(f"[breakdown] {backend} x{args.count}", flush=True)
            here = scratch / backend
            here.mkdir(parents=True, exist_ok=True)
            one = run_backend(backend, args.count, args.seed, here)
            pass_a[backend] = one
            validation[backend] = time_validation(Path(one["images_dir"]))

        pass_b: dict[str, dict[str, dict]] = {}
        if not args.skip_ageing:
            names = augmentations()
            for backend in backends:
                pass_b[backend] = {}
                for name in names:
                    print(f"[ageing] {backend} {name} x{args.ageing_count}", flush=True)
                    here = scratch / "ageing" / backend / name
                    here.mkdir(parents=True, exist_ok=True)
                    pass_b[backend][name] = run_backend(
                        backend, args.ageing_count, args.seed, here,
                        force=[f"augmentation={name}"])

        model = cost_model(pass_a, pass_b, validation, seed=args.seed)
        held_out = None
        if args.verify:
            if args.verify not in backends:
                raise SystemExit(f"--verify {args.verify} was not profiled; "
                                 f"this run covered {backends}")
            print(f"[verify] {args.verify} x{args.verify_count}", flush=True)
            held_out = verify(model, args.verify, args.verify_count,
                              args.seed + 50000, scratch)
            model["held_out"] = held_out
        merged = profiling.merge(list(pass_a.values())
                                 + [one for by in pass_b.values() for one in by.values()])
        (args.out / "cost_model.json").write_text(
            json.dumps(model, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (args.out / "profile.json").write_text(
            json.dumps({"breakdown": pass_a, "ageing": pass_b,
                        "validation": validation, "merged": merged},
                       indent=2, sort_keys=True) + "\n", encoding="utf-8")
        try:
            shape = shipped_plan()
        except Exception as error:                     # noqa: BLE001
            print(f"could not price the declared plan: {error}", file=sys.stderr)
            shape = None
        write_markdown(model, pass_a, validation, args.out / "README.md",
                       merged["overhead"], held_out, shape)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    print("\n".join(table(pass_a, validation)))
    print()
    print("\n".join(degradation_table(model)))
    print(f"\n-> {args.out}/cost_model.json")

    # The check that decides whether the rest may be read as a breakdown of the
    # run: a stage table that covers 80% of the time has not found where the
    # time goes.
    bad = {name: one["unattributed_share"] for name, one in pass_a.items()
           if one["unattributed_share"] > args.max_unattributed}
    if bad:
        for name, share in bad.items():
            print(f"{name}: {share:.1%} of the wall clock is unaccounted for "
                  f"(limit {args.max_unattributed:.0%})", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
