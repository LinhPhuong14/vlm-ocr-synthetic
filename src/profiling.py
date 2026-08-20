"""A stopwatch for the generator, off unless someone asks for it.

    with profiling.stage("degradation"):
        image = apply_recipe(image, recipe)

Three things decide whether a measurement of a pipeline is worth reading, and
all three are design choices made here rather than conventions to remember.

**Nothing is a suspect until it is measured.** The largest cost found in this
generator so far was `load_rules()` -- reading YAML, 4.1% of an image -- which
is in nobody's list of expensive things. So the instrument goes around whole
stages including the ones everyone assumes are free, and the unmeasured
remainder is *reported as a number* rather than left implicit. A profile whose
stages sum to 70% of the wall clock has not found where the time goes; it has
found where 70% of the time goes, which is a different and much weaker claim.

**Exclusive and inclusive are both kept.** A stage that contains another would
otherwise count its child twice, and the total would exceed the wall clock --
at which point the percentages are decoration. `stage()` nests: entering a
child suspends the parent's own accumulation, so exclusive times sum to the
time actually spent inside instrumented code and the difference from the wall
clock is the honest unattributed remainder.

**The instrument measures itself.** Every measurement of a fast thing is partly
a measurement of the clock around it, and the only way to know whether that
matters is to calibrate: `enable()` times a few thousand empty stages, and the
report carries the per-call cost, the number of calls made, and what those
multiply to as a share of the run. If that share is not small, the profile is
saying more about this module than about the generator.

Off, `stage()` returns a shared object whose `__enter__`/`__exit__` do nothing
-- about a hundred nanoseconds, and no allocation. That matters because the
instrumentation lives in the real code path: the generator must not get slower,
or produce a different pixel, because a profiler exists.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

# Set to a path by a driver that wants its child renderers profiled too. The
# child writes its report there and the driver merges it in; see
# `tools/profile_pipeline.py`.
ENV = "VLM_PROFILE"

_on = False
_stack: list["_Stage"] = []
_totals: dict[str, dict] = {}
_calls = 0
_per_call = 0.0
_started: float | None = None
_clock = time.perf_counter


class _Off:
    """What `stage()` gives back when profiling is off. Costs an attribute
    lookup and two method calls; allocates nothing."""

    __slots__ = ()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


_OFF = _Off()


class _Stage:
    __slots__ = ("name", "start", "children")

    def __init__(self, name: str):
        self.name = name
        self.start = 0.0
        self.children = 0.0

    def __enter__(self):
        global _calls
        _calls += 1
        _stack.append(self)
        self.start = _clock()
        return self

    def __exit__(self, *exc):
        inclusive = _clock() - self.start
        _stack.pop()
        if _stack:
            _stack[-1].children += inclusive
        entry = _totals.get(self.name)
        if entry is None:
            entry = _totals[self.name] = {"calls": 0, "inclusive": 0.0, "exclusive": 0.0}
        entry["calls"] += 1
        entry["inclusive"] += inclusive
        entry["exclusive"] += inclusive - self.children
        return False


def stage(name: str):
    """Time the block, under `name`, nested under whatever is already open.

    The recorded name is the full path -- `degradation/gradient_domain` when a
    model is timed inside the degradation stage -- so the tree is recoverable
    from a flat table and a reader can see which sub-stage belongs to which.
    """
    if not _on:
        return _OFF
    return _Stage(f"{_stack[-1].name}/{name}" if _stack else name)


def enabled() -> bool:
    return _on


def enable(calibrate: bool = True) -> None:
    """Start measuring. Idempotent; resets what was collected before."""
    global _on, _calls, _per_call, _started
    _stack.clear()
    _totals.clear()
    _calls = 0
    _on = True
    _per_call = _calibrate() if calibrate else 0.0
    # After calibration, so the calibration loop's own stages are not counted
    # against the run.
    _totals.clear()
    _calls = 0
    _started = _clock()


def disable() -> None:
    global _on
    _on = False


def enable_from_env() -> Path | None:
    """Turn on if a parent process asked for it, and say where to write.

    A renderer runs as a subprocess of the worker, so the switch has to survive
    a process boundary; an environment variable is the only channel that costs
    the caller nothing when it is not set.
    """
    target = os.environ.get(ENV, "")
    if not target:
        return None
    enable()
    return Path(target)


def _calibrate(rounds: int = 4000) -> float:
    """Seconds one `with stage(...)` pair costs, net of the loop around it."""
    start = _clock()
    for _ in range(rounds):
        with stage("_calibration"):
            pass
    measured = _clock() - start

    start = _clock()
    for _ in range(rounds):
        with _OFF:
            pass
    empty = _clock() - start
    return max((measured - empty) / rounds, 0.0)


def report(wall: float | None = None) -> dict:
    """What was measured, plus what was not.

    `wall` overrides the internal clock for callers who know the real span --
    a driver timing a subprocess knows the interpreter start-up the child could
    not see. Without it the span is from `enable()` to now.
    """
    span = wall if wall is not None else (_clock() - _started if _started else 0.0)
    stages = {
        name: {"calls": entry["calls"],
               "inclusive": round(entry["inclusive"], 6),
               "exclusive": round(entry["exclusive"], 6)}
        for name, entry in sorted(_totals.items())
    }
    attributed = sum(entry["exclusive"] for entry in _totals.values())
    overhead = _calls * _per_call
    return {
        "wall": round(span, 6),
        "stages": stages,
        # The number that says whether the rest of the report may be read as a
        # breakdown of the run rather than of part of it.
        "unattributed": round(span - attributed, 6),
        "unattributed_share": round((span - attributed) / span, 6) if span > 0 else 0.0,
        "overhead": {
            "calls": _calls,
            "per_call": _per_call,
            # Nanoseconds, so rounded finer than the stage times: this number
            # is small by construction, and rounding it to microseconds would
            # turn "the instrument cost 26 us" into "the instrument cost 26 us,
            # give or take 100%".
            "total": round(overhead, 12),
            "share": round(overhead / span, 8) if span > 0 else 0.0,
        },
    }


def dump(path: Path | str, extra: dict | None = None, wall: float | None = None) -> dict:
    out = report(wall)
    if extra:
        out.update(extra)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out


def merge(reports: list[dict]) -> dict:
    """Add up several reports -- one per renderer process, usually."""
    stages: dict[str, dict] = {}
    wall = calls = 0.0
    weighted = 0.0
    for one in reports:
        wall += one.get("wall", 0.0)
        calls += one.get("overhead", {}).get("calls", 0)
        weighted += (one.get("overhead", {}).get("per_call", 0.0)
                     * one.get("overhead", {}).get("calls", 0))
        for name, entry in (one.get("stages") or {}).items():
            into = stages.setdefault(name, {"calls": 0, "inclusive": 0.0, "exclusive": 0.0})
            into["calls"] += entry["calls"]
            into["inclusive"] = round(into["inclusive"] + entry["inclusive"], 6)
            into["exclusive"] = round(into["exclusive"] + entry["exclusive"], 6)
    attributed = sum(entry["exclusive"] for entry in stages.values())
    return {
        "wall": round(wall, 6),
        "stages": dict(sorted(stages.items())),
        "unattributed": round(wall - attributed, 6),
        "unattributed_share": round((wall - attributed) / wall, 6) if wall > 0 else 0.0,
        "overhead": {"calls": int(calls),
                     "per_call": (weighted / calls) if calls else 0.0,
                     "total": round(weighted, 12),
                     "share": round(weighted / wall, 8) if wall > 0 else 0.0},
    }


def tops(one: dict) -> dict[str, dict]:
    """Only the stages with no parent -- the ones whose inclusive times
    partition the run, and therefore the ones a percentage table is about."""
    return {name: entry for name, entry in (one.get("stages") or {}).items()
            if "/" not in name}


__all__ = ["ENV", "disable", "dump", "enable", "enable_from_env", "enabled",
           "merge", "report", "stage", "tops"]
