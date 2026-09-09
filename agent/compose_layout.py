"""Mức 3 — the model COMPOSES a layout, instead of varying one.

    python -m agent.compose_layout --document invoice_detailed --explain
    python -m agent.compose_layout --document invoice_detailed --id invoice_kiosk
    python -m agent.compose_layout --document invoice_detailed --id invoice_kiosk --write

Three levels of redress exist in this package and they answer three different
questions about the same sheet of paper:

| level | module | what it may change | question it asks |
| --- | --- | --- | --- |
| 1 · reuse | `variants.py` | paint: rule weight, paper tint, type, ornament | *this sheet, in a different ink?* |
| 2 · redraw | `redesign.py`, `augment_layout.py` | block order, column count, where the totals sit | *this sheet, laid out differently?* |
| 3 · compose | **this module** | which blocks exist at all, which paper, how the page divides | *what would a DIFFERENT print shop have produced?* |

The difference from level 2 is not a bigger diff. Level 2 is handed a layout
file and edits it, so its output is always its input plus changes -- measured
at 0.764 mean distance by `agent/distance.py` over 306 redraws, and structurally
incapable of dropping a block its parent had. This module is handed *k*
reference layouts as **evidence about a document kind**, plus the field spec,
plus bounds, and writes a structure that was in none of them.

What the model returns is a **structure**, never markup
--------------------------------------------------------

`Composition` is blocks, columns, paper and reasoning. `to_layout()` -- code,
not the model -- turns it into the same `rulebase/layouts/*.yaml` a person
writes, and `generators/html/sheets/` turns that into HTML as it always has.

That is not tidiness, it is the label contract. Every run must be a `<span>`
holding escaped text and nothing else, because the measurement takes
`span.firstElementChild || span` -- **a nested tag quietly becomes the box that
gets recorded**. Measured: a `<sub>` in a formula made the box 5.3 px wide
instead of 310.6; an `<i>` in a citation made the box hug only the italic run.
A model writing HTML makes that contract depend on the model not forgetting, on
every page, across 5000 pages. A builder writing it makes it true by
construction. So no string this module accepts may contain `<`, and `check()`
refuses the whole composition over one.

The three layers, computed rather than asserted
------------------------------------------------

§8.1 of the spec splits a reference layout into legal invariants (on *every*
sheet), trade convention (on most), and the print shop's own choices (differing
between sheets) -- and says only the third may be touched. That is a claim
about a set of files, so it is read off the files: `layers()` intersects the
*k* references for what they all share and diffs them for what they do not.

A document whose references agree about everything has **no visible third
layer**, and `layers()` says so rather than inventing one. That is §8.2's
"báo lại, đừng bịa": 12 of this repository's 22 `free` documents have exactly
one reference layout, which makes them level-2 material until a second phôi is
measured, not level-3 material with a shrug.

Two gates, and both refuse rather than default
-----------------------------------------------

`agent/policy.yaml` says whether the document may be redrawn at all --
`locked` never reaches here. `agent/constraints.yaml` says what it may be
redrawn *into*, and a document with no reviewed entry is refused with the name
of the file to edit. Neither defaults to permissive: the cost of forgetting to
declare a phôi is one missing variant, and the cost of defaulting is a
generated giấy tờ nhà nước.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import json
import math
import random
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import augment_layout, constraints as constraints_mod
from agent import layout_schema as schema_mod
from agent import policy as policy_module
from agent.client import LLMError
from agent.ollama import prompt
from rulebase.layout import DEFAULT_SECTIONS, SECTIONS

REPO_ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = REPO_ROOT / "rulebase" / "layouts"
DOCUMENTS = REPO_ROOT / "rulebase" / "documents"
BLANKS = REPO_ROOT / "rulebase" / "blanks.yaml"

# The label vocabulary of axis 1, from the one place that already defines it.
# `Blank-Page` is the whole-page property `agent/prompts/regions.md` names
# separately -- it describes a sheet, not a block on one -- so the 19 the
# converter knows are the 18 a block may claim, plus it.
WHOLE_PAGE = "Blank-Page"

# How many characters a column title may run to. Measured off the committed
# layouts at import time rather than chosen; see `_title_bound`.
TITLE_SLACK = 1.25

# `columns[].width: 0` is a sentinel meaning "take whatever the fixed columns
# leave", and exactly one column carries it. Not a small number: see
# `augment_layout.check_sentinels`, and the ten label values that went missing
# the day a model read it as one.
FLEX = 0


class ComposeError(ValueError):
    """The repository cannot answer a question this module has to ask."""


# --------------------------------------------------------------- IN-6, IN-7


def regions() -> tuple[str, ...]:
    """The 18 block-level labels of axis 1 (IN-7, R-2).

    Read from `pipeline.record.DOCSYNTH_LABELS`, which is what actually labels
    a drawn page, so a composition cannot name a region no record will ever
    carry. Imported lazily: `pipeline.record` pulls in the record schema and
    this module is also used by `--explain`, which needs none of it.
    """
    from pipeline.record import DOCSYNTH_LABELS

    return tuple(sorted(DOCSYNTH_LABELS - {WHOLE_PAGE}))


@dataclass(frozen=True)
class Vocabulary:
    """Every name a composition may use, and where each one came from.

    Nothing here is a list in this file. `sections` is `rulebase.layout.
    SECTIONS`, which is the dispatch table the builder actually walks;
    `options` is derived from the committed layouts by `agent/layout_schema.py`;
    `regions` is the converter's own label set. A vocabulary written down here
    would be a fourth place to keep in step with the other three, and it would
    lose that race -- which is the whole argument of `layout_schema`'s own
    docstring, applied one level up.
    """

    sections: tuple[str, ...]
    regions: tuple[str, ...]
    options: dict[str, dict[str, dict]]     # section -> leaf -> JSON-schema spec
    column_keys: tuple[str, ...]
    aligns: tuple[str, ...]
    title_max: int

    def option_spec(self, section: str, leaf: str) -> dict | None:
        return self.options.get(section, {}).get(leaf)


def _leaf_spec(leaf: schema_mod.Leaf) -> dict | None:
    """One derived `Leaf` as a JSON-schema fragment, or None if it is text.

    Printed Vietnamese text is deliberately not offered as a section option.
    The one place a composition writes words onto the paper is a column title,
    which goes through its own length and charset check; letting it write
    `letterhead.labels.tax_code` as well would be handing it the wording of a
    legally required label with nothing measuring the result.
    """
    if leaf.types == {"bool"}:
        return {"type": "boolean"}
    if leaf.types <= {"int", "float"} and leaf.numbers:
        low, high = leaf.bounds()
        if leaf.types == {"int"}:
            # `bounds()` pads by SLACK and so always returns floats, which is
            # right for `layout_schema.ranges()` -- it compares a value against
            # them. It is NOT right here: `{"type": "integer", "minimum":
            # 1.4285714285714286}` is a schema that contradicts itself, and a
            # constrained-decoding backend building an integer lexeme out of a
            # fractional bound is where a real vLLM host returned HTTP 500 with
            # no message. Measured: the same schema with these six leaves
            # rounded answers 200. Tightening to the enclosed whole numbers
            # changes nothing a decoder could have emitted -- an integer >=
            # 1.43 is an integer >= 2 -- so this is a well-formedness repair,
            # not a narrowing of what the model may say.
            low_i, high_i = math.ceil(low), math.floor(high)
            if low_i > high_i:
                # A spread too narrow to contain a whole number. The observed
                # values are integers by construction, so they are the widest
                # bound that is certainly satisfiable.
                low_i, high_i = int(min(leaf.numbers)), int(max(leaf.numbers))
            return {"type": "integer", "minimum": low_i, "maximum": high_i}
        return {"type": "number", "minimum": low, "maximum": high}
    if leaf.enum:
        # `layout_schema.TEXT_LEAVES` names the leaves that carry words onto
        # the paper rather than dispatch the builder, and it matches the last
        # path segment exactly -- so `parties.left_label` slips through it and
        # is derived as an enum, because only one layout sets it and one value
        # looks like a closed set. Harmless where that schema is used (a
        # variant copying its parent's label is fine); not harmless here, where
        # it would hand a composition the wording of "BÊN MUA HÀNG". Matched on
        # the suffix instead, and only for this module.
        tail = leaf.key.split("[]")[-1].lstrip(".").split(".")[-1]
        if any(tail == word or tail.endswith(f"_{word}")
               for word in schema_mod.TEXT_LEAVES):
            return None
        return {"type": "string", "enum": sorted(leaf.values)}
    return None


def _merge(one: dict | None, two: dict | None) -> dict | None:
    """Two specs for the same leaf name under different sections.

    `parties.split` and `notes.split` are both `split`, and the flat union the
    guided-decoding schema needs cannot tell them apart. Widening to cover both
    is safe because `check()` re-validates every option against **its own
    section's** leaf afterwards: the schema stops a nonsense type up front, and
    the check stops a value that is legal for the wrong block.
    """
    if one is None or two is None:
        return one or two
    if one.get("type") != two.get("type"):
        return None
    merged = dict(one)
    if "minimum" in one and "minimum" in two:
        merged["minimum"] = min(one["minimum"], two["minimum"])
        merged["maximum"] = max(one["maximum"], two["maximum"])
    if "enum" in one and "enum" in two:
        merged["enum"] = sorted(set(one["enum"]) | set(two["enum"]))
    return merged


def _title_bound(schema: dict[str, schema_mod.Leaf]) -> int:
    """How long a column title may be, measured off the ones that exist."""
    leaf = schema.get("columns[].title")
    seen = max((len(value) for value in leaf.values), default=24) if leaf else 24
    return int(seen * TITLE_SLACK)


def vocabulary(schema: dict[str, schema_mod.Leaf] | None = None) -> Vocabulary:
    schema = schema if schema is not None else schema_mod.derive()

    options: dict[str, dict[str, dict]] = {}
    for path, leaf in schema.items():
        head, _, rest = path.partition(".")
        if head not in SECTIONS or not rest:
            continue
        # A two-number range is written `<section>.<leaf>[]` by `walk`; keep it
        # as a range rather than as a scalar, because that is what the builder
        # writes and what `rulebase` feeds to `randrange`.
        name, ranged = (rest[:-2], True) if rest.endswith("[]") else (rest, False)
        if "." in name or "[]" in name:
            continue                    # nested, e.g. letterhead.labels.address
        spec = _leaf_spec(leaf)
        if spec is None:
            continue
        if ranged:
            spec = {"type": "array", "items": spec, "minItems": 2, "maxItems": 2}
        options.setdefault(head, {})[name] = spec

    keys = schema.get("columns[].key")
    aligns = schema.get("columns[].align")
    return Vocabulary(
        sections=tuple(sorted(SECTIONS)),
        regions=regions(),
        options=options,
        column_keys=tuple(sorted(keys.values)) if keys else (),
        aligns=tuple(sorted(aligns.values)) if aligns else ("left", "center", "right"),
        title_max=_title_bound(schema),
    )


# ----------------------------------------------------------------- IN-2, §8.1


@dataclass(frozen=True)
class Reference:
    """One phôi, as evidence rather than as a thing to edit."""

    id: str
    spec: dict

    @property
    def sections(self) -> tuple[str, ...]:
        """The blocks this phôi draws, INCLUDING the ones it does not name.

        `rulebase.layout.build_grid` reads `spec.get("sections") or
        DEFAULT_SECTIONS`, so a layout that declares none still draws six --
        the till-roll order that predates the key. Seven of the committed
        layouts are in that position, and reading their `sections:` literally
        made both phôi of `supermarket` look like they carried no blocks at
        all: layer 1+2 empty, layer 3 empty, and `--explain` reporting that a
        document with two real phôi had nothing in common with itself.
        """
        return tuple(self.spec.get("sections") or DEFAULT_SECTIONS)

    @property
    def column_keys(self) -> tuple[str, ...]:
        return tuple(str(c.get("key")) for c in (self.spec.get("columns") or []))


def references(document: str, blanks: Path | str = BLANKS,
               root: Path | str = LAYOUTS,
               include_generated: bool = False) -> list[Reference]:
    """The *k* reference layouts for `document` (IN-2), in declared order.

    `rulebase/blanks.yaml`'s `documents:` map is the right source and the tag
    system is not: `requires`/`excludes` describe a *relation*, so a layout
    added with generous tags silently joins every document that matches, while
    `documents:` is the list a person meant. That is the same argument
    `blanks.yaml`'s own header makes for existing at all.

    **A generated layout is not evidence.** `agent/layout_schema.py` excludes
    them from its derivation for a stated reason -- "otherwise the first
    variant widens the schema and the second is checked against the first one's
    mistakes" -- and reasoning about layers has the same failure with a longer
    fuse: compose once, register, compose again, and the second page's idea of
    what every print shop does includes a page no print shop made. Only what a
    person measured off paper counts, which is exactly what `MARK` distinguishes.
    """
    raw = yaml.safe_load(Path(blanks).read_text(encoding="utf-8")) or {}
    named = (raw.get("documents") or {}).get(document)
    if not named:
        raise ComposeError(
            f"{document!r} has no `documents:` entry in {Path(blanks).name}, so "
            f"there is no phôi to reason from. Level 3 reads references; it "
            f"does not invent a document kind.")
    found, skipped = [], []
    for layout_id in named:
        path = Path(root) / f"{layout_id}.yaml"
        if not path.exists():
            raise ComposeError(f"{document}: reference {layout_id!r} has no file "
                               f"in {root}")
        if not include_generated and schema_mod.is_generated(path):
            skipped.append(str(layout_id))
            continue
        found.append(Reference(id=str(layout_id),
                               spec=yaml.safe_load(path.read_text(encoding="utf-8")) or {}))
    if not found:
        raise ComposeError(
            f"{document}: every layout it draws is generated ({skipped}); there "
            f"is no measured phôi left to reason from")
    return found


@dataclass(frozen=True)
class Layers:
    """§8.1's three layers, read off the references instead of asserted."""

    always: tuple[str, ...]        # layer 1+2: on every phôi -- keep
    sometimes: tuple[str, ...]     # layer 3: differs between phôi -- free
    key_always: tuple[str, ...]
    key_sometimes: tuple[str, ...]
    orders: tuple[tuple[str, ...], ...]
    families: tuple[str, ...]
    # The rest of layer 3, and most of it in practice: §8.1 lists "khổ giấy,
    # có khung không, tên cột viết tắt hay đủ, có logo không" -- none of which
    # is a block being present or absent. Read the same way, by disagreement
    # between phôi.
    settings_vary: tuple[str, ...]     # `table.compact`, `totals.grand_scale`
    columns_vary: tuple[str, ...]      # `title`, `width`, `align`
    paper_vary: tuple[str, ...]        # `width`, `gutter`, `sheet`, `rule_char`

    @property
    def varies(self) -> dict[str, tuple[str, ...]]:
        """Every dimension the phôi disagree on, for the report and for §8.2."""
        return {
            "khối": self.sometimes,
            "thứ tự khối": ("có",) if len(set(self.orders)) > 1 else (),
            "cột": self.key_sometimes,
            "thuộc tính cột": self.columns_vary,
            "tuỳ chọn khối": self.settings_vary,
            "khổ giấy": self.paper_vary,
        }

    @property
    def free(self) -> bool:
        """Whether a third layer is visible at all (§8.2).

        Deliberately wider than "the phôi carry different blocks", because
        reading it that narrowly gets the answer wrong on the evidence in this
        repository: exactly ONE of 33 eligible documents has phôi that differ
        in which blocks they draw, and `invoice_plain`'s four -- a centred
        logo, a dense table, a minimalist sheet, a multi-page form -- carry the
        same four blocks in the same order and differ in `table.compact`,
        `table.blank_rows`, `totals.grand_scale` and the measure. Four
        different pages a person drew from four different photographs, which is
        exactly what layer 3 is, called empty by an intersection looking at one
        key.
        """
        return any(self.varies.values())


