"""The rule-base: six attributes, many values each, one drawn per image.

    document      what kind of paper this is       (loại document)
    layout        how the fields are arranged      (bố cục)
    content       what goes in the fields          (nội dung)
    visual        font, paper, print quality       (hình thức)
    color         the ink and the tint             (màu)
    augmentation  how the page is then aged        (làm cũ)

Every value carries a weight, so the mix is tuned by editing numbers in
`rules/*.yaml` and nothing else. Values also carry tags, and may require or
exclude tags chosen earlier -- that is what stops the sampler from pairing a
supermarket barcode layout with a hand-written restaurant corpus, or asking a
1990s thermal printer for colour.

Attributes are drawn in the order above, each one seeing the tags the earlier
ones contributed. So `document` is the widest choice and `augmentation` the
narrowest, which matches how a real receipt comes about: the shop decides what
it prints long before the page decides how it will be creased.

    from rulebase import sample_recipe
    recipe = sample_recipe(seed=7)
    recipe.layout.id            -> 'market_barcode'
    recipe.get("visual", "font_size")
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

import yaml

# A run may need rules of its own -- `pipeline.yaml` can re-weight a value for
# one job without editing the shipped files. The renderers are separate
# processes, so the only way to hand them a variation is a directory on disk and
# an environment variable pointing at it. Unset, which is the normal case, this
# is exactly the shipped path and nothing about generation changes.
RULES_ROOT = Path(os.environ.get("VLM_RULES_ROOT") or Path(__file__).resolve().parent / "rules")
ORDER_FILE = "_order.yaml"


class RuleError(ValueError):
    """A rules file asks for something impossible."""


def attribute_order(root: Path | str = RULES_ROOT) -> tuple[str, ...]:
    """The attributes, in the order they are drawn, from `rules/_order.yaml`.

    Attributes are discovered rather than hard-coded, so a seventh criterion is
    a new YAML file and a line in the manifest -- no Python edit. The manifest
    exists because auto-discovery alone would be a downgrade: a hard-coded
    tuple is impossible to forget, a directory listing is not. Three ways to
    get it wrong, all of them loud:

    * a `rules/foo.yaml` the manifest never mentions -- the file would simply
      never be drawn, and generation would carry on without it;
    * a manifest entry with no file behind it;
    * the same attribute listed twice, which would draw it twice and let the
      second draw see the first one's tags.

    Order is not cosmetic. A value can only `require` a tag that an *earlier*
    attribute sets, so this list decides which constraints are expressible;
    `validate()` reports the ones that are not.
    """
    root = Path(root)
    path = root / ORDER_FILE
    if not path.exists():
        raise RuleError(f"missing {path}: it lists the attributes and their order")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    order = raw.get("order")
    if not order:
        raise RuleError(f"{path}: no 'order:' list")
    order = [str(name) for name in order]

    duplicates = sorted({name for name in order if order.count(name) > 1})
    if duplicates:
        raise RuleError(f"{path}: {duplicates} listed more than once")

    present = {p.stem for p in root.glob("*.yaml") if not p.name.startswith("_")}
    listed = set(order)
    forgotten = sorted(present - listed)
    if forgotten:
        raise RuleError(
            f"{path}: {forgotten} exist in {root} but are not listed, so they "
            f"would never be drawn; add them or delete the files"
        )
    missing = sorted(listed - present)
    if missing:
        raise RuleError(f"{path}: lists {missing}, but there is no rules file for them")
    return tuple(order)


class _Attributes(Sequence):
    """`ATTRIBUTES` as it always was, but read from the manifest.

    A module-level tuple would freeze the order at import time, before a test
    or a tool has had the chance to point at a different rules directory. This
    reads on use and stays a plain sequence, so `for a in ATTRIBUTES`,
    `a in ATTRIBUTES`, indexing and `len()` all behave as they did.
    """

    def _order(self) -> tuple[str, ...]:
        return attribute_order()

    def __getitem__(self, index):
        return self._order()[index]

    def __len__(self) -> int:
        return len(self._order())

    def __repr__(self) -> str:
        return repr(self._order())

    def __eq__(self, other) -> bool:
        return tuple(self._order()) == tuple(other)

    def __hash__(self) -> int:
        return hash(self._order())


ATTRIBUTES: Sequence[str] = _Attributes()


@dataclass(frozen=True)
class Option:
    """One value of one attribute."""

    id: str
    weight: float = 1.0
    tags: frozenset[str] = frozenset()
    requires: frozenset[str] = frozenset()
    excludes: frozenset[str] = frozenset()
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], attribute: str) -> "Option":
        known = {"id", "weight", "tags", "requires", "excludes", "params"}
        unknown = set(raw) - known
        if unknown:
            raise RuleError(
                f"{attribute}: option {raw.get('id', '?')!r} has unknown keys "
                f"{sorted(unknown)}; params belong under 'params:'"
            )
        if "id" not in raw:
            raise RuleError(f"{attribute}: an option has no id")
        weight = float(raw.get("weight", 1.0))
        if weight < 0:
            raise RuleError(f"{attribute}/{raw['id']}: negative weight")
        return cls(
            id=str(raw["id"]),
            weight=weight,
            tags=frozenset(raw.get("tags") or ()),
            requires=frozenset(raw.get("requires") or ()),
            excludes=frozenset(raw.get("excludes") or ()),
            params=dict(raw.get("params") or {}),
        )

    def allowed(self, tags: Iterable[str]) -> bool:
        tags = set(tags)
        return self.requires <= tags and not (self.excludes & tags)


@dataclass(frozen=True)
class Recipe:
    """One sampled point in the space -- everything a backend needs."""

    seed: int
    choices: dict[str, Option]
    tags: frozenset[str]

    def __getattr__(self, name: str) -> Option:
        try:
            return self.choices[name]
        except KeyError:
            raise AttributeError(name) from None

    def get(self, attribute: str, key: str, default: Any = None) -> Any:
        option = self.choices.get(attribute)
        return default if option is None else option.params.get(key, default)

    def ids(self) -> dict[str, str]:
        return {name: option.id for name, option in self.choices.items()}

    def to_dict(self) -> dict[str, Any]:
        """Provenance to store next to the image."""
        return {
            "seed": self.seed,
            "attributes": {
                name: {"id": option.id, "params": option.params}
                for name, option in self.choices.items()
            },
            "tags": sorted(self.tags),
        }


def load_rules(root: Path | str = RULES_ROOT) -> dict[str, list[Option]]:
    """Read every `rules/<attribute>.yaml`, in the order the manifest gives.

    The returned dict is insertion-ordered in draw order, and everything
    downstream iterates *it* rather than a module-level constant. That is what
    lets a caller load a different rules directory -- a test, a preflight
    against a candidate tree -- and have the sampler honour its order.

    Files are read and checked before the manifest is consulted, so a broken
    YAML is reported as a broken YAML rather than as a manifest mismatch.
    """
    root = Path(root)
    files = sorted(path for path in root.glob("*.yaml") if not path.name.startswith("_"))
    if not files:
        raise RuleError(f"missing rules files in {root}")

    parsed: dict[str, list[Option]] = {}
    for path in files:
        attribute = path.stem
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        options = raw.get("options")
        if not options:
            raise RuleError(f"{path}: no options")
        entries = [Option.from_dict(item, attribute) for item in options]
        seen: set[str] = set()
        for option in entries:
            if option.id in seen:
                raise RuleError(f"{path}: duplicate option id {option.id!r}")
            seen.add(option.id)
        parsed[attribute] = entries

    return {attribute: parsed[attribute] for attribute in attribute_order(root)}


def _weighted_choice(options: Sequence[Option], rng: random.Random) -> Option:
    total = sum(option.weight for option in options)
    if total <= 0:
        raise RuleError("every candidate has weight 0")
    threshold = rng.random() * total
    upto = 0.0
    for option in options:
        upto += option.weight
        if upto >= threshold:
            return option
    return options[-1]  # only reachable through float rounding


def sample_recipe(
    seed: int | None = None,
    rules: dict[str, list[Option]] | None = None,
    force: dict[str, str] | None = None,
) -> Recipe:
    """Draw one value per attribute, honouring weights and constraints.

    `force` pins an attribute to a named value -- how the dataset driver gets
    an even spread over layouts instead of the weighted mix that a single
    random image should have. A pinned value still has to satisfy its own
    `requires`/`excludes`, otherwise the recipe it produced would be one the
    rules say cannot exist.
    """
    rules = rules or load_rules()
    force = force or {}
    # The order comes from the rules mapping, not from the manifest on disk:
    # a caller that built `rules` by hand decides its own order, and reading
    # the shipped manifest here would ignore that.
    order = tuple(rules)
    unknown = set(force) - set(order)
    if unknown:
        raise RuleError(f"cannot force unknown attributes {sorted(unknown)}")

    if seed is None:
        seed = random.randrange(2**31)
    rng = random.Random(seed)

    tags: set[str] = set()
    choices: dict[str, Option] = {}

    for attribute in order:
        options = rules[attribute]
        candidates = [option for option in options if option.allowed(tags)]
        if attribute in force:
            wanted = force[attribute]
            by_id = {option.id: option for option in options}
            if wanted not in by_id:
                raise RuleError(
                    f"{attribute}: no option {wanted!r}; have "
                    f"{', '.join(sorted(by_id))}"
                )
            pinned = by_id[wanted]
            if not pinned.allowed(tags):
                blocking = sorted((pinned.requires - tags) | (pinned.excludes & tags))
                raise RuleError(
                    f"{attribute}={wanted!r} is not compatible with the recipe so "
                    f"far ({', '.join(sorted(tags)) or 'no tags'}); tags at fault: "
                    f"{', '.join(blocking)}"
                )
            chosen = pinned
        else:
            if not candidates:
                raise RuleError(
                    f"{attribute}: nothing satisfies the tags chosen so far "
                    f"({', '.join(sorted(tags)) or 'none'})"
                )
            chosen = _weighted_choice(candidates, rng)
        choices[attribute] = chosen
        tags |= chosen.tags

    return Recipe(seed=seed, choices=choices, tags=frozenset(tags))


def parse_force(items: Iterable[str] | None, layout: str | None = None) -> dict[str, str] | None:
    """Turn `["augmentation=pristine"]` into the dict `sample_recipe` wants.

    Every renderer takes the same `--force ATTR=ID` flag, so this lives here
    rather than being written out three times and drifting. `layout` is the
    older, narrower flag; it is folded in so both spellings work.
    """
    forced: dict[str, str] = {}
    for item in items or ():
        attribute, separator, value = item.partition("=")
        if not separator or not value:
            raise RuleError(f"--force expects ATTR=ID, got {item!r}")
        attribute = attribute.strip()
        if attribute not in ATTRIBUTES:
            raise RuleError(
                f"--force: unknown attribute {attribute!r}; have {', '.join(ATTRIBUTES)}"
            )
        forced[attribute] = value.strip()
    if layout:
        forced.setdefault("layout", layout)
    return forced or None


def enumerate_valid(
    attribute: str,
    rules: dict[str, list[Option]] | None = None,
    tags: Iterable[str] = (),
) -> list[str]:
    """Which values of `attribute` are reachable given `tags`. For the docs."""
    rules = rules or load_rules()
    return [option.id for option in rules[attribute] if option.allowed(tags)]


def validate(rules: dict[str, list[Option]] | None = None) -> list[str]:
    """Static check of the rules: unreachable values, unsatisfiable tags.

    Run by the test suite. A value nobody can ever draw is almost always a
    typo in a tag name rather than a deliberate switch-off, and a silent one
    -- generation keeps working, that value just never appears.
    """
    rules = rules or load_rules()
    problems: list[str] = []

    # Every tag that could ever be set by an earlier attribute.
    reachable: set[str] = set()
    for attribute in rules:
        for option in rules[attribute]:
            missing = option.requires - reachable
            if missing:
                problems.append(
                    f"{attribute}/{option.id}: requires {sorted(missing)}, which no "
                    f"earlier attribute ever sets"
                )
            if option.weight == 0:
                problems.append(f"{attribute}/{option.id}: weight 0, never drawn")
        reachable |= {tag for option in rules[attribute] for tag in option.tags}

    # Something has to be drawable for every attribute in the worst case.
    for attribute in rules:
        if not any(option.weight > 0 for option in rules[attribute]):
            problems.append(f"{attribute}: every option has weight 0")
    return problems


__all__ = [
    "ATTRIBUTES",
    "ORDER_FILE",
    "attribute_order",
    "Option",
    "Recipe",
    "RuleError",
    "RULES_ROOT",
    "enumerate_valid",
    "load_rules",
    "parse_force",
    "sample_recipe",
    "validate",
]
