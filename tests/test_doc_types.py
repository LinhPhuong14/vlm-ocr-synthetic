"""The join between the rule-base and the hierarchy.

`doc_type` on a rules value is the only thing connecting "what the sampler
draws" to "what the label says this is". These tests cover the three ways it is
used -- narrowing a draw, planning a run, labelling an image -- and the ways it
can be wrong.
"""

from __future__ import annotations

import json

import pytest
import yaml
from conftest import build_rules, write_rules_dir

import rulebase
import taxonomy
from rulebase.spec import RuleError, load_rules, sample_recipe, validate_doc_types

READY = "business.receipt.retail"
OTHER = "business.receipt.restaurant"


# ------------------------------------------------------- pinning a type


@pytest.mark.parametrize("query", ["retail", "receipt.retail", READY])
def test_a_type_can_be_asked_for_by_any_unambiguous_name(query):
    recipe = sample_recipe(seed=11, doc_type=query)
    assert recipe.doc_type == READY


def test_pinning_a_type_narrows_the_draw_and_nothing_else():
    """Asking for a retail receipt must not decide what paper it is printed on."""
    seen_visual = {sample_recipe(seed=seed, doc_type=READY).visual.id for seed in range(40)}
    assert len(seen_visual) > 1
    assert all(sample_recipe(seed=seed, doc_type=READY).doc_type == READY
               for seed in range(40))


def test_two_seeds_with_one_pinned_type_are_still_two_documents():
    """The many-to-one bug `sample_recipe` documents, in its doc_type form."""
    texts = {rulebase.make(seed=seed, doc_type=READY)[1].text_sequence()
             for seed in range(30)}
    assert len(texts) == 30


def test_a_type_nothing_realises_says_so_rather_than_drawing_something_else():
    with pytest.raises(RuleError, match="no value realises"):
        sample_recipe(seed=1, doc_type="medical.prescription")


def test_a_type_that_is_not_in_the_hierarchy_is_a_taxonomy_error():
    with pytest.raises(taxonomy.TaxonomyError, match="no document type"):
        sample_recipe(seed=1, doc_type="business.receipt.hovercraft")


def test_an_ambiguous_name_is_refused_rather_than_guessed():
    with pytest.raises(taxonomy.TaxonomyError, match="matches 2 types"):
        sample_recipe(seed=1, doc_type="certificate")


def test_pinning_a_type_and_a_contradicting_value_is_refused():
    """`--doc retail --force document=pub_eatery` is two different requests."""
    with pytest.raises(RuleError, match="asked for"):
        sample_recipe(seed=1, doc_type=READY, force={"document": "pub_eatery"})


def test_a_value_and_a_type_that_agree_are_fine():
    recipe = sample_recipe(seed=1, doc_type=READY, force={"document": "supermarket"})
    assert recipe.document.id == "supermarket" and recipe.doc_type == READY


# ------------------------------------------------------------- the label


def test_the_label_carries_the_type_the_recipe_drew():
    for seed in range(20):
        recipe, receipt, _grid = rulebase.make(seed=seed)
        assert receipt.ground_truth()["doc_type"] == recipe.doc_type


def test_the_recipe_records_the_type_for_the_provenance_file():
    recipe = sample_recipe(seed=3)
    assert recipe.to_dict()["doc_type"] == recipe.doc_type


def test_a_migrated_label_is_what_a_fresh_run_would_have_written():
    """The property that makes migrating a committed dataset trustworthy.

    `tools/migrate_labels.py` rewrites the classification block of an old label
    in place -- the images are untouched because the type is never printed on
    the page. That is only sound if the result is indistinguishable from a label
    generated today, so it is checked rather than asserted in a docstring.
    """
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
    from migrate_labels import LEGACY, migrate_parse

    tree = taxonomy.tree()
    legacy_name = {value: key for key, value in LEGACY.items()}
    for seed in range(10):
        _recipe, receipt, _grid = rulebase.make(seed=seed)
        fresh = receipt.ground_truth()
        # An old label: the invented name, and no family or path beside it.
        old = {"doc_type": legacy_name[fresh["doc_type"]],
               **{k: v for k, v in fresh.items()
                  if k not in ("doc_type", "doc_family", "doc_path")}}
        migrated, changed = migrate_parse(old, tree)
        assert changed
        assert json.dumps(migrated, sort_keys=False, ensure_ascii=False) == \
            json.dumps(fresh, sort_keys=False, ensure_ascii=False)


