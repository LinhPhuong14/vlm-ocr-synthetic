"""Run a whole job: preflight, shards in parallel, then assemble.

    python pipeline/run.py                       # reads pipeline.yaml
    python pipeline/run.py -c pipeline.yaml --workers 8

Order matters and is not negotiable. **Preflight comes first**, and any problem
stops the run -- including one labelled `unchecked:`, because a job that starts
without knowing whether its fonts cover its corpus is the thing preflight exists
to prevent. Forty minutes of rendering saved by four hundred milliseconds of
looking.

Parallelism is by **process**, never thread: Playwright's sync API is not
thread-safe and synthtiger seeds numpy's global RNG, so two threads would
quietly interleave each other's randomness and the seeds would stop meaning
anything.

**`manifest.json` carries no durations.** The headline check of W1 is that one
worker and eight produce byte-identical output, manifest included, and a
duration is never identical. Put one in and the check has to be relaxed to
"identical except these fields", and the exempt list only ever grows. Timings go
to `timings.json`, which nothing compares.

Layout on disk:

    out/
      plan.json          what was asked for; no absolute paths, portable
      .shards/shard-*/   one directory per shard, each with its own DONE
      manifest.json      what happened; comparable byte for byte
      timings.json       how long it took; deliberately not comparable
      <backend>/         the assembled dataset, as the sequential driver left it
      dataset.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import multiprocessing
import os
import shutil
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from pipeline import drift, invariants, preflight, record, synthesis  # noqa: E402
from pipeline.config import Config, apply_overrides, materialise_rules  # noqa: E402
from pipeline.plan import build_plan, write_plan  # noqa: E402
from pipeline.worker import (  # noqa: E402
    INVARIANTS,
    ShardError,
    is_done,
    render_shard,
    shard_dir,
)

SHARDS_DIR = ".shards"


def gather_invariants(plan: dict, shards_root: Path) -> dict:
    """Add up what every finished shard measured about its own content.

    Counts only, summed in shard order, so two runs of the same plan produce
    the same bytes here -- `manifest.json` is compared whole, and W1's headline
    check is that one worker and eight agree on it.
    """
    images = boxes = 0
    values: dict[str, int] = {}
    unprinted: dict[str, dict[str, int]] = {}
    notes: dict[str, int] = {}
    unchecked: set[str] = set()

    for shard in sorted(plan["shards"], key=lambda s: s["index"]):
        path = shard_dir(shards_root, shard["index"]) / INVARIANTS
        if not path.exists():
            continue
        report = json.loads(path.read_text(encoding="utf-8"))
        images += report.get("images", 0)
        boxes += report.get("boxes", 0)
        for layout, count in (report.get("label_values") or {}).items():
            values[layout] = values.get(layout, 0) + count
        for layout, fields in (report.get("unprinted") or {}).items():
            for name, count in fields.items():
                bucket = unprinted.setdefault(layout, {})
                bucket[name] = bucket.get(name, 0) + count
        for name, count in (report.get("notes") or {}).items():
            notes[name] = notes.get(name, 0) + count
        unchecked.update(report.get("unchecked") or [])

    return {
        "images": images,
        "boxes": boxes,
        "label_values": dict(sorted(values.items())),
        "unprinted": {layout: dict(sorted(fields.items()))
                      for layout, fields in sorted(unprinted.items())},
        "notes": dict(sorted(notes.items())),
        "unchecked": sorted(unchecked),
    }


def gather_drift(plan: dict, shards_root: Path, quality: dict | None,
                 rules=None) -> tuple[dict, list[str]]:
    """Compare every finished shard's mix against what the plan asked for.

    Done here rather than in the worker because the expectation is a property of
    the whole plan, and because a shard that is merely *unusual* should not fail
    -- the run reports it and returns non-zero, which is loud without throwing
    away an hour of rendering. The content-source axis is the exception and is
    already handled in the worker: that one is a fault, not a mix.
    """
    tolerance = drift.tolerance_of(quality)
    vectors: list[dict] = []
    warnings: list[str] = []
    notes: list[str] = []

    for shard in sorted(plan["shards"], key=lambda s: s["index"]):
        path = shard_dir(shards_root, shard["index"]) / drift.VECTOR
        if not path.exists():
            continue
        vector = json.loads(path.read_text(encoding="utf-8"))
        vectors.append(vector)
        shares, problems = drift.expected_shares(shard, plan, rules=rules)
        warnings += [f"shard {shard['index']}: {problem}" for problem in problems]
        found, stops, said = drift.compare(vector, shares, tolerance=tolerance)
        warnings += [f"shard {shard['index']}: {message}" for message in found + stops]
        notes += [f"shard {shard['index']}: {message}" for message in said]

    summary = drift.summarise(vectors, plan.get("pairing", "paired"))
    summary["tolerance"] = tolerance
    # Not warnings: "too small to judge" is a fact about the request, not a
    # fault, and a correct 60-image run must not exit non-zero because of it.
    summary["notes"] = sorted(set(notes))
    return summary, sorted(set(warnings))


def _render_one(job: dict) -> dict:
    """Run one shard in a worker process. Must be importable, hence top-level."""
    out = Path(job["out"])
    plan = json.loads(Path(job["plan"]).read_text(encoding="utf-8"))
    shard = next(s for s in plan["shards"] if s["index"] == job["index"])
    logs = out / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    started = time.time()
    with open(logs / f"shard-{job['index']:04d}.log", "a", encoding="utf-8") as log:
        try:
            result = render_shard(
                shard, out, plan,
                rules_root=Path(job["rules_root"]) if job.get("rules_root") else None,
                log=log,
            )
            result["error"] = None
        except (ShardError, Exception) as error:  # noqa: BLE001 - reported, not raised
            log.write(f"FAILED: {error}\n")
            result = {"shard": job["index"], "backend": shard["backend"],
                      "images": 0, "skipped": False, "error": str(error)}
    result["seconds"] = round(time.time() - started, 3)
    return result


def assemble(out: Path, plan: dict, shards_root: Path) -> tuple[dict, list[str]]:
    """Gather finished shards into the flat per-backend dataset.

    Images are hard-linked rather than moved, so the shard directories stay
    intact and a later resume still sees its own `DONE`. On a filesystem that
    cannot link, this falls back to copying.
    """
    warnings: list[str] = []
    frameworks: dict[str, dict] = {}

    for backend in plan["backends"]:
        target = out / backend
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)

        by_layout: dict[str, int] = {}
        # Counted, not assumed. Before W1b a pinned draw walked to the next
        # fitting seed, so twenty images held ten receipts and every denominator
        # in the proof reports was wrong by a factor of two. A dataset that does
        # not report its own distinct-sample count lets that happen again at a
        # larger size with nobody watching.
        seeds: set[int] = set()
        labels: set[str] = set()
        written = 0
        # The records and the provenance, assembled together: they are one
        # dataset, and a run that produced only half of it would leave images
        # nothing can redraw.
        with synthesis.Writer(synthesis.beside(target), backend) as notes:
            for shard in sorted((s for s in plan["shards"] if s["backend"] == backend),
                                key=lambda s: s["index"]):
                directory = shard_dir(shards_root, shard["index"])
                if not is_done(directory):
                    warnings.append(
                        f"shard {shard['index']} ({backend}) is missing from the "
                        f"assembled dataset: no DONE")
                    continue
                drew = synthesis.read_if_there(directory)
                for item in record.read(directory):
                    name = record.file_name(item)
                    source = directory / name
                    destination = target / name
                    try:
                        os.link(source, destination)
                    except OSError:
                        shutil.copy2(source, destination)
                    record.write_one(item, target)

                    page = dict(drew.entry(name))
                    recipe = drew.recipe(name) if name in drew else {}
                    notes.add(name, job_id=item["job_id"],
                              layout=drew.layout(name) if name in drew else "",
                              recipe=recipe,
                              text_sequence=str(page.pop("text_sequence", "")),
                              extra={key: value for key, value in page.items()
                                     if key not in ("job_id", "seed", "layout",
                                                    "attributes", "tags")})

                    layout = drew.layout(name) if name in drew else "?"
                    by_layout[layout] = by_layout.get(layout, 0) + 1
                    seeds.add(recipe.get("seed"))
                    labels.add(hashlib.sha256(
                        record.ground_truth(item).encode("utf-8")).hexdigest())
                    written += 1
        frameworks[backend] = {
            "images": written,
            "distinct_seeds": len(seeds),
            "distinct_labels": len(labels),
            "by_layout": by_layout,
        }
        if written and len(labels) < written:
            warnings.append(
                f"{backend}: {written} images but only {len(labels)} distinct "
                f"labels; the sample is smaller than the file count says")
    return frameworks, warnings


def execute(config: Config, *, workers: int | None = None,
            skip_preflight: bool = False, runs=None) -> int:
    """Run one job. The entry point for both the CLI and `generate_dataset.py`.

    Taking a `Config` rather than a path is what lets the compatibility shell
    reuse this without writing a temporary YAML file and parsing it back.
    """
    workers = workers or config.workers

    # 1. Preflight. Everything, before anything.
    if not skip_preflight:
        problems = preflight.check()
        if problems:
            print(f"PREFLIGHT: {len(problems)} vấn đề — không chạy\n")
            for problem in problems:
                print(f"  - {problem}")
            return 1

    from rulebase import available_layouts
    from rulebase.spec import load_rules

    # The run says which layouts, or takes the directory. Naming them is how a
    # fixed comparison stays fixed: `split_by_layout` walks the list in order,
    # so a plan that took the directory draws a different set the day someone
    # adds a layout -- which is how the golden baseline went red without being
    # able to say why.
    available = available_layouts()
    layouts = list(config.layouts) if config.layouts else available
    unknown = [name for name in layouts if name not in available]
    if unknown:
        raise SystemExit(
            f"run.layouts: no such layout(s) {unknown}; have {', '.join(available)}")
    out = config.out
    out.mkdir(parents=True, exist_ok=True)
    shards_root = out / SHARDS_DIR
    shards_root.mkdir(parents=True, exist_ok=True)

    # 2. Overrides become a rules directory the renderer subprocesses can read.
    rules_root = None
    rendered_rules = None
    if config.overrides:
        rendered_rules = apply_overrides(load_rules(), config.overrides)
        rules_root = materialise_rules(rendered_rules, out / ".rules")

    # 3. Plan.
    plan = build_plan(config, layouts, runs=runs)

    # Before a single page is drawn: under `paired` the backends must actually
    # be drawing the same receipts. Cheap, and the alternative is finding out
    # from a proof report months later that three renderers were compared on
    # three different corpora -- which is what happened before W1b.
    mismatched = invariants.paired_content(plan)
    if mismatched:
        print(f"PAIRING: {len(mismatched)} vấn đề — không chạy\n")
        for problem in mismatched:
            print(f"  - {problem}")
        return 1

    plan_path = write_plan(plan, out / "plan.json")
    plan_sha = hashlib.sha256(plan_path.read_bytes()).hexdigest()

    pending = [s for s in plan["shards"] if not is_done(shard_dir(shards_root, s["index"]))]
    print(f"{len(plan['shards'])} shard, {len(pending)} chưa xong, {workers} worker")

    jobs = [{"out": str(shards_root), "plan": str(plan_path), "index": s["index"],
             "rules_root": str(rules_root) if rules_root else None}
            for s in pending]

    started = time.time()
    results: list[dict] = []
    if jobs:
        # spawn, not fork: it is what Windows uses anyway, so a job that works
        # here works there rather than depending on inherited state.
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=min(workers, len(jobs)),
                                 mp_context=context) as pool:
            futures = {pool.submit(_render_one, job): job for job in jobs}
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                state = "ok" if not result["error"] else "FAILED"
                print(f"  [{state}] shard {result['shard']:4d} "
                      f"{result['backend']:9s} {result['images']:5d} ảnh")
    elapsed = time.time() - started

    # 4. Assemble whatever finished, then report honestly about the rest.
    frameworks, warnings = assemble(out, plan, shards_root)
    # The rules the run actually rendered with, overrides included: comparing an
    # overridden run against the shipped weights would report drift on every one.
    quality, drifting = gather_drift(plan, shards_root, config.quality,
                                     rules=rendered_rules)
    warnings += drifting
    failed = sorted((r for r in results if r["error"]), key=lambda r: r["shard"])

    manifest = {
        "plan_sha256": plan_sha,
        "seed": plan["seed"],
        # Which mode produced this dataset. Not decoration: every
        # side-by-side number computed from it is only interpretable
        # once you know whether the backends drew the same receipts.
        "pairing": plan.get("pairing", "paired"),
        "per_backend": plan["per_backend"],
        "backends": plan["backends"],
        "layouts": plan["layouts"],
        "shard_size": plan["shard_size"],
        "clean": plan["clean"],
        "force": plan["force"],
        "overrides": plan["overrides"],
        "shards": [
            {"index": s["index"], "backend": s["backend"],
             "images": s["count"],
             # One renderer process per shard since W3b, whatever the layout
             # count. Recorded because it is a property of the run worth being
             # able to check without reading the worker, and because it was 14
             # here before the change. It is a count, not a duration, so it
             # compares byte for byte between one worker and eight.
             "renderer_processes": 1,
             "seeds": [[r["seed"], r["seed"] + r["count"] - 1] for r in s["runs"]],
             "layouts": sorted({r["layout"] for r in s["runs"]}),
             "done": is_done(shard_dir(shards_root, s["index"]))}
            for s in sorted(plan["shards"], key=lambda s: s["index"])
        ],
        "frameworks": frameworks,
        # Counts, not durations: see the note below about what this file is for.
        "invariants": gather_invariants(plan, shards_root),
        # The run's mix, and the tolerance it was judged against. Also counts,
        # for the same reason: two runs of one plan must agree here byte for byte.
        "quality": quality,
        "failed": [{"shard": r["shard"], "backend": r["backend"], "error": r["error"]}
                   for r in failed],
        "warnings": sorted(warnings),
    }
    # Sorted keys and no durations: this file has to compare byte for byte
    # between a one-worker run and an eight-worker one, which is the whole
    # point of W1. See timings.json for how long it took.
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")

    (out / "timings.json").write_text(json.dumps({
        "workers": workers,
        "seconds_total": round(elapsed, 3),
        "shards": sorted(
            ({"shard": r["shard"], "seconds": r["seconds"]} for r in results),
            key=lambda r: r["shard"]),
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # `dataset.json` in the shape the sequential driver wrote, so everything
    # downstream -- ocr_proof, check_boxes, the READMEs -- keeps working.
    (out / "dataset.json").write_text(json.dumps({
        "per_framework": plan["per_backend"],
        "layouts": plan["layouts"],
        # Downstream tools read this file rather than the manifest, and a
        # comparison between renderers only means something under `paired`.
        "pairing": plan.get("pairing", "paired"),
        "clean": plan["clean"],
        "force": plan["force"],
        # Which page model drew these images. Absent or empty is the character
        # grid, which is what every set built before `generators/html/sheets/`
        # existed was; a reader should not have to guess from the pixels.
        "template": plan.get("template", ""),
        "frameworks": frameworks,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    total = sum(entry["images"] for entry in frameworks.values())
    print(f"\n{total} ảnh -> {out}")
    if failed or warnings:
        for entry in manifest["failed"]:
            print(f"  [FAILED] shard {entry['shard']}: {entry['error'].splitlines()[0]}")
        for warning in manifest["warnings"]:
            print(f"  [warn] {warning}")
        # A shard that failed must never look like a smaller run that succeeded.
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-c", "--config", type=Path, default=REPO_ROOT / "pipeline.yaml")
    parser.add_argument("--workers", type=int, help="override run.workers")
    parser.add_argument("-o", "--out", type=Path, help="override run.out")
    parser.add_argument("--no-preflight", action="store_true",
                        help=argparse.SUPPRESS)  # for testing preflight itself
    args = parser.parse_args()

    config = Config.load(args.config)
    if args.out:
        config = replace(config, out=Path(args.out).expanduser().resolve())
    return execute(config, workers=args.workers, skip_preflight=args.no_preflight)


if __name__ == "__main__":
    raise SystemExit(main())
