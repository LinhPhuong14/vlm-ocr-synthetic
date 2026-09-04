"""The shape of one page's record, checked where it is written.

    data/dataset60/html/
        html_000.jpg     html_000.json
        html_001.jpg     html_001.json
        …                synthesis.json

**One file per image, not one index for the set.** A converted page comes back
as one document about one file, so that is what is written here: the record has
the image's name with a `.json` suffix and sits next to it. The images are
therefore the listing -- nothing has to be told which files in a directory are
records, an image with no record beside it is an error `read` raises rather than
skips, and a single page can be handed to somebody without shipping the index of
a set they do not have.

Each renderer builds its own dict, so a key can drift in one of the three and
nothing says so until somebody loads the dataset and finds a field missing for a
fifth of it. This is the one definition: `build` assembles a record, `validate`
is called on the way out, and every reader goes through the accessors at the
bottom rather than reaching for a key by name.

**The shape is the converter's, and only the converter's.** A page produced
here is meant to stand in for a page that came back from the document converter,
so a line carries what a converted line carries and nothing else:

    schema_version  8 -- the converter's schema this shape follows
    job_id          uuid5 of parser|layout|seed|filename: same page, same id
    task            what produced the record: `convert`, or `table_structure`
    parser          which renderer drew it (was `framework`)
    filename        the image, relative to the backend's directory
    source_files    what the job was given; one drawn page, so `[filename]`
    settings        the job's options, spelled as the converter spells them
    documents       segmentation, which a single drawn page has none of: `[]`
    pages           one entry: page number, pixel size, and the sample's blanks
    blocks          one per drawn field, in reading order (was `boxes`)
    markdown        the page as markdown, built from the blocks
    html            the same, as HTML
    extracted       the CORD-style nested label as an object (was `ground_truth`)

**How the page was made is not in here.** The seed, the six sampled attributes
and their params, the flat reading order: none of that is something a converter
could return, and most of it is the same text on every page of a run --
`ornament` and `augmentation` describe a *background*, and twenty pages sharing
one chain wrote that chain out twenty times. It lives in `synthesis.json` in the same
directory instead, params written once per option id, joined back to a page by
its `job_id` or its file name -- one file for the set, because it is a statement
about the set. `pipeline/synthesis.py` is that file, and
`Synthesis.recipe()` hands back exactly the `recipe.to_dict()` the rule-base
produced.

**Why a block keeps `kind`, `text` and `quad` beside `label`, `bbox` and
`content`.** The converter's block is a region of a page and its label is one of
eleven layout classes; this generator's box is one *field* and its kind names
which field (`total.grand.label`, `menu.qty`). Collapsing the second into the
first would throw away what every check in `pipeline/invariants.py` is written
against, and `bbox` cannot hold a quad that follows a curl in the paper -- the
glyph backend draws those, and `tools/check_boxes.py` reads them. So both are
written: `label`/`bbox`/`content` for a converter-shaped consumer, and
`kind`/`text`/`quad` for everything in this repository. `label` is derived from
`kind` by `label_for`, once, here.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path
from typing import Any, Iterable

# The converter schema these records follow. Bumped only when the converter's
# own schema is, which is why it is a number copied from it rather than one this
# repository owns.
SCHEMA_VERSION = 8

# What produced the record. A drawn document page is a `convert` job; a table
# image is a `table_structure` one, and `generators/html/tables.py` says so --
# their labels are different things and flattening one into the other would lie.
TASK_CONVERT = "convert"
TASK_TABLE = "table_structure"

# `job_id` is a uuid5 rather than a uuid4 because `metadata.jsonl` is hashed:
# `tools/baseline.py` compares every line of a run against a captured one, so a
# random id would make every verification fail and every dataset unreproducible.
# uuid5 of the four things that decide what the page *is* -- see `job_id`.
JOB_NAMESPACE = uuid.UUID("29ede217-1783-5493-a680-21290a740c52")

# --------------------------------------------------------------- block labels

# The converter's layout vocabulary, which is DocLayNet's. Fixed by what reads
# these records, not by this repository: a twelfth label here would be one no
# consumer has a class for. `label_for` may only return one of these, and
# `tests/test_record.py` checks that it does.
PAGE_LABELS = frozenset({
    "Caption", "Footnote", "Formula", "List-item", "Page-footer", "Page-header",
    "Picture", "Section-header", "Table", "Text", "Title",
})

# kind prefix -> the converter's layout label. Longest prefix wins, so
# `total.grand.label` follows `total.` and `store.address.label` follows
# `store.` without either being listed. `tests/test_record.py` walks every kind
# in every committed dataset through `label_for` and fails on one that lands on
# the fallback, which is what stops a new field kind from being labelled `Text`
# by accident.
LABELS: dict[str, str] = {
    "title": "Title",
    "subtitle": "Section-header",
    "parties.title": "Section-header",
    "store.": "Page-header",
    "invoice.subtitle": "Section-header",
    "invoice.": "Text",
    "menu.": "Table",
    "colhdr": "Table",
    "colnum": "Table",
    "total.": "Table",
    "summary.": "Table",
    "period": "Text",
    "meta": "Text",
    "note": "Text",
    "sign.": "Text",
    "footer": "Page-footer",
    "cell": "Table",
    # A struck seal is ink, not running text -- `Picture` is the closest thing
    # the converter's own vocabulary has to "not words". See
    # `generators/html/sheets/base.py::seal_mark`.
    "seal.": "Picture",
    # The party block of an invoice. `parties.title` above is the section
    # heading ("THÔNG TIN CÁC BÊN"); everything else under it -- the per-side
    # titles and the field labels -- is running text. Longest prefix wins, so
    # this does not take the heading back.
    "parties.": "Text",

    # ----------------------------------------------------------------------
    # The periodical family: newspapers, magazines, classifieds.
    #
    # These 65 kinds went UNMAPPED for as long as no committed dataset held a
    # periodical page -- the layouts shipped, the fallback quietly labelled
    # every field `Text`, and `test_every_kind_in_every_committed_dataset_is_mapped`
    # had nothing to walk. `data/layouts84` is the first set that draws all 42
    # layouts, which is what turned the hole into a failing test.
    "masthead": "Title",
    "issue_": "Page-header",           # issue_label, issue_no, issue_date
    "slogan": "Page-header",
    "price": "Page-header",            # the cover price, beside the masthead
    "website": "Page-footer",
    "hotline": "Page-footer",
    "page_no": "Page-footer",
    # The lead story, and the ones below the fold.
    "headline": "Title",
    "hero.headline": "Title",
    "hero.kicker": "Section-header",
    "hero.": "Text",                   # byline, teaser, page_no
    "kicker": "Section-header",
    "deck": "Section-header",
    "dateline": "Text",
    "byline": "Text",                  # byline, byline_by, byline_photo
    "body": "Text",
    "jump": "Text",                    # "xem tiếp trang 4"
    "pull_quote": "Text",
    "caption": "Caption",
    "bottom.headline": "Section-header",
    "bottom.caption": "Caption",
    "bottom.": "Text",
    "teaser.kicker": "Section-header",
    "teaser.headline": "Section-header",
    "teaser.": "Text",
    "section": "Section-header",       # section, section.name
    "category": "Section-header",
    # A magazine's table of contents is a LIST, not running text: each entry is
    # a title, a teaser and the page it is on. `List-item` is the one label in
    # the converter's vocabulary that says so.
    "entry.": "List-item",
    # The interview.
    "qa.question": "Section-header",
    "qa.answer": "Text",
    "subject_": "Text",                # subject_name, subject_role
    "bio_title": "Section-header",
    "bio.": "Text",
    "sidebar.title": "Section-header",
    "sidebar.": "Text",
    # Classifieds: small ads, official notices, obituaries.
    "ad.heading": "Section-header",
    "ad.": "Text",
    "notice.title": "Section-header",
    "notice.": "Text",
    "obit.title": "Section-header",
    "obit.": "Text",
    "condolence": "Text",
    "rate": "Text",                    # the line-rate card at the foot
}

# What a kind nobody has mapped becomes. Deliberately the converter's most
# generic label rather than an error: an unmapped kind must not stop a shard
# halfway through a run. `tests/test_record.py` is where it is caught instead.
DEFAULT_LABEL = "Text"

# Labels that own a whole line of the page, so they are never joined with the
# block beside them when the markdown is built.
STANDALONE = {"Title", "Section-header", "Picture"}

# Labels to a markdown prefix. Everything not listed is written as it stands.
MARKDOWN_PREFIX = {"Title": "# ", "Section-header": "## "}

# The HTML element vocabulary the converter's own HTML consumer accepts.
# `HTML_TAG` below may only pick from here -- checked by
# `test_every_html_tag_is_one_the_converter_allows` rather than left as a
# comment, so a future label cannot quietly pick a tag nothing downstream
# renders.
ALLOWED_TAGS = frozenset({
    "math", "br", "i", "b", "u", "del", "sup", "sub", "table", "tr", "td",
    "p", "th", "div", "pre", "h1", "h2", "h3", "h4", "h5", "ul", "ol", "li",
    "input", "a", "span", "img", "hr", "tbody", "small", "caption", "strong",
    "thead", "big", "code", "chem",
})

# ...and to the HTML element that holds it. The tag names the box's ROLE on
# the page -- what a heading, a footnote, a formula *are* -- never what the
# box happens to say; two "Text" blocks with unrelated content still both get
# `<p>`. `Page-header` and `Page-footer` are page furniture rather than prose,
# not `<p>` with running text, and `ALLOWED_TAGS` has no `<header>`/`<footer>`
# to give them instead, so they get the generic block container, `<div>`.
# Every label in `PAGE_LABELS` has an entry here now, so nothing falls through
# to the `.get(..., "p")` fallback below by accident.
HTML_TAG = {
    "Title": "h1",
    "Section-header": "h2",
    "Caption": "caption",
    "Footnote": "small",
    "Formula": "math",
    "List-item": "li",
    "Page-header": "div",
    "Page-footer": "div",
    "Picture": "div",
    "Table": "table",
    "Text": "p",
}

# ---------------------------------------------------------- docsynth labels
#
# `word_annotations`/`layout_annotations` (below `boxes`/`blocks_from_boxes`)
# write `layout_class` in a SECOND, wider vocabulary -- `docsynth.
# annotations.v1`'s 19 labels, fixed by what reads those two arrays, not by
# this repository. Kept separate from `PAGE_LABELS`/`LABELS` above rather
# than replacing them: those two already carry a lot of judgment about which
# `kind` prefix wins and where -- the periodical family alone maps 65 of
# them -- and redoing that BY HAND against a different vocabulary would be
# throwing that judgment away to re-derive it, not improving it. Translating
# the label `label_for` already computes is cheaper and just as faithful:
# every existing reader of `label_for`/`blocks[]` sees no change at all.
DOCSYNTH_LABELS = frozenset({
    "Caption", "Footnote", "Equation-Block", "List-Group", "Page-Header",
    "Page-Footer", "Image", "Section-Header", "Table", "Text",
    "Complex-Block", "Code-Block", "Form", "Table-Of-Contents", "Figure",
    "Chemical-Block", "Diagram", "Bibliography", "Blank-Page",
})

# kind prefix -> `docsynth.annotations.v1` label, DIRECTLY -- not through
# `label_for`/`PAGE_LABELS`. That two-hop version (kind -> old 11-label ->
# new 19-label) was cheaper to write, but it can only ever hand back
# whichever of the 19 the OLD label happened to translate to, one per old
# label, even when a `kind` deserves a more specific one the eleven-label
# vocabulary had no slot for -- a magazine's `entry.` (its table of
# contents) is `List-item` there and would translate to the generic
# `List-Group`, when the vocabulary has an exact name for what it is:
# `Table-Of-Contents`. This table is seeded from the same prefixes `LABELS`
# already carries -- the judgment about which KIND belongs to which GROUP is
# not redone -- with the target chosen against the 19 directly, prefix by
# prefix, instead of inherited from a different vocabulary's answer.
#
# Same rule as `LABELS`: longest prefix wins. A `kind` this does not cover
# reads as `Text`, `layout_class_for`'s own default -- most of what a
# Vietnamese business document says IS running text, and the eight labels
# actually used below (`Caption`, `Image`, `Page-Footer`, `Page-Header`,
# `Section-Header`, `Table`, `Table-Of-Contents`, `Text`) are what this
# repository's content actually is; the other eleven (`Equation-Block`,
# `Chemical-Block`, `Bibliography`, ...) name things no layout here draws,
# and forcing a `kind` onto one of them would be a label lying about the
# page, not a use of the vocabulary's breadth.
DOCSYNTH_LABEL_FOR_KIND: dict[str, str] = {
    # A document's own title reads as `Page-Header` here by explicit call:
    # this repository draws one document per page, so "the page's header"
    # and "the document's title" are the same band of ink -- a choice, not
    # the DocLayNet-style reading that would put it under `Section-Header`
    # instead.
    "title": "Page-Header",
    "subtitle": "Section-Header",
    "parties.title": "Section-Header",
    # Only the org's own name is PAGE-HEADER material -- the running
    # identification a reader expects there, terse and repeated on every
    # page of this business regardless of which document it is. Everything
    # else under `store.*` (branch, address, tax code, phone, bank account,
    # website) is substantive contact/legal/bank DATA a downstream reader
    # extracts precisely, the same kind of content `invoice.field`/
    # `parties.*` carry for the other party on the same page -- and those
    # already read as `Text` below. Left as a blanket `"store.":
    # "Page-Header"`, every one of those detail fields inherited the label
    # too, so a header box built from a company's letterhead block ran five
    # lines tall and carried its tax code and bank account number, while the
    # identical fields for the OTHER party on the same page (typed through
    # `invoice.field` instead of `store.*`) correctly read as `Text` -- the
    # same content, labelled two different ways only because of which side
    # of the transaction printed it.
    "store.name": "Page-Header",
    "store.": "Text",
    "invoice.subtitle": "Section-Header",
    "invoice.": "Text",
    "menu.": "Table",
    "colhdr": "Table",
    "colnum": "Table",
    "total.": "Table",
    "summary.": "Table",
    "period": "Text",
    "meta": "Text",
    "note": "Text",
    # A signature line is a field a signer fills in, not running prose --
    # `Form` is the 19-label vocabulary's name for that, and it is the only
    # entry here `Text` would otherwise swallow despite there being a better
    # word for it.
    "sign.": "Form",
    "footer": "Page-Footer",
    "cell": "Table",
    "seal.": "Image",
    # A blank placeholder box standing in for a photo the renderer never
    # actually draws (a portrait for an ID, a product shot) -- its own
    # caption ("ẢNH", "4x6") is the one word this repository ever prints
    # inside that box, so it is what marks the region as `Image` rather than
    # `Text`; nothing else about the box is `span()`-worthy on its own.
    "photo.": "Image",
    "parties.": "Text",
    "masthead": "Section-Header",
    "issue_": "Page-Header",
    "slogan": "Page-Header",
    "price": "Page-Header",
    "website": "Page-Footer",
    "hotline": "Page-Footer",
    "page_no": "Page-Footer",
    "headline": "Section-Header",
    "hero.headline": "Section-Header",
    "hero.kicker": "Section-Header",
    "hero.": "Text",
    "kicker": "Section-Header",
    "deck": "Section-Header",
    "dateline": "Text",
    "byline": "Text",
    "body": "Text",
    "jump": "Text",
    "pull_quote": "Text",
    "caption": "Caption",
    "bottom.headline": "Section-Header",
    "bottom.caption": "Caption",
    "bottom.": "Text",
    "teaser.kicker": "Section-Header",
    "teaser.headline": "Section-Header",
    "teaser.": "Text",
    "section": "Section-Header",
    "category": "Section-Header",
    # A lettered/numbered heading that introduces one block of a page's own
    # body ("A. Thông tin dự án", "I. Bên mua bảo hiểm...") -- a different
    # thing from `section` above, which names a magazine's editorial
    # category, not a heading's own text.
    "subhead": "Section-Header",
    # The one direct improvement over the two-hop version: a real table of
    # contents, not a generic list.
    "entry.": "Table-Of-Contents",
    "qa.question": "Section-Header",
    "qa.answer": "Text",
    "subject_": "Text",
    "bio_title": "Section-Header",
    "bio.": "Text",
    "sidebar.title": "Section-Header",
    "sidebar.": "Text",
    "ad.heading": "Section-Header",
    "ad.": "Text",
    "notice.title": "Section-Header",
    "notice.": "Text",
    "obit.title": "Section-Header",
    "obit.": "Text",
    "condolence": "Text",
    "rate": "Text",
}


def layout_class_for(kind: str) -> str:
    """The `docsynth.annotations.v1` label for one of this repository's field
    kinds, chosen directly against the 19-label vocabulary -- see
    `DOCSYNTH_LABEL_FOR_KIND`'s own comment for why not through `label_for`.
    """
    kind = str(kind or "")
    best = ""
    for prefix in DOCSYNTH_LABEL_FOR_KIND:
        if (kind == prefix or kind.startswith(prefix)) and len(prefix) > len(best):
            best = prefix
    return DOCSYNTH_LABEL_FOR_KIND[best] if best else "Text"

# ------------------------------------------------------------------- settings

# The converter's job options, given the values that are true of a drawn page.
# Spelled out rather than left empty because a consumer that reads `settings`
# reads it on every record, and a missing key there is the same bug as a missing
# key anywhere else. `convert_mode` and `extract_fields` are filled in per page
# by `build` -- they name the renderer that drew it and the label it carries, and
# both differ page to page. The rest are constants and each one is a statement
# about the generator:
#
#   end2end             False -- the label comes from the rule-base, not a model
#   skip_preprocess     True  -- there is nothing to deskew, the page is drawn
#   keep_header_footer  True  -- the label carries them, so they are not dropped
#   convert_mode        the renderer, same value as `parser`
#   retry_repeat        False -- a page is drawn once; a repeat is a bug
#   max_pixels          null -- no cap: the page was drawn at the size it is,
#                       not resized to fit one. Its size is in `pages[0]`
#   segment_document_mode  "single" -- one image, one page, no segmentation
#   segment_output_format  "standard"
#   target_language     Vietnamese; the corpus is, including the folded layouts
#   translate_source    "synthetic" -- not scanned, and saying so matters
BASE_SETTINGS: dict[str, Any] = {
    "end2end": False,
    "skip_preprocess": True,
    "keep_header_footer": True,
    "convert_mode": "",
    "retry_repeat": False,
    "max_pixels": None,
    "segment_document_mode": "single",
    "segment_output_format": "standard",
    "target_language": "Vietnamese",
    "translate_source": "synthetic",
    "extract_fields": [],
}

# The two above that `build` fills in per page. Naming them once means `validate`
# and `refresh` cannot disagree about which options are allowed to differ between
# two records of the same set.
PER_PAGE_SETTINGS = ("convert_mode", "extract_fields")

# Top level, in the order the converter writes them. `json.dump` keeps insertion
# order, so a record built here reads down the page the way the sample does.
ORDER = ("schema_version", "job_id", "task", "parser", "filename", "source_files",
         "settings", "documents", "pages", "blocks", "word_annotations",
         "layout_annotations", "markdown", "html", "extracted")

# Every key, and there is no second set: a line has these and nothing else, so
# a record that grew one is as wrong as a record that lost one. That is checked
# rather than described -- see `validate`.
REQUIRED = frozenset(ORDER)


class RecordError(ValueError):
    """A metadata line is not what a loader will expect."""


def label_for(kind: str) -> str:
    """The converter's layout label for one of this repository's field kinds."""
    kind = str(kind or "")
    best = ""
    for prefix in LABELS:
        if (kind == prefix or kind.startswith(prefix)) and len(prefix) > len(best):
            best = prefix
    return LABELS[best] if best else DEFAULT_LABEL


def job_id(parser: str, layout: str, seed: Any, filename: str) -> str:
    """A stable id for the conversion job that produced this page.

    Four things decide it, and all four are recoverable from the record: which
    renderer drew it, from which layout, at which seed, into which file. Two
    runs of the same plan give the same ids, which is what lets
    `tools/baseline.py` compare metadata lines at all; two pages in one dataset
    cannot collide, because the file name is in there and a directory holds one
    of each.
    """
    return str(uuid.uuid5(JOB_NAMESPACE, f"{parser}|{layout}|{seed}|{filename}"))


# --------------------------------------------------------------------- blocks


def bbox_of(quad: Any) -> dict[str, int]:
    """The axis-aligned box around a quad, which may not be axis-aligned.

    Rounded to whole pixels, as the converter writes them. The quad itself stays
    on the block: this is a summary of it, not a replacement, and a page the
    glyph backend curled has quads no bbox describes.
    """
    xs, ys = [], []
    for corner in quad or []:
        try:
            xs.append(float(corner[0]))
            ys.append(float(corner[1]))
        except (TypeError, ValueError, IndexError):
            continue
    if not xs or not ys:
        return {"x1": 0, "y1": 0, "x2": 0, "y2": 0}
    return {"x1": int(round(min(xs))), "y1": int(round(min(ys))),
            "x2": int(round(max(xs))), "y2": int(round(max(ys)))}


def block_content(label: str, text: str) -> str:
    """One block as markdown: a heading is marked as one, everything else stands."""
    text = str(text or "").strip()
    return MARKDOWN_PREFIX.get(label, "") + text if text else ""


def blocks_from_boxes(boxes: Iterable[dict[str, Any]], *,
                      page_number: int = 1) -> list[dict[str, Any]]:
    """One block per drawn field, in the order the renderer drew them."""
    out: list[dict[str, Any]] = []
    for index, box in enumerate(boxes or []):
        if not isinstance(box, dict):
            continue
        kind = str(box.get("kind", ""))
        text = str(box.get("text", ""))
        label = label_for(kind)
        block = {
            "id": f"p{page_number}-b{index}",
            "page_number": page_number,
            "index_in_page": index,
            "label": label,
            "bbox": bbox_of(box.get("quad")),
            "content": block_content(label, text),
            # This repository's half of the block: which field it is, what it
            # says, and where its corners are before they were squared off.
            "kind": kind,
            "text": text,
            "quad": box.get("quad"),
        }
        out.append(block)
    return out


def _word_field_role(kind: str) -> str:
    """`"key"` for a field's own caption, `"unbound"` for page furniture that
    is not really a document field (a title, a footer line), `"value"` for
    everything else -- the three roles `docsynth.annotations.v1` uses."""
    if kind.endswith(".label") or kind.endswith(".title"):
        return "key"
    if kind in ("title", "footer", "note") or kind.startswith(("footer", "note")):
        return "unbound"
    return "value"


def words_from_boxes(boxes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """One `docsynth.annotations.v1` `word_annotations` entry per word --
    `boxes` here is `page.py::CELL_RECTS_JS`'s `words` array, already one
    entry per whitespace-separated word (or, for an inked run with no text
    node to split, one entry for the whole run -- see that function's own
    comment for why).

    `field_path`/`relation_path`/`field_pattern` all read the same as `kind`
    on purpose: `kind` already IS the dotted field path every `sheets/*.py`
    family writes (`"store.name"`, `"total.grand"`), so there is nothing this
    function would compute that `kind` does not already say -- three names
    for callers written against the target schema's own vocabulary, not
    three different derivations.
    """
    out: list[dict[str, Any]] = []
    for index, box in enumerate(boxes or []):
        if not isinstance(box, dict):
            continue
        kind = str(box.get("kind", ""))
        bbox = bbox_of(box.get("quad"))
        x1, y1, x2, y2 = bbox["x1"], bbox["y1"], bbox["x2"], bbox["y2"]
        out.append({
            "word_index": index,
            "text": str(box.get("text", "")),
            "layout_region_index": None,   # filled in by `regions_from_words`
            # Set from `kind` directly, not left null: a reader needs every
            # word classified into the 19-label vocabulary, not only the ones
            # that happened to land inside a named region -- `layout_class_for`
            # already knows what EVERY `kind` this repository writes means.
            "layout_class": layout_class_for(kind),
            "field_role": _word_field_role(kind),
            "field_path": kind,
            "relation_path": kind,
            "field_pattern": kind,
            "field_name": kind.rsplit(".", 1)[-1] if kind else "",
            "bbox": [x1, y1, x2, y2],
            "bbox_mode": "xyxy_pixel",
            # Not "*_3d_projected_perimeter" like the sample this was built
            # from: this repository does not re-project a box through a
            # geometric distortion after it is measured (`render.py` asserts
            # against exactly that), so the polygon below is the plain
            # rectangle `bbox` already is, not an approximation of a curve.
            "bbox_strategy": "visible_content_perimeter",
            "polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]],
        })
    return out


# Added to every region's word-derived bbox -- a region is a BLOCK a reader
# would point at ("the header", "the signature line"), and a box drawn exactly
# to the ink inside it reads as a crop, not the block. Small and fixed rather
# than proportional to the page: the point is "this box has the breathing room
# a component has," not a second wear knob.
REGION_PAD_PX = 6

# How many word-heights of vertical gap end a region and start the next one,
# when grouping by `layout_class` -- see `regions_from_words`.
REGION_GAP_HEIGHTS = 1.6

# How many word-heights of HORIZONTAL gap end a region and start the next one,
# for two words that sit on the *same* line. Wider than `REGION_GAP_HEIGHTS`
# on purpose: a column gutter -- the space between a date field and a serial
# number field printed side by side in one header row -- reads as several
# word-heights of blank paper, while the space between two words IN one
# phrase is a fraction of one. Any layout that prints unrelated same-class
# content side by side needs this, not just the one that first exposed it.
REGION_GAP_WIDTHS = 3.0


def _pad_bbox(bbox: tuple[float, float, float, float], page_size) -> list[int]:
    x1, y1, x2, y2 = bbox
    x1, y1 = x1 - REGION_PAD_PX, y1 - REGION_PAD_PX
    x2, y2 = x2 + REGION_PAD_PX, y2 + REGION_PAD_PX
    if page_size:
        width, height = page_size
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(width, x2), min(height, y2)
    return [int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2))]


def _region_entry(region_index: int, layout_class: str, text: str,
                  bbox: tuple[float, float, float, float], strategy: str,
                  page_size) -> dict[str, Any]:
    x1, y1, x2, y2 = _pad_bbox(bbox, page_size)
    return {
        "region_index": region_index,
        "tag": "div",
        "layout_class": layout_class,
        "text": text,
        "bbox": [x1, y1, x2, y2],
        "bbox_mode": "xyxy_pixel",
        "bbox_strategy": strategy,
        "polygon": [[x1, y1], [x2, y1], [x2, y2], [x1, y2], [x1, y1]],
    }


def _region_gap_ok(current_bbox: list[float], word_bbox: list[float],
                   gap_y: float, gap_x: float) -> bool:
    """Whether `word_bbox` continues the run `current_bbox` is the union of,
    rather than starting a new region.

    One test, on both axes at once -- not "same line, judge only by the
    horizontal gap" versus "different line, judge only by the vertical gap."
    An earlier version split on that distinction and it does tell a phrase
    from an unrelated field beside it (a date at the left of a header, a
    serial number at the right, sharing a line), but checking only the
    vertical gap for two words on different lines has its own failure: a
    checklist's Yes/No answer column sits far to the right of the question
    text it answers, so once that answer starts a region of its own -- correct,
    it is not close horizontally to the question beside it -- the *next*
    question below, on a new line, was still judged only by the vertical
    gap to that isolated answer and got pulled into its region, dragging
    every question after it in behind it.

    Testing both axes against the RUNNING UNION avoids this without a special
    case for either shape: the union grows to cover the column a wrapped
    paragraph actually occupies, so a later line that starts back at that
    same left margin has zero horizontal gap to it however far below the
    line above it sits -- ordinary paragraphs and stacked lists still merge
    across their own vertical gap exactly as before. A one-word fragment far
    to the side (that answer column) keeps a narrow union bbox of its own, so
    the next line's horizontal distance to it stays large and the wrong
    merge no longer happens.
    """
    ax1, ay1, ax2, ay2 = current_bbox
    bx1, by1, bx2, by2 = word_bbox
    dx = max(0.0, bx1 - ax2, ax1 - bx2)
    dy = max(0.0, by1 - ay2, ay1 - by2)
    return dx <= gap_x and dy <= gap_y


def regions_from_words(words: list[dict[str, Any]], *,
                       cells: Iterable[dict[str, Any]] = (),
                       page_size: tuple[int, int] | None = None) -> list[dict[str, Any]]:
    """Every `layout_annotations` region on the page, covering EVERY word --
    not only the ones that happen to sit in an obviously named block. As a
    side effect, sets `layout_region_index` on every word (already carrying
    its own `layout_class` from `words_from_boxes`).

    Two passes:

    1. **A real `<table>`, if the page drew one** (`cells`, from `page.py::
       CELL_REGIONS_JS` -- empty for the character-grid backend, which has no
       `<table>` element to measure: its rules are painted marks, not cells).
       The region's box is the union of the measured `<td>` boxes -- the
       table's own border and padding, which is what "the table" means to a
       reader, not a crop of whichever cell's text happens to run furthest
       in each direction. Multiple real tables on one page (an invoice's
       items table and its separate tax-summary table) are folded into one
       Table region rather than told apart: both ARE tables, and telling them
       apart needs geometry this function does not have reason to compute
       twice when `words_from_boxes` already means both count as one label.

    2. **Everything else**, grouped by `layout_class` in reading order, split
       into a new region wherever the next word is not "close" to the run so
       far -- see `_region_gap_ok` for what "close" means. This is what gives
       every remaining word a region: there is no third bucket.
    """
    cells = list(cells or [])
    regions: list[dict[str, Any]] = []
    covered = [False] * len(words)

    if cells:
        x1 = min(c["quad"][0][0] for c in cells)
        y1 = min(c["quad"][0][1] for c in cells)
        x2 = max(c["quad"][2][0] for c in cells)
        y2 = max(c["quad"][2][1] for c in cells)
        text = " ".join(str(c.get("text", "")) for c in cells if c.get("text"))
        regions.append(_region_entry(0, "Table", text, (x1, y1, x2, y2),
                                     "dom_element_perimeter", page_size))
        for i, word in enumerate(words):
            cx = (word["bbox"][0] + word["bbox"][2]) / 2
            cy = (word["bbox"][1] + word["bbox"][3]) / 2
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                covered[i] = True

    heights = [w["bbox"][3] - w["bbox"][1] for i, w in enumerate(words) if not covered[i]]
    median_height = sorted(heights)[len(heights) // 2] if heights else 12.5
    gap_y = median_height * REGION_GAP_HEIGHTS
    gap_x = median_height * REGION_GAP_WIDTHS

    current: dict[str, Any] | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        member = current["members"]
        x1, y1, x2, y2 = current["bbox"]
        text = " ".join(w["text"] for w in member if w["text"])
        regions.append(_region_entry(len(regions), current["layout_class"], text,
                                     (x1, y1, x2, y2), "visible_content_union_perimeter",
                                     page_size))
        for w in member:
            w["layout_region_index"] = regions[-1]["region_index"]
        current = None

    for i, word in enumerate(words):
        if covered[i]:
            flush()
            word["layout_region_index"] = 0   # the Table region, always index 0
            continue
        cls = word["layout_class"]
        wb = word["bbox"]
        if (current is not None and current["layout_class"] == cls
                and _region_gap_ok(current["bbox"], wb, gap_y, gap_x)):
            current["members"].append(word)
            current["bbox"] = [min(current["bbox"][0], wb[0]), min(current["bbox"][1], wb[1]),
                               max(current["bbox"][2], wb[2]), max(current["bbox"][3], wb[3])]
        else:
            flush()
            current = {"layout_class": cls, "members": [word], "bbox": list(wb)}
    flush()
    return regions


def rows(blocks: Iterable[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    """Blocks grouped into the lines they were printed on.

    A receipt line is three boxes -- name, quantity, amount -- and writing each
    on its own markdown line turns a table into a column. Two adjacent blocks
    share a row when their boxes overlap vertically by more than half the
    shorter one's height, which is the same test a person makes by eye and does
    not need the grid the renderer has already thrown away. Headings never join
    a row: a title beside a date is still a title.

    **Down the page, then across it -- not the order the renderer drew in.**
    `synthesis.json` keeps the canonical `text_sequence` the label is built in,
    which is a different thing and stays a different thing: a form draws its
    left column and then its right, so drawn order puts every label in one run
    and every value in another, and the markdown would read as two lists rather
    than as the page. Sorting by the top edge and then the left one is what a
    converter reading the pixels would do, and it is what puts
    `(1) Họ tên người bệnh: ...` and `Ngày, tháng, năm sinh: ...` back on the
    one line they are printed on.
    """
    grouped: list[list[dict[str, Any]]] = []
    ordered = sorted(
        (block for block in blocks if str(block.get("content", "")).strip()),
        key=lambda block: (float((block.get("bbox") or {}).get("y1", 0)),
                           float((block.get("bbox") or {}).get("x1", 0))))
    for block in ordered:
        box = block.get("bbox") or {}
        top, bottom = float(box.get("y1", 0)), float(box.get("y2", 0))
        alone = block.get("label") in STANDALONE
        if grouped and not alone:
            last = grouped[-1][-1]
            if last.get("label") not in STANDALONE:
                other = last.get("bbox") or {}
                o_top, o_bottom = float(other.get("y1", 0)), float(other.get("y2", 0))
                overlap = min(bottom, o_bottom) - max(top, o_top)
                shorter = min(bottom - top, o_bottom - o_top)
                if shorter > 0 and overlap > shorter / 2:
                    grouped[-1].append(block)
                    continue
        grouped.append([block])
    # Left to right inside a row, which is the order it was read in and not
    # necessarily the order it was drawn in. A stable sort, so two boxes that
    # start at the same x keep the renderer's own order between them.
    return [sorted(row, key=lambda block: float((block.get("bbox") or {}).get("x1", 0)))
            for row in grouped]


def markdown_of(blocks: Iterable[dict[str, Any]]) -> str:
    """The page as markdown: one paragraph per printed line."""
    lines = ["  ".join(block["content"] for block in row) for row in rows(blocks)]
    return "\n\n".join(line for line in lines if line.strip())


def html_of(blocks: Iterable[dict[str, Any]]) -> str:
    """The same page as HTML, one element per printed line."""
    out: list[str] = []
    for row in rows(blocks):
        tag = HTML_TAG.get(row[0].get("label", ""), "p")
        text = " ".join(str(block.get("text", "")).strip() for block in row)
        out.append(f"<{tag}>{_escape(text)}</{tag}>")
    return "\n".join(out) + ("\n" if out else "")


def _escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def field_paths(extracted: Any, prefix: str = "") -> list[str]:
    """Every leaf path in the nested label, which is what `extract_fields` names.

    `settings.extract_fields` is empty on a converter run that was asked for
    nothing in particular. Here the label is always produced, so the honest
    value is the list of fields it carries.
    """
    out: list[str] = []
    if isinstance(extracted, dict):
        for key, value in extracted.items():
            out += field_paths(value, f"{prefix}.{key}" if prefix else str(key))
    elif isinstance(extracted, list):
        for value in extracted:
            out += field_paths(value, prefix)
    elif prefix:
        out.append(prefix)
    return sorted(dict.fromkeys(out))


# ---------------------------------------------------------------------- build


def build(*, filename: str, width: int, height: int, parser: str,
          boxes: Iterable[dict[str, Any]] = (), words: Iterable[dict[str, Any]] = (),
          cells: Iterable[dict[str, Any]] = (), extracted: Any = None, seed: Any = "",
          layout: str = "", task: str = TASK_CONVERT,
          settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """One metadata line, assembled once so the three renderers cannot drift.

    `seed` and `layout` are not written down -- they are in `synthesis.json` --
    but the `job_id` is a function of both, so they are asked for here and again
    in `stamp`, which is the only other place that id is derived.

    `words`: `page.py::CELL_RECTS_JS`'s `words` array (one box per
    whitespace-separated word), separate from `boxes` (one box per field,
    the same as it always was) because they feed two DIFFERENT arrays here --
    `blocks` stays exactly what every existing reader already expects;
    `word_annotations`/`layout_annotations` are additive, in the
    `docsynth.annotations.v1` shape (`layout_class` from `DOCSYNTH_LABELS`,
    not `PAGE_LABELS`) -- see `words_from_boxes`/`regions_from_words`.

    `cells`: `generators/html/render.py::regions_from_rects`'s table-cell
    list (empty off the character-grid backend, which draws no `<table>`) --
    lets the Table region use the cells' own measured boxes instead of a
    union of the words inside them. See `regions_from_words`.
    """
    blocks = blocks_from_boxes(boxes)
    word_annotations = words_from_boxes(words)
    layout_annotations = regions_from_words(
        word_annotations, cells=cells, page_size=(int(width), int(height)))

    options = {**BASE_SETTINGS, **(settings or {})}
    options["convert_mode"] = parser
    options["extract_fields"] = field_paths(extracted)

    return {
        "schema_version": SCHEMA_VERSION,
        "job_id": job_id(parser, layout, seed, filename),
        "task": task,
        "parser": parser,
        "filename": filename,
        "source_files": [filename],
        "settings": options,
        # A drawn page is one page of one document, so there is nothing for the
        # converter's segmentation to say. `source_file` and `html` are blank
        # for the same reason they are blank in a converter's own single-page
        # output: the page came from the image itself, and the markup is at the
        # top level rather than repeated per page.
        "documents": [],
        "pages": [{
            "page_number": 1,
            "width": int(width),
            "height": int(height),
            "source_file": "",
            "document_index": None,
            "html": "",
        }],
        "blocks": blocks,
        "word_annotations": word_annotations,
        "layout_annotations": layout_annotations,
        "markdown": markdown_of(blocks),
        "html": html_of(blocks),
        "extracted": extracted,
    }


def stamp(item: dict[str, Any], *, parser: str, layout: str, seed: Any,
          filename: str) -> dict[str, Any]:
    """Say again whose page this is, in place, and re-derive the id from it.

    A shard renames every image as it moves it out of staging and attaches the
    layout the plan asked for, and four fields follow: `parser`,
    `settings.convert_mode`, `filename` with its `source_files`, and the
    `job_id`, which is a function of all four.

    All four are arguments rather than read back off the record, because two of
    them -- the layout and the seed -- are not on it: they are in
    `synthesis.json`, and the caller renaming a page is the caller that has
    them.
    """
    item["parser"] = parser
    item.setdefault("settings", {})["convert_mode"] = parser
    item["filename"] = filename
    item["source_files"] = [filename]
    item["job_id"] = job_id(parser, layout, seed, filename)
    return item


# ------------------------------------------------------------------- checking


def validate(record: dict[str, Any], *, strict: bool = True) -> list[str]:
    """Everything wrong with one record, most important first.

    A key that is *not* in the schema is as wrong as one that is missing.
    That is the whole point of the shape: a line is what a converted page
    looks like, and a generator that quietly appended its own key to it would
    put this repository's business back in a file that is meant to be free of
    it. `strict=False` is kept for a caller checking a record still being
    assembled, and today relaxes nothing else.
    """
    problems: list[str] = []
    for key in sorted(REQUIRED - set(record)):
        problems.append(f"missing key {key!r}")
    for key in sorted(set(record) - REQUIRED):
        problems.append(f"{key!r} is not in the converter's schema; how a page "
                        f"was made belongs in synthesis.json")

    if record.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"schema_version must be {SCHEMA_VERSION}, "
                        f"got {record.get('schema_version')!r}")

    name = record.get("filename")
    if name is not None:
        if not isinstance(name, str) or not name:
            problems.append("filename must be a non-empty string")
        elif Path(name).is_absolute() or ".." in Path(name).parts:
            # An absolute path here would make the dataset unmovable, and would
            # differ between two machines that produced identical images.
            problems.append(f"filename must be relative and simple, got {name!r}")
        elif record.get("source_files") != [name]:
            problems.append("source_files must be exactly [filename]")

    pages = record.get("pages")
    if pages is not None:
        if not isinstance(pages, list) or len(pages) != 1:
            problems.append("pages must hold exactly one page")
        else:
            page = pages[0]
            missing = {"page_number", "width", "height"} - set(page or {})
            if missing:
                problems.append(f"pages[0] needs {', '.join(sorted(missing))}")
            elif not (int(page["width"]) > 0 and int(page["height"]) > 0):
                problems.append("pages[0] has no size, so no bbox can be checked")

    if not record.get("parser"):
        problems.append("parser is empty; nothing said which renderer drew it")

    # `settings` was described as exact and never checked, which is how
    # `max_pixels` drifted: it held the page's own pixel count until `dabf19f`
    # made it null -- it is a *cap*, none was applied, and the size is already
    # in `pages[0]` -- and 295 already-written records kept the old value. The
    # data then described a cap the generator had stopped applying, and nothing
    # said so. Checked here rather than described in a comment, so the next
    # option to move takes the records with it or fails loudly.
    settings = record.get("settings")
    if settings is not None:
        if not isinstance(settings, dict):
            problems.append("settings must be an object")
        else:
            for key in sorted(set(BASE_SETTINGS) - set(settings)):
                problems.append(f"settings is missing {key!r}")
            for key in sorted(set(settings) - set(BASE_SETTINGS)):
                problems.append(f"settings.{key} is not one of the converter's "
                                f"job options")
            for key, value in BASE_SETTINGS.items():
                if key in PER_PAGE_SETTINGS or key not in settings:
                    continue
                # Type as well as value: `False` and `0` compare equal in
                # Python, and a record that said `end2end: 0` would be a record
                # written by something that did not know it was a flag.
                if settings[key] != value or type(settings[key]) is not type(value):
                    problems.append(f"settings.{key} must be {value!r}, "
                                    f"got {settings[key]!r}")
            if "convert_mode" in settings:
                mode, drew = settings["convert_mode"], record.get("parser")
                if mode != drew:
                    problems.append(f"settings.convert_mode must be the parser "
                                    f"{drew!r}, got {mode!r}")

    # A drawn document page carries a nested label; a table image does not, and
    # `generators/html/tables.py` says so with its own `task`. Asking a table
    # for a `total` it has no notion of is how a shared envelope turns into a
    # lie, so the two are checked for different things.
    if record.get("task") == TASK_CONVERT:
        value = record.get("extracted")
        if not isinstance(value, dict) or not value:
            problems.append("extracted must be the nested label, as an object")

    blocks = record.get("blocks")
    if blocks is not None:
        if not isinstance(blocks, list):
            problems.append("blocks must be a list")
        else:
            for position, block in enumerate(blocks):
                wanted = {"id", "page_number", "index_in_page", "label", "bbox",
                          "content", "kind", "text", "quad"}
                if not isinstance(block, dict) or wanted - set(block):
                    problems.append(
                        f"blocks[{position}] needs {', '.join(sorted(wanted))}")
                    break
                quad = block["quad"]
                if not isinstance(quad, list) or len(quad) != 4:
                    problems.append(f"blocks[{position}].quad must be four corners")
                    break
                if set(block["bbox"] or {}) != {"x1", "y1", "x2", "y2"}:
                    problems.append(f"blocks[{position}].bbox needs x1, y1, x2, y2")
                    break

    word_annotations = record.get("word_annotations")
    if word_annotations is not None:
        if not isinstance(word_annotations, list):
            problems.append("word_annotations must be a list")
        else:
            wanted = {"word_index", "text", "layout_region_index", "layout_class",
                     "field_role", "field_path", "relation_path", "field_pattern",
                     "field_name", "bbox", "bbox_mode", "bbox_strategy", "polygon"}
            for position, word in enumerate(word_annotations):
                if not isinstance(word, dict) or wanted - set(word):
                    problems.append(
                        f"word_annotations[{position}] needs {', '.join(sorted(wanted))}")
                    break
                if word["field_role"] not in ("key", "value", "unbound"):
                    problems.append(
                        f"word_annotations[{position}].field_role must be key/value/unbound")
                    break

    layout_annotations = record.get("layout_annotations")
    if layout_annotations is not None:
        if not isinstance(layout_annotations, list):
            problems.append("layout_annotations must be a list")
        else:
            wanted = {"region_index", "tag", "layout_class", "text", "bbox",
                     "bbox_mode", "bbox_strategy", "polygon"}
            for position, region in enumerate(layout_annotations):
                if not isinstance(region, dict) or wanted - set(region):
                    problems.append(
                        f"layout_annotations[{position}] needs {', '.join(sorted(wanted))}")
                    break
                if region["layout_class"] not in DOCSYNTH_LABELS:
                    problems.append(
                        f"layout_annotations[{position}].layout_class "
                        f"{region['layout_class']!r} is not one of the 19 docsynth labels")
                    break
    return problems


def check(record: dict[str, Any], *, strict: bool = True, where: str = "") -> dict[str, Any]:
    """Return the record, or raise naming what is wrong with it."""
    problems = validate(record, strict=strict)
    if problems:
        prefix = f"{where}: " if where else ""
        raise RecordError(prefix + "; ".join(problems))
    return record


# ------------------------------------------------------- the shape before this
#
# `metadata.jsonl` -- one index holding every page, the renderer's own keys, and
# the whole recipe repeated per line -- is what the datasets under `data/` were
# written in before this module followed the converter's schema. Every one of
# them has been brought forward and none is left in the repository, so this is
# here for a set someone generated earlier and kept elsewhere.
#
# It lives in this file rather than in a tool of its own because a record has
# exactly one definition, `build` above, and both callers reach it: a renderer
# with pixels in hand, and this, with an old line in hand. A second module would
# be a second place for that definition to drift to. `python -c "from pipeline
# import record; record.migrate(Path('data/old'))"` is the whole interface.
#
# Nothing here re-renders. Every value is already in the old record, except the
# page size, which the old shape never carried and which is read from the JPEG
# header beside it.


def _jpeg_size(path):
    from pipeline.invariants import jpeg_size  # noqa: PLC0415 -- avoids a cycle

    return jpeg_size(path)


# What a table's cell becomes on the way to a block. `tables.py` writes a cell
# as a list of single-character tokens and a list of quads, because that is what
# the PPStructure label wants; a block wants the word and one quad.
CELL_KIND = "cell"


def framework_of(item: dict, directory: Path) -> str:
    """Which renderer drew it: what the record says, or what the name says.

    A record written by a direct renderer run has no `framework` -- the shard is
    what used to attach it -- but every renderer names its files after itself,
    and `data/hand12/` is a whole set of them.
    """
    named = item.get("framework")
    if named:
        return str(named)
    stem = Path(str(item.get("file_name", ""))).name
    for backend in ("synthdog", "genalog", "html"):
        if stem.startswith(backend + "_"):
            return backend
    return directory.name


def _legacy_page_size(path: Path) -> tuple[int, int]:
    size = _jpeg_size(path)
    if size is None:
        raise SystemExit(f"{path}: cannot read the image size, so no page can be built")
    return size


def convert_page(item: dict, directory: Path) -> tuple[dict, dict]:
    """One drawn document page, old shape to (index line, provenance entry)."""
    name = str(item["file_name"])
    width, height = _legacy_page_size(directory / name)
    parser = framework_of(item, directory)
    recipe = item.get("recipe") or {}
    layout = str(item.get("layout") or "")
    if not layout:
        layout = str(((recipe.get("attributes") or {}).get("layout") or {}).get("id", ""))

    truth = item.get("ground_truth")
    extracted = {}
    if isinstance(truth, str):
        try:
            extracted = json.loads(truth).get("gt_parse") or {}
        except (json.JSONDecodeError, AttributeError):
            extracted = {}

    # Everything the old record carried beside the five renderer keys. It went
    # in additively then and it goes to `synthesis.json` now: `handwriting` is
    # what the checkpoint wrote and what it refused, `cells` and `structure` are
    # the structure half of a template render, and dropping either would lose a
    # label nothing else holds.
    extras = {key: value for key, value in item.items()
              if key not in {"file_name", "ground_truth", "text_sequence",
                             "recipe", "boxes", "framework", "layout"}}
    built = build(
        filename=name, width=width, height=height, parser=parser,
        boxes=item.get("boxes") or [], extracted=extracted,
        seed=recipe.get("seed", ""), layout=layout,
    )
    return built, {"job_id": built["job_id"], "layout": layout, "recipe": recipe,
                   "text_sequence": str(item.get("text_sequence", "")),
                   "extra": extras}


def convert_table(item: dict, directory: Path) -> tuple[dict, dict]:
    """One table image, old shape to new.

    A table's label is its structure, so the HTML *is* the ground truth and goes
    where the converter puts a page's markup. There is no faithful markdown for
    a table with merged cells, so `markdown` is left empty rather than filled
    with something a reader would have to un-guess. The border style is in the
    file name, which is where `tables.py` put it, and it is the nearest thing a
    table has to a layout.
    """
    name = str(item["file_name"])
    width, height = _legacy_page_size(directory / name)
    border = Path(name).stem.rsplit("_", 1)[0]
    boxes = []
    for cell in item.get("cells") or []:
        quads = cell.get("bbox") or []
        boxes.append({
            "kind": CELL_KIND,
            "text": "".join(cell.get("tokens") or []),
            "quad": quads[0] if quads else None,
        })
    built = build(
        filename=name, width=width, height=height, parser="html",
        boxes=boxes, extracted=None, task=TASK_TABLE, layout=border,
    )
    built["html"] = str(item.get("ground_truth", ""))
    built["markdown"] = ""
    return built, {"job_id": built["job_id"], "layout": border,
                   "recipe": {"seed": None, "attributes": {}, "tags": []},
                   "extra": {"n_cells": item.get("n_cells", len(boxes))}}


def table_border(name: str) -> str:
    """A table image's border style, which `tables.py` put in its file name.

    The nearest thing a table has to a layout, and the axis a table set is
    actually reported along -- so it is recovered rather than left blank.
    """
    return Path(name).stem.rsplit("_", 1)[0]


def split_synthesis(item: dict, directory: Path) -> tuple[dict, dict]:
    """A converter-shaped line that still carries its provenance inside it.

    A shape this repository did ship, between moving to the converter's schema
    and moving the provenance out of it. Nothing is read from disk here: every
    value is already in the line, under `synthesis`.
    """
    item = dict(item)
    name = str(item.get("filename", ""))
    inside = item.pop("synthesis", None) or {}
    recipe = inside.pop("recipe", None) or {}
    layout = str(inside.pop("layout", ""))
    extras = {key: value for key, value in inside.items() if key != "framework"}

    if item.get("task") == TASK_TABLE:
        layout = layout or table_border(name)
        # A table's structure tokens and cell boxes are its *label*, and
        # `gt.txt` beside the index is the file that holds them, in the format
        # other tools read. Carried in the record as well while the provenance
        # rode inside it; dropped here, but only once that file is there to
        # point at.
        if (directory / "gt.txt").exists():
            extras.pop("structure_tokens", None)
            extras.pop("cells", None)

    return item, {"job_id": str(item.get("job_id", "")), "layout": layout,
                  "recipe": recipe, "text_sequence": str(inside.get("text_sequence", "")
                                                         or extras.pop("text_sequence", "")),
                  "extra": extras}


def convert(item: dict, directory: Path) -> tuple[dict, dict]:
    if item.get("schema_version") == SCHEMA_VERSION:
        return split_synthesis(item, directory)
    if item.get("task") == TASK_TABLE and "cells" in item:
        return convert_table(item, directory)
    return convert_page(item, directory)


def refresh(record: dict[str, Any]) -> bool:
    """Reset one record's constant job options to the current definition.

    Only the constants: `convert_mode` names the renderer and `extract_fields`
    names the label, and `build` already fills both in per page. Returns whether
    anything moved, so a caller can leave a file it would rewrite byte for byte
    alone.

    A record does not have to be re-rendered to be brought forward when an
    option changes meaning -- `max_pixels` went from the page's own pixel count
    to null and the pixels never moved, only what the record claimed about them.
    That is the whole difference between this and re-drawing the set.
    """
    settings = record.get("settings")
    if not isinstance(settings, dict):
        return False
    moved = False
    for key, value in BASE_SETTINGS.items():
        if key in PER_PAGE_SETTINGS:
            continue
        if (key not in settings or settings[key] != value
                or type(settings[key]) is not type(value)):
            settings[key] = value
            moved = True

    # `word_annotations`/`layout_annotations` are additive: a page drawn
    # before they existed was never wrong, it just has nothing to put there --
    # an empty list is the honest answer, not a re-render.
    for key in ("word_annotations", "layout_annotations"):
        if key not in record:
            record[key] = []
            moved = True
    return moved


def migrate(directory: Path | str, *, write: bool = True) -> tuple[int, int]:
    """An older set, brought forward. Returns (pages, sets).

    Two things can be out of date, and a set can have either or both:

    * **the shape** -- one `metadata.jsonl` for a set instead of one record per
      image, with how the page was made mixed into the same line;
    * **a value** -- a record already in the converter's schema, but written
      when one of the constant job options meant something else.

    Neither re-renders anything. Idempotent, which is what makes running it over
    a whole tree safe: a directory with no index and no stale option reports
    zero.
    """
    from pipeline import synthesis  # noqa: PLC0415 -- avoids a cycle

    directory = Path(directory)
    pages = sets = 0
    for index in sorted(directory.rglob("metadata.jsonl")):
        here = index.parent
        lines = [json.loads(line) for line in
                 index.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            continue
        # An index whose lines are ALREADY the converter's schema, with the
        # provenance already beside it, has only the shape of the set out of
        # date: the lines are exploded into a file each and nothing is rebuilt.
        split_only = (lines[0].get("schema_version") == SCHEMA_VERSION
                      and "synthesis" not in lines[0]
                      and synthesis.beside(here).exists())
        built_all: list[dict[str, Any]] = []
        entries: list[tuple[str, dict[str, Any]]] = []
        framework = ""
        for item in lines:
            if split_only:
                built, entry = item, None
            elif (item.get("schema_version") == SCHEMA_VERSION
                    and "synthesis" not in item):
                raise RecordError(
                    f"{index}: the index is already in the converter's schema "
                    f"but carries no provenance, and there is no "
                    f"{synthesis.NAME} beside it -- so how these {len(lines)} "
                    f"pages were made is gone and cannot be rebuilt from here")
            else:
                built, entry = convert(item, here)
            refresh(built)
            name = file_name(built)
            check(built, where=f"{index}:{name}")
            built_all.append(built)
            if entry is not None:
                entries.append((name, entry))
            framework = framework or built["parser"]
        if write:
            for built in built_all:
                write_one(built, here)
            if entries:
                synthesis.write(synthesis.beside(here), framework, entries)
            # Both halves are on disk, so the index is now a second answer to
            # the same question -- and the stale one would still parse.
            index.unlink()
        pages += len(built_all)
        sets += 1

    # Second pass: sets that are already one record per image, but were written
    # when a constant option meant something else. The first pass cannot see
    # them -- it looks for an index, and these have none -- and they are the
    # common case now that every committed set is exploded. A record the first
    # pass just wrote is read back here, does not move, and is not counted.
    touched: set[Path] = set()
    for image in images(directory):
        path = beside(image)
        if not path.exists():
            continue
        try:
            item = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            raise RecordError(f"{path}: not readable as JSON -- {error}") from error
        if not refresh(item):
            continue
        check(item, where=str(path))
        if write:
            # `write_one` resolves the record's own `filename` against the
            # directory it is handed, and that name is not always a bare one:
            # `generators/html/tables.py` keeps its pages in `img/` and says so
            # in the record. Handing it `image.parent` would write
            # `img/img/border_0001.json`, so the directory the name is relative
            # *to* is walked back out of the image's path instead.
            depth = len(Path(str(item.get("filename", ""))).parts)
            write_one(item, image.parents[depth - 1])
        pages += 1
        touched.add(image.parent)
    # No double count: a set the first pass handled was written through `build`,
    # so `refresh` finds nothing to move in it and it never reaches `touched`.
    sets += len(touched)
    return pages, sets


# ------------------------------------------------- one file, beside its image

# What a picture is, for the purpose of finding the record next to it. The
# generator writes JPEG; the other two are here because a dataset that arrives
# with PNGs should be readable rather than silently empty.
IMAGES = (".jpg", ".jpeg", ".png")
SUFFIX = ".json"


def beside(image: Path | str) -> Path:
    """The record for one image: the same path, `.json`.

    Not an index and not a subdirectory. A converted page comes back as one
    document about one file, so that is what is written -- `html_000.jpg` and
    `html_000.json`, side by side. It also means the *images* are the listing:
    nothing has to be told which files in a directory are records, and a file
    like `synthesis.json`, which no image is named after, is never mistaken for
    one.
    """
    return Path(image).with_suffix(SUFFIX)


def images(directory: Path | str) -> list[Path]:
    """Every image under a dataset directory, in name order.

    Recursive, because `generators/html/tables.py` keeps its pages in `img/`.
    """
    directory = Path(directory)
    found = [path for path in directory.rglob("*")
             if path.suffix.lower() in IMAGES and path.is_file()]
    return sorted(found, key=lambda path: path.relative_to(directory).as_posix())


def write_one(record: dict[str, Any], directory: Path | str, *,
              strict: bool = True, fsync: bool = False) -> Path:
    """Write one record beside its image, validating on the way out.

    `fsync` is for the shard, which must not write its `DONE` in front of a
    record that is not yet on disk: resume would skip a shard that is short.
    """
    directory = Path(directory)
    name = str(record.get("filename", ""))
    check(record, strict=strict, where=name or "?")
    path = beside(directory / name)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False)
        handle.write("\n")
        if fsync:
            handle.flush()
            os.fsync(handle.fileno())
    return path


def write(records: Iterable[dict[str, Any]], directory: Path | str, *,
          strict: bool = True) -> int:
    """Write a record per image. Streamed: nothing is held but the one in hand."""
    written = 0
    for record in records:
        write_one(record, directory, strict=strict)
        written += 1
    return written


def read_one(path: Path | str) -> dict[str, Any]:
    """One record, given its own path or its image's."""
    return json.loads(beside(path).read_text(encoding="utf-8"))


