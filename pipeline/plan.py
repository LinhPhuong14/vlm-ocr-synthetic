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

**The layouts are dealt, not blocked.** A run used to draw its quota of one
layout, then the next layout's quota: every neighbour in the output shared a
layout, and a set read in file order -- by a loader without shuffling, by a
contact sheet, by a person opening the directory -- showed one document kind at
a time. `deal` hands them out like cards instead, so image *i* and image *i+1*
carry different layouts (`adjacent_repeats` checks it, and `build_plan` refuses
a plan where it does not hold). Seeds are untouched by this: the k-th image of a
layout is still the k-th seed of that layout's block, so the deal changes the
ORDER pages come out in and not one page's content.

**Whether the backends share their seeds is declared, not implied.** The
arithmetic is `seed + backend_offset + layout_index * 1000 + k`, and
`backend_offset` is what `run.pairing` decides:

    paired        0                                  (the default)
    independent   backend_index * BACKEND_STRIDE

W1 inherited the strided form unconditionally, from the sequential driver, and
kept it deliberately -- W1 changed scheduling and nothing else, which is what
made the golden baseline a usable check. But the consequence was that the three
renderers were never drawing the same receipts. They shared no seed at all, so
the three sets of pages differed in their *content*, and every side-by-side
number in the proof reports -- `money_total` at 144, 141 and 149 -- was
comparing three different corpora and reading the difference as a property of
the renderers. `README.md` says the opposite is the point of the repository.

`independent` keeps the old behaviour for the case it is actually good for:
three backends over disjoint seeds give three times the distinct pages, which
is what a volume run wants and a comparison run must not have. Because the two
modes produce datasets that look identical from outside, the mode is written
into `manifest.json`; a dataset that cannot say which one it is cannot be
interpreted.

The stride is not obviously collision-free -- 1001 images of one layout would
run into the next layout's block -- so `disjoint_seeds()` computes the ranges
and says so, and `build_plan` refuses to emit a plan whose blocks overlap.
Under `paired` the backends overlap *by design*, so the check is applied per
backend rather than across them; overlapping there would still be the bug it
always was.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any

# Inherited from tools/generate_dataset.py. `BACKEND_STRIDE` is only applied
# under `pairing: independent` since W1b -- see the module docstring -- but it
# is kept rather than deleted because that mode still needs it.
BACKEND_STRIDE = 100_000
LAYOUT_STRIDE = 1_000


