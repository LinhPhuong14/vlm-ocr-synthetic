"""Content: the arithmetic on the page, and the label agreeing with the grid.

The second half is the one that earns its keep. `docs/huong-dan-va-giai-thich.md`
§9 records a bug where narrow paper truncated an address to fit a column while
the ground truth kept the full string -- a label describing text no reader can
see. It was found by measuring, not by looking, and 0.8% of fields were wrong.
`test_printed_text_is_all_in_the_label` is that measurement, run every time.
"""

from __future__ import annotations

import pytest

import rulebase

SEEDS = tuple(range(40))


_RECEIPTS: list | None = None


def receipts():
    """(seed, receipt, grid) for a fixed sweep. Built once -- see test_layout."""
    global _RECEIPTS
    if _RECEIPTS is None:
        _RECEIPTS = [(seed,) + rulebase.make(seed=seed)[1:] for seed in SEEDS]
    return _RECEIPTS


def _strings(value) -> list[str]:
    """Every leaf string in a nested ground-truth structure."""
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in _strings(item)]
    if isinstance(value, (list, tuple)):
        return [s for item in value for s in _strings(item)]
    return []


# ------------------------------------------------------------- arithmetic


def test_line_amounts_are_quantity_times_price():
    for seed, receipt, _grid in receipts():
        for item in receipt.items:
            if item.weighed:
                continue  # priced by weight; the rounding is checked below
            assert item.amount == item.unit_price * item.qty, (
                f"seed={seed}: {item.name!r} {item.qty} x {item.unit_price} "
                f"!= {item.amount}"
            )


def test_weighed_items_price_out_within_rounding():
    for seed, receipt, _grid in receipts():
        for item in receipt.items:
            if not item.weighed:
                continue
            expected = item.unit_price * item.qty
            assert abs(item.amount - expected) <= 5, (
                f"seed={seed}: {item.name!r} weighed amount {item.amount} "
                f"is not {expected} to the nearest 5"
            )


def test_a_weighed_item_prints_quantity_one():
    # A till prints the weighing, not the weight: SL = 1 and the unit price is
    # what that weighing cost. Getting this wrong put "0.40" in a 4-character
    # column and truncated a real quantity.
    for seed, receipt, _grid in receipts():
        for item in receipt.items:
            if item.weighed:
                assert item.display_qty() == 1, f"seed={seed}: {item.name!r}"
                assert item.display_unit_price() == item.amount, f"seed={seed}"


def test_every_item_has_a_positive_amount():
    for seed, receipt, _grid in receipts():
        for item in receipt.items:
            assert item.amount > 0, f"seed={seed}: {item.name!r} costs {item.amount}"
            assert item.qty > 0, f"seed={seed}: {item.name!r} qty {item.qty}"


def test_discounts_never_exceed_the_line():
    for seed, receipt, _grid in receipts():
        for item in receipt.items:
            assert 0 <= item.discount <= item.amount, (
                f"seed={seed}: {item.name!r} discount {item.discount} on {item.amount}"
            )


def test_there_is_always_something_on_the_receipt():
    for seed, receipt, _grid in receipts():
        assert receipt.items, f"seed={seed}: no items"
        assert receipt.totals, f"seed={seed}: no totals"
        assert receipt.store.name, f"seed={seed}: no shop name"


# ------------------------------------------------------- label ↔ the grid


# Header roles paired with where the label keeps the same string. These never
# wrap -- one field, one cell -- so the two can be compared for equality, which
# is what makes truncation detectable.
HEADER_ROLES = {
    "store.name": ("store", "name"),
    "store.branch": ("store", "branch"),
    "store.address": ("store", "address"),
    "store.address2": ("store", "address2"),
    "store.phone": ("store", "phone"),
    "store.website": ("store", "website"),
}


def test_label_quotes_exactly_what_was_printed():
    """A label field must equal the cell, not merely contain it.

    This is the truncation guard, and *equality* is the whole point. Narrow
    paper cuts a long address to fit its column and the cut has to be written
    back into the object the label is built from. Checking that the printed
    text merely appears in the label does not catch that: a truncation is a
    prefix of the original, so substring containment stays true while the label
    promises characters nobody inked. Removing the write-back in
    `rulebase/layout.py` must turn this red, and it does.
    """
    failures = []
    for seed, receipt, grid in receipts():
        label = receipt.ground_truth()
        for cell in grid.cells:
            target = HEADER_ROLES.get(cell.role)
            if target is None or not cell.text.strip():
                continue
            section, key = target
            recorded = label.get(section, {}).get(key)
            if recorded != cell.text:
                failures.append(
                    f"seed={seed}: {cell.role} printed {cell.text!r} "
                    f"but the label says {recorded!r}"
                )
        # Item names take the same treatment wherever the layout truncates
        # instead of wrapping (`wrap_name: false`, the 2011 till). One cell per
        # item is the signal that no wrapping happened.
        names = [cell.text for cell in grid.cells if cell.role == "menu.name"]
        if len(names) == len(receipt.items):
            recorded = [entry["nm"] for entry in label["menu"]]
            if names != recorded:
                failures.append(
                    f"seed={seed}: item names printed {names} but label has {recorded}"
                )
    assert not failures, "\n".join(failures[:15])


