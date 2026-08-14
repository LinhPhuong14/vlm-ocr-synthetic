"""The scenario space: axes of variants, sampled per page.

A dataset is a cross product -- layout x backend x style x degradation --
and the useful part is *not* enumerating it but sampling it with weights
you control, while keeping nonsense combinations out (an A4 office style on
58mm thermal paper).

Three ideas carry the whole design:

``Variant``
    One choice on one axis. It owns a ``value`` the pipeline knows how to
    use, a ``weight`` (relative, not a probability), ``tags`` it contributes
    to the scenario, and ``requires`` -- tags that must already be present
    for it to be eligible.
``Axis``
    An ordered bag of variants plus weighted sampling. Weights come from
    code by default and are overridden by config, so tuning a distribution
    never means editing Python.
``ScenarioSpace``
    The axes in resolution order. Earlier axes contribute tags that later
    axes filter on, which is what keeps the cross product sane.

Variants are declared in Python (their values are objects: a PaperConfig, a
callable, a dict of renderer options); YAML only carries weights.
"""

from __future__ import annotations

import random
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from typing import Any


class IncompatibleSpace(RuntimeError):
    """No variant on an axis is eligible for the scenario so far."""


@dataclass(frozen=True)
class Variant:
    """One choice on one axis."""

    name: str
    value: Any = None
    weight: float = 1.0
    # Tags this variant contributes to the scenario being built.
    tags: frozenset[str] = frozenset()
    # Tags that must already be present for this variant to be eligible.
    requires: frozenset[str] = frozenset()

    def eligible(self, tags: frozenset[str]) -> bool:
        return self.requires <= tags

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "weight": self.weight,
            "tags": sorted(self.tags),
            "requires": sorted(self.requires),
        }


@dataclass(frozen=True)
class Axis:
    """An ordered bag of variants with weighted sampling."""

    name: str
    variants: tuple[Variant, ...]

    def __post_init__(self) -> None:
        seen = [variant.name for variant in self.variants]
        duplicates = {name for name in seen if seen.count(name) > 1}
        if duplicates:
            raise ValueError(f"axis '{self.name}' has duplicate variants: {duplicates}")

    def names(self) -> list[str]:
        return [variant.name for variant in self.variants]

    def get(self, name: str) -> Variant:
        for variant in self.variants:
            if variant.name == name:
                return variant
        raise KeyError(
            f"axis '{self.name}' has no variant '{name}'; "
            f"available: {', '.join(self.names())}"
        )

    def with_weights(self, weights: dict[str, float]) -> Axis:
        """Override weights by name. Unknown names raise -- they are typos.

        A weight of 0 keeps the variant declared but never samples it, which
        is how you switch one off without deleting it.
        """
        unknown = set(weights) - set(self.names())
        if unknown:
            raise KeyError(
                f"axis '{self.name}': unknown variant(s) {sorted(unknown)}; "
                f"available: {', '.join(self.names())}"
            )

        return Axis(
            name=self.name,
            variants=tuple(
                replace(variant, weight=float(weights.get(variant.name, variant.weight)))
                for variant in self.variants
            ),
        )

    def eligible(self, tags: frozenset[str]) -> list[Variant]:
        return [
            variant
            for variant in self.variants
            if variant.weight > 0 and variant.eligible(tags)
        ]

    def sample(self, rng: random.Random, tags: frozenset[str] = frozenset()) -> Variant:
        candidates = self.eligible(tags)
        if not candidates:
            raise IncompatibleSpace(
                f"axis '{self.name}': no variant is eligible for tags {sorted(tags)}"
            )
        return rng.choices(
            candidates, weights=[variant.weight for variant in candidates], k=1
        )[0]


@dataclass(frozen=True)
class Scenario:
    """One fully resolved combination, and the seed that produced it."""

    index: int
    seed: int
    choices: dict[str, Variant]

    def __getitem__(self, axis: str) -> Variant:
        return self.choices[axis]

    @property
    def tags(self) -> frozenset[str]:
        return frozenset().union(*(v.tags for v in self.choices.values()))

    def key(self, axes: Iterable[str]) -> tuple:
        """Identity across the given axes -- used to reuse a render."""
        return tuple(self.choices[axis].name for axis in axes)

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "seed": self.seed,
            **{axis: variant.name for axis, variant in self.choices.items()},
        }