def read(directory: Path | str) -> list[dict[str, Any]]:
    """Every record under a directory, in the order of the images they describe.

    An image with no record beside it stops this rather than being skipped: a
    dataset that is quietly short is the failure the whole shard contract exists
    to prevent, and a loader that shrugs at it moves that failure downstream.
    """
    directory = Path(directory)
    out: list[dict[str, Any]] = []
    for image in images(directory):
        path = beside(image)
        if not path.exists():
            raise RecordError(
                f"{image.relative_to(directory).as_posix()} has no "
                f"{path.name} beside it")
        out.append(json.loads(path.read_text(encoding="utf-8")))
    return out


# ------------------------------------------------------------------ accessors
#
# One place that knows where a value lives. Everything in this repository that
# reads a metadata line goes through these, so the next time the shape moves it
# moves here and nowhere else -- which is the change that made this file worth
# having when three renderers each spelled the same keys by hand.


def file_name(item: dict[str, Any]) -> str:
    return str(item.get("filename", ""))


def boxes(item: dict[str, Any]) -> list[dict[str, Any]]:
    """The blocks, which carry `kind`, `text` and `quad` as the old boxes did."""
    return list(item.get("blocks") or [])


def word_annotations(item: dict[str, Any]) -> list[dict[str, Any]]:
    """One entry per word -- see `words_from_boxes`."""
    return list(item.get("word_annotations") or [])


