"""The generation step, and the boundary that keeps it out of the render path.

No model runs here. Everything under test is a pure function over strings --
the validator, the provenance stamp, the line cleaner -- which is deliberate:
those are the parts that decide what reaches `rulebase/`, and a test that
needed a 4.7 GB checkpoint to run is a test that does not run.

The first test is the load-bearing one. `tools/llm/` may write files that the
pipeline later reads; it may never be *called* by the pipeline. If that ever
stops being true, the repository quietly loses the property everything else
rests on -- the same seed drawing the same bytes -- and it loses it without a
single test going red anywhere else.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.llm import corpus_rules as rules  # noqa: E402
from tools.llm import layout_schema  # noqa: E402
from tools.llm import provenance as prov  # noqa: E402
from tools.llm.client import lines_of, retab  # noqa: E402

# Where the render path lives. Every one of these is imported by a running
# render or a running pipeline, so an import of `tools.llm` from any of them
# would put a model call on that path.
RENDER_PATH = ("generators", "pipeline", "rulebase", "degradation", "components")


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def test_the_render_path_cannot_reach_the_generator():
    """The whole architecture, as one assertion.

    A model in the render path costs `tools/baseline.py`, the byte-for-byte
    check in `tests/test_worklist.py`, and every renderer comparison that rests
    on "only the drawing differs" -- and it costs them silently, because the
    images still come out.
    """
    offenders = []
    for package in RENDER_PATH:
        for path in (REPO_ROOT / package).rglob("*.py"):
            if ".venv" in path.parts:
                continue
            for name in _imports(path):
                if name == "tools.llm" or name.startswith("tools.llm."):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} imports {name}")
    assert offenders == [], (
        "the render path must not import the generator:\n  " + "\n  ".join(offenders))


def test_the_generator_never_writes_outside_the_corpus_and_the_rules():
    """A generator that could write anywhere is a generator nobody can review.

    Checked as text rather than by running it, because the point is that the
    paths are *stated* in the source: an audit reads this list, not a strace.
    """
    allowed = ("rulebase/corpus", "rulebase/layouts", "rulebase/variants")
    for path in (REPO_ROOT / "tools" / "llm").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "open(" in source and "\"a\"" in source:
            assert any(part in source for part in ("CORPUS_VI", "CORPUS_ROOT")), (
                f"{path.name} appends to a file without going through a "
                "corpus path constant")
        # `allowed` used to be declared and never read, so the list an audit is
        # told to read was not checked against anything. Every rulebase path
        # named in the source has to sit under one of the three roots.
        for named in re.findall(r'"(rulebase/[^"]+)"', source):
            assert named.startswith(allowed), (
                f"{path.name} names {named!r}, outside {allowed}")


# ------------------------------------------------------------- the validator


def test_the_rules_accept_every_committed_line():
    """The audit, as a test. A rule that rejects a line a person already wrote
    is a broken rule -- and the first version of these rules rejected 48 % of
    the corpus, then 25 %, before this test existed to say so."""
    total, thrown = rules.audit()
    assert total > 500, "the corpus went missing, not the rules"
    assert thrown == [], "\n".join(f"{item.why}: {item.line}" for item in thrown[:10])


@pytest.mark.parametrize("line,why", [
    ("Sữa tươi Vinamilk 1L\t28.000\t35.000", "plain integers"),
    ("Sữa tươi Vinamilk 1L\t35000\t28000", "not below"),
    ("Sữa tươi Vinamilk 1L\t2000\t900000", "spans more"),
    ("Sữa tươi Vinamilk 1L\t28000", "columns"),
    ("Милка шоколад молочный\t28000\t35000", "does not use"),
    ("Sữa 🥛 Vinamilk 1L\t28000\t35000", "does not use"),
    ("  Sữa tươi Vinamilk 1L\t28000\t35000", "padded"),
])
def test_a_bad_item_line_is_refused_with_the_reason(line, why):
    assert why in rules.check(line, rules.SHAPES["items"])


def _sizes(stem: str):
    """The real file's measured envelope, which is what the generator uses."""
    return rules.envelopes(
        (rules.CORPUS_ROOT / "vi" / f"{stem}.txt").read_text(encoding="utf-8"))


def test_a_good_item_line_is_kept():
    assert rules.check("Sữa tươi Vinamilk không đường 1L\t28000\t35000",
                       rules.SHAPES["items"], _sizes("items_market")) == ""


