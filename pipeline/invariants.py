"""What must be true of every image, checked while it is still cheap to say so.

`record.validate()` checks the *shape* of a metadata line: the keys are there,
the quad has four corners, `extracted` is an object. That catches a renderer
that forgot a field. It does not catch a renderer that filled every field with
something wrong, and it is the second kind that produces a dataset which loads,
trains, and teaches a model to hallucinate.

This module checks the *content*, on every image, from the record alone:

* every value in `extracted` is text some block actually printed;
* `cnt x unitprice == price` on each line, the lines add up to the subtotal,
  and cash minus total is the change;
* every quad lies inside the frame;
* no text is empty, and none carries a replacement character (U+FFFD) or the
  missing-glyph box (U+25A1);
* `recipe` names every attribute `rules/_order.yaml` declares.

**Blocks are the definition of "printed".** Not `synthesis.text_sequence` --
that is built from the `Receipt`, so it lists a phone number the layout never
had room for and would agree with the label about text no reader can see.
`blocks` comes from the renderer's own geometry, one per drawn cell, and
`tools/check_boxes.py` verifies against the pixels that this is so.

The budget, and why it is not one number
----------------------------------------

Layouts deliberately drop fields they have no column for -- `market_compact`
prints no barcode, `eatery_ascii` prints no title -- while `ground_truth()` still
reports them. It is a real defect, measured at 9.5-12.4% of label values, and W4
fixes it when it regenerates the datasets anyway. W2 measures it.

The tempting way to measure it is one ratio against one ceiling. That would be a
new bucket to swallow errors: a different defect appearing at 2% would sit under
a 13% ceiling forever without anyone seeing it. So the check is in two parts, and
neither is a single number.

**Which fields.** `BUDGETS` names the ten fields any layout is known to suppress.
A value that no box printed, in a field outside that list, is an **error on the
first image** -- not a budget line, not a warning.

**How much, and where.** Measurement says the defect is not a rate at all: it is
a property of a *pair*. `market_compact` prints no barcode on any receipt, ever;
`eatery_indexed` prints all of them. So `SUPPRESSED` records the pairs, and a
pair that is not in it -- a known field going missing in a layout that used to
print it -- is judged against that field's budget, as a share of that field's own
occurrences in that layout.

That is what makes the number mean something. A ratio taken over the whole shard
would rise and fall with which layouts landed in it, and any ceiling loose enough
never to trip on `market_compact` would be far too loose to notice a sixth layout
quietly dropping the same field. Judging per pair removes the mix from the
question entirely.

Everything here is a deterministic function of the record and the image bytes:
no clock, no PID, no absolute path. `report()` is therefore comparable between
two runs, which is what T-10 aggregates and W1's byte-for-byte manifest check
depends on.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

import profiling
from pipeline import record

# Same convention as `pipeline/preflight.py`: a check that could not run is not
# a check that passed, and it says which of the two it was.
UNCHECKED = "unchecked:"

# What a shard leaves beside its metadata. Named here rather than in the worker
# so `pipeline/drift.py` can read it without importing the module that writes it.
INVARIANTS_NAME = "invariants.json"

# The augmentation value whose chain is empty -- what `--clean` pins. Named
# rather than inlined so renaming it in rules/augmentation.yaml fails loudly
# instead of silently producing an aged "clean" set.
CLEAN_AUGMENTATION = "pristine"

# Characters that mean a font had nothing to draw. They reach the label only
# through a corpus or a font change, and both are worth stopping for.
REPLACEMENT = "�"
MISSING_GLYPH = "□"

# The ten fields a layout is known to suppress, and how much of one may go
# unprinted in a layout that is NOT recorded below as suppressing it. Anything
# not named here is an error, whatever its rate; that is the point of the list.
#
# The ceilings are uniform, and deliberately so: measured over 360 images, the
# rate outside `SUPPRESSED` is zero for all ten. There is no per-field evidence
# to spread them apart with, and inventing different numbers to look thorough
# would be a worse lie than one honest number repeated. What is per field is the
# *verdict*: a regression in `store.phone` is reported as `store.phone` and
# cannot be padded out of sight by the volume of `menu.barcode`.
#
# 5% leaves room for a value that fails to match on whitespace or a stray
# separator without failing a shard; a layout that stops printing a field lands
# near 100% and is nowhere close to it.
BUDGETS: dict[str, float] = {
    "menu.barcode": 0.05,
    "menu.unitprice": 0.05,
    "menu.unitprice_per_unit": 0.05,
    "menu.vatrate": 0.05,
    "menu.weight": 0.05,
    "store.address": 0.05,
    "store.address2": 0.05,
    "store.branch": 0.05,
    "store.phone": 0.05,
    "title": 0.05,
}

# layout -> the fields it does not print. Measured over `data/dataset60` and
# `data/dataset60_clean` (360 images, 5890 label values); the share of each
# field's own occurrences that goes unprinted is in the comment beside it. They
# are near-total, which is the finding: this is not a rate, it is a column that
# does not exist.
#
# A pair here is expected and only counted. A pair *not* here is measured
# against the budget above -- so a sixth layout that drops a barcode has to be
# added deliberately rather than arriving unnoticed.
SUPPRESSED: dict[str, frozenset[str]] = {
    "eatery_ascii": frozenset({
        "menu.unitprice",            # 63.6% -- matches when qty is 1 and it equals the line
        "title",                     # 100%
    }),
    "market_barcode": frozenset({
        "menu.unitprice_per_unit",   # 100%
        "menu.vatrate",              # 93.3% -- the rate also appears in the VAT total's label
    }),
    "market_compact": frozenset({
        "menu.barcode",              # 100%
        "menu.unitprice_per_unit",   # 100%
        "menu.vatrate",              # 82.4%
        "menu.weight",               # 100%
        "store.address",             # 100%
        "store.address2",            # 100%
        "store.branch",              # 100%
        "store.phone",               # 100%
    }),
    "market_vat": frozenset({
        "menu.unitprice_per_unit",   # 100%
        "menu.weight",               # 100%
        "store.branch",              # 100%
    }),
    "eatery_indexed": frozenset(),   # prints everything it is given
}

# A budget is only consulted once this many values of that field failed to
# print in that layout. One stray value in a three-image shard is noise; a
# layout that stopped printing a column produces them by the dozen.
MIN_COUNT = 5

# Money differing by less than this is the same amount. Values are whole đồng
# except in `comma_2dp`, where they carry two decimals.
EPSILON = 0.5

_MONEY = re.compile(r"[^0-9.,]")


class InvariantError(ValueError):
    """An image says something about itself that is not true."""


# ------------------------------------------------------------------ helpers


def _fold(text: str) -> str:
    """Compare two labels without caring about case or diacritics.

    `total_labels` comes from the recipe as it was written in the rules; what
    lands in `ground_truth` has been through `apply_case`, which may have
    uppercased it, stripped its diacritics, or both, and which of those
    happened is not recorded. Folding both sides is how the two are matched
    without inventing a field.
    """
    decomposed = unicodedata.normalize("NFD", text)
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.replace("đ", "d").replace("Đ", "D").upper().strip()


def _amount(text: str, style: str) -> float | None:
    """One printed amount, back to a number. None if it is not one."""
    if not isinstance(text, str):
        return None
    negative = text.strip().startswith("-")
    body = _MONEY.sub("", text)
    if not body:
        return None
    if style == "dot":
        body = body.replace(".", "").replace(",", ".")
    else:  # comma and comma_2dp both use ',' for thousands and '.' for decimals
        body = body.replace(",", "")
    try:
        value = float(body)
    except ValueError:
        return None
    return -value if negative else value


def leaves(value: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """(field, string) for every leaf string in a ground-truth structure.

    A list does not extend the path: `menu` is a list of entries and the field
    is `menu.nm`, not `menu.0.nm`. The budget is about a field, not a position.
    """
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from leaves(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from leaves(item, path)


def jpeg_size(path: Path) -> tuple[int, int] | None:
    """(width, height) from a JPEG header, without decoding the image.

    Reading a few hundred bytes rather than importing an imaging library keeps
    this runnable in the dependency-free `tests` CI job, and keeps the cost of
    the frame check at roughly a thousandth of what drawing the page cost.
    """
    try:
        with open(path, "rb") as handle:
            if handle.read(2) != b"\xff\xd8":
                return None
            while True:
                byte = handle.read(1)
                if not byte:
                    return None
                if byte != b"\xff":
                    continue
                while byte == b"\xff":       # fill bytes before the marker
                    byte = handle.read(1)
                if not byte:
                    return None
                marker = byte[0]
                if marker == 0xD9 or marker == 0xDA:  # end of image / start of scan
                    return None
                if marker == 0x01 or 0xD0 <= marker <= 0xD8:
                    continue                 # standalone markers carry no length
                header = handle.read(2)
                if len(header) < 2:
                    return None
                length = int.from_bytes(header, "big")
                # SOFn, excluding DHT (C4), JPG (C8) and DAC (CC)
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                    frame = handle.read(5)
                    if len(frame) < 5:
                        return None
                    return (int.from_bytes(frame[3:5], "big"),
                            int.from_bytes(frame[1:3], "big"))
                handle.seek(length - 2, 1)
    except OSError:
        return None


# ------------------------------------------------------------ one image


@dataclass
class Observation:
    """What one image was found to be. Deterministic; no time, no path."""

    layout: str = "?"
    values: int = 0                                   # label values examined
    boxes: int = 0
    errors: list[str] = field(default_factory=list)
    occurrences: dict[str, int] = field(default_factory=dict)   # budgeted fields only
    unprinted: dict[str, int] = field(default_factory=dict)
    notes: dict[str, int] = field(default_factory=dict)
    unchecked: list[str] = field(default_factory=list)


def _printed(boxes: list[dict]) -> tuple[str, dict[str, str]]:
    """The page as one string, and one string per box kind.

    Both are needed. A dish name too long for its column wraps across two rows
    and is two boxes, so it appears in neither alone; joining by kind puts it
    back together without letting an unrelated field match by accident, which
    joining everything would.
    """
    texts = [box.get("text", "") for box in boxes if isinstance(box, dict)]
    page = " ".join(" ".join(texts).split())
    by_kind: dict[str, list[str]] = {}
    for box in boxes:
        if isinstance(box, dict):
            by_kind.setdefault(str(box.get("kind", "?")), []).append(box.get("text", ""))
    return page, {kind: " ".join(" ".join(v).split()) for kind, v in by_kind.items()}


def _check_arithmetic(gt: dict, style: str, labels: dict, out: Observation) -> None:
    """The sums a till would have done, redone from the label alone."""
    menu = gt.get("menu")
    if not isinstance(menu, list):
        return

    lines: list[float | None] = []
    for position, entry in enumerate(menu):
        if not isinstance(entry, dict):
            continue
        amount = _amount(entry.get("price", ""), style)
        lines.append(amount)
        if "unitprice" not in entry or amount is None:
            continue
        count = _amount(entry.get("cnt", ""), style)
        unit = _amount(entry["unitprice"], style)
        if count is None or unit is None:
            out.errors.append(
                f"menu[{position}] {entry.get('nm', '?')!r}: cnt {entry.get('cnt')!r} or "
                f"unitprice {entry['unitprice']!r} is not a {style} amount")
        elif abs(count * unit - amount) > EPSILON:
            out.errors.append(
                f"menu[{position}] {entry.get('nm', '?')!r}: {entry.get('cnt')} x "
                f"{entry['unitprice']} = {count * unit:.0f}, but price is {entry['price']}")

    totals = gt.get("total")
    if not isinstance(totals, dict) or not totals:
        return
    keys = list(totals)
    values = [_amount(v, style) for v in totals.values()]
    folded = [_fold(k) for k in keys]

    def index_of(name: str | None) -> int | None:
        if not name:
            return None
        wanted = _fold(name)
        for position, key in enumerate(folded):
            if key == wanted:
                return position
        return None

    subtotal = index_of(labels.get("subtotal"))
    if subtotal is not None and values[subtotal] is not None and None not in lines:
        total = sum(x for x in lines if x is not None)
        if abs(total - values[subtotal]) > EPSILON:
            out.errors.append(
                f"the {len(lines)} lines add to {total:.0f}, but "
                f"{keys[subtotal]!r} says {totals[keys[subtotal]]}")

    grand = index_of(labels.get("grand"))
    change = index_of(labels.get("change"))
    if grand is not None and change is not None and change >= 1:
        if change - 1 == grand:
            pass                      # already reported above, by the page
        else:
            paid = values[change - 1]
            if None not in (paid, values[grand], values[change]):
                if abs(paid - values[grand] - values[change]) > EPSILON:
                    out.errors.append(
                        f"{keys[change - 1]!r} {totals[keys[change - 1]]} minus "
                        f"{keys[grand]!r} {totals[keys[grand]]} is not "
                        f"{keys[change]!r} {totals[keys[change]]}")


def _check_totals_survived(item, gt, out) -> None:
    """Every total row the page printed has to be in the label.

    `total` in `ground_truth` is a dict keyed by the *drawn label*, so two rows
    printed under one label collapse into one entry: the reader sees both
    amounts and the ground truth carries one. On `market_vat` the payment row
    and the grand total can both be drawn "Tiền khách trả", and the amount
    actually owed is the one that disappears.

    This was counted as a note until now -- `total_label_collapsed` -- on the
    grounds that W4 rewrites these labels anyway. It then sat in the shipped
    data through three waves, because a count nobody trips over is a defect
    with a hiding place. It stops the shard now, and whatever route still
    reaches it has to say so rather than be reasoned about in advance.

    Read off the boxes, not off the receipt: the boxes are the page's own
    account of what was drawn, so this cannot be satisfied by a renderer that
    agrees with a label they both got wrong.
    """
    totals = gt.get("total")
    if not isinstance(totals, dict) or not totals:
        return
    drawn = [str(box.get("text", "")) for box in record.boxes(item)
             if str(box.get("kind", "")).startswith("total.")
             and str(box.get("kind", "")).endswith(".label")]
    if not drawn:
        return                        # no boxes: `Tally` records that separately
    doubled = sorted({text for text in drawn if drawn.count(text) > 1})
    if doubled:
        out.errors.append(
            f"the page prints {len(drawn)} total rows under {len(set(drawn))} "
            f"labels -- {', '.join(repr(t) for t in doubled)} twice -- so the "
            f"`total` dict carries {len(totals)} and one printed amount is in "
            f"no label"
        )


def inspect(item: dict[str, Any], *, order: tuple[str, ...] | list[str],
            image: Path | None = None, where: str = "") -> Observation:
    """Everything one metadata line and its image say about themselves.

    Errors are collected rather than raised so a caller can report all of them
    for one page; `Tally.inspect` is the one that stops the shard.
    """
    out = Observation(layout=record.layout(item))
    prefix = f"{where}: " if where else ""

    attributes = record.attributes(item)
    for name in order:
        if name not in attributes:
            out.errors.append(f"recipe has no {name!r}, which rules/_order.yaml declares")
    style = "dot"
    labels: dict[str, str] = {}
    if isinstance(attributes, dict):
        content = (attributes.get("content") or {}).get("params") or {}
        document = (attributes.get("document") or {}).get("params") or {}
        style = str(content.get("money_style", "dot"))
        labels = document.get("total_labels") or {}

    boxes = record.boxes(item)
    out.boxes = len(boxes)
    page, by_kind = _printed(boxes)

    # --- text that no font could draw, on either side of the pairing
    for position, box in enumerate(boxes):
        text = box.get("text", "") if isinstance(box, dict) else ""
        if not str(text).strip():
            out.errors.append(f"boxes[{position}] has no text, so it labels nothing")
        elif REPLACEMENT in text or MISSING_GLYPH in text:
            out.errors.append(f"boxes[{position}] text {text!r} carries a missing glyph")

    # --- the frame
    if image is not None:
        size = jpeg_size(Path(image))
        if size is None:
            out.unchecked.append(
                f"{UNCHECKED} could not read the size of {Path(image).name}, so no "
                f"quad was checked against the frame")
        else:
            width, height = size
            # The record's own account of the page, against the pixels. New
            # with the converter shape: `pages[0]` states a size, and a record
            # that states the wrong one puts every bbox in it out of scale
            # without a single quad leaving the frame.
            stated = record.page_size(item)
            if stated != (0, 0) and stated != (width, height):
                out.errors.append(
                    f"pages[0] says the page is {stated[0]}x{stated[1]} where "
                    f"the image is {width}x{height}")
            for position, box in enumerate(boxes):
                quad = box.get("quad") if isinstance(box, dict) else None
                if not isinstance(quad, list):
                    continue
                for corner in quad:
                    try:
                        x, y = float(corner[0]), float(corner[1])
                    except (TypeError, ValueError, IndexError):
                        out.errors.append(f"boxes[{position}].quad has a bad corner")
                        break
                    # +-1 for the rounding every renderer does on the way out,
                    # the same tolerance tools/check_boxes.py uses.
                    if not (-1 <= x <= width + 1 and -1 <= y <= height + 1):
                        out.errors.append(
                            f"boxes[{position}] {box.get('text', '')!r} corner "
                            f"({x:.0f},{y:.0f}) is outside the {width}x{height} frame")
                        break

    # --- the label against what was drawn
    gt: dict[str, Any] = record.extracted(item)
    for name, value in leaves(gt):
        if not value.strip() or value.startswith("receipt_"):
            continue          # doc_type is a class, not text on the page
        out.values += 1
        if REPLACEMENT in value or MISSING_GLYPH in value:
            out.errors.append(f"label {name} {value!r} carries a missing glyph")
        # `total` keys are the printed labels themselves, so they vary per
        # receipt; they collapse to one family name, which is not in BUDGETS,
        # which means an unprinted total is an error.
        name = "total" if name.startswith("total.") else name
        if name in BUDGETS:
            out.occurrences[name] = out.occurrences.get(name, 0) + 1
        wanted = " ".join(value.split())
        if wanted in page or any(wanted in text for text in by_kind.values()):
            continue
        if name in BUDGETS:
            out.unprinted[name] = out.unprinted.get(name, 0) + 1
        else:
            out.errors.append(
                f"label {name} {wanted!r} appears on no box, and {name!r} is not a "
                f"field any layout is known to suppress")

    _check_arithmetic(gt, style, labels, out)
    _check_totals_survived(item, gt, out)

    if prefix:
        out.errors = [prefix + problem for problem in out.errors]
    return out


# --------------------------------------------------------------- one shard


class Tally:
    """Adds up observations, and judges the budgets once, at the end.

    Per-image judgement is not possible for a ratio: one page has twenty label
    values, so a single unprinted barcode is 5% of it. The errors above fire per
    image because they are absolute; the budgets fire per shard because they are
    proportions.
    """

    def __init__(self, order: tuple[str, ...] | list[str]):
        self.order = tuple(order)
        self.images = 0
        self.boxes = 0
        self.values: dict[str, int] = {}                     # layout -> label values
        self.occurrences: dict[str, dict[str, int]] = {}     # layout -> field -> count
        self.unprinted: dict[str, dict[str, int]] = {}       # layout -> field -> count
        self.notes: dict[str, int] = {}
        self.unchecked: list[str] = []

    def inspect(self, item: dict[str, Any], *, image: Path | None = None,
                where: str = "") -> Observation:
        """Check one image and keep the numbers. Raises on anything absolute."""
        with profiling.stage("validation"):
            out = inspect(item, order=self.order, image=image, where=where)
        if out.errors:
            raise InvariantError("\n".join(out.errors))
        self.images += 1
        self.boxes += out.boxes
        self.values[out.layout] = self.values.get(out.layout, 0) + out.values
        for target, source in ((self.occurrences, out.occurrences),
                               (self.unprinted, out.unprinted)):
            bucket = target.setdefault(out.layout, {})
            for name, count in source.items():
                bucket[name] = bucket.get(name, 0) + count
        for name, count in out.notes.items():
            self.notes[name] = self.notes.get(name, 0) + count
        self.unchecked += out.unchecked
        return out

    def problems(self) -> list[str]:
        """Budgets that were exceeded, plus anything that could not be looked at.

        A (layout, field) pair listed in `SUPPRESSED` is expected: it is counted
        into the report so W4 has a before and after, and it is not judged. Every
        other pair is.
        """
        problems: list[str] = []
        for layout in sorted(self.unprinted):
            known = SUPPRESSED.get(layout, frozenset())
            for name in sorted(self.unprinted[layout]):
                if name in known:
                    continue
                count = self.unprinted[layout][name]
                total = self.occurrences.get(layout, {}).get(name, 0)
                if not total or count < MIN_COUNT:
                    continue
                share = count / total
                if share > BUDGETS[name]:
                    problems.append(
                        f"{layout}: {name} went unprinted in {count} of {total} "
                        f"({share:.0%}), over its budget of {BUDGETS[name]:.0%}, and "
                        f"{layout} is not recorded as suppressing it")
        return problems + sorted(set(self.unchecked))

    def report(self) -> dict[str, Any]:
        """The numbers, as a shard writes them down. Comparable between runs.

        `unprinted` beside `occurrences` is the ruler W4 needs: after the label
        is fixed the first should go to zero while the second does not move.
        """
        return {
            "images": self.images,
            "boxes": self.boxes,
            "label_values": dict(sorted(self.values.items())),
            "occurrences": {layout: dict(sorted(fields.items()))
                            for layout, fields in sorted(self.occurrences.items())
                            if fields},
            "unprinted": {layout: dict(sorted(fields.items()))
                          for layout, fields in sorted(self.unprinted.items())
                          if fields},
            "notes": dict(sorted(self.notes.items())),
            "unchecked": sorted(set(self.unchecked)),
            "budgets": dict(sorted(BUDGETS.items())),
        }


# ------------------------------------------------- the plan, before rendering


# How many images per backend the content check actually rebuilds. The
# structural half is free and covers every image; this half costs a receipt
# each, so it is capped -- a 100k run must not spend minutes proving something
# a dozen pages already demonstrate.
PAIRED_SAMPLE = 12


def paired_content(plan: dict[str, Any], *, sample: int = PAIRED_SAMPLE) -> list[str]:
    """Under `paired`, check the backends really do draw the same receipts.

    Two halves, because they fail differently:

    * **structural** -- the (seed, layout, index) list must be identical for
      every backend. Free, covers every image, and catches the actual W1b
      defect: three backends on three disjoint seed blocks.
    * **content** -- rebuild a sample of images from *each backend's own* plan
      entry and check the sampler gives back what the plan claims: the seed it
      was asked for, the layout it was pinned to, and the same receipt for
      every backend. Comparing the three labels alone would be redundant with
      the structural half -- identical inputs to a deterministic function --
      so what earns this half its cost is the other two: a plan naming a layout
      the rules no longer have, or a sampler that has stopped returning the
      seed it was given, both of which look perfectly well-formed on paper and
      fail an hour into rendering.

    Returns problems, empty under `independent` -- where the backends are
    *supposed* to differ, so there is nothing here to check.
    """
    if plan.get("pairing", "paired") != "paired":
        return []

    jobs: dict[str, list[tuple[int, str, int]]] = {}
    for shard in plan.get("shards", []):
        entries = jobs.setdefault(shard["backend"], [])
        for run in shard["runs"]:
            for offset in range(run["count"]):
                entries.append((run["seed"] + offset, run["layout"],
                                run["first_index"] + offset))
    for entries in jobs.values():
        entries.sort(key=lambda entry: entry[2])

    problems: list[str] = []
    backends = sorted(jobs)
    if len(backends) < 2:
        return problems
    reference = backends[0]
    for backend in backends[1:]:
        if jobs[backend] != jobs[reference]:
            mismatched = [a for a, b in zip(jobs[backend], jobs[reference]) if a != b]
            problems.append(
                f"pairing is 'paired' but {backend} and {reference} do not draw the "
                f"same pages: {len(mismatched)} of {len(jobs[reference])} differ, "
                f"first at index {mismatched[0][2] if mismatched else '?'}")
    try:
        import rulebase
    except ImportError as error:  # pragma: no cover - rulebase is always there
        return problems + [
            f"{UNCHECKED} could not import rulebase ({error}), so no content "
            f"was compared"]

    for position in range(min(max(sample, 0), len(jobs[reference]))):
        labels: dict[str, str] = {}
        for backend in backends:
            if position >= len(jobs[backend]):
                continue
            seed, layout, index = jobs[backend][position]
            try:
                recipe, receipt, grid = rulebase.make(seed=seed,
                                                      force={"layout": layout})
            except Exception as error:  # noqa: BLE001 - a stale layout lands here
                problems.append(
                    f"{backend} image {index}: the plan asks for layout {layout!r} at "
                    f"seed {seed}, which the rules will not produce: {error}")
                continue
            if recipe.seed != seed:
                problems.append(
                    f"{backend} image {index}: asked for seed {seed}, the sampler "
                    f"returned {recipe.seed}; the plan cannot be reproduced from it")
            if grid.layout_id != layout:
                problems.append(
                    f"{backend} image {index}: pinned to layout {layout!r}, drew "
                    f"{grid.layout_id!r}")
            labels[backend] = json.dumps(receipt.ground_truth(), sort_keys=True,
                                         ensure_ascii=False)
        if len(set(labels.values())) > 1:
            differing = sorted(b for b in labels if labels[b] != labels.get(reference))
            problems.append(
                f"image {position} would be a different receipt in "
                f"{', '.join(differing)} than in {reference}, but pairing is 'paired'")
    return problems


def attribute_names() -> tuple[str, ...]:
    """The attributes a recipe must name, from `rules/_order.yaml`.

    Read, never hard-coded. A seventh attribute is a YAML file and a manifest
    line; if this said `6` that change would fail every image in the run.
    """
    from rulebase.spec import attribute_order

    return tuple(attribute_order())


__all__ = [
    "BUDGETS",
    "CLEAN_AUGMENTATION",
    "INVARIANTS_NAME",
    "MIN_COUNT",
    "SUPPRESSED",
    "UNCHECKED",
    "InvariantError",
    "Observation",
    "Tally",
    "attribute_names",
    "inspect",
    "jpeg_size",
    "leaves",
]
