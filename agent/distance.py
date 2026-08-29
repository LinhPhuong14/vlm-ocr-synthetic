"""How different a dressed page is from the phôi it was dressed from.

    python -m agent.distance --dressings 64          # measure the catalogue

"Khác 70% so với layout gốc" needs an operational meaning before it can be a
gate, and the only honest one is measured on the drawn page rather than counted
off the CSS: two dressings can name six changes each and one of them can leave
the page looking untouched.

**The metric.** Draw the same recipe twice -- once with `variant=none`, once
with the dressing -- and compare where the labelled runs ended up. Both pages
carry the same text by construction (same seed, same content, same everything
but the dressing), so runs pair up by `kind` and reading order. A run counts as
moved when its box centre shifts by more than `MOVED` of the page's diagonal, or
its width or height changes by more than `RESIZED`. Distance is the share of
runs that moved, plus a term for runs that appear on one page and not the other.

    distance = (|moved| + |unpaired|) / (|paired| + |unpaired|)

**The bulk shift is subtracted first.** Wider margins push every run down by the
same amount, and a page that slid 15 mm as one piece is not a different layout
-- it is the same layout, lower. The median displacement over all pairs is the
dressing's bulk shift; what is measured is what moved *relative* to that. Before
this, `le_rong` scored 1.000 by translating the page and rearranging nothing.

Deliberately not pixels: a tint changes every pixel and moves nothing, and a
metric that called that "100% different" would be measuring paint again, which
is exactly the complaint this is answering.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# A run has moved if its centre travels more than this share of the page
# diagonal, or if either side changes by more than the second figure. Both are
# deliberately coarse: sub-millimetre drift from a border width is not what
# anybody means by a different layout.
MOVED = 0.02
RESIZED = 0.12


def _centre(box: dict) -> tuple[float, float, float, float]:
    quad = box.get("quad")
    if isinstance(quad, list) and len(quad) >= 4:
        xs = [float(p[0]) for p in quad[:4]]
        ys = [float(p[1]) for p in quad[:4]]
    else:
        bbox = box.get("bbox") or {}
        xs = [float(bbox.get("x1", 0)), float(bbox.get("x2", 0))]
        ys = [float(bbox.get("y1", 0)), float(bbox.get("y2", 0))]
    return (sum(xs) / len(xs), sum(ys) / len(ys), max(xs) - min(xs), max(ys) - min(ys))


def _runs(record: dict) -> dict[str, list[tuple]]:
    """Box geometry per kind, in reading order, plus the page size."""
    from pipeline import record as schema

    out: dict[str, list[tuple]] = defaultdict(list)
    for box in schema.boxes(record):
        out[str(box.get("kind", "?"))].append(_centre(box))
    return out


def compare(plain: dict, dressed: dict) -> dict:
    """The share of labelled runs the dressing moved, resized or removed."""
    from pipeline import record as schema

    width, height = schema.page_size(dressed) or (0, 0)
    diagonal = math.hypot(width or 1, height or 1)
    left, right = _runs(plain), _runs(dressed)

    # Every pair's displacement, and the median of them. The median is the
    # dressing's bulk shift -- wider margins push the whole page down, and a
    # page that slid 15 mm as one piece is not a different layout, it is the
    # same layout lower. Subtracting it leaves only runs that moved RELATIVE to
    # the rest, which is what rearranging blocks actually does.
    pairs: list[tuple[tuple, tuple]] = []
    unpaired = 0
    for kind in set(left) | set(right):
        a, b = left.get(kind, []), right.get(kind, [])
        unpaired += abs(len(a) - len(b))
        pairs.extend(zip(a, b))

    if pairs:
        dxs = sorted(two[0] - one[0] for one, two in pairs)
        dys = sorted(two[1] - one[1] for one, two in pairs)
        bulk_x, bulk_y = dxs[len(dxs) // 2], dys[len(dys) // 2]
    else:
        bulk_x = bulk_y = 0.0

    paired = moved = 0
    for one, two in pairs:
        paired += 1
        shift = math.hypot((two[0] - one[0]) - bulk_x,
                           (two[1] - one[1]) - bulk_y) / diagonal
        grew = (abs(one[2] - two[2]) / max(one[2], 1) > RESIZED
                or abs(one[3] - two[3]) / max(one[3], 1) > RESIZED)
        if shift > MOVED or grew:
            moved += 1
    total = paired + unpaired
    if not total:
        return {"distance": 0.0, "paired": 0, "moved": 0, "unpaired": 0}
    return {
        "distance": round((moved + unpaired) / total, 4),
        "paired": paired, "moved": moved, "unpaired": unpaired,
        "bulk_shift": [round(bulk_x, 1), round(bulk_y, 1)],
        "page": [width, height],
    }


def render(out: Path, seed: int, force: dict[str, str], rules_root: Path) -> dict | None:
    """One page, drawn with these pins. The record, or None if it did not draw."""
    jobs = out / "jobs.json"
    jobs.write_text(json.dumps([{"layout": force["layout"], "seed": seed,
                                 "count": 1, "force": force}]), encoding="utf-8")
    environment = dict(os.environ, VLM_RULES_ROOT=str(rules_root))
    command = [str(REPO_ROOT / "generators" / "html" / ".venv" / "bin" / "python"),
               str(REPO_ROOT / "generators" / "html" / "render.py"),
               "-o", str(out), "--jobs", str(jobs), "--template", "auto"]
    done = subprocess.run(command, cwd=REPO_ROOT, env=environment,
                          capture_output=True, text=True)
    if done.returncode != 0:
        return None
    records = sorted(out.glob("html_*.json"))
    if not records:
        return None
    return json.loads(records[0].read_text(encoding="utf-8"))


def measure(dressing_id: str, layout: str, document: str, seed: int,
            rules_root: Path) -> dict | None:
    """Distance for one dressing on one phôi, or None if either page failed."""
    base = {"document": document, "layout": layout}
    with tempfile.TemporaryDirectory(prefix="dist-plain-") as one, \
            tempfile.TemporaryDirectory(prefix="dist-dressed-") as two:
        plain = render(Path(one), seed, {**base, "variant": "none"}, rules_root)
        dressed = render(Path(two), seed, {**base, "variant": dressing_id}, rules_root)
    if plain is None or dressed is None:
        return None
    return compare(plain, dressed)


__all__ = ["MOVED", "RESIZED", "compare", "measure", "render"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dressings", type=int, default=64)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--layouts", nargs="+", default=None)
    parser.add_argument("--out", type=Path, default=None,
                        help="write the qualified set here, for --qualified")
    parser.add_argument("--min", type=float, default=0.70, dest="minimum",
                        help="a dressing qualifies at or above this distance")
    args = parser.parse_args()

    from agent import policy, variants
    from agent import rules as agent_rules

    catalogue = variants.build(count=args.dressings, seed=args.seed)
    pol = policy.load()
    root = agent_rules.materialise(
        Path(tempfile.mkdtemp(prefix="dist-rules-")), catalogue, pol)
    built = agent_rules.compose(catalogue, pol)
    reach = agent_rules.reachable(built, pol)

    # One free document per layout family, so a dressing is judged where it is
    # actually allowed to be worn.
    by_layout: dict[str, str] = {}
    for document in pol.documents("free"):
        for option in built["layout"]:
            if option.allowed(next(o.tags for o in built["document"]
                                   if o.id == document)):
                by_layout.setdefault(option.id, document)
    layouts = args.layouts or sorted(by_layout)

    rows = []
    for dressing in catalogue:
        if dressing.level != "free":
            continue
        scores = []
        for layout in layouts:
            document = by_layout.get(layout)
            if not document or dressing.id not in reach.get(document, ()):
                continue
            got = measure(dressing.id, layout, document, args.seed, root)
            if got:
                scores.append(got["distance"])
        if scores:
            rows.append({"id": dressing.id, "axes": dressing.axes,
                         "mean": round(sum(scores) / len(scores), 4),
                         "min": min(scores), "max": max(scores),
                         "layouts": len(scores)})
            print(f"{rows[-1]['mean']:.3f}  {dressing.id}")
    rows.sort(key=lambda r: -r["mean"])
    passed = [r["id"] for r in rows if r["mean"] >= args.minimum]
    if args.out:
        args.out.write_text(json.dumps({
            "min": args.minimum, "seed": args.seed, "dressings": args.dressings,
            "layouts": layouts, "moved": MOVED, "resized": RESIZED,
            "passed": passed, "rows": rows,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n-> {args.out}")
    if rows:
        means = [r["mean"] for r in rows]
        print(f"{len(rows)} dressing đo được | trung bình {sum(means)/len(means):.3f} "
              f"| cao nhất {max(means):.3f} | đạt >={args.minimum}: {len(passed)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
