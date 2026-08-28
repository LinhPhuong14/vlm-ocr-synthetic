"""The metadata line's shape, and the two things that would silently rot it.

`pipeline/record.py` had no test of its own while it was five keys and a
validator. It is the converter's schema now -- thirteen keys, a label
vocabulary, a derived markdown and an id that has to come out the same twice --
and three of those are the kind of thing that breaks without anybody noticing:

* **the label vocabulary.** A new field kind falls through to `Text` and the
  dataset still loads. So every kind in every committed dataset is walked
  through `label_for` here, and one that lands on the fallback fails.
* **the id.** `job_id` is a uuid5 because `metadata.jsonl` is hashed; a uuid4
  would make every run differ from every other and nobody would see it until
  `make baseline-verify` went red for no reason anyone could name.
* **the committed datasets.** They are the first thing the README tells a
  reader to look at, so they are validated here rather than assumed.

Nothing below renders an image, so this runs in the dependency-free CI job.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import record as R

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA = REPO_ROOT / "data"

QUAD = [[10, 20], [110, 20], [110, 60], [10, 60]]


def a_box(kind="store.name", text="NHA HANG", quad=None):
    return {"kind": kind, "text": text, "quad": quad or QUAD}


def a_record(**changes):
    fields = dict(filename="html_000.jpg", width=800, height=1200, parser="html",
                  layout="eatery_ascii", seed=7, boxes=[a_box()],
                  extracted={"store": {"name": "NHA HANG"}})
    fields.update(changes)
    return R.build(**fields)


# --------------------------------------------------------------- the envelope


def test_a_built_record_is_the_converters_shape():
    item = a_record()
    assert list(item) == list(R.ORDER)
    assert item["schema_version"] == R.SCHEMA_VERSION
    assert item["task"] == "convert"
    assert item["source_files"] == [item["filename"]]
    assert item["documents"] == []
    assert item["pages"] == [{"page_number": 1, "width": 800, "height": 1200,
                              "source_file": "", "document_index": None, "html": ""}]
    assert not R.validate(item)


def test_the_settings_describe_the_page_that_was_drawn():
    item = a_record()
    assert item["settings"]["convert_mode"] == "html"
    # No cap was applied -- the page was drawn at the size it is, and that size
    # is in `pages[0]` rather than restated here as if it were a limit.
    assert item["settings"]["max_pixels"] is None
    # `extract_fields` names what `extracted` actually carries, rather than
    # being empty because nothing in particular was asked for.
    assert item["settings"]["extract_fields"] == ["store.name"]
    assert set(item["settings"]) == set(R.BASE_SETTINGS)


def test_how_the_page_was_made_is_not_in_the_line():
    """The whole point of the shape: a line is what a converter would return.

    The seed, the attributes and the reading order are in `synthesis.json`, and
    a record that grew a key for any of them is rejected rather than tolerated
    -- a schema nobody enforces is a schema that drifts back.
    """
    item = a_record()
    assert set(item) == set(R.ORDER)
    for key in ("synthesis", "recipe", "text_sequence", "layout", "framework"):
        assert key not in item

    item["synthesis"] = {"recipe": {"seed": 7}}
    problems = R.validate(item)
    assert any("not in the converter's schema" in problem for problem in problems), problems


# ------------------------------------------------------------------ the label


@pytest.mark.parametrize("kind,label", [
    ("title", "Title"),
    ("subtitle", "Section-header"),
    ("store.name", "Page-header"),
    # A `.label` half follows its own family without being listed for it.
    ("store.address.label", "Page-header"),
    ("total.grand.label", "Table"),
    ("menu.unit_price", "Table"),
    ("footer", "Page-footer"),
])
def test_a_kind_lands_on_the_label_its_family_says(kind, label):
    assert R.label_for(kind) == label


def test_every_label_is_one_the_converter_knows():
    assert set(R.LABELS.values()) <= R.PAGE_LABELS
    assert R.DEFAULT_LABEL in R.PAGE_LABELS


def test_every_kind_in_every_committed_dataset_is_mapped():
    """The one that catches a field kind added without a label.

    An unmapped kind is not an error at render time -- a shard must not die
    halfway through a run over a label vocabulary -- so this is where it is
    caught instead. If this fails, add the kind to `LABELS`; do not widen the
    fallback.
    """
    unmapped: dict[str, str] = {}
    seen = 0
    for directory in page_directories():
        for item in R.read(directory):
            for block in R.boxes(item):
                kind = str(block.get("kind", ""))
                seen += 1
                if kind and R.label_for(kind) == R.DEFAULT_LABEL:
                    # `Text` is a real answer for some kinds; only a kind that
                    # matches no prefix at all is a hole.
                    if not any(kind == p or kind.startswith(p) for p in R.LABELS):
                        unmapped[kind] = str(directory.relative_to(REPO_ROOT))
    assert seen, "no committed dataset to check against"
    assert unmapped == {}


# --------------------------------------------------------------- the geometry


def test_a_bbox_is_the_hull_of_a_quad_and_does_not_replace_it():
    """The glyph backend curls the paper, so a bbox cannot be the whole story."""
    curled = [[10, 25], [110, 20], [112, 62], [8, 60]]
    block = R.blocks_from_boxes([a_box(quad=curled)])[0]
    assert block["bbox"] == {"x1": 8, "y1": 20, "x2": 112, "y2": 62}
    assert block["quad"] == curled


def test_a_block_keeps_the_field_it_is_as_well_as_the_class_it_is_in():
    block = R.blocks_from_boxes([a_box(kind="total.grand", text="232,000")])[0]
    assert block["label"] == "Table"          # what the converter calls it
    assert block["kind"] == "total.grand"     # which field it actually is
    assert block["text"] == "232,000"
    assert block["id"] == "p1-b0" and block["index_in_page"] == 0


# --------------------------------------------------------------- the markdown


def line(x1, y1, x2, y2, text, kind="menu.name"):
    return {"kind": kind, "text": text,
            "quad": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]]}


def test_a_printed_line_is_one_markdown_line_not_three():
    """Three boxes on one row are a receipt line, not a column of three."""
    blocks = R.blocks_from_boxes([
        line(60, 350, 90, 380, "1", "menu.qty"),
        line(110, 350, 620, 380, "CA LOC CHIEN MAM XOAI"),
        line(780, 350, 930, 380, "58,000", "menu.amount"),
    ])
    assert R.markdown_of(blocks) == "1  CA LOC CHIEN MAM XOAI  58,000"


def test_the_markdown_reads_down_the_page_not_in_the_order_it_was_drawn():
    """A form draws its left column then its right; the page prints them paired."""
    blocks = R.blocks_from_boxes([
        line(40, 100, 300, 130, "Họ tên: Chu Văn Lâm", "invoice.field"),
        line(40, 160, 300, 190, "Địa chỉ: 77 Nguyễn Chí Thanh", "invoice.field"),
        line(600, 100, 900, 130, "Ngày sinh: 10/02/1960", "invoice.field"),
        line(600, 160, 900, 190, "Giới tính: 2", "invoice.field"),
    ])
    assert R.markdown_of(blocks).split("\n\n") == [
        "Họ tên: Chu Văn Lâm  Ngày sinh: 10/02/1960",
        "Địa chỉ: 77 Nguyễn Chí Thanh  Giới tính: 2",
    ]


def test_a_heading_is_marked_as_one_and_never_joins_the_line_beside_it():
    blocks = R.blocks_from_boxes([
        line(300, 100, 700, 140, "HOÁ ĐƠN GIÁ TRỊ GIA TĂNG", "title"),
        line(750, 105, 900, 135, "Ngày 25/03/2019", "invoice.field"),
    ])
    assert R.markdown_of(blocks).split("\n\n") == [
        "# HOÁ ĐƠN GIÁ TRỊ GIA TĂNG", "Ngày 25/03/2019"]
    assert R.html_of(blocks).startswith("<h1>HOÁ ĐƠN GIÁ TRỊ GIA TĂNG</h1>")


def test_a_block_that_printed_nothing_is_in_no_line():
    blocks = R.blocks_from_boxes([line(40, 100, 300, 130, "  ", "note"),
                                  line(40, 160, 300, 190, "CAM ON", "footer")])
    assert R.markdown_of(blocks) == "CAM ON"


def test_the_html_escapes_what_it_prints():
    blocks = R.blocks_from_boxes([line(40, 100, 300, 130, "A & B <C>", "note")])
    assert R.html_of(blocks).strip() == "<p>A &amp; B &lt;C&gt;</p>"


# --------------------------------------------------------------------- the id


def test_the_same_page_gets_the_same_id_twice():
    """A uuid4 here would make every run differ from every other run."""
    assert a_record()["job_id"] == a_record()["job_id"]


@pytest.mark.parametrize("change", [
    {"parser": "genalog"},
    {"layout": "market_vat"},
    {"filename": "html_001.jpg"},
    {"seed": 8},
])
def test_the_id_moves_when_what_it_names_moves(change):
    assert a_record(**change)["job_id"] != a_record()["job_id"]


def test_stamping_a_page_moves_every_field_that_follows_its_name():
    """What a shard does when it moves a page out of staging."""
    item = a_record()
    before = item["job_id"]

    R.stamp(item, parser="genalog", layout="market_vat", seed=9,
            filename="genalog_007.jpg")
    assert item["filename"] == "genalog_007.jpg"
    assert item["source_files"] == ["genalog_007.jpg"]
    assert item["parser"] == "genalog"
    assert item["settings"]["convert_mode"] == "genalog"
    assert item["job_id"] == R.job_id("genalog", "market_vat", 9, "genalog_007.jpg")
    assert item["job_id"] != before
    assert R.validate(item) == []


# -------------------------------------------------------------- the validator


@pytest.mark.parametrize("break_it,expected", [
    (lambda i: i.update(schema_version=7), "schema_version must be 8"),
    (lambda i: i.update(filename="/tmp/x.jpg"), "must be relative"),
    (lambda i: i.update(source_files=["other.jpg"]), "source_files must be exactly"),
    (lambda i: i.update(pages=[]), "exactly one page"),
    (lambda i: i["pages"][0].update(width=0), "no size"),
    (lambda i: i.update(extracted=None), "extracted must be the nested label"),
    (lambda i: i.update(parser=""), "parser is empty"),
    (lambda i: i.update(synthesis={}), "not in the converter's schema"),
    (lambda i: i.pop("markdown"), "missing key 'markdown'"),
    (lambda i: i["blocks"][0].pop("quad"), "blocks[0] needs"),
    (lambda i: i["blocks"][0].update(quad=[[0, 0]]), "must be four corners"),
    (lambda i: i["blocks"][0].update(bbox={"x1": 0}), "bbox needs"),
    # `settings` was described as exact and never checked. These four are the
    # ways it can be wrong, and the first is the one that actually happened.
    (lambda i: i["settings"].update(max_pixels=800 * 1200), "settings.max_pixels"),
    (lambda i: i["settings"].pop("retry_repeat"), "settings is missing"),
    (lambda i: i["settings"].update(dpi=300), "not one of the converter's"),
    (lambda i: i["settings"].update(convert_mode="genalog"), "must be the parser"),
    # `False == 0` in Python, so a value check alone would let this through and
    # the record would claim a flag it does not have.
    (lambda i: i["settings"].update(end2end=0), "settings.end2end"),
])
def test_a_record_that_would_break_a_loader_is_named(break_it, expected):
    item = a_record()
    break_it(item)
    problems = R.validate(item)
    assert any(expected in problem for problem in problems), problems


def test_a_record_is_written_beside_its_image_and_named_after_it(tmp_path):
    """One file per page, so the images are the listing and nothing else is."""
    for name in ("html_000.jpg", "html_001.jpg"):
        (tmp_path / name).write_bytes(b"pretend jpeg")
    assert R.write([a_record(), a_record(filename="html_001.jpg")], tmp_path) == 2

    assert (tmp_path / "html_000.json").exists()
    assert (tmp_path / "html_001.json").exists()
    assert R.read_one(tmp_path / "html_000.jpg") == a_record()

    back = R.read(tmp_path)
    assert [R.file_name(item) for item in back] == ["html_000.jpg", "html_001.jpg"]

    # A file nothing is named after is not a record, however much it looks like
    # one -- which is what lets `synthesis.json` share the directory.
    (tmp_path / "synthesis.json").write_text("{}", encoding="utf-8")
    assert len(R.read(tmp_path)) == 2


def test_an_image_with_no_record_stops_a_read_rather_than_being_skipped(tmp_path):
    """A dataset that is quietly short is the failure the shard exists to stop."""
    (tmp_path / "html_000.jpg").write_bytes(b"pretend jpeg")
    R.write_one(a_record(), tmp_path)
    (tmp_path / "html_001.jpg").write_bytes(b"pretend jpeg")

    with pytest.raises(R.RecordError, match="html_001.jpg has no html_001.json"):
        R.read(tmp_path)


def test_writing_a_bad_record_raises_rather_than_writing_it(tmp_path):
    with pytest.raises(R.RecordError):
        R.write([a_record(extracted=None)], tmp_path)
    assert not list(tmp_path.glob("*.json"))


# --------------------------------------------------------- what is committed


def page_directories():
    """Every committed directory of drawn pages.

    A directory of pages is one with a `synthesis.json` in it -- which is what
    tells `data/dataset60/html/` apart from `data/dataset60/proof/`, whose
    images are Tesseract's working, not the generator's output.

    `.shards/` is skipped. It is a run's own working state, gitignored, and
    holds a second copy of every image; counting it would put the census
    hundreds ahead on the machine that did the rendering and nowhere else --
    a test that passes on CI and fails for its author, for no reason either
    could see.
    """
    return sorted(path.parent for path in DATA.rglob("synthesis.json")
                  if ".shards" not in path.parts)


def test_every_committed_page_has_a_record_in_the_shape_this_file_defines():
    """`cat data/dataset60/html/html_000.json` is the README's first example."""
    directories = page_directories()
    assert directories, "no committed dataset to check"
    seen = 0
    for directory in directories:
        for image in R.images(directory):
            path = R.beside(image)
            where = str(image.relative_to(REPO_ROOT))
            assert path.exists(), f"{where} has no record beside it"
            assert R.validate(json.loads(path.read_text(encoding="utf-8"))) == [], where
            seen += 1
    # A census, so it moves whenever a committed set is rebuilt -- and it is
    # meant to: a set that quietly lost half its pages would otherwise look
    # like a passing test. 294 = 307 before `data/dataset_test` was rebuilt on
    # the CSS sheets, which took it from 30 images over two renderers to 16,
    # one per layout, on the only backend the pipeline still drives.
    #
    # 2278 = the 278 that were already here plus the first two 1000-page batches
    # of `data/5k_llm`; it reaches 5278 when the last one lands. The
    # 278 is not 294 and was not 294 before this set arrived: the older figure
    # is 16 pages ahead of what is committed, on a tree with nothing modified
    # under `data/`. Left as found rather than folded into this number -- which
    # of the two is wrong is a question about those sets, not about this one.
    assert seen == 2278, seen


