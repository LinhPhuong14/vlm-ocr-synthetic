"""Split an old `metadata.jsonl` into the index and the provenance beside it.

    python tools/migrate_metadata.py data/dataset60          # in place
    python tools/migrate_metadata.py data --check            # say what would change

The records committed under `data/` were written before `pipeline/record.py`
followed the converter's schema and before how a page was made moved out of it.
They are output, not source, but they are also the first thing the README tells
a reader to look at -- `head -1 data/dataset60/html/metadata.jsonl` -- so
leaving half the repository in the old shape would make the documented format
and the committed format disagree.

Each old line becomes two things:

* a `metadata.jsonl` line in the converter's schema and nothing else;
* an entry in `synthesis.json` beside it -- the seed, which option the page drew
  for each attribute, its tags, its reading order, and whatever extras it
  carried (`handwriting`, `cells`, `structure`). The params behind those option
  ids are written once for the whole file rather than once per page, which is
  most of why the old records were as large as they were.

Nothing here re-renders. Every value written is already in the old record, with
two exceptions, and both are read rather than invented:

* **the page size**, which the old records never carried, comes from the JPEG
  header beside them (`pipeline/invariants.jpeg_size`, a few hundred bytes and
  no imaging library);
* **the framework and layout**, which a record written by a renderer run rather
  than by a shard does not have, come from the file-name prefix and from the
  recipe's own layout id.

So the conversion is total: run it twice and the second run changes nothing,
which is what `--check` reports on.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import invariants, record, synthesis  # noqa: E402

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


def page_size(path: Path) -> tuple[int, int]:
    size = invariants.jpeg_size(path)
    if size is None:
        raise SystemExit(f"{path}: cannot read the image size, so no page can be built")
    return size


def convert_page(item: dict, directory: Path) -> tuple[dict, dict]:
    """One drawn document page, old shape to (index line, provenance entry)."""
    name = str(item["file_name"])
    width, height = page_size(directory / name)
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
    built = record.build(
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
    width, height = page_size(directory / name)
    border = Path(name).stem.rsplit("_", 1)[0]
    boxes = []
    for cell in item.get("cells") or []:
        quads = cell.get("bbox") or []
        boxes.append({
            "kind": CELL_KIND,
            "text": "".join(cell.get("tokens") or []),
            "quad": quads[0] if quads else None,
        })
    built = record.build(
        filename=name, width=width, height=height, parser="html",
        boxes=boxes, extracted=None, task=record.TASK_TABLE, layout=border,
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

    if item.get("task") == record.TASK_TABLE:
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
    if item.get("schema_version") == record.SCHEMA_VERSION:
        return split_synthesis(item, directory)
    if item.get("task") == record.TASK_TABLE and "cells" in item:
        return convert_table(item, directory)
    return convert_page(item, directory)


def convert_file(path: Path, *, write: bool = True) -> tuple[int, int]:
    """Convert one `metadata.jsonl` and the file beside it.

    Returns (lines, lines that changed). Already-converted input is recognised
    by the line carrying a `schema_version`, and is left exactly as it is --
    including its provenance, which is read back and written out again so the
    two files never fall out of step.
    """
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return 0, 0

    first = json.loads(lines[0])
    if (first.get("schema_version") == record.SCHEMA_VERSION
            and "synthesis" not in first and synthesis.beside(path).exists()):
        return len(lines), 0            # already split; run it twice

    converted: list[str] = []
    entries: list[tuple[str, dict]] = []
    changed = 0
    framework = ""
    for line in lines:
        item = json.loads(line)
        if (item.get("schema_version") == record.SCHEMA_VERSION
                and "synthesis" not in item):
            raise SystemExit(
                f"{path}: the index is already in the converter's schema but "
                f"carries no provenance, and there is no {synthesis.NAME} beside "
                f"it -- so how these {len(lines)} pages were made is gone and "
                f"cannot be rebuilt from here")
        new, entry = convert(item, path.parent)
        record.check(new, where=f"{path}:{record.file_name(new)}")
        text = json.dumps(new, ensure_ascii=False)
        changed += text != line
        converted.append(text)
        entries.append((record.file_name(new), entry))
        framework = framework or new["parser"]

    if write and changed:
        path.write_text("\n".join(converted) + "\n", encoding="utf-8")
        synthesis.write(synthesis.beside(path), framework, entries)
    return len(lines), changed



def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", type=Path, nargs="+",
                        help="directories to walk for metadata.jsonl")
    parser.add_argument("--check", action="store_true",
                        help="report what would change and write nothing")
    args = parser.parse_args()

    files = sorted({path for root in args.roots
                    for path in ([root] if root.is_file()
                                 else root.rglob("metadata.jsonl"))})
    if not files:
        print("no metadata.jsonl found", file=sys.stderr)
        return 1

    total, moved = 0, 0
    for path in files:
        lines, changed = convert_file(path, write=not args.check)
        total += lines
        moved += changed
        verb = "would convert" if args.check else "converted"
        print(f"[{'--' if changed == 0 else 'ok'}] {path}  {lines} line(s), "
              f"{verb} {changed}")
    print(f"{len(files)} file(s), {total} line(s), {moved} changed")
    return 1 if (args.check and moved) else 0


if __name__ == "__main__":
    raise SystemExit(main())