def _vary(refs: list[Reference], read) -> tuple[str, ...]:
    """Names on which the phôi disagree, per `read(ref) -> {name: value}`.

    A name only SOME phôi set counts as disagreement: `table.blank_rows` on one
    sheet of four is the choice that sheet made, and treating "absent" as
    "agrees" would erase it.
    """
    # Two passes, and the second one is the point. A single pass that unions
    # names as it goes never records "absent" for the phôi it already walked,
    # so a key first declared by the LAST reference looks unanimous: one value,
    # seen once. `table.blank_rows` -- set by exactly one of `invoice_plain`'s
    # four sheets, and precisely the choice that sheet made -- vanished that
    # way.
    read_all = [read(ref) for ref in refs]
    names = set().union(*read_all) if read_all else set()
    varies = []
    for name in names:
        values = {json.dumps(got.get(name), sort_keys=True, ensure_ascii=False)
                  for got in read_all}
        if len(values) > 1:
            varies.append(name)
    return tuple(sorted(varies))


def layers(refs: list[Reference]) -> Layers:
    if not refs:
        raise ComposeError("no references to read layers from")
    section_sets = [set(r.sections) for r in refs]
    key_sets = [set(r.column_keys) for r in refs]
    every_section = set.intersection(*section_sets)
    any_section = set.union(*section_sets)
    every_key = set.intersection(*key_sets) if key_sets else set()
    any_key = set.union(*key_sets) if key_sets else set()

    def settings(ref: Reference) -> dict:
        out = {}
        for name in SECTIONS:
            block = ref.spec.get(name)
            if isinstance(block, dict):
                out.update({f"{name}.{leaf}": value for leaf, value in block.items()})
        return out

    def columns(ref: Reference) -> dict:
        out = {}
        for column in ref.spec.get("columns") or []:
            key = str(column.get("key"))
            out.update({f"{key}.{leaf}": value for leaf, value in column.items()
                        if leaf != "key"})
        return out

    def paper(ref: Reference) -> dict:
        return {name: ref.spec.get(name)
                for name in ("sheet", "width", "gutter", "rule_char", "rules", "font")}

    return Layers(
        always=tuple(sorted(every_section)),
        sometimes=tuple(sorted(any_section - every_section)),
        key_always=tuple(sorted(every_key)),
        key_sometimes=tuple(sorted(any_key - every_key)),
        orders=tuple(r.sections for r in refs),
        families=tuple(sorted({str(r.spec.get("family", "")) for r in refs if
                               r.spec.get("family")})),
        settings_vary=_vary(refs, settings),
        columns_vary=_vary(refs, columns),
        paper_vary=_vary(refs, paper),
    )


# ----------------------------------------------------------------------- IN-3


def field_spec(document: str, root: Path | str = DOCUMENTS) -> dict:
    """What the document's fields are (IN-3), from `rulebase/documents/`.

    This repository has no `schema/<document>.yaml`; it has this, which is the
    same thing under the name it already had -- what `rulebase.content.build`
    reads to decide what a page of this kind says.
    """
    path = Path(root) / f"{document}.yaml"
    if not path.exists():
        raise ComposeError(f"no field spec at {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def required_sections(document: str, refs: list[Reference], limits=None,
                      root: Path | str = DOCUMENTS) -> tuple[str, ...]:
    """Blocks a page of this kind must carry (R-4, I-3).

    Three sources, unioned, and none of them is a list in this file:

    * every block on **every** reference (layers 1+2 of §8.1) -- a block all
      *k* print shops kept is not one the k+1st drops;
    * blocks the document's own field spec implies. `signature_labels:` means
      the paper is signed, `words_label:` means the amount is written out in
      words, `party_fields:` means there are named parties. Each of those keys
      exists because `rulebase.content.build` fills something for it, so a
      layout with no block to print it produces a label describing a value the
      page does not carry -- which is exactly what `pipeline/invariants.py`
      fails a shard over;
    * `constraints.yaml`'s own `sections.required`, which is where a reviewer
      corrects the first bullet. **The intersection counts blocks, not
      fields**, and those are not the same question: `invoice_header_table`
      drops `strip` and still prints the invoice date, because its
      `header.align: corner` draws those two fields into the corner box
      instead. The intersection therefore calls `strip` optional, and the
      first composed layout that took it at its word left
      `invoice.strip.Ngày` in the label and off the paper on all ten seeds.
      That is a fact about how two blocks interact, not about the phôi, so it
      is written down by the person who knows it rather than inferred.
    """
    spec = field_spec(document, root)
    implied = {
        "signature_labels": "signatures",
        "words_label": "words",
        "party_fields": "parties",
        "summary_labels": "vat_summary",
    }
    wanted = {section for key, section in implied.items() if spec.get(key)}
    if limits is not None:
        wanted |= set(limits.required)
    return tuple(sorted(set(layers(refs).always) | wanted))


# ------------------------------------------------------------------ the thing