def test_a_truncated_item_name_is_written_back():
    """The `wrap_name: false` path, forced rather than waited for.

    An old thermal till cuts a long dish name instead of wrapping it, and the
    label has to follow. Sampling will not reach this on its own: over 40 seeds
    21 receipts use a non-wrapping layout and *none* of them happens to draw a
    name longer than the column, so the branch is dead code as far as the sweep
    is concerned. The condition is therefore constructed.
    """
    import random

    _recipe, receipt, _grid = rulebase.make(seed=5, force={"layout": "eatery_ascii"})
    receipt.items[0].name = "MI QUANG SUON NON RAU RUNG DAC BIET THAP CAM LOAI LON"
    grid = rulebase.build_grid(receipt, "eatery_ascii", random.Random(5))

    printed = [cell.text for cell in grid.cells if cell.role == "menu.name"]
    assert printed, "no item names on the page"
    assert len(printed[0]) < len("MI QUANG SUON NON RAU RUNG DAC BIET THAP CAM LOAI LON"), (
        "the name was not truncated, so this test is not exercising the path"
    )
    assert receipt.ground_truth()["menu"][0]["nm"] == printed[0], (
        "the label kept the full name after the page printed a cut one"
    )


def test_the_title_is_quoted_exactly():
    for seed, receipt, grid in receipts():
        printed = [cell.text for cell in grid.cells if cell.role == "title"]
        if printed:
            assert printed[0] == receipt.ground_truth()["title"], f"seed={seed}"


def _unprinted_label_values(receipt, grid) -> list[str]:
    """Label values that no cell prints, allowing for wrapped text."""
    order = sorted(grid.cells, key=lambda cell: (cell.row, cell.col0))
    page = " ".join(" ".join(cell.text for cell in order).split())
    by_role: dict[str, list[str]] = {}
    for cell in order:
        by_role.setdefault(cell.role, []).append(cell.text)
    # A long dish name wraps over two rows, so it is on the page but not in any
    # single cell. Joining per role reassembles it without letting an unrelated
    # field match by accident.
    joined = {role: " ".join(" ".join(texts).split()) for role, texts in by_role.items()}

    missing = []
    for value in _strings(receipt.ground_truth()):
        if not value.strip() or value.startswith("receipt_"):
            continue
        wanted = " ".join(value.split())
        if wanted in page or any(wanted in text for text in joined.values()):
            continue
        missing.append(wanted)
    return missing


@pytest.mark.xfail(strict=True, reason=(
    "known open defect: a layout that suppresses a field -- market_compact "
    "prints no branch and no barcode, eatery_ascii prints no title -- still "
    "gets that field in ground_truth(). Measured at 11.4% of label values over "
    "40 seeds: vatrate, barcode, unitprice, weight, branch, address, phone, "
    "title. Truncation is already written back (layout.py); suppression is not. "
    "Fixing it changes labels for every committed dataset, so it is deliberately "
    "not part of W0."
))
def test_label_never_describes_unprinted_text():
    failures = []
    for seed, receipt, grid in receipts():
        failures += [f"seed={seed}: {value!r}" for value in
                     _unprinted_label_values(receipt, grid)]
    assert not failures, "\n".join(failures[:15])


def test_the_suppressed_field_defect_has_not_grown():
    """A budget on the known defect, so it cannot quietly get worse.

    The xfail above records that the problem exists; this records how big it is.
    A new layout that drops another field would push the share up and fail here
    long before anyone noticed a model hallucinating.
    """
    total = unprinted = 0
    for _seed, receipt, grid in receipts():
        total += len([v for v in _strings(receipt.ground_truth())
                      if v.strip() and not v.startswith("receipt_")])
        unprinted += len(_unprinted_label_values(receipt, grid))
    share = unprinted / total
    assert share <= 0.13, f"unprinted label values rose to {share:.2%} (was 11.4%)"


def test_ground_truth_has_the_shape_donut_expects():
    for seed, receipt, _grid in receipts():
        label = receipt.ground_truth()
        assert set(label) >= {"doc_type", "title", "store", "menu", "total", "footer"}, seed
        assert label["doc_type"].startswith("receipt_"), seed
        assert isinstance(label["menu"], list) and label["menu"], seed
        for entry in label["menu"]:
            assert "nm" in entry and "price" in entry, f"seed={seed}: {entry}"


@pytest.mark.parametrize("profile", ["eatery", "market"])
def test_both_profiles_are_reachable(profile):
    seen = any(receipt.profile == profile for _seed, receipt, _grid in receipts())
    assert seen, f"no seed in the sweep produced a {profile} receipt"
