"""Level 3: composing a layout that never existed, and what stops it.

The claim this file defends: **a composed layout cannot name anything the
repository does not draw, cannot drop a field the label promises, and cannot
be composed at all for a phôi nobody has bounded.** All three are enforced by
data -- `policy.yaml`, `constraints.yaml`, and the vocabulary derived from the
committed layouts -- so all three are tested against that data rather than
against the composer, which is the same rule `tests/test_agent.py` follows.

Nothing here draws a page. Gates 6 and 7 need Chromium and the renderer's own
interpreter, and they are exercised by the command itself
(`augment_layout.draws`, `preflight`); what is testable without them is every
gate that reads structure, which is gates 1 to 5.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent import compose_layout as compose  # noqa: E402
from agent import constraints as constraints_mod  # noqa: E402
from agent import layout_schema  # noqa: E402
from agent import policy as policy_module  # noqa: E402
from rulebase.layout import SECTIONS  # noqa: E402

# The one document `constraints.yaml` ships reviewed. Read rather than named
# twice: the point of the file is that this list is editorial, and a test that
# hard-coded the id would go red the day somebody reviews a second phôi.
OPEN_DOCUMENTS = constraints_mod.load().documents()


@pytest.fixture(scope="module")
def bench():
    """Everything one composition needs, for the first reviewed document."""
    document = OPEN_DOCUMENTS[0]
    _pol, limits = compose.open_for(document)
    refs = compose.references(document)
    layers = compose.layers(refs)
    vocab = compose.vocabulary()
    required = compose.required_sections(document, refs, limits)
    available = sorted((set(layers.always) | set(layers.sometimes) | set(required))
                       - limits.forbidden)
    return {"document": document, "limits": limits, "refs": refs,
            "layers": layers, "vocab": vocab, "required": required,
            "available": available}


def compose_one(bench, seed: int = 7):
    return compose.offline(bench["document"], bench["limits"], bench["refs"],
                           bench["layers"], bench["vocab"], bench["available"],
                           seed, bench["required"])


def verdict(bench, comp):
    return compose.check(comp, bench["limits"], bench["layers"], bench["vocab"],
                         bench["required"], bench["available"])


# ------------------------------------------------------------------ the gates


def test_the_constraints_open_at_least_one_document():
    """A scaffold with nothing reviewed would make every test below vacuous."""
    assert OPEN_DOCUMENTS, (
        "agent/constraints.yaml has no `reviewed: true` entry, so level 3 is "
        "shut for every document and nothing here is actually exercised")


def test_an_unbounded_document_is_refused_rather_than_defaulted():
    """The same stance `policy.py` takes: absence is an error, not permission."""
    loaded = constraints_mod.load()
    unbounded = next((name for name in policy_module.load().documents("free")
                      if name not in loaded.by_document
                      and name not in loaded.unreviewed), None)
    assert unbounded, "every free document is bounded; pick another for this test"
    with pytest.raises(constraints_mod.ConstraintsError, match="no entry"):
        compose.open_for(unbounded)


def test_a_locked_document_never_reaches_compose():
    """I-6. A phôi the state issues has one valid shape; composing a second
    teaches the model that a forgery is genuine."""
    for document in policy_module.load().documents("locked"):
        with pytest.raises(compose.ComposeError, match="locked"):
            compose.open_for(document)


def test_an_unreviewed_entry_is_shut_and_says_so(tmp_path):
    path = tmp_path / "constraints.yaml"
    path.write_text(yaml.safe_dump({
        "defaults": {"gutter": [1, 3], "flex_min": 12,
                     "sections": {"min": 2, "max": 12, "forbidden": []}},
        "documents": {"whatever": {"reviewed": False, "reviewer": ""}},
    }), encoding="utf-8")
    loaded = constraints_mod.load(path)
    assert loaded.documents() == []
    with pytest.raises(constraints_mod.ConstraintsError, match="not reviewed"):
        loaded.limits("whatever")


def test_a_reviewed_entry_with_no_reviewer_is_an_error(tmp_path):
    """The name is the point: it says who to ask about the numbers."""
    path = tmp_path / "constraints.yaml"
    path.write_text(yaml.safe_dump({
        "documents": {"x": {"reviewed": True, "papers": ["a4"],
                            "width": [40, 50], "gutter": [1, 2],
                            "columns": [2, 5], "flex_min": 8,
                            "sections": {"min": 2, "max": 6},
                            "families": ["modern"]}},
    }), encoding="utf-8")
    with pytest.raises(constraints_mod.ConstraintsError, match="no `reviewer:`"):
        constraints_mod.load(path)


@pytest.mark.parametrize("key,value,match", [
    ("papers", ["a3"], "not a sheet"),
    ("families", ["kiosk"], "dresses no committed layout"),
    ("width", [96, 72], "swapped"),
])
def test_a_name_the_repository_does_not_know_is_refused(tmp_path, key, value, match):
    """A constraint with a typo constrains nothing, and nothing else would say
    so -- which is the failure mode a constraints file has that a schema does
    not."""
    entry = {"reviewed": True, "reviewer": "test", "papers": ["a4"],
             "width": [40, 50], "gutter": [1, 2], "columns": [2, 5],
             "flex_min": 8, "sections": {"min": 2, "max": 6},
             "families": ["modern"]}
    entry[key] = value
    path = tmp_path / "constraints.yaml"
    path.write_text(yaml.safe_dump({"documents": {"x": entry}}), encoding="utf-8")
    with pytest.raises(constraints_mod.ConstraintsError, match=match):
        constraints_mod.load(path)


def test_a_forbidden_section_with_a_typo_is_refused(tmp_path):
    path = tmp_path / "constraints.yaml"
    path.write_text(yaml.safe_dump({"documents": {"x": {
        "reviewed": True, "reviewer": "test", "papers": ["a4"],
        "width": [40, 50], "gutter": [1, 2], "columns": [2, 5], "flex_min": 8,
        "sections": {"min": 2, "max": 6, "forbidden": ["vat_summry"]},
        "families": ["modern"]}}}), encoding="utf-8")
    with pytest.raises(constraints_mod.ConstraintsError, match="vat_summry"):
        constraints_mod.load(path)


def test_a_couple_naming_a_setting_no_layout_has_is_refused(tmp_path):
    """A coupling that matches nothing turns back into 'require both blocks',
    which is the conservative behaviour it was written to replace -- arrived at
    by accident, with nothing saying so."""
    path = tmp_path / "constraints.yaml"
    path.write_text(yaml.safe_dump({"documents": {"x": {
        "reviewed": True, "reviewer": "test", "papers": ["a4"],
        "width": [40, 50], "gutter": [1, 2], "columns": [2, 5], "flex_min": 8,
        "sections": {"min": 2, "max": 6}, "families": ["modern"],
        "couples": [{"option": "header.aligment", "equals": "corner",
                     "replaces": "strip"}]}}}), encoding="utf-8")
    with pytest.raises(constraints_mod.ConstraintsError, match="no committed"):
        constraints_mod.load(path)


# ------------------------------------------------------------- the vocabulary


def test_the_regions_are_the_eighteen_of_axis_one():
    """R-2. Read from the converter's own label set, so a composition cannot
    name a region no record will ever carry."""
    from pipeline.record import DOCSYNTH_LABELS

    got = compose.regions()
    assert len(got) == 18
    assert set(got) == set(DOCSYNTH_LABELS) - {compose.WHOLE_PAGE}


def test_every_section_the_vocabulary_offers_is_one_the_builder_draws():
    """R-3. `rulebase.layout.SECTIONS` is the dispatch table; a name outside it
    is a block the page would silently not have."""
    vocab = compose.vocabulary()
    assert set(vocab.sections) == set(SECTIONS)
    assert set(vocab.options) <= set(SECTIONS)


def test_no_section_option_carries_words_onto_the_paper():
    """A composition writes column titles and nothing else that gets printed.
    `parties.left_label` reads as a one-value enum to the derived schema and
    would otherwise hand the model the wording of 'BÊN MUA HÀNG'.

    Strings only, and the distinction is the point: `header.title` is a
    BOOLEAN -- print the document's own title or do not -- and a flag named
    after the thing it switches carries no words at all. What is refused is a
    *value* that lands on the paper, not a key whose name resembles one.
    """
    vocab = compose.vocabulary()
    for section, options in vocab.options.items():
        for name, spec in options.items():
            if spec.get("type") != "string":
                continue
            tail = name.split(".")[-1]
            assert not any(tail == word or tail.endswith(f"_{word}")
                           for word in layout_schema.TEXT_LEAVES), \
                f"{section}.{name} carries printed text"


# ----------------------------------------------------------------- the layers


def test_the_three_layers_are_read_off_the_phôi_not_asserted(bench):
    """§8.1. What every phôi shares is layer 1+2; what they differ on is
    layer 3, and that is a fact about a set of files."""
    layers, refs = bench["layers"], bench["refs"]
    for name in layers.always:
        assert all(name in ref.sections for ref in refs), name
    for name in layers.sometimes:
        seen = [name in ref.sections for ref in refs]
        assert any(seen) and not all(seen), name
    assert not set(layers.always) & set(layers.sometimes)


def test_a_document_whose_phôi_all_agree_has_no_third_layer():
    """§8.2: báo lại, đừng bịa. A single reference cannot show what varies."""
    one = compose.Reference(id="a", spec={"sections": ["header", "footer"]})
    assert not compose.layers([one]).free
    two = compose.Reference(id="b", spec={"sections": ["header", "footer"]})
    assert not compose.layers([one, two]).free
    three = compose.Reference(id="c", spec={"sections": ["footer", "header"]})
    assert compose.layers([one, three]).free, "a different ORDER is a choice too"


def test_layer_three_is_wider_than_which_blocks_are_present():
    """§8.1 lists "khổ giấy, có khung không, tên cột viết tắt hay đủ, có logo
    không" -- none of which is a block being present. Reading it as blocks only
    got the answer wrong on this repository's own evidence: exactly ONE of 33
    eligible documents has phôi that differ in which blocks they draw."""
    same_blocks = {"sections": ["header", "table"]}
    one = compose.Reference(id="a", spec={**same_blocks, "table": {"compact": True}})
    two = compose.Reference(id="b", spec={**same_blocks, "table": {"compact": False}})
    got = compose.layers([one, two])
    assert got.sometimes == () and len(set(got.orders)) == 1
    assert got.settings_vary == ("table.compact",)
    assert got.free, "four sheets a person drew from four photographs"


@pytest.mark.parametrize("dimension,spec", [
    ("thuộc tính cột", {"columns": [{"key": "name", "width": 20}]}),
    ("khổ giấy", {"width": [70, 80]}),
])
def test_every_layer_three_dimension_counts(dimension, spec):
    base = {"sections": ["header"], "columns": [{"key": "name", "width": 10}],
            "width": [40, 50]}
    one = compose.Reference(id="a", spec=dict(base))
    two = compose.Reference(id="b", spec={**base, **spec})
    assert compose.layers([one, two]).varies[dimension], dimension


def test_a_setting_only_one_phôi_declares_still_counts_as_disagreement():
    """`table.blank_rows` on one sheet of four is the choice that sheet made;
    treating "absent" as "agrees" would erase it."""
    one = compose.Reference(id="a", spec={"sections": ["table"], "table": {}})
    two = compose.Reference(id="b", spec={"sections": ["table"],
                                          "table": {"blank_rows": 6}})
    assert compose.layers([one, two]).settings_vary == ("table.blank_rows",)


def test_a_till_layout_that_names_no_sections_still_draws_six():
    """`build_grid` reads `spec.get("sections") or DEFAULT_SECTIONS`. Reading
    it literally made both phôi of `supermarket` look like they carried no
    blocks at all, and `--explain` reported a document with two real phôi as
    having nothing in common with itself."""
    from rulebase.layout import DEFAULT_SECTIONS

    assert compose.Reference(id="a", spec={}).sections == tuple(DEFAULT_SECTIONS)
    bare = [path.stem for path in compose.LAYOUTS.glob("*.yaml")
            if not (yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                    ).get("sections")]
    assert bare, "no layout relies on the default order any more; drop this test"


def test_a_generated_phôi_is_not_evidence():
    """The drift `layout_schema` avoids by measuring only human files: compose,
    register, compose again, and layer 3 grows to include a page no print shop
    made."""
    generated = [path.stem for path in compose.LAYOUTS.glob("*.yaml")
                 if layout_schema.is_generated(path)]
    for document in OPEN_DOCUMENTS:
        got = {ref.id for ref in compose.references(document)}
        assert not got & set(generated), document


# ------------------------------------------------- what a composition may say


def test_the_offline_composer_passes_every_structural_gate(bench):
    for seed in (0, 7, 11, 42, 99):
        comp = compose_one(bench, seed)
        assert verdict(bench, comp) == [], f"seed {seed}"


def test_the_same_seed_gives_the_same_composition(bench):
    """R-6. An LLM is only ever *usually* reproducible (agent/README.md §11);
    this half is byte-identical, so the claim has something to be true about."""
    assert compose_one(bench, 5).to_dict() == compose_one(bench, 5).to_dict()
    assert compose_one(bench, 5).to_dict() != compose_one(bench, 6).to_dict()


def test_reasoning_must_answer_all_five_questions(bench):
    """R-5. This measures empty, not platitude -- A-5 (a person, 50 pages a
    round) is what catches the rest, and the module says so."""
    for key in compose.REASONING_KEYS:
        comp = compose_one(bench)
        comp.reasoning[key] = "" if not isinstance(comp.reasoning[key], list) else []
        assert any("reasoning." + key in line for line in verdict(bench, comp))


def test_a_string_containing_a_tag_refuses_the_whole_composition(bench):
    """R-7/I-4. The measurement takes `span.firstElementChild || span`, so a
    nested tag quietly becomes the box that gets recorded."""
    comp = compose_one(bench)
    comp.reasoning["printer"] = "cửa hàng <b>tiện lợi</b>, in laser"
    problems = compose.check_contract(comp)
    assert problems and "'<'" in problems[0]


def test_css_that_breaks_the_box_contract_is_refused(bench):
    comp = compose_one(bench)
    comp.reasoning["density"] = "dùng text-transform: uppercase cho tiêu đề"
    assert any("text-transform" in line for line in compose.check_contract(comp))
    comp = compose_one(bench)
    comp.reasoning["density"] = "content: 'ĐÃ THANH TOÁN' ở góc"
    assert any("content:" in line for line in compose.check_contract(comp))


def test_an_invented_section_name_is_refused_not_ignored(bench):
    """R-3/A-6. A key the builder does not read is silently ignored, and the
    page comes out unchanged while the report claims a new layout."""
    comp = compose_one(bench)
    comp.blocks[1]["section"] = "sidebar_totals"
    assert any("sidebar_totals" in line for line in verdict(bench, comp))


def test_an_invented_region_is_refused(bench):
    comp = compose_one(bench)
    comp.blocks[0]["region"] = "Mark"
    assert any("Mark" in line for line in verdict(bench, comp))


def test_an_option_that_belongs_to_another_block_is_refused(bench):
    """Defence in depth: the schema makes this unspellable (see the next test),
    and this is what stops it from a server that ignored the schema."""
    comp = compose_one(bench)
    comp.settings.setdefault("table", {})["name_bold"] = True
    assert any("name_bold" in line for line in verdict(bench, comp))


def test_the_schema_cannot_spell_another_blocks_option(bench):
    """Cửa ải 1 has to make the wrong answer IMPOSSIBLE, not merely rejected.

    A single flat union of every block's settings permits `header.name_gap`
    (real, on `signatures`) and `table.indent` (real, on `totals`), and a model
    asked to fill an object fills what it is offered. Measured against a local
    server: 9 of 13 refusals in round 1, 12 of 14 in round 2 and 7 of 11 in
    round 3 were the schema inviting a key and the check refusing it.
    """
    schema = compose.schema_for(bench["document"], bench["limits"],
                                bench["layers"], bench["vocab"], bench["available"],
                                bench["refs"])
    settings = schema["properties"]["settings"]["properties"]
    assert settings, "no block offers settings; this test proves nothing"
    for section, spec in settings.items():
        assert spec["additionalProperties"] is False
        for name in spec["properties"]:
            assert bench["vocab"].option_spec(section, name) is not None
    # ...and the collisions that made the union wrong really do collide.
    everywhere = [name for spec in settings.values() for name in spec["properties"]]
    assert len(everywhere) > len(set(everywhere)), (
        "no two blocks share a settings name any more, so the union this "
        "replaced would have been harmless; drop the split if that holds")


def test_settings_for_a_block_that_is_not_on_the_page_are_refused(bench):
    comp = compose_one(bench)
    absent = next(name for name in SECTIONS if name not in comp.sections)
    comp.settings[absent] = {}
    assert any(absent in line for line in verdict(bench, comp))


def test_dropping_a_required_block_is_refused(bench):
    """R-4/I-3. A block dropped here is a label describing a value the page
    does not print, which is what `pipeline/invariants.py` fails a shard over."""
    comp = compose_one(bench)
    droppable = next(name for name in bench["required"]
                     if name in comp.sections
                     and bench["limits"].couple_for(name) is None)
    comp.blocks = [b for b in comp.blocks if b["section"] != droppable]
    assert any("missing blocks" in line for line in verdict(bench, comp))


def test_a_coupled_block_and_its_stand_in_are_exactly_one_of_the_two(bench):
    """Asserted on the BUILT LAYOUT, not on the composition, because that is
    where the invariant now lives.

    Across all 52 committed layouts `header.align: corner` holds exactly when
    `strip` is absent and `table.component: true` exactly when `totals` is --
    one decision. The composition states it once, by listing the block or not;
    `to_layout` writes the setting. Asking for it in both places made a real
    server fail three rounds running, each time wanting a corner masthead AND
    a date strip -- a reasonable page, refused for disagreeing with itself
    about a thing it had been asked twice.
    """
    couples = bench["limits"].couples
    if not couples:
        pytest.skip("no couples declared for this document")
    for seed in range(12):
        comp = compose_one(bench, seed)
        spec = compose.to_layout(comp, "test_composed", bench["limits"],
                                 bench["refs"], bench["vocab"])
        for couple in couples:
            on = (spec.get(couple.section) or {}).get(couple.leaf) == couple.value
            assert on != (couple.replaces in spec["sections"]), (
                f"seed {seed}: {couple.replaces} and {couple.option} must be "
                f"exactly one of the two, never both and never neither")


def test_the_model_is_never_offered_the_stand_in_value(bench):
    """Cửa ải 1 again: unspellable beats rejected. The leaf survives where it
    has other values -- `header.align: split` is still a choice."""
    schema = compose.schema_for(bench["document"], bench["limits"],
                                bench["layers"], bench["vocab"],
                                bench["available"], bench["refs"])
    settings = schema["properties"]["settings"]["properties"]
    for couple in bench["limits"].couples:
        spec = (settings.get(couple.section) or {}).get("properties", {})
        offered = spec.get(couple.leaf)
        if offered is None:
            continue                      # struck entirely: nothing left to say
        assert couple.value not in offered.get("enum", []), couple.option


def test_both_a_block_and_its_stand_in_is_refused(bench):
    limits = bench["limits"]
    couple = next(iter(limits.couples), None)
    if couple is None:
        pytest.skip("no couples declared for this document")
    comp = next(compose_one(bench, seed) for seed in range(12)
                if couple.replaces in compose_one(bench, seed).sections)
    comp.settings.setdefault(couple.section, {})[couple.leaf] = couple.value
    assert any("does the other's job" in line for line in verdict(bench, comp))


# ------------------------------------------------------- the flexible column


def test_exactly_one_column_takes_the_rest_of_the_sheet(bench):
    """`width: 0` is a sentinel, not a small number. With none every column is
    fixed and the sheet has a gap; with two neither knows what it gets."""
    comp = compose_one(bench)
    table = comp.table_block()
    assert sum(1 for c in table["columns"] if c["width"] == compose.FLEX) == 1
    table["columns"][0]["width"] = compose.FLEX
    assert any("carry `width: 0`" in line for line in verdict(bench, comp))


def test_widening_a_fixed_column_narrows_the_name_and_is_caught(bench):
    """`augment_layout._slack`'s lesson, stated as a bound rather than as a
    comparison against a parent, because level 3 has no parent."""
    comp = compose_one(bench)
    table = comp.table_block()
    for column in table["columns"]:
        if column["width"] != compose.FLEX:
            column["width"] += 12
    assert any("flexible column gets" in line for line in verdict(bench, comp))


def test_the_column_ceiling_comes_from_the_phôi_not_from_half_the_sheet(bench):
    """Half an A4 measure is 48 characters; the widest fixed column any of the
    six phôi rules is 15. The loose bound let a model spend the budget on two
    columns and hand the item name zero -- twice, on the first real run."""
    schema = compose.schema_for(bench["document"], bench["limits"],
                                bench["layers"], bench["vocab"], bench["available"],
                                bench["refs"])
    column = schema["properties"]["blocks"]["items"]["properties"]["columns"]
    ceiling = column["items"]["properties"]["width"]["maximum"]
    widest = max(int(c.get("width") or 0) for ref in bench["refs"]
                 for c in (ref.spec.get("columns") or []))
    assert widest <= ceiling < bench["limits"].width[1] // 2


def test_the_user_message_does_the_width_arithmetic_for_the_model(bench):
    """A sum constraint is the one thing JSON Schema cannot express, so it is
    stated in the prompt with the phôi's own numbers rather than as a rule the
    model has to rediscover."""
    message = compose.user_message(bench["document"], bench["limits"],
                                   bench["refs"], bench["layers"], bench["vocab"],
                                   bench["available"], 1, bench["required"])
    assert str(bench["limits"].flex_min) in message
    assert "≤" in message
    for couple in bench["limits"].couples:
        assert couple.option in message and couple.replaces in message


def test_a_number_is_written_in_the_type_the_corpus_writes_it_in(bench):
    """JSON has one number type; `layout_schema` has Python's two and refuses
    `totals.indent: 0` because all seven layouts that set it write a float.
    Right for a hand-written file -- an integer there is a person meaning
    something else -- and wrong for a value that crossed a wire, where the
    model chose the VALUE and the type is an artefact of the format.
    """
    assert isinstance(compose._as_written({"type": "number"}, 1), float)
    assert isinstance(compose._as_written({"type": "integer"}, 3.0), int)
    # Only when it survives exactly, and never onto a bool.
    assert compose._as_written({"type": "integer"}, 3.5) == 3.5
    assert compose._as_written({"type": "number"}, True) is True
    assert compose._as_written({"type": "array", "items": {"type": "number"}},
                               [1, 2]) == [1.0, 2.0]


def test_the_built_layout_survives_a_number_sent_as_an_integer(bench):
    """End to end, on whichever float leaf has a whole number inside its own
    measured range -- the shape of the failure a real server produced."""
    import math

    comp = compose_one(bench)
    found = None
    for section, options in bench["vocab"].options.items():
        if section not in comp.sections:
            continue
        for name, spec in options.items():
            if spec.get("type") != "number":
                continue
            whole = math.ceil(spec["minimum"])
            if spec["minimum"] <= whole <= spec["maximum"]:
                found = (section, name, whole)
                break
        if found:
            break
    if not found:
        pytest.skip("no float leaf on this page has a whole number in range")
    section, name, whole = found
    comp.settings.setdefault(section, {})[name] = whole
    spec = compose.to_layout(comp, "test_composed", bench["limits"],
                             bench["refs"], bench["vocab"])
    assert layout_schema.check(spec, layout_schema.derive()) == []


def test_a_paper_the_document_may_not_use_is_refused(bench):
    """I-2. A till roll cannot wear a 16 mm margin; a supermarket slip is not
    A3."""
    comp = compose_one(bench)
    other = next(name for name in ("a5_landscape", "letter", "a5")
                 if name not in bench["limits"].papers)
    comp.paper["sheet"] = other
    assert any(other in line for line in verdict(bench, comp))


# ------------------------------------------------------------- the builder


def test_the_built_layout_fits_the_schema_derived_from_hand_written_ones(bench):
    """Gate 4, on the composer's own output: a key path no person ever wrote is
    a key the builder ignores, so the page draws unchanged while the run
    reports a new layout."""
    schema = layout_schema.derive()
    for seed in (0, 7, 42):
        spec = compose.to_layout(compose_one(bench, seed), "test_composed",
                                 bench["limits"], bench["refs"], bench["vocab"])
        assert layout_schema.check(spec, schema) == [], f"seed {seed}"
        assert layout_schema.ranges(spec) == [], f"seed {seed}"
        assert layout_schema.missing(spec) == [], f"seed {seed}"


def test_the_builder_writes_the_item_wiring_not_the_model(bench):
    """I-1. `item.rows` is derived from the chosen columns rather than
    restated, so a composition physically cannot promise a `from:` its own
    table has no column for."""
    comp = compose_one(bench)
    spec = compose.to_layout(comp, "test_composed", bench["limits"],
                             bench["refs"], bench["vocab"])
    keys = [column["key"] for column in spec["columns"]]
    for row in spec["item"]["rows"]:
        assert [cell["from"] for cell in row] == keys
        assert [cell["col"] for cell in row] == keys


def test_the_model_does_not_get_to_write_the_provenance(bench):
    """`source:` names the photograph a shape was measured against, and a
    composed shape was measured against none. A model asked to write that field
    once produced a receipt from a year nobody photographed."""
    comp = compose_one(bench)
    comp.reasoning["printer"] = "đo từ ảnh hoá đơn Co.op 2023"
    spec = compose.to_layout(comp, "test_composed", bench["limits"],
                             bench["refs"], bench["vocab"])
    assert "2023" not in spec["source"]
    assert "không đo từ ảnh nào" in spec["source"]
    assert all(ref.id in spec["source"] for ref in bench["refs"])


def test_the_header_records_the_five_answers(bench):
    """§3.2: the reviewer reads them to know why this layout exists, and
    `yaml.safe_load` never sees a comment, so nothing downstream is affected."""
    comp = compose_one(bench)
    spec = compose.to_layout(comp, "test_composed", bench["limits"],
                             bench["refs"], bench["vocab"])
    text = compose.emit(spec, comp, "offline", "0000")
    assert text.startswith(layout_schema.MARK)
    for key in compose.REASONING_KEYS:
        assert key in text.split("id:")[0]
    assert yaml.safe_load(text)["id"] == "test_composed"


# ------------------------------------------------------------ the guided schema


def test_the_schema_closes_every_set_a_composition_may_draw_from(bench):
    """Gate 1. An enum is worth more than a paragraph of prompt: it makes 'the
    model invented a name' impossible rather than unlikely, which is what makes
    A-6 measurable."""
    schema = compose.schema_for(bench["document"], bench["limits"],
                                bench["layers"], bench["vocab"], bench["available"],
                                bench["refs"])
    block = schema["properties"]["blocks"]["items"]["properties"]
    assert set(block["section"]["enum"]) == set(bench["available"])
    assert set(block["region"]["enum"]) == set(compose.regions())
    assert set(schema["properties"]["paper"]["properties"]["sheet"]["enum"]) \
        == set(bench["limits"].papers)
    column = block["columns"]["items"]["properties"]
    assert set(column["key"]["enum"]) <= set(compose.vocabulary().column_keys)
    assert schema["properties"]["blocks"]["additionalProperties" if False else
                                          "maxItems"] == bench["limits"].sections_max


def test_reasoning_is_generated_before_the_blocks_it_decided():
    """A decoder emits properties in the order the schema lists them. The other
    order would make the five answers a caption written after the fact."""
    document = OPEN_DOCUMENTS[0]
    _pol, limits = compose.open_for(document)
    refs = compose.references(document)
    schema = compose.schema_for(document, limits, compose.layers(refs),
                                compose.vocabulary(), ["header", "footer"], refs)
    keys = list(schema["properties"])
    assert keys.index("reasoning") < keys.index("blocks")


def test_no_integer_leaf_is_bounded_by_a_fraction():
    """A schema that contradicts itself is not caught by anything downstream.

    `layout_schema.Leaf.bounds()` pads by SLACK and so always returns floats,
    which is right where `ranges()` compares a value against them and wrong
    here. Six option leaves shipped as `{"type": "integer", "minimum":
    1.4285714285714286}`, and a real vLLM host answered the whole composition
    request with HTTP 500 and an empty message -- the grammar backend builds an
    integer lexeme out of that bound and dies inside the engine, where no
    validation layer is left to name the cause. Measured on that host: the same
    schema with only those six leaves rounded answers 200, and the same schema
    with only the float-ranged leaves removed still answers 500. So the fraction
    on an integer was both necessary and sufficient, and it is worth a gate of
    its own -- every document, because the bounds come from each one's data.
    """
    for document in OPEN_DOCUMENTS:
        _pol, limits = compose.open_for(document)
        refs = compose.references(document)
        layers = compose.layers(refs)
        required = compose.required_sections(document, refs, limits)
        available = sorted((set(layers.always) | set(layers.sometimes)
                            | set(required)) - limits.forbidden)
        schema = compose.schema_for(document, limits, layers,
                                    compose.vocabulary(), available, refs)
        bad: list[str] = []

        def walk(node, path):
            if isinstance(node, dict):
                if node.get("type") == "integer":
                    for key in ("minimum", "maximum"):
                        if key in node and not isinstance(node[key], int):
                            bad.append(f"{path}.{key} = {node[key]!r}")
                for key, value in node.items():
                    walk(value, f"{path}.{key}")
            elif isinstance(node, list):
                for index, value in enumerate(node):
                    walk(value, f"{path}[{index}]")

        walk(schema, document)
        assert not bad, ("an integer bounded by a fraction: "
                         + ", ".join(sorted(bad)))


def test_no_schema_property_would_admit_markup(bench):
    """R-7 is enforced twice on purpose: the schema keeps `<` out of the enums
    and bounded strings, and `check_contract` refuses it in whatever a server
    that ignores the schema sends back."""
    schema = compose.schema_for(bench["document"], bench["limits"],
                                bench["layers"], bench["vocab"], bench["available"],
                                bench["refs"])

    def walk(node):
        if isinstance(node, dict):
            for value in node.get("enum", []):
                assert "<" not in str(value)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(schema)


def test_the_prompt_asks_the_five_questions_in_order():
    """The five are the whole method (§7); a prompt that lost one would still
    fill `reasoning` and the loss would show up only in A-5, months later."""
    from agent.ollama import prompt

    text = prompt("compose")
    at = [text.index(f"`{key}`") for key in compose.REASONING_KEYS]
    assert at == sorted(at), "the five questions are out of order in the prompt"


def test_the_user_message_names_only_facts_read_from_the_repository(bench):
    message = compose.user_message(bench["document"], bench["limits"],
                                   bench["refs"], bench["layers"], bench["vocab"],
                                   bench["available"], 11, bench["required"])
    for ref in bench["refs"]:
        assert ref.id in message
    for name in bench["required"]:
        assert name in message
    assert bench["limits"].reviewer in message
    assert "<" not in message


# ------------------------------------------------------------------ the report


def test_a_composition_records_which_mode_decided_it(bench):
    """`agent/README.md` §4: a run that silently degrades is the bad outcome; a
    run that records which mode it used, per page, is not."""
    assert compose_one(bench).by == "coverage"


def test_offline_reasoning_never_invents_a_printer(bench):
    """A fabricated printer story is exactly the platitude §3.2 exists to make
    visible, and a reviewer skimming `by: coverage` pages has to be able to
    tell them from the model's at a glance."""
    reasoning = compose_one(bench).reasoning
    assert "coverage" in reasoning["printer"]
    assert "không suy luận" in reasoning["reader"]


def test_deep_copying_a_composition_changes_nothing(bench):
    """`offline` seeds a block's options off the phôi; sharing a mutable value
    with `rulebase/layouts/*.yaml`'s parsed spec would let a later edit reach
    back into it."""
    comp = compose_one(bench)
    before = copy.deepcopy(comp.to_dict())
    compose.to_layout(comp, "test_composed", bench["limits"], bench["refs"],
                      bench["vocab"])
    assert comp.to_dict() == before
