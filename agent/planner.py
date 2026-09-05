"""The agent that chooses every attribute of every page, instead of the seed.

    decisions = planner.plan(count=5000, seed=2026, rules=rules, policy=policy)

`rulebase.sample_recipe` draws one page well: weighted, constrained, and
independent of the last page. That independence is exactly what a 5000-image
run cannot afford. Independent draws leave the tail of the space empty -- the
rarest `document x layout x variant` triples are never reached, the commonest
arrive hundreds of times, and the set is narrower than the rules it was drawn
from. The agent's job is to remember what it has already drawn.

Two ways it decides, and both are recorded per page
---------------------------------------------------

`llm`       a server was configured, and answered with ids that were legal.
`coverage`  no server, or the server's pick for that attribute was not legal.

The offline half is not a fallback bolted on: it is the objective the prompt
asks the model for, written out. Score every legal value of an attribute as

    weight / (1 + times already used) ** pressure

and draw from that. At `pressure = 0` it is the shipped sampler exactly; at 1
it is near-uniform coverage; in between it keeps the authored realism -- a
`weight: 8` value stays common -- while pushing the run through the corners of
the space. `pressure` is the one number that says how hard the agent is trying.

Legality is never assumed
-------------------------

Attributes are walked in the rules' own draw order and each is chosen from the
values `Option.allowed()` admits given the tags collected so far -- the same
walk `_draw_once` does. So a plan cannot contain a combination the rules forbid,
whether the value came from the model or from the objective, and
`verify()` re-draws every decision through `sample_recipe` to prove it.

Ornament instead of geometry
----------------------------

A document the policy locks may not be redressed, so its only room to vary is
the ink pressed onto it afterwards. On those pages the agent pushes the
"no ornament" value down hard (`BARE_PENALTY`) -- they come out stamped and
sealed rather than plain, which is where their diversity has to come from.

A page decided is a network round trip, not a coin flip
---------------------------------------------------------

The `coverage` half is instant; the `llm` half is not, and 5000 of them is a
run measured in minutes to hours depending on what is on the other end of
`VLM_LLM_URL`. `plan()` shows a bar for that (`pipeline/progress.py`) and, via
`checkpoint=`, writes what it has decided so far every `block` pages -- so a
run a dropped connection or a killed process cuts short has lost at most one
block of model calls, not every one since the start. `resume=` is the other
half: hand back a `read()` of that checkpoint and the loop picks up where it
left off instead of asking the model again for pages it already answered.
`tools/agent_dataset.py --resume` is the wiring for both.
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from pipeline.progress import Bar
from rulebase.spec import Option, sample_recipe

# How much a locked or livery document's "no ornament at all" value is worth
# relative to the rest. Not zero: a prescribed form genuinely does turn up
# unstamped, and a set where every one of them carries a seal is its own lie.
BARE_PENALTY = 0.18
BARE_ID = "no_ornament"

# Attributes the model is asked for. All of them -- an agent that chose the
# paper but not the ageing would leave the half that matters most to a chance
# it never saw.
DEFAULT_PRESSURE = 0.72

# How many times a page may be redrawn when a walk dead-ends. `sample_recipe`
# uses the same idea for a pin that does not fit; a handful is plenty, because
# the dead ends are a property of a few documents rather than of the draw.
ATTEMPTS = 24


@dataclass
class Decision:
    """One page, as the agent settled it."""

    index: int
    seed: int
    force: dict[str, str]
    by: str = "coverage"
    note: str = ""

    @property
    def layout(self) -> str:
        return self.force["layout"]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Clash(RuntimeError):
    """This walk reached an attribute with nothing left to draw.

    Not a fault in the rules: a document can be legal while every layout it
    admits is switched off, and `sample_recipe` answers that by redrawing the
    whole recipe rather than by failing. So does `decide_one` -- see its retry.
    """


class Chooser:
    """Weighted choice that remembers, over one attribute at a time."""

    def __init__(self, rules: dict[str, list[Option]], order: tuple[str, ...],
                 seed: int, pressure: float = DEFAULT_PRESSURE,
                 penalty: dict[str, dict[str, float]] | None = None,
                 ban: Iterable[tuple[tuple[str, str], tuple[str, str]]] = ()):
        self.rules = rules
        self.order = tuple(order)
        self.rng = random.Random(seed)
        self.pressure = float(pressure)
        self.used: dict[str, dict[str, int]] = {name: {} for name in self.order}
        # What `agent/critic.py` learnt from the last run, if anything: a
        # multiplier per value, and pairs that are only bad together. Empty by
        # default, so a first run behaves exactly as it did before there was a
        # reviewer -- the loop is opt-in and the driver's `--feedback` opens it.
        self.penalty = {a: dict(o) for a, o in (penalty or {}).items()}
        self.ban: dict[tuple[str, str], set[tuple[str, str]]] = {}
        for one, two in ban or ():
            self.ban.setdefault(tuple(one), set()).add(tuple(two))
            self.ban.setdefault(tuple(two), set()).add(tuple(one))

    def legal(self, attribute: str, tags: frozenset[str]) -> list[Option]:
        """Drawable values: allowed by the tags, and not switched off.

        The rules switch a value off two ways and `_draw_once` reads both:
        `weight: 0` is the accidental one and `enabled: false` the deliberate
        one -- `stains`, `crumpled`, `torn_edges` and `punched` are all off that
        way today, because their chains carry `gradient_domain` and `holes`.

        The coverage score divides by usage and floors at a tiny positive
        number, so a chooser that checked neither would pick a switched-off
        value the moment everything else had been used once, which is the
        opposite of off. Checking only `weight` would still have drawn all four
        of those, and drawn holes punched through pages the label says are
        whole.
        """
        return [option for option in self.rules[attribute]
                if option.weight > 0 and option.enabled and option.allowed(tags)]

    def permitted(self, attribute: str, tags: frozenset[str],
                  chosen: Iterable[tuple[str, str]] = ()) -> list[Option]:
        """`legal`, minus values the reviewer banned alongside what is chosen.

        A ban is a pair, never a single value: `layout=form_dense` is a good
        layout and `ornament=qr_dau_trang` is a good mark, and the fault is
        only in the two of them on one page. Dropping either one on its own
        would cost the set a phôi or a mark for no reason.
        """
        options = self.legal(attribute, tags)
        if not self.ban:
            return options
        forbidden: set[tuple[str, str]] = set()
        for pair in chosen:
            forbidden |= self.ban.get(tuple(pair), set())
        if not forbidden:
            return options
        kept = [o for o in options if (attribute, o.id) not in forbidden]
        # Never strand a walk on the reviewer's advice: the bans are a
        # heuristic and the rules are not, so an attribute the bans would empty
        # keeps its legal values and the pair is drawn rather than the run dying.
        return kept or options

    def _score(self, attribute: str, option: Option, bare_penalty: float) -> float:
        used = self.used[attribute].get(option.id, 0)
        score = option.weight / (1.0 + used) ** self.pressure
        if attribute == "ornament" and option.id == BARE_ID:
            score *= bare_penalty
        score *= self.penalty.get(attribute, {}).get(option.id, 1.0)
        return max(score, 1e-9)

    def take(self, attribute: str, tags: frozenset[str],
             bare_penalty: float = 1.0, record: bool = True,
             chosen: Iterable[tuple[str, str]] = ()) -> Option:
        options = self.permitted(attribute, tags, chosen)
        if not options:
            raise Clash(
                f"{attribute}: nothing is drawable under tags {sorted(tags)}")
        weights = [self._score(attribute, option, bare_penalty) for option in options]
        option = self.rng.choices(options, weights=weights, k=1)[0]
        if record:
            self.record(attribute, option.id)
        return option

    def record(self, attribute: str, option_id: str) -> None:
        self.used[attribute][option_id] = self.used[attribute].get(option_id, 0) + 1

    def find(self, attribute: str, option_id: str, tags: frozenset[str]) -> Option | None:
        """The named value, if the rules admit it here. None means 'not legal'."""
        for option in self.legal(attribute, tags):
            if option.id == option_id:
                return option
        return None


def _bare_penalty(policy, document: str) -> float:
    """A locked or livery page has to get its variety from ink, so it gets ink."""
    return 1.0 if policy.klass(document) == "free" else BARE_PENALTY


def decide_one(chooser: Chooser, policy, index: int, seed: int,
               proposal: dict[str, str] | None = None) -> Decision:
    """One page: the model's ids where they are legal, the objective elsewhere."""
    proposal = proposal or {}
    last: Clash | None = None
    # A walk can dead-end: `form_project_kv` is a legal document whose every
    # layout is `enabled: false`, and nothing about the document says so. The
    # sampler answers that by redrawing the whole recipe from the same rng, and
    # so does this -- usage is committed only when a walk finishes, or a
    # dead-ended walk would bias the counts toward the choices that led into it.
    for _ in range(ATTEMPTS):
        tags: frozenset[str] = frozenset()
        force: dict[str, str] = {}
        taken: list[tuple[str, str]] = []
        from_model: list[str] = []
        rejected: list[str] = []
        penalty = 1.0
        try:
            for attribute in chooser.order:
                wanted = str(proposal.get(attribute, "") or "")
                option = chooser.find(attribute, wanted, tags) if wanted else None
                if wanted and option is None:
                    rejected.append(f"{attribute}={wanted}")
                if option is not None:
                    from_model.append(attribute)
                else:
                    option = chooser.take(attribute, tags, bare_penalty=penalty,
                                          record=False, chosen=taken)
                force[attribute] = option.id
                taken.append((attribute, option.id))
                tags = tags | option.tags
                if attribute == "document":
                    # Read once the document is known, and used when `ornament`
                    # comes round several attributes later.
                    penalty = _bare_penalty(policy, option.id)
        except Clash as clash:
            last = clash
            continue
        for attribute, option_id in taken:
            chooser.record(attribute, option_id)
        by = "llm" if from_model else "coverage"
        note = "rules refused " + ", ".join(rejected) if rejected else ""
        return Decision(index=index, seed=seed, force=force, by=by, note=note)
    raise ValueError(
        f"image {index}: no legal page after {ATTEMPTS} attempts ({last})")


