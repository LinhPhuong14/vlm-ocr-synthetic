"""How far each kind of document may be varied, and who is allowed to ask.

    from tools.llm.policy import Policy, level_of
    level_of("vat_invoice_form")     # "fixed"
    level_of("newspaper_classifieds")  # "free"

`rulebase/augmentable.yaml` is the data; this is the reader, the default, and
the check that the two lists have not drifted apart.

**The default is the strictest level.** A document nobody has classified is
`fixed`, so forgetting to add a new one costs a variation that was not made --
not a licence forged in a way nobody reviewed. That asymmetry is the whole
reason this file has a default at all rather than raising: a run must not stop
because somebody added a document type, and it must not silently start varying
one either.

## What each level actually permits

The levels constrain the LAYOUT and nothing else. Content varies at every
level: the fields of a prescribed form are exactly the part that is meant to
be different on every copy, and a VAT invoice with the same buyer on 4,000
pages is a worse dataset than one with the same layout on 4,000 pages.

    fixed    the layout file is used as committed. No variant, no reordering,
             no relabelled column.
    styled   a variant may be proposed, and goes through the whole gauntlet in
             `augment_layout.py` before it draws anything.
    free     the same, with a wider brief -- the prompt is allowed to ask for
             a different kind of page rather than a different dress.

`fixed` is not a statement about how interesting the document is. It is a
statement about who decides its shape: for `vat_invoice_form` that is a
circular from the tax authority, and a generated variant of it is a document
that does not exist. A model trained on those learns to look for a field where
no real page has one.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
POLICY_FILE = REPO_ROOT / "rulebase" / "augmentable.yaml"

FIXED, STYLED, FREE = "fixed", "styled", "free"
LEVELS = (FIXED, STYLED, FREE)

# What an unclassified document gets. The strictest level, on purpose -- see
# the module docstring.
DEFAULT = FIXED

_CACHE: dict[str, str] | None = None


class PolicyError(ValueError):
    """`rulebase/augmentable.yaml` says something it may not say."""


def load(path: Path | str = POLICY_FILE) -> dict[str, str]:
    """`{document id: level}`, cached. Every level must be one of `LEVELS`."""
    global _CACHE
    if _CACHE is not None and Path(path) == POLICY_FILE:
        return _CACHE
    body = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    documents = body.get("documents") or {}
    if not isinstance(documents, dict):
        raise PolicyError(f"{path}: `documents:` must be a mapping of id -> level")
    out: dict[str, str] = {}
    for name, level in documents.items():
        level = str(level)
        if level not in LEVELS:
            raise PolicyError(
                f"{path}: {name} is {level!r}; must be one of {', '.join(LEVELS)}")
        out[str(name)] = level
    if Path(path) == POLICY_FILE:
        _CACHE = out
    return out


def level_of(document: str, path: Path | str = POLICY_FILE) -> str:
    return load(path).get(document, DEFAULT)


def may_vary_layout(document: str) -> bool:
    return level_of(document) != FIXED


def problems(rules=None) -> list[str]:
    """Every disagreement between the policy and the rules, both ways.

    A document in the rules with no level is not an error -- it gets `fixed`,
    which is safe -- but it IS reported, because "safe" here means a document
    type that quietly never varies, and a run whose whole point is variety
    should not have to find that out by reading the output.

    A level for a document the rules do not have is the other half: almost
    always a rename half-done, and the policy still pointing at the old name
    while the new one silently falls to `fixed`.
    """
    from rulebase.spec import load_rules

    rules = rules or load_rules()
    known = {option.id for option in rules["document"]}
    drawable = {option.id for option in rules["document"] if option.enabled}
    levels = load()
    found: list[str] = []
    for name in sorted(drawable - set(levels)):
        found.append(
            f"document/{name}: no level in rulebase/augmentable.yaml, so it is "
            f"treated as {DEFAULT!r} and never varies")
    for name in sorted(set(levels) - known):
        found.append(
            f"augmentable.yaml names {name!r}, which rules/document.yaml does "
            f"not have")
    return found


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="report documents the policy and the rules disagree about")
    args = parser.parse_args()

    levels = load()
    by_level: dict[str, list[str]] = {level: [] for level in LEVELS}
    for name, level in sorted(levels.items()):
        by_level[level].append(name)
    for level in LEVELS:
        print(f"{level:8} {len(by_level[level]):2}  {', '.join(by_level[level])}")

    if args.check:
        found = problems()
        print()
        for problem in found:
            print(f"  - {problem}")
        print("chính sách khớp với luật" if not found else f"{len(found)} vấn đề")
        return 1 if found else 0
    return 0


__all__ = ["DEFAULT", "FIXED", "FREE", "LEVELS", "POLICY_FILE", "STYLED",
           "PolicyError", "level_of", "load", "may_vary_layout", "problems"]

if __name__ == "__main__":
    raise SystemExit(main())
