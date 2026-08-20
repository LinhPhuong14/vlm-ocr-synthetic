"""The table generator, everything above the browser.

No page is opened here on purpose. The markup, the token list and the label are
pure functions of a seed, so they can be checked without a browser stack -- and
they are the half that a silent break would ruin, because a structure label that
has drifted from its page still looks like a valid label.
"""

from __future__ import annotations

import random
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

import tables as T  # noqa: E402

SHAPE = dict(min_row=3, max_row=12, min_col=3, max_col=7,
             max_span_row=3, max_span_col=3, max_span=10, colour_prob=0.3)
SEEDS = list(range(40))


def built(seed: int):
    rng = random.Random(seed)
    table = T.build_table(rng, **SHAPE)
    markup, tokens = T.build_page(table, rng)
    return table, markup, tokens


def cell_slots(tokens: list[str]) -> int:
    """How many cells the token list says the table has.

    PPStructure marks the end of a cell's opening tag with `<td>` when it has no
    span and with `>` when it does; a reader inserts the cell text after that
    token. Count them and you have the number of cells the label promises.
    """
    return sum(1 for token in tokens if token in ("<td>", ">"))


# ------------------------------------------------------- the label matches


@pytest.mark.parametrize("seed", SEEDS)
def test_the_token_list_promises_exactly_the_cells_the_page_has(seed):
    """The one invariant a structure label cannot survive breaking.

    `rebuild_html` zips the cell texts onto the token slots. One slot too many
    or too few and every text after that point lands in the wrong cell, in a
    label that still parses and still looks right.
    """
    _table, markup, tokens = built(seed)
    written = len(re.findall(r"<t[dh][ >]", markup))
    assert cell_slots(tokens) == written


@pytest.mark.parametrize("seed", SEEDS)
def test_a_covered_cell_is_written_neither_as_markup_nor_as_a_token(seed):
    """A cell under a span does not exist, in either description of the table."""
    table, _markup, tokens = built(seed)
    covered = sum(1 for row in range(table.rows) for col in range(table.cols)
                  if table.rowspan[row][col] == -1 or table.colspan[row][col] == -1)
    assert cell_slots(tokens) == table.rows * table.cols - covered


@pytest.mark.parametrize("seed", SEEDS[:12])
def test_the_rebuilt_html_carries_every_cell_text(seed):
    table, _markup, tokens = built(seed)
    cells = [{"text": f"c{i}", "quad": [[0, 0], [1, 0], [1, 1], [0, 1]]}
             for i in range(cell_slots(tokens))]
    label = T.ppstructure_label("img/x.jpg", tokens, cells)
    assert label["gt"].count("<td") == cell_slots(tokens)
    for index in range(len(cells)):
        assert f"c{index}" in label["gt"]
    assert label["html"]["structure"]["tokens"] == tokens
    # Upstream's nesting, kept deliberately: `bbox` holds the quad, it is not
    # the quad. Tools that read PP-Structure labels expect it that way.
    assert label["html"]["cells"][0]["bbox"] == [cells[0]["quad"]]
    assert T.metadata_record(label)["n_cells"] == len(cells)
    assert table.rows >= 3


def test_the_index_record_is_not_the_receipts_schema():
    """Two tasks, two labels. Flattening one into the other would lie."""
    _table, _markup, tokens = built(3)
    cells = [{"text": "x", "quad": [[0, 0], [1, 0], [1, 1], [0, 1]]}
             for _ in range(cell_slots(tokens))]
    record = T.metadata_record(T.ppstructure_label("img/x.jpg", tokens, cells))
    assert record["task"] == "table_structure"
    assert set(record) == {"file_name", "task", "ground_truth",
                           "structure_tokens", "cells", "n_cells"}


# ------------------------------------------------------------- the content


@pytest.mark.parametrize("seed", SEEDS)
def test_a_cell_holds_whole_words(seed):
    """The reason the generator moved rather than being wrapped.

    Upstream slices its corpus by *character*, so a cell reads `ình Thọ Ng`.
    Every cell here is either a number, money, or words the corpus owns.
    """
    # Folded too: one column type in four is ASCII-folded Vietnamese, which is
    # what a form printed on a machine with no Unicode looks like.
    from rulebase.text import ascii_fold

    known = set()
    for phrase in T.phrases():
        for word in phrase.split():
            known.add(word)
            known.add(ascii_fold(word))

    table, markup, _tokens = built(seed)
    texts = re.findall(r"<t[dh][^>]*>([^<]*)</t[dh]>", markup)
    assert texts
    for text in texts:
        text = text.strip()
        if not text or re.fullmatch(r"[0-9.,]+( đ)?", text):
            continue
        for word in text.split():
            assert word in known, (seed, text, word, table.border)


def test_money_is_spelled_by_the_same_function_the_receipts_use():
    from rulebase.text import money

    rng = random.Random(0)
    table = T.build_table(rng, **{**SHAPE, "colour_prob": 0})
    table.col_types = ["m"] * table.cols
    table.missing.clear()
    separator = "." if table.style == "dot" else ","

    grouped = 0
    for _ in range(200):
        amount = T.cell_text(rng, table, T.HEADER_ROWS, 1).replace(" đ", "")
        # `money` groups; the other branch writes a plain two-place decimal and
        # is not this function's business.
        if separator not in amount:
            continue
        assert amount == money(int(amount.replace(separator, "")), table.style)
        grouped += 1
    assert grouped, "no grouped amount was drawn in 200 tries"


# -------------------------------------------------------------- the shapes


def test_every_border_style_is_reachable_and_named_as_upstream_named_it():
    """The file name of every image carries the style, so the names are API."""
    assert set(T.BORDERS) == {
        "border", "border_top", "border_bottom", "head_border_bottom",
        "no_border", "border_left", "border_right",
    }
    drawn = {T.build_table(random.Random(seed), **SHAPE).border for seed in range(200)}
    assert drawn == set(T.BORDERS)


def test_merged_cells_are_the_normal_case_not_the_rare_one():
    """A structure dataset with no spans teaches nothing a grid would not."""
    spanned = 0
    for seed in SEEDS:
        table, _markup, _tokens = built(seed)
        if any(value > 1 for row in table.rowspan + table.colspan for value in row):
            spanned += 1
    assert spanned >= len(SEEDS) * 0.9


@pytest.mark.parametrize("seed", SEEDS[:10])
def test_one_seed_is_one_table(seed):
    """Per image, not per run: image 40 rebuilds without rebuilding 0-39."""
    assert built(seed)[1] == built(seed)[1]
    assert built(seed)[1] != built(seed + 1)[1]


def test_the_font_families_are_faces_the_page_actually_embeds():
    """A family name with a space in it matches nothing and falls through."""
    from page import font_faces

    embedded = set(re.findall(r"font-family:'([^']+)'", font_faces()))
    assert embedded, "no fonts found under assets/fonts/"
    for family in T.FAMILIES:
        assert family in embedded, family
