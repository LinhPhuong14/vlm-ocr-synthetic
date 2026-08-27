"""Periodical content: the newspaper/magazine model has no basket, no totals.

`rulebase/periodical.py` is a sibling to `rulebase/content.py`, not an
extension of it -- see that module's docstring. `tests/test_content.py`
explicitly excludes periodical draws from its own sweep (its assertions are
written against `.items`/`.invoice`/`.totals`, fields a periodical page does
not have) and points here instead. This file is that "here": the same
"found by measuring, not by looking" discipline, aimed at the four
dataclasses (`ArticlePage`, `ClassifiedsPage`, `TocPage`, `QaPage`) rather
than at `Receipt`.

Each composition is reached by forcing `layout=<id>` rather than relying on
an unforced sweep to draw a periodical page by weighted luck -- the same
`force={"layout": ...}` pattern `test_content.py::_forced` uses, since
`periodical_page` layouts and their matching documents are a small,
1-to-1-tagged slice of the whole space (see `rulebase/rules/layout.yaml`'s
`periodical_page` group).
"""

from __future__ import annotations

import rulebase
from rulebase import periodical

SEEDS = range(8)


def _forced(layout: str, seed: int):
    _recipe, receipt, grid = rulebase.make(seed=seed, force={"layout": layout})
    return receipt, grid


def _strings(value) -> list[str]:
    """Every leaf string in a nested ground-truth structure."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in _strings(item)]
    if isinstance(value, (list, tuple)):
        return [s for item in value for s in _strings(item)]
    return []


# ---------------------------------------------------------------- shared


def _assert_common_shape(receipt, doc_type: str, seed: int):
    """What every one of the four classes must get right, regardless of shape."""
    label = receipt.ground_truth()
    assert label.get("doc_type") == doc_type, f"seed={seed}: {label.get('doc_type')!r}"
    assert not label["doc_type"].startswith("receipt_"), seed  # never mistaken for one

    sequence = receipt.text_sequence()
    assert isinstance(sequence, str) and sequence.strip(), f"seed={seed}: empty text_sequence"

    # Every non-empty leaf string in ground_truth must actually appear in the
    # flattened text -- the same "label agreeing with what got printed"
    # property test_content.py checks for Receipt, applied to these instead.
    for value in _strings(label):
        if value.strip():
            assert value in sequence, f"seed={seed}: {value!r} in ground_truth but not text_sequence"

    grid_source = receipt.as_grid_receipt()
    assert isinstance(grid_source, rulebase.Receipt), seed
    # The shim owes no label-fidelity (see rulebase/periodical.py's module
    # docstring) -- only that it is a real, buildable Receipt.
    assert grid_source.profile == "periodical", seed


# ----------------------------------------------------------- lead_sidebar


def test_article_page_lead_sidebar():
    for seed in SEEDS:
        receipt, grid = _forced("newspaper_front_broadsheet", seed)
        assert isinstance(receipt, periodical.ArticlePage), seed
        _assert_common_shape(receipt, "periodical_lead_sidebar", seed)

        assert receipt.masthead == "Minh Hoạ", seed
        assert receipt.headline, seed
        assert receipt.body, seed
        assert grid.sheet == "a4", seed

        for teaser in receipt.teasers:
            assert teaser.headline, seed
        for story in receipt.bottom_stories:
            assert story.headline and story.body, seed


def test_article_page_teaser_and_bottom_counts_match_the_document():
    """`teaser_count`/`bottom_count` in the document params are the contract."""
    receipt, _grid = _forced("newspaper_front_broadsheet", 0)
    assert len(receipt.teasers) == 3
    assert len(receipt.bottom_stories) == 2
    assert receipt.sidebar_title and receipt.sidebar_items  # sidebar_box always drawn
    assert receipt.sidebar_headline  # secondary_rail: true


# ------------------------------------------------------------ classifieds


def test_classifieds_page():
    for seed in SEEDS:
        receipt, grid = _forced("newspaper_classifieds", seed)
        assert isinstance(receipt, periodical.ClassifiedsPage), seed
        _assert_common_shape(receipt, "periodical_classifieds", seed)

        assert receipt.categories, seed
        for category in receipt.categories:
            assert category.name, seed
            assert category.ads, seed
            for ad in category.ads:
                assert ad.body, seed
                # A rao vặt line opens with either a bold lead-in or is
                # boxed under its own heading -- never neither.
                assert ad.lead_in or ad.heading, f"seed={seed}: {ad}"
        for notice in receipt.notices:
            assert notice.title and notice.body, seed
        for obituary in receipt.obituaries:
            assert obituary.name and obituary.body, seed
        assert grid.sheet == "a4", seed


# --------------------------------------------------------------------- toc


def test_toc_page():
    for seed in SEEDS:
        receipt, grid = _forced("magazine_contents", seed)
        assert isinstance(receipt, periodical.TocPage), seed
        _assert_common_shape(receipt, "periodical_toc", seed)

        assert receipt.masthead == "Tạp chí Bến", seed
        assert receipt.hero_headline, seed
        assert receipt.sections, seed
        for section in receipt.sections:
            assert section.name, seed
            assert section.entries, seed
            for entry in section.entries:
                assert entry.page_no and entry.title, seed
        assert grid.sheet == "a4", seed


# ---------------------------------------------------------------------- qa


def test_qa_page():
    for seed in SEEDS:
        receipt, grid = _forced("magazine_qa_interview", seed)
        assert isinstance(receipt, periodical.QaPage), seed
        _assert_common_shape(receipt, "periodical_qa", seed)

        assert receipt.headline and receipt.subject_name, seed
        assert receipt.byline_by.startswith("Thực hiện: "), seed
        assert receipt.byline_photo.startswith("Ảnh: "), seed
        assert len(receipt.qa_pairs) >= 2, seed
        for pair in receipt.qa_pairs:
            assert pair.question and pair.answer, seed
        assert grid.sheet == "a4", seed


def test_qa_page_writer_and_photographer_are_distinct_each_draw():
    """Drawn via `rng.sample` -- a real name collision would be a data bug."""
    for seed in SEEDS:
        receipt, _grid = _forced("magazine_qa_interview", seed)
        writer = receipt.byline_by.removeprefix("Thực hiện: ")
        photographer = receipt.byline_photo.removeprefix("Ảnh: ")
        assert writer != photographer, seed
