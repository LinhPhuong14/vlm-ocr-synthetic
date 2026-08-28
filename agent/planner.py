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
"""

from __future__ import annotations

import json
import random
from dataclasses import asdict, dataclass
from typing import Any

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


class Chooser:
    """Weighted choice that remembers, over one attribute at a time."""

    def __init__(self, rules: dict[str, list[Option]], order: tuple[str, ...],
                 seed: int, pressure: float = DEFAULT_PRESSURE):
        self.rules = rules
        self.order = tuple(order)
        self.rng = random.Random(seed)
        self.pressure = float(pressure)
        self.used: dict[str, dict[str, int]] = {name: {} for name in self.order}

    def legal(self, attribute: str, tags: frozenset[str]) -> list[Option]:
        """Drawable values: allowed by the tags, and not switched off.

        `weight: 0` is how the rules switch a value off -- `_weighted_choice`
        has always read it that way. The coverage score divides by usage and
        floors at a tiny positive number, so without this a switched-off value
        would be picked the moment everything else had been used once, which is
        the opposite of off.
        """
        return [option for option in self.rules[attribute]
                if option.weight > 0 and option.allowed(tags)]

    def _score(self, attribute: str, option: Option, bare_penalty: float) -> float:
        used = self.used[attribute].get(option.id, 0)
        score = option.weight / (1.0 + used) ** self.pressure
        if attribute == "ornament" and option.id == BARE_ID:
            score *= bare_penalty
        return max(score, 1e-9)

    def take(self, attribute: str, tags: frozenset[str],
             bare_penalty: float = 1.0) -> Option:
        options = self.legal(attribute, tags)
        if not options:
            raise ValueError(
                f"{attribute}: nothing is drawable under tags {sorted(tags)}; "
                f"the rules cannot produce a page here")
        weights = [self._score(attribute, option, bare_penalty) for option in options]
        option = self.rng.choices(options, weights=weights, k=1)[0]
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
    tags: frozenset[str] = frozenset()
    force: dict[str, str] = {}
    from_model: list[str] = []
    rejected: list[str] = []
    penalty = 1.0

    for attribute in chooser.order:
        wanted = str(proposal.get(attribute, "") or "")
        option = chooser.find(attribute, wanted, tags) if wanted else None
        if wanted and option is None:
            rejected.append(f"{attribute}={wanted}")
        if option is not None:
            chooser.record(attribute, option.id)
            from_model.append(attribute)
        else:
            option = chooser.take(attribute, tags, bare_penalty=penalty)
        force[attribute] = option.id
        tags = tags | option.tags
        if attribute == "document":
            # Read once the document is known, and used when `ornament` comes
            # round several attributes later.
            penalty = _bare_penalty(policy, option.id)

    by = "llm" if from_model else "coverage"
    note = ""
    if rejected:
        note = "rules refused " + ", ".join(rejected)
    return Decision(index=index, seed=seed, force=force, by=by, note=note)


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
         pressure: float = DEFAULT_PRESSURE, block: int = 24) -> list[Decision]:
    """`count` decided pages, in output order."""
    order = tuple(order or rules.keys())
    chooser = Chooser(rules, order, seed=seed, pressure=pressure)
    out: list[Decision] = []
    pending: list[dict[str, str]] = []

    for index in range(count):
        if llm is not None and not pending:
            pending = propose(llm, rules, order, min(block, count - index), chooser.used)
        proposal = pending.pop(0) if pending else None
        out.append(decide_one(chooser, policy, index, seed + index, proposal))
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
    """Values the rules define that the plan never draws. Should be empty-ish."""
    seen: dict[str, set[str]] = {}
    for decision in decisions:
        for attribute, value in decision.force.items():
            seen.setdefault(attribute, set()).add(value)
    return {name: sorted({o.id for o in options} - seen.get(name, set()))
            for name, options in rules.items()
            if {o.id for o in options} - seen.get(name, set())}


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


__all__ = ["BARE_ID", "BARE_PENALTY", "DEFAULT_PRESSURE", "Chooser", "Decision",
           "SYSTEM", "audit_drawn", "coverage", "decide_one", "plan", "propose",
           "schema", "to_runs", "unused", "verify", "write"]
