"""One run where an LLM agent, not the seed, decides what every page is.

    python tools/agent_dataset.py -o data/5k_llm -n 5000 --workers 3

The ordinary driver (`tools/generate_dataset.py`) splits a quota over layouts
and lets `sample_recipe` draw the rest. This one hands the whole decision to
`agent/planner.py`: which kind of paper, which phôi, which dressing, which ink,
which ageing -- 5000 times, each recorded, each replayable.

Five stages, and the order matters
----------------------------------

1. **Dressings.** `agent/variants.py` composes a catalogue from seven axes.
2. **Rules.** `agent/rules.py` writes a rules root for this run alone: the
   shipped seven attributes, plus `variant`, plus the tag on every document
   that says whether it may be redressed at all. Exported through
   `VLM_RULES_ROOT`, so the planner here and the renderer subprocesses read the
   same rules -- a mismatch there would be a plan that describes pages nobody
   drew.
3. **Plan.** One decision per image, verified back through `sample_recipe`
   before a browser starts. An hour of rendering is a bad place to find out
   that a pin was illegal.
4. **Render.** `pipeline/run.py::execute`, unchanged, given the prepared runs.
   Everything the ordinary driver gets -- shards, resume, invariants per image,
   drift, assembly -- applies here because it is the same machinery.
5. **Proof.** One overlay per image, from the record beside it.

`--template auto` is the default and not an option worth changing: a dressing
is CSS, and the character grid has none. A run drawn on the grid would record
a `variant` that changed nothing, which is worse than not having one.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from agent import client as llm_client  # noqa: E402
from agent import planner, policy, variants  # noqa: E402
from agent import rules as agent_rules  # noqa: E402

PLAN_NAME = "agent_plan.json"
REPORT_NAME = "agent_report.json"
RULES_DIR = "rules"


def report(out: Path, decisions, rules, pol, catalogue, elapsed: dict) -> dict:
    """What this run decided, and what it covered. Written beside the images."""
    payload = {
        "images": len(decisions),
        "policy": {
            "classes": {name: pol.documents(name) for name in policy.ORDER},
            "reasons": pol.reasons,
            "reachable_variants": {name: len(ids) for name, ids
                                   in agent_rules.reachable(rules, pol).items()},
        },
        "variants": {
            "catalogue": len(catalogue),
            "space": variants.space(),
            "axes": {axis.name: {"level": axis.level, "values": sorted(axis.values)}
                     for axis in variants.AXES},
        },
        "coverage": planner.coverage(decisions, rules),
        "never_drawn": planner.unused(decisions, rules),
        "elapsed_seconds": elapsed,
    }
    (out / REPORT_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path, default=REPO_ROOT / "data" / "5k_llm")
    parser.add_argument("-n", "--count", type=int, default=5000)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--shard", type=int, default=125,
                        help="images per renderer process; one browser each")
    parser.add_argument("--dressings", type=int, default=48,
                        help="how many variants the catalogue holds")
    parser.add_argument("--pressure", type=float, default=planner.DEFAULT_PRESSURE,
                        help="0 draws like the shipped sampler, 1 chases coverage")
    parser.add_argument("--clean", action="store_true", help="no ageing at all")
    parser.add_argument("--template", default="auto",
                        help="page model; 'auto' is the sheet the layout belongs to")
    parser.add_argument("--proof-workers", type=int, default=0,
                        help="0 uses --workers")
    parser.add_argument("--no-proof", action="store_true")
    parser.add_argument("--plan-only", action="store_true",
                        help="decide and report, draw nothing")
    args = parser.parse_args()

    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    clock: dict[str, float] = {}

    # 1-2. Dressings, then the rules root this run reads and writes through.
    started = time.time()
    catalogue = variants.build(count=args.dressings, seed=args.seed)
    pol = policy.load()
    root = agent_rules.materialise(out / RULES_DIR, catalogue, pol)
    agent_rules.activate(root)
    rules = agent_rules.compose(catalogue, pol)
    clock["rules"] = round(time.time() - started, 2)
    print(f"[agent] {len(catalogue)} dressing, rules -> {root}")

    # 3. The plan. A server if one is configured; the coverage objective if not.
    llm = llm_client.from_env()
    if llm is not None and not llm.alive():
        print(f"[agent] {llm.url} không trả lời — chuyển sang chế độ coverage")
        llm = None
    print(f"[agent] chế độ: {'llm ' + llm.model if llm else 'coverage (không có server)'}")

    started = time.time()
    decisions = planner.plan(args.count, args.seed, rules, pol,
                             llm=llm, pressure=args.pressure)
    clock["plan"] = round(time.time() - started, 2)

    started = time.time()
    problems = planner.verify(decisions, rules)
    clock["verify"] = round(time.time() - started, 2)
    if problems:
        print(f"[agent] KẾ HOẠCH SAI: {len(problems)} vấn đề — không vẽ")
        for problem in problems[:20]:
            print(f"  - {problem}")
        return 1
    planner.write(out / PLAN_NAME, decisions)

    summary = planner.coverage(decisions, rules)
    print(f"[agent] {len(decisions)} trang, {summary['distinct_triples']} tổ hợp "
          f"document|layout|variant khác nhau, "
          f"{summary['by']['llm']} do llm chọn")

    if args.plan_only:
        report(out, decisions, rules, pol, catalogue, clock)
        return 0

    # 4. Render, through the pipeline the ordinary driver uses.
    from pipeline.config import Config
    from pipeline.run import execute

    config = Config.from_dict({
        "run": {
            "out": str(out),
            "per_backend": len(decisions),
            "seed": args.seed,
            "workers": args.workers,
            "clean": bool(args.clean),
            "layouts": [],
            "force": [],
            "pairing": "paired",
            "template": args.template,
        },
        "backends": ["html"],
        "shard": {"size": max(args.shard, 1)},
    })
    started = time.time()
    code = execute(config, runs={"html": planner.to_runs(decisions)})
    clock["render"] = round(time.time() - started, 2)
    if code != 0:
        report(out, decisions, rules, pol, catalogue, clock)
        return code

    # 4b. What was drawn, against what was decided. The one check that catches a
    # plan which never reached the renderer -- a failure with no other symptom.
    drifted = planner.audit_drawn(out, decisions)
    if drifted:
        print(f"[agent] {len(drifted)} trang được vẽ KHÁC với kế hoạch:")
        for problem in drifted[:10]:
            print(f"  - {problem}")
        report(out, decisions, rules, pol, catalogue, clock)
        return 1
    print(f"[agent] {len(decisions)} trang: thuộc tính đã vẽ khớp kế hoạch")

    # 5. A proof beside every page.
    if not args.no_proof:
        import proof_boxes  # noqa: PLC0415 -- needs cv2, and step 4 does not

        started = time.time()
        written, total = proof_boxes.run(
            out, "html", workers=args.proof_workers or args.workers)
        clock["proof"] = round(time.time() - started, 2)
        print(f"[agent] {written}/{total} ảnh proof -> {out / 'proof'}")
        if written != total:
            print("[agent] một số ảnh proof không vẽ được")
            code = 1

    payload = report(out, decisions, rules, pol, catalogue, clock)
    print(f"[agent] báo cáo -> {out / REPORT_NAME}")
    never = {k: v for k, v in payload["never_drawn"].items() if v}
    if never:
        print(f"[agent] giá trị chưa bao giờ được vẽ: {never}")
    return code


if __name__ == "__main__":
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    raise SystemExit(main())
