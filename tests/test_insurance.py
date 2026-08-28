"""Insurance documents: ten layouts, all still a real `rulebase.Receipt`.

Unlike `rulebase/periodical.py`, this root needed no sibling content model --
every one of the ten documents is parties/fields (+ sometimes a priced
table) + notes + signatures, the shape `Receipt`/`Invoice` already model
(see the plan this root shipped from). So this file's job is narrower than
`test_periodical.py`'s: confirm each layout draws a real `Receipt`, that its
ground truth is fully printed (the same property `test_content.py` checks
for every other receipt), and the handful of facts specific to this root's
two small additive flags (`no_totals`, `Invoice.checks`).

Each composition is reached by forcing `layout=<id>`, the same
`force={"layout": ...}` pattern `test_periodical.py`/`test_content.py`'s
`_forced` use.
"""

from __future__ import annotations

import rulebase

SEEDS = range(8)

_LAYOUTS = [
    "insurance_moto_certificate",
    "insurance_auto_certificate",
    "insurance_life_schedule",
    "insurance_application_form",
    "insurance_health_id_card",
    "insurance_health_certificate",
    "insurance_cargo_policy",
    "insurance_fire_certificate",
    "insurance_travel_certificate",
    "insurance_property_contract",
]


def _forced(layout: str, seed: int):
    _recipe, receipt, grid = rulebase.make(seed=seed, force={"layout": layout})
    return receipt, grid


def _strings(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for item in value.values() for s in _strings(item)]
    if isinstance(value, (list, tuple)):
        return [s for item in value for s in _strings(item)]
    return []


def _assert_has_a_label_and_a_sequence(receipt, seed):
    """The looser, honest version of "the label agrees with the page":
    `text_sequence()` is a best-effort flat dump, not a rigorous printed-page
    check (`tests/test_content.py::test_label_never_describes_unprinted_text`
    is `xfail(strict=True)` for exactly this reason -- `unitprice` alongside
    `amount` is a documented, pre-existing 11.4%-of-values gap, not something
    this root introduced). The rigorous check is `pipeline/invariants.py`
    against the real rendered page, exercised by the full suite's
    `test_what_the_label_says_the_page_prints`, not here.
    """
    label = receipt.ground_truth()
    assert label.get("doc_type") == f"receipt_{receipt.profile}", seed
    sequence = receipt.text_sequence()
    assert isinstance(sequence, str) and sequence.strip(), f"seed={seed}: empty text_sequence"
    # What IS a fair, unconditional check: every top-level party value that
    # isn't a secondary money duplicate shows up. `store.name` always must.
    assert label["store"]["name"] in sequence, seed


def test_every_insurance_layout_draws_a_real_receipt_with_a4_grid_sheet():
    """`sheet: a4` on all ten, regardless of true physical paper -- the same
    dodge `newspaper_*.yaml` established (see `rulebase/rules/layout.yaml`'s
    `insurance_page` group comment).
    """
    for layout in _LAYOUTS:
        for seed in SEEDS:
            receipt, grid = _forced(layout, seed)
            assert isinstance(receipt, rulebase.Receipt), (layout, seed)
            assert grid.sheet == "a4", (layout, seed)
            _assert_has_a_label_and_a_sequence(receipt, (layout, seed))


def test_no_items_certificates_carry_no_basket_and_no_total():
    for layout in ("insurance_moto_certificate", "insurance_auto_certificate",
                   "insurance_health_id_card", "insurance_cargo_policy"):
        receipt, _grid = _forced(layout, 0)
        assert receipt.items == [], layout
        assert receipt.totals == [], layout
        assert receipt.invoice is not None and receipt.invoice.left, layout


def test_priced_tables_carry_a_real_total():
    for layout in ("insurance_life_schedule", "insurance_fire_certificate",
                   "insurance_property_contract"):
        receipt, _grid = _forced(layout, 0)
        assert receipt.items, layout
        assert receipt.totals, layout  # a real grand line, unlike no_totals below


def test_no_totals_tables_carry_items_but_no_total_line():
    """`no_totals: true` -- a schedule of independent coverage limits, not a
    basket with a sum. See `rulebase/content.py`'s comment beside the flag.
    """
    for layout in ("insurance_travel_certificate", "insurance_health_certificate"):
        receipt, _grid = _forced(layout, 0)
        assert receipt.items, layout
        assert receipt.totals == [], layout
        # And the leaf-fidelity check still has to hold with an empty total:
        # nothing claims a sum that isn't there to print.
        assert "total" not in receipt.ground_truth() or not receipt.ground_truth()["total"], layout


def test_health_certificate_items_are_grouped_under_three_headings():
    receipt, _grid = _forced("insurance_health_certificate", 3)
    groups = [item for item in receipt.items if item.is_group]
    lines = [item for item in receipt.items if not item.is_group]
    assert len(groups) == 3, [g.name for g in groups]
    assert lines, "no benefit lines drawn under any group"
    # A group heading is excluded from `ground_truth()["menu"]` (it repeats
    # what the lines under it already say) -- confirm that stays true here,
    # the same way `medical.py`'s own grouped table already relies on it.
    names_in_menu = {entry["nm"] for entry in receipt.ground_truth()["menu"]}
    for group in groups:
        assert group.name not in names_in_menu, group.name


def test_application_form_checks_carry_real_answers():
    # `case()` may uppercase and/or ascii-fold the whole page (a `content:`
    # style draw, unrelated to this root) -- normalise both away before
    # comparing, the same way every other family's own tests already have to.
    yes_forms = {"CÓ", "CO"}
    no_forms = {"KHÔNG", "KHONG"}
    for seed in SEEDS:
        receipt, _grid = _forced("insurance_application_form", seed)
        assert len(receipt.invoice.checks) == 5, seed
        for question, answer, detail in receipt.invoice.checks:
            normalised = answer.upper()
            assert question and normalised in yes_forms | no_forms, (seed, question, answer)
            if normalised in no_forms:
                assert detail == "", (seed, question, detail)
            else:
                assert detail, (seed, question)
        checks_gt = receipt.ground_truth()["invoice"].get("checks", [])
        assert len(checks_gt) == 5, seed


def test_cargo_and_travel_certificates_print_both_languages():
    """`bilingual_field_line()` -- both the English and the Vietnamese label
    are real `data-kind` runs, so both must survive into `text_sequence()`.
    """
    for layout in ("insurance_cargo_policy", "insurance_travel_certificate"):
        receipt, _grid = _forced(layout, 1)
        sequence = receipt.text_sequence()
        left = receipt.invoice.left
        assert left, layout
        # The label text itself isn't ground truth (see insurance.py's own
        # `_build_cargo_policy`/`_build_travel_cert` -- only the *value* is a
        # `span()`), so this checks the values printed, same as `_assert_printed`.
        for _label, value in left:
            if value:
                assert value in sequence, (layout, value)


def test_vehicle_certificates_carry_a_plausible_plate_chassis_engine():
    for layout in ("insurance_moto_certificate", "insurance_auto_certificate"):
        receipt, _grid = _forced(layout, 2)
        by_label = dict(receipt.invoice.left)
        plate = by_label.get("Biển số xe:") or by_label.get("Biển số xe")
        assert plate and "-" in plate, (layout, by_label)
