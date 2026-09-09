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
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from agent import client as llm_client  # noqa: E402
from agent import compose, compose_layout, planner, policy, variants  # noqa: E402
from agent import rules as agent_rules  # noqa: E402
from pipeline.invariants import CLEAN_FORCES  # noqa: E402

PLAN_NAME = "agent_plan.json"
REPORT_NAME = "agent_report.json"
RULES_DIR = "rules"
LAYOUTS_DIR = REPO_ROOT / "rulebase" / "layouts"


def table_layout_ids(layouts_dir: Path = LAYOUTS_DIR) -> set[str]:
    """Every layout id whose file lays out a real item table.

    Read off `rulebase/layouts/*.yaml` at call time -- a `columns:` list is
    what every renderer keys its `items_table()` call on regardless of family
    (till roll, A4 form, medical statement), so it is the one generic signal
    that a page has rows of items rather than fields or running text. Nothing
    here names a layout: a new table-bearing layout is picked up the next
    time this runs, and one that stops carrying a table drops out on its own.
    """
    import yaml  # noqa: PLC0415 -- only this helper needs it

    ids = set()
    for path in sorted(layouts_dir.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if spec.get("columns"):
            ids.add(str(spec.get("id") or path.stem))
    return ids


def report(out: Path, decisions, rules, pol, catalogue, elapsed: dict,
           feedback: dict | None = None) -> dict:
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
        "feedback": feedback or {},
        "coverage": planner.coverage(decisions, rules),
        "never_drawn": planner.unused(decisions, rules),
        # Drawable on paper and impossible in practice -- see planner.unreachable.
        "unreachable": planner.unreachable(rules),
        "elapsed_seconds": elapsed,
    }
    (out / REPORT_NAME).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def compose_new_layouts(args, out: Path) -> list[str]:
    """MỨC 3 as a step of a run: compose `--compose-layout N` new layouts.

    Runs `agent/compose_layout.py`'s own command, once per layout, in a
    subprocess -- not by importing and calling it. Three reasons, and the
    third is the one that matters:

    * that command already owns the seven gates, the registration and the
      rollback, and a second caller doing four of the seven is how the two
      drift apart;
    * `rulebase` and `sheets` cache the layout directory at import, and this
      writes into it -- the same reason `augment_layout.draws` is a subprocess;
    * **a layout that fails leaves nothing behind.** The command removes the
      file and reverts both registries itself, so a run that composes five and
      lands three continues with three rather than with a rule base naming two
      files that are not there.

    Which documents: `agent/constraints.yaml`'s reviewed list, intersected
    with the ones that actually have a visible third layer (§8.2). Read from
    the data, not listed here -- a document reviewed tomorrow joins without
    this file changing.
    """
    from agent import constraints as constraints_mod

    wanted = args.compose_document
    if not wanted:
        wanted = []
        for document in constraints_mod.load().documents():
            try:
                if compose_layout.layers(compose_layout.references(document)).free:
                    wanted.append(document)
            except compose_layout.ComposeError:
                continue
    if not wanted:
        print("[agent] mức 3: chưa chứng từ nào vừa được duyệt trong "
              "agent/constraints.yaml vừa có lớp 3 — bỏ qua bước soạn")
        return []

    made: list[str] = []
    for index in range(args.compose_layout):
        document = wanted[index % len(wanted)]
        # The id carries the run's seed, so two runs never race for one name
        # and a composed layout can be traced back to the run that made it.
        layout_id = f"{document}_c{args.seed}_{index:02d}"
        done = subprocess.run(
            [sys.executable, "-m", "agent.compose_layout",
             "--document", document, "--id", layout_id,
             "--seed", str(args.seed + index), "--write"],
            cwd=str(REPO_ROOT), capture_output=True, text=True)
        if done.returncode == 0:
            made.append(layout_id)
        else:
            tail = [line for line in (done.stdout or "").splitlines()
                    if line.strip().startswith("✗")]
            print(f"[agent] mức 3: {layout_id} trượt — "
                  f"{tail[-1].strip() if tail else 'xem log'}")
    if made:
        (out / "composed_layouts.json").write_text(
            json.dumps({"layouts": made, "seed": args.seed}, ensure_ascii=False,
                       indent=1) + "\n", encoding="utf-8")
    return made


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
    parser.add_argument(
        "--qualified", type=Path, default=None, metavar="JSON",
        help="keep only the dressings named in this file, which "
             "`python -m agent.distance --out` writes: the ones measured to move "
             "at least `--min` of a page's labelled runs relative to the phôi. "
             "Designing a dressing to look different and measuring that it does "
             "are not the same claim, and only the second one is checkable")
    parser.add_argument(
        "--llm-concurrency", type=int, default=1, metavar="N",
        help="prefetch N blocks of model proposals at once over separate "
             "threads instead of one at a time -- see agent.planner.plan's "
             "own docstring for what stays sequential regardless (applying a "
             "block, so reproducibility holds) and what does not (the "
             "diversity tally a concurrent block's prompt sees, which goes a "
             "few blocks stale). 1 keeps the old one-at-a-time behaviour.")
    parser.add_argument(
        "--compose-layout", type=int, default=0, metavar="N",
        help="MỨC 3: soạn N bố cục MỚI trước khi lập kế hoạch, rồi vẽ trên cả "
             "chúng. Model nhận k phôi cùng loại chứng từ làm bằng chứng và "
             "viết ra một cấu trúc chưa từng có; nó đi qua bảy cửa ải rồi mới "
             "được đăng ký, và cái nào trượt thì bị xoá cùng cả hai đăng ký. "
             "Chỉ những chứng từ đã duyệt trong agent/constraints.yaml mới "
             "được soạn. Xem agent/compose_layout.py.")
    parser.add_argument(
        "--compose-document", action="append", default=None, metavar="ID",
        help="chỉ soạn cho những chứng từ này (lặp lại cờ). Mặc định: mọi "
             "chứng từ constraints.yaml đã duyệt VÀ có lớp 3 nhìn thấy được")
    parser.add_argument(
        "--content-llm", action="store_true",
        help="let the model write store names, item names, and (medical "
             "documents) the diagnosis/comorbid pair, instead of "
             "rulebase/content.py drawing them from corpus. Opt-in, and NOT "
             "auto-enabled by VLM_LLM_URL the way planning is -- rewriting "
             "text on every page is a bigger behaviour change than picking "
             "among existing enum ids. See agent/compose.py. Numbers are "
             "never affected: amounts and totals are always rule-based.")
    parser.add_argument("--pressure", type=float, default=planner.DEFAULT_PRESSURE,
                        help="0 draws like the shipped sampler, 1 chases coverage")
    parser.add_argument(
        "--feedback", type=Path, default=None, metavar="JSON",
        help="the previous run's review, which `tools/critic_review.py` "
             "writes as feedback.json. Values it found on broken pages get "
             "drawn less often and pairs that only fail together stop being "
             "drawn at all -- which is how the reviewing agent reaches the "
             "generating one instead of just filing a report nobody reads")
    parser.add_argument(
        "--layouts-with-table", action="store_true",
        help="draw only layouts that lay out a real item table -- a letter, "
             "a questionnaire, a magazine page have nothing to switch off "
             "for. The set is read off rulebase/layouts/*.yaml at run time "
             "(see table_layout_ids), not written down here")
    parser.add_argument("--clean", action="store_true", help="no ageing at all")
    parser.add_argument("--template", default="auto",
                        help="page model; 'auto' is the sheet the layout belongs to")
    parser.add_argument(
        "--naming", default=None, metavar="TEMPLATE",
        help="output file name, e.g. '{document}_{index:03d}' -- a format "
             "string over `backend`, `index`, and any rule-base attribute a "
             "page was drawn with. Default keeps `{backend}_NNN`, see "
             "pipeline.config.DEFAULT_NAMING")
    parser.add_argument("--proof-workers", type=int, default=0,
                        help="0 uses --workers")
    parser.add_argument("--no-proof", action="store_true",
                        help="skip the field-box proof (proof/) drawn by default")
    parser.add_argument("--no-proof-layout", action="store_true",
                        help="skip the proof from layout_annotations "
                             "(proof_layout/), one box per region, coloured "
                             "by the 19-label docsynth vocabulary. Drawn by "
                             "default alongside proof/ and proof_words/ -- "
                             "a page from this driver is meant to be looked "
                             "at, not just trusted.")
    parser.add_argument("--no-proof-words", action="store_true",
                        help="skip the proof from word_annotations "
                             "(proof_words/), one box per word, same "
                             "palette as proof_layout, tagged by "
                             "field_role. Drawn by default, same reason.")
    parser.add_argument("--no-save-html", action="store_true",
                        help="skip writing each page's own markup beside its "
                             "image (html_000.html next to html_000.jpg). "
                             "Saved by default -- see "
                             "generators/html/render.py --save-html.")
    parser.add_argument("--plan-only", action="store_true",
                        help="decide and report, draw nothing")
    parser.add_argument(
        "--render-upto", type=int, default=0, metavar="N",
        help="plan all --count pages but draw only the first N of them. The "
             "plan is unchanged, so the coverage objective still balances over "
             "the whole run; raising N on the next invocation resumes -- the "
             "shards already carrying a DONE are skipped. This is how a long "
             "run is delivered in batches without the batches each becoming a "
             "differently-balanced dataset")
    parser.add_argument(
        "--resume", action="store_true",
        help="if the plan step was interrupted -- the process was killed, the "
             "model server dropped -- pick it back up from "
             f"<out>/{PLAN_NAME}.partial instead of asking the model again "
             "for pages it already answered. Only meaningful with the same "
             "--seed/--dressings/--qualified/--pressure as the run being "
             "resumed; verify() below still catches a mismatch that made a "
             "resumed page illegal, it just cannot tell you resumed for the "
             "wrong reason")
    args = parser.parse_args()

    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    clock: dict[str, float] = {}

    # 1-2. Dressings, then the rules root this run reads and writes through.
    started = time.time()
    catalogue = variants.build(count=args.dressings, seed=args.seed)
    if args.qualified:
        table = json.loads(args.qualified.read_text(encoding="utf-8"))
        keep = set(table.get("passed") or ())
        before = len(catalogue)
        # `livery` dressings are not measured against this bar: they are the
        # ones a prescribed form wears, and moving its geometry is the thing
        # they exist not to do.
        catalogue = [d for d in catalogue if d.level != "free" or d.id in keep]
        free = sum(1 for d in catalogue if d.level == "free")
        if not free:
            print(f"[agent] không dressing nào đạt ngưỡng {table.get('min')} "
                  f"trong {args.qualified}")
            return 1
        print(f"[agent] lọc theo khoảng cách >= {table.get('min')}: "
              f"{len(catalogue)}/{before} dressing giữ lại ({free} loại free)")
    pol = policy.load()

    # MỨC 3, và nó phải chạy TRƯỚC `materialise`: một bố cục soạn ra chỉ tồn
    # tại khi nó đã nằm trong `rulebase/rules/layout.yaml` và `blanks.yaml`,
    # và rules root của lượt chạy được dựng từ hai file ấy. Soạn sau là soạn
    # ra thứ kế hoạch không biết tới.
    if args.compose_layout:
        started = time.time()
        made = compose_new_layouts(args, out)
        clock["compose_layout"] = round(time.time() - started, 2)
        if made:
            print(f"[agent] mức 3: {len(made)} bố cục mới đăng ký — "
                  f"{', '.join(made)}")
        else:
            print("[agent] mức 3: không bố cục nào qua được hàng rào; "
                  "lượt chạy tiếp tục với các phôi đang có")

    root = agent_rules.materialise(out / RULES_DIR, catalogue, pol)
    agent_rules.activate(root)
    rules = agent_rules.compose(catalogue, pol)

    if args.layouts_with_table:
        keep = table_layout_ids()
        drop = {option.id for option in rules["layout"]} - keep
        rules = agent_rules.switch_off(rules, "layout", drop)
        print(f"[agent] --layouts-with-table: giữ {len(keep)}/{len(keep) + len(drop)} "
              f"bố cục có bảng hàng")

    # `handwriting.py` refuses to fake ink when WriteViT is absent, and it is
    # right to: a page whose label says a field was filled by hand and whose
    # pixels show a printed font is a lie. So the ink sources that need it are
    # switched off deliberately here, and the run says so, rather than dying on
    # whichever page first drew one.
    if agent_rules.writevit_missing() is not None:
        rules = agent_rules.switch_off(rules, "handwriting",
                                       agent_rules.NEEDS_WRITEVIT)
        print(f"[agent] không có WriteViT tại {agent_rules.writevit_missing()} — "
              f"tắt {', '.join(agent_rules.NEEDS_WRITEVIT)}; "
              f"chạy `python tools/writevit/setup.py` để bật lại")
    clock["rules"] = round(time.time() - started, 2)
    print(f"[agent] {len(catalogue)} dressing, rules -> {root}")

    # 3. The plan. A server if one is configured; the coverage objective if not.
    llm = llm_client.from_env()
    if llm is not None and not llm.alive():
        print(f"[agent] {llm.url} không trả lời — chuyển sang chế độ coverage")
        llm = None
    print(f"[agent] chế độ: {'llm ' + llm.model if llm else 'coverage (không có server)'}")

    weights: dict[str, dict[str, float]] = {}
    bans: list = []
    if args.feedback:
        from agent import critic  # noqa: PLC0415 -- only this branch needs it

        weights, bans = critic.load_feedback(args.feedback)
        listed = sum(len(v) for v in weights.values())
        print(f"[agent] phản hồi từ {args.feedback}: phạt {listed} giá trị, "
              f"cấm {len(bans)} cặp")
        for attribute, options in sorted(weights.items()):
            for option, factor in sorted(options.items(), key=lambda kv: kv[1]):
                print(f"          {attribute}={option} x{factor}")

    checkpoint = out / f"{PLAN_NAME}.partial"
    resume: list = []
    if args.resume:
        resume = planner.read(checkpoint)[:args.count]
        if resume:
            print(f"[agent] tiếp tục từ checkpoint {checkpoint.name}: "
                  f"{len(resume)}/{args.count} trang đã quyết định từ trước")
        else:
            print(f"[agent] --resume: không có checkpoint ở {checkpoint} "
                  "(hoặc rỗng) — chạy từ đầu")

    started = time.time()
    decisions = planner.plan(args.count, args.seed, rules, pol,
                             llm=llm, pressure=args.pressure,
                             concurrency=args.llm_concurrency,
                             pin=CLEAN_FORCES if args.clean else None,
                             penalty=weights, ban=bans,
                             resume=resume, checkpoint=checkpoint)
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
    # The checkpoint's only job was surviving a plan step that never finished.
    # One that did needs it no longer, and leaving it behind would make a
    # later --resume load a plan already superseded by args.count/rules.
    checkpoint.unlink(missing_ok=True)

    summary = planner.coverage(decisions, rules)
    print(f"[agent] {len(decisions)} trang, {summary['distinct_triples']} tổ hợp "
          f"document|layout|variant khác nhau, "
          f"{summary['by']['llm']} do llm chọn")

    # The plan stays whole; only the drawing is cut short. `agent_plan.json`
    # therefore describes 5000 pages whether 1000 or 5000 of them exist yet,
    # which is what makes the batches one dataset rather than five.
    drawing = decisions[:args.render_upto] if args.render_upto else decisions
    if args.render_upto:
        print(f"[agent] vẽ {len(drawing)}/{len(decisions)} trang trong lượt này")

    applied = {"from": str(args.feedback) if args.feedback else "",
               "penalties": weights, "ban": [[list(a), list(b)] for a, b in bans]}
    if args.plan_only:
        report(out, decisions, rules, pol, catalogue, clock, applied)
        return 0

    # 3b. Content, if asked for -- writes store names, item names, and (for
    # medical documents) the diagnosis/comorbid pair, in place of what
    # rulebase/content.py would have drawn from corpus. See agent/compose.py.
    content_overrides_path = None
    if args.content_llm:
        started = time.time()
        composed = compose.decide(drawing, rules, llm=llm, concurrency=args.llm_concurrency)
        content_overrides_path = out / "content_overrides.json"
        compose.write(composed, out / "compose.jsonl", content_overrides_path)
        clock["compose"] = round(time.time() - started, 2)
        written = sum(1 for page in composed if page.by == "llm")
        print(f"[agent] {written}/{len(composed)} trang có nội dung do llm viết "
              f"-> {content_overrides_path}")

    # 4. Render, through the pipeline the ordinary driver uses.
    from pipeline.config import Config
    from pipeline.run import execute

    # `build_plan` insists every layout it is handed gets at least one page
    # (see `pipeline/plan.py::uncovered`) -- right for the ordinary quota
    # driver, and wrong here read against ALL 52 shipped layouts: this run's
    # plan already names exactly which layout every page uses, so the only
    # universe that check should cover is the one this run actually drew
    # from, which shrinks with `--layouts-with-table` and with a small -n
    # alike. Leaving this `[]` (`pipeline/run.py`'s "no run.layouts" -> "every
    # shipped layout") is what made `-n 4` fail before either restriction was
    # a factor: 4 pages cannot cover a fixed 52.
    config = Config.from_dict({
        "run": {
            "out": str(out),
            "per_backend": len(drawing),
            "seed": args.seed,
            "workers": args.workers,
            "clean": bool(args.clean),
            "layouts": sorted({decision.layout for decision in drawing}),
            "force": [],
            "pairing": "paired",
            "template": args.template,
            "save_html": not args.no_save_html,
            "naming": args.naming,
        },
        "backends": ["html"],
        "shard": {"size": max(args.shard, 1)},
    })
    started = time.time()
    code = execute(config, runs={"html": planner.to_runs(drawing)},
                   content_overrides=content_overrides_path)
    clock["render"] = round(time.time() - started, 2)
    if code != 0:
        report(out, decisions, rules, pol, catalogue, clock, applied)
        return code

    # 4b. What was drawn, against what was decided. The one check that catches a
    # plan which never reached the renderer -- a failure with no other symptom.
    drifted = planner.audit_drawn(out, drawing, naming=config.naming)
    if drifted:
        print(f"[agent] {len(drifted)} trang được vẽ KHÁC với kế hoạch:")
        for problem in drifted[:10]:
            print(f"  - {problem}")
        report(out, decisions, rules, pol, catalogue, clock, applied)
        return 1
    print(f"[agent] {len(drawing)} trang: thuộc tính đã vẽ khớp kế hoạch")

    # 5. A proof beside every page -- all three of `proof_boxes.MODES` by
    # default, each its own opt-OUT flag rather than folded into one: someone
    # who wants only `layout`/`words` without the field-box one still needs to
    # drop exactly that one, not rebuild the whole set from nothing.
    wanted = [mode for mode, flag in (("blocks", not args.no_proof),
                                       ("layout", not args.no_proof_layout),
                                       ("words", not args.no_proof_words)) if flag]
    if wanted:
        import proof_boxes  # noqa: PLC0415 -- needs cv2, and step 4 does not

        for mode in wanted:
            started = time.time()
            written, total = proof_boxes.run(
                out, "html", workers=args.proof_workers or args.workers, mode=mode)
            clock[f"proof_{mode}"] = round(time.time() - started, 2)
            print(f"[agent] {written}/{total} ảnh proof ({mode}) -> "
                  f"{out / proof_boxes.OUT_DIRNAME[mode]}")
            if written != total:
                print(f"[agent] một số ảnh proof ({mode}) không vẽ được")
                code = 1

    payload = report(out, decisions, rules, pol, catalogue, clock, applied)
    print(f"[agent] báo cáo -> {out / REPORT_NAME}")
    never = {k: v for k, v in payload["never_drawn"].items() if v}
    if never:
        print(f"[agent] giá trị chưa bao giờ được vẽ: {never}")
    return code


if __name__ == "__main__":
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    raise SystemExit(main())
