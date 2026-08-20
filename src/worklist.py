"""What one renderer process is to draw, when that is more than one thing.

    generators/html/.venv/bin/python generators/html/render.py -o out --jobs jobs.json

A renderer used to draw one layout per invocation, because that is the shape a
command line naturally has: `--layout X --seed N --count K`. The worker then
started a process per layout, and since the quota splits twenty images over
fourteen layouts, each process drew about one and a half images and paid the
start-up cost in full for it -- between 23% and 44% of a run, measured in
`docs/where-the-time-goes.md`. That is the largest single cost in the generator
and
it is not in any renderer: it is the shape of the invocation.

A job list is the same fields, repeated:

    [{"layout": "market_vat", "seed": 2026, "count": 2},
     {"layout": "eatery_ascii", "seed": 2028, "count": 1,
      "force": {"augmentation": "pristine"}}]

and the process pays start-up once for all of them. Nothing else changes --
each page is still drawn from its own seed, so the *n*th page of a job is the
page that seed has always produced whether it was drawn alone or in a list of
a hundred. That is a claim about output, and it is checked as one: the
byte-for-byte comparison in `tests/test_worklist.py` and, at run scale,
`make baseline-verify` plus the workers 1-versus-8 comparison.

`force` is per job so a list can mix pins the way a plan can -- it is merged
over whatever `--force` the command line gave, and the job wins, because the
narrower statement should.

`--layout/--seed/--count` keep working exactly as before. Two ways in is worth
it here: scripts and tests use the old one, and a flag that quietly changed
meaning would be worse than a second flag.

Unknown keys are rejected rather than ignored, like everywhere else in this
repository: a job with `"layouts"` in it that renders anyway, on the default,
is the silent failure that costs a day.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

FIELDS = {"layout", "seed", "count", "force"}


class JobError(ValueError):
    """This job list does not describe work anything can do."""


@dataclass(frozen=True)
class Job:
    """One layout, `count` pages, starting at `seed`.

    `layout` may be None, which means the sampler picks -- the single-image
    case a person gets from `render.py -c 10` with no `--layout`. A list
    written by the worker always names one, because a plan always does.

    `force` is a tuple of pairs rather than a dict so a Job stays hashable and
    can key a cache: `parse_force` reads the rules to validate a pin, and a
    list of a hundred pages holds a handful of distinct pins.
    """

    layout: str | None
    seed: int
    count: int
    force: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.count < 1:
            raise JobError(f"count must be at least 1, got {self.count}")
        if not isinstance(self.seed, int) or isinstance(self.seed, bool):
            raise JobError(f"seed must be an integer, got {self.seed!r}")
        if self.layout is not None and not str(self.layout).strip():
            raise JobError("layout must be a name or absent, not an empty string")

    def pins(self, extra: list[str] | None = None) -> list[str]:
        """`--force`-shaped strings: the command line's, then this job's.

        The job comes second so it wins the merge in `rulebase.parse_force`.
        """
        return list(extra or []) + [f"{name}={value}" for name, value in self.force]


def add_argument(parser) -> None:
    """The flag, spelled the same way by all three renderers."""
    parser.add_argument(
        "--jobs", type=Path, metavar="JSON",
        help="draw several layouts in this one process: a JSON list of "
             "{layout, seed, count, force}. Overrides --layout/--seed/--count. "
             "The point is to pay interpreter and backend start-up once "
             "instead of once per layout; see worklist.py",
    )


def parse(raw) -> list[Job]:
    if not isinstance(raw, list):
        raise JobError(f"a job list is a list, got {type(raw).__name__}")
    if not raw:
        raise JobError("a job list with nothing in it draws nothing; omit --jobs instead")
    jobs = []
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise JobError(f"job {index}: expected an object, got {type(entry).__name__}")
        unknown = set(entry) - FIELDS
        if unknown:
            raise JobError(f"job {index}: unknown keys {sorted(unknown)}; "
                           f"a job has {sorted(FIELDS)}")
        missing = {"seed", "count"} - set(entry)
        if missing:
            raise JobError(f"job {index}: missing {sorted(missing)}")
        pins = entry.get("force") or {}
        if not isinstance(pins, dict):
            raise JobError(f"job {index}: force is a mapping of attribute to "
                           f"value, got {type(pins).__name__}")
        jobs.append(Job(layout=entry.get("layout"), seed=entry["seed"],
                        count=entry["count"],
                        force=tuple(sorted((str(k), str(v)) for k, v in pins.items()))))
    return jobs


def read(path: Path | str) -> list[Job]:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise JobError(f"{path}: not valid JSON ({error})") from error
    return parse(raw)


def write(path: Path | str, jobs: list[Job]) -> Path:
    path = Path(path)
    out = []
    for job in jobs:
        entry = {"layout": job.layout, "seed": job.seed, "count": job.count}
        if job.force:
            entry["force"] = dict(job.force)
        out.append(entry)
    path.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    return path


def load(args) -> list[Job]:
    """The jobs this invocation asks for, list or not.

    One function so the three renderers cannot disagree about what `--jobs`
    together with `--layout` means. It means the list: a flag that silently
    lost to another flag is worse than one that is documented to win.
    """
    if getattr(args, "jobs", None):
        return read(args.jobs)
    return [Job(layout=getattr(args, "layout", None), seed=args.seed, count=args.count)]


def total(jobs: list[Job]) -> int:
    return sum(job.count for job in jobs)


def pages(jobs: list[Job]) -> Iterator[tuple[int, Job, int]]:
    """`(index, job, seed)` for every page, in order.

    The index counts across the whole batch, so the files a process writes are
    numbered without collision; the seed counts within a job, so a page is the
    page its seed has always been.
    """
    index = 0
    for job in jobs:
        for offset in range(job.count):
            yield index, job, job.seed + offset
            index += 1


__all__ = ["Job", "JobError", "add_argument", "load", "pages", "parse", "read",
           "total", "write"]