# ------------------------------------------------------ rules validation


def _rules_with(doc_type: str):
    return build_rules({
        "document": [{"id": "a", "doc_type": doc_type}],
        "layout": [{"id": "b"}],
        "content": [{"id": "c"}],
        "visual": [{"id": "d"}],
        "color": [{"id": "e"}],
        "augmentation": [{"id": "f"}],
    })


@pytest.mark.parametrize("doc_type, expected", [
    ("business.receipt.hovercraft", "not in the hierarchy"),
    ("business.receipt", "is a branch"),
    ("academic.certificate", "is an alias"),
    ("medical.prescription", "still marked planned"),
])
def test_a_value_pointing_at_the_wrong_kind_of_node_is_reported(doc_type, expected):
    problems = validate_doc_types(_rules_with(doc_type))
    assert any(expected in problem for problem in problems), problems


def test_the_shipped_rules_and_the_shipped_tree_agree():
    assert validate_doc_types(load_rules()) == []


# ------------------------------------------- an attribute split into files


def test_an_attribute_may_be_a_directory_of_files(tmp_path):
    """How `rules/document/` scales: one file per family, ids unique across them."""
    root = write_rules_dir(tmp_path / "rules", {
        "layout": [{"id": "b"}], "content": [{"id": "c"}], "visual": [{"id": "d"}],
        "color": [{"id": "e"}], "augmentation": [{"id": "f"}],
    }, order=["document", "layout", "content", "visual", "color", "augmentation"])
    (root / "document.yaml").unlink(missing_ok=True)
    directory = root / "document"
    directory.mkdir()
    (directory / "one.yaml").write_text(
        yaml.safe_dump({"options": [{"id": "alpha"}]}), encoding="utf-8")
    (directory / "two.yaml").write_text(
        yaml.safe_dump({"options": [{"id": "beta"}]}), encoding="utf-8")

    rules = load_rules(root)
    assert [option.id for option in rules["document"]] == ["alpha", "beta"]


def test_the_same_id_in_two_family_files_is_refused(tmp_path):
    """Otherwise which one you get depends on which filename sorts first."""
    root = write_rules_dir(tmp_path / "rules", {
        "layout": [{"id": "b"}], "content": [{"id": "c"}], "visual": [{"id": "d"}],
        "color": [{"id": "e"}], "augmentation": [{"id": "f"}],
    }, order=["document", "layout", "content", "visual", "color", "augmentation"])
    (root / "document.yaml").unlink(missing_ok=True)
    directory = root / "document"
    directory.mkdir()
    for name in ("one.yaml", "two.yaml"):
        (directory / name).write_text(
            yaml.safe_dump({"options": [{"id": "alpha"}]}), encoding="utf-8")

    with pytest.raises(RuleError, match="duplicate option id"):
        load_rules(root)


def test_a_file_and_a_directory_for_one_attribute_is_refused(tmp_path):
    root = write_rules_dir(tmp_path / "rules", {
        "document": [{"id": "a"}], "layout": [{"id": "b"}], "content": [{"id": "c"}],
        "visual": [{"id": "d"}], "color": [{"id": "e"}], "augmentation": [{"id": "f"}],
    })
    (root / "document").mkdir()
    (root / "document" / "extra.yaml").write_text(
        yaml.safe_dump({"options": [{"id": "z"}]}), encoding="utf-8")
    with pytest.raises(RuleError, match="keep one"):
        load_rules(root)


# --------------------------------------------------- which layouts a type has


def test_a_type_only_offers_the_layouts_its_rules_allow():
    """Pinning a supermarket layout on a restaurant receipt fails deep in a run.

    Computed statically from the rules so a planner can avoid the pair entirely,
    which is what `pipeline.quota.strata` does.
    """
    retail = {option.id for option in rulebase.reachable_options("layout", doc_type=READY)}
    restaurant = {option.id for option in rulebase.reachable_options("layout", doc_type=OTHER)}
    assert retail and restaurant
    assert not (retail & restaurant), "a layout claimed by both types"
    assert retail | restaurant <= set(rulebase.available_layouts())


def test_without_a_type_every_declared_layout_is_reachable():
    assert {option.id for option in rulebase.reachable_options("layout")} == \
        set(rulebase.available_layouts())
