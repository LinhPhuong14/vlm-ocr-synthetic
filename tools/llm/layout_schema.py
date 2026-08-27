"""What a layout file may contain, derived from the layouts that exist.

`rulebase/layout.py::load_layout` is `yaml.safe_load` and nothing else -- there
is no schema, and there never needed to be one while a human wrote every layout
by hand and `preflight` caught the rest. A model writing layouts changes that:
a typo in a key name is silently ignored by the builder, so the variant draws
the parent's page and the run reports a new layout that is not new.

So the schema is **derived** rather than declared, by walking every committed
layout and recording, for each key path:

* the types seen at it,
* the numeric range, if it is a number,
* the distinct values, if it is a string with few of them -- `align` is
  `left|center|right` and nothing else, and a model that writes `centre` should
  be told so rather than have it ignored.

Derived rather than written down for the same reason `corpus_rules` measures:
a hand-written schema goes stale the day someone adds `table.shade`, and a
stale schema rejects a real layout. `--show` prints it, and the 17 committed
layouts produce 88 key paths.

**Generated layouts are excluded from the derivation.** Otherwise the first
variant widens the schema and the second is checked against the first one's
mistakes -- the same drift `corpus_rules.Envelope` avoids by measuring only
human lines. `MARK` is how a file says it was generated.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYOUTS_ROOT = REPO_ROOT / "rulebase" / "layouts"

# The first line of a generated layout. A comment, so `yaml.safe_load` never
# sees it and every existing reader is unchanged.
MARK = "# llm-generated"

# A string key with at most this many distinct values across the corpus of
# layouts is treated as an enum; above it, it is free text (a title, a label,
# a column key) and only the charset is checked.
ENUM_MAX = 6

# How far outside the observed numeric range a value may sit. A layout is
# meant to be able to be wider than any existing one -- but not ten times.
SLACK = 1.4

# Keys whose value is free Vietnamese text printed on the page. Checked for
# charset and length, never against a list.
TEXT_LEAVES = ("title", "label", "name", "source", "separator", "leader",
               "notes", "id")


@dataclass
class Leaf:
    types: set[str] = field(default_factory=set)
    numbers: list[float] = field(default_factory=list)
    values: set[str] = field(default_factory=set)
    seen: int = 0

    @property
    def enum(self) -> bool:
        return (self.types == {"str"} and len(self.values) <= ENUM_MAX
                and all(len(v) <= 24 for v in self.values))

    def bounds(self) -> tuple[float, float]:
        low, high = min(self.numbers), max(self.numbers)
        return (low / SLACK if low > 0 else low * SLACK,
                high * SLACK if high > 0 else high / SLACK)


def walk(node: Any, path: str = ""):
    """Every leaf of a layout, by the key path that reaches it.

    A list is `[]` in the path rather than an index, so `columns[0].align` and
    `columns[3].align` are one key: they are the same field, and a schema that
    told them apart would learn nothing from either.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            yield from walk(value, f"{path}.{key}" if path else str(key))
    elif isinstance(node, list):
        for value in node:
            yield from walk(value, path + "[]")
    else:
        yield path, node


def is_generated(path: Path) -> bool:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.readline().startswith(MARK)


def derive(root: Path = LAYOUTS_ROOT, include_generated: bool = False
           ) -> dict[str, Leaf]:
    """The schema, from the committed layouts a person wrote."""
    schema: dict[str, Leaf] = {}
    for path in sorted(root.glob("*.yaml")):
        if not include_generated and is_generated(path):
            continue
        for key, value in walk(yaml.safe_load(path.read_text(encoding="utf-8"))):
            leaf = schema.setdefault(key, Leaf())
            leaf.types.add(type(value).__name__)
            leaf.seen += 1
            if isinstance(value, bool):
                continue                      # bool is an int; keep them apart
            if isinstance(value, (int, float)):
                leaf.numbers.append(float(value))
            elif isinstance(value, str):
                leaf.values.add(value)
    return schema


def charset(schema: dict[str, Leaf]) -> frozenset[str]:
    """Every punctuation mark the committed layouts actually use.

    Measured, not listed -- and for the reason the rest of this package is a
    catalogue of. A hand-written list of "the characters a layout uses" was
    tried first and rejected all seventeen layouts on one character: `name:`
    carries a human-readable description and every one of them has an em dash
    in it. Guessing a charset guesses wrong.

    Letters and digits are not enumerated: those are checked structurally, so
    the corpus of layouts does not have to contain every Vietnamese letter for
    a new layout to be allowed to use one.
    """
    marks: set[str] = set()
    for leaf in schema.values():
        for value in leaf.values:
            marks |= {c for c in value
                      if not (c.isalnum() or c.isspace() or unicodedata.combining(c))}
    return frozenset(marks)


def _text_ok(value: str, allowed: frozenset[str]) -> str:
    """A free-text field: Latin letters, digits, and the marks layouts use."""
    for character in value:
        if character.isspace() or character.isdigit():
            continue
        if unicodedata.combining(character) or character in allowed:
            continue
        if not character.isalnum():
            return f"the character {character!r} is not printed on any layout"
        base = unicodedata.normalize("NFD", character)[0]
        if not unicodedata.name(base, "").startswith("LATIN"):
            return f"{character!r} is not Latin -- this is a Vietnamese layout"
    return ""


