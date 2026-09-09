"""How far a composed layout may go, read from `constraints.yaml`.

    limits = constraints.load().limits("invoice_detailed")
    limits.papers          # ('a4',)
    limits.width           # (72, 96)

`agent/policy.py` answers *may this document be redrawn at all*. This answers
the next question -- *within what* -- and it is a separate file because it is a
separate judgement, made by a different person at a different time.

Everything here refuses rather than guesses, the same way `policy.py` does and
for the same reason. A document with no entry is an error; a document whose
entry still says `reviewed: false` is an error naming the person who has to
look at it. The whole point of the file is that a phôi cannot arrive
unconstrained and start being composed from scratch.

**Every name in the file is checked against the repository's own vocabulary at
load time**, not at use time: `papers` against `rulebase.style.SHEETS`,
`sections.forbidden` against `rulebase.layout.SECTIONS`, `families` against the
`family:` keys the committed layouts actually carry. A typo in a hand-edited
YAML is then a message naming the alternatives, rather than a constraint that
silently forbids nothing -- which is the failure mode a constraint file has
that a schema does not: `forbidden: [vat_summry]` reads as valid YAML, forbids
nothing at all, and nothing downstream would ever say so.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from agent import layout_schema
from rulebase.layout import LAYOUTS_ROOT, SECTIONS
from rulebase.style import SHEETS

CONSTRAINTS_FILE = Path(__file__).resolve().parent / "constraints.yaml"

# The roll: a layout that names no `sheet:` prints on continuous paper, whose
# height is decided by the cutter. `rulebase.style.sheet_ratio` returns None
# for it on purpose, so "" is a real value here and not a missing one.
ROLL = ""


class ConstraintsError(ValueError):
    """The constraints and the repository disagree about what exists."""


@dataclass(frozen=True)
class Couple:
    """One block whose job another block's setting can do instead.

    The intersection of §8.1 counts BLOCKS, and a page is made of FIELDS.
    Where a phôi drops a block and still prints its fields, it is because some
    other block was told to do that job -- `invoice_header_table` drops `strip`
    and prints the invoice date because `header.align: corner` draws it into
    the corner box, and drops `totals` because `table.component: true` merges
    the three total rows into the item table itself.

    Written down rather than inferred, for §5.1's reason: this is a fact about
    how two builder functions interact, and no amount of reading the phôi
    yields it -- you have to read `sheets/modern.py`. Written down at all
    because the alternative, tried first, was to require both blocks always,
    which is safe and costs every composition that a real print shop would
    have made.

    A coupling is exclusive in both directions. Neither present is a field with
    a label and no ink (I-5); both present is the same field printed twice.
    """

    section: str        # the block carrying the setting
    leaf: str           # the setting
    value: Any          # the value that does the replacing
    replaces: str       # the block it stands in for
    why: str

    @property
    def option(self) -> str:
        return f"{self.section}.{self.leaf}"

    def active_in(self, options_by_section: dict) -> bool:
        got = (options_by_section.get(self.section) or {})
        return self.leaf in got and got[self.leaf] == self.value


@dataclass(frozen=True)
class Limits:
    """What one document's composed layout may be, after review."""

    document: str
    reviewer: str
    papers: tuple[str, ...]
    width: tuple[int, int]
    gutter: tuple[int, int]
    columns: tuple[int, int]
    flex_min: int
    sections_min: int
    sections_max: int
    forbidden: frozenset[str]
    required: frozenset[str]
    couples: tuple[Couple, ...]
    families: tuple[str, ...]
    note: str

    def couple_for(self, section: str) -> Couple | None:
        """The setting that can stand in for `section`, if one was declared."""
        return next((c for c in self.couples if c.replaces == section), None)

    def paper_ok(self, sheet: str) -> str:
        if sheet not in self.papers:
            have = ", ".join(repr(p) for p in self.papers)
            return (f"sheet {sheet!r} is not one of {have} for {self.document} "
                    f"-- see constraints.yaml")
        return ""

    def band_ok(self, name: str, value: Any, band: tuple[int, int]) -> str:
        low, high = band
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return f"{name} is {value!r}, which is not a number"
        if not low <= value <= high:
            return f"{name} is {value}, outside {low}..{high}"
        return ""


@dataclass(frozen=True)
class Constraints:
    """The file, parsed and checked against the rules it governs."""

    by_document: dict[str, Limits]
    unreviewed: dict[str, str]           # document -> why it is still shut
    defaults: dict[str, Any]

    def limits(self, document: str) -> Limits:
        try:
            return self.by_document[document]
        except KeyError:
            pass
        if document in self.unreviewed:
            raise ConstraintsError(
                f"{document!r} has an entry in {CONSTRAINTS_FILE.name} but it is "
                f"not reviewed yet: {self.unreviewed[document]}. Compose is shut "
                f"until a person sets `reviewed: true` -- the numbers there are "
                f"a judgement about Vietnamese paper, not a measurement.")
        raise ConstraintsError(
            f"{document!r} has no entry in {CONSTRAINTS_FILE.name}. Add one "
            f"(there is a template at the bottom of the file) -- a document "
            f"nobody has put bounds on must not be composed from scratch.")

    def documents(self) -> list[str]:
        """Every document compose is open for. Sorted, so reports are stable."""
        return sorted(self.by_document)


