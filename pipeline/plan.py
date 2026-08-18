"""Turn a config into shards, deterministically.

    from pipeline.plan import build_plan
    plan = build_plan(config, layouts)

**A shard is a range of images, not a layout.** That is the one structural
decision in W1 and it is easy to get wrong, because the sequential driver cuts
by layout and that works. It works and it costs: a worker that only ever sees
one layout cannot share a browser across the shard, so Chromium starts once per
layout forever. Cutting by range lets a later wave hand a worker one browser and
a list of pages. The price of the layout cut does not show up now -- it shows up
two waves later, when it is expensive to undo.

**Seeds are assigned exactly as the sequential driver assigned them.** W1 is a
change of scheduling and nothing else, so every image keeps the seed, the layout
and the output name it had before. That is what makes the golden baseline a
usable check rather than a formality.

The arithmetic is `seed + backend_index * 100000 + layout_index * 1000 + k`,
inherited. It is not obviously collision-free -- 100 images of one layout would
run into the next layout's block -- so `disjoint_seeds()` computes the ranges
and says so, and `build_plan` refuses to emit a plan whose blocks overlap.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

# Inherited from tools/generate_dataset.py, deliberately unchanged: altering
# either would change every seed and therefore every pixel.
BACKEND_STRIDE = 100_000
LAYOUT_STRIDE = 1_000


@dataclass(frozen=True)
class Run:
    """One invocation of a renderer: consecutive seeds, one layout."""

    layout: str
    seed: int          # the first seed; the renderer walks seed..seed+count-1
    count: int
    first_index: int   # position of the first image in the backend's numbering


@dataclass
class Shard:
    index: int
    backend: str
    runs: list[Run] = field(default_factory=list)

    @property
    def count(self) -> int:
        return sum(run.count for run in self.runs)

    @property
    def name(self) -> str:
        return f"shard-{self.index:04d}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "backend": self.backend,
            "count": self.count,
            "runs": [asdict(run) for run in self.runs],
        }


def split_by_layout(count: int, layouts: list[str]) -> list[tuple[str, int]]:
    """(layout, quota), as evenly as the layouts allow.

    Lifted from `tools/generate_dataset.py::plan` on purpose: it already
    distributes the remainder the way the committed datasets were built, and
    re-deriving it would silently renumber everything.
    """
    base, extra = divmod(count, len(layouts))
    return [(layout, base + (1 if index < extra else 0))
            for index, layout in enumerate(layouts)]


def backend_runs(backend_index: int, per_backend: int, seed: int,
                 layouts: list[str]) -> list[Run]:
    """Every render invocation for one backend, in output order."""
    base = seed + backend_index * BACKEND_STRIDE
    runs: list[Run] = []
    offset = 0        # counts only layouts that got a quota, as the driver does
    produced = 0
    for layout, quota in split_by_layout(per_backend, layouts):
        if quota == 0:
            continue
        runs.append(Run(layout=layout, seed=base + offset * LAYOUT_STRIDE,
                        count=quota, first_index=produced))
        produced += quota
        offset += 1
    return runs


def disjoint_seeds(runs_by_backend: dict[str, list[Run]]) -> list[str]:
    """Report any two runs whose seed ranges overlap.

    A renderer walks `seed .. seed + count - 1`, so a layout with more images
    than `LAYOUT_STRIDE` runs into the next layout's block and two images come
    out identical -- with different file names, which is the reason nobody would
    notice. Checked rather than reasoned about, because the stride is inherited
    and the counts are not.
    """
    spans: list[tuple[int, int, str]] = []
    for backend, runs in runs_by_backend.items():
        for run in runs:
            spans.append((run.seed, run.seed + run.count - 1,
                          f"{backend}/{run.layout}"))
    spans.sort()
    problems = []
    for (a_lo, a_hi, a_name), (b_lo, b_hi, b_name) in zip(spans, spans[1:]):
        if b_lo <= a_hi:
            problems.append(
                f"seed ranges overlap: {a_name} covers {a_lo}..{a_hi} and "
                f"{b_name} starts at {b_lo}"
            )
    return problems


def shard_runs(runs: list[Run], backend: str, size: int,
               start_index: int) -> list[Shard]:
    """Cut a backend's runs into shards of `size` images, splitting runs freely.

    A run is split across shards when it has to be. That is what allows a shard
    to hold the tail of one layout and the head of the next, which is the whole
    point of not cutting by layout.
    """
    shards: list[Shard] = []
    current = Shard(index=start_index + len(shards), backend=backend)
    room = size
    for run in runs:
        taken = 0
        while taken < run.count:
            take = min(room, run.count - taken)
            current.runs.append(Run(
                layout=run.layout,
                seed=run.seed + taken,
                count=take,
                first_index=run.first_index + taken,
            ))
            taken += take
            room -= take
            if room == 0:
                shards.append(current)
                current = Shard(index=start_index + len(shards), backend=backend)
                room = size
    if current.runs:
        shards.append(current)
    return shards


def build_plan(config, layouts: list[str]) -> dict[str, Any]:
    """The full plan: shards, seeds, names. No absolute paths anywhere.

    `plan.json` is what reproduces a dataset on another machine, so a path from
    this one has no business in it. The output directory lives in the config and
    is supplied at run time.
    """
    runs_by_backend: dict[str, list[Run]] = {}
    for backend_index, backend in enumerate(config.backends):
        runs_by_backend[backend] = backend_runs(
            backend_index, config.per_backend, config.seed, layouts)

    overlaps = disjoint_seeds(runs_by_backend)
    if overlaps:
        raise ValueError(
            "the plan would render duplicate images:\n  " + "\n  ".join(overlaps)
            + f"\n(per_backend={config.per_backend} exceeds the {LAYOUT_STRIDE}-seed "
            "block each layout gets)"
        )

    shards: list[Shard] = []
    for backend in config.backends:
        shards += shard_runs(runs_by_backend[backend], backend,
                             config.shard_size, len(shards))

    return {
        "seed": config.seed,
        "per_backend": config.per_backend,
        "backends": list(config.backends),
        "layouts": list(layouts),
        "shard_size": config.shard_size,
        "clean": config.clean,
        "force": list(config.force),
        "overrides": dict(config.overrides),
        "shards": [shard.to_dict() for shard in shards],
    }


def write_plan(plan: dict[str, Any], path: Path) -> Path:
    """Stable bytes: same config, same file, so two runs can be compared."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8")
    return path


def image_name(backend: str, index: int) -> str:
    """The output file name, matching what the sequential driver produced."""
    return f"{backend}_{index:03d}.jpg"


__all__ = [
    "BACKEND_STRIDE",
    "LAYOUT_STRIDE",
    "Run",
    "Shard",
    "backend_runs",
    "build_plan",
    "disjoint_seeds",
    "image_name",
    "shard_runs",
    "split_by_layout",
    "write_plan",
]