@dataclass
class Composition:
    """One composed layout, as structure. The artifact, before any YAML."""

    document: str
    seed: int
    paper: dict[str, Any] = field(default_factory=dict)
    reasoning: dict[str, Any] = field(default_factory=dict)
    blocks: list[dict[str, Any]] = field(default_factory=list)
    # Settings live BESIDE the blocks, keyed by block name, rather than inside
    # each block. That is not a style choice; it is what makes cửa ải 1 real.
    #
    # Inside the block they have to be one flat union of every section's keys,
    # because the block list is one JSON array and a decoder needs one item
    # schema for it -- so the schema PERMITS `header.name_gap` (which exists,
    # on `signatures`) and `table.indent` (which exists, on `totals`), and a
    # model asked to fill an object fills what it is offered. Measured on the
    # first real run against a local server: 9 of 13 refusals in round 1, 12 of
    # 14 in round 2, 7 of 11 in round 3 were exactly that -- the schema
    # inviting a key and `check_structure` refusing it a moment later.
    #
    # Keyed by section, each block's settings are their own object with their
    # own `additionalProperties: false`, so `header.name_gap` is unspellable
    # rather than merely rejected. It also happens to be the shape of the file
    # being built: `sections: [...]` at the top and `header: {...}` beside it
    # is exactly how a layout YAML is written.
    settings: dict[str, dict[str, Any]] = field(default_factory=dict)
    unmet: list[dict[str, str]] = field(default_factory=list)
    by: str = "coverage"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def options_for(self, section: str) -> dict[str, Any]:
        return dict(self.settings.get(section) or {})

    @property
    def sections(self) -> list[str]:
        return [str(b.get("section", "")) for b in self.blocks]

    def table_block(self) -> dict | None:
        return next((b for b in self.blocks if b.get("columns")), None)


REASONING_KEYS = ("printer", "reader", "first", "required", "density")

# How many characters of answer counts as an answer. §3.2's whole point is that
# a `reasoning` filled with platitudes is visible to a reviewer -- this cannot
# measure platitude, and does not pretend to. It measures empty, which is the
# one failure a schema can catch, and A-5 (a person, 50 pages a round) is what
# catches the rest.
REASONING_MIN = 12


def schema_for(document: str, limits, layers_: Layers, vocab: Vocabulary,
               available: list[str], refs: list[Reference]) -> dict:
    """The guided-decoding schema -- cửa ải 1 (§9).

    An enum here is worth more than a paragraph of prompt: the section names,
    the region names, the column keys and the paper are all closed sets, and
    constrained decoding makes "the model invented a name" impossible rather
    than unlikely. That is the same argument `agent/client.py`'s docstring
    makes about attribute ids, one level up -- and it is what makes A-6 (zero
    invented layout names) measurable instead of hopeful.
    """
    # One settings object per block, each closed over its OWN keys. See the
    # note on `Composition.settings` for what the union version cost.
    settings = {
        "type": "object",
        "properties": {
            section: {"type": "object",
                      "properties": _settable(section, vocab, limits),
                      "additionalProperties": False}
            for section in available if _settable(section, vocab, limits)
        },
        "additionalProperties": False,
    }

    keys = sorted(set(layers_.key_always) | set(layers_.key_sometimes)) \
        or list(vocab.column_keys)
    column = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "enum": keys},
            "title": {"type": "string", "minLength": 1,
                      "maxLength": vocab.title_max},
            # Measured off the phôi, not halved off the sheet. Half the
            # measure is 48 characters for an A4 invoice, and the widest fixed
            # column any of the six sheets rules is 15 -- so the loose bound
            # let a model spend the whole budget on one column and hand the
            # item name nothing. `SLACK` is `layout_schema`'s own 1.4, the
            # same allowance every derived numeric bound already carries.
            "width": {"type": "integer", "minimum": 0,
                      "maximum": _column_ceiling(refs, limits)},
            "align": {"type": "string", "enum": list(vocab.aligns)},
        },
        "required": ["key", "title", "width", "align"],
        "additionalProperties": False,
    }

    block = {
        "type": "object",
        "properties": {
            "section": {"type": "string", "enum": sorted(available)},
            "region": {"type": "string", "enum": list(vocab.regions)},
            # `maxItems` is the number of DISTINCT keys, not the constraint's
            # ceiling: a schema cannot say "unique by `key`" (`uniqueItems`
            # compares whole objects, and two columns differing only in title
            # are two different objects), so the closest it gets is refusing to
            # ask for more columns than there are keys to fill them. The real
            # check is `check_numbers`; this stops the easy half of it.
            "columns": {"type": "array", "items": column,
                        "minItems": limits.columns[0],
                        "maxItems": min(limits.columns[1], len(keys))},
        },
        "required": ["section", "region"],
        "additionalProperties": False,
    }

    reasoning = {
        "type": "object",
        "properties": {
            "printer": {"type": "string", "minLength": REASONING_MIN},
            "reader": {"type": "string", "minLength": REASONING_MIN},
            "first": {"type": "string", "minLength": 1},
            "required": {"type": "array", "items": {"type": "string"}, "minItems": 1},
            "density": {"type": "string", "minLength": REASONING_MIN},
        },
        "required": list(REASONING_KEYS),
        "additionalProperties": False,
    }

    return {
        "type": "object",
        "properties": {
            "paper": {
                "type": "object",
                "properties": {
                    "sheet": {"type": "string", "enum": list(limits.papers)},
                    "width": {"type": "array", "minItems": 2, "maxItems": 2,
                              "items": {"type": "integer",
                                        "minimum": limits.width[0],
                                        "maximum": limits.width[1]}},
                    "gutter": {"type": "integer", "minimum": limits.gutter[0],
                               "maximum": limits.gutter[1]},
                },
                "required": ["sheet", "width", "gutter"],
                "additionalProperties": False,
            },
            # `reasoning` before `blocks` on purpose: a decoder emits properties
            # in the order the schema lists them, so the five answers of §7 are
            # generated BEFORE the page they are supposed to have decided. The
            # other order would make them a caption written after the fact.
            "reasoning": reasoning,
            "blocks": {"type": "array", "items": block,
                       "minItems": limits.sections_min,
                       "maxItems": limits.sections_max},
            "settings": settings,
            "unmet": {"type": "array", "items": {
                "type": "object",
                "properties": {"want": {"type": "string", "minLength": 1},
                               "why": {"type": "string", "minLength": 1}},
                "required": ["want", "why"], "additionalProperties": False}},
        },
        "required": ["paper", "reasoning", "blocks", "settings"],
        "additionalProperties": False,
    }


def _settable(section: str, vocab: Vocabulary, limits) -> dict[str, dict]:
    """A block's settings MINUS the value that stands in for another block.

    A coupled setting is not an independent choice. Across all 52 committed
    layouts `header.align: corner` holds exactly when `strip` is absent and
    `table.component: true` exactly when `totals` is -- one decision, and the
    block list already states it. Offering it twice asks a model to say the
    same thing in two places and then refuses it for disagreeing, which is
    what a real server did three rounds running, each time wanting a corner
    masthead AND a date strip.

    So the coupling value is struck from the enum and `to_layout` derives it
    from the block list, the same way `item.rows` is derived from the columns
    rather than restated. The leaf itself survives where it has other values:
    `header.align: split` is still a choice, because it is one.
    """
    options = dict(vocab.options.get(section, {}))
    for couple in limits.couples:
        if couple.section != section or couple.leaf not in options:
            continue
        spec = dict(options[couple.leaf])
        if spec.get("type") == "boolean":
            # The only value left is the one that means "not coupled", which
            # is also the builder's default. Offering a one-value boolean is a
            # question with one answer -- struck, not narrowed.
            options.pop(couple.leaf)
            continue
        values = [value for value in spec.get("enum", []) if value != couple.value]
        if values:
            options[couple.leaf] = {**spec, "enum": values}
        else:
            options.pop(couple.leaf)
    return options


