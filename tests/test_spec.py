"""The sampler: loading, weighting, constraints, pinning."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from conftest import build_rules, write_rules_dir

from rulebase.spec import (
    ATTRIBUTES,
    Group,
    Option,
    RuleError,
    load_groups,
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


# ---------------------------------------------------------- parent nodes


def _grouped(root: Path, groups: list[dict], attribute: str = "layout") -> Path:
    """A rules directory where one attribute is sorted into nodes."""
    spec = {name: [{"id": f"{name}1", "weight": 1}] for name in ATTRIBUTES}
    spec.pop(attribute)
    root = write_rules_dir(root, spec, order=list(ATTRIBUTES))
    (root / f"{attribute}.yaml").write_text(
        yaml.safe_dump({"groups": groups}, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return root


def test_a_grouped_file_loads_as_a_flat_list_of_values(tmp_path):
    """The sampler never sees a node: it draws values, flattened in file order."""
    root = _grouped(tmp_path / "rules", [
        {"id": "till", "label": "giấy tính tiền", "options": [
            {"id": "a", "weight": 1}, {"id": "b", "weight": 1}]},
        {"id": "form", "label": "tờ mẫu", "options": [{"id": "c", "weight": 1}]},
    ])
    values = load_rules(root)["layout"]
    assert [option.id for option in values] == ["a", "b", "c"]
    assert [option.group for option in values] == ["till", "till", "form"]


def test_a_node_hands_its_constraints_to_every_value_under_it(tmp_path):
    """The point of the node: one constraint, not one per value."""
    root = _grouped(tmp_path / "rules", [
        {"id": "till", "tags": ["paper"], "excludes": ["invoice"],
         "options": [
             {"id": "a", "weight": 1, "tags": ["narrow"]},
             {"id": "b", "weight": 1, "requires": ["barcode"]},
         ]},
    ])
    by_id = {option.id: option for option in load_rules(root)["layout"]}
    assert by_id["a"].tags == frozenset({"paper", "narrow"})
    assert by_id["a"].excludes == frozenset({"invoice"})
    # Inherited and own constraints are merged, not replaced.
    assert by_id["b"].requires == frozenset({"barcode"})
    assert by_id["b"].excludes == frozenset({"invoice"})
    assert not by_id["b"].allowed({"invoice", "barcode"})
    assert by_id["b"].allowed({"barcode"})


def test_a_value_cannot_name_its_own_parent(tmp_path):
    # Structure decides which node a value is in. A `group:` key on the value
    # would let two nodes claim it and the file stop saying which.
    with pytest.raises(RuleError, match="unknown keys"):
        Option.from_dict({"id": "x", "group": "till"}, "layout")


def test_a_file_may_not_use_both_shapes(tmp_path):
    root = tmp_path / "rules"
    spec = {name: [{"id": f"{name}1", "weight": 1}] for name in ATTRIBUTES}
    spec.pop("layout")
    write_rules_dir(root, spec, order=list(ATTRIBUTES))
    (root / "layout.yaml").write_text(
        yaml.safe_dump({
            "options": [{"id": "loose", "weight": 1}],
            "groups": [{"id": "g", "options": [{"id": "inside", "weight": 1}]}],
        }, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    with pytest.raises(RuleError, match="both"):
        load_rules(root)


def test_an_empty_node_is_rejected(tmp_path):
    root = _grouped(tmp_path / "rules", [{"id": "till", "options": []}])
    with pytest.raises(RuleError, match="no options"):
        load_rules(root)


def test_two_nodes_may_not_share_an_id(tmp_path):
    root = _grouped(tmp_path / "rules", [
        {"id": "till", "options": [{"id": "a", "weight": 1}]},
        {"id": "till", "options": [{"id": "b", "weight": 1}]},
    ])
    with pytest.raises(RuleError, match="duplicate group id"):
        load_rules(root)


def test_a_node_carries_no_params(tmp_path):
    root = _grouped(tmp_path / "rules", [
        {"id": "till", "params": {"width": 40}, "options": [{"id": "a", "weight": 1}]},
    ])
    with pytest.raises(RuleError, match="unknown keys"):
        load_rules(root)


def test_load_groups_reports_the_nodes_with_their_labels(tmp_path):
    root = _grouped(tmp_path / "rules", [
        {"id": "till", "label": "giấy tính tiền", "options": [{"id": "a", "weight": 1}]},
    ])
    groups = load_groups(root)
    assert groups["layout"] == [Group(id="till", label="giấy tính tiền")]
    # An attribute listed flat has no nodes, and says so with an empty list
    # rather than by being absent.
    assert groups["document"] == []


def test_every_shipped_layout_belongs_to_a_node(real_rules):
    """A layout added outside the taxonomy is one nobody can classify."""
    nodes = {group.id for group in load_groups()["layout"]}
    assert nodes, "rules/layout.yaml no longer sorts its values into nodes"
    for option in real_rules["layout"]:
        assert option.group in nodes, f"{option.id} sits under no parent node"


def test_the_shipped_nodes_are_labelled():
    for attribute, groups in load_groups().items():
        for group in groups:
            assert group.label.strip(), f"{attribute}/{group.id} has no label"


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


# ------------------------------------------------------- the order manifest


def test_order_manifest_drives_the_attribute_list():
    from rulebase.spec import attribute_order

    assert tuple(ATTRIBUTES) == attribute_order()
    assert ATTRIBUTES[0] == "document", "document must be drawn first"
    assert ATTRIBUTES[-1] == "augmentation", "augmentation must be drawn last"


def test_a_rules_file_the_manifest_forgets_is_an_error(tmp_path):
    # The whole risk of auto-discovery: a hard-coded tuple cannot forget a
    # file, a directory listing can. Left unchecked this would be a new silent
    # failure -- the value simply never drawn -- which is the class of bug the
    # discovery was meant to remove, not add.
    spec = {attribute: [{"id": f"{attribute}0", "weight": 1}] for attribute in ATTRIBUTES}
    root = write_rules_dir(tmp_path / "rules", spec)
    (root / "orphan.yaml").write_text(
        yaml.safe_dump({"options": [{"id": "x", "weight": 1}]}), encoding="utf-8")
    with pytest.raises(RuleError, match="orphan"):
        load_rules(root)


def test_a_manifest_entry_without_a_file_is_an_error(tmp_path):
    spec = {attribute: [{"id": f"{attribute}0", "weight": 1}] for attribute in ATTRIBUTES}
    root = write_rules_dir(tmp_path / "rules", spec,
                           order=list(ATTRIBUTES) + ["ghost"])
    with pytest.raises(RuleError, match="ghost"):
        load_rules(root)


def test_a_repeated_manifest_entry_is_an_error(tmp_path):
    # Drawn twice, the second draw would see the first one's tags -- a value
    # excluding its own tag would become undrawable for reasons nobody could
    # find in the YAML.
    spec = {attribute: [{"id": f"{attribute}0", "weight": 1}] for attribute in ATTRIBUTES}
    root = write_rules_dir(tmp_path / "rules", spec,
                           order=list(ATTRIBUTES) + ["color"])
    with pytest.raises(RuleError, match="more than once"):
        load_rules(root)


def test_a_missing_manifest_is_an_error(tmp_path):
    root = tmp_path / "rules"
    root.mkdir()
    for attribute in ATTRIBUTES:
        (root / f"{attribute}.yaml").write_text(
            yaml.safe_dump({"options": [{"id": "x", "weight": 1}]}), encoding="utf-8")
    with pytest.raises(RuleError, match="_order.yaml"):
        load_rules(root)


def test_a_seventh_attribute_needs_no_python(tmp_path):
    """Adding a criterion is a YAML file and a manifest line."""
    spec = {attribute: [{"id": f"{attribute}0", "weight": 1}] for attribute in ATTRIBUTES}
    spec["binding"] = [{"id": "stapled", "weight": 1, "params": {"corner": "top_left"}}]
    root = write_rules_dir(tmp_path / "rules", spec)

    rules = load_rules(root)
    assert list(rules)[-1] == "binding", "the manifest decides the position"
    recipe = sample_recipe(seed=3, rules=rules)
    assert recipe.ids()["binding"] == "stapled"
    assert recipe.get("binding", "corner") == "top_left"
    assert "binding" in recipe.to_dict()["attributes"]


def test_the_sampler_follows_the_order_it_was_given(tmp_path):
    # Reversing the order must make a forward dependency unsatisfiable: proof
    # the order is honoured rather than merely stored.
    spec = {
        "document": [{"id": "d", "weight": 1, "tags": ["early"]}],
        "layout": [{"id": "l", "weight": 1, "requires": ["early"]}],
        **{attribute: [{"id": f"{attribute}0", "weight": 1}]
           for attribute in ("content", "visual", "color", "augmentation")},
    }
    forward = write_rules_dir(tmp_path / "fwd", spec)
    assert sample_recipe(seed=0, rules=load_rules(forward)).ids()["layout"] == "l"

    backward = write_rules_dir(
        tmp_path / "bwd", spec,
        order=["layout", "document", "content", "visual", "color", "augmentation"])
    with pytest.raises(RuleError, match="nothing satisfies"):
        sample_recipe(seed=0, rules=load_rules(backward))


# -------------------------------------------------- forcing is injective (W1b)


def test_forcing_maps_distinct_seeds_to_distinct_recipes(real_rules):
    """Law 7: deterministic was never the whole question. Is it one-to-one?

    Until W1b a clashing pin was handled by trying `seed + 1`, `seed + 2` until
    one fitted, so every seed in the gap returned the *same* recipe. Measured
    on the shipped rule-base, 2000 consecutive seeds gave 249 distinct results
    for `market_vat` and 837 for `eatery_ascii`, with runs of up to 36 seeds
    collapsing onto one. The shipped 60-image dataset therefore held 33
    receipts, not 60.

    Two hundred seeds is enough to catch it without slowing the suite: the old
    code gave 30 here for `market_vat` and 114 for the least affected layout.
    """
    from rulebase import available_layouts

    for layout in available_layouts():
        seeds = [sample_recipe(seed=k, rules=real_rules, force={"layout": layout}).seed
                 for k in range(200)]
        assert len(set(seeds)) == 200, (
            f"{layout}: {len(set(seeds))} distinct recipes from 200 seeds")


def test_a_forced_recipe_reports_the_seed_it_was_asked_for(real_rules):
    """Everything that rebuilds a page from `recipe.seed` depends on this."""
    from rulebase import available_layouts

    for layout in available_layouts():
        for seed in range(0, 200, 7):
            recipe = sample_recipe(seed=seed, rules=real_rules, force={"layout": layout})
            assert recipe.seed == seed


def test_a_forced_draw_is_still_deterministic(real_rules):
    for seed in range(0, 120, 3):
        first = sample_recipe(seed=seed, rules=real_rules, force={"layout": "market_vat"})
        second = sample_recipe(seed=seed, rules=real_rules, force={"layout": "market_vat"})
        assert first.ids() == second.ids()


def test_an_unforced_draw_never_needs_a_second_attempt(real_rules):
    """The re-draw loop must not touch the unforced path.

    Every committed dataset and the golden baseline were drawn without a pin,
    and `attempts=1` proves the loop returns on its first pass rather than
    quietly relying on retries.
    """
    for seed in range(200):
        sample_recipe(seed=seed, rules=real_rules, attempts=1)


def test_an_unlucky_seed_and_an_impossible_pin_say_different_things(constraint_rules):
    """The cap has to distinguish the two, or a caller cannot act on either."""
    # Legal, but this seed's first draw of `document` happened to block it.
    unlucky = None
    for seed in range(20):
        try:
            sample_recipe(seed=seed, rules=constraint_rules,
                          force={"layout": "needs_x"}, attempts=1)
        except RuleError as error:
            unlucky = str(error)
            break
    assert unlucky and "unlucky rather than impossible" in unlucky
    assert "tags at fault" in unlucky, unlucky

    # Impossible: `sets_y` never sets x, so no number of attempts will help.
    with pytest.raises(RuleError, match="cannot be drawn at all") as caught:
        sample_recipe(seed=0, rules=constraint_rules,
                      force={"document": "sets_y", "layout": "needs_x"})
    assert "tags at fault" in str(caught.value)


def test_a_legal_pin_is_found_however_unlucky_the_seed(constraint_rules):
    # Half the seeds draw `sets_y` first and must re-draw; none may fail.
    for seed in range(60):
        recipe = sample_recipe(seed=seed, rules=constraint_rules,
                               force={"layout": "needs_x"})
        assert recipe.ids() == {"document": "sets_x", "layout": "needs_x",
                                "content": "c1", "visual": "v1",
                                "color": "k1", "augmentation": "a1"}
        assert recipe.seed == seed


def test_a_weight_zero_option_cannot_rescue_an_impossible_pin():
    """Reachability must ignore what the sampler will never draw.

    A value with weight 0 is switched off, so the tag it would have set is not
    available to anything -- counting it would report a pin as reachable that
    no draw can ever reach.
    """
    rules = build_rules({
        "document": [{"id": "off", "weight": 0, "tags": ["x"]},
                     {"id": "on", "weight": 1, "tags": ["y"]}],
        "layout": [{"id": "needs_x", "weight": 1, "requires": ["x"]}],
        **{attribute: [{"id": f"{attribute}0", "weight": 1}]
           for attribute in ("content", "visual", "color", "augmentation")},
    })
    with pytest.raises(RuleError, match="cannot be drawn at all"):
        sample_recipe(seed=0, rules=rules, force={"layout": "needs_x"})


def test_an_unforced_failure_is_reported_directly_not_as_an_unlucky_seed():
    """Without a pin there is nothing to re-draw around, so retrying is wrong.

    Not merely slower: a rule-base with an unreachable attribute would be
    reported as "this seed is unlucky, try another", which sends a reader
    looking for a seed that does not exist instead of at the rules.
    """
    rules = build_rules({
        "document": [{"id": "d", "weight": 1, "tags": ["x"]}],
        "layout": [{"id": "l", "weight": 1, "excludes": ["x"]}],
        **{attribute: [{"id": f"{attribute}0", "weight": 1}]
           for attribute in ("content", "visual", "color", "augmentation")},
    })
    with pytest.raises(RuleError) as caught:
        sample_recipe(seed=0, rules=rules)
    message = str(caught.value)
    assert message.startswith("layout: nothing satisfies"), message
    assert "unlucky" not in message and "last clash" not in message, message