# ------------------------------------------------------- the shape before this

def _jpeg(width: int, height: int) -> bytes:
    """A JPEG header and nothing else -- `jpeg_size` reads no further.

    Hand-built so this test needs no imaging library, for the same reason
    `invariants.jpeg_size` reads the header itself: the dependency-free CI job
    has to be able to run it.
    """
    import struct

    sof = b"\xff\xc0" + struct.pack(">HBHHB", 17, 8, height, width, 3) + b"\x00" * 9
    return b"\xff\xd8" + sof + b"\xff\xd9"


def _old_line(name: str) -> dict:
    return {
        "file_name": name,
        "ground_truth": json.dumps({"gt_parse": {"store": {"name": "Hoà Bình"}}},
                                   ensure_ascii=False),
        "text_sequence": "Hoà Bình",
        "recipe": {"seed": 7, "attributes": {
            "layout": {"id": "invoice_vat_form", "params": {}, "tags": []}}},
        "boxes": [{"kind": "store.name", "text": "Hoà Bình",
                   "quad": [[10, 10], [90, 10], [90, 30], [10, 30]]}],
        "handwriting": {"source": "font", "inked": [], "printed": {}},
    }


def test_migrate_splits_an_old_index_into_a_record_per_image(tmp_path):
    """The old shape is still readable, and it is readable HERE.

    `metadata.jsonl` -- one index for a whole set, the renderer's own keys, the
    recipe repeated per line -- is what every dataset under `data/` was written
    in before this module followed the converter's schema. Converting it lives
    beside `build` rather than in a tool of its own so that a record has exactly
    one definition and both callers reach it: a renderer with pixels in hand,
    and this, with an old line in hand.
    """
    from pipeline import record, synthesis

    directory = tmp_path / "html"
    directory.mkdir()
    for index in range(2):
        name = f"html_{index:03d}.jpg"
        (directory / name).write_bytes(_jpeg(1020, 2652))
    (directory / "metadata.jsonl").write_text(
        "\n".join(json.dumps(_old_line(f"html_{i:03d}.jpg")) for i in range(2)),
        encoding="utf-8")

    assert record.migrate(tmp_path) == (2, 1)

    # One record per image, in the converter's schema, and the index is gone --
    # leaving it would leave a second answer to the same question, and the
    # stale one still parses.
    assert not (directory / "metadata.jsonl").exists()
    records = record.read(directory)
    assert len(records) == 2
    assert records[0]["schema_version"] == record.SCHEMA_VERSION
    assert record.file_name(records[0]) == "html_000.jpg"
    assert records[0]["pages"][0]["width"] == 1020

    # ...and how the page was made is in one file for the set, not in each line.
    made = synthesis.read(directory)
    assert len(made) == 2 and "html_000.jpg" in made
    page = made.entry("html_000.jpg")
    assert page["seed"] == 7
    assert page["layout"] == "invoice_vat_form"
    assert page["handwriting"]["source"] == "font"
    # The recipe goes back in the shape it came out: ids in the page, params
    # once for the set, and `recipe()` folds them together again.
    assert made.recipe("html_000.jpg")["attributes"]["layout"]["id"] == "invoice_vat_form"

    # Running it again is a no-op: there is no index left to convert.
    assert record.migrate(tmp_path) == (0, 0)


