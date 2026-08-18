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


def _sources(root: Path | str) -> dict[str, list[Path]]:
    """`{attribute: [file, ...]}` -- one YAML file, or a directory of them.

    `rules/layout.yaml` and `rules/document/business.yaml` are both the
    attribute they are named after. The directory form exists because the
    document attribute is the one that grows with the hierarchy: six receipt
    values fit in one file, ninety-eight document types across twelve families
    do not, and splitting them family by family is the only way the file a
    person needs to edit stays findable.

    Both forms for one attribute is an error rather than a merge. Two places to
    look for the same option is how a run ends up drawing from the copy nobody
    was editing.
    """
    root = Path(root)
    if not root.is_dir():
        # Reported by the caller as "missing rules files in ...", which is what
        # it always said. Listing a directory that is not there would raise an
        # OSError from three frames down instead.
        return {}
    found: dict[str, list[Path]] = {}
    for path in sorted(root.glob("*.yaml")):
        if not path.name.startswith("_"):
            found[path.stem] = [path]
    for directory in sorted(p for p in root.iterdir() if p.is_dir()):
        if directory.name.startswith("_"):
            continue
        files = sorted(directory.glob("*.yaml"))
        if not files:
            raise RuleError(f"{directory}: an attribute directory with no *.yaml in it")
        if directory.name in found:
            raise RuleError(
                f"{root}: {directory.name} exists both as {directory.name}.yaml and as "
                f"a directory; keep one"
            )
        found[directory.name] = files
    return found


def attribute_order(root: Path | str = RULES_ROOT) -> tuple[str, ...]:
    """The attributes, in the order they are drawn, from `rules/_order.yaml`.

    Attributes are discovered rather than hard-coded, so a seventh criterion is
    a new YAML file and a line in the manifest -- no Python edit. The manifest
    exists because auto-discovery alone would be a downgrade: a hard-coded
    tuple is impossible to forget, a directory listing is not. Three ways to
    get it wrong, all of them loud:

    * a `rules/foo.yaml` -- or a `rules/foo/` directory -- the manifest never
      mentions, which would simply never be drawn while generation carried on;
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

    present = set(_sources(root))
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
    """One value of one attribute.

    `doc_type` is the join to the hierarchy in `taxonomy/`: it names the node
    this value realises, e.g. `business.receipt.retail`. Several values may
    realise one type -- a supermarket and a convenience store both print a
    retail receipt -- and that is the point: the type is what the label says and
    what a dataset is balanced over, the value is one way of producing it.
    """

    id: str
    weight: float = 1.0
    tags: frozenset[str] = frozenset()
    requires: frozenset[str] = frozenset()
    excludes: frozenset[str] = frozenset()
    params: dict[str, Any] = field(default_factory=dict)
    doc_type: str = ""

    @classmethod
    def from_dict(cls, raw: dict[str, Any], attribute: str) -> "Option":
        known = {"id", "weight", "tags", "requires", "excludes", "params", "doc_type"}
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
            doc_type=str(raw.get("doc_type") or ""),
        )

    def allowed(self, tags: Iterable[str]) -> bool:
        tags = set(tags)
        return self.requires <= tags and not (self.excludes & tags)

    def realises(self, doc_type: str) -> bool:
        """Does this value produce `doc_type`, or something under it?

        Subtree-wide, so a run can ask for `business.receipt` and get all four
        kinds of receipt, or for `business` and get the whole family. The prefix
        test is on dotted segments rather than characters: `business.receipt`
        must not match a hypothetical `business.receipt_draft`.
        """
        if not self.doc_type or not doc_type:
            return False
        return self.doc_type == doc_type or self.doc_type.startswith(doc_type + ".")


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

    @property
    def doc_type(self) -> str:
        """Which node of `taxonomy/` this recipe is an instance of.

        Read off whichever drawn value declares one -- in practice the
        `document` attribute, but the sampler does not need to know that, which
        is what lets a later attribute refine the type (a `layout` value that
        turns a retail receipt into an ATM slip) without a special case here.
        The last declaration down the draw order wins, since later attributes
        see everything the earlier ones chose.
        """
        found = ""
        for option in self.choices.values():
            if option.doc_type:
                found = option.doc_type
        return found

    def to_dict(self) -> dict[str, Any]:
        """Provenance to store next to the image."""
        return {
            "seed": self.seed,
            "doc_type": self.doc_type,
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

    An attribute may be one file or a directory of them (see `_sources`). A
    directory's files are concatenated in name order and the ids must still be
    unique across all of them -- two families defining `certificate` would
    otherwise shadow each other depending on which file sorted first.
    """
    root = Path(root)
    sources = _sources(root)
    if not sources:
        raise RuleError(f"missing rules files in {root}")

    parsed: dict[str, list[Option]] = {}
    for attribute, files in sources.items():
        entries: list[Option] = []
        seen: dict[str, Path] = {}
        for path in files:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            options = raw.get("options")
            if not options:
                raise RuleError(f"{path}: no options")
            for item in options:
                option = Option.from_dict(item, attribute)
                if option.id in seen:
                    raise RuleError(
                        f"{path}: duplicate option id {option.id!r}"
                        + (f" (also in {seen[option.id].name})"
                           if seen[option.id] != path else "")
                    )
                seen[option.id] = path
                entries.append(option)
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


