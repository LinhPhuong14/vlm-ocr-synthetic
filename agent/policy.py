"""Which documents an agent may redress, read from `policy.yaml`.

The policy is data because it is a judgement about paper, not about code: a
Vietnamese reader who disagrees that a water bill is `livery` rather than
`free` should be able to move one line and re-run, without touching Python.

Everything here refuses rather than guesses. A document the policy has never
heard of is an error, not a silent `free` -- the whole point of the file is
that a new phôi cannot arrive unclassified and start being redrawn.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

POLICY_FILE = Path(__file__).resolve().parent / "policy.yaml"

# Widest first. `livery` may draw what `locked` may draw, and `free` may draw
# what both may, so the order is what `allows` reads to decide.
ORDER = ("locked", "livery", "free")


class PolicyError(ValueError):
    """The policy and the rules disagree about what documents exist."""


@dataclass(frozen=True)
class Policy:
    """Document id -> class, and the tag each class puts on a document."""

    by_document: dict[str, str]
    tags: dict[str, str]
    reasons: dict[str, str]

    def klass(self, document: str) -> str:
        try:
            return self.by_document[document]
        except KeyError:
            raise PolicyError(
                f"document {document!r} is in no class in {POLICY_FILE.name}. "
                f"Add it to locked, livery or free -- an unclassified phôi must "
                f"not default to being redrawn.") from None

    def tag(self, document: str) -> str:
        return self.tags[self.klass(document)]

    def allows(self, document: str, level: str) -> bool:
        """Whether this document may wear a variant of `level`."""
        return ORDER.index(level) <= ORDER.index(self.klass(document))

    def documents(self, klass: str) -> list[str]:
        return sorted(name for name, k in self.by_document.items() if k == klass)


def load(path: Path | str = POLICY_FILE) -> Policy:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    classes = raw.get("classes") or {}
    tags = raw.get("tags") or {}
    missing = set(ORDER) - set(classes)
    if missing:
        raise PolicyError(f"{path}: no class {sorted(missing)}")
    if set(tags) != set(ORDER):
        raise PolicyError(f"{path}: tags must name exactly {list(ORDER)}")

    by_document: dict[str, str] = {}
    reasons: dict[str, str] = {}
    for name in ORDER:
        entry = classes[name] or {}
        reasons[name] = " ".join(str(entry.get("reason") or "").split())
        for document in entry.get("documents") or []:
            if document in by_document:
                raise PolicyError(
                    f"{path}: document {document!r} is in both "
                    f"{by_document[document]!r} and {name!r}")
            by_document[str(document)] = name
    return Policy(by_document=by_document, tags=dict(tags), reasons=reasons)


def problems(rules, path: Path | str = POLICY_FILE) -> list[str]:
    """Everything the policy gets wrong about the rules it governs.

    Same shape as `rulebase.blanks.problems`, and for the same reason: a
    registry beside the rules is only worth having if something checks that the
    two still describe the same world.
    """
    policy = load(path)
    actual = {option.id for option in rules["document"]}
    declared = set(policy.by_document)
    found = [f"policy: {name!r} is not a document" for name in sorted(declared - actual)]
    found += [f"policy: document {name!r} is in no class; it would never be "
              f"classified and the run would stop on it"
              for name in sorted(actual - declared)]
    return found


__all__ = ["ORDER", "POLICY_FILE", "Policy", "PolicyError", "load", "problems"]