# ------------------------------------------------------------------ the model


def schema(rules: dict[str, list[Option]], order: tuple[str, ...], block: int) -> dict:
    """A JSON schema whose every field is an enum of ids the rules define.

    Constrained decoding then makes an invalid id impossible rather than
    unlikely, which is the difference between a planner that needs a repair
    path for correctness and one that needs it only for coherence.
    """
    page = {
        "type": "object",
        "properties": {name: {"type": "string",
                              "enum": sorted(o.id for o in rules[name])}
                       for name in order},
        "required": list(order),
        "additionalProperties": False,
    }
    return {
        "type": "object",
        "properties": {"pages": {"type": "array", "items": page,
                                 "minItems": block, "maxItems": block}},
        "required": ["pages"],
        "additionalProperties": False,
    }


SYSTEM = """Bạn là bộ chọn tham số cho một máy sinh ảnh chứng từ Việt Nam.
Mỗi trang là một tổ hợp thuộc tính. Hãy chọn sao cho:

1. TỪNG TRANG hợp lý như giấy thật — quán ăn vỉa hè không in hoá đơn GTGT có
   mã vạch; máy in nhiệt đời cũ không in màu; tờ khách sạn không kẻ 12 cột.
2. CẢ LÔ đa dạng — đừng lặp lại một tổ hợp, hãy phủ đều các loại giấy, bố cục
   và cách dựng lại (variant).
3. Giấy tờ do nhà nước quy định mẫu thì variant phải là "none"; bù lại hãy cho
   chúng con dấu hoặc hoạ tiết (ornament) thay vì đổi bố cục.

Chỉ trả về id có trong enum."""


