"""How long each image took, written beside it and read back by the worker.

    from pipeline.imagetimes import Log, read
    with Log(out) as clock:
        with clock.time("html_000.jpg", layout="market_vat"):
            ...draw it...

**Why this is a file of its own rather than a field in `synthesis.json`.**

`tools/baseline.py` fingerprints every image, every record and the
`synthesis.json` beside them, and says in its own docstring what happens if a
duration ever gets into one of those:

    If a path or a timestamp ever enters a record this verification starts
    failing on every machine, which is the correct outcome: both belong in
    `timings.json`, not in a label.

A duration is not reproducible -- that is the whole point of measuring it -- so
putting it where a reproducibility check reads would break the check on every
machine forever. `synthesis.json` stays the per-image *config*: which layout,
which ten attributes, which tags, and it is byte-identical between a one-worker
run and an eight-worker one. This file is the per-image *cost*, and nothing
compares it between runs.

## The shape

One JSON object per line, so a renderer that dies halfway leaves a readable
file of what it did manage rather than a truncated array:

    {"file": "html_000.jpg", "layout": "market_vat", "seconds": 1.412,
     "stages": {"render": 1.02, "geometry": 0.21, "degradation": 0.14}}

`stages` is whatever `profiling` was recording, and is absent when profiling
was off -- which it is by default, because it costs a stopwatch per stage per
image. The total is always there; it is one `time.monotonic()` either side.

## Names

The renderer writes its own names (`html_000.jpg` as the renderer numbered it);
the worker renames pages into the dataset's numbering as it moves them and
re-keys these at the same time. That is why `read` returns a plain dict rather
than something clever: the caller has to be able to rewrite the keys.
"""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

NAME = "imagetimes.jsonl"


def beside(directory: Path | str) -> Path:
    return Path(directory) / NAME


@dataclass
class Entry:
    file: str
    layout: str = ""
    seconds: float = 0.0
    stages: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        out = {"file": self.file, "layout": self.layout,
               "seconds": round(self.seconds, 4)}
        if self.stages:
            out["stages"] = {k: round(v, 4) for k, v in sorted(self.stages.items())}
        return out


class Log:
    """Append-as-you-go, so a killed run still says what it drew."""

    def __init__(self, directory: Path | str):
        self.path = beside(directory)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self.path, "w", encoding="utf-8")
        self.count = 0

    def __enter__(self) -> "Log":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if not self._handle.closed:
            self._handle.close()

    def add(self, entry: Entry) -> None:
        self._handle.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
        self._handle.flush()
        self.count += 1

    @contextmanager
    def time(self, file: str, layout: str = ""):
        """Time one image, yielding the `Entry` for the caller to fill in.

        The entry rather than a bare dict, because the two things a caller
        wants to add are learned at different moments: a stage as it finishes,
        and the LAYOUT only once the recipe has been drawn -- a job that pins
        no layout does not know which one it is until the sampler has spoken.

        Written in a `finally`, so an image that raises still leaves the time
        it burned and the name it was going to have. A row missing from this
        file would make the slow page invisible in exactly the case where
        somebody is looking for it.
        """
        entry = Entry(file=file, layout=layout)
        started = time.monotonic()
        try:
            yield entry
        finally:
            entry.seconds = time.monotonic() - started
            self.add(entry)


def read(directory: Path | str) -> dict[str, Entry]:
    """`{filename: Entry}`. Missing file is an empty dict, not an error.

    A renderer that predates this, or one run with it switched off, simply has
    no per-image times -- and a run report that says "no per-image timing" is a
    better outcome than one that refuses to be written.
    """
    path = beside(directory)
    if not path.exists():
        return {}
    out: dict[str, Entry] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            body = json.loads(line)
        except ValueError:
            continue          # a torn last line from a killed process
        name = str(body.get("file") or "")
        if not name:
            continue
        out[name] = Entry(file=name, layout=str(body.get("layout") or ""),
                          seconds=float(body.get("seconds") or 0.0),
                          stages={k: float(v) for k, v
                                  in (body.get("stages") or {}).items()})
    return out


def summarise(entries) -> dict:
    """Totals, and the per-layout breakdown that says where the time went.

    Per layout rather than per image, because a run is thousands of images and
    a dozen layouts: "which kind of page is slow" is answerable and "which of
    these 4,000 images was slowest" is not, beyond naming the one.
    """
    entries = list(entries)
    if not entries:
        return {"images": 0}
    times = sorted(entry.seconds for entry in entries)
    by_layout: dict[str, list[float]] = {}
    for entry in entries:
        by_layout.setdefault(entry.layout or "?", []).append(entry.seconds)
    stages: dict[str, float] = {}
    for entry in entries:
        for name, value in entry.stages.items():
            stages[name] = stages.get(name, 0.0) + value
    slowest = max(entries, key=lambda e: e.seconds)
    out = {
        "images": len(entries),
        "seconds_total": round(sum(times), 3),
        "seconds_mean": round(sum(times) / len(times), 3),
        "seconds_median": round(times[len(times) // 2], 3),
        # p95 rather than max alone: one slow page is noise, and the shoulder
        # is what a shard-size decision is actually made against.
        "seconds_p95": round(times[min(int(len(times) * 0.95), len(times) - 1)], 3),
        "slowest": {"file": slowest.file, "layout": slowest.layout,
                    "seconds": round(slowest.seconds, 3)},
        "by_layout": {
            layout: {"images": len(values),
                     "seconds_total": round(sum(values), 3),
                     "seconds_mean": round(sum(values) / len(values), 3)}
            for layout, values in sorted(by_layout.items())
        },
    }
    if stages:
        out["seconds_by_stage"] = {k: round(v, 3) for k, v in sorted(stages.items())}
    return out


__all__ = ["NAME", "Entry", "Log", "beside", "read", "summarise"]