def test_a_page_size_left_in_max_pixels_is_named_for_what_it_is():
    """The drift, in the shape it had on disk.

    `settings.max_pixels` held the page's own pixel count until it was made
    null -- it is a *cap*, none was applied, and the size is already in
    `pages[0]`. 295 records written before that kept the old value, so the data
    described a cap the generator had stopped applying and no test said so,
    because `validate` walked every top-level key and never looked inside
    `settings`. It looks now.
    """
    item = a_record()
    item["settings"]["max_pixels"] = 800 * 1200
    problems = R.validate(item)
    assert len(problems) == 1
    assert "settings.max_pixels must be None, got 960000" in problems[0]


def test_refresh_moves_a_constant_option_and_leaves_the_rest_alone():
    """Bringing a record forward is not re-rendering it.

    The pixels never moved -- only what the record claimed about them -- so a
    stale option is fixed by rewriting one value, and everything a renderer
    put there stays exactly as it was.
    """
    item = a_record()
    before = json.dumps(item, sort_keys=True)
    item["settings"]["max_pixels"] = 800 * 1200

    assert R.refresh(item) is True
    assert item["settings"]["max_pixels"] is None
    assert json.dumps(item, sort_keys=True) == before
    assert R.validate(item) == []

    # Idempotent, which is what lets a caller run it over a whole tree and
    # leave the files it would rewrite byte for byte alone.
    assert R.refresh(item) is False