def _column_ceiling(refs: list[Reference], limits) -> int:
    """How wide one fixed column may be, from the widest any phôi rules.

    A ceiling derived from the sheet (`width // 2`) is not a ceiling: it says
    48 for an A4 invoice whose six phôi never rule a column past 15, and a
    model that takes it at its word spends the whole measure on two columns and
    leaves the flexible one at zero. Twice, on the first real run.
    """
    seen = [int(column.get("width") or 0)
            for ref in refs for column in (ref.spec.get("columns") or [])
            if column.get("width")]
    if not seen:
        # No phôi rules a fixed column, so there is nothing measured to bound
        # this with and half the measure is the only honest answer. `refs` is
        # a required argument rather than one defaulting to `[]` precisely so
        # that this branch means "the phôi are silent" and never "the caller
        # forgot" -- the loose bound is what the model overspent against.
        return max(limits.width[1] // 2, 1)
    return max(int(max(seen) * schema_mod.SLACK), 1)


def user_message(document: str, limits, refs: list[Reference], layers_: Layers,
                 vocab: Vocabulary, available: list[str], seed: int,
                 required: tuple[str, ...] = ()) -> str:
    """What the model is told about THIS document. Facts, not instructions.

    The five questions, the three layers and the hard rules are in
    `prompts/compose.md`, which is the system turn and does not change per
    call. What changes is here, and every line of it is read off the
    repository: the phôi and what they agree on, the fields the content builder
    will fill, and the numbers a person put in `constraints.yaml`.
    """
    spec = field_spec(document)
    lines = [
        f"# Chứng từ: {document}",
        f"Hạt giống: {seed}. Cùng hạt giống + cùng đầu vào phải ra cùng đầu ra.",
        "",
        f"Tiêu đề in trên trang: {spec.get('titles') or spec.get('title') or '—'}",
        f"Hồ sơ nội dung (`profile`): {spec.get('profile', '—')}",
        "",
        "## Ràng buộc (constraints.yaml — người duyệt: "
        f"{limits.reviewer})",
        f"* Khổ giấy được phép: {', '.join(repr(p) for p in limits.papers)}",
        f"* Bề ngang: {limits.width[0]}..{limits.width[1]} ký tự · "
        f"gutter {limits.gutter[0]}..{limits.gutter[1]}",
        f"* Bảng hàng: {limits.columns[0]}..{limits.columns[1]} cột · "
        f"cột co giãn phải còn ít nhất {limits.flex_min} ký tự",
        f"* Số khối: {limits.sections_min}..{limits.sections_max}",
    ]
    if limits.forbidden:
        lines.append(f"* Khối KHÔNG được dùng: {', '.join(sorted(limits.forbidden))}")
    if limits.note:
        lines.append(f"* Ghi chú của người duyệt: {limits.note}")

    lines += ["", f"## {len(refs)} tờ mẫu, và ba lớp của chúng", ""]
    for ref in refs:
        lines.append(f"* `{ref.id}` — khối: {', '.join(ref.sections)}")
    lines += [
        "",
        f"**Lớp 1+2 (có trên MỌI tờ — giữ nguyên):** {', '.join(layers_.always) or '—'}",
        f"**Khối BẮT BUỘC, phải có đủ:** {', '.join(sorted(required)) or '—'}"
        + (f" (rộng hơn lớp 1+2 vì người duyệt đã thêm "
           f"{', '.join(sorted(set(required) - set(layers_.always)))} — khối "
           f"ấy in trường mà bỏ đi là nhãn không có mực)"
           if set(required) - set(layers_.always) else ""),
        f"**Lớp 3 (chỉ có trên vài tờ — tự do):** "
        f"{', '.join(n for n in layers_.sometimes if n not in required) or '—'}",
        f"**Cột có trên mọi tờ:** {', '.join(layers_.key_always) or '—'}",
        f"**Cột chỉ vài tờ có:** {', '.join(layers_.key_sometimes) or '—'}",
        "",
        "## Từ vựng đóng — dùng sai một tên là cả bố cục bị từ chối",
        "",
        f"Khối (`section`): {', '.join(sorted(available))}",
        f"Vùng nhãn (`region`, 18 lớp trục 1): {', '.join(vocab.regions)}",
        "",
        "Tuỳ chọn của từng khối — để trong `settings` dưới đúng tên khối. Mỗi "
        "khối chỉ nhận những khoá dưới đây:",
    ]
    for section in sorted(available):
        names = vocab.options.get(section)
        if names:
            lines.append(f"* `{section}`: {', '.join(sorted(names))}")
    keys = sorted(set(layers_.key_always) | set(layers_.key_sometimes))
    ceiling = _column_ceiling(refs, limits)
    lines += [
        "",
        "## Ngân sách bề ngang — chỗ dễ hỏng nhất, tính trước khi viết cột",
        "",
        f"Cột được dùng ({len(keys)} khoá, mỗi khoá TỐI ĐA MỘT cột): "
        f"{', '.join(keys)}",
        "",
        "Đúng MỘT cột mang `width: 0` — cột tên hàng, lấy phần còn lại. Không "
        "phải không cột nào, không phải hai. Mọi cột khác là số ký tự thật, và "
        f"không cột nào quá {ceiling} ký tự.",
        "",
        "**Phép tính phải đúng, không phải gần đúng:**",
        "",
        "```",
        "  tổng cột cố định + gutter×(số cột − 1)  ≤  paper.width[0] − "
        f"{limits.flex_min}",
        "```",
    ]
    for ref in refs[:3]:
        columns = ref.spec.get("columns") or []
        fixed = [int(c.get("width") or 0) for c in columns if c.get("width")]
        gutter = int(ref.spec.get("gutter") or 0)
        low = int((ref.spec.get("width") or [0, 0])[0])
        if fixed and low:
            lines.append(
                f"  `{ref.id}`: {sum(fixed)} + {gutter}×{len(columns) - 1} = "
                f"{sum(fixed) + gutter * (len(columns) - 1)} ≤ {low} − "
                f"{limits.flex_min} = {low - limits.flex_min} ✓ "
                f"(cột tên còn {low - sum(fixed) - gutter * (len(columns) - 1)})")
    lines += [
        "",
        f"Sáu phôi đều chừa cho cột tên khoảng 20 ký tự. Dưới {limits.flex_min} "
        "là tên hàng bị cắt cụt mà nhãn vẫn khai đủ — cả bố cục bị từ chối.",
        "",
        "Mọi cặp hai số là `[nhỏ, lớn]` — `paper.width`, mọi `*scale`. Viết "
        "ngược là mọi hạt giống đều lỗi.",
    ]
    if limits.couples:
        lines += ["", "## Khối có khối khác làm thay được — chọn MỘT, không "
                      "được cả hai, không được không cái nào", ""]
        for couple in limits.couples:
            lines.append(
                f"* **`{couple.replaces}`** HOẶC **`{couple.option}: "
                f"{json.dumps(couple.value, ensure_ascii=False)}`** — "
                f"{couple.why}")
        lines.append("")
        lines.append("Có cả hai là in cùng một trường hai lần; không có cái nào "
                     "là nhãn hứa một giá trị không có trên giấy.")
    lines += [
        "",
        "Trả JSON: `paper`, `reasoning` (5 khoá), `blocks`, `settings`, và "
        "`unmet` nếu bạn cần một cách bày mà từ vựng trên chưa có.",
    ]
    return "\n".join(lines)


# ------------------------------------------------------------- cửa ải 2, 3, 5


def _strings(node: Any):
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from _strings(value)
    elif isinstance(node, list):
        for value in node:
            yield from _strings(value)
    elif isinstance(node, str):
        yield node


def check_contract(comp: Composition) -> list[str]:
    """R-7: no markup reaches the builder, and no CSS that breaks the box.

    `<` is refused outright rather than sanitised. A composition carrying one
    is a composition that misunderstood its job, and quietly stripping the
    character would hide that from the person reading the diff -- which is the
    only place the misunderstanding shows.

    `text-transform` and a `content:` carrying words are the two CSS rules
    `generators/html/sheets/variant.py::forbidden` already refuses at the other
    end of the pipe, for the reason `agent/README.md` §2 gives: the DOM keeps
    the original string while the pixels show another, so the label describes
    something the paper does not print. Named here too because a string that
    reaches the builder has not met `variant.py` yet.
    """
    problems = []
    for text in _strings(comp.to_dict()):
        if "<" in text:
            problems.append(f"a string contains '<': {text[:60]!r}. The builder "
                            f"writes the markup; a composition is structure.")
        low = text.lower()
        if "text-transform" in low:
            problems.append(f"{text[:60]!r} names text-transform: the DOM would "
                            f"keep one string and the paper show another")
        if re.search(r"content\s*:\s*['\"]\s*\S", low):
            problems.append(f"{text[:60]!r} puts words in a CSS `content:`; a "
                            f"generated glyph has no box to describe it")
    return problems


def check_numbers(comp: Composition, limits, vocab: Vocabulary) -> list[str]:
    """Cửa ải 2 — the arithmetic a schema cannot express.

    The flexible column is the whole of it. `columns[].width: 0` means "take
    what the fixed columns leave", so the name's width is never written down
    anywhere: it is `roll − Σ fixed − gutters`, and **widening any other column
    narrows it**. A composition can sit inside every declared bound and still
    leave the item name six characters wide, at which point `till` and `modern`
    both truncate a name that carries its own weight and unit price and the
    label goes on promising them. That is `augment_layout._slack`'s lesson, and
    it is stated here as a bound rather than as a comparison against a parent,
    because level 3 has no parent to compare against.
    """
    problems: list[str] = []
    paper = comp.paper or {}

    problem = limits.paper_ok(str(paper.get("sheet", "")))
    if problem:
        problems.append(problem)

    width = paper.get("width")
    if not (isinstance(width, list) and len(width) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in width)):
        return problems + [f"paper.width is {width!r}, not a [min, max] pair of "
                           f"whole characters"]
    if width[0] > width[1]:
        problems.append(f"paper.width [{width[0]}, {width[1]}] has its ends "
                        f"swapped; `rulebase` feeds it straight to randrange "
                        f"and every seed raises")
    for edge in width:
        problem = limits.band_ok("paper.width", edge, limits.width)
        if problem:
            problems.append(problem)
    gutter = paper.get("gutter")
    problem = limits.band_ok("paper.gutter", gutter, limits.gutter)
    if problem:
        problems.append(problem)

    table = comp.table_block()
    if table is None:
        return problems
    columns = table.get("columns") or []
    if not limits.columns[0] <= len(columns) <= limits.columns[1]:
        problems.append(f"{len(columns)} columns, and this document allows "
                        f"{limits.columns[0]}..{limits.columns[1]}")
    flexible = [c for c in columns if c.get("width") == FLEX]
    if len(flexible) != 1:
        problems.append(
            f"{len(flexible)} columns carry `width: 0`, and exactly one must. "
            f"It is a sentinel meaning 'take the rest of the sheet', not a "
            f"width of zero -- with none, every column is fixed and the sheet "
            f"has a gap; with two, neither knows what it gets.")
    seen: set[str] = set()
    for column in columns:
        key = str(column.get("key", ""))
        if key in seen:
            problems.append(f"column {key!r} appears twice; each key wires one "
                            f"value onto the page")
        seen.add(key)
        title = str(column.get("title", ""))
        if not title.strip():
            problems.append(f"column {key!r} has no title, so its heading is "
                            f"blank ink with a label behind it")
        elif len(title) > vocab.title_max:
            problems.append(f"column {key!r} title is {len(title)} characters; "
                            f"the longest on any committed layout is "
                            f"{vocab.title_max}")
        elif not any(ch.isalpha() for ch in title):
            problems.append(f"column {key!r} title {title!r} has no letter in it")

    if isinstance(gutter, int) and not isinstance(gutter, bool) and len(width) == 2:
        fixed = sum(int(c.get("width") or 0) for c in columns)
        gutters = gutter * max(len(columns) - 1, 0)
        left = width[0] - fixed - gutters
        if left < limits.flex_min:
            problems.append(
                f"the flexible column gets {left} characters at the narrow end "
                f"({width[0]} − {fixed} fixed − {gutters} gutter), and this "
                f"document needs at least {limits.flex_min}. The item name "
                f"carries its own weight and price-per-unit inside it; below "
                f"that they are trimmed off the page and left in the label.")
    return problems


