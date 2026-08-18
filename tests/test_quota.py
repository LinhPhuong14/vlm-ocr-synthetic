"""Allocating a run over the hierarchy: the arithmetic, and the reason for it.

`pipeline.quota` is pure -- ids in, counts out -- so these tests use invented
type names rather than the shipped tree. What is being checked is the
apportionment, not the twelve families.
"""

from __future__ import annotations

import pytest

from pipeline.quota import (
    QuotaError,
    allocate,
    even_split,
    rule_weights,
    strata,
)

WIDE = [f"business.b{i}" for i in range(16)]
NARROW = [f"log.l{i}" for i in range(6)]


def by_family(pairs):
    found: dict[str, int] = {}
    for node_id, count in pairs:
        found[node_id.split(".")[0]] = found.get(node_id.split(".")[0], 0) + count
    return found


@pytest.mark.parametrize("balance", ["family", "equal", "weight"])
def test_every_image_is_allocated_and_none_invented(balance):
    for total in (0, 1, 7, 20, 101, 5000):
        pairs = allocate(total, WIDE + NARROW, balance)
        assert sum(count for _id, count in pairs) == total, (balance, total)
        assert [node_id for node_id, _ in pairs] == WIDE + NARROW


def test_family_balance_ignores_how_branchy_a_family_is():
    """The reason `family` is the default.

    Sixteen business types and six log types is a fact about how the tree was
    drawn, not about how common the documents are. Splitting over the leaves
    would hand business 73% of a dataset for that reason alone.
    """
    assert by_family(allocate(220, WIDE + NARROW, "family")) == {"business": 110, "log": 110}
    assert by_family(allocate(220, WIDE + NARROW, "equal")) == {"business": 160, "log": 60}


def test_weight_balance_reproduces_the_mix_the_rules_describe():
    weights = {"business.b0": 3.0, "business.b1": 1.0}
    assert allocate(100, ["business.b0", "business.b1"], "weight", weights) == [
        ("business.b0", 75), ("business.b1", 25)]


def test_a_type_the_weights_do_not_mention_still_gets_a_share():
    """A partially weighted config is a whole allocation, not a broken one."""
    pairs = dict(allocate(100, ["a.x", "a.y"], "weight", {"a.x": 1.0}))
    assert sum(pairs.values()) == 100 and all(count > 0 for count in pairs.values())


def test_allocation_is_deterministic_including_the_remainder():
    for balance in ("family", "equal", "weight"):
        first = allocate(97, WIDE + NARROW, balance)
        assert first == allocate(97, WIDE + NARROW, balance)


def test_a_run_too_small_for_the_slice_reports_zeros_rather_than_dropping_types():
    """5 images over 22 types cannot cover them; the caller has to be able to say so."""
    pairs = allocate(5, WIDE + NARROW, "equal")
    assert sum(count for _id, count in pairs) == 5
    assert len([node_id for node_id, count in pairs if count == 0]) == 17


def test_even_split_puts_the_remainder_at_the_front():
    assert even_split(7, 3) == [3, 2, 2]
    assert even_split(0, 3) == [0, 0, 0]
    assert even_split(3, 0) == []


@pytest.mark.parametrize("bad, expected", [
    ((10, [], "equal"), "no document types"),
    ((10, ["a.x"], "alphabetical"), "expected one of"),
    ((-1, ["a.x"], "equal"), "cannot allocate"),
])
def test_an_impossible_request_is_refused(bad, expected):
    with pytest.raises(QuotaError, match=expected):
        allocate(*bad)


# ------------------------------------------------------------------ strata


def test_a_types_images_are_spread_over_the_layouts_it_can_legally_have():
    layouts = {"a.x": ["one", "two"], "a.y": ["three"]}
    assert strata(["a.x", "a.y"], [5, 4], layouts.get) == [
        ("a.x", "one", 3), ("a.x", "two", 2), ("a.y", "three", 4)]


def test_a_type_with_no_drawable_layout_is_an_error_not_a_short_dataset():
    """Rules that realise a type no layout admits is a rule-base bug.

    Skipping it would produce a dataset quietly missing a type it claims, which
    is the failure mode this repository keeps designing against.
    """
    with pytest.raises(QuotaError, match="no layout"):
        strata(["a.x"], [5], lambda _node_id: [])


def test_a_type_allocated_nothing_produces_no_strata():
    assert strata(["a.x"], [0], lambda _n: ["one"]) == []


def test_rule_weights_add_up_the_values_that_produce_each_type():
    from rulebase.spec import Option

    rules = {"document": [
        Option.from_dict({"id": "a", "weight": 3, "doc_type": "x.one"}, "document"),
        Option.from_dict({"id": "b", "weight": 2, "doc_type": "x.one"}, "document"),
        Option.from_dict({"id": "c", "weight": 4, "doc_type": "x.two"}, "document"),
        Option.from_dict({"id": "d", "weight": 0, "doc_type": "x.three"}, "document"),
        Option.from_dict({"id": "e", "weight": 9}, "document"),
    ]}
    # weight 0 means never drawn, so it contributes nothing and a value with no
    # doc_type is not a document type at all.
    assert rule_weights(rules) == {"x.one": 5.0, "x.two": 4.0}


# ------------------------------------------- the shipped rules and tree


def test_the_shipped_types_each_have_at_least_one_layout():
    """Every generatable type must be drawable, which `strata` would otherwise raise on."""
    import rulebase
    from rulebase.documents import coverage

    ready = [node_id for node_id, state in coverage().items() if state["generatable"]]
    for node_id in ready:
        assert rulebase.reachable_options("layout", doc_type=node_id), node_id


def test_a_run_selects_only_types_it_can_actually_generate():
    from pipeline.config import Config
    from pipeline.quota import select_types

    config = Config.from_dict({
        "run": {"out": "/tmp/x", "per_backend": 20},
        "backends": ["html"],
        "taxonomy": {"include": ["business.receipt"]},
    })
    selected, skipped = select_types(config)
    assert sum(count for _id, count in selected) == 20
    # The receipt branch holds four types and two of them have no rules yet;
    # they are reported rather than silently dropped.
    assert set(skipped) == {"business.receipt.payment", "business.receipt.atm"}


def test_asking_for_one_unbuilt_type_by_name_is_refused():
    """Asking for prescriptions and quietly getting receipts is the worst answer."""
    from pipeline.config import Config
    from pipeline.quota import select_types

    config = Config.from_dict({
        "run": {"out": "/tmp/x", "per_backend": 20},
        "backends": ["html"],
        "taxonomy": {"include": ["prescription"]},
    })
    with pytest.raises(QuotaError, match="cannot be generated yet"):
        select_types(config)