def test_refresh_leaves_the_two_options_that_differ_per_page():
    """`convert_mode` names the renderer and `extract_fields` names the label.

    Resetting either to the constant would make every record in a set claim the
    same renderer and the same fields, which is the opposite of the point.
    """
    item = a_record(parser="genalog")
    assert item["settings"]["convert_mode"] == "genalog"
    assert item["settings"]["extract_fields"] == ["store.name"]

    assert R.refresh(item) is False
    assert item["settings"]["convert_mode"] == "genalog"
    assert item["settings"]["extract_fields"] == ["store.name"]


def test_migrate_brings_a_stale_option_forward_without_touching_the_image(tmp_path):
    """The second thing that can be out of date about a set.

    The first is its *shape* -- one index instead of a record per image. This
    is a set already in the right shape, written when a constant option meant
    something else, which is every committed set as of this commit. There is no
    index to find it by, so `migrate` walks the images too.
    """
    directory = tmp_path / "html"
    directory.mkdir()
    pixels = _jpeg(800, 1200)
    (directory / "html_000.jpg").write_bytes(pixels)
    item = a_record()
    item["settings"]["max_pixels"] = 800 * 1200
    (directory / "html_000.json").write_text(json.dumps(item, ensure_ascii=False),
                                             encoding="utf-8")

    assert R.migrate(tmp_path, write=False) == (1, 1)
    # A dry run reports and writes nothing.
    assert json.loads((directory / "html_000.json").read_text(
        encoding="utf-8"))["settings"]["max_pixels"] == 960000

    assert R.migrate(tmp_path) == (1, 1)
    brought = R.read_one(directory / "html_000.json")
    assert brought["settings"]["max_pixels"] is None
    assert R.validate(brought) == []
    # Nothing was re-rendered: the image is the same bytes it was.
    assert (directory / "html_000.jpg").read_bytes() == pixels

    assert R.migrate(tmp_path) == (0, 0)


def test_migrate_writes_beside_the_image_when_the_record_names_a_subdirectory(tmp_path):
    """`generators/html/tables.py` keeps its pages in `img/` and says so.

    Its records carry `img/border_0001.jpg` as the filename, not a bare name.
    Resolving that against the image's own directory writes
    `img/img/border_0001.json` -- a second record for a page that already had
    one, and the original left stale. All 60 of them landed there first.
    """
    directory = tmp_path / "tables" / "img"
    directory.mkdir(parents=True)
    (directory / "border_0001.jpg").write_bytes(_jpeg(800, 1200))
    item = a_record(filename="img/border_0001.jpg")
    item["settings"]["max_pixels"] = 800 * 1200
    (directory / "border_0001.json").write_text(json.dumps(item, ensure_ascii=False),
                                                encoding="utf-8")

    assert R.migrate(tmp_path) == (1, 1)

    assert not (directory / "img").exists()
    brought = R.read_one(directory / "border_0001.json")
    assert brought["settings"]["max_pixels"] is None
    assert R.file_name(brought) == "img/border_0001.jpg"