def check_structure(comp: Composition, limits, layers_: Layers, vocab: Vocabulary,
                    required: tuple[str, ...], available: list[str]) -> list[str]:
    """R-2, R-3, R-4, R-5 and the forbidden list, in one pass."""
    problems: list[str] = []

    for key in REASONING_KEYS:                                        # R-5
        value = (comp.reasoning or {}).get(key)
        if isinstance(value, list):
            if not [v for v in value if str(v).strip()]:
                problems.append(f"reasoning.{key} is empty")
            continue
        if not str(value or "").strip():
            problems.append(f"reasoning.{key} is empty; §7 asks five questions "
                            f"and this is the answer to one of them")
    stray = sorted(set(comp.reasoning or {}) - set(REASONING_KEYS))
    if stray:
        problems.append(f"reasoning has extra keys {stray}; it is exactly the "
                        f"five answers, not a place for notes")

    if not limits.sections_min <= len(comp.blocks) <= limits.sections_max:
        problems.append(f"{len(comp.blocks)} blocks, and this document allows "
                        f"{limits.sections_min}..{limits.sections_max}")

    seen: list[str] = []
    for index, block in enumerate(comp.blocks):
        section = str(block.get("section", ""))
        region = str(block.get("region", ""))
        if section not in available:                                  # R-3
            problems.append(
                f"blocks[{index}]: {section!r} is not a block this repository "
                f"draws for {comp.document}; have {', '.join(sorted(available))}"
                + (". Need a way of laying out that the vocabulary has no name "
                   "for? Say so in `unmet` -- do not name it yourself."
                   if section else ""))
        elif section in limits.forbidden:
            problems.append(f"blocks[{index}]: {section!r} is forbidden for "
                            f"{comp.document} by constraints.yaml")
        if region not in vocab.regions:                               # R-2
            problems.append(f"blocks[{index}]: region {region!r} is not one of "
                            f"the 18 axis-1 classes")
        if section in seen:
            problems.append(f"blocks[{index}]: {section!r} twice; the builder "
                            f"emits a section once")
        seen.append(section)

        for name, value in comp.options_for(section).items():         # R-3
            spec = vocab.option_spec(section, name)
            if spec is None:
                problems.append(
                    f"blocks[{index}] ({section}): no committed layout has "
                    f"`{section}.{name}`. A key the builder does not read is "
                    f"silently ignored, and the page comes out unchanged while "
                    f"the report claims a new layout.")
                continue
            problems += _option_problems(f"blocks[{index}] ({section}).{name}",
                                         value, spec)

    # R-4, with the couples of §5.1 applied: a required block may be absent
    # exactly when the setting declared to stand in for it is switched on, and
    # may not be present at the same time as it -- see `constraints.Couple`.
    by_section = {str(b.get("section", "")): comp.options_for(str(b.get("section", "")))
                  for b in comp.blocks}
    missing = []
    for name in required:
        couple = limits.couple_for(name)
        if couple is None:
            if name not in seen:
                missing.append(name)
            continue
        # A coupled block is OPTIONAL, and that is the whole of it: `to_layout`
        # writes the stand-in when the block is absent and withholds it when
        # the block is there, so both halves of the page are consistent by
        # construction. What is still worth refusing is a composition that
        # states the stand-in itself -- the schema no longer lets a model do
        # that (see `_settable`), and a hand-written composition still can.
        if name in seen and couple.active_in(by_section):
            problems.append(
                f"both {name!r} and `{couple.option}: {couple.value!r}` are on "
                f"this page, and one does the other's job -- {couple.why} So "
                f"the same field is printed twice, once with a label behind it "
                f"and once without. Drop one; the block list alone decides "
                f"this, and the builder writes the setting.")
    if missing:
        problems.append(
            f"missing blocks {missing}, which every phôi of {comp.document} "
            f"carries or whose field spec fills them. A block dropped here is "
            f"a label describing a value the page does not print, which is what "
            f"`pipeline/invariants.py` fails a shard over.")

    stray = sorted(set(comp.settings) - set(seen))
    if stray:
        problems.append(
            f"settings name block(s) {stray} that are not in `blocks`. The "
            f"builder runs a block because `sections:` lists it, so a settings "
            f"map with no block is a set of values nothing reads -- and a "
            f"block whose settings were meant to be there draws with defaults.")

    keys_present = {str(c.get("key")) for b in comp.blocks
                    for c in (b.get("columns") or [])}
    dropped = [key for key in layers_.key_always if key not in keys_present]
    if comp.table_block() is not None and dropped:
        problems.append(f"the table drops column(s) {dropped}, which all "
                        f"{len(layers_.orders)} phôi carry")
    return problems


def _option_problems(where: str, value: Any, spec: dict) -> list[str]:
    kind = spec.get("type")
    if kind == "boolean":
        return [] if isinstance(value, bool) else [f"{where}: {value!r} is not true/false"]
    if kind in ("number", "integer"):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return [f"{where}: {value!r} is not a number"]
        if not spec["minimum"] <= value <= spec["maximum"]:
            return [f"{where}: {value}, outside the "
                    f"{spec['minimum']:g}..{spec['maximum']:g} the layouts use"]
        return []
    if kind == "string":
        if value not in spec.get("enum", []):
            return [f"{where}: {value!r} is not one of "
                    f"{'|'.join(spec.get('enum', []))}"]
        return []
    if kind == "array":
        if not (isinstance(value, list) and len(value) == 2):
            return [f"{where}: {value!r} is not a [min, max] pair"]
        problems = []
        for item in value:
            problems += _option_problems(where, item, spec["items"])
        numbers = [v for v in value if isinstance(v, (int, float))
                   and not isinstance(v, bool)]
        if len(numbers) == 2 and numbers[0] > numbers[1]:
            problems.append(f"{where}: [{numbers[0]:g}, {numbers[1]:g}] is a "
                            f"range with its ends swapped")
        return problems
    return []


def check(comp: Composition, limits, layers_: Layers, vocab: Vocabulary,
          required: tuple[str, ...], available: list[str]) -> list[str]:
    """Every problem with a composition, before anything is written."""
    return (check_contract(comp)
            + check_structure(comp, limits, layers_, vocab, required, available)
            + check_numbers(comp, limits, vocab))


# ---------------------------------------------------------------- the builder


def to_layout(comp: Composition, layout_id: str, limits, refs: list[Reference],
              vocab: Vocabulary) -> dict:
    """Structure -> the `rulebase/layouts/*.yaml` a person would have written.

    Code, not the model, and that is R-7. Three things this writes and the
    model never touches:

    * **`item.rows`** -- the item template, one cell per chosen column. It is
      the wiring into the data (I-1), derived from the columns rather than
      restated, so a composition physically cannot promise a `from:` its own
      table has no column for.
    * **`source:`** -- provenance. Every hand-written layout uses that field
      for the photograph it was measured against, and a composed layout was
      measured against nothing. `augment_layout.restate_source` learned this
      the day a model wrote `PHIẾU TÍNH TIỀN 2023` -- a receipt that does not
      exist, in the one field whose whole job is to be checkable.
    * **`family:`** and `rules:` -- inherited from the references, because the
      CSS module that dresses this document is not a thing a composition gets
      an opinion about.
    """
    primary = refs[0].spec
    family = comp.paper.get("family") or (layers(refs).families or ("modern",))[0]
    if family not in limits.families:
        family = limits.families[0]

    # `name` and `source` are written here and not by the model, and both are
    # kept to the punctuation `layout_schema.charset()` measured off the
    # committed layouts -- `#&'()*+,-./:=_|·—` and nothing else. The model's
    # own answer to "who prints this" goes in the file's header comment, which
    # `yaml.safe_load` never sees, so a semicolon in it costs nothing; here it
    # would fail the derived schema, correctly. `source:` in particular is not
    # the model's to write at all: on every hand-written layout it names the
    # photograph the shape was measured against, and this shape was measured
    # against none -- see `augment_layout.restate_source`.
    spec: dict[str, Any] = {
        "id": layout_id,
        "name": f"Soạn mới cho {comp.document} — {len(comp.blocks)} khối, "
                f"{len(refs)} phôi tham khảo",
        "source": (f"soạn mới bằng LLM từ {len(refs)} phôi tham khảo "
                   f"({', '.join(r.id for r in refs)}) — không đo từ ảnh nào"),
        "family": family,
        "width": list(comp.paper.get("width") or list(limits.width)),
        "gutter": int(comp.paper.get("gutter") or limits.gutter[0]),
        "rule_char": str(primary.get("rule_char", "-")),
    }
    sheet = str(comp.paper.get("sheet", "") or "")
    if sheet:
        spec["sheet"] = sheet
    if primary.get("rules"):
        spec["rules"] = primary["rules"]

    spec["sections"] = comp.sections

    table = comp.table_block()
    if table is not None:
        columns = []
        for column in table["columns"]:
            entry = {"key": str(column["key"]), "title": str(column["title"]),
                     "width": int(column["width"]), "align": str(column["align"])}
            # `title_align` is not the model's to choose: every committed
            # layout aligns a heading with its column, and a heading that
            # disagreed with its own numbers would be a design decision nobody
            # asked for dressed as a variation.
            entry["title_align"] = entry["align"]
            columns.append(entry)
        spec["columns"] = columns
        spec["item"] = {
            "wrap_name": bool(primary.get("item", {}).get("wrap_name", True)),
            "rows": [[{"col": c["key"], "from": c["key"]} for c in columns]],
        }

    for block in comp.blocks:
        section = str(block["section"])
        options = {name: _as_written(vocab.option_spec(section, name), value)
                   for name, value in comp.options_for(section).items()
                   if vocab.option_spec(section, name) is not None}
        for couple in limits.couples:
            if couple.section != section:
                continue
            if couple.replaces in comp.sections:
                # The block is on the page and does its own job; the stand-in
                # must not also fire, whatever the composition says.
                options.pop(couple.leaf, None)
            else:
                options[couple.leaf] = couple.value
        if options:
            spec[section] = options
        elif section in ("signatures", "strip", "words") and section not in spec:
            # `sections:` names it, so the builder runs it; the settings map may
            # legitimately be empty. `signatures: {}` is how the committed
            # layouts spell that, and the key has to be there for `layout_
            # schema.check` to see the same shape it derived.
            spec.setdefault(section, {})
    return spec


def _as_written(spec: dict | None, value: Any) -> Any:
    """`0` where every committed layout writes `0.0`, and back again.

    JSON has one number type; `layout_schema` has the two Python has, and it
    refuses `totals.indent: 0` because all seven layouts that set it write a
    float. That refusal is right for a hand-written file -- an integer there is
    a person meaning something different -- and wrong here, where the model
    chose a VALUE and the type is an artefact of the wire format it had to send
    it over. So the builder writes it in the type the corpus writes it in.

    Only ever between int and float, only when the value survives the round
    trip exactly, and never onto a leaf the corpus writes both ways.
    """
    if not isinstance(spec, dict) or isinstance(value, bool):
        return value
    if spec.get("type") == "number" and isinstance(value, int):
        return float(value)
    if spec.get("type") == "integer" and isinstance(value, float) \
            and value.is_integer():
        return int(value)
    if spec.get("type") == "array" and isinstance(value, list):
        return [_as_written(spec.get("items"), item) for item in value]
    return value