class _Clash(RuleError):
    """A pin did not fit what *this attempt* happened to draw before it.

    A `RuleError` subclass on purpose: without `force` there is nothing to
    retry, so it propagates and reads exactly as it always did.
    """


# How many times one seed may re-draw before the pin is declared unreachable.
# Whether it really is unreachable is then decided by `_reachable_tags`, not by
# having run out of patience -- see `sample_recipe`.
DRAW_ATTEMPTS = 500


def _draw_once(order: tuple[str, ...], rules: dict[str, list[Option]],
               force: dict[str, str], rng: random.Random, doc_type: str = ""
               ) -> tuple[dict[str, Option], set[str]]:
    """One pass down the attributes. Raises `_Clash` if a pin does not fit."""
    tags: set[str] = set()
    choices: dict[str, Option] = {}

    for attribute in order:
        options = rules[attribute]
        if doc_type and any(option.doc_type for option in options):
            # This attribute is one that names document types, so the request
            # narrows it. Attributes that name none are untouched -- asking for
            # a prescription must not stop the paper from being thermal.
            narrowed = [option for option in options if option.realises(doc_type)]
            if not narrowed:
                raise RuleError(
                    f"{attribute}: no value realises doc_type {doc_type!r}. The type "
                    f"exists in the hierarchy but nothing in the rules produces it yet"
                )
        else:
            narrowed = options
        candidates = [option for option in narrowed if option.allowed(tags)]
        if attribute in force:
            wanted = force[attribute]
            # Looked up in the *unnarrowed* list so that pinning a value the
            # doc_type rules out reads as the conflict it is, rather than as a
            # value that does not exist.
            by_id = {option.id: option for option in options}
            if wanted not in by_id:
                # Not a clash: no draw will ever conjure a value that is not in
                # the rules, so retrying would only delay the same answer.
                raise RuleError(
                    f"{attribute}: no option {wanted!r}; have "
                    f"{', '.join(sorted(by_id))}"
                )
            pinned = by_id[wanted]
            if pinned not in narrowed:
                raise RuleError(
                    f"{attribute}={wanted!r} produces "
                    f"{pinned.doc_type or 'no document type'}, but this run asked for "
                    f"{doc_type!r}. Pin one or the other, not both"
                )
            if not pinned.allowed(tags):
                blocking = sorted((pinned.requires - tags) | (pinned.excludes & tags))
                raise _Clash(
                    f"{attribute}={wanted!r} is not compatible with the recipe so "
                    f"far ({', '.join(sorted(tags)) or 'no tags'}); tags at fault: "
                    f"{', '.join(blocking)}"
                )
            chosen = pinned
        else:
            if not candidates:
                raise _Clash(
                    f"{attribute}: nothing satisfies the tags chosen so far "
                    f"({', '.join(sorted(tags)) or 'none'})"
                )
            chosen = _weighted_choice(candidates, rng)
        choices[attribute] = chosen
        tags |= chosen.tags

    return choices, tags


def _reachable_tags(order: tuple[str, ...], rules: dict[str, list[Option]],
                    force: dict[str, str], upto: int,
                    doc_type: str = "") -> set[frozenset[str]]:
    """Every tag set the attributes before `upto` can possibly produce.

    A breadth-first sweep over tag sets rather than over recipes: two different
    draws that leave the same tags are the same thing to everything downstream,
    so the state space stays small even though the recipe space does not.

    Used only when a seed has failed every attempt, to answer the question that
    decides which of two messages the caller gets: is this pin unreachable, or
    was this seed merely unlucky? Answering it by "we gave up" would be a guess.
    """
    states: set[frozenset[str]] = {frozenset()}
    for attribute in order[:upto]:
        options = rules[attribute]
        if doc_type and any(option.doc_type for option in options):
            options = [option for option in options if option.realises(doc_type)]
        if attribute in force:
            options = [option for option in options if option.id == force[attribute]]
        following: set[frozenset[str]] = set()
        for tags in states:
            for option in options:
                # weight 0 means never drawn, so it cannot supply a tag either.
                if option.weight > 0 and option.allowed(tags):
                    following.add(frozenset(tags | option.tags))
        states = following
        if not states:
            break
    return states