def propose(llm, rules, order, block: int, seen: dict[str, dict[str, int]],
            temperature: float | None = None) -> list[dict[str, str]]:
    """`block` proposals from the server, or [] if it could not give any."""
    from .client import LLMError

    tally = {name: dict(sorted(counts.items(), key=lambda kv: -kv[1])[:6])
             for name, counts in seen.items() if counts}
    user = (f"Chọn tham số cho {block} trang tiếp theo.\n"
            f"Những giá trị đã dùng nhiều nhất cho tới giờ (hãy tránh bớt):\n"
            f"{json.dumps(tally, ensure_ascii=False)}")
    if temperature is not None:
        llm.temperature = temperature
    try:
        answer = llm.decide(SYSTEM, user, schema(rules, order, block))
    except LLMError:
        return []
    pages = answer.get("pages")
    if not isinstance(pages, list):
        return []
    return [{k: str(v) for k, v in page.items() if isinstance(v, str)}
            for page in pages if isinstance(page, dict)]


# -------------------------------------------------------------------- the plan


def plan(count: int, seed: int, rules: dict[str, list[Option]], policy,
         *, order: tuple[str, ...] | None = None, llm=None,
         pressure: float = DEFAULT_PRESSURE, block: int = 24,
         penalty: dict[str, dict[str, float]] | None = None,
         ban: Iterable[tuple[tuple[str, str], tuple[str, str]]] = (),
         resume: list[Decision] = (), checkpoint=None) -> list[Decision]:
    """`count` decided pages, in output order.

    `penalty` and `ban` are the previous run's review, as
    `agent/critic.py::load_feedback` hands them back. Passing them is how the
    reviewer's findings reach the next set: values that broke pages get drawn
    less, and pairs that only break together stop being drawn at all.

    A page decided by the model is one network round trip that cannot be
    replayed for free, so a run of thousands is not a thing to lose to a
    dropped connection or a killed process. Two knobs cover that:

    `resume` is a prefix of already-decided pages, typically `read()` back
    from a checkpoint an earlier, interrupted call to `plan()` left behind.
    Their usage is replayed into the chooser -- so the coverage objective
    still sees them as drawn -- and the loop picks up at `len(resume)`
    instead of asking the model again for pages it already answered.

    `checkpoint`, if given, is a path `write()` is called against after every
    `block` pages, so a run killed partway loses at most one block's worth of
    model calls rather than every one since the start. Bounded by `block` on
    purpose: writing after every single page would turn thousands of model
    calls into thousands of rewrites of a JSON file that only grows.

    Progress prints to stderr either way -- see `pipeline/progress.py` for
    what it shows and why it never touches stdout.
    """
    order = tuple(order or rules.keys())
    chooser = Chooser(rules, order, seed=seed, pressure=pressure,
                      penalty=penalty, ban=ban)
    out: list[Decision] = list(resume)
    for decision in out:
        for attribute, option_id in decision.force.items():
            chooser.record(attribute, option_id)
    pending: list[dict[str, str]] = []

    with Bar(count, "trang") as bar:
        bar.set(len(out))
        since_checkpoint = 0
        for index in range(len(out), count):
            if llm is not None and not pending:
                pending = propose(llm, rules, order, min(block, count - index), chooser.used)
            proposal = pending.pop(0) if pending else None
            decision = decide_one(chooser, policy, index, seed + index, proposal)
            out.append(decision)
            bar.advance(1, note=decision.by)
            since_checkpoint += 1
            if checkpoint is not None and since_checkpoint >= block:
                write(checkpoint, out)
                since_checkpoint = 0
        if checkpoint is not None and since_checkpoint:
            write(checkpoint, out)
    return out


