"""Review a finished set, write the feedback, write the guideline.

    python tools/critic_review.py --dataset data/5k_llm
    python tools/critic_review.py --dataset data/5k_llm --repair 40

The second agent, as a command. It reads a dataset the way a consumer of that
dataset would -- images and records, nothing else -- and leaves three things
behind:

    feedback.json    the findings, and the weights the next run should use
    feedback.md      the same, as something a person reads
    guideline/       what to tell the LLM that replaces the coverage objective

`--repair` closes the loop the rest of the way. It takes the pages the review
called broken, redraws each with the value the review blames swapped for
another legal one, and reviews the result: the report then says how many of
them came back clean. That is the difference between a reviewer that complains
and a reviewer the pipeline listens to -- and it is measured rather than
asserted, because a repair that fixes nothing should be visible as a repair
that fixes nothing.

Run it with the renderer's interpreter, which is the one that has OpenCV:

    generators/html/.venv/bin/python tools/critic_review.py --dataset ...
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from agent import critic, guideline, policy  # noqa: E402

FEEDBACK = "feedback.json"
REPORT = "feedback.md"
REPAIR = "repair.json"


def rules_root(dataset: Path) -> Path:
    """Which rules directory this set was drawn through.

    A run materialises its own root beside the images (`agent/rules.py`) with
    the `variant` attribute in it; a set from the ordinary driver has none and
    falls back to the shipped rules.
    """
    from rulebase import spec

    root = dataset / "rules"
    return root.resolve() if root.is_dir() else Path(spec.RULES_ROOT)


def _rules_for(dataset: Path):
    """The rules this set was drawn through, loaded from that root.

    Passed as an argument rather than through `VLM_RULES_ROOT`, because
    `rulebase.spec` reads that variable once at import time: setting it here
    would be too late for any process that has already imported the module, and
    the symptom is not an error -- it is a different set of attributes. That
    silently cost the repair pass every page it tried, planning against the
    shipped eleven attributes (`handwriting`, `toner`, `drum`, `rollers`, no
    `variant`) and then failing to draw what it planned.

    The variable is still exported, because the renderer subprocesses read it.
    """
    root = rules_root(dataset)
    from agent import rules as agent_rules
    from rulebase import spec

    agent_rules.activate(root)
    return spec.load_rules(root)


def repair(dataset: Path, review: critic.Review, limit: int,
           backend: str = "html") -> dict:
    """Redraw the broken pages without what the review blames, and re-review.

    One page at a time through `agent/distance.py::render`, which is the same
    subprocess call the renderer makes, into a scratch directory: nothing in
    the reviewed set is touched. The point is not to patch the delivered images
    -- a dataset that has been edited in place cannot be reproduced from its
    plan -- it is to find out whether the penalty the review proposes would
    have helped, before a five-thousand-page run bets on it.
    """
    from agent import distance

    weights = critic.penalties(review)
    blamed = {(attribute, option) for attribute, options in weights.items()
              for option in options}
    if not blamed:
        return {"attempted": 0, "note": "không có giá trị nào bị quy trách nhiệm"}

    attributes = critic.attributes_of(dataset, backend)
    seeds = {name: int(entry.get("seed") or 0) for name, entry in
             (json.loads((dataset / backend / "synthesis.json")
                         .read_text(encoding="utf-8")).get("pages") or {}).items()}
    by_page: dict[str, list[critic.Finding]] = {}
    for finding in review.findings:
        if finding.severity == critic.SEVERE:
            by_page.setdefault(finding.page, []).append(finding)

    rules = _rules_for(dataset)
    root = rules_root(dataset)
    order = tuple(rules.keys())
    pol = policy.load()

    rows: list[dict] = []
    from agent import planner

    for page in sorted(by_page)[:limit]:
        chosen = attributes.get(page)
        if not chosen:
            continue
        guilty = [(a, o) for a, o in chosen.items() if (a, o) in blamed]
        if not guilty:
            continue
        # Re-decide this one page with the blamed values banned outright, then
        # draw it. `plan` of length one keeps the walk's clash retries.
        seed = seeds.get(page, 0)
        penalty = {attribute: {option: 0.0001} for attribute, option in guilty}
        try:
            decision = planner.plan(1, seed, rules, pol, order=order,
                                    penalty=penalty)[0]
        except (ValueError, planner.Clash) as problem:
            rows.append({"page": page, "ok": False, "note": str(problem)})
            continue
        with tempfile.TemporaryDirectory(prefix="repair-") as scratch:
            record = distance.render(Path(scratch), seed, decision.force, root)
            if record is None:
                rows.append({"page": page, "ok": False, "note": "không vẽ được"})
                continue
            image = next(Path(scratch).glob("html_*.jpg"), None)
            # The redrawn page carries its own mark report, in its own
            # `synthesis.json`, so the `che_box` check applies to the repair as
            # much as to the original.
            struck = critic.marks_of(Path(scratch), backend="")
            after = critic.read_page(record, page,
                                     next(iter(struck.values()), []))
            if image is not None:
                after += critic.read_paper(record, image, page)
        was = [f.code for f in by_page[page] if f.severity == critic.SEVERE]
        now = [f.code for f in after if f.severity == critic.SEVERE]
        rows.append({"page": page, "ok": not now, "before": was, "after": now,
                     "swapped": [list(g) for g in guilty],
                     "drew": decision.force})

    fixed = sum(1 for row in rows if row.get("ok"))
    return {"attempted": len(rows), "fixed": fixed,
            "share": round(fixed / max(len(rows), 1), 3),
            "blamed": sorted(f"{a}={o}" for a, o in blamed),
            "pages": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--backend", default="html")
    parser.add_argument("--out", type=Path, default=None,
                        help="where feedback.json and feedback.md go "
                             "(default: inside the dataset)")
    parser.add_argument("--guideline", type=Path, default=guideline.DEFAULT_DIR,
                        help="where the three markdown files go")
    parser.add_argument("--no-guideline", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0,
                        help="review only the first N pages")
    parser.add_argument("--no-paper", action="store_true",
                        help="record checks only; no image is opened")
    parser.add_argument("--lift", type=float, default=critic.LIFT,
                        help="blame a value at or above this fault ratio")
    parser.add_argument("--repair", type=int, default=0, metavar="N",
                        help="redraw up to N broken pages without the value "
                             "the review blames, and report how many came "
                             "back clean")
    args = parser.parse_args()

    dataset: Path = args.dataset.resolve()
    if not (dataset / args.backend).is_dir():
        print(f"[critic] không thấy {dataset / args.backend}")
        return 1
    out: Path = (args.out or dataset).resolve()
    out.mkdir(parents=True, exist_ok=True)

    review = critic.sweep(dataset, args.backend, paper=not args.no_paper,
                          workers=args.workers, limit=args.limit)
    severe = review.bad_pages()
    print(f"[critic] {review.pages} trang, {len(review.findings)} lỗi, "
          f"{len(severe)} trang lỗi nặng "
          f"({len(severe) / max(review.pages, 1) * 100:.1f}%)")
    for code, times in review.by_code().items():
        print(f"          {code:16s} {times}")

    payload = critic.feedback(review, lift=args.lift)
    if args.repair:
        payload["repair"] = repair(dataset, review, args.repair, args.backend)
        (out / REPAIR).write_text(
            json.dumps(payload["repair"], ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        done = payload["repair"]
        print(f"[critic] vá thử {done.get('attempted', 0)} trang: "
              f"{done.get('fixed', 0)} trang sạch lại "
              f"({done.get('share', 0) * 100:.0f}%) -> {out / REPAIR}")

    (out / FEEDBACK).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / REPORT).write_text(critic.report(review, lift=args.lift),
                              encoding="utf-8")
    print(f"[critic] {out / FEEDBACK}")
    print(f"[critic] {out / REPORT}")

    if not args.no_guideline:
        rules = _rules_for(dataset)
        written = guideline.write(args.guideline, rules, policy.load(), review)
        print(f"[critic] guideline -> {args.guideline}")
        for name, size in written.items():
            print(f"          {name:18s} {size:>6,} ký tự")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    raise SystemExit(main())
