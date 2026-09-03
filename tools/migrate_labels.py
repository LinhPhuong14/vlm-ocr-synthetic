"""Rewrite a dataset's labels onto the document hierarchy. Images untouched.

    python tools/migrate_labels.py data/dataset60           # say what would change
    python tools/migrate_labels.py data/dataset60 --write    # do it

Before `taxonomy/` existed, a label's type was `receipt_eatery` or
`receipt_market` -- two names invented here, meaning nothing outside this
repository. They are now `business.receipt.restaurant` and
`business.receipt.retail`, and the label carries the family and the readable
path beside the id.

**Why the committed datasets can be migrated rather than regenerated.** The
document type is a *classification*: it is never printed on the page, which is
exactly why `pipeline.invariants` exempts it from "every label value must appear
on some box". So the pixels of `data/dataset60` are as correct after this as
before, and rewriting the labels is not a fudge -- it is the whole change.
Anything that did touch the pixels would need the three renderers and a
regeneration, and this tool would refuse to be the answer.

A migrated record is byte-identical to what the generator writes today for the
same content: the classification block goes first, in the same order, and every
other key keeps its place. That is checked by a test rather than asserted here,
because "the migration produces what a fresh run would" is the only property
that makes a migrated dataset trustworthy.

Default is a dry run. A tool that edits committed data on the strength of a
path typed once should say what it is about to do first.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import taxonomy  # noqa: E402

# The two names the repository used before the hierarchy, and the nodes they
# always meant. `profile: eatery` was every kind of eatery from a street stall
# to a restaurant printing VAT; `market` was supermarkets and convenience
# stores. Both map one-to-one, which is why this is a rename and not a guess.
LEGACY = {
    "receipt_eatery": "business.receipt.restaurant",
    "receipt_market": "business.receipt.retail",
}


def migrate_parse(parse: dict, tree) -> tuple[dict, bool]:
    """One `gt_parse`, with its classification block rebuilt. `(label, changed)`."""
    doc_type = parse.get("doc_type")
    if not doc_type:
        return parse, False
    resolved = LEGACY.get(str(doc_type), str(doc_type))
    if resolved not in tree:
        raise SystemExit(
            f"label says doc_type={doc_type!r}, which is neither a type in "
            f"taxonomy/ nor one of the old names {sorted(LEGACY)}. Nothing here "
            f"knows what it should become, so nothing is written."
        )
    node = tree.node(resolved)
    classification = {
        "doc_type": node.id,
        "doc_family": node.family,
        "doc_path": list(node.names),
    }
    rebuilt = {**classification,
               **{key: value for key, value in parse.items()
                  if key not in classification}}
    return rebuilt, rebuilt != parse


def migrate_file(path: Path, tree, write: bool) -> tuple[int, int]:
    """`(records, changed)` for one metadata.jsonl."""
    lines = path.read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    changed = 0
    records = 0
    for line in lines:
        if not line.strip():
            continue
        records += 1
        record = json.loads(line)
        raw = record.get("ground_truth")
        if not raw:
            out.append(json.dumps(record, ensure_ascii=False))
            continue
        label = json.loads(raw)
        parse = label.get("gt_parse")
        if not isinstance(parse, dict):
            out.append(json.dumps(record, ensure_ascii=False))
            continue
        rebuilt, did = migrate_parse(parse, tree)
        if did:
            changed += 1
            label["gt_parse"] = rebuilt
            record["ground_truth"] = json.dumps(label, ensure_ascii=False)
        out.append(json.dumps(record, ensure_ascii=False))

    if write and changed:
        # Written through a temporary file in the same directory: a half-written
        # metadata.jsonl is a dataset nobody can use, and this runs over data
        # that is committed rather than regenerable.
        temporary = path.with_suffix(".jsonl.tmp")
        temporary.write_text("\n".join(out) + "\n", encoding="utf-8")
        temporary.replace(path)
    return records, changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("dataset", type=Path, nargs="+",
                        help="dataset directories to migrate")
    parser.add_argument("--write", action="store_true",
                        help="actually rewrite; without it, only report")
    args = parser.parse_args(argv)

    tree = taxonomy.tree()
    total_records = total_changed = 0
    for dataset in args.dataset:
        files = sorted(dataset.rglob("metadata.jsonl"))
        if not files:
            print(f"{dataset}: no metadata.jsonl anywhere under it")
            continue
        for path in files:
            records, changed = migrate_file(path, tree, args.write)
            total_records += records
            total_changed += changed
            state = "rewritten" if (args.write and changed) else "would change"
            print(f"  {path.relative_to(dataset.parent)}: {changed}/{records} "
                  f"{state if changed else 'already current'}")

    print(f"\n{total_changed} of {total_records} labels "
          f"{'rewritten' if args.write else 'would be rewritten'}")
    if total_changed and not args.write:
        print("re-run with --write to apply")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