def verify(decisions: list[Decision], rules: dict[str, list[Option]]) -> list[str]:
    """Re-draw every decision through the sampler. Empty is the healthy answer.

    Cheap insurance against the one bug that would be invisible until the
    renderer had run for an hour: a pin the rules refuse makes `sample_recipe`
    re-draw the other attributes, so the page would be *a* page -- just not the
    one the plan says, with a record that disagrees with its own provenance.
    """
    problems: list[str] = []
    for decision in decisions:
        try:
            recipe = sample_recipe(seed=decision.seed, rules=rules,
                                   force=decision.force, attempts=4)
        except Exception as error:                       # noqa: BLE001
            problems.append(f"image {decision.index}: {type(error).__name__}: {error}")
            continue
        drew = recipe.ids()
        for attribute, wanted in decision.force.items():
            if drew.get(attribute) != wanted:
                problems.append(
                    f"image {decision.index}: asked {attribute}={wanted!r}, "
                    f"sampler drew {drew.get(attribute)!r}")
    return problems


def audit_drawn(out, decisions: list[Decision], backend: str = "html") -> list[str]:
    """Compare what was DRAWN against what was decided. Empty is healthy.

    `verify()` proves the plan is a plan the sampler would honour. It cannot
    prove the plan reached the renderer, and that is a different failure with
    no symptom: `pipeline.plan.shard_runs` rebuilt each piece of a split run
    field by field and silently dropped `force`, so 5000 pages were drawn from
    the layout pin alone. Every page rendered, every invariant passed, every
    record was well-formed, and `agent_plan.json` described none of them.

    So the run reads its own provenance back. `synthesis.json` records the
    attributes each page was actually built from; this is the one place they
    are held against the decision that asked for them.
    """
    import json
    from pathlib import Path

    from pipeline.plan import image_name

    path = Path(out) / backend / "synthesis.json"
    if not path.exists():
        return [f"{path} is missing, so nothing can be checked against the plan"]
    pages = (json.loads(path.read_text(encoding="utf-8")) or {}).get("pages") or {}
    problems: list[str] = []
    for decision in decisions:
        name = image_name(backend, decision.index)
        entry = pages.get(name)
        if entry is None:
            continue                    # not drawn: the shard report covers that
        drew = {key: (value["id"] if isinstance(value, dict) else value)
                for key, value in (entry.get("attributes") or {}).items()}
        if not drew:
            continue
        wrong = {name: (wanted, drew.get(name))
                 for name, wanted in decision.force.items() if drew.get(name) != wanted}
        if wrong:
            problems.append(f"{name}: drawn with " + ", ".join(
                f"{k}={got!r} where the plan said {wanted!r}"
                for k, (wanted, got) in sorted(wrong.items())))
    return problems