@dataclass(frozen=True)
class Run:
    """One invocation of a renderer: consecutive seeds, one layout.

    `force` pins attributes for this run alone, on top of whatever the whole
    job pins. Empty for a plan built the ordinary way -- the quota decides the
    layout and the sampler decides the rest. An agent-planned run sets all of
    them and takes `count: 1`, which is how "the model chose this page" is
    said in the vocabulary the renderers already read (`worklist.Job.force`).
    """

    layout: str
    seed: int          # the first seed; the renderer walks seed..seed+count-1
    count: int
    first_index: int   # position of the first image in the backend's numbering
    force: dict[str, str] = field(default_factory=dict)


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

    A quota of zero is arithmetic, not policy, and it is left in the result so
    `uncovered` below can name exactly which layouts got nothing. `build_plan`
    is what refuses the run.
    """
    base, extra = divmod(count, len(layouts))
    return [(layout, base + (1 if index < extra else 0))
            for index, layout in enumerate(layouts)]


def deal(count: int, layouts: list[str]) -> list[tuple[str, int]]:
    """`count` images as (layout, which image of that layout), dealt round-robin.

    The output ORDER of a run, and the reason this is not `split_by_layout`:
    that one hands out quotas, and the plan used to draw them in blocks --
    twenty images of `market_vat`, then twenty of `pub_eatery`. A dataset built
    that way has every neighbour sharing a layout, so any consumer that reads it
    in file order (a training loader without shuffling, a contact sheet, a
    person paging through a directory) sees one document kind at a time.

    Dealt like cards instead: one image of each layout, then one of each again,
    until the quotas run out. Two consequences, both of them the point:

    * **No two adjacent images share a layout**, provided there is more than one
      layout in the run. Inside a round the layouts are distinct by
      construction; across a round boundary the last layout is the end of the
      list and the next is the front of it. `adjacent_repeats` below checks it
      rather than trusting this paragraph.
    * **The k-th image of a layout is still the k-th seed of its block.** The
      second element of each pair is that `k`, so interleaving changes the
      ORDER pages come out in and not a single page's content. A layout whose
      seeds moved would make every committed dataset unreproducible.

    `split_by_layout` still decides the quotas: it distributes the remainder to
    the front of the list, which is what the committed sets were built with.
    """
    quotas = split_by_layout(count, layouts)
    order: list[tuple[str, int]] = []
    for round_index in range(max((quota for _layout, quota in quotas), default=0)):
        for layout, quota in quotas:
            if round_index < quota:
                order.append((layout, round_index))
    return order


def adjacent_repeats(sequence: list[str]) -> list[int]:
    """Positions where an image has the same layout as the image before it.

    Empty is the healthy answer for any run with more than one layout. A run
    pinned to a single layout repeats at every position and that is not a
    fault -- `build_plan` asks for this only when there is a choice to be made.
    """
    return [index for index in range(1, len(sequence))
            if sequence[index] == sequence[index - 1]]


def uncovered(count: int, layouts: list[str]) -> list[str]:
    """The layouts this run would draw ZERO images of.

    The split walks the list in order and hands the remainder to the front, so
    `per_backend` below the layout count does not spread thin -- it drops the
    tail of the list entirely, and says nothing. Seventeen layouts at
    `per_backend: 10` draws ten of them and no more; the other seven are absent
    from the dataset while `dataset.json` still lists them under `layouts`,
    because that field records what the run was pointed at rather than what
    came out.

    Which is the failure this exists to stop: a set that claims a spread it
    does not have is worse than a run that refuses to start.
    """
    return [layout for layout, quota in split_by_layout(count, layouts)
            if quota == 0]


def backend_offset(backend_index: int, pairing: str) -> int:
    """How far this backend's seed block sits from the run's base seed.

    Zero under `paired`, which is what makes all three backends draw the same
    receipts. Named rather than inlined so the one place the modes differ is
    the one place to read.
    """
    if pairing == "paired":
        return 0
    if pairing == "independent":
        return backend_index * BACKEND_STRIDE
    raise ValueError(f"unknown pairing {pairing!r}; have paired, independent")


def backend_runs(backend_index: int, per_backend: int, seed: int,
                 layouts: list[str], pairing: str = "paired") -> list[Run]:
    """Every render invocation for one backend, in output order.

    One `Run` per image rather than one per layout, because the images of a
    layout are no longer consecutive -- see `deal`. A run is "consecutive seeds,
    one layout", and dealt pages are a run of one.

    That is a hundred jobs in a hundred-image shard instead of a dozen, and it
    costs nothing that matters: a shard has been ONE renderer process since W3b
    whatever its job count (`pipeline/worker.py`), and the jobs travel as a
    list. What used to be expensive was a process per job, not a job.
    """
    base = seed + backend_offset(backend_index, pairing)
    # Each layout keeps its own thousand-seed block, indexed by its position
    # among the layouts that got a quota -- exactly as before the deal, so a
    # page drawn at position 7 of the old plan is the same page here.
    blocks: dict[str, int] = {}
    for layout, quota in split_by_layout(per_backend, layouts):
        if quota:
            blocks[layout] = base + len(blocks) * LAYOUT_STRIDE
    return [Run(layout=layout, seed=blocks[layout] + which, count=1,
                first_index=index)
            for index, (layout, which) in enumerate(deal(per_backend, layouts))]


def disjoint_seeds(runs_by_backend: dict[str, list[Run]],
                   pairing: str = "paired") -> list[str]:
    """Report any two runs whose seed ranges overlap.

    A renderer walks `seed .. seed + count - 1`, so a layout with more images
    than `LAYOUT_STRIDE` runs into the next layout's block and two images come
    out identical -- with different file names, which is the reason nobody would
    notice. Checked rather than reasoned about, because the stride is inherited
    and the counts are not.

    Under `paired` the backends deliberately cover the same seeds, so they are
    checked one at a time; an overlap *within* a backend is the bug it always
    was. Under `independent` the blocks are supposed to be disjoint across
    backends too, so everything is checked together.
    """
    if pairing == "paired":
        groups = [{backend: runs} for backend, runs in sorted(runs_by_backend.items())]
    else:
        groups = [runs_by_backend]

    problems = []
    for group in groups:
        spans: list[tuple[int, int, str]] = []
        for backend, runs in group.items():
            for run in runs:
                spans.append((run.seed, run.seed + run.count - 1,
                              f"{backend}/{run.layout}"))
        spans.sort()
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

    **Every field of the run survives the cut, `force` included.** It did not,
    once: this rebuilt each piece from `layout`, `seed`, `count` and
    `first_index` and dropped the rest, which was invisible while `force` was
    the only other field and was always empty. An agent-planned run puts all
    eight attributes there, and the pages came out drawn from the layout pin
    alone -- correct-looking pages, a plan that described none of them, and
    nothing anywhere that said so. `tests/test_plan.py` now says so.
    """
    shards: list[Shard] = []
    current = Shard(index=start_index + len(shards), backend=backend)
    room = size
    for run in runs:
        taken = 0
        while taken < run.count:
            take = min(room, run.count - taken)
            current.runs.append(replace(
                run,
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


def pinned_layout(force) -> str | None:
    """The layout `--force` pins, if it pins one."""
    for item in force or ():
        name, _, value = str(item).partition("=")
        if name.strip() == "layout" and value.strip():
            return value.strip()
    return None


def build_plan(config, layouts: list[str],
               runs: dict[str, list[Run]] | None = None) -> dict[str, Any]:
    """The full plan: shards, seeds, names. No absolute paths anywhere.

    `plan.json` is what reproduces a dataset on another machine, so a path from
    this one has no business in it. The output directory lives in the config and
    is supplied at run time.

    `runs` hands the plan a list somebody else built -- the agent planner, which
    decides every attribute of every page and so cannot express itself as a
    quota over layouts. Left None, the quota builds them, which is every other
    caller and every committed dataset.
    """
    pairing = getattr(config, "pairing", "paired")

    # `--force layout=X` narrows the plan, it does not ride along beside it.
    #
    # Without this the plan still spreads the run across all fourteen layouts
    # and hands each renderer `--layout Y --force layout=X`. The renderer draws
    # X, because `--force` wins; the worker then stamps `synthesis.layout = Y`
    # from the plan. The image is X and the label says Y -- and the invariants,
    # which read the layout to know what that layout is allowed to suppress,
    # then judge X's page against Y's rules and fail on a correct run.
    pinned = pinned_layout(getattr(config, "force", ()))
    if pinned is not None:
        if pinned not in layouts:
            raise ValueError(
                f"--force layout={pinned!r}: no such layout; "
                f"have {', '.join(sorted(layouts))}"
            )
        layouts = [pinned]

    # `per_backend: auto` is "one image of every layout, whatever the layout
    # count is today". Resolved HERE rather than in the config, because this is
    # the first place that knows how many layouts the run has -- and resolved
    # into `plan.json`, so the number a dataset was built with is recorded even
    # though the config that asked for it says a word.
    per_backend = config.per_backend or len(layouts)

    # Every layout in the run draws at least one page, or the run does not
    # start. See `uncovered`: the alternative is a dataset silently missing the
    # tail of the layout list while its manifest still names them.
    missing = uncovered(per_backend, layouts)
    if missing:
        raise ValueError(
            f"per_backend={per_backend} cannot cover {len(layouts)} layouts: "
            f"{', '.join(missing)} would get no images at all.\n"
            f"Raise run.per_backend to at least {len(layouts)} per backend, set it "
            "to `auto`, or name a shorter run.layouts."
        )

    runs_by_backend: dict[str, list[Run]] = {}
    if runs is not None:
        missing = [b for b in config.backends if b not in runs]
        if missing:
            raise ValueError(f"prepared runs are missing backend(s) {missing}")
        runs_by_backend = {backend: list(runs[backend]) for backend in config.backends}
        # No deal check on a prepared list. `deal` interleaves the layouts so no
        # two neighbours share one, which is the right shape for a quota split
        # over layouts and the wrong one to impose on a caller that decided the
        # order itself: `agent/planner.py` orders by a coverage objective, and
        # forcing neighbours apart would fight it for no gain -- the property
        # that matters there is what the whole run covers, not what sits beside
        # what. Every other guarantee below still applies to these runs.
    else:
        for backend_index, backend in enumerate(config.backends):
            runs_by_backend[backend] = backend_runs(
                backend_index, per_backend, config.seed, layouts, pairing)

        # The deal is meant to put a different layout beside every image. Checked
        # rather than trusted: `deal` is twelve lines and the property is one
        # `split_by_layout` change away from quietly not holding, and "quietly" is
        # the operative word -- a run whose neighbours pair up produces a dataset
        # that looks exactly like a correct one until somebody opens the directory.
        for backend, runs_of in sorted(runs_by_backend.items()):
            if len(layouts) < 2:
                break                     # one layout: every neighbour is itself
            repeats = adjacent_repeats([run.layout for run in runs_of
                                        for _ in range(run.count)])
            if repeats:
                raise ValueError(
                    f"{backend}: images {repeats[:5]} would each carry the same "
                    f"layout as the image before them; the deal in "
                    f"pipeline/plan.py::deal is broken")

    overlaps = disjoint_seeds(runs_by_backend, pairing)
    if overlaps:
        raise ValueError(
            "the plan would render duplicate images:\n  " + "\n  ".join(overlaps)
            + f"\n(per_backend={per_backend} exceeds the {LAYOUT_STRIDE}-seed "
            "block each layout gets)"
        )

    shards: list[Shard] = []
    for backend in config.backends:
        shards += shard_runs(runs_by_backend[backend], backend,
                             config.shard_size, len(shards))

    return {
        "seed": config.seed,
        "pairing": pairing,
        "per_backend": per_backend,
        "backends": list(config.backends),
        "layouts": list(layouts),
        # WHERE that list came from, which the list itself cannot say.
        #
        #   all       every file in rulebase/layouts/ at the time of the run
        #   named     run.layouts spelled them out -- a fixed comparison
        #   forced    --force layout=X narrowed it to one
        #
        # `all` is the right answer for a dataset and the wrong one for a fixed
        # comparison: the day someone adds a layout, an `all` run draws a
        # different set and the two plans are not comparable. A reader of
        # `plan.json` can now tell which kind of run they are holding instead
        # of guessing from a list that looks the same either way.
        "layout_source": ("forced" if pinned is not None
                          else "named" if getattr(config, "layouts", ()) else "all"),
        "shard_size": config.shard_size,
        "clean": config.clean,
        "force": list(config.force),
        "template": config.template,
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
    "adjacent_repeats",
    "backend_offset",
    "backend_runs",
    "build_plan",
    "deal",
    "disjoint_seeds",
    "image_name",
    "shard_runs",
    "split_by_layout",
    "uncovered",
    "write_plan",
]
