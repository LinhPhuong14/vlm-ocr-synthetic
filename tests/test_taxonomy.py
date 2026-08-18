"""The document hierarchy: it loads, it refuses to load wrong, and it agrees
with the rules.

Two kinds of test here, kept apart on purpose. Anything about the *mechanism* --
inheritance, aliases, resolution -- builds its own little tree in a temporary
directory, so an editorial change to `taxonomy/families/` cannot turn it red.
Anything about the *shipped* tree is a check on the twelve families as they
stand, and is supposed to go red when someone edits them into an inconsistent
state. That is the same split `conftest.py` describes for the rule-base.
"""

from __future__ import annotations

import pytest
import yaml

import taxonomy
from taxonomy import Taxonomy, TaxonomyError

ROOT = {
    "version": "9.9",
    "root": {"name": "Document", "name_vi": "Tài liệu"},
    "statuses": {"ready": "y", "draft": "m", "planned": "n"},
    "engines": {"grid": {"name": "Grid", "built": True},
                "flow": {"name": "Flow", "built": False}},
}


def write_tree(root, families: list[dict], meta: dict | None = None) -> "Taxonomy":
    """A hierarchy on disk, loaded. Every mechanism test starts here."""
    (root / "families").mkdir(parents=True, exist_ok=True)
    (root / "document.yaml").write_text(
        yaml.safe_dump(meta or ROOT, allow_unicode=True), encoding="utf-8")
    for index, family in enumerate(families):
        (root / "families" / f"{index:02d}-{family['id']}.yaml").write_text(
            yaml.safe_dump(family, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return taxonomy.load(root)


def family(id_, number, children, **extra):
    return {"id": id_, "number": number, "name": id_.title(), "name_vi": id_,
            "engine": "grid", "status": "planned", "children": children, **extra}


# ------------------------------------------------------------- mechanism


def test_a_child_inherits_status_and_engine_from_its_family(tmp_path):
    tree = write_tree(tmp_path, [family("alpha", 1, [
        {"id": "one", "name": "One", "name_vi": "một"},
        {"id": "two", "name": "Two", "name_vi": "hai", "engine": "flow", "status": "ready"},
    ])])
    assert tree.node("alpha.one").engine == "grid"
    assert tree.node("alpha.one").status == "planned"
    # A leaf may disagree with its family: family 3 in the shipped tree is
    # `card` overall and holds two `flow` documents.
    assert tree.node("alpha.two").engine == "flow"
    assert tree.node("alpha.two").status == "ready"


def test_depth_varies_between_branches(tmp_path):
    """Family 1 has a level the other eleven do not, and ids stay honest."""
    tree = write_tree(tmp_path, [family("alpha", 1, [
        {"id": "mid", "name": "Mid", "name_vi": "giữa", "children": [
            {"id": "deep", "name": "Deep", "name_vi": "sâu"}]},
        {"id": "flat", "name": "Flat", "name_vi": "phẳng"},
    ])])
    assert [n.id for n in tree.leaves()] == ["alpha.mid.deep", "alpha.flat"]
    assert tree.node("alpha.mid.deep").depth == 3
    assert tree.node("alpha.flat").depth == 2
    assert tree.node("alpha.mid.deep").names == ("Alpha", "Mid", "Deep")


def test_an_alias_is_one_document_filed_twice(tmp_path):
    tree = write_tree(tmp_path, [
        family("alpha", 1, [{"id": "thing", "name": "Thing", "name_vi": "vật",
                             "status": "ready", "engine": "flow"}]),
        family("beta", 2, [{"id": "thing", "name": "Thing",
                            "same_as": "alpha.thing"}]),
    ])
    alias = tree.node("beta.thing")
    # Everything but its place in the tree comes from the canonical node, so
    # there is one answer to "can we generate a Thing".
    assert alias.same_as == "alpha.thing"
    assert (alias.name_vi, alias.status, alias.engine) == ("vật", "ready", "flow")
    assert tree.canonical("beta.thing").id == "alpha.thing"
    # And it is not counted twice: a quota over the leaves must not generate it
    # once per filing.
    assert [n.id for n in tree.leaves()] == ["alpha.thing"]
    assert len(tree.leaves(aliases=True)) == 2


@pytest.mark.parametrize("second, expected", [
    ({"id": "thing", "name": "Thing", "name_vi": "vật2"}, "same document filed twice"),
    ({"id": "thing", "name": "Thing", "same_as": "alpha.nope"}, "does not exist"),
    ({"id": "other", "name": "Other", "same_as": "alpha.thing"}, "names have to agree"),
])
def test_a_repeated_name_must_be_declared_or_it_does_not_load(tmp_path, second, expected):
    """The trap this tree is full of: Certificate, Financial Report, Official Letter.

    Two leaves with one name are two labels a classifier cannot tell apart, and
    a coverage report that counts one document twice. Either they are the same
    thing -- say so with `same_as` -- or they need names that differ.
    """
    with pytest.raises(TaxonomyError, match=expected):
        write_tree(tmp_path, [
            family("alpha", 1, [{"id": "thing", "name": "Thing", "name_vi": "vật"}]),
            family("beta", 2, [second]),
        ])


def test_an_alias_may_not_carry_its_own_status(tmp_path):
    with pytest.raises(TaxonomyError, match="unknown keys"):
        write_tree(tmp_path, [
            family("alpha", 1, [{"id": "thing", "name": "Thing", "name_vi": "vật"}]),
            family("beta", 2, [{"id": "thing", "name": "Thing",
                                "same_as": "alpha.thing", "status": "ready"}]),
        ])


def test_two_names_for_one_document_inside_one_family_is_a_duplicate(tmp_path):
    with pytest.raises(TaxonomyError, match="same family"):
        write_tree(tmp_path, [family("alpha", 1, [
            {"id": "thing", "name": "Thing", "name_vi": "vật"},
            {"id": "copy", "name": "Thing", "same_as": "alpha.thing"},
        ])])


@pytest.mark.parametrize("child, expected", [
    ({"id": "Bad", "name": "Bad", "name_vi": "x"}, "lower-case"),
    ({"id": "ok", "name": "Ok"}, "no name_vi"),
    ({"id": "ok", "name": "Ok", "name_vi": "x", "status": "someday"}, "status"),
    ({"id": "ok", "name": "Ok", "name_vi": "x", "engine": "laser"}, "engine"),
    ({"id": "ok", "name": "Ok", "name_vi": "x", "enigne": "grid"}, "unknown keys"),
])
def test_a_node_that_says_something_impossible_does_not_load(tmp_path, child, expected):
    with pytest.raises(TaxonomyError, match=expected):
        write_tree(tmp_path, [family("alpha", 1, [child])])


def test_resolve_takes_a_suffix_but_never_guesses(tmp_path):
    tree = write_tree(tmp_path, [
        family("alpha", 1, [{"id": "mid", "name": "Mid", "name_vi": "m", "children": [
            {"id": "leaf", "name": "Leaf", "name_vi": "lá"}]}]),
        family("beta", 2, [{"id": "leaf", "name": "Other Leaf", "name_vi": "lá2"}]),
    ])
    assert tree.resolve("alpha.mid.leaf").id == "alpha.mid.leaf"
    assert tree.resolve("beta.leaf").id == "beta.leaf"
    assert tree.resolve("mid.leaf").id == "alpha.mid.leaf"
    with pytest.raises(TaxonomyError, match="matches 2 types"):
        tree.resolve("leaf")


def test_select_is_include_minus_exclude(tmp_path):
    tree = write_tree(tmp_path, [family("alpha", 1, [
        {"id": "one", "name": "One", "name_vi": "1"},
        {"id": "two", "name": "Two", "name_vi": "2", "status": "ready"},
    ]), family("beta", 2, [{"id": "three", "name": "Three", "name_vi": "3"}])])
    assert [n.id for n in tree.select(["alpha"])] == ["alpha.one", "alpha.two"]
    assert [n.id for n in tree.select(None, ["alpha"])] == ["beta.three"]
    assert [n.id for n in tree.select(["alpha"], ["alpha.one"])] == ["alpha.two"]
    assert [n.id for n in tree.select(status=["ready"])] == ["alpha.two"]


def test_a_family_number_may_not_repeat(tmp_path):
    with pytest.raises(TaxonomyError, match="share a number"):
        write_tree(tmp_path, [
            family("alpha", 1, [{"id": "one", "name": "One", "name_vi": "1"}]),
            family("beta", 1, [{"id": "two", "name": "Two", "name_vi": "2"}]),
        ])


# --------------------------------------------------------- the shipped tree


def test_the_shipped_hierarchy_loads_and_is_consistent():
    tree = taxonomy.tree()
    assert tree.validate() == []
    counts = tree.counts()
    assert counts["families"] == 12
    assert counts["leaves"] + counts["aliases"] == 101


def test_every_family_is_numbered_in_file_order():
    """`01-business.yaml` is family 1. The two orders must not drift apart."""
    tree = taxonomy.tree()
    files = sorted((taxonomy.TAXONOMY_ROOT / taxonomy.FAMILIES_DIR).glob("*.yaml"))
    assert len(files) == 12
    for path, node in zip(files, tree.families()):
        assert path.name.startswith(f"{node.number:02d}-"), path.name
        assert path.stem.endswith(node.id), path.name


def test_the_three_documents_filed_twice_are_the_ones_the_hierarchy_names():
    """Certificate, Financial Report, Official Letter -- and nothing else.

    Pinned rather than counted: a fourth alias appearing without anyone
    deciding it should is how a tree stops meaning one thing per name.
    """
    tree = taxonomy.tree()
    aliases = {node.id: node.same_as for node in tree if node.is_alias}
    assert aliases == {
        "academic.certificate": "identity.certificate",
        "report.financial_report": "business.financial.financial_report",
        "communication.official_letter": "identity.official_letter",
    }


def test_every_ready_type_can_actually_be_generated():
    """The claim in `taxonomy/` against the rules and the builders.

    This is the check the whole status field exists for. `ready` means a run can
    produce it today; a `ready` type with no rules value or no builder is a
    coverage report that lies about the repository.
    """
    from rulebase.documents import coverage

    lying = [node_id for node_id, state in coverage().items()
             if (state["declared"] == "ready") != state["generatable"]]
    assert not lying, (
        f"the tree and the code disagree about {lying}; `make taxonomy` explains "
        f"which half is missing"
    )


def test_a_generatable_type_names_a_leaf_that_is_not_an_alias():
    from rulebase.documents import coverage

    tree = taxonomy.tree()
    for node_id, state in coverage().items():
        if state["generatable"]:
            node = tree.node(node_id)
            assert node.is_leaf and not node.is_alias, node_id
