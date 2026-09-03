"""The rules root a run builds for itself, with the agent's dressings in it.

    root = rules.materialise(out / "rules", catalogue, policy)

The shipped `rulebase/rules/` has seven attributes and no `variant`. Adding one
there would change every seed in the repository and break the golden baseline
for a reason that has nothing to do with what the baseline checks. So a run
writes its own rules directory instead and points the renderers at it with
`VLM_RULES_ROOT` -- the mechanism `pipeline/config.py` already provides for a
run that needs rules of its own.

What this adds to the shipped rules
-----------------------------------

* a **tag on every document** naming its augmentation class -- `aug_locked`,
  `aug_livery`, `aug_free`, from `agent/policy.yaml`;
* a **`variant` attribute**, drawn straight after `layout` because it dresses
  what `layout` chose, whose values are the catalogue from `agent/variants.py`
  plus `none`.

The policy is then enforced by the tag solver rather than by the planner:

    none            no constraint          every document can draw it
    livery variant  excludes aug_locked    a prescribed form cannot
    free variant    requires aug_free      only a commercial document can

which is what makes `make check-rules` able to see the policy, and what makes
a planner bug unable to redraw a giấy tờ nhà nước by mistake.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

from rulebase.spec import ATTRIBUTES, Option, load_rules

from . import policy as policy_module

# Where `variant` sits in the draw order. After `layout`: a dressing is a
# statement about a phôi, so the phôi has to have been chosen. Before
# `content`, so a later attribute could be made to depend on the dressing --
# nothing does yet, and putting it last would foreclose it.
AFTER = "layout"
ATTRIBUTE = "variant"
NONE_ID = "none"

# How much of the mix draws no dressing at all. The undressed sheet is the one
# every committed dataset holds, so it stays common -- but not dominant: at 6.0
# it was, and a fifth of the run came out as the plain phôi while another two
# fifths wore a paint-only dressing, which is a set that varies in colour and
# not much else.
NONE_WEIGHT = 2.5

# A `free` document can draw a `livery` dressing too -- a commercial invoice
# printed with nothing but a different ink is a real page. It should not be the
# usual one, though: without this the 31 full dressings and the 17 paint-only
# ones split a free document's draws almost evenly, and the run reads as a
# colour sweep. Weighted, roughly three in four free pages are restructured.
FREE_WEIGHT = 2.5


# The tag `rules/layout.yaml` puts on the thermal-roll family. A dressing that
# sets the page's own margins in millimetres cannot be worn by a roll about
# 80 mm across; naming the tag here keeps that one fact in one place.
TILL_TAG = "till_receipt"

# Ink sources that need the WriteViT clone beside the repository. Named here so
# a run without it switches them off deliberately and says so, rather than
# dying on the first page that draws one -- `handwriting.py` refuses to fake
# ink when the model is missing, which is the right call and a fatal one.
NEEDS_WRITEVIT = ("hand_model", "hand_both")


class RulesError(ValueError):
    """The agent's rules cannot be built from the shipped ones."""


def _tagged_documents(options: list[Option], policy) -> list[Option]:
    """Every document, carrying the tag of the class the policy puts it in."""
    out = []
    for option in options:
        tag = policy.tag(option.id)
        out.append(Option.from_dict({
            "id": option.id,
            "weight": option.weight,
            "tags": sorted(set(option.tags) | {tag}),
            "requires": sorted(option.requires),
            "excludes": sorted(option.excludes),
            "params": option.params,
        }, "document"))
    return out


def variant_options(catalogue: list, policy) -> list[Option]:
    """`none`, then one option per dressing, constrained by its level."""
    tags = policy.tags
    out = [Option.from_dict({
        "id": NONE_ID,
        "weight": NONE_WEIGHT,
        "params": {"label": "không dựng lại — giữ nguyên phôi", "level": "locked",
                   "css": ""},
    }, ATTRIBUTE)]
    for dressing in catalogue:
        if dressing.level == "livery":
            constraint = {"excludes": [tags["locked"]]}
        elif dressing.level == "free":
            constraint = {"requires": [tags["free"]]}
            if dressing.wide_only:
                # `till_receipt` is set by the `retail_receipt` layout group, and
                # `layout` is drawn before `variant`, so the tag is in hand by
                # the time this is filtered. See variants.WIDE_ONLY_STRUCTURE.
                constraint["excludes"] = [TILL_TAG]
        else:
            raise RulesError(
                f"dressing {dressing.id!r} has level {dressing.level!r}; "
                f"expected 'livery' or 'free'")
        out.append(Option.from_dict({
            "id": dressing.id,
            "weight": FREE_WEIGHT if dressing.level == "free" else 1.0,
            "tags": [f"dressed_{dressing.level}"],
            **constraint,
            "params": {"label": dressing.label, "level": dressing.level,
                       "axes": dressing.axes, "css": dressing.css,
                       "moves": [list(move) for move in dressing.moves]},
        }, ATTRIBUTE))
    return out


