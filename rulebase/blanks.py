"""Phôi gốc: the standard form a document is drawn from, before anyone measured it.

`rulebase/layouts/<id>.yaml` is a layout -- columns and rows in character units.
This module is about what came *before* that: the photograph or scan of the real
paper it was measured off. The repository has always named those in a `source:`
line inside each layout file, one string, unreadable as a set and unchecked by
anything.

Two things that string could not say, and this can:

* a blank that has not been converted yet (`layout: null`). Work still owed, in
  the one place someone would look for it.
* which blanks a document is *meant* to draw from. `requires`/`excludes` already
  decide that, and they stay the deciding side -- but a tag solver reports a
  relation, never an intention. Give a new layout one tag too few and every
  document sharing it silently gains a blank. `documents:` is the intention, and
  `problems()` is what fails when the two drift apart.

Deliberately not an attribute in `rules/`: nothing here is sampled. The sampler
never reads this file, and a run whose rules were materialised without it draws
exactly what it drew before.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
BLANKS_FILE = Path(__file__).resolve().parent / "blanks.yaml"


class BlankError(ValueError):
    """The registry and the rules disagree."""


@dataclass(frozen=True)
class Blank:
    """One standard form, and what became of it."""

    id: str
    source: str
    layout: str | None
    sheet: str | None

    @property
    def converted(self) -> bool:
        return self.layout is not None


def load_blanks(path: Path | str = BLANKS_FILE
                ) -> tuple[dict[str, Blank], dict[str, tuple[str, ...]]]:
    """`(blanks by id, blanks each document may draw from)`."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    blanks = {
        name: Blank(id=name, source=str(entry.get("source") or ""),
                    layout=entry.get("layout"), sheet=entry.get("sheet"))
        for name, entry in (raw.get("blanks") or {}).items()
    }
    documents = {name: tuple(members or ())
                 for name, members in (raw.get("documents") or {}).items()}
    return blanks, documents


def resolved(rules) -> dict[str, set[str]]:
    """Which layouts each document can actually draw, per the tags.

    The same walk the sampler does, minus the weighting: `layout` is drawn
    second, so the only tags in play when it is filtered are the document's.
    """
    return {
        document.id: {layout.id for layout in rules["layout"]
                      if layout.allowed(document.tags)}
        for document in rules["document"]
    }


def problems(rules, path: Path | str = BLANKS_FILE) -> list[str]:
    """Everything the registry gets wrong, as lines a person can act on."""
    blanks, documents = load_blanks(path)
    layout_ids = {option.id for option in rules["layout"]}
    found: list[str] = []

    for name, blank in sorted(blanks.items()):
        if blank.layout is not None and blank.layout not in layout_ids:
            found.append(f"blank {name}: layout {blank.layout!r} does not exist")
        if blank.sheet and not (REPO_ROOT / blank.sheet).is_file():
            found.append(f"blank {name}: no sheet at {blank.sheet}")

    declared = set(documents)
    actual = {option.id for option in rules["document"]}
    for name in sorted(declared - actual):
        found.append(f"documents: {name!r} is not a document")
    for name in sorted(actual - declared):
        found.append(f"documents: {name!r} is missing; every document needs its blanks")

    used = {member for members in documents.values() for member in members}
    for name in sorted(used - set(blanks)):
        found.append(f"documents: blank {name!r} is not declared under blanks:")
    for name in sorted(set(blanks) - used):
        found.append(f"blank {name}: no document draws from it")

    # Chỗ chính: chủ đích và tag phải nói cùng một chuyện.
    by_tags = resolved(rules)
    for name in sorted(declared & actual):
        want = {blanks[member].layout for member in documents[name]
                if member in blanks and blanks[member].converted}
        got = by_tags[name]
        for layout in sorted(got - want):
            found.append(
                f"{name}: tags allow layout {layout!r}, blanks.yaml does not "
                f"list a blank for it")
        for layout in sorted(want - got):
            found.append(
                f"{name}: blanks.yaml expects layout {layout!r}, tags forbid it")
    return found


def check(rules, path: Path | str = BLANKS_FILE) -> None:
    found = problems(rules, path)
    if found:
        raise BlankError("\n".join(found))


__all__ = ["BLANKS_FILE", "Blank", "BlankError", "check", "load_blanks",
           "problems", "resolved"]
