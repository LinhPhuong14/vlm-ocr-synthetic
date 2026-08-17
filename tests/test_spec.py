"""The sampler: loading, weighting, constraints, pinning."""

from __future__ import annotations

import pytest
import yaml
from conftest import build_rules, write_rules_dir

from rulebase.spec import (
    ATTRIBUTES,
    Option,
    RuleError,
    load_rules,
    parse_force,
    sample_recipe,
    validate,
)

# --------------------------------------------------------------- loading


def test_load_rules_reads_every_attribute(real_rules):
    assert set(real_rules) == set(ATTRIBUTES)
    for attribute in ATTRIBUTES:
        assert real_rules[attribute], f"{attribute} has no options"


def test_duplicate_id_is_rejected(tmp_path):
    root = write_rules_dir(tmp_path / "rules", {
        attribute: [{"id": "same", "weight": 1}, {"id": "same", "weight": 1}]
        for attribute in ATTRIBUTES
    })
    with pytest.raises(RuleError, match="duplicate"):
        load_rules(root)


def test_unknown_key_is_rejected():
    # The mistake this guards is real and silent: writing `font_size: [22, 30]`
    # at the option's top level instead of under `params:`. Without the check
    # the key is simply ignored and the value renders with defaults.
    with pytest.raises(RuleError, match="unknown keys"):
        Option.from_dict({"id": "x", "font_size": [22, 30]}, "visual")


def test_missing_id_is_rejected():
    with pytest.raises(RuleError, match="no id"):
        Option.from_dict({"weight": 1}, "visual")


def test_negative_weight_is_rejected():
    with pytest.raises(RuleError, match="negative weight"):
        Option.from_dict({"id": "x", "weight": -1}, "visual")


def test_missing_file_is_reported(tmp_path):
    (tmp_path / "rules").mkdir()
    with pytest.raises(RuleError, match="missing rules file"):
        load_rules(tmp_path / "rules")


def test_empty_options_is_rejected(tmp_path):
    root = tmp_path / "rules"
    root.mkdir()
    for attribute in ATTRIBUTES:
        (root / f"{attribute}.yaml").write_text(
            yaml.safe_dump({"options": []}), encoding="utf-8")
    with pytest.raises(RuleError, match="no options"):
        load_rules(root)


# ------------------------------------------------------------ determinism


def test_same_seed_gives_the_same_recipe(real_rules):
    first = sample_recipe(seed=1234, rules=real_rules)
    second = sample_recipe(seed=1234, rules=real_rules)
    assert first.ids() == second.ids()
    assert first.tags == second.tags


def test_different_seeds_eventually_differ(real_rules):
    # Not a distribution test -- just that the seed is actually threaded
    # through, which a stray `random.random()` would break.
    ids = {tuple(sample_recipe(seed=s, rules=real_rules).ids().items()) for s in range(30)}
    assert len(ids) > 1


# ------------------------------------------------------------ constraints


def test_requires_and_excludes_decide_what_is_drawable(constraint_rules):
    for seed in range(40):
        recipe = sample_recipe(seed=seed, rules=constraint_rules)
        document, layout = recipe.ids()["document"], recipe.ids()["layout"]
        if document == "sets_x":
            assert layout == "needs_x", "excludes did not block hates_x after tag x"
        else:
            assert layout == "hates_x", "requires did not block needs_x without tag x"


def test_no_candidate_left_is_an_error():
    rules = build_rules({
        "document": [{"id": "d", "weight": 1, "tags": ["x"]}],
        "layout": [{"id": "l", "weight": 1, "excludes": ["x"]}],
        "content": [{"id": "c", "weight": 1}],
        "visual": [{"id": "v", "weight": 1}],
        "color": [{"id": "k", "weight": 1}],
        "augmentation": [{"id": "a", "weight": 1}],
    })
    with pytest.raises(RuleError, match="nothing satisfies"):
        sample_recipe(seed=0, rules=rules)


