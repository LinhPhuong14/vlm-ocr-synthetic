"""The scenario space: weights, compatibility, reproducibility.

A combinatorial space fails in ways a single render never does -- a weight
typo silently changes the dataset, an incompatible pair slips through, a
rare combination never appears. These tests cover exactly that.
"""

from __future__ import annotations

import random
from collections import Counter

import pytest

from vlm_ocr_synthetic.variations import (
    BACKEND_AXIS,
    DEGRADATION_AXIS,
    LAYOUT_AXIS,
    STYLE_AXIS,
    default_space,
)
from vlm_ocr_synthetic.variations.space import (
    Axis,
    IncompatibleSpace,
    ScenarioSpace,
    Variant,
    plan,
    realised_distribution,
    seed_for,
)


@pytest.fixture
def toy_space() -> ScenarioSpace:
    paper = Axis(
        "paper",
        (
            Variant("wide", weight=1, tags=frozenset({"wide"})),
            Variant("narrow", weight=1, tags=frozenset({"narrow"})),
        ),
    )
    style = Axis(
        "style",
        (
            Variant("big", weight=1, requires=frozenset({"wide"})),
            Variant("small", weight=1),
        ),
    )
    return ScenarioSpace(axes=(paper, style))


# ------------------------------------------------------------------- axes


def test_duplicate_variant_names_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        Axis("x", (Variant("a"), Variant("a")))


def test_unknown_variant_in_weights_is_a_typo_not_a_no_op():
    with pytest.raises(KeyError, match="thermal_18"):
        STYLE_AXIS.with_weights({"thermal_18": 3})


def test_zero_weight_keeps_the_variant_but_never_samples_it():
    axis = LAYOUT_AXIS.with_weights({name: 0 for name in LAYOUT_AXIS.names()[1:]})
    keep = LAYOUT_AXIS.names()[0]

    assert len(axis.variants) == len(LAYOUT_AXIS.variants)
    rng = random.Random(0)
    assert {axis.sample(rng).name for _ in range(20)} == {keep}


def test_weights_are_respected_within_sampling_noise():
    axis = Axis(
        "x", (Variant("common", weight=9), Variant("rare", weight=1))
    )
    rng = random.Random(4)
    counts = Counter(axis.sample(rng).name for _ in range(4000))

    assert counts["common"] / 4000 == pytest.approx(0.9, abs=0.03)


def test_sampling_with_no_eligible_variant_raises(toy_space):
    style = toy_space.axis("style")
    with pytest.raises(IncompatibleSpace):
        Axis("style", (style.get("big"),)).sample(random.Random(0), frozenset())


# ----------------------------------------------------------- compatibility


def test_requires_is_honoured_when_sampling(toy_space):
    rng = random.Random(0)
    for index in range(200):
        scenario = toy_space.sample(rng, index=index)
        if scenario["paper"].name == "narrow":
            assert scenario["style"].name == "small"


def test_combinations_only_lists_compatible_pairs(toy_space):
    combos = {
        (choice["paper"].name, choice["style"].name)
        for choice in toy_space.combinations()
    }
    assert combos == {("wide", "big"), ("wide", "small"), ("narrow", "small")}


def test_narrow_paper_never_gets_a_wide_only_style():
    """58mm receipts must not be sampled with an 80mm-sized font."""
    space = default_space()
    rng = random.Random(7)
    wide_only = {
        variant.name
        for variant in STYLE_AXIS.variants
        if "wide_thermal" in variant.requires
    }
    assert wide_only  # the constraint exists at all

    for index in range(300):
        scenario = space.sample(rng, index=index)
        if "narrow" in scenario["layout"].tags:
            assert scenario["style"].name not in wide_only


def test_absolute_layout_only_for_documents_that_pin_their_blocks():
    space = default_space()
    rng = random.Random(3)

    for index in range(300):
        scenario = space.sample(rng, index=index)
        if scenario["backend"].name == "html-absolute":
            assert "pinned" in scenario["layout"].tags


def test_every_axis_has_at_least_one_variant_per_layout():
    """No layout may be a dead end for the axes that follow it."""
    space = default_space()

    for layout in LAYOUT_AXIS.variants:
        tags = layout.tags
        for axis in (BACKEND_AXIS, STYLE_AXIS, DEGRADATION_AXIS):
            assert axis.eligible(tags), f"{layout.name} has no {axis.name}"
            tags = tags | axis.eligible(tags)[0].tags


# ------------------------------------------------------ plans and seeding


def test_seed_is_derived_from_the_master_and_the_index():
    assert seed_for(1234, 0) != seed_for(1234, 1)
    assert seed_for(1234, 7) == seed_for(1234, 7)
    assert seed_for(1, 7) != seed_for(2, 7)


def test_the_same_master_seed_plans_the_same_run():
    space = default_space()
    first = plan(space, 50, master_seed=99)
    second = plan(space, 50, master_seed=99)
    other = plan(space, 50, master_seed=100)

    assert [s.as_dict() for s in first] == [s.as_dict() for s in second]
    assert [s.as_dict() for s in first] != [s.as_dict() for s in other]


def test_stratified_covers_every_combination_before_repeating(toy_space):
    scenarios = toy_space.stratified(3, random.Random(0))
    combos = {(s["paper"].name, s["style"].name) for s in scenarios}

    assert len(combos) == 3 == toy_space.count_combinations()


def test_sampling_alone_can_miss_rare_combinations(toy_space):
    """Why stratified mode exists."""
    skewed = ScenarioSpace(
        axes=(
            toy_space.axis("paper").with_weights({"wide": 1000, "narrow": 1}),
            toy_space.axis("style"),
        )
    )
    sampled = plan(skewed, 30, master_seed=0, mode="sample")
    assert {s["paper"].name for s in sampled} == {"wide"}  # narrow never drawn

    stratified = plan(skewed, 30, master_seed=0, mode="stratified")
    assert {s["paper"].name for s in stratified} == {"wide", "narrow"}


def test_unknown_mode_is_rejected(toy_space):
    with pytest.raises(ValueError, match="stratified"):
        plan(toy_space, 5, mode="uniform")


def test_realised_distribution_counts_every_axis(toy_space):
    scenarios = plan(toy_space, 40, master_seed=1)
    counts = realised_distribution(scenarios)

    assert set(counts) == {"paper", "style"}
    assert sum(counts["paper"].values()) == 40


def test_space_rejects_unknown_axis_in_weights():
    with pytest.raises(KeyError, match="degredation"):
        default_space().with_weights({"degredation": {"clean": 1}})


def test_shipped_space_has_the_promised_size():
    space = default_space()

    assert space.axis_names() == ["layout", "backend", "style", "degradation"]
    assert len(LAYOUT_AXIS.variants) == 10
    assert len(STYLE_AXIS.variants) == 15
    assert len(DEGRADATION_AXIS.variants) == 10
    assert space.count_combinations() > 500
