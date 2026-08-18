"""The document hierarchy: what it declares, what this repository can build.

    python tools/taxonomy_report.py                    # the tree      (make taxonomy)
    python tools/taxonomy_report.py --summary          # families only
    python tools/taxonomy_report.py --check            # only the problems, exit 1
    python tools/taxonomy_report.py --dataset data/dataset60    # ...with image counts
    python tools/taxonomy_report.py --json

With ninety-eight document types, "what can this repository actually produce"
stops being a question anybody can answer by reading files. Three separate
things have to agree before an image of a given type can exist -- the tree
declares it `ready`, some rules value realises it, and a builder is registered
for it -- and each lives in a different place on purpose. This prints all three
side by side, so a disagreement is a line you can see rather than a dataset that
comes out short.

    ✓  ready and reachable: rules and a builder, both present
    ~  draft: it renders, nothing has been measured against a real page
    ·  planned: named in the hierarchy and nowhere else
    !  a disagreement -- the tree and the code say different things

The last one is the reason this is not just a pretty printer. `!` is a claim in
`taxonomy/families/` that the code does not back up, or code that nothing can
reach; both are silent everywhere else.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import taxonomy  # noqa: E402
from rulebase.documents import coverage  # noqa: E402
from rulebase.spec import load_rules, validate_doc_types  # noqa: E402

MARKS = {"ready": "✓", "draft": "~", "planned": "·", "clash": "!"}


def mark(state: dict) -> str:
    """One character for how a type stands. `!` when its own facts disagree."""
    declared = state["declared"]
    if declared == "ready" and not state["generatable"]:
        return MARKS["clash"]
    if declared != "ready" and state["generatable"]:
        return MARKS["clash"]
    return MARKS.get(declared, "?")


def why(state: dict) -> str:
    """The short reason a type is not generatable, in fixing terms."""
    if state["generatable"]:
        return ""
    missing = []
    if not state["rules"]:
        missing.append("rules")
    if not state["builder"]:
        missing.append("builder")
    return "no " + " or ".join(missing)


def counts_by_type(dataset: Path) -> Counter:
    """How many images of each document type a generated dataset holds.

    Read from the labels rather than from the directory names: the label is
    what a consumer of the dataset sees, so if the two ever disagree the label
    is the one that matters. Older datasets carry a `doc_type` that predates the
    hierarchy; they are counted under the name they carry, which is what makes
    them show up as unknown rather than as nothing.
    """
    found: Counter = Counter()
    for path in sorted(dataset.rglob("metadata.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                label = json.loads(record.get("ground_truth") or "{}")
            except json.JSONDecodeError:
                continue
            parse = label.get("gt_parse") or {}
            doc_type = parse.get("doc_type") or record.get("doc_type")
            if doc_type:
                found[str(doc_type)] += 1
    return found


def _leaf_rows(tree, node, states, images, prefix, last, rows):
    """Depth-first, drawing the branch characters as we go."""
    for index, child_id in enumerate(node.children):
        child = tree.node(child_id)
        final = index == len(node.children) - 1
        stem = "└── " if final else "├── "
        if child.children:
            rows.append((prefix + stem + child.name, "", "", "", ""))
            _leaf_rows(tree, child, states, images, prefix + ("    " if final else "│   "),
                       final, rows)
            continue
        state = states.get(child.id, {})
        if child.is_alias:
            rows.append((prefix + stem + child.name, "=", "",
                         f"filed under {child.same_as}", ""))
            continue
        seen = images.get(child.id, 0) if images is not None else None
        rows.append((
            prefix + stem + child.name,
            mark(state),
            child.engine,
            why(state) or ("" if state.get("declared") == "ready" else state.get("declared", "")),
            "" if seen is None else (str(seen) if seen else "-"),
        ))


def render_tree(tree, states, images=None) -> list[str]:
    lines = []
    for family in tree.families():
        leaves = tree.leaves(under=family.id)
        ready = sum(1 for leaf in leaves if states.get(leaf.id, {}).get("generatable"))
        header = f"{family.number:>2}. {family.name}"
        lines.append("")
        lines.append(f"{header}  [{ready}/{len(leaves)} sẵn sàng · {family.engine}]")
        rows: list[tuple[str, str, str, str, str]] = []
        _leaf_rows(tree, family, states, images, "    ", True, rows)
        width = max((len(row[0]) for row in rows), default=0)
        for name, sign, engine, note, seen in rows:
            if not sign:
                lines.append(f"{name}")
                continue
            tail = f"  {engine:<7}{note}"
            if seen:
                tail = f"  {engine:<7}{seen:>5}  {note}".rstrip()
            lines.append(f"{name.ljust(width)}  {sign}{tail.rstrip()}")
    return lines


def render_summary(tree, states, images=None) -> list[str]:
    lines = ["", f"{'':>2}  {'family':<34}{'types':>6}{'ready':>7}{'engine':>9}"]
    for family in tree.families():
        leaves = tree.leaves(under=family.id)
        ready = sum(1 for leaf in leaves if states.get(leaf.id, {}).get("generatable"))
        seen = ("" if images is None else
                f"{sum(images.get(leaf.id, 0) for leaf in leaves):>8} ảnh")
        lines.append(f"{family.number:>2}. {family.name:<34}{len(leaves):>6}"
                     f"{ready:>7}{family.engine:>9}{seen}")
    return lines


def render_engines(tree, states) -> list[str]:
    """What it would take to cover the rest of the tree, by engine.

    The single most useful number in this report. Every unbuilt type needs one
    of four engines, and only one of the four exists -- so "add ninety-six
    document types" is really "write three engines, then add corpora". Sized
    here rather than guessed at in a planning meeting.
    """
    lines = ["", "Còn thiếu gì — theo engine:"]
    for name, engine in tree.engines.items():
        leaves = [node for node in tree.leaves() if node.engine == name]
        ready = [node for node in leaves if states.get(node.id, {}).get("generatable")]
        state = "có sẵn" if engine.get("built") else "CHƯA CÓ"
        lines.append(
            f"  {name:<8}{state:<9}{len(ready):>3}/{len(leaves):<4} loại sinh được"
            f"   {engine.get('name', '')}")
    return lines


def problems(tree, states) -> list[str]:
    """Everything the report would mark `!`, plus the tree's own lint."""
    found = [f"taxonomy: {problem}" for problem in tree.validate()]
    found += validate_doc_types(load_rules())
    for node_id, state in states.items():
        if state["declared"] != "ready" and state["generatable"]:
            found.append(
                f"{node_id}: generatable (rules and a builder) but still marked "
                f"{state['declared']}; promote it to ready in taxonomy/families/")
    return found


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--summary", action="store_true", help="families only, no leaves")
    parser.add_argument("--check", action="store_true",
                        help="print only the disagreements; exit 1 if there are any")
    parser.add_argument("--dataset", type=Path,
                        help="count the images of each type in a generated dataset")
    parser.add_argument("--json", action="store_true", help="machine-readable")
    args = parser.parse_args(argv)

    tree = taxonomy.tree()
    states = coverage()
    images = counts_by_type(args.dataset) if args.dataset else None
    faults = problems(tree, states)

    if args.json:
        payload = {
            "version": tree.version,
            "counts": tree.counts(),
            "types": {node_id: dict(state) for node_id, state in states.items()},
            "problems": faults,
        }
        if images is not None:
            payload["images"] = dict(images)
        print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        return 1 if (args.check and faults) else 0

    if args.check:
        if not faults:
            print("cây phân cấp và rule-base khớp nhau")
            return 0
        print(f"{len(faults)} vấn đề:\n")
        for fault in faults:
            print(f"  - {fault}")
        return 1

    counts = tree.counts()
    print(f"{tree.root_name.upper()} — cây phân cấp v{tree.version}")
    print(f"{counts['families']} họ · {counts['leaves']} loại "
          f"({counts['leaves'] + counts['aliases']} khai báo, {counts['aliases']} lọc trùng)"
          f" · {sum(1 for s in states.values() if s['generatable'])} sinh được")

    lines = (render_summary(tree, states, images) if args.summary
             else render_tree(tree, states, images))
    print("\n".join(lines))
    print("\n".join(render_engines(tree, states)))

    if images is not None:
        unknown = {name: n for name, n in images.items() if name not in tree}
        empty = [node_id for node_id, state in states.items()
                 if state["generatable"] and not images.get(node_id)]
        print(f"\n{args.dataset}: {sum(images.values())} ảnh, "
              f"{len([n for n in images if n in tree])} loại có mặt")
        if empty:
            print(f"  sinh được nhưng không có ảnh nào: {', '.join(empty)}")
        if unknown:
            # A label naming a type the tree does not have. Almost always a
            # dataset built before the hierarchy, which `tools/migrate_labels.py`
            # rewrites; occasionally a rules file pointing at a deleted node.
            print(f"  nhãn ngoài cây: {', '.join(f'{k} ({v})' for k, v in unknown.items())}")

    print(f"\n  {MARKS['ready']} sinh được   {MARKS['draft']} draft   "
          f"{MARKS['planned']} mới khai báo   = lọc trùng   {MARKS['clash']} mâu thuẫn")
    if faults:
        print(f"\n{len(faults)} vấn đề — chạy `make taxonomy-check` để xem chi tiết")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
