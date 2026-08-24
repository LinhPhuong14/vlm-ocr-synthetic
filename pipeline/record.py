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

# ...and to the HTML element that holds it.
HTML_TAG = {"Title": "h1", "Section-header": "h2", "Page-header": "p",
            "Page-footer": "p", "Table": "p", "Text": "p", "Picture": "p"}

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
         "settings", "documents", "pages", "blocks", "markdown", "html",
         "extracted")

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
          boxes: Iterable[dict[str, Any]] = (), extracted: Any = None,
          seed: Any = "", layout: str = "", task: str = TASK_CONVERT,
          settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """One metadata line, assembled once so the three renderers cannot drift.

    `seed` and `layout` are not written down -- they are in `synthesis.json` --
    but the `job_id` is a function of both, so they are asked for here and again
    in `stamp`, which is the only other place that id is derived.
    """
    blocks = blocks_from_boxes(boxes)

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
    "JOB_NAMESPACE",
    "LABELS",
    "ORDER",
    "PAGE_LABELS",
    "PER_PAGE_SETTINGS",
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
    "markdown_of",
    "migrate",
    "page_size",
    "read",
    "read_one",
    "refresh",
    "stamp",
    "rows",
    "validate",
    "write",
    "write_one",
]
