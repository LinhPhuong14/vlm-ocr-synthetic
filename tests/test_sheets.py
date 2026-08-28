"""The CSS sheets, everything above the engine.

No browser and no print engine here, on purpose. The markup, the labelled runs
and the structure tokens are pure functions of a seed, and they are the half a
silent break would ruin: a structure label that has drifted from its page still
looks like a valid label.

What is checked is what the brief in `docs/brief-engine-html.md` asked for and
what the old single-template `a4.py` could not do -- a sheet chosen by the
layout, merged cells that are real `colspan`/`rowspan`, and a table whose rows
all add up to the same width, which is the machine-checkable form of "the two
tables on this page line up".
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

import sheets  # noqa: E402

import rulebase  # noqa: E402
from rulebase.layout import available as available_layouts  # noqa: E402

SEEDS = (1, 7, 2026)
LAYOUTS = available_layouts()

_PAGES: dict[tuple[str, int], tuple] = {}


def page(layout: str, seed: int):
    """`(recipe, receipt, markup)` for one sheet, built once and reused."""
    key = (layout, seed)
    if key not in _PAGES:
        recipe, receipt, _rng = rulebase.make_content(seed=seed, force={"layout": layout})
        _PAGES[key] = (recipe, receipt, sheets.build(recipe, receipt))
    return _PAGES[key]


def test_every_layout_has_a_sheet():
    """A layout with no family is a page drawn as some other document."""
    missing = [layout for layout in LAYOUTS if layout not in sheets.FAMILIES]
    assert not missing, f"no CSS sheet for {missing}"
    extra = [name for name in sheets.FAMILIES if name not in LAYOUTS]
    assert not extra, f"sheets.FAMILIES names layouts that do not exist: {extra}"


def test_unknown_layout_is_an_error():
    with pytest.raises(KeyError):
        sheets.family_of("no_such_layout")


@pytest.mark.parametrize("layout", LAYOUTS)
def test_builds_and_is_one_document(layout):
    _recipe, _receipt, markup = page(layout, 7)
    assert markup.startswith("<!doctype html>")
    assert markup.count('id="sheet"') == 1
    assert "{FONT_FACES}" in markup, "the font block placeholder must survive"


def test_the_sheet_follows_the_layout():
    """The defect this package exists to fix: one page for every layout.

    `a4.build()` never read `recipe.layout.id`, so a hotel folio forced through
    it came out a VAT invoice -- measured as three different layouts producing
    pages of identical size. Different families must now differ in the markup.
    """
    seen = {}
    for layout in ("invoice_vat_summary", "invoice_hotel_stay", "invoice_brand"):
        _recipe, _receipt, markup = page(layout, 7)
        seen[layout] = markup
    assert len(set(seen.values())) == 3
    # And in the thing a reader would notice first: the paper.
    sizes = {re.search(r"@page\{size:([^;]+);", markup).group(1)
             for markup in seen.values()}
    assert len(sizes) > 1, f"every family printed on the same paper: {sizes}"


@pytest.mark.parametrize("layout", LAYOUTS)
@pytest.mark.parametrize("seed", SEEDS)
def test_rows_all_span_the_same_width(layout, seed):
    """Every row of a table covers the table, counting both kinds of span.

    This is the check that a merged cell is *modelled* rather than drawn. A row
    whose cells leave a gap has a hole; one that runs past the last column has a
    cell hanging off the end. Either way the structure label describes a table
    that is not on the page.

    Occupancy, not a sum of `colspan`. A two-level header's lower band holds
    four cells and covers thirteen columns, because nine cells in the band above
    it reach down with `rowspan="2"` -- adding up one row's colspans and calling
    that its width would report the row that makes the header work as the one
    that breaks it.
    """
    _recipe, _receipt, markup = page(layout, seed)
    cells = sheets.cells_from_markup(markup)
    if not cells:
        return                # a form of fields has no table; see sheets/statement.py
    occupied: dict[int, set[int]] = {}
    for cell in cells:
        for row in range(cell["row"], cell["row"] + cell["rowspan"]):
            occupied.setdefault(row, set()).update(
                range(cell["col"], cell["col"] + cell["colspan"]))
    widths = {row: max(columns) + 1 for row, columns in occupied.items()}
    for row, columns in occupied.items():
        assert columns == set(range(widths[row])), (
            f"{layout} seed {seed}: row {row} covers {sorted(columns)}, "
            f"which is not columns 0..{widths[row] - 1}")
    # Two tables on one sheet are allowed two widths -- the item table and the
    # tax summary have different column counts -- but never a width used by a
    # single row, which is what a hole looks like.
    counts: dict[int, int] = {}
    for width in widths.values():
        counts[width] = counts.get(width, 0) + 1
    odd = [width for width, count in counts.items() if count == 1 and len(counts) > 1]
    assert not odd, f"{layout} seed {seed}: row width(s) {odd} used once, of {counts}"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_columns_never_overlap_within_a_row(layout):
    _recipe, _receipt, markup = page(layout, 7)
    rows: dict[int, list[dict]] = {}
    for cell in sheets.cells_from_markup(markup):
        rows.setdefault(cell["row"], []).append(cell)
    for row, cells in rows.items():
        taken: set[int] = set()
        for cell in sorted(cells, key=lambda c: c["col"]):
            columns = set(range(cell["col"], cell["col"] + cell["colspan"]))
            assert not (columns & taken), (
                f"{layout} row {row}: two cells claim column(s) {columns & taken}")
            taken |= columns


def test_row_numbers_are_page_wide():
    """Two tables on one page must not share row numbers.

    `structure_from_cells` groups by `data-row`; a second table that restarted
    at zero would have its first row welded onto the item table's first row --
    one row of thirteen cells that exists nowhere on the paper.
    """
    _recipe, _receipt, markup = page("invoice_vat_summary", 7)
    cells = sheets.cells_from_markup(markup)
    widths = {cell["row"]: 0 for cell in cells}
    for cell in cells:
        widths[cell["row"]] += cell["colspan"]
    assert {8, 5} <= set(widths.values()), (
        "the item table and the tax summary should have their own widths, "
        f"got {sorted(set(widths.values()))}")


@pytest.mark.parametrize("layout", LAYOUTS)
def test_structure_tokens_match_the_cells(layout):
    """The token stream and the cells describe one table."""
    _recipe, _receipt, markup = page(layout, 7)
    tokens = sheets.structure_from_markup(markup)
    cells = sheets.cells_from_markup(markup)
    assert tokens.count("<tr>") == len({cell["row"] for cell in cells})
    assert tokens.count("</td>") == len(cells)
    merged = sum(1 for cell in cells if cell["colspan"] > 1 or cell["rowspan"] > 1)
    spans = sum(1 for token in tokens if token.startswith((" colspan", " rowspan")))
    assert spans >= merged, "a merged cell lost its span in the token stream"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_labelled_run_is_a_span_with_a_kind(layout):
    """The box contract. `CELL_RECTS_JS` reads these and nothing else."""
    _recipe, _receipt, markup = page(layout, 7)
    runs = sheets.labelled_runs(markup)
    assert runs, f"{layout} labelled nothing"
    for kind, text in runs:
        assert kind, f"a run with no kind: {text!r}"
        assert text.strip(), f"an empty run labelled {kind!r}"
    # Labelled runs are text only: `CELL_RECTS_JS` measures the span's first
    # element child when it has one, so a nested tag would make the quad
    # describe a fragment of the run instead of the run.
    for match in re.finditer(r'<span data-kind="[^"]*"[^>]*>(.*?)</span>', markup, re.S):
        assert "<" not in match.group(1), f"{layout}: a labelled run has a child element"


@pytest.mark.parametrize("layout", LAYOUTS)
def test_what_the_label_says_the_page_prints(layout):
    """Every label value is somewhere in the markup, joined by kind.

    The same rule `pipeline/invariants.py` applies to a rendered page, checked
    here where a failure names the layout rather than an image -- and against
    the same `SUPPRESSED` table, so a sheet is held to exactly the standard the
    character grid is held to. A till roll has no column for a barcode on
    either path; an invoice has room for everything it is given on both.
    """
    from pipeline.invariants import SUPPRESSED, _tight

    allowed = SUPPRESSED.get(layout, frozenset())
    for seed in SEEDS:
        _recipe, receipt, markup = page(layout, seed)
        by_kind: dict[str, list[str]] = {}
        for kind, text in sheets.labelled_runs(markup):
            by_kind.setdefault(kind, []).append(text)
        printed = " ".join(" ".join(sum(by_kind.values(), [])).split())
        joined = {kind: " ".join(" ".join(texts).split())
                  for kind, texts in by_kind.items()}
        for name, value in _leaves(receipt.ground_truth()):
            if not value.strip() or name == "doc_type":
                continue
            field = "total" if name.startswith("total.") else name
            if field in allowed:
                continue
            wanted = " ".join(value.split())
            if wanted in printed or any(wanted in text for text in joined.values()):
                continue
            # `comb_box()` (base.py) prints one character per `data-kind` run
            # rather than one run for the whole value -- see its own
            # docstring on why -- so the space-sensitive check above rejoins
            # it as "T r ầ n" rather than "Trần". The same whitespace-
            # insensitive fallback `pipeline/invariants.py::_printed()`
            # already applies to a wrapped-at-a-hyphen run applies here too.
            tight = _tight(wanted)
            assert any(tight in _tight(text) for text in joined.values()), (
                f"{layout} seed {seed}: {name} {wanted!r} is in the label and on no run")


def _leaves(value, path: str = ""):
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _leaves(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for item in value:
            yield from _leaves(item, path)
    else:
        yield path, str(value)


def test_the_same_seed_gives_the_same_markup():
    for layout in ("invoice_vat_summary", "invoice_hotel_compact", "market_vat"):
        recipe, receipt, _rng = rulebase.make_content(seed=11, force={"layout": layout})
        again, again_receipt, _rng2 = rulebase.make_content(seed=11, force={"layout": layout})
        assert sheets.build(recipe, receipt) == sheets.build(again, again_receipt)


def test_a_grid_is_not_laid_over_the_contents_first():
    """`make_content` must leave the receipt as it was sampled.

    `build_grid` cuts a value that will not fit its character column and writes
    the cut back, so the label matches the drawn page. A CSS sheet has no
    character columns, and a sheet built after a grid prints "Hàng hoá không
    chịu thuế GTG" on a line with room for the whole label.
    """
    seed = 77
    _recipe, receipt, _rng = rulebase.make_content(seed=seed,
                                                   force={"layout": "invoice_vat_summary"})
    assert receipt.invoice is not None
    labels = [row.get("label", "") for row in receipt.invoice.summary]
    assert any(label.rstrip().endswith(":") for label in labels), labels