def _band(entry: dict, key: str, defaults: dict, where: str) -> tuple[int, int]:
    """A `[min, max]` pair, ascending, from the entry or the defaults."""
    raw = entry.get(key, defaults.get(key))
    if raw is None:
        raise ConstraintsError(f"{where}: no {key}, and no default for it")
    if not (isinstance(raw, list) and len(raw) == 2):
        raise ConstraintsError(f"{where}: {key} is {raw!r}, not a [min, max] pair")
    low, high = raw
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (low, high)):
        raise ConstraintsError(f"{where}: {key} = {raw!r}, and both ends must be "
                               "whole numbers of characters")
    if low > high:
        raise ConstraintsError(f"{where}: {key} = [{low}, {high}] has its ends "
                               "swapped; every range in this repository is "
                               "[min, max]")
    return (low, high)


def families(root: Path | str = LAYOUTS_ROOT) -> frozenset[str]:
    """Every CSS family a committed layout names. Measured, not listed.

    `sheets.FAMILIES` maps family names to modules and lives behind the
    renderer's own `sys.path`, which this package deliberately does not join
    (see `agent/README.md` §0). The layouts carry the same names in their own
    `family:` key and are plain YAML, so the vocabulary is readable from here
    without importing the render path.
    """
    found: set[str] = set()
    for path in sorted(Path(root).glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        name = str(spec.get("family", "") or "").strip()
        if name:
            found.add(name)
    return frozenset(found)


def _limits(document: str, entry: dict, defaults: dict,
            known_families: frozenset[str]) -> Limits:
    where = f"{CONSTRAINTS_FILE.name}: {document}"

    papers = entry.get("papers")
    if not isinstance(papers, list) or not papers:
        raise ConstraintsError(f"{where}: no `papers:` list. Write [a4], or "
                               f'[""] for continuous roll.')
    papers = [ROLL if p is None else str(p) for p in papers]
    unknown = [p for p in papers if p != ROLL and p not in SHEETS]
    if unknown:
        raise ConstraintsError(
            f"{where}: paper {unknown} is not a sheet this repository draws; "
            f'have {", ".join(sorted(SHEETS))} and "" for a continuous roll')

    sections = entry.get("sections") or {}
    if not isinstance(sections, dict):
        raise ConstraintsError(f"{where}: `sections:` must be a mapping")
    default_sections = defaults.get("sections") or {}
    low = sections.get("min", default_sections.get("min"))
    high = sections.get("max", default_sections.get("max"))
    if not all(isinstance(v, int) and not isinstance(v, bool) for v in (low, high)):
        raise ConstraintsError(f"{where}: sections.min/max must be whole numbers")
    if low > high:
        raise ConstraintsError(f"{where}: sections [{low}, {high}] is reversed")
    named: dict[str, list[str]] = {}
    for key in ("forbidden", "required"):
        value = sections.get(key, default_sections.get(key) or [])
        if not isinstance(value, list):
            raise ConstraintsError(f"{where}: sections.{key} must be a list")
        value = [str(name) for name in value]
        stray = [name for name in value if name not in SECTIONS]
        if stray:
            raise ConstraintsError(
                f"{where}: sections.{key} names {stray}, which "
                f"`rulebase.layout.SECTIONS` does not draw; have "
                f"{', '.join(sorted(SECTIONS))}. A name with a typo in it "
                f"constrains nothing, and nothing else would ever say so.")
        named[key] = value
    forbidden, wanted = named["forbidden"], named["required"]
    clash = sorted(set(forbidden) & set(wanted))
    if clash:
        raise ConstraintsError(
            f"{where}: sections {clash} are in both `required` and `forbidden`")

    names = entry.get("families")
    if not isinstance(names, list) or not names:
        raise ConstraintsError(f"{where}: no `families:` list")
    names = [str(name) for name in names]
    stray = [name for name in names if name not in known_families]
    if stray:
        raise ConstraintsError(
            f"{where}: family {stray} dresses no committed layout; have "
            f"{', '.join(sorted(known_families))}")

    flex = entry.get("flex_min", defaults.get("flex_min"))
    if not isinstance(flex, int) or isinstance(flex, bool) or flex < 0:
        raise ConstraintsError(f"{where}: flex_min must be a whole number of "
                               f"characters, not {flex!r}")

    return Limits(
        document=document,
        reviewer=str(entry.get("reviewer", "") or "").strip(),
        papers=tuple(papers),
        width=_band(entry, "width", defaults, where),
        gutter=_band(entry, "gutter", defaults, where),
        columns=_band(entry, "columns", defaults, where),
        flex_min=flex,
        sections_min=int(low),
        sections_max=int(high),
        forbidden=frozenset(forbidden),
        required=frozenset(wanted),
        couples=_couples(entry, where),
        families=tuple(names),
        note=" ".join(str(entry.get("note", "") or "").split()),
    )


def _couples(entry: dict, where: str) -> tuple[Couple, ...]:
    """`couples:` from one document entry, checked against the derived schema.

    The setting has to exist. A coupling naming `header.aligment` reads as
    valid YAML, matches nothing, and would quietly turn back into "require
    both blocks always" -- which is the conservative behaviour it was written
    to replace, arrived at by accident and with nothing saying so.
    """
    raw = entry.get("couples") or []
    if not isinstance(raw, list):
        raise ConstraintsError(f"{where}: `couples:` must be a list")
    schema = layout_schema.derive()
    found = []
    for item in raw:
        if not isinstance(item, dict):
            raise ConstraintsError(f"{where}: a couple must be a mapping")
        missing = [key for key in ("option", "equals", "replaces")
                   if key not in item]
        if missing:
            raise ConstraintsError(f"{where}: a couple is missing {missing}")
        option = str(item["option"])
        section, _, leaf = option.partition(".")
        if section not in SECTIONS:
            raise ConstraintsError(
                f"{where}: couple option {option!r} names block {section!r}, "
                f"which `rulebase.layout.SECTIONS` does not draw")
        if not leaf or option not in schema:
            near = [k for k in schema if k.startswith(f"{section}.")]
            raise ConstraintsError(
                f"{where}: couple option {option!r} is a key no committed "
                f"layout has, so nothing would ever set it; "
                f"`{section}` has {', '.join(sorted(near)) or 'no settings'}")
        replaces = str(item["replaces"])
        if replaces not in SECTIONS:
            raise ConstraintsError(
                f"{where}: couple replaces {replaces!r}, which is not a block")
        found.append(Couple(section=section, leaf=leaf, value=item["equals"],
                            replaces=replaces,
                            why=" ".join(str(item.get("why", "")).split())))
    seen = [c.replaces for c in found]
    twice = sorted({name for name in seen if seen.count(name) > 1})
    if twice:
        raise ConstraintsError(f"{where}: {twice} is replaced by more than one "
                               f"couple; a block has one stand-in or none")
    return tuple(found)


def load(path: Path | str = CONSTRAINTS_FILE,
         layouts: Path | str = LAYOUTS_ROOT) -> Constraints:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    defaults = raw.get("defaults") or {}
    entries = raw.get("documents") or {}
    if not isinstance(entries, dict):
        raise ConstraintsError(f"{path}: `documents:` must be a mapping")

    known = families(layouts)
    open_for: dict[str, Limits] = {}
    shut: dict[str, str] = {}
    for document, entry in entries.items():
        document = str(document)
        if not isinstance(entry, dict):
            raise ConstraintsError(f"{path}: {document} is not a mapping")
        if "reviewed" not in entry:
            raise ConstraintsError(
                f"{path}: {document} has no `reviewed:` key. It is not optional "
                f"-- an entry nobody claims is an entry nobody checked.")
        if not entry.get("reviewed"):
            shut[document] = (f"reviewer is "
                              f"{entry.get('reviewer') or 'nobody yet'}")
            continue
        limits = _limits(document, entry, defaults, known)
        if not limits.reviewer:
            raise ConstraintsError(
                f"{path}: {document} is `reviewed: true` with no `reviewer:`. "
                f"The name is the point: it says who to ask about the numbers.")
        open_for[document] = limits
    return Constraints(by_document=open_for, unreviewed=shut, defaults=defaults)


def problems(rules, pol=None, path: Path | str = CONSTRAINTS_FILE) -> list[str]:
    """Everything the constraints get wrong about the rules they govern.

    Same shape as `rulebase.blanks.problems` and `agent.policy.problems`, and
    for the same reason: a registry beside the rules is only worth having if
    something checks that the two still describe the same world.

    A document *missing* from here is not reported. Absence is the default and
    it is the safe one -- `Constraints.limits` refuses it, so the worst it
    costs is a variant nobody gets. What is reported is an entry naming a
    document that does not exist, and an entry opening a document the policy
    has already shut, which is the one way the two files can contradict each
    other without anything noticing.
    """
    loaded = load(path)
    actual = {option.id for option in rules["document"]}
    named = set(loaded.by_document) | set(loaded.unreviewed)
    found = [f"constraints: {name!r} is not a document"
             for name in sorted(named - actual)]
    if pol is not None:
        for name in loaded.documents():
            if pol.klass(name) == "locked":
                found.append(
                    f"constraints: {name!r} is reviewed open for compose, but "
                    f"policy.yaml has it `locked` -- a phôi the state issues "
                    f"has one valid shape and composing a second teaches the "
                    f"model that a forgery is genuine")
    return found


__all__ = ["CONSTRAINTS_FILE", "ROLL", "Constraints", "ConstraintsError",
           "Couple", "Limits", "families", "load", "problems"]