def resolve_doc_type(query: str | None) -> str:
    """A document type as a person typed it -> its full id in `taxonomy/`.

    `retail`, `receipt.retail` and `business.receipt.retail` are the same
    request; a name that matches two nodes -- `certificate` does -- is an error
    naming both rather than a guess. Kept here so every entry point that takes a
    document type (three renderers, the planner, the report) resolves it the
    same way.
    """
    if not query:
        return ""
    import taxonomy

    return taxonomy.tree().resolve(str(query)).id


def sample_recipe(
    seed: int | None = None,
    rules: dict[str, list[Option]] | None = None,
    force: dict[str, str] | None = None,
    attempts: int = DRAW_ATTEMPTS,
    doc_type: str | None = None,
) -> Recipe:
    """Draw one value per attribute, honouring weights and constraints.

    `force` pins an attribute to a named value -- how the dataset driver gets
    an even spread over layouts instead of the weighted mix that a single
    random image should have. A pinned value still has to satisfy its own
    `requires`/`excludes`, otherwise the recipe it produced would be one the
    rules say cannot exist.

    `doc_type` pins the *document type* instead of a rules value: it restricts
    every attribute that names types to the ones under that node of the
    hierarchy, and leaves the rest of the draw alone. The distinction matters
    once the tree is wide -- a run is balanced over document types, which are
    stable and public and appear in the label, not over rules values, which are
    an implementation detail and get split and renamed as a family grows.

    **A pin that clashes re-draws; it does not move to another seed.** Until
    W1b, `make()` handled a clash by trying `seed + 1`, `seed + 2` and so on
    until one fitted. That kept the function deterministic and quietly made it
    many-to-one: every seed in the gap before a fitting one returned that same
    recipe, so 2000 consecutive seeds pinned to `market_vat` produced 217
    distinct recipes and a run of 36 seeds could collapse onto a single page.
    A dataset built that way reports twenty images and holds ten.

    Re-drawing from the same `random.Random(seed)` fixes it without touching the
    contract everything else depends on: `recipe.seed` is still the seed that
    was asked for, and it still reproduces the page. The alternatives were
    worse -- a separate `effective_seed` leaves two kinds of seed for every
    reader to keep straight, and pre-computing which seeds fit puts knowledge of
    the rules into the scheduling layer.

    Without `force` nothing can clash, the loop returns on its first pass, and
    the draw is bit-for-bit what it was before.
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
    if attempts < 1:
        raise RuleError(f"attempts must be at least 1, got {attempts}")
    wanted_type = resolve_doc_type(doc_type)

    if seed is None:
        seed = random.randrange(2**31)
    rng = random.Random(seed)

    clash: _Clash | None = None
    for _ in range(attempts):
        try:
            choices, tags = _draw_once(order, rules, force, rng, wanted_type)
        except _Clash as unlucky:
            if not force and not wanted_type:
                raise            # nothing to re-draw around; this is the answer
            clash = unlucky
            continue
        return Recipe(seed=seed, choices=choices, tags=frozenset(tags))

    # Out of attempts. Which of the two failures this is has to be decided, not
    # assumed: "impossible" and "unlucky" want different actions from a caller.
    impossible = [
        f"{attribute}={force[attribute]!r}"
        for index, attribute in enumerate(order)
        if attribute in force
        and not any(
            option.allowed(tags)
            for option in rules[attribute] if option.id == force[attribute]
            for tags in _reachable_tags(order, rules, force, index, wanted_type)
        )
    ]
    # The same question for a pinned document type: is there any attribute that
    # nothing can satisfy once the type has narrowed the ones before it? A type
    # whose rules exist but whose layouts do not lands here, and saying which
    # attribute ran dry is the difference between a fixable message and a shrug.
    starved = [
        attribute
        for index, attribute in enumerate(order)
        if wanted_type
        and not any(
            option.allowed(tags)
            for option in rules[attribute]
            if option.weight > 0 and (not option.doc_type or option.realises(wanted_type))
            for tags in _reachable_tags(order, rules, force, index, wanted_type)
        )
    ]
    if impossible or starved:
        parts = []
        if impossible:
            parts.append(f"{', '.join(impossible)} cannot be drawn at all")
        if starved:
            parts.append(
                f"doc_type {wanted_type!r} leaves {', '.join(starved)} with nothing "
                f"drawable"
            )
        raise RuleError(
            f"{'; '.join(parts)}: no legal choice of the attributes before it "
            f"produces the tags it needs. The rules forbid this combination, so no "
            f"seed will satisfy it.\n  last clash: {clash}"
        )
    asked_for = ", ".join(
        part for part in (str(force) if force else "", f"doc_type={wanted_type}"
                          if wanted_type else "") if part)
    raise RuleError(
        f"seed {seed} failed {attempts} draws with {asked_for}; the combination is "
        f"legal, so this seed is unlucky rather than impossible -- raise `attempts` "
        f"or use another seed.\n  last clash: {clash}"
    )


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


def reachable_options(
    attribute: str,
    rules: dict[str, list[Option]] | None = None,
    doc_type: str | None = None,
) -> list[Option]:
    """Which values of `attribute` a run could ever draw for a document type.

    `enumerate_valid` answers the question for one known tag set; this answers
    it for *all* of them at once, by sweeping every tag set the earlier
    attributes can produce. That is what a planner needs and a renderer does
    not: to spread a retail receipt's images over its layouts, the planner has
    to know which layouts a retail receipt can legally have -- pinning
    `eatery_ascii` on a supermarket is a run that fails a hundred images in.

    With no `doc_type` this is "every value anything could draw", which is the
    old behaviour of listing the layouts directory, minus the values the rules
    have made unreachable.
    """
    rules = rules or load_rules()
    order = tuple(rules)
    if attribute not in order:
        raise RuleError(f"unknown attribute {attribute!r}; have {', '.join(order)}")
    wanted = resolve_doc_type(doc_type)
    states = _reachable_tags(order, rules, {}, order.index(attribute), wanted)

    options = rules[attribute]
    if wanted and any(option.doc_type for option in options):
        options = [option for option in options if option.realises(wanted)]
    return [
        option for option in options
        if option.weight > 0 and any(option.allowed(tags) for tags in states)
    ]


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

    problems.extend(validate_doc_types(rules))
    return problems


def validate_doc_types(rules: dict[str, list[Option]] | None = None) -> list[str]:
    """Check the rules against `taxonomy/`, in both directions.

    Forwards: a value that names a type the hierarchy does not have, or names a
    branch rather than a leaf, or names an alias instead of the node the
    document is really filed under.

    Backwards, and this is the one that matters: a type the hierarchy calls
    `ready` that no value realises. That combination is exactly the lie the
    status field exists to prevent -- a coverage report showing a green type
    that no run can produce -- and it is invisible from either file alone.
    """
    import taxonomy

    rules = rules if rules is not None else load_rules()
    tree = taxonomy.tree()
    problems: list[str] = []
    realised: set[str] = set()

    for attribute, options in rules.items():
        for option in options:
            if not option.doc_type:
                continue
            if option.doc_type not in tree:
                problems.append(
                    f"{attribute}/{option.id}: doc_type {option.doc_type!r} is not in "
                    f"the hierarchy; see taxonomy/families/"
                )
                continue
            node = tree.node(option.doc_type)
            if not node.is_leaf:
                problems.append(
                    f"{attribute}/{option.id}: doc_type {node.id!r} is a branch with "
                    f"{len(node.children)} types under it; name one of them"
                )
                continue
            if node.is_alias:
                problems.append(
                    f"{attribute}/{option.id}: doc_type {node.id!r} is an alias of "
                    f"{node.same_as!r}; generate the canonical one"
                )
                continue
            if node.status == "planned":
                problems.append(
                    f"{attribute}/{option.id}: realises {node.id!r}, which is still "
                    f"marked planned; move it to draft or ready"
                )
            realised.add(node.id)

    from .documents import covered

    builders = covered()
    for node in tree.leaves():
        if node.status != "ready":
            continue
        if node.id not in realised:
            problems.append(
                f"taxonomy: {node.id} is marked ready but no rules value realises it"
            )
        if node.id not in builders:
            problems.append(
                f"taxonomy: {node.id} is marked ready but no builder is registered "
                f"for it in rulebase/documents.py"
            )
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
    "reachable_options",
    "resolve_doc_type",
    "sample_recipe",
    "validate",
    "validate_doc_types",
]
