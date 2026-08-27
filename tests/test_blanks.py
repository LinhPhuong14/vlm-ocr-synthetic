"""The blank registry, and the drift it exists to catch."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
import yaml

from rulebase.blanks import (
    BlankError,
    check,
    load_blanks,
    problems,
    resolved,
)

# --------------------------------------------------------------- the shipped file


def test_the_shipped_registry_agrees_with_the_shipped_rules(real_rules):
    check(real_rules)


def test_every_blank_names_a_real_layout_and_a_sheet_that_exists(real_rules):
    blanks, _ = load_blanks()
    ids = {option.id for option in real_rules["layout"]}
    for blank in blanks.values():
        assert blank.layout is None or blank.layout in ids
        assert blank.sheet is None or Path(blank.sheet).suffix == ".html"


def test_a_document_with_one_blank_is_reported_as_such(real_rules):
    """Most kinds have exactly one, and that is the fact the file exists to show.

    `pub_eatery` has three since `eatery_indexed_b` shipped. A variant is drawn
    by the same documents as the layout it varies -- that is what makes it a
    variant rather than a new kind of paper -- so `tools/llm/augment_layout.py`
    adds it beside its parent in every document list the parent appears in, and
    this count moves with it.
    """
    _, documents = load_blanks()
    counts = {name: len(members) for name, members in documents.items()}
    assert counts["hospital_bill"] == 1
    assert counts["pub_eatery"] == 3
    assert set(counts) == {option.id for option in real_rules["document"]}


# --------------------------------------------------------------- drift


def _registry(tmp_path: Path, blanks: dict, documents: dict) -> Path:
    path = tmp_path / "blanks.yaml"
    path.write_text(yaml.safe_dump({"blanks": blanks, "documents": documents},
                                   allow_unicode=True), encoding="utf-8")
    return path


def _shipped_copy(tmp_path: Path) -> Path:
    blanks, documents = load_blanks()
    return _registry(
        tmp_path,
        {name: {"source": b.source, "layout": b.layout, "sheet": b.sheet}
         for name, b in blanks.items()},
        {name: list(members) for name, members in documents.items()},
    )


def test_a_layout_whose_tags_reach_too_far_is_caught(real_rules, tmp_path):
    """The failure this file is for: one loose `requires:` quietly re-aims a
    layout at every document that happens to share a tag, and nothing else in
    the repository would say so."""
    loose = dataclasses.replace(real_rules["layout"][0], id="new_layout",
                                requires=frozenset())
    rules = dict(real_rules)
    rules["layout"] = [*real_rules["layout"], loose]
    found = problems(rules, _shipped_copy(tmp_path))
    assert found and all("new_layout" in line for line in found)


def test_a_layout_whose_tags_narrow_is_caught(real_rules, tmp_path):
    tight = dataclasses.replace(real_rules["layout"][0],
                                requires=frozenset({"no_such_tag"}))
    rules = dict(real_rules)
    rules["layout"] = [tight, *real_rules["layout"][1:]]
    found = problems(rules, _shipped_copy(tmp_path))
    assert any("tags forbid it" in line for line in found)


def test_a_blank_naming_a_layout_that_does_not_exist_is_caught(real_rules, tmp_path):
    path = _registry(tmp_path,
                     {"ghost": {"source": "x", "layout": "not_a_layout", "sheet": None}},
                     {"pub_eatery": ["ghost"]})
    assert any("does not exist" in line for line in problems(real_rules, path))


def test_a_blank_no_document_draws_from_is_caught(real_rules, tmp_path):
    blanks, documents = load_blanks()
    payload = {name: {"source": b.source, "layout": b.layout, "sheet": b.sheet}
               for name, b in blanks.items()}
    payload["orphan"] = {"source": "chưa ai dùng", "layout": None, "sheet": None}
    path = _registry(tmp_path, payload,
                     {name: list(m) for name, m in documents.items()})
    assert any("no document draws from it" in line
               for line in problems(real_rules, path))


def test_a_document_with_no_entry_is_caught(real_rules, tmp_path):
    blanks, documents = load_blanks()
    trimmed = {name: list(m) for name, m in documents.items()}
    trimmed.pop("hospital_bill")
    path = _registry(tmp_path,
                     {name: {"source": b.source, "layout": b.layout, "sheet": b.sheet}
                      for name, b in blanks.items()},
                     trimmed)
    assert any("'hospital_bill' is missing" in line
               for line in problems(real_rules, path))


def test_check_raises_rather_than_returning(real_rules, tmp_path):
    path = _registry(tmp_path, {}, {})
    with pytest.raises(BlankError):
        check(real_rules, path)


# --------------------------------------------------------------- the tag side


def test_resolved_is_what_the_sampler_would_allow(real_rules):
    by_tags = resolved(real_rules)
    for document in real_rules["document"]:
        expected = {layout.id for layout in real_rules["layout"]
                    if layout.allowed(document.tags)}
        assert by_tags[document.id] == expected
        assert expected, f"{document.id} can draw no layout at all"