def test_all_zero_weights_is_an_error():
    rules = build_rules({
        attribute: [{"id": f"{attribute}0", "weight": 0}] for attribute in ATTRIBUTES
    })
    with pytest.raises(RuleError, match="weight 0"):
        sample_recipe(seed=0, rules=rules)


def test_weight_zero_is_never_drawn():
    rules = build_rules({
        "document": [{"id": "never", "weight": 0}, {"id": "always", "weight": 5}],
        **{attribute: [{"id": f"{attribute}0", "weight": 1}]
           for attribute in ATTRIBUTES if attribute != "document"},
    })
    drawn = {sample_recipe(seed=s, rules=rules).ids()["document"] for s in range(60)}
    assert drawn == {"always"}


# ---------------------------------------------------------------- forcing


def test_force_pins_the_value(real_rules):
    recipe = sample_recipe(seed=7, rules=real_rules, force={"augmentation": "pristine"})
    assert recipe.ids()["augmentation"] == "pristine"


def test_force_unknown_attribute_is_rejected(real_rules):
    with pytest.raises(RuleError, match="unknown attribute"):
        sample_recipe(seed=1, rules=real_rules, force={"nonsense": "x"})


def test_force_unknown_value_is_rejected(real_rules):
    with pytest.raises(RuleError, match="no option"):
        sample_recipe(seed=1, rules=real_rules, force={"augmentation": "no_such_value"})


def test_force_that_violates_requires_names_the_blocking_tag(constraint_rules):
    # The message has to name the tag, not just say no. A pinned value that
    # silently fell back to a legal one would produce a dataset that quietly
    # disagrees with the flag that asked for it.
    with pytest.raises(RuleError) as caught:
        sample_recipe(seed=0, rules=constraint_rules,
                      force={"document": "sets_y", "layout": "needs_x"})
    assert "x" in str(caught.value)
    assert "tags at fault" in str(caught.value)


def test_parse_force_round_trip():
    assert parse_force(["augmentation=pristine", "visual=laser_sharp"]) == {
        "augmentation": "pristine", "visual": "laser_sharp"}
    assert parse_force([]) is None
    assert parse_force(None, layout="market_vat") == {"layout": "market_vat"}


def test_parse_force_rejects_bad_input():
    with pytest.raises(RuleError, match="ATTR=ID"):
        parse_force(["augmentation"])
    with pytest.raises(RuleError, match="unknown attribute"):
        parse_force(["nonsense=x"])


# --------------------------------------------------------------- the rules


def test_shipped_rules_validate(real_rules):
    assert validate(real_rules) == []


def test_validate_catches_a_tag_nobody_sets():
    rules = build_rules({
        "document": [{"id": "d", "weight": 1, "tags": ["x"]}],
        "layout": [{"id": "l", "weight": 1, "requires": ["typo_tag"]}],
        **{attribute: [{"id": f"{attribute}0", "weight": 1}]
           for attribute in ("content", "visual", "color", "augmentation")},
    })
    problems = validate(rules)
    assert any("typo_tag" in problem for problem in problems)


def test_validate_catches_a_backwards_dependency():
    # `document` is drawn first, so requiring a tag that only `layout` sets can
    # never be satisfied -- the causal order is load-bearing, not decorative.
    rules = build_rules({
        "document": [{"id": "d", "weight": 1, "requires": ["late"]}],
        "layout": [{"id": "l", "weight": 1, "tags": ["late"]}],
        **{attribute: [{"id": f"{attribute}0", "weight": 1}]
           for attribute in ("content", "visual", "color", "augmentation")},
    })
    assert any("late" in problem for problem in validate(rules))


def test_recipe_to_dict_carries_seed_and_every_attribute(real_rules):
    recipe = sample_recipe(seed=99, rules=real_rules)
    payload = recipe.to_dict()
    assert payload["seed"] == 99
    assert set(payload["attributes"]) == set(ATTRIBUTES)
    assert payload["tags"] == sorted(recipe.tags)