def test_a_bare_noun_is_refused_on_a_supermarket_line_and_kept_on_a_menu():
    """The reason the envelope is per file rather than per family. `Phở gà` is
    a real menu line; `Sữa` is not a real supermarket line. No single word
    count separates them -- the file each belongs to does."""
    assert rules.check("Phở gà\t35000\t55000",
                       rules.SHAPES["items"], _sizes("items_eatery")) == ""
    assert rules.check("Sữa\t28000\t35000",
                       rules.SHAPES["items"], _sizes("items_market"))
    # ... and the same line against the menu file is fine, which is the point:
    # nothing about `Sữa` is wrong, it is wrong *for a supermarket line*.
    assert rules.check("Sữa\t28000\t35000",
                       rules.SHAPES["items"], _sizes("items_eatery")) == ""


def test_a_generated_line_cannot_widen_the_envelope_for_the_next_round():
    """Otherwise the tenth round is checked against the ninth round's mistakes
    -- a validator slowly ratifying its own drift."""
    stamp = prov.Stamp("m", "d", "p:0000", 0, "2026-08-26")
    human_lines = "\n".join(f"Món ăn số {n}\t20000\t30000" for n in range(12))
    drifted = human_lines + "\n" + stamp.block(
        ["Một cái tên rất dài lê thê vượt xa mọi dòng người viết ra ở đây\t20000\t30000"])
    assert rules.envelopes(drifted)[0] == rules.envelopes(human_lines)[0]


def test_the_letter_d_with_a_stroke_is_a_latin_letter():
    """The bug that rejected 209 committed lines. `đ` does not decompose under
    NFD -- the bar is part of the letter -- so a Latin test written as a range
    throws out the most Vietnamese letter there is."""
    assert rules.check_name("Đường trắng Biên Hoà", rules.SHAPES["items"]) == ""
    assert rules.check_name("Bánh đa nem", rules.SHAPES["items"]) == ""


def test_a_decomposed_name_is_the_same_as_a_composed_one():
    """Vietnamese may arrive with its marks split off; both are the same word."""
    import unicodedata

    composed = "Cà phê sữa đá"
    assert rules.check_name(composed, rules.SHAPES["items"]) == ""
    assert rules.check_name(unicodedata.normalize("NFD", composed),
                            rules.SHAPES["items"]) == ""


def test_a_family_is_held_to_its_own_shape_not_a_shared_one():
    """`wards.txt` is three columns of ward, district and city -- three columns
    does not mean prices -- and a footer is shouted on purpose."""
    assert rules.check("Nhân Chính\tThanh Xuân\tHà Nội", rules.SHAPES["wards"]) == ""
    assert rules.check("CẢM ƠN QUÝ KHÁCH VÀ HẸN GẶP LẠI",
                       rules.SHAPES["footers"]) == ""
    # ... and the same shouting is refused where the corpus stores names cased.
    assert "ALL CAPS" in rules.check("SỮA TƯƠI VINAMILK 1L\t28000\t35000",
                                     rules.SHAPES["items"])


def test_a_stuttered_name_is_refused_and_a_real_repeat_is_not():
    """A small model padding to a length repeats the phrase it just wrote:
    `Cà phê hòa tan hòa tan 250g` came out of a real round. But a single word
    repeating is ordinary Vietnamese -- `HẢO HẢO` is a brand and `in ấn ấn
    phẩm` is two words that happen to meet -- and the first version of this
    check rejected both."""
    sizes = _sizes("items_market")
    assert "twice in a row" in rules.check(
        "Cà phê hòa tan hòa tan 250g\t22000\t30000", rules.SHAPES["items"], sizes)
    assert rules.check("HẢO HẢO Mì tôm chua cay thùng 30 gói\t105000\t135000",
                       rules.SHAPES["items"], sizes) == ""


def test_an_unmeasured_family_is_an_error_not_a_free_pass():
    with pytest.raises(KeyError, match="no shape"):
        rules.shape_of("gadgets_market")


def test_a_batch_with_no_vietnamese_at_all_is_caught_as_a_batch():
    """Per line, "no diacritic" is false -- `Natri Clorid 0,9%` is a real drug.
    Over a batch it is the signal: the model answered in the wrong language."""
    assert rules.foreign_batch(["Milk 1L", "Sugar 1kg", "Rice 5kg", "Salt 500g"])
    assert not rules.foreign_batch(["Sữa tươi 1L", "Đường trắng 1kg",
                                    "Gạo ST25 5kg", "Muối I-ốt 500g"])
    # Two lines is not a batch; refusing on that would refuse real short answers.
    assert not rules.foreign_batch(["Milk 1L", "Sugar 1kg"])