def check(layout: dict, schema: dict[str, Leaf] | None = None) -> list[str]:
    """Every problem with a proposed layout. Empty is the healthy answer."""
    schema = schema if schema is not None else derive()
    allowed = charset(schema)
    problems: list[str] = []
    for key, value in walk(layout):
        leaf = schema.get(key)
        if leaf is None:
            near = [k for k in schema if k.split(".")[-1] == key.split(".")[-1]]
            problems.append(
                f"{key}: no layout has this key"
                + (f" (did you mean {near[0]}?)" if near else ""))
            continue
        kind = type(value).__name__
        if kind not in leaf.types:
            problems.append(
                f"{key}: {kind} {value!r}, but every layout has "
                f"{'/'.join(sorted(leaf.types))} here")
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)) and leaf.numbers:
            low, high = leaf.bounds()
            if not low <= float(value) <= high:
                problems.append(
                    f"{key}: {value}, outside {low:g}..{high:g} "
                    f"(layouts use {min(leaf.numbers):g}..{max(leaf.numbers):g})")
        elif isinstance(value, str):
            if leaf.enum and value not in leaf.values:
                problems.append(
                    f"{key}: {value!r} is not one of "
                    f"{'|'.join(sorted(leaf.values))}")
            elif not leaf.enum:
                problem = _text_ok(value, allowed)
                if problem:
                    problems.append(f"{key}: {problem}")
    return problems


def ranges(layout: dict, path: str = "") -> list[str]:
    """Every `[min, max]` pair that is the wrong way round.

    A layout states its variable numbers as a two-element list -- `width:
    [48, 42]`, `name_scale: [1.0, 1.3]` -- and `rulebase` feeds them straight
    to `randrange`. Reversed, that is `ValueError: empty range for randrange()`
    on **every seed**, which the build step below does catch -- after six
    subprocesses and half a minute.

    This is the same failure for the price of a comparison, and it is a real
    one: it is what the first generated variant did. All 59 numeric pairs
    across the seventeen committed layouts ascend, so there is no legitimate
    descending pair to reject by mistake.
    """
    problems: list[str] = []
    if isinstance(layout, dict):
        for key, value in layout.items():
            problems += ranges(value, f"{path}.{key}" if path else str(key))
    elif isinstance(layout, list):
        numbers = [v for v in layout
                   if isinstance(v, (int, float)) and not isinstance(v, bool)]
        if len(layout) == 2 and len(numbers) == 2 and numbers[0] > numbers[1]:
            problems.append(
                f"{path}: [{numbers[0]:g}, {numbers[1]:g}] is a range with its "
                "ends swapped; every layout writes [min, max]")
        for value in layout:
            problems += ranges(value, path + "[]")
    return problems


def required(schema: dict[str, Leaf] | None = None,
             root: Path = LAYOUTS_ROOT) -> list[str]:
    """Key paths EVERY committed layout has. A variant missing one is broken.

    `id`, `name`, `source`, `width`, `rule_char`, `footer.rule_before` and
    `sections` are in all seventeen; anything else is a choice some layouts
    make and others do not.
    """
    files = [p for p in sorted(root.glob("*.yaml")) if not is_generated(p)]
    if not files:
        return []
    common: set[str] | None = None
    for path in files:
        keys = {key for key, _ in walk(yaml.safe_load(path.read_text(encoding="utf-8")))}
        common = keys if common is None else (common & keys)
    return sorted(common or set())


def missing(layout: dict, root: Path = LAYOUTS_ROOT) -> list[str]:
    have = {key for key, _ in walk(layout)}
    return [key for key in required(root=root) if key not in have]


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--show", action="store_true", help="print the schema")
    args = parser.parse_args()
    if not args.show:
        parser.error("nothing to do; --show is the only mode")

    schema = derive()
    files = [p for p in sorted(LAYOUTS_ROOT.glob("*.yaml")) if not is_generated(p)]
    print(f"{len(schema)} key paths over {len(files)} hand-written layouts")
    for key in sorted(schema):
        leaf = schema[key]
        kinds = "/".join(sorted(leaf.types))
        if leaf.numbers:
            detail = f"{min(leaf.numbers):g}..{max(leaf.numbers):g}"
        elif leaf.enum:
            detail = "|".join(sorted(leaf.values))
        else:
            detail = f"{len(leaf.values)} distinct, free text"
        print(f"  {key:44} {kinds:10} n={leaf.seen:3}  {detail}")
    print("\nrequired in every layout: " + ", ".join(required(schema)))
    return 0


__all__ = ["ENUM_MAX", "LAYOUTS_ROOT", "MARK", "SLACK", "Leaf", "charset",
           "check", "derive", "is_generated", "missing", "ranges", "required",
           "walk"]

if __name__ == "__main__":
    raise SystemExit(main())