def emit(spec: dict, comp: Composition, model: str, digest: str) -> str:
    """The YAML file, with the header that says who wrote it and from what."""
    header = (f"{schema_mod.MARK} {model}@{digest} compose "
              f"document={comp.document} seed={comp.seed} by={comp.by} "
              f"{_datetime.date.today().isoformat()}\n"
              f"# Mức 3 — soạn mới, không phải biến thể của một phôi. "
              f"Cửa ải nó đã qua: agent/compose_layout.py.\n"
              f"# Vì sao tờ này trông như thế (§7):\n")
    for key in REASONING_KEYS:
        value = comp.reasoning.get(key)
        value = ", ".join(str(v) for v in value) if isinstance(value, list) else value
        header += f"#   {key:9} {' '.join(str(value or '').split())}\n"
    if comp.unmet:
        header += "# Model xin một cách bày mà từ vựng chưa có (R-8):\n"
        for item in comp.unmet:
            header += f"#   - {item.get('want')}: {item.get('why')}\n"
    return header + yaml.safe_dump(spec, allow_unicode=True, sort_keys=False)


# --------------------------------------------------------------- the two modes


def propose(llm, document: str, limits, refs: list[Reference], layers_: Layers,
            vocab: Vocabulary, available: list[str], seed: int,
            required: tuple[str, ...] = ()) -> Composition:
    """Ask the model. Raises `LLMError` rather than degrading silently."""
    system = prompt("compose") + "\n\n" + prompt("regions")
    schema = schema_for(document, limits, layers_, vocab, available, refs)
    answer = llm.decide(system, user_message(document, limits, refs, layers_,
                                             vocab, available, seed, required),
                        schema)
    return Composition(
        document=document, seed=seed,
        paper=answer.get("paper") or {},
        reasoning=answer.get("reasoning") or {},
        blocks=list(answer.get("blocks") or []),
        settings=dict(answer.get("settings") or {}),
        unmet=list(answer.get("unmet") or []),
        by="llm")


def offline(document: str, limits, refs: list[Reference], layers_: Layers,
            vocab: Vocabulary, available: list[str], seed: int,
            required: tuple[str, ...] = ()) -> Composition:
    """The same job with the model's judgement replaced by a seeded draw.

    Not a fallback bolted on. `agent/README.md` §4 makes the argument for the
    planner and it holds here: a run that silently degrades is the bad outcome,
    and a run that records which mode it used is not. This one also gives R-6
    something to be true about -- an LLM is only ever *usually* reproducible
    (see `agent/README.md` §11), while this is byte-identical for a seed, so
    `--seed N` twice is a real determinism test rather than an aspiration.

    What it does NOT do is write a `reasoning` in prose. Every value there is a
    statement of what this function actually did and what it read, because a
    fabricated printer story would be exactly the platitude §3.2 exists to make
    visible -- and a reviewer skimming `by: coverage` pages needs to be able to
    tell them from the model's at a glance.
    """
    rng = random.Random(seed)
    # `required` rather than `layers_.always`: the measured intersection is the
    # floor, and `constraints.yaml` raises it wherever a reviewer found a block
    # the intersection let go (see `required_sections`). Reading the floor here
    # instead would make this function propose exactly what `check_structure`
    # is about to refuse -- which is what it did, on `strip`, every seed.
    must = set(required) | set(layers_.always)
    # Couples are settled BEFORE the blocks, because a couple is a choice
    # between a block and a setting and there is no order in which both
    # decisions can be made independently. Deciding blocks first and settings
    # after is what put `header.align: corner` on a page that also carried
    # `strip`, and `table.component: true` on one that also carried `totals` --
    # the same field printed twice, both times.
    using = {couple.replaces: couple for couple in limits.couples
             if rng.random() < 0.5}
    # The leaf itself is never written here: `to_layout` derives it from the
    # block list, so there is exactly one place that decides it. What this
    # settles is which BLOCKS the page carries.
    skip: dict[str, set[str]] = {}
    for couple in limits.couples:
        skip.setdefault(couple.section, set()).add(couple.leaf)
    must -= set(using)
    keep = [name for name in must if name not in limits.forbidden]
    optional = [name for name in layers_.sometimes
                if name not in limits.forbidden and name not in must
                and name not in using]
    chosen = set(keep) | {name for name in optional if rng.random() < 0.5}

    # Order: the reference orders are the only evidence about what reads well,
    # so one phôi is the spine and anything extra lands where that phôi's
    # neighbours put it. Inventing an order from nothing is how a signature
    # block ends up above the item table -- and, the first time this ran, how
    # the item table came out with "Thành tiền" in column one and "STT" in
    # column four, because the layers are stored sorted for reporting and
    # sorted is not an order any shop prints.
    spine_ref = refs[rng.randrange(len(refs))]
    order = [name for name in spine_ref.sections if name in chosen]
    for name in sorted(chosen - set(order)):
        elsewhere = next((list(o) for o in layers_.orders if name in o), None)
        at = elsewhere.index(name) / max(len(elsewhere) - 1, 1) if elsewhere else 1.0
        order.insert(min(int(round(at * len(order))), len(order)), name)
    order = order[:limits.sections_max]
    while len(order) < limits.sections_min and optional:
        spare = next((n for n in optional if n not in order), None)
        if spare is None:
            break
        order.append(spare)

    from pipeline.record import DOCSYNTH_LABEL_FOR_KIND

    # Same argument, one level down: which columns is a set question, what
    # order they sit in is not. The spine phôi's own left-to-right order is the
    # answer, with any column it does not carry appended -- a shop that adds a
    # VAT-rate column puts it beside the money, not in front of the line number.
    wanted = set(layers_.key_always) | {k for k in layers_.key_sometimes
                                        if rng.random() < 0.4}
    keys = [key for key in spine_ref.column_keys if key in wanted]
    keys += [key for key in layers_.key_always + layers_.key_sometimes
             if key in wanted and key not in keys]
    keys = keys[:limits.columns[1]]
    titles = {c["key"]: c.get("title") for r in refs
              for c in (r.spec.get("columns") or []) if c.get("title")}
    widths = {c["key"]: c.get("width") for r in refs
              for c in (r.spec.get("columns") or [])}
    aligns = {c["key"]: c.get("align", "left") for r in refs
              for c in (r.spec.get("columns") or [])}

    columns = [{"key": key, "title": str(titles.get(key, key)),
                "width": int(widths.get(key, 10) or 0),
                "align": str(aligns.get(key, "left"))}
               for key in keys]

    blocks: list[dict[str, Any]] = []
    settings: dict[str, dict[str, Any]] = {}
    for name in order:
        block: dict[str, Any] = {"section": name,
                                 "region": _region_for(name, DOCSYNTH_LABEL_FOR_KIND)}
        if name == "table" and columns:
            block["columns"] = columns
        blocks.append(block)
        chosen = _seed_options(name, refs, spine_ref, vocab, rng,
                               skip.get(name) or set())
        if chosen:
            settings[name] = chosen

    # The sheet is decided AFTER the columns, not before, and that is the one
    # place this differs from §7.1 step 1 on purpose. A person answering
    # "who prints this" picks the paper and then fits the columns to it; a
    # seeded draw has no such answer, so picking the paper first would just
    # produce the arithmetic failure `check_numbers` reports -- the narrow end
    # of the band minus the reference columns leaving the item name too little
    # to hold its own weight and unit price. Widening the narrow end until the
    # flexible column clears `flex_min` is the same decision made in the only
    # order the information allows.
    gutter = rng.randint(*limits.gutter)
    fixed = sum(int(c["width"]) for c in columns)
    needed = fixed + gutter * max(len(columns) - 1, 0) + limits.flex_min
    low = max(limits.width[0], needed)
    width = [min(low, limits.width[1]), limits.width[1]]

    return Composition(
        document=document, seed=seed,
        paper={"sheet": limits.papers[rng.randrange(len(limits.papers))],
               "width": width, "gutter": gutter},
        reasoning={
            "printer": (f"chế độ coverage: không có server, nên tờ này do một "
                        f"phép bốc có hạt giống {seed} quyết, không do ai suy "
                        f"luận về nhà in"),
            "reader": (f"không suy luận — thứ tự khối và thứ tự cột chép từ "
                       f"phôi `{spine_ref.id}`, khối thêm vào đặt theo chỗ các "
                       f"phôi khác đặt nó"),
            "first": order[0] if order else "",
            "required": sorted(must | set(using)),
            "density": ((f"bỏ khối {', '.join(sorted(using))} và để "
                         f"{', '.join(sorted(c.option for c in using.values()))} "
                         f"in thay; " if using else "")
                        + f"bề ngang {width[0]}..{width[1]} ký tự — đầu hẹp lấy "
                        f"từ {fixed} ký tự cột cố định của phôi cộng "
                        f"{limits.flex_min} tối thiểu cho cột tên, không phải "
                        f"từ một phán đoán về giấy"),
        },
        blocks=blocks, settings=settings, by="coverage")


def _seed_options(section: str, refs: list[Reference], spine: Reference,
                  vocab: Vocabulary, rng: random.Random,
                  skip: set[str] | None = None) -> dict[str, Any]:
    """A block's settings, taken from the phôi and then moved off them.

    A composition that names its blocks and sets nothing is not a different
    print shop -- it is the builder's defaults, which is a *worse* page than
    any phôi rather than a different one. Measured the first time this ran:
    with no settings at all the `notes` block fell back to `style: block`
    where every reference that carries notes sets `two_column`, and nine
    blocks came out at **108% of the A4 sheet** at seed 2. `preflight` caught
    it, which is the correct place for it to be caught and the wrong place for
    it to keep being caught.

    So the spine's own settings are the starting point, and the variation is
    per key: where the *k* phôi disagree about a value, one of their values is
    drawn (that is layer 3, measured); where they agree, the value stands (that
    is layer 1 or 2, and moving it needs a reason a seeded draw does not have).
    A boolean nobody disagrees about is flipped only rarely, because a phôi
    agreeing six times out of six is evidence and a coin is not.
    """
    settings = dict(spine.spec.get(section) or {})
    known = vocab.options.get(section, {})
    skip = skip or set()
    out: dict[str, Any] = {}
    for name, spec in known.items():
        # A coupled setting is not the draw's to make. It follows from which
        # blocks the page carries, and `to_layout` is the one place that says
        # so -- copying a phôi's value for it here would put a second opinion
        # about the same decision into the composition.
        if name in skip:
            continue
        seen = [ref.spec[section][name] for ref in refs
                if isinstance(ref.spec.get(section), dict)
                and name in ref.spec[section]]
        if not seen:
            continue
        distinct = {json.dumps(value, sort_keys=True) for value in seen}
        if len(distinct) > 1:
            value = seen[rng.randrange(len(seen))]           # layer 3: measured
        elif spec.get("type") == "boolean" and rng.random() < 0.15:
            value = not settings.get(name, seen[0])          # a rare, deliberate flip
        else:
            value = settings.get(name, seen[0])
        if _option_problems("", value, spec):
            continue                # a phôi value the derived bounds refuse is
                                    # the schema's business, not this draw's
        out[name] = value
    return out