def test_sifting_drops_duplicates_of_the_corpus_and_of_itself():
    existing = ["Sữa tươi Vinamilk 1L\t28000\t35000"]
    kept, thrown = rules.sift(
        ["Sữa tươi Vinamilk 1L\t30000\t36000",     # same product, new band
         "Bánh quy Cosy bơ sữa 200g\t22000\t30000",
         "bánh quy cosy bơ sữa 200g\t23000\t31000"],   # same, differently cased
        existing, rules.SHAPES["items"])
    assert kept == ["Bánh quy Cosy bơ sữa 200g\t22000\t30000"]
    assert [item.why for item in thrown] == ["already in the corpus"] * 2


# ------------------------------------------------------------ the line cleaner


@pytest.mark.parametrize("raw,want", [
    ("1. Sữa tươi Vinamilk 1L", "Sữa tươi Vinamilk 1L"),
    ("- Sữa tươi Vinamilk 1L", "Sữa tươi Vinamilk 1L"),
    ("* Sữa tươi Vinamilk 1L.", "Sữa tươi Vinamilk 1L"),
    ("   Sữa   tươi   1L  ", "Sữa tươi 1L"),
])
def test_the_cleaner_strips_what_a_chat_model_adds(raw, want):
    assert lines_of(raw) == [want]


def test_the_cleaner_drops_fences_and_keeps_tabs():
    text = "```\nSữa tươi 1L\t28000\t35000\n```"
    assert lines_of(text) == ["Sữa tươi 1L\t28000\t35000"]


def test_retab_puts_back_a_tab_the_model_dropped():
    """Measured: round one on items_market lost 15 of 15 lines to `1 columns;
    this family has 3`, because the model copied the columns and not the tab."""
    assert retab("Bánh mì nướng bơ 100g 18000 30000", 3) == \
        "Bánh mì nướng bơ 100g\t18000\t30000"
    assert retab("VinCommerce VM Royal City", 2) == "VinCommerce VM Royal City"


def test_retab_refuses_to_guess_where_a_column_ends():
    """Narrow on purpose: it may put a separator back, never invent one.

    A guess about where a column ends is a guess in the dataset, so anything
    ambiguous is returned untouched and the validator rejects it -- which is
    the outcome that shows up in the rejection list rather than in a page.
    """
    # Already tabbed: nothing to do, and re-splitting would destroy a real name.
    assert retab("Sữa 1L\t28000\t35000", 3) == "Sữa 1L\t28000\t35000"
    # A name ending in one number is not a three-column line.
    assert retab("Sữa tươi 1L", 3) == "Sữa tươi 1L"
    # Prices with separators are not integers, so this stays broken and is
    # rejected for it -- rather than being silently repaired into the corpus.
    assert retab("Sữa tươi 1L 28.000 35.000", 3) == "Sữa tươi 1L 28.000 35.000"
    assert retab("Sữa tươi 1L", 1) == "Sữa tươi 1L"


def test_the_cleaner_does_not_repair_content():
    """It removes formatting and nothing else. A cleaner that fixed a bad line
    would be a cleaner that let a bad line through wearing a hat."""
    assert lines_of("Milk 1L\t28.000\t35.000") == ["Milk 1L\t28.000\t35.000"]


# --------------------------------------------------------------- provenance


def test_a_stamped_block_is_comments_every_existing_reader_already_skips():
    stamp = prov.Stamp("qwen2.5:7b-instruct", "845dbda0ea48", "items:3f2a",
                       11, "2026-08-26")
    block = stamp.block(["Sữa tươi 1L\t28000\t35000"])
    fences = [line for line in block.splitlines()
              if line.startswith(prov.OPEN) or line == prov.CLOSE]
    assert len(fences) == 2
    assert all(line.startswith("#") for line in fences)


def test_an_empty_block_writes_nothing_rather_than_a_bare_stamp():
    stamp = prov.Stamp("m", "d", "p:0000", 0, "2026-08-26")
    assert stamp.block([]) == ""


def test_a_stamp_reads_back_off_the_file_it_was_written_into():
    """The audit direction: given a corpus, which of it did a model write?"""
    stamp = prov.Stamp("qwen2.5:7b-instruct", "845dbda0ea48", "items:3f2a",
                       11, "2026-08-26")
    text = ("# a comment\nGạo ST25 5kg\t195000\t240000\n"
            + stamp.block(["Sữa tươi 1L\t28000\t35000", "Muối I-ốt 500g\t6000\t9000"]))
    found = prov.blocks(text)
    assert len(found) == 1
    assert found[0][0] == stamp
    assert len(found[0][1]) == 2
    assert prov.generated(text) == {"Sữa tươi 1L\t28000\t35000",
                                    "Muối I-ốt 500g\t6000\t9000"}
    assert prov.human(text) == {"Gạo ST25 5kg\t195000\t240000"}