def layout_annotations(item: dict[str, Any]) -> list[dict[str, Any]]:
    """One entry per layout region -- see `regions_from_words`."""
    return list(item.get("layout_annotations") or [])


def extracted(item: dict[str, Any]) -> dict[str, Any]:
    """The nested label, as an object."""
    value = item.get("extracted")
    return value if isinstance(value, dict) else {}


def ground_truth(item: dict[str, Any]) -> str:
    """The nested label as the JSON *string* a Donut-style loader reads."""
    return json.dumps({"gt_parse": extracted(item)}, ensure_ascii=False)


def framework(item: dict[str, Any]) -> str:
    """Which renderer drew it. The recipe, the layout and the reading order are
    not here any more -- they are in `synthesis.json`, and
    `pipeline/synthesis.py` reads them by file name."""
    return str(item.get("parser", ""))


def page_size(item: dict[str, Any]) -> tuple[int, int]:
    pages = item.get("pages") or [{}]
    page = pages[0] if pages else {}
    return int(page.get("width", 0) or 0), int(page.get("height", 0) or 0)


__all__ = [
    "BASE_SETTINGS",
    "DEFAULT_LABEL",
    "DOCSYNTH_LABELS",
    "DOCSYNTH_LABEL_FOR_KIND",
    "JOB_NAMESPACE",
    "LABELS",
    "ORDER",
    "PAGE_LABELS",
    "PER_PAGE_SETTINGS",
    "REGIONS",
    "REQUIRED",
    "IMAGES",
    "SCHEMA_VERSION",
    "SUFFIX",
    "TASK_CONVERT",
    "TASK_TABLE",
    "RecordError",
    "bbox_of",
    "beside",
    "blocks_from_boxes",
    "block_content",
    "boxes",
    "build",
    "check",
    "extracted",
    "field_paths",
    "file_name",
    "framework",
    "ground_truth",
    "html_of",
    "images",
    "job_id",
    "label_for",
    "layout_annotations",
    "layout_class_for",
    "markdown_of",
    "migrate",
    "page_size",
    "read",
    "read_one",
    "refresh",
    "regions_from_words",
    "stamp",
    "rows",
    "validate",
    "word_annotations",
    "words_from_boxes",
    "write",
    "write_one",
]