def switch_off(rules: dict[str, list[Option]], attribute: str,
               ids: Iterable[str]) -> dict[str, list[Option]]:
    """Set `weight: 0` on named values -- one of the rules' two ways to say off.

    The other is `enabled: false`, which `rulebase/rules/` uses for a value a
    person switched off on purpose. This one is for a value a *run* cannot use
    -- the WriteViT ink sources on a machine with no WriteViT -- so the shipped
    files keep saying what they mean and only this run's rules root differs.

    Not a deletion either way: the value keeps its id, tags and params, so
    anything reading a record still knows what it would have meant.
    """
    wanted = set(ids)
    out = dict(rules)
    out[attribute] = [
        option if option.id not in wanted else Option.from_dict({
            "id": option.id, "weight": 0,
            "tags": sorted(option.tags),
            "requires": sorted(option.requires),
            "excludes": sorted(option.excludes),
            "params": option.params,
        }, attribute)
        for option in rules[attribute]
    ]
    return out


def writevit_missing() -> Path | None:
    """Where WriteViT should be, when it is not there. None means it is."""
    root = Path(os.environ.get("WRITEVIT_DIR")
                or Path(__file__).resolve().parents[2] / "WriteViT")
    return None if root.is_dir() else root


def compose(catalogue: list, policy=None) -> dict[str, list[Option]]:
    """The shipped rules, tagged, with `variant` spliced in after `layout`."""
    policy = policy or policy_module.load()
    shipped = load_rules()
    problems = policy_module.problems(shipped)
    if problems:
        raise RulesError("\n".join(problems))

    out: dict[str, list[Option]] = {}
    for name in ATTRIBUTES:
        out[name] = (_tagged_documents(shipped[name], policy)
                     if name == "document" else list(shipped[name]))
        if name == AFTER:
            out[ATTRIBUTE] = variant_options(catalogue, policy)
    if ATTRIBUTE not in out:
        raise RulesError(f"{AFTER!r} is not in the draw order, so {ATTRIBUTE!r} "
                         f"has nowhere to go; have {list(ATTRIBUTES)}")
    return out


def materialise(destination: Path | str, catalogue: list, policy=None) -> Path:
    """Write the rules root and return it. Sets nothing; the caller exports it."""
    from pipeline.config import materialise_rules

    return materialise_rules(compose(catalogue, policy), Path(destination))


def activate(root: Path | str) -> None:
    """Point this process *and every child it spawns* at `root`.

    Exported into `os.environ` rather than handed to the worker as an argument:
    `pipeline/run.py` only materialises a root when a run has overrides, and
    this run has none -- it has a whole extra attribute. The environment is the
    channel the renderers already read, and putting it there keeps the parent's
    view of the rules identical to theirs, which a mismatched pair of orders
    would silently break.
    """
    from pipeline.config import RULES_ENV

    os.environ[RULES_ENV] = str(Path(root).resolve())


def reachable(rules: dict[str, list[Option]], policy) -> dict[str, list[str]]:
    """Which dressings each document can actually draw. For the run report."""
    documents = {option.id: option.tags for option in rules["document"]}
    return {
        name: sorted(option.id for option in rules[ATTRIBUTE] if option.allowed(tags))
        for name, tags in sorted(documents.items())
    }


__all__ = ["AFTER", "ATTRIBUTE", "FREE_WEIGHT",
           "NEEDS_WRITEVIT", "TILL_TAG", "switch_off", "writevit_missing",
           "NONE_ID", "NONE_WEIGHT", "RulesError",
           "activate", "compose", "materialise", "reachable", "variant_options"]
