"""Per-image invariants: one mutation each, because a check nobody broke is a guess.

W0 shipped a test suite that passed after the code under it was deleted -- the
assertion was `printed in label`, and a truncated string is a *prefix*, so it
stayed true. The lesson written down as Law 1 is that an invariant is worth what
its mutation is worth, so every rule `pipeline/invariants.py` states has a test
here that breaks exactly that rule and expects it to be seen.

Records are built from `rulebase.make()` rather than read from `data/`, so this
runs in the dependency-free `tests` CI job and does not go stale when a dataset
is regenerated. The one exception is `jpeg_size`, which needs a real JPEG and
uses a committed one.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import rulebase
from pipeline import invariants, record
from pipeline.invariants import BUDGETS, InvariantError, Tally, inspect

REPO_ROOT = Path(__file__).resolve().parent.parent
ORDER = invariants.attribute_names()

# The size these records claim their page is. Nothing here draws one, so it is
# arbitrary -- except in the two tests that pass a real image, which set it to
# that image's own size, because a record that disagrees with its pixels is now
# an error in its own right.
PAGE = (1000, 1400)

# Chosen for what they contain, and PINNED so they keep containing it: an
# eatery roll that prints no title, two market receipts that carry barcodes and
# weights, and two invoices. Unpinned, these were five bare seeds -- and a bare
# seed draws whatever the rules currently offer, so adding a document type
# silently turned the "eatery with a subtotal" into something else and three
# tests about budgets started failing for a reason none of them was about.
CASES = (
    # First, and `a_record()` returns the first: a layout that prints
    # everything it is given, so a test that removes one field measures that
    # field and nothing else.
    (3, "eatery_indexed"),
    (11, "market_compact"),
    (27, "market_barcode"),
    (40, "invoice_vat_form"),
    (41, "invoice_hotel_stay"),
)
SEEDS = tuple(seed for seed, _layout in CASES)


class Page:
    """A metadata line and the provenance beside it -- which is two files now.

    `pipeline/record.py` writes what a converted page looks like and nothing
    else; the recipe and the layout live in `synthesis.json`. The checks take
    both, so the tests hold both, and a test that mutates one is visibly
    mutating one and not the other.
    """

    def __init__(self, item: dict, recipe: dict, layout: str) -> None:
        self.item = item
        self.recipe = recipe
        self.layout = layout

    def copy(self) -> "Page":
        return Page(json.loads(json.dumps(self.item)),
                    json.loads(json.dumps(self.recipe)), self.layout)

    @property
    def attributes(self) -> dict:
        return self.recipe["attributes"]

    def errors(self, **kwargs) -> list[str]:
        return self.observe(**kwargs).errors

    def observe(self, order=ORDER, **kwargs):
        return inspect(self.item, order=order, recipe=self.recipe,
                       layout=self.layout, **kwargs)

    def into(self, tally: Tally, **kwargs):
        return tally.inspect(self.item, recipe=self.recipe, layout=self.layout,
                             **kwargs)


def build(seed: int, layout: str | None = None) -> Page:
    """One page as a renderer that drew every cell would write it."""
    recipe, receipt, grid = rulebase.make(
        seed=seed, force={"layout": layout} if layout else None)
    boxes = [
        # A real box also carries a quad; the frame check is the only invariant
        # that reads one, and the tests that exercise it add their own.
        {"kind": cell.role, "text": cell.text, "quad": [[0, 0], [1, 0], [1, 1], [0, 1]]}
        for cell in grid.cells if cell.text.strip() and cell.role != "sep"
    ]
    item = record.build(
        filename=f"test_{seed:03d}.jpg", width=PAGE[0], height=PAGE[1],
        parser="test", layout=grid.layout_id, boxes=boxes, seed=seed,
        extracted=receipt.ground_truth())
    return Page(item, recipe.to_dict(), grid.layout_id)


_RECORDS: list[Page] | None = None


def records() -> list[Page]:
    global _RECORDS
    if _RECORDS is None:
        _RECORDS = [build(seed, layout) for seed, layout in CASES]
    return _RECORDS


def errors_of(page: Page, **kwargs) -> list[str]:
    return page.errors(**kwargs)


def a_record(**wanted) -> Page:
    """A deep copy of the first page matching `wanted`, safe to mutate."""
    for page in records():
        gt = page.item["extracted"]
        if all(key in gt and gt[key] for key in wanted.get("has", ())):
            return page.copy()
    raise AssertionError(f"no seed in {SEEDS} produced a record with {wanted}")


# ------------------------------------------------------- no false positives


def test_a_faithfully_drawn_page_raises_nothing():
    """Criterion 3: the invariants must be silent on correct output."""
    tally = Tally(ORDER)
    for item in records():
        item.into(tally, where=item.item["filename"])
    assert tally.images == len(SEEDS)
    assert tally.problems() == []


# --------------------------------------------- the label against the boxes


def test_a_known_suppressed_field_is_budgeted_not_errored():
    item = a_record()
    gt = item.item["extracted"]
    gt["title"] = "MOT TIEU DE KHONG HE IN RA"
    item.item["extracted"] = gt
    out = item.observe()
    assert out.errors == []
    assert out.unprinted == {"title": 1}


def test_a_field_outside_the_known_set_is_an_error():
    """Criterion 2, and the whole reason the budget is per field.

    `store.name` is printed by every layout. If an unprinted one were counted
    against a shared ceiling it would hide under the 12% the known defect
    already uses; here it stops the first image that shows it.
    """
    item = a_record()
    gt = item.item["extracted"]
    gt["store"]["name"] = "CUA HANG KHONG TON TAI TREN ANH"
    item.item["extracted"] = gt
    errors = errors_of(item)
    assert any("store.name" in e and "not a field any layout" in e for e in errors), errors


def test_every_budgeted_field_is_one_no_layout_prints_reliably():
    """The budget list is a claim about the rule-base; check it is still true.

    A field added to BUDGETS that every layout does print would be a hole
    nobody opened deliberately.
    """
    assert set(BUDGETS) == {
        "menu.unitprice", "menu.vatrate", "menu.barcode", "title",
        "store.address", "store.address2", "store.branch", "store.phone",
        "menu.unitprice_per_unit", "menu.weight", "menu.discountprice",
    }


def test_every_suppressed_pair_names_a_field_that_has_a_budget():
    """`SUPPRESSED` may only excuse fields the budget list already knows about."""
    for layout, fields in invariants.SUPPRESSED.items():
        assert set(fields) <= set(BUDGETS), layout


def test_an_unprinted_total_is_an_error_not_a_budget_line():
    item = a_record()
    gt = item.item["extracted"]
    label = next(iter(gt["total"]))
    gt["total"][label] = "999.999.999"
    item.item["extracted"] = gt
    errors = errors_of(item)
    assert any("total" in e for e in errors), errors


def test_wrapped_text_is_still_printed():
    """A dish name split over two rows is on the page and must not be a miss."""
    item = a_record()
    gt = item.item["extracted"]
    name = gt["menu"][0]["nm"]
    if " " not in name:
        pytest.skip("this seed's first dish is one word, so it cannot wrap")
    head, _, tail = name.partition(" ")
    for position, box in enumerate(item.item["blocks"]):
        if box["text"] == name:
            box["text"] = head
            # Inserted next to its own head, which is where the second row of a
            # wrapped name actually lands in reading order.
            item.item["blocks"].insert(
                position + 1,
                {"kind": box["kind"], "text": tail, "quad": box["quad"]})
            break
    assert errors_of(item) == []


def test_wrapped_text_is_still_printed_across_a_hyphen():
    """Same wrap, but at a HYPHEN -- which leaves no space to rejoin on.

    Not hypothetical: a real hospital-bill item name, "[Thu tiền chênh lệch
    giá] SOLI-MEDON 40", wraps across two rows as "...SOLI-" then "MEDON 40"
    -- measured off an actual Chromium render, `page.py`'s `CELL_RECTS_JS`
    splits a wrapped run at the character, not the word, and a hyphen has no
    space either side of it. `by_kind`'s space-joined reconstruction in
    `invariants.py` used to read "SOLI- MEDON 40", one character short of the
    label. None of this file's five seeds happens to draw a hyphenated dish
    name on its own, so this rewrites one in place rather than skip the case
    the bug actually lives in.
    """
    item = a_record()
    gt = item.item["extracted"]
    name = gt["menu"][0]["nm"]
    hyphenated = f"{name}-MEDON 40"
    gt["menu"][0]["nm"] = hyphenated
    head, sep, tail = hyphenated.rpartition("-")
    for position, box in enumerate(item.item["blocks"]):
        if box["text"] == name:
            box["text"] = head + sep       # "...SOLI-", no trailing space
            item.item["blocks"].insert(
                position + 1,
                {"kind": box["kind"], "text": tail, "quad": box["quad"]})
            break
    assert errors_of(item) == []


# ----------------------------------------------------------- the arithmetic


def test_a_line_that_does_not_multiply_out_is_caught():
    item = a_record()
    gt = item.item["extracted"]
    entry = next(e for e in gt["menu"] if "unitprice" in e)
    entry["price"] = "1.234.567"
    item.item["extracted"] = gt
    errors = errors_of(item)
    assert any("price is" in e for e in errors), errors


def test_lines_that_do_not_add_to_the_subtotal_are_caught():
    for item in records():
        gt = item.item["extracted"]
        labels = item.attributes["document"]["params"].get("total_labels") or {}
        if not any(invariants._fold(k) == invariants._fold(labels.get("subtotal", "\0"))
                   for k in gt["total"]):
            continue
        copy = item.copy()
        gt = copy.item["extracted"]
        # Drop one line: the remaining ones no longer reach the printed subtotal.
        gt["menu"] = gt["menu"][:-1]
        copy.item["extracted"] = gt
        errors = errors_of(copy)
        assert any("add to" in e for e in errors), errors
        return
    pytest.skip(f"no seed in {SEEDS} printed a subtotal")


def test_change_that_is_not_cash_minus_total_is_caught():
    for item in records():
        gt = item.item["extracted"]
        labels = item.attributes["document"]["params"].get("total_labels") or {}
        keys = [invariants._fold(k) for k in gt["total"]]
        change = invariants._fold(labels.get("change", "\0"))
        grand = invariants._fold(labels.get("grand", "\0"))
        if change not in keys or grand not in keys:
            continue
        if keys.index(change) - 1 == keys.index(grand):
            continue  # the collapsed-label case; it has its own test
        copy = item.copy()
        gt = copy.item["extracted"]
        key = list(gt["total"])[keys.index(change)]
        gt["total"][key] = "7.777.777"
        copy.item["extracted"] = gt
        errors = errors_of(copy)
        assert any("minus" in e for e in errors), errors
        return
    pytest.skip(f"no seed in {SEEDS} printed both a total and change")


def test_a_total_row_the_label_cannot_carry_stops_the_shard():
    """Counted for three waves, and it stayed in the shipped data for three.

    `total` in `ground_truth` is a dict keyed by the drawn label, so two rows
    printed under one label collapse into one entry: the reader sees both
    amounts and the ground truth carries one. It was a note --
    `total_label_collapsed` -- on the grounds that W4 rewrites these labels
    anyway, and a count nobody trips over is a defect with a hiding place. It
    is an error now.

    Constructed rather than waited for: the page has to *print* the doubled
    label, so the boxes are what says so.
    """
    item = a_record()
    boxes = [box for box in item.item["blocks"]
             if str(box["kind"]).startswith("total.")
             and str(box["kind"]).endswith(".label")]
    if len(boxes) < 2:
        pytest.skip("this seed printed a single total line")
    boxes[1]["text"] = boxes[0]["text"]          # the page draws one label twice

    out = item.observe()
    assert out.notes == {}
    assert any("in no label" in error or "one printed amount" in error
               for error in out.errors), out.errors

    with pytest.raises(InvariantError):
        tally = Tally(ORDER)
        item.into(tally)


def test_total_rows_that_all_differ_are_silent():
    """The opposite case, so the check is not simply always on."""
    item = a_record()
    out = item.observe()
    assert not [e for e in out.errors if "in no label" in e], out.errors


# ------------------------------------------------------------- the pixels


def test_a_quad_outside_the_frame_is_caught(tmp_path):
    image = REPO_ROOT / "data" / "dataset60" / "html" / "html_000.jpg"
    width, height = invariants.jpeg_size(image)
    item = a_record()
    item.item["pages"][0].update(width=width, height=height)
    for box in item.item["blocks"]:
        box["quad"] = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert errors_of(item, image=image) == []

    item.item["blocks"][0]["quad"] = [[0, 0], [width + 40, 0],
                                [width + 40, height + 40], [0, height + 40]]
    errors = errors_of(item, image=image)
    assert any("outside the" in e for e in errors), errors


def test_a_page_size_that_disagrees_with_the_image_is_caught():
    """`pages[0]` states a size, so a wrong one is a defect of its own.

    Every bbox in the record is in the coordinates of that page. A record that
    claims a page twice the size of the image it points at has no quad outside
    the frame -- they are all comfortably inside a frame that does not exist --
    and every box is at half the scale a loader will draw it at.
    """
    image = REPO_ROOT / "data" / "dataset60" / "html" / "html_000.jpg"
    width, height = invariants.jpeg_size(image)
    item = a_record()
    item.item["pages"][0].update(width=width, height=height)
    for box in item.item["blocks"]:
        box["quad"] = [[0, 0], [10, 0], [10, 10], [0, 10]]
    assert errors_of(item, image=image) == []

    item.item["pages"][0]["width"] = width * 2
    errors = errors_of(item, image=image)
    assert any("says the page is" in e for e in errors), errors


def test_an_unreadable_image_is_unchecked_rather_than_fine(tmp_path):
    """Law 3: not being able to look is not the same as nothing being wrong."""
    broken = tmp_path / "not_really.jpg"
    broken.write_bytes(b"this is not a JPEG")
    out = a_record().observe(image=broken)
    assert out.errors == []
    assert out.unchecked and out.unchecked[0].startswith(invariants.UNCHECKED)

    tally = Tally(ORDER)
    a_record().into(tally, image=broken)
    assert any(p.startswith(invariants.UNCHECKED) for p in tally.problems())


def test_jpeg_size_reads_what_the_renderers_wrote():
    for framework in ("synthdog", "html", "genalog"):
        image = next((REPO_ROOT / "data" / "dataset60" / framework).glob("*.jpg"))
        size = invariants.jpeg_size(image)
        assert size is not None, image
        assert size[0] > 100 and size[1] > 100, (image, size)


# --------------------------------------------------------------- the text


@pytest.mark.parametrize("text", ["", "   "])
def test_a_box_with_no_text_is_caught(text):
    item = a_record()
    item.item["blocks"][0]["text"] = text
    errors = errors_of(item)
    assert any("no text" in e for e in errors), errors


@pytest.mark.parametrize("bad", ["�", "□"])
def test_a_missing_glyph_in_a_box_is_caught(bad):
    item = a_record()
    item.item["blocks"][0]["text"] = f"TIEN{bad}MAT"
    errors = errors_of(item)
    assert any("missing glyph" in e for e in errors), errors


@pytest.mark.parametrize("bad", ["�", "□"])
def test_a_missing_glyph_in_the_label_is_caught(bad):
    item = a_record()
    gt = item.item["extracted"]
    gt["store"]["name"] = f"CUA{bad}HANG"
    item.item["extracted"] = gt
    errors = errors_of(item)
    assert any("missing glyph" in e for e in errors), errors


# ------------------------------------------------------------ the recipe


@pytest.mark.parametrize("attribute", ORDER)
def test_a_recipe_missing_any_declared_attribute_is_caught(attribute):
    item = a_record()
    item.attributes.pop(attribute)
    errors = errors_of(item)
    assert any(attribute in e and "_order.yaml" in e for e in errors), errors


def test_the_attribute_list_comes_from_the_manifest_not_from_six(tmp_path):
    """Criterion 7: a seventh attribute must not break the check.

    A probe attribute is added to a copy of the rules and the recipe is given a
    seventh entry. Code that counted six would reject a perfectly good record;
    code that reads `_order.yaml` accepts it and would reject one that left the
    probe out.
    """
    import shutil

    from rulebase.spec import RULES_ROOT, attribute_order

    root = tmp_path / "rules"
    shutil.copytree(RULES_ROOT, root)
    (root / "probe.yaml").write_text(
        "values:\n  - id: only_value\n    weight: 1\n", encoding="utf-8")
    order = root / "_order.yaml"
    order.write_text(order.read_text(encoding="utf-8") + "  - probe\n", encoding="utf-8")

    probed = attribute_order(root)
    assert probed[-1] == "probe" and len(probed) == len(ORDER) + 1

    item = a_record()
    item.attributes["probe"] = {"id": "only_value", "params": {}}
    assert item.observe(order=probed).errors == []

    item.attributes.pop("probe")
    assert any("probe" in e for e in item.observe(order=probed).errors)


# ------------------------------------------------------------- the budgets


def regressed(layout: str, images: int, fields=("branch", "address", "address2", "phone")) -> Tally:
    """A shard of `images` pages in a layout that stopped printing store fields."""
    tally = Tally(ORDER)
    for _ in range(images):
        item = a_record()
        item.layout = layout
        gt = item.item["extracted"]
        for key in fields:
            gt["store"][key] = f"KHONG IN RA {key}"
        item.item["extracted"] = gt
        item.into(tally)
    return tally


def test_a_field_over_its_budget_is_reported():
    """Constructed, not waited for: outside SUPPRESSED the real rate is zero."""
    tally = regressed("a_layout_with_a_regression", 8)
    problems = tally.problems()
    assert problems, tally.report()
    assert all("store." in p and "over its budget" in p for p in problems), problems
    # Four store fields, four separately named verdicts -- not one rolled-up
    # number that a reader has to take apart.
    assert len(problems) == 4, problems


def test_a_regression_in_one_field_is_not_masked_by_the_volume_of_another():
    """Criterion 4, in the form that actually matters.

    `menu.barcode` occurs once per line and `store.phone` once per receipt, so a
    shared denominator would let a total loss of the phone number disappear
    under a percent. Each field is scored against its own occurrences.
    """
    tally = regressed("a_layout_with_a_regression", 8, fields=("phone",))
    problems = tally.problems()
    assert len(problems) == 1 and "store.phone" in problems[0], problems


def test_a_pair_already_recorded_as_suppressed_is_counted_not_judged():
    """The known defect must be measured every shard, and must not fail it."""
    tally = Tally(ORDER)
    for item in records():
        item.into(tally)
    report = tally.report()
    assert tally.problems() == []
    counted = {(layout, name)
               for layout, fields in report["unprinted"].items() for name in fields}
    assert counted, "the known defect vanished from the measurement"
    for layout, name in counted:
        assert name in invariants.SUPPRESSED.get(layout, frozenset()), (layout, name)


def test_a_single_stray_value_does_not_trip_a_budget():
    """MIN_COUNT: one value in a small shard is noise, not a regression."""
    tally = Tally(ORDER)
    strayed = a_record()
    strayed.layout = "a_layout_that_prints_everything"
    gt = strayed.item["extracted"]
    gt["store"]["address"] = "MOT DIA CHI KHONG IN RA"
    strayed.item["extracted"] = gt
    strayed.into(tally)

    assert tally.problems() == []
    layout = strayed.layout
    assert tally.report()["unprinted"][layout]["store.address"] == 1


def test_the_budget_is_scored_against_one_layout_not_the_shard():
    """Why the verdict is per (layout, field), asserted.

    Padding a shard with pages from a layout that suppresses nothing must not
    dilute a real regression in another layout away.
    """
    tally = regressed("a_layout_with_a_regression", 8)
    assert tally.problems()
    for _ in range(40):                      # forty clean pages of another layout
        clean = a_record()
        clean.layout = "a_layout_that_is_fine"
        clean.into(tally)
    assert tally.problems(), "a clean layout diluted another layout's regression"


# --------------------------------------------------------------- the report


def test_the_report_is_a_function_of_the_shard_alone():
    """Law 5: comparable, so no clock, no PID, no path."""
    def run() -> str:
        tally = Tally(ORDER)
        for item in records():
            item.into(tally, where=item.item["filename"])
        return json.dumps(tally.report(), sort_keys=True, ensure_ascii=False)

    assert run() == run()
    text = run()
    assert '"/' not in text and "\\\\" not in text



# ------------------------------------------------- the data that was shipped


SHIPPED = [path for path in (REPO_ROOT / "data").glob("*/*/metadata.jsonl")]


@pytest.mark.skipif(not SHIPPED, reason="no dataset is committed")
def test_no_shipped_image_prints_a_total_row_the_label_cannot_carry():
    """Law 9: a defect is closed on the population that shipped, or not at all.

    This one was reported closed on 1500 freshly drawn receipts while six of
    the hundred and twenty committed images still carried it. Fresh draws are a
    different population -- no pins, no `force`, another distribution -- so they
    could not have answered the question. The committed files can, and this is
    the check that asks them.
    """
    import collections
    import json

    bad = []
    for index in SHIPPED:
        for line in index.read_text(encoding="utf-8").splitlines():
            record = json.loads(line)
            drawn = [box["text"] for box in record.get("boxes", ())
                     if str(box["kind"]).startswith("total.")
                     and str(box["kind"]).endswith(".label")]
            doubled = [t for t, c in collections.Counter(drawn).items() if c > 1]
            if doubled:
                bad.append(f"{index.parent.parent.name}/{record['file_name']}: {doubled}")
    assert not bad, "\n".join(bad)
