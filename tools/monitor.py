"""Look at the rule space, or at a run while it is still going.

    python tools/monitor.py --static            # the whole space, no run needed
    python tools/monitor.py data/run01          # one look at a run
    python tools/monitor.py data/run01 --watch  # keep looking

**Static** answers "what can this rule-base produce": every attribute, its
values, their weights and tags, the layouts and degradation chains they name,
and what two thousand draws actually come out as -- which is not the same
question, because a weight is relative to the candidates still standing after
filtering. The simulated numbers are the same draws `make distribution` makes,
from the same seed, so the two never disagree.

**Dynamic** answers "how is this run going", and it has to answer it *during*
the run. `manifest.json` is written once, at the end; a job that has been going
for forty minutes and has forty to go is exactly when somebody wants to look, so
everything here is read from `.shards/shard-NNNN/` -- the `DONE` files, the
metadata each worker streams as it goes, and the quality vectors.

The part that is easy to get wrong
----------------------------------

A shard with no `DONE` is **not** a shard that has lost images. The worker's
contract is all-or-nothing: on restart it deletes whatever is there and renders
from the start, precisely so that a half-written shard can never be mistaken for
a complete one. So between two looks a shard's image count can go *down* -- W1
saw 7 then 5 -- and that is the contract working, not data disappearing.

A monitor that reports "2 images lost" every time somebody resumes a job gets
switched off in a week, and a monitor that is switched off is worth exactly
nothing. So a shard without `DONE` is never reported as a count at all: it is
reported as progress, and when `--watch` sees the count fall it says the shard
restarted, because that is what happened.

Nothing here writes anything. It is safe to run against a directory a pool of
workers is actively writing to, and it leaves no trace behind.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

from rules_report import check, sample_distribution  # noqa: E402

from rulebase import ATTRIBUTES, available_layouts, load_rules  # noqa: E402

# The same numbers `make distribution` prints. Fixed so the two cannot drift
# apart into two different answers to one question.
STATIC_DRAWS = 2000
STATIC_SEED = 0

SHARDS_DIR = ".shards"
DONE = "DONE"


# ------------------------------------------------------------------ static


def static_report(draws: int = STATIC_DRAWS, seed: int = STATIC_SEED) -> int:
    """Everything the rules allow, and what they actually produce."""
    rules = load_rules()
    print(f"RULE SPACE -- {len(rules)} attributes\n")

    for attribute in ATTRIBUTES:
        options = rules[attribute]
        total = sum(option.weight for option in options) or 1.0
        print(f"[{attribute}]  {len(options)} values")
        for option in sorted(options, key=lambda o: (-o.weight, o.id)):
            share = option.weight / total
            marks = []
            if option.tags:
                marks.append("sets " + ",".join(sorted(option.tags)))
            if option.requires:
                marks.append("needs " + ",".join(sorted(option.requires)))
            if option.excludes:
                marks.append("not with " + ",".join(sorted(option.excludes)))
            if not option.weight:
                marks.append("WEIGHT 0 -- never drawn")
            print(f"    {option.id:<26} w={option.weight:<5g} {share:>6.1%}"
                  f"   {'; '.join(marks)}")
        print()

    print(f"[layouts]  {', '.join(available_layouts())}\n")

    counters, failures = sample_distribution(draws, seed)
    drawn = draws - failures
    print(f"DRAWN -- {drawn} of {draws} draws, seed {seed}")
    print("(a weight is relative to the candidates left after filtering, so this")
    print(" is not the weight column above)\n")
    for attribute in ATTRIBUTES:
        print(f"[{attribute}]")
        for name, count in counters[attribute].most_common():
            share = count / drawn if drawn else 0
            print(f"    {name:<26} {count:>5}  {share:>6.1%} {'#' * int(share * 40)}")
        never = sorted({option.id for option in rules[attribute]}
                       - set(counters[attribute]))
        for name in never:
            print(f"    {name:<26} {0:>5}  {0:>6.1%}  <- never came up in {draws} draws")
        print()

    problems = check()
    if problems:
        print("PROBLEMS")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("no problems in the rules")
    return 0


# ----------------------------------------------------------------- dynamic


def scan(out: Path) -> dict:
    """The state of a run, read from disk. Writes nothing, locks nothing.

    Safe to call against a directory workers are writing to: a half-written
    `metadata.jsonl` line is skipped rather than crashing the reader, because
    the alternative is a monitor that falls over exactly when it is needed.
    """
    out = Path(out)
    plan_path = out / "plan.json"
    if not plan_path.exists():
        raise SystemExit(f"no plan.json in {out}; is that a run directory?")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    shards_root = out / SHARDS_DIR

    started = plan_path.stat().st_mtime
    shards = []
    for entry in sorted(plan["shards"], key=lambda s: s["index"]):
        directory = shards_root / f"shard-{entry['index']:04d}"
        done = (directory / DONE).exists()
        images = len(list(directory.glob("*.jpg"))) if directory.exists() else 0
        state = "done" if done else ("working" if directory.exists() else "waiting")
        vector = directory / "drift.json"
        quality = json.loads(vector.read_text(encoding="utf-8")) if vector.exists() else {}
        if directory.exists():
            started = min(started, directory.stat().st_mtime)
        shards.append({
            "index": entry["index"],
            "backend": entry["backend"],
            "planned": entry["count"],
            "images": images,
            "state": state,
            "layouts": sorted({run["layout"] for run in entry["runs"]}),
            "collapsed": quality.get("collapsed_totals"),
            "sources": quality.get("content_sources") or {},
            "unchecked": quality.get("unchecked") or [],
        })

    failures = []
    logs = out / "logs"
    if logs.exists():
        for log in sorted(logs.glob("shard-*.log")):
            for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("FAILED:"):
                    failures.append(f"{log.stem}: {line[len('FAILED:'):].strip()}")

    # A finished run knows exactly how long it took, and it is written down in
    # the one file that is allowed to hold a duration. Guessing from file mtimes
    # would report the time since the run started, which for anything looked at
    # later is not the same number at all -- 57 minutes for a 90-second run, as
    # this first did.
    seconds = None
    timings = out / "timings.json"
    if timings.exists():
        try:
            seconds = float(json.loads(timings.read_text(encoding="utf-8"))["seconds_total"])
        except (ValueError, KeyError, TypeError):
            seconds = None

    return {
        "out": str(out),
        "pairing": plan.get("pairing", "paired"),
        "backends": plan["backends"],
        "per_backend": plan["per_backend"],
        "shards": shards,
        "started": started,
        "finished": (out / "manifest.json").exists(),
        "seconds": seconds,
        "failures": failures,
    }


def observed_mix(out: Path, attribute: str = "augmentation") -> dict[str, int]:
    """What one attribute has actually drawn so far, across finished shards.

    Only finished shards: a shard still being written is a partial sample, and
    counting it would make the mix jump about for reasons that are not the
    generator's.
    """
    counts: dict[str, int] = {}
    plan = json.loads((Path(out) / "plan.json").read_text(encoding="utf-8"))
    backends = sorted({s["backend"] for s in plan["shards"]})

    def completed(backend: str) -> int:
        return sum(1 for entry in plan["shards"] if entry["backend"] == backend
                   and (Path(out) / SHARDS_DIR / f"shard-{entry['index']:04d}"
                        / DONE).exists())

    if plan.get("pairing", "paired") == "paired":
        # One backend, because under `paired` the others drew the same receipts
        # and adding them would multiply one sample by three. The most advanced
        # one, so a mid-run view is not held back by whichever backend is
        # slowest; sorted first on a tie, so it does not flicker.
        counted = [max(backends, key=lambda name: (completed(name), [-ord(c) for c in name]))]
    else:
        counted = backends

    for entry in sorted(plan["shards"], key=lambda s: s["index"]):
        if entry["backend"] not in counted:
            continue
        directory = Path(out) / SHARDS_DIR / f"shard-{entry['index']:04d}"
        vector = directory / "drift.json"
        if not (directory / DONE).exists() or not vector.exists():
            continue
        drawn = json.loads(vector.read_text(encoding="utf-8"))
        for value, count in (drawn.get("attributes") or {}).get(attribute, {}).items():
            counts[value] = counts.get(value, 0) + int(count)
    return counts


def _elapsed(seconds: float) -> str:
    seconds = max(int(seconds), 0)
    if seconds < 90:
        return f"{seconds}s"
    if seconds < 5400:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


def render(state: dict, previous: dict | None = None, *, now: float | None = None) -> str:
    """One screenful. `previous` is the last scan, for spotting a restart."""
    now = time.time() if now is None else now
    lines: list[str] = []
    shards = state["shards"]
    planned = sum(s["planned"] for s in shards)
    done_shards = [s for s in shards if s["state"] == "done"]
    finished_images = sum(s["planned"] for s in done_shards)
    in_flight = sum(s["images"] for s in shards if s["state"] == "working")

    head = "finished" if state["finished"] else "running"
    lines.append(f"{state['out']}  [{head}]  pairing={state['pairing']}  "
                 f"{len(state['backends'])} backends x {state['per_backend']}")
    lines.append("")

    was = {s["index"]: s for s in (previous or {}).get("shards", [])}
    for shard in shards:
        before = was.get(shard["index"])
        note = ""
        if shard["state"] == "done":
            bar = f"{shard['planned']:>5}/{shard['planned']:<5}"
        elif shard["state"] == "working":
            bar = f"{shard['images']:>5}/{shard['planned']:<5}"
            # The one piece of interpretation this tool owes its reader. A count
            # that fell means the worker threw a fragment away and started the
            # shard again, which is the contract, not a loss.
            if before and before["state"] == "working" and shard["images"] < before["images"]:
                note = (f"<- restarted; the {before['images']} images it had were a "
                        f"fragment and were deleted, not lost")
            elif before and before["state"] == "done":
                note = "<- being redone"
        else:
            bar = f"{'':>5}/{shard['planned']:<5}"
        lines.append(f"  shard {shard['index']:>4}  {shard['backend']:<9} "
                     f"{shard['state']:<8} {bar}  {','.join(shard['layouts'])} {note}")

    lines.append("")
    # While the run is going, the clock; once it is over, what it recorded.
    elapsed = state["seconds"] if state["finished"] and state["seconds"] else now - state["started"]
    done_now = finished_images + in_flight
    lines.append(f"  images   {done_now} of {planned}"
                 f"   ({done_now / planned:.0%})" if planned else "  images   0")
    lines.append(f"  elapsed  {_elapsed(elapsed)}"
                 + ("  (from timings.json)" if state["finished"] and state["seconds"] else ""))
    if done_now and elapsed > 0:
        # Every image on disk counts toward the rate, not only the ones inside a
        # finished shard. Counting finished shards alone looks more conservative
        # and is much worse: with nine shards and four workers, an ETA taken at
        # 22% said 1m39s for a run that had 45s left, because most of the work
        # in progress was invisible to it. Images written is the closest thing
        # to a measure of work actually done.
        rate = done_now / elapsed
        remaining = planned - done_now
        lines.append(f"  rate     {rate:.2f} images/s ({1 / rate:.2f} s/image)")
        if remaining > 0:
            lines.append(f"  eta      {_elapsed(remaining / rate)} "
                         f"for the remaining {remaining}")
        else:
            lines.append("  eta      -")
    else:
        lines.append("  rate     -- no shard has finished yet")

    collapsed = sum(s["collapsed"] or 0 for s in shards if s["collapsed"] is not None)
    sources: dict[str, int] = {}
    for shard in shards:
        for value, count in shard["sources"].items():
            sources[value] = sources.get(value, 0) + int(count)
    if sources:
        lines.append("  content  " + ", ".join(
            f"{value} {count}" for value, count in sorted(sources.items())))
    if collapsed:
        lines.append(f"  labels   {collapsed} receipts lost a total line to a "
                     f"duplicate label (known, W4)")

    mix = observed_mix(Path(state["out"]))
    if mix:
        total = sum(mix.values())
        lines.append("")
        lines.append(f"  augmentation drawn so far ({total} draws, "
                     f"{'one backend, they are paired' if state['pairing'] == 'paired' else 'all backends'})")
        for value, count in sorted(mix.items(), key=lambda item: -item[1]):
            lines.append(f"    {value:<24} {count:>5}  {count / total:>6.1%}")

    unchecked = sorted({u for s in shards for u in s["unchecked"]})
    if unchecked:
        lines.append("")
        for message in unchecked:
            lines.append(f"  {message}")
    if state["failures"]:
        lines.append("")
        for failure in state["failures"]:
            lines.append(f"  FAILED {failure}")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("run", nargs="?", type=Path,
                        help="a run directory; omit with --static")
    parser.add_argument("--static", action="store_true",
                        help="report the rule space instead of a run")
    parser.add_argument("--watch", action="store_true", help="keep looking")
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("-n", "--draws", type=int, default=STATIC_DRAWS)
    parser.add_argument("--seed", type=int, default=STATIC_SEED)
    args = parser.parse_args()

    if args.static or not args.run:
        return static_report(args.draws, args.seed)

    previous = None
    while True:
        state = scan(args.run)
        print(render(state, previous))
        if not args.watch or state["finished"]:
            return 1 if state["failures"] else 0
        previous = state
        print()
        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