@dataclass(frozen=True)
class ScenarioSpace:
    """Axes in resolution order; earlier ones constrain later ones."""

    axes: tuple[Axis, ...]

    def __post_init__(self) -> None:
        if not self.axes:
            raise ValueError("a scenario space needs at least one axis")

    def axis(self, name: str) -> Axis:
        for axis in self.axes:
            if axis.name == name:
                return axis
        raise KeyError(f"no axis '{name}'; have {[a.name for a in self.axes]}")

    def axis_names(self) -> list[str]:
        return [axis.name for axis in self.axes]

    def with_weights(self, weights: dict[str, dict[str, float]]) -> ScenarioSpace:
        """Apply ``{axis: {variant: weight}}``, usually straight from YAML."""
        unknown = set(weights) - set(self.axis_names())
        if unknown:
            raise KeyError(
                f"unknown axis/axes {sorted(unknown)}; "
                f"available: {', '.join(self.axis_names())}"
            )

        return ScenarioSpace(
            axes=tuple(
                axis.with_weights(weights.get(axis.name, {})) for axis in self.axes
            )
        )

    # --------------------------------------------------------------- sampling

    def sample(self, rng: random.Random, index: int = 0, seed: int = 0) -> Scenario:
        """Resolve one scenario, honouring requires/tags as it goes."""
        choices: dict[str, Variant] = {}
        tags: frozenset[str] = frozenset()

        for axis in self.axes:
            variant = axis.sample(rng, tags)
            choices[axis.name] = variant
            tags = tags | variant.tags

        return Scenario(index=index, seed=seed, choices=choices)

    def combinations(self) -> Iterator[dict[str, Variant]]:
        """Every compatible combination, weights ignored (0-weight excluded)."""

        def walk(
            remaining: tuple[Axis, ...],
            chosen: dict[str, Variant],
            tags: frozenset[str],
        ) -> Iterator[dict[str, Variant]]:
            if not remaining:
                yield dict(chosen)
                return
            axis, rest = remaining[0], remaining[1:]
            for variant in axis.eligible(tags):
                chosen[axis.name] = variant
                yield from walk(rest, chosen, tags | variant.tags)
            chosen.pop(axis.name, None)

        yield from walk(self.axes, {}, frozenset())

    def count_combinations(self) -> int:
        return sum(1 for _ in self.combinations())

    def stratified(
        self, count: int, rng: random.Random, seed_base: int = 0
    ) -> list[Scenario]:
        """Cover every compatible combination before repeating any.

        i.i.d. sampling leaves rare combinations out entirely -- at 5000
        pages over 1500 combinations, a long tail simply never appears.
        This walks the full list in a shuffled order and wraps around.
        """
        combos = list(self.combinations())
        if not combos:
            raise IncompatibleSpace("no compatible combination in this space")

        rng.shuffle(combos)
        scenarios = []
        for index in range(count):
            choices = combos[index % len(combos)]
            scenarios.append(
                Scenario(
                    index=index,
                    seed=seed_for(seed_base, index),
                    choices=dict(choices),
                )
            )
        return scenarios


def seed_for(master_seed: int, index: int) -> int:
    """Per-page seed derived from the master, so any page is reproducible."""
    return (master_seed * 1_000_003 + index * 7_919) % (2**31 - 1)


def plan(
    space: ScenarioSpace,
    count: int,
    master_seed: int = 0,
    mode: str = "sample",
) -> list[Scenario]:
    """The full list of scenarios for a run, before anything is rendered."""
    if count <= 0:
        raise ValueError("count must be positive")

    rng = random.Random(master_seed)
    if mode == "stratified":
        return space.stratified(count, rng, seed_base=master_seed)
    if mode != "sample":
        raise ValueError(f"unknown sampling mode '{mode}' (sample | stratified)")

    return [
        space.sample(
            random.Random(seed_for(master_seed, index)),
            index=index,
            seed=seed_for(master_seed, index),
        )
        for index in range(count)
    ]


def realised_distribution(scenarios: list[Scenario]) -> dict[str, dict[str, int]]:
    """What the plan actually contains, per axis -- for ``--dry-run``."""
    counts: dict[str, dict[str, int]] = {}
    for scenario in scenarios:
        for axis, variant in scenario.choices.items():
            counts.setdefault(axis, {})
            counts[axis][variant.name] = counts[axis].get(variant.name, 0) + 1
    return counts