def test_every_committed_corpus_line_is_attributable():
    """Not that a model wrote them -- that a reader can tell which did.

    A corpus with unfenced generated lines in it is a corpus where "is this
    real?" has no answer, which is the whole reason the fence exists.
    """
    for path in sorted(rules.CORPUS_ROOT.rglob("*.txt")):
        text = path.read_text(encoding="utf-8")
        stamps = prov.blocks(text)
        for stamp, body in stamps:
            assert stamp.digest and stamp.model, path.name
            assert body, f"{path.name}: an empty generated block"


def test_every_prompt_the_generator_names_exists():
    """A missing prompt fails at the ask, after the model has been loaded --
    eleven seconds and 4.7 GB later. Cheaper to find out here."""
    from tools.llm import augment_content as content
    from tools.llm.client import prompt

    for name in set(content.PROMPTS.values()) | {content.DEFAULT_PROMPT}:
        assert prompt(name).strip(), name


def test_every_generatable_family_has_a_vietnamese_description():
    """Asking the model for `shops_market` by its file name gets file-name
    shaped nonsense back, so a stem with no description must stop the run."""
    from tools.llm import augment_content as content

    for stem in content.SUBJECTS:
        assert rules.shape_of(stem)          # the family is measured
        assert content.subject_for(stem)     # and it is asked for in Vietnamese
    with pytest.raises(SystemExit, match="no Vietnamese description"):
        content.subject_for("items_nonesuch")


# ------------------------------------------------------- the layout schema


def test_the_schema_accepts_every_hand_written_layout():
    """The same rule as the corpus audit, and it failed the same way twice:
    once on `đ` not decomposing under NFD, once on the em dash that every
    layout's `name:` carries. A schema that rejects a committed layout is a
    broken schema."""
    import yaml

    schema = layout_schema.derive()
    for path in sorted(layout_schema.LAYOUTS_ROOT.glob("*.yaml")):
        if layout_schema.is_generated(path):
            continue
        layout = yaml.safe_load(path.read_text(encoding="utf-8"))
        problems = (layout_schema.check(layout, schema)
                    + layout_schema.ranges(layout)
                    + [f"missing {k}" for k in layout_schema.missing(layout)])
        assert problems == [], f"{path.stem}: {problems[:3]}"


def test_a_generated_layout_cannot_widen_the_schema():
    """Otherwise the second variant is checked against the first one's
    mistakes -- the same drift the corpus envelope avoids."""
    files = [p for p in layout_schema.LAYOUTS_ROOT.glob("*.yaml")]
    hand = [p for p in files if not layout_schema.is_generated(p)]
    assert len(hand) < len(files) or len(hand) == len(files)
    assert layout_schema.derive() == layout_schema.derive(include_generated=False)


def test_an_unknown_key_is_reported_with_the_key_it_resembles():
    problems = layout_schema.check({"rule_charr": "-"})
    assert problems and "no layout has this key" in problems[0]
    assert "rule_char" in problems[0]


def test_a_reversed_range_is_caught_before_anything_is_built():
    """`width: [48, 42]` is `ValueError: empty range for randrange()` on every
    seed. The build step catches it -- after six subprocesses. This is the same
    failure for the price of a comparison, and it is what the first generated
    variant actually did."""
    assert layout_schema.ranges({"width": [48, 42]})
    assert layout_schema.ranges({"width": [42, 48]}) == []
    assert layout_schema.ranges({"header": {"name_scale": [1.5, 1.2]}})


def test_every_committed_numeric_pair_ascends():
    """The measurement the rule above rests on: 59 pairs, none descending, so
    there is no legitimate reversed range to reject by mistake."""
    import yaml

    for path in sorted(layout_schema.LAYOUTS_ROOT.glob("*.yaml")):
        layout = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert layout_schema.ranges(layout) == [], path.stem


def test_an_enum_value_outside_the_observed_set_is_refused():
    """`align` is left|center|right and nothing else. A model writing `centre`
    should be told, not silently ignored by the builder."""
    problems = layout_schema.check({"columns": [{"align": "centre"}]})
    assert problems and "is not one of" in problems[0]
    assert layout_schema.check({"columns": [{"align": "center"}]}) == []


def test_the_charset_is_measured_rather_than_listed():
    """A hand-written list of "characters a layout uses" rejected all seventeen
    on the em dash in `name:`."""
    marks = layout_schema.charset(layout_schema.derive())
    assert "—" in marks, "every layout's name: carries one"
    assert layout_schema.check({"name": "Siêu thị — hoá đơn GTGT"}) == []
    assert layout_schema.check({"name": "Siêu thị 🧾 hoá đơn"})