def _region_for(section: str, table: dict[str, str]) -> str:
    """The axis-1 label for a block, from the map the records already use.

    `pipeline.record` maps a run's `kind` prefix to a label; a section's name
    is the prefix for most of them (`totals` -> `total.`, `signatures` ->
    `sign.`), so the answer is looked up rather than restated. Text is the
    documented default of `layout_class_for` itself, so falling through to it
    is that function's own answer, not a guess made here.
    """
    for prefix in (section, section.rstrip("s") + ".", section + "."):
        if prefix in table:
            return table[prefix]
    return {"header": "Page-Header", "letterhead": "Page-Header",
            "doctitle": "Title", "footer": "Page-Footer",
            "table": "Table", "parties": "Form",
            "signatures": "Form"}.get(section, "Text")


# --------------------------------------------------------------------- A-2


def _agent_rules_root() -> Path:
    """A rules root carrying the `variant` attribute, so it can be pinned.

    The shipped rules have no `variant`: it is spliced in after `layout` by
    `agent/rules.py::compose` for the length of an agent run, which is why
    `--force variant=none` against `rulebase/rules/` fails with "unknown
    attribute". Both pages of a comparison have to wear the same dressing or
    the measurement is of the dressing, so the root is built the same way
    `agent/distance.py::main` builds it rather than the pin being dropped.
    """
    import tempfile as _tempfile

    from agent import policy as _policy, variants as _variants
    from agent import rules as _agent_rules

    catalogue = _variants.build(count=8, seed=0)
    return _agent_rules.materialise(
        Path(_tempfile.mkdtemp(prefix="cmp-rules-")), catalogue, _policy.load())


def nearest(layout_id: str, document: str, refs: list[Reference], seed: int,
            rules_root: Path | str | None = None) -> dict:
    """How far the composed layout sits from its NEAREST phôi (A-2).

    `agent/distance.py` already answers "did this move anything", and answers it
    the only honest way -- draw both pages and count the labelled runs that
    ended up somewhere else, after subtracting the bulk shift, because a page
    slid 15 mm as one piece is the same layout lower. What it does not do is
    compare two *layouts*: `measure()` pins one layout and varies the dressing,
    which is level 1's question.

    So this pins the dressing (`variant: none`, both sides) and varies the
    layout, and reuses `render`/`compare` unchanged. Nearest rather than mean,
    and that is the whole point of A-2: a composition that is far from five
    phôi and a copy of the sixth is a copy. The threshold to beat is **0.764**,
    the mean level 2 reached over 306 redraws -- level 3 costing more than
    level 2 and moving less would be level 2 with extra steps.
    """
    from agent.distance import compare, render

    import tempfile as _tempfile

    rules_root = Path(rules_root) if rules_root else _agent_rules_root()
    scores = {}
    # A composed layout that has been written and registered becomes a phôi of
    # its own document, which is correct for the NEXT composition and useless
    # here: comparing a page with itself measures 0.000 and would report the
    # thing being measured as its own nearest neighbour.
    for ref in (r for r in refs if r.id != layout_id):
        with _tempfile.TemporaryDirectory(prefix="cmp-ref-") as one, \
                _tempfile.TemporaryDirectory(prefix="cmp-new-") as two:
            base = {"document": document, "variant": "none"}
            left = render(Path(one), seed, {**base, "layout": ref.id}, Path(rules_root))
            right = render(Path(two), seed, {**base, "layout": layout_id},
                           Path(rules_root))
        if left is None or right is None:
            continue
        scores[ref.id] = compare(left, right)
    if not scores:
        return {"nearest": None, "distance": None, "scores": {}}
    closest = min(scores, key=lambda name: scores[name]["distance"])
    return {"nearest": closest, "distance": scores[closest]["distance"],
            "scores": {name: got["distance"] for name, got in scores.items()}}


# --------------------------------------------------------------- cửa ải 7


PROOF_ROOT = REPO_ROOT / "data" / "compose"


def proof(layout_id: str, document: str, count: int, seed: int,
          out: Path | str | None = None) -> tuple[Path, Any]:
    """Draw real pages of a composed layout and read them back (cửa ải 7).

    The six gates the command runs before this all read STRUCTURE: they build
    the grid, build the markup, and check that every label landed on a run.
    None of them makes a pixel, so none of them can see a heading that overlaps
    the column under it, a rule that runs off the trim, or type too small to
    read -- the thirteen codes in `agent/critic.py`, which is the reviewer's
    eye and the last gate of §9.

    It is also what A-5 needs. "Một nhà in có thể đã in tờ này" is a judgement
    about a photograph of paper, and a person cannot make it from a YAML file.
    So this leaves the images somewhere, and says where.

    Renders into `<out>/html` because that is the shape `critic.sweep` reads --
    the same shape `tools/agent_dataset.py` leaves behind, so a composed
    layout is reviewed by exactly the command that reviews a real run.
    """
    from agent import critic

    out = Path(out) if out else PROOF_ROOT / layout_id
    (out / "html").mkdir(parents=True, exist_ok=True)
    rules_root = _agent_rules_root()
    jobs = out / "jobs.json"
    # Pinned clean, and pinned on purpose. What is under review here is the
    # LAYOUT: whether its own boxes overlap, run off the trim, or come out too
    # small to read. Ageing is a separate axis with its own reviewer
    # (`tools/critic_review.py` over a real run), and letting it draw here
    # would mean a composed layout's verdict depended on which of 26
    # degradation models the seed happened to pick -- and, the first time this
    # ran, on whether Blender was installed at all.
    #
    # `pipeline.invariants.CLEAN_FORCES` is the repository's own name for
    # "the value whose chain is empty", so this uses it rather than spelling
    # `pristine` a second time and letting the two drift.
    from pipeline.invariants import CLEAN_FORCES

    jobs.write_text(json.dumps([{
        "layout": layout_id, "seed": seed, "count": count,
        "force": {"document": document, "layout": layout_id, "variant": "none",
                  **CLEAN_FORCES},
    }]), encoding="utf-8")

    import os
    import subprocess

    interpreter = REPO_ROOT / "generators" / "html" / ".venv" / "bin" / "python"
    done = subprocess.run(
        [str(interpreter if interpreter.exists() else sys.executable),
         str(REPO_ROOT / "generators" / "html" / "render.py"),
         "-o", str(out / "html"), "--jobs", str(jobs), "--template", "auto"],
        cwd=str(REPO_ROOT), env=dict(os.environ, VLM_RULES_ROOT=str(rules_root)),
        capture_output=True, text=True)
    if done.returncode != 0:
        raise ComposeError(f"render failed:\n{done.stderr.strip()[-800:]}")
    return out, critic.sweep(out)


# ------------------------------------------------------------------------ CLI


def open_for(document: str) -> tuple[Any, Any]:
    """Both gates, in the order that gives the most useful refusal.

    Policy first: `locked` is a statement about the paper and no amount of
    reviewing `constraints.yaml` changes it, so being told "this is a giấy tờ
    nhà nước" is more use than being told "add an entry".
    """
    pol = policy_module.load()
    klass = pol.klass(document)
    if klass == "locked":
        raise ComposeError(
            f"{document!r} is `locked` in policy.yaml: {pol.reasons['locked']} "
            f"Level 3 composes a shape that never existed, and for a phôi the "
            f"state issues that teaches the model a forgery is genuine.")
    return pol, constraints_mod.load().limits(document)