def coverage(decisions: list[Decision], rules: dict[str, list[Option]]
             ) -> dict[str, Any]:
    """What the plan actually covers, per attribute and as joint triples."""
    per: dict[str, dict[str, int]] = {}
    for decision in decisions:
        for attribute, value in decision.force.items():
            per.setdefault(attribute, {})[value] = per.setdefault(attribute, {}).get(value, 0) + 1
    triples = {f"{d.force['document']}|{d.force['layout']}|{d.force['variant']}"
               for d in decisions if "variant" in d.force}
    return {
        "images": len(decisions),
        "by": {mode: sum(1 for d in decisions if d.by == mode)
               for mode in ("llm", "coverage")},
        "distinct_triples": len(triples),
        "attributes": {
            name: {"defined": len(rules.get(name, ())), "used": len(counts),
                   "min": min(counts.values()), "max": max(counts.values()),
                   "counts": dict(sorted(counts.items()))}
            for name, counts in sorted(per.items())
        },
    }


def unused(decisions: list[Decision], rules: dict[str, list[Option]]) -> dict[str, list[str]]:
    """Drawable values the plan never draws. Empty is the healthy answer.

    Values switched off -- `weight: 0` or `enabled: false` -- are not counted.
    A report that listed `torn_edges` as never drawn would be reporting that the
    rules did what they say, every run, forever, which is noise that hides the
    one line that means something.
    """
    seen: dict[str, set[str]] = {}
    for decision in decisions:
        for attribute, value in decision.force.items():
            seen.setdefault(attribute, set()).add(value)
    dead = set(unreachable(rules).get("document") or ())
    out = {}
    for name, options in rules.items():
        drawable = {o.id for o in options if o.weight > 0 and o.enabled}
        if name == "document":
            drawable -= dead
        missing = sorted(drawable - seen.get(name, set()))
        if missing:
            out[name] = missing
    return out


def unreachable(rules: dict[str, list[Option]]) -> dict[str, list[str]]:
    """Documents that pass every option check and still cannot make a page.

    A document is drawable -- positive weight, `enabled: true` -- and every
    layout its tags admit is switched off. Nothing about the document says so,
    and the walk simply dead-ends on `layout` every time. Worth naming: it is
    almost always a layout switched off without anyone checking who was left
    depending on it, and the symptom otherwise is a document that quietly never
    appears in any dataset.
    """
    def live(options):
        return [o for o in options if o.weight > 0 and o.enabled]

    out: list[str] = []
    for document in live(rules.get("document") or []):
        if not any(option.allowed(document.tags)
                   for option in live(rules.get("layout") or [])):
            out.append(document.id)
    return {"document": sorted(out)} if out else {}


def to_runs(decisions: list[Decision]) -> list:
    """The plan, as `pipeline.plan.Run` objects: one page each, fully pinned."""
    from pipeline.plan import Run

    return [Run(layout=d.layout, seed=d.seed, count=1, first_index=d.index,
                force=dict(d.force)) for d in decisions]


def write(path, decisions: list[Decision]) -> Any:
    import pathlib

    path = pathlib.Path(path)
    path.write_text(json.dumps([d.to_dict() for d in decisions],
                               ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def read(path) -> list[Decision]:
    """The inverse of `write()` -- [] for a path that is not there yet.

    Missing rather than raising, because the caller is always a checkpoint
    that may not exist: the first run of a plan, or one that finished
    cleanly and had its checkpoint removed. Either way, "nothing to resume
    from" is not an error.
    """
    import pathlib

    path = pathlib.Path(path)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [Decision(**item) for item in raw]


__all__ = ["BARE_ID", "BARE_PENALTY", "DEFAULT_PRESSURE", "Chooser", "Decision",
           "SYSTEM", "audit_drawn", "coverage", "decide_one", "plan", "propose",
           "read", "schema", "to_runs", "unreachable", "unused", "verify", "write"]
