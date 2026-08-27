"""What the run did: every case, its verdict, and what it cost.

    out/report.json      machine-readable, one entry per shard and per check
    printed to stdout    the same thing, short enough to read

`manifest.json` says what the dataset *is* and has to compare byte for byte
between a one-worker run and an eight-worker one, so it can hold no duration
and no verdict that depends on wall-clock. `timings.json` says how long, and
nothing else. Neither answers the question a person actually asks after a run
of forty minutes: **did it pass, and if not, which part.**

So this file, and the split is deliberate:

* `manifest.json` -- comparable. Counts only.
* `timings.json`  -- durations, per shard and per image summary.
* `report.json`   -- verdict. Cases, pass/fail, and the durations quoted
  alongside them, because "which case failed" and "which case was slow" are
  read at the same moment and nobody wants to join two files by hand.

## What counts as a case

Two kinds, and they fail differently:

* a **shard** -- twenty-odd images rendered by one process. `pass` if it
  reached `DONE`, `fail` if the worker raised, `resumed` if it was already
  finished before this run started and was left alone. `resumed` is not a
  pass: this run did not draw it, and a report that claimed it did would be
  the run taking credit for an earlier one's work.
* a **check** -- a gate over the whole run: preflight, pairing, the invariant
  budget, drift against the expected mix. These are what stop a run that
  produced every image and got them wrong.

A run passes when every case passes. `verdict` is that sentence and nothing
more clever; the exit code of `pipeline/run.py` agrees with it.
"""

from __future__ import annotations

import json
from pathlib import Path

from pipeline import imagetimes, progress

NAME = "report.json"

PASS, FAIL, RESUMED = "pass", "fail", "resumed"


def beside(directory: Path | str) -> Path:
    return Path(directory) / NAME


def _shard_cases(plan: dict, results: list[dict], done: dict[int, bool]) -> list[dict]:
    """One entry per shard in the plan, whether this run touched it or not.

    Walked from the plan rather than from the results, because the results only
    hold the shards this run was given: on a resume that is two out of twelve,
    and a report listing two shards for a twelve-shard dataset describes
    something that does not exist.
    """
    by_index = {result["shard"]: result for result in results}
    cases: list[dict] = []
    for shard in sorted(plan["shards"], key=lambda s: s["index"]):
        index = shard["index"]
        result = by_index.get(index)
        if result is None:
            status = PASS if done.get(index) else FAIL
            case = {"shard": index, "backend": shard["backend"],
                    "status": RESUMED if status == PASS else FAIL,
                    "images": shard["count"] if status == PASS else 0}
            if status == FAIL:
                case["error"] = "not rendered and not done"
        else:
            failed = bool(result.get("error"))
            case = {
                "shard": index,
                "backend": shard["backend"],
                "status": RESUMED if result.get("skipped") else (FAIL if failed else PASS),
                "images": result.get("images", 0),
                "seconds": result.get("seconds"),
            }
            if failed:
                case["error"] = str(result["error"]).strip().splitlines()[0]
        case["layouts"] = sorted({run["layout"] for run in shard["runs"]})
        case["asked"] = shard["count"]
        cases.append(case)
    return cases


def build(*, plan: dict, results: list[dict], frameworks: dict,
          warnings: list[str], checks: list[dict], elapsed: float, workers: int,
          times, done: dict[int, bool]) -> dict:
    """The whole verdict. `checks` are the gates the caller already ran."""
    shards = _shard_cases(plan, results, done)
    failed = [case for case in shards if case["status"] == FAIL]
    failed_checks = [check for check in checks if check["status"] == FAIL]
    written = sum(entry["images"] for entry in frameworks.values())
    asked = sum(shard["count"] for shard in plan["shards"])
    entries = list(times)
    return {
        "verdict": FAIL if (failed or failed_checks) else PASS,
        "workers": workers,
        "seconds_total": round(elapsed, 3),
        "images": {"asked": asked, "written": written},
        "cases": {
            "shards": len(shards),
            "passed": sum(1 for case in shards if case["status"] == PASS),
            "resumed": sum(1 for case in shards if case["status"] == RESUMED),
            "failed": len(failed),
            "checks": len(checks),
            "checks_failed": len(failed_checks),
        },
        "checks": checks,
        "shards": shards,
        # The per-image numbers live here as well as in `timings.json`: a
        # report that says a shard failed and cannot say the run was three
        # times slower than usual makes a person open two files to ask one
        # question.
        "timing": imagetimes.summarise(entries),
        "warnings": sorted(warnings),
    }


def write(directory: Path | str, payload: dict) -> Path:
    path = beside(directory)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False,
                               sort_keys=True) + "\n", encoding="utf-8")
    return path


def render(payload: dict, limit: int = 8) -> str:
    """The console version: the verdict, the cost, and what went wrong.

    Every failure is printed, however many; the *slowest layouts* are cut at
    `limit`, because that list is a curiosity and the failures are not.
    """
    cases = payload["cases"]
    timing = payload.get("timing") or {}
    lines = [
        f"KẾT QUẢ: {payload['verdict'].upper()} — "
        f"{payload['images']['written']}/{payload['images']['asked']} ảnh, "
        f"{progress.duration(payload['seconds_total'])}, "
        f"{payload['workers']} worker",
        f"  shard: {cases['passed']} pass, {cases['resumed']} sẵn có, "
        f"{cases['failed']} fail; kiểm tra: "
        f"{cases['checks'] - cases['checks_failed']}/{cases['checks']} pass",
    ]
    if timing.get("images"):
        lines.append(
            f"  mỗi ảnh: trung bình {timing['seconds_mean']:.2f}s, "
            f"trung vị {timing['seconds_median']:.2f}s, "
            f"p95 {timing['seconds_p95']:.2f}s, "
            f"chậm nhất {timing['slowest']['seconds']:.2f}s "
            f"({timing['slowest']['layout'] or '?'})")
        slow = sorted((entry for entry in timing.get("by_layout", {}).items()),
                      key=lambda item: item[1]["seconds_mean"], reverse=True)
        for layout, numbers in slow[:limit]:
            lines.append(f"    {layout:24} {numbers['images']:4d} ảnh  "
                         f"{numbers['seconds_mean']:6.2f}s/ảnh")
        if len(slow) > limit:
            lines.append(f"    … {len(slow) - limit} bố cục nữa (report.json)")
    for check in payload["checks"]:
        if check["status"] == FAIL:
            lines.append(f"  [FAIL] {check['name']}: {check.get('detail', '')}")
    for case in payload["shards"]:
        if case["status"] == FAIL:
            lines.append(f"  [FAIL] shard {case['shard']}: "
                         f"{case.get('error', 'không rõ')}")
    for warning in payload["warnings"]:
        lines.append(f"  [warn] {warning}")
    return "\n".join(lines)


__all__ = ["FAIL", "NAME", "PASS", "RESUMED", "beside", "build", "render", "write"]