def _explain(document: str, refs: list[Reference], layers_: Layers,
             required: tuple[str, ...], limits, available: list[str]) -> int:
    print(f"{document}: {len(refs)} phôi tham khảo "
          f"({', '.join(r.id for r in refs)})")
    print(f"  lớp 1+2 (mọi phôi)  : {', '.join(layers_.always) or '—'}")
    print(f"  cột mọi phôi có     : {', '.join(layers_.key_always) or '—'}")
    print(f"  khối bắt buộc (R-4) : {', '.join(required)}")
    print(f"\n  LỚP 3 — chỗ được tự do, đo bằng chỗ các phôi bất đồng:")
    for name, values in layers_.varies.items():
        shown = ", ".join(values)
        if len(shown) > 96:
            shown = shown[:93] + "…"
        print(f"    {name:16} {shown or '—'}")
    print(f"  khối được chọn      : {', '.join(sorted(available))}")
    if limits is None:
        print(f"  ràng buộc           : CHƯA CÓ — viết mục {document!r} vào "
              f"agent/constraints.yaml\n"
              f"                        (khuôn để chép ở cuối file). Mức 3 "
              f"không chạy tới khi có.")
    else:
        print(f"  khổ giấy            : {', '.join(limits.papers)}  "
              f"· bề ngang {limits.width[0]}..{limits.width[1]}"
              f" · cột {limits.columns[0]}..{limits.columns[1]}")
    if not layers_.free:
        print(f"\n  ✗ không nhìn ra lớp 3: {len(refs)} phôi đồng ý về khối, thứ "
              f"tự, cột, tuỳ chọn VÀ khổ giấy.\n    Theo §8.2 đây KHÔNG phải "
              f"chứng từ của mức 3 — đo thêm một phôi thật,\n    hoặc để nó "
              f"cho mức 2 (`agent/augment_layout.py`).")
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--document", required=True, help="the document kind to compose for")
    parser.add_argument("--id", dest="layout_id", help="the new layout's id and file name")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--seeds", type=int, default=augment_layout.SEEDS,
                        help="how many pages the layout must draw")
    parser.add_argument("--explain", action="store_true",
                        help="print the three layers and stop -- what to read "
                             "before writing this document's constraints entry")
    parser.add_argument("--distance", metavar="LAYOUT_ID",
                        help="measure an ALREADY WRITTEN composed layout "
                             "against every phôi of --document and report the "
                             "nearest (A-2). Draws pages, so it needs the "
                             "renderer's venv.")
    parser.add_argument("--proof", type=int, metavar="N", default=0,
                        help="draw N real pages of an ALREADY WRITTEN composed "
                             "layout and run agent/critic.py over them (cửa ải "
                             "7). Leaves the images under data/compose/<id>/ "
                             "so a person can answer A-5.")
    parser.add_argument("--out", type=Path, default=None,
                        help="where --proof leaves its pages")
    parser.add_argument("--offline", action="store_true",
                        help="skip the server and compose by seeded draw")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--keep-failed", action="store_true")
    args = parser.parse_args(argv)

    # `--explain` is what a person runs BEFORE writing this document's
    # `constraints.yaml` entry -- both that file's header and the README say so
    # -- so it must not require the entry it exists to help write. It still
    # goes through the policy gate: reading the layers of a `locked` phôi is
    # reading the shape of a giấy tờ nhà nước for the purpose of redrawing it,
    # and the answer to that is no at every stage, not just the last one.
    try:
        pol = policy_module.load()
        if pol.klass(args.document) == "locked":
            raise ComposeError(
                f"{args.document!r} is `locked` in policy.yaml: "
                f"{pol.reasons['locked']} Level 3 composes a shape that never "
                f"existed, and for a phôi the state issues that teaches the "
                f"model a forgery is genuine.")
        refs = references(args.document)
        limits = None
        try:
            limits = constraints_mod.load().limits(args.document)
        except constraints_mod.ConstraintsError as error:
            if not args.explain:
                raise
            print(f"  · chưa có ràng buộc: {error}\n")
    except (ComposeError, policy_module.PolicyError,
            constraints_mod.ConstraintsError) as error:
        print(f"✗ {error}")
        return 2

    layers_ = layers(refs)
    vocab = vocabulary()
    required = required_sections(args.document, refs, limits)
    # A required block that is also forbidden is the two halves of the policy
    # contradicting each other, and resolving it silently either way produces a
    # page nobody asked for. Say which two lines disagree instead.
    forbidden = limits.forbidden if limits is not None else frozenset()
    clash = sorted(set(required) & forbidden)
    if clash:
        print(f"✗ {args.document}: constraints.yaml forbids {clash}, but every "
              f"phôi carries it (or the field spec fills it). One of the two "
              f"is wrong -- a block cannot be both required and refused.")
        return 2
    available = sorted((set(layers_.always) | set(layers_.sometimes) | set(required))
                       - forbidden)

    if args.explain:
        return _explain(args.document, refs, layers_, required, limits, available)
    if args.proof:
        target = args.layout_id or args.distance
        if not target:
            parser.error("--proof needs --id naming the layout to draw")
        try:
            where, review = proof(target, args.document, args.proof, args.seed,
                                  args.out)
        except ComposeError as error:
            print(f"✗ {error}")
            return 2
        from agent import critic

        print(critic.report(review))
        # A-3 counts PAGES with a severe finding, not findings: three
        # overlapping boxes on one sheet is one bad page, and `Review.
        # bad_pages` is the repository's own answer to that question.
        bad = review.bad_pages(critic.SEVERE)
        rate = len(bad) / max(review.pages, 1)
        print(f"\nảnh ở {where / 'html'} — {review.pages} trang, "
              f"{len(bad)} trang lỗi nặng ({rate:.1%}; A-3 đòi ≤ 1,2%)")
        print("Mở vài tấm và trả lời A-5: 'một nhà in có thể đã in tờ này?' — "
              "không cửa nào thay được câu ấy.")
        return 0 if rate <= 0.012 else 1

    if args.distance:
        got = nearest(args.distance, args.document, refs, args.seed)
        if got["distance"] is None:
            print(f"✗ {args.distance}: neither page drew; nothing to compare")
            return 2
        for name, value in sorted(got["scores"].items(), key=lambda kv: kv[1]):
            print(f"  {value:.3f}  {name}")
        floor = 0.764
        verdict = "✓" if got["distance"] > floor else "✗"
        print(f"\n{verdict} gần nhất: {got['nearest']} ở {got['distance']:.3f} "
              f"(A-2 đòi > {floor:.3f}, là trung bình mức 2 trên 306 lượt dựng "
              f"lại). Một tờ xa năm phôi mà trùng phôi thứ sáu vẫn là bản sao, "
              f"nên chỉ số là GẦN NHẤT chứ không phải trung bình.")
        return 0 if got["distance"] > floor else 1
    if not args.layout_id:
        parser.error("--id is required unless --explain, --distance or --proof")
    if not layers_.free:
        print(f"✗ {args.document}: {len(refs)} phôi đồng ý về khối, thứ tự, "
              f"cột, tuỳ chọn và khổ giấy, nên không có lớp 3 để đụng vào "
              f"(§8.2). Chạy với --explain để xem, rồi đo thêm một phôi thật.")
        return 2

    target = LAYOUTS / f"{args.layout_id}.yaml"
    if target.exists():
        print(f"✗ {target} already exists; pick another --id")
        return 2

    llm = None
    if not args.offline:
        from agent import client

        llm = client.from_env()
        if llm is not None and not llm.alive():
            print(f"  · {client.URL_ENV} is set but the server did not answer; "
                  f"composing offline")
            llm = None
        elif llm is None:
            print(f"  · {client.URL_ENV} is unset; composing offline")

    varies = [name for name, values in layers_.varies.items() if values]
    print(f"{args.document} -> {args.layout_id}: {len(refs)} phôi, "
          f"{len(available)} khối được chọn, {len(vocab.regions)} vùng nhãn, "
          f"lớp 3 ở: {', '.join(varies)}")

    comp = None
    for index in range(args.rounds if llm is not None else 1):
        if llm is None:
            candidate = offline(args.document, limits, refs, layers_, vocab,
                                available, args.seed, required)
        else:
            try:
                candidate = propose(llm, args.document, limits, refs, layers_,
                                    vocab, available, args.seed + index, required)
            except LLMError as error:
                print(f"  round {index + 1}: {error}")
                break
        problems = check(candidate, limits, layers_, vocab, required, available)
        label = f"  round {index + 1} ({candidate.by})"
        if problems:
            print(f"{label}: {len(problems)} problem(s)")
            for line in problems[:12]:
                print(f"      ✗ {line}")
            if len(problems) > 12:
                print(f"      ✗ ... and {len(problems) - 12} more")
            continue
        print(f"{label}: ✓ structure clean")
        comp = candidate
        break

    if comp is None:
        print("no round produced a composition that passes; nothing written")
        return 1
    if comp.unmet:
        print(f"  · R-8: the model asked for {len(comp.unmet)} thing(s) the "
              f"vocabulary has no name for -- these are the input to widening "
              f"`sheets/`, not a failure:")
        for item in comp.unmet:
            print(f"      · {item.get('want')}: {item.get('why')}")

    spec = to_layout(comp, args.layout_id, limits, refs, vocab)
    schema = schema_mod.derive()
    problems = (schema_mod.check(spec, schema) + schema_mod.ranges(spec)
                + [f"missing {key}, which every layout has"
                   for key in schema_mod.missing(spec)])
    if problems:
        print(f"  ✗ the built layout does not fit the schema derived from the "
              f"{len(refs)} phôi and their siblings:")
        for line in problems[:12]:
            print(f"      ✗ {line}")
        return 1
    print("  ✓ built layout passes the derived schema (cửa ải 4)")

    if not args.write:
        print("\n-- would write (pass --write) --")
        print(emit(spec, comp, "offline" if comp.by == "coverage" else "llm",
                   f"{comp.seed:04x}")[:1800])
        return 0

    target.write_text(emit(spec, comp, "offline" if comp.by == "coverage" else "llm",
                           f"{comp.seed:04x}"), encoding="utf-8")
    (target.with_suffix(".compose.json")).write_text(
        json.dumps(comp.to_dict(), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    print(f"wrote {target.relative_to(REPO_ROOT)} and its composition")

    before = {path: path.read_text(encoding="utf-8")
              for path in (augment_layout.RULES_LAYOUT, augment_layout.BLANKS)}

    def rollback() -> None:
        for path, text in before.items():
            path.write_text(text, encoding="utf-8")

    today = _datetime.date.today().isoformat()
    problems = augment_layout.register(
        args.layout_id, refs[0].id, today,
        note=(f"composed for {args.document} from {len(refs)} phôi, "
              f"registered against {refs[0].id} for its requires/excludes"))
    if problems:
        target.unlink()
        target.with_suffix(".compose.json").unlink(missing_ok=True)
        rollback()
        for line in problems:
            print(f"  ✗ {line}")
        return 1
    print(f"registered against {refs[0].id} in rules/layout.yaml and blanks.yaml")

    print(f"building {args.seeds} pages ...")
    problems = augment_layout.draws(args.layout_id, args.seeds)
    if not problems:
        print("  ✓ every seed drew a page, and every label landed on a run "
              "(cửa ải 6)")
        print("running preflight ...")
        problems = augment_layout.preflight()
        if not problems:
            print("  ✓ preflight clean")
    if problems:
        for line in problems[:10]:
            print(f"  ✗ {line}")
        orphans = sorted({line.split(":")[1].strip().split(".")[0]
                          for line in problems if "is in the label and on no run" in line
                          and ":" in line})
        if orphans:
            print(f"\n  · Nhãn mồ côi (I-5) trên trường {orphans}: một khối "
                  f"trang này bỏ đi vẫn được `rulebase.content` điền. Phép giao "
                  f"§8.1 đếm KHỐI chứ không đếm TRƯỜNG, nên nó không thấy. Chỗ "
                  f"sửa là `sections.required` của {args.document} trong "
                  f"agent/constraints.yaml — thêm khối in trường ấy vào đó.")
        print(f"\n{target.name} does not draw. Removing it and rolling both "
              f"registrations back: a half-registered layout is a rule base "
              f"naming a file that is not there, and preflight reports that as "
              f"a fault of the repository rather than of this command.")
        rollback()
        target.with_suffix(".compose.json").unlink(missing_ok=True)
        if args.keep_failed:
            target.rename(target.with_suffix(".yaml.rejected"))
        else:
            target.unlink()
        return 1

    print(f"\n{args.layout_id} qua sáu cửa ải chạy được ngoại tuyến. Còn hai "
          f"việc, và không cửa nào thay được:\n"
          f"  · `python -m agent.distance` — A-2, tờ này khác phôi bao nhiêu\n"
          f"  · một người đọc `reasoning` ở đầu file và trả lời A-5: "
          f"'một nhà in có thể đã in tờ này?'")
    return 0


__all__ = ["Composition", "ComposeError", "Layers", "REASONING_KEYS",
           "Reference", "Vocabulary", "check", "check_contract", "check_numbers",
           "check_structure", "emit", "field_spec", "layers", "main", "nearest",
           "offline", "proof",
           "open_for", "propose", "references", "regions", "required_sections",
           "schema_for", "to_layout", "user_message", "vocabulary"]

if __name__ == "__main__":
    raise SystemExit(main())
