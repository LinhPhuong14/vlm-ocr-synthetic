"""Every phôi, beside every way this repository knows to rebuild it.

    python tools/layout_gallery.py -o data/layout_augment

`data/5k_llm` answers "what does a run look like". It does not answer "what did
the augmentation actually do to *this* phôi", because a phôi's five hundred
pages are scattered through five thousand and each wears a different ink, a
different ageing and a different mark. Nobody can see a layout change through
that.

So this is the other view of the same machinery: one directory per layout, the
bare phôi first, then its rebuilds, each drawn from **the same seed and the same
document with the ageing pinned off** -- so the only thing that differs between
two images in a directory is the architecture. Beside each image, its proof with
every box tagged, and beside the set, a report saying in words what each rebuild
changed against the phôi and how much of the page it measurably moved.

How many rebuilds each phôi gets
--------------------------------

* A phôi that carries a **legally prescribed** document gets **2**, and both are
  drawn from the designs marked `graphic` -- the owner's decision that a
  prescribed form may be redrawn in a more designed direction, provided it still
  reads as an official piece.
* Every other phôi gets **7**.

A thermal roll gets its rebuilds from `redesign.NARROW`, because a sidebar
does not fit on 80 mm of paper and the seven roll designs exist for exactly
this reason.

**This directory deliberately relaxes the production policy.** In a run,
`agent/policy.yaml` refuses to let a prescribed document be restructured at all,
and that has not changed -- `agent/rules.py::variant_options` still enforces it
everywhere else. Here the class constraint is dropped on purpose, because the
question this folder answers is "what would it look like", which you cannot show
by refusing to draw it. The report names every document whose class was
overridden, so nobody mistakes the gallery for the policy.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from agent import critic, distance, policy as policy_module, redesign  # noqa: E402
from agent import rules as agent_rules  # noqa: E402
from rulebase import spec  # noqa: E402
from rulebase.spec import Option  # noqa: E402

BASELINE = "goc"
LOCKED_COUNT = 2
FREE_COUNT = 7

# Pinned on every page in the gallery. A layout comparison is about geometry,
# and a photocopy chain is the loudest thing on any page it runs on.
NEUTRAL = {"ornament": "no_ornament", "augmentation": "pristine"}

# A rebuild that moved less than this share of the page did not happen: the
# selectors matched nothing on this family. Not a bar on how different a design
# has to be -- that is a judgement the report leaves to the reader with a number
# beside it -- but a floor under "did the CSS reach this phôi at all".
NOTHING = 0.05
# How many times a phôi may swap a rejected design for the next in its pool.
RETRIES = 3


def options(catalogue) -> list[Option]:
    """The `variant` attribute for the gallery: no class constraint at all.

    `agent/rules.py::variant_options` writes `requires: [aug_free]` on a free
    dressing, which is the whole mechanism that stops a birth certificate being
    restructured in a run. Here that constraint is dropped and only the
    physical one is kept -- a design that needs a full-width sheet still cannot
    be worn by a till roll, because that is about paper rather than about law.
    """
    out = [Option.from_dict({
        "id": agent_rules.NONE_ID, "weight": 1.0,
        "params": {"label": "phôi gốc, không dựng lại", "level": "locked",
                   "css": ""},
    }, agent_rules.ATTRIBUTE)]
    for dressing in catalogue:
        constraint = ({"excludes": [agent_rules.TILL_TAG]}
                      if dressing.wide_only else {})
        out.append(Option.from_dict({
            "id": dressing.id, "weight": 1.0,
            "tags": [f"dressed_{dressing.level}"],
            **constraint,
            "params": {"label": dressing.label, "level": dressing.level,
                       "axes": dressing.axes, "css": dressing.css,
                       "moves": [list(move) for move in dressing.moves]},
        }, agent_rules.ATTRIBUTE))
    return out


def materialise(root: Path, catalogue, pol) -> Path:
    """A rules root for the gallery: the shipped rules plus this `variant`.

    Composed and written out through `pipeline.config.materialise_rules`, not
    copied. Copying the yaml files loses the params: `rulebase/document/` and
    its siblings sit BESIDE `rulebase/rules/` rather than inside it, so a
    copied tree has every option with an empty `params`, and the first
    newspaper it drew died on a `Receipt` with no masthead. The composed shape
    carries params inline, which is what a generated tree is for.
    """
    from pipeline.config import materialise_rules

    rules = spec.load_rules()
    order = list(rules.keys())
    order.insert(order.index("layout") + 1, agent_rules.ATTRIBUTE)
    built = {name: (options(catalogue) if name == agent_rules.ATTRIBUTE
                    else rules[name]) for name in order}
    if root.exists():
        shutil.rmtree(root)
    return materialise_rules(built, Path(root))


def pairing(rules, pol) -> list[dict]:
    """One row per layout: which document shows it, and which class that is.

    The document is the first one the layout admits, in id order, so a rerun
    draws the same gallery. Where a layout admits documents of several classes
    the widest one wins -- showing a phôi through its most restricted document
    would understate what the phôi can do.
    """
    documents = {option.id: option for option in rules["document"]}
    rows = []
    for layout in rules["layout"]:
        admitted = [name for name, option in sorted(documents.items())
                    if layout.allowed(option.tags)]
        if not admitted:
            continue
        ranked = sorted(admitted,
                        key=lambda name: (-policy_module.ORDER.index(pol.klass(name)),
                                          name))
        document = ranked[0]
        rows.append({"layout": layout.id, "document": document,
                     "klass": pol.klass(document),
                     "narrow": agent_rules.TILL_TAG in layout.tags,
                     "documents": admitted})
    return rows


# A sheet no taller than this many times its width is a card, not a page.
CARD_RATIO = 1.15


def shape_of(row: dict, size: tuple[int, int] | None) -> str:
    """`roll`, `card` or `page` -- which pool of designs this phôi can wear.

    The roll comes from the rules (`till_receipt` is a tag). The card is
    measured, not declared: the four landscape certificates are only landscape
    because `insurance.py` asks for `A6_LANDSCAPE` deep inside a build
    function, and a list of names kept here would be a second copy of that
    fact, wrong the first time somebody adds a fifth.
    """
    if row["narrow"]:
        return "roll"
    if size and size[0] and size[1] / float(size[0]) <= CARD_RATIO:
        return "card"
    return "page"


def pool_for(row: dict, shape: str = "page") -> list:
    """Every rebuild this phôi could wear, in the order they are tried."""
    pool = list({"roll": redesign.NARROW, "card": redesign.CARD,
                 "page": redesign.WIDE}[shape])
    if row["klass"] == "locked":
        # Graphic first, then the rest. A prescribed phôi is meant to get the
        # designed-piece treatment, but two rebuilds it can actually wear beat
        # nought rebuilds of the preferred kind: when both graphic card designs
        # were rejected on the moto slip, the folder for that phôi came out
        # empty, which answers nothing.
        return ([d for d in pool if d.graphic]
                + [d for d in pool if not d.graphic]) or pool
    return pool


def wanted_count(row: dict) -> int:
    return LOCKED_COUNT if row["klass"] == "locked" else FREE_COUNT


def rejected(entry: dict, inherited: set[str] = frozenset()) -> str:
    """Why this rebuild is not worth keeping, or "" if it is.

    Two reasons, and they are different failures. A rebuild the reviewer faults
    is a design that reached this phôi and broke it. A rebuild that measured
    nothing is a design that never reached it at all -- `the_chia_hai_cot`
    scored 0.000 on the health card, because that card is an absolutely
    positioned panel and CSS columns have nothing to do on one. Neither belongs
    in a folder whose whole claim is "this is what the augmentation does".

    `inherited` is what the bare phôi already gets wrong, and a design is not
    blamed for it. `magazine_contents` overlapped its own hero kicker with its
    own page number, so all nine designs offered to it came back faulted and it
    ended the run with one rebuild instead of seven -- for a bug that was
    nothing to do with any of them.
    """
    if not entry.get("drawn"):
        return "không vẽ được"
    severe = [f for f in entry.get("findings") or ()
              if f["severity"] == critic.SEVERE and f["code"] not in inherited]
    if severe:
        return f"{len(severe)} lỗi nặng ({severe[0]['code']})"
    moved = (entry.get("distance") or {}).get("distance", 0.0)
    if moved < NOTHING:
        return f"không đổi gì ({moved * 100:.1f}%)"
    return ""


def draw(out: Path, row: dict, designs: list, seed: int, root: Path,
         baseline: bool = True) -> list[dict]:
    """The phôi and its rebuilds, in one renderer invocation."""
    out.mkdir(parents=True, exist_ok=True)
    base = {"document": row["document"], "layout": row["layout"], **NEUTRAL}
    wanted = ([agent_rules.NONE_ID] if baseline else []) + [d.id for d in designs]
    jobs = [{"layout": row["layout"], "seed": seed, "count": 1,
             "force": {**base, "variant": variant}} for variant in wanted]
    (out / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False),
                                   encoding="utf-8")
    command = [str(REPO_ROOT / "generators" / "html" / ".venv" / "bin" / "python"),
               str(REPO_ROOT / "generators" / "html" / "render.py"),
               "-o", str(out), "--jobs", str(out / "jobs.json"),
               "--template", "auto"]
    done = subprocess.run(command, cwd=REPO_ROOT,
                          env=dict(os.environ, VLM_RULES_ROOT=str(root)),
                          capture_output=True, text=True)
    if done.returncode != 0:
        return [{"variant": variant, "drawn": False,
                 "note": done.stderr.strip()[-300:]} for variant in wanted]

    drawn = sorted(out.glob("html_*.jpg"))
    rows: list[dict] = []
    offset = 0 if baseline else 1
    for index, variant in enumerate(wanted):
        if index >= len(drawn):
            rows.append({"variant": variant, "drawn": False,
                         "note": "renderer vẽ thiếu trang"})
            continue
        image = drawn[index]
        name = (BASELINE if variant == agent_rules.NONE_ID
                else f"v{index + offset}_{variant}")
        target = out / f"{name}.jpg"
        image.replace(target)
        image.with_suffix(".json").replace(out / f"{name}.json")
        rows.append({"variant": variant, "drawn": True, "name": name,
                     "image": target.name})
    for stray in ("jobs.json", "imagetimes.jsonl"):
        (out / stray).unlink(missing_ok=True)
    return rows


def measure(out: Path, rows: list[dict]) -> None:
    """How much of the page each rebuild moved, against the phôi beside it.

    Read off the two records rather than drawn again: they came from the same
    seed and the same document in one invocation, so the runs pair up exactly
    the way `agent/distance.py` needs and the second render would be waste.
    """
    plain = next((row for row in rows if row.get("name") == BASELINE), None)
    if plain is None or not plain.get("drawn"):
        return
    before = json.loads((out / f"{BASELINE}.json").read_text(encoding="utf-8"))
    for row in rows:
        if not row.get("drawn") or row["name"] == BASELINE:
            continue
        after = json.loads((out / f"{row['name']}.json").read_text(encoding="utf-8"))
        row["distance"] = distance.compare(before, after)


def proofs(out: Path, rows: list[dict], gallery: Path, layout: str) -> int:
    """One tagged proof per image, under `<gallery>/proof/<layout>/`.

    A sibling tree, not a subdirectory of the pages, and not
    `<name>_proof.jpg` beside them. Both of those put an image with no record
    next to one that has a record, and this repository treats that as an error
    in two places: `critic.sweep` counted eight proofs as eight broken pages,
    and `tests/test_record.py` walks every committed directory holding a
    `synthesis.json` and fails on any image with no record. `data/5k_llm/`
    already keeps `html/` and `proof/` apart for the same reason.
    """
    import proof_boxes

    directory = gallery / "proof" / layout
    directory.mkdir(parents=True, exist_ok=True)
    written = 0
    for row in rows:
        if not row.get("drawn"):
            continue
        if proof_boxes.draw(out / f"{row['name']}.jpg", out / f"{row['name']}.json",
                            directory / f"{row['name']}.jpg", tags=True):
            row["proof"] = f"proof/{layout}/{row['name']}.jpg"
            written += 1
    return written


def review(out: Path, rows: list[dict]) -> list[dict]:
    """Run the reviewing agent over what was just drawn.

    The gallery is where a design is seen first, so it is where a design's own
    bugs should be caught -- and they were: `cot_nhan_dien_trai` indented the
    item table twice and pushed the amount column off the sheet, which nobody
    noticed until `critic.tran_le` said so. A design that draws a broken page
    should not be able to reach a five-thousand-page run through a folder that
    only ever showed it approvingly.
    """
    found: list[dict] = []
    for row in rows:
        if not row.get("drawn"):
            continue
        record = json.loads((out / f"{row['name']}.json").read_text(encoding="utf-8"))
        struck = critic.marks_of(out, backend="")
        problems = critic.read_page(record, row["name"],
                                    struck.get(f"{row['name']}.jpg", []))
        image = out / f"{row['name']}.jpg"
        if image.exists():
            problems += critic.read_paper(record, image, row["name"])
        row["findings"] = [f.to_dict() for f in problems]
        found.extend(row["findings"])
    return found


def layout_report(row: dict, rows: list[dict], designs: list) -> str:
    """The per-layout page: what each rebuild changed, and by how much."""
    by_id = {design.id: design for design in designs}
    inherited = row.get("inherited") or []
    lines = [
        f"# `{row['layout']}`",
        "",
        f"Chứng từ dùng để dựng: `{row['document']}` — hạng **{row['klass']}**"
        f"{' (phôi cuộn giấy nhiệt)' if row['narrow'] else ''}.",
        "",
    ]
    if inherited:
        lines += [f"> Bản thân phôi gốc đã có lỗi `{'`, `'.join(inherited)}` — "
                  f"mọi bản dựng lại đều thừa hưởng, nên không tính cho thiết "
                  f"kế nào.", ""]
    lines += [
        f"Phôi gốc: `{BASELINE}.jpg` "
        f"(proof: `../proof/{row['layout']}/{BASELINE}.jpg`). "
        f"Tất cả các bản dưới đây vẽ từ **cùng một hạt giống, cùng một chứng "
        f"từ, tắt hết hiệu ứng làm cũ và không đóng dấu** — nên khác nhau chỗ "
        f"nào thì đúng là bố cục khác nhau chỗ ấy.",
        "",
    ]
    for entry in rows:
        if not entry.get("drawn") or entry["name"] == BASELINE:
            continue
        design = by_id.get(entry["variant"])
        measured = entry.get("distance") or {}
        lines += [
            f"## `{entry['name']}`",
            "",
            f"**{design.label if design else entry['variant']}**",
            "",
            f"Đo được: **{measured.get('distance', 0) * 100:.0f}%** số ô chữ "
            f"đã đổi chỗ so với phôi "
            f"({measured.get('moved', 0)}/{measured.get('paired', 0)} ô ghép "
            f"được, {measured.get('unpaired', 0)} ô chỉ có ở một bên; đã trừ "
            f"độ dịch chung {measured.get('bulk_shift', [0, 0])}).",
            "",
        ]
        if design and design.changes:
            lines += ["| mặt | phôi gốc | bản dựng lại |", "|---|---|---|"]
            lines += [f"| {a} | {b} | {c} |" for a, b, c in design.changes]
            lines.append("")
        if design and design.moves:
            lines += ["Khối được xếp lại: "
                      + "; ".join(f"`{how}` {' → '.join(rest)}"
                                  for how, *rest in design.moves), ""]
        lines += [f"Ảnh: `{entry['name']}.jpg` — proof: "
                  f"`{entry.get('proof', '—')}`", ""]
        problems = [f for f in entry.get("findings") or ()
                    if f["severity"] == critic.SEVERE]
        if problems:
            lines += ["Bộ phản biện soi ra:", ""]
            lines += [f"- **{f['severity']}** `{f['code']}` — {f['detail']}"
                      for f in problems[:8]]
            lines.append("")
    dropped = row.get("dropped") or []
    if dropped:
        lines += ["## Những bản bị loại", "",
                  "Vẽ ra rồi bỏ đi, vì bộ phản biện bắt lỗi nặng hoặc vì đo ra "
                  "không đổi gì — nghĩa là CSS của thiết kế ấy không với tới "
                  "được họ giấy này. Thiết kế kế tiếp trong danh sách được "
                  "lấy thay.", "",
                  "| thiết kế | lý do |", "|---|---|"]
        lines += [f"| `{d['variant']}` | {d['why']} |" for d in dropped]
        lines.append("")
    return "\n".join(lines)


def overview(gallery: dict) -> str:
    """The top-level report: the whole gallery in one table."""
    rows = gallery["layouts"]
    total = sum(len(row["variants"]) - 1 for row in rows)
    scores = [entry["distance"]["distance"] for row in rows
              for entry in row["variants"]
              if entry.get("distance") and entry["name"] != BASELINE]
    over = [s for s in scores if s >= 0.70]
    lines = [
        "# Thư viện dựng lại bố cục",
        "",
        f"{len(rows)} phôi, {total} bản dựng lại, mỗi bản kèm ảnh proof có "
        f"tag từng box.",
        "",
        "| | |",
        "|---|---:|",
        f"| số phôi | {len(rows)} |",
        f"| bản dựng lại | {total} |",
        f"| đo được | {len(scores)} |",
        f"| trung bình khác phôi | {sum(scores) / max(len(scores), 1) * 100:.1f}% |",
        f"| đạt ngưỡng ≥70% | {len(over)}/{len(scores)} "
        f"({len(over) / max(len(scores), 1) * 100:.0f}%) |",
        "",
        "## Đọc con số ấy thế nào",
        "",
        "Vẽ cùng một trang hai lần — một lần phôi trần, một lần mặc bản dựng "
        "lại — rồi đếm tỉ lệ ô chữ có nhãn đã đổi chỗ, **sau khi trừ đi độ "
        "dịch chung của cả trang**. Trừ độ dịch chung là điểm mấu chốt: nới lề "
        "đẩy cả trang xuống 15mm thì vẫn là trang cũ nằm thấp hơn, không phải "
        "bố cục mới. Chi tiết trong `agent/distance.py`.",
        "",
        "## Chính sách trong thư mục này khác lúc chạy thật",
        "",
        "Lúc chạy thật, `agent/policy.yaml` **cấm** dựng lại bố cục của giấy "
        "tờ do pháp luật quy định, và điều đó không đổi. Ở đây thì cho phép — "
        "2 bản, và chỉ lấy từ những thiết kế đánh dấu `graphic` — vì câu hỏi "
        "của thư mục này là *nếu dựng lại thì trông thế nào*, mà muốn trả lời "
        "thì phải vẽ ra.",
        "",
        "| phôi | chứng từ | hạng | số bản | khác phôi (thấp – cao) |",
        "|---|---|---|---:|---|",
    ]
    for row in rows:
        got = [entry["distance"]["distance"] for entry in row["variants"]
               if entry.get("distance")]
        span = (f"{min(got) * 100:.0f}% – {max(got) * 100:.0f}%" if got else "—")
        shape = {"roll": " · cuộn", "card": " · thẻ ngang", "page": ""}
        lines.append(f"| `{row['layout']}` | `{row['document']}` | "
                     f"{row['klass']}{shape.get(row.get('shape'), '')} | "
                     f"{len(got)} | {span} |")

    faults: dict[str, int] = {}
    for row in rows:
        for entry in row["variants"]:
            for finding in entry.get("findings") or ():
                faults[finding["code"]] = faults.get(finding["code"], 0) + 1
    thrown = [(row["layout"], d["variant"], d["why"])
              for row in rows for d in row.get("dropped") or ()]
    lines += ["", "## Những bản vẽ ra rồi bỏ", "",
              f"{len(thrown)} bản. Một thiết kế bị bỏ khi bộ phản biện bắt lỗi "
              f"nặng trên trang nó vẽ ra, hoặc khi đo được dưới "
              f"{NOTHING * 100:.0f}% — tức là CSS của nó không với tới họ giấy "
              f"ấy. Thiết kế kế tiếp trong danh sách được lấy thay, tối đa "
              f"{RETRIES} lần.", ""]
    if thrown:
        lines += ["| phôi | thiết kế | lý do |", "|---|---|---|"]
        lines += [f"| `{a}` | `{b}` | {c} |" for a, b, c in thrown[:40]]
    else:
        lines.append("Không bản nào bị bỏ.")

    lines += ["", "## Bộ phản biện soi lại thư viện này", "",
              "`agent/critic.py` chạy trên chính những trang vừa vẽ. Thư viện "
              "là chỗ một thiết kế được nhìn thấy lần đầu, nên cũng phải là "
              "chỗ lỗi của nó bị bắt — chứ không phải một thư mục chỉ khoe "
              "cái đẹp rồi để thiết kế hỏng đi thẳng vào lượt 5000 trang.", ""]
    if not faults:
        lines.append("Không có lỗi nào.")
    else:
        lines += ["| mã | mức | số lần | nghĩa |", "|---|---|---:|---|"]
        for code, times in sorted(faults.items(), key=lambda kv: -kv[1]):
            severity, _, means = critic.CODES.get(code, ("?", "?", ""))
            lines.append(f"| `{code}` | {severity} | {times} | {means} |")

    lines += ["", "## Bản dựng lại nào được dùng ở đâu", "",
              "| thiết kế | kiểu | dùng cho | số lần |", "|---|---|---|---:|"]
    used: dict[str, int] = {}
    for row in rows:
        for entry in row["variants"]:
            if entry["name"] != BASELINE:
                used[entry["variant"]] = used.get(entry["variant"], 0) + 1
    for design in redesign.DESIGNS:
        if design.id not in used:
            continue
        kind = "graphic" if design.graphic else "thường"
        paper = ("thẻ ngang" if design.short_only
                 else "cuộn giấy nhiệt" if not design.wide_only else "khổ rộng")
        lines.append(f"| `{design.id}` | {kind} | {paper} | {used[design.id]} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-o", "--out", type=Path,
                        default=REPO_ROOT / "data" / "layout_augment")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--layouts", nargs="+", default=None,
                        help="only these phôi; default is all of them")
    parser.add_argument("--no-proof", action="store_true")
    args = parser.parse_args()

    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    started = time.time()

    pol = policy_module.load()
    catalogue = redesign.as_variants()
    root = materialise(out / "rules", catalogue, pol)
    rules = spec.load_rules(root)
    problems = policy_module.problems(rules)
    if problems:
        for problem in problems:
            print(f"[gallery] {problem}")
        return 1

    rows = pairing(rules, pol)
    if args.layouts:
        wanted = set(args.layouts)
        rows = [row for row in rows if row["layout"] in wanted]
    print(f"[gallery] {len(rows)} phôi -> {out}")

    gallery = {"seed": args.seed, "neutral": NEUTRAL,
               "counts": {"locked": LOCKED_COUNT, "free": FREE_COUNT},
               "layouts": []}
    failed = bad = 0
    for index, row in enumerate(rows, start=1):
        directory = out / row["layout"]
        # The phôi first and alone: its sheet decides which pool of designs it
        # can wear, and only the render knows how big that sheet is.
        first = draw(directory, row, [], args.seed, root)
        size = None
        if first and first[0].get("drawn"):
            from pipeline import record as schema

            record = json.loads((directory / f"{BASELINE}.json")
                                .read_text(encoding="utf-8"))
            size = schema.page_size(record)
        row["shape"] = shape_of(row, size)
        row["sheet"] = list(size or ())

        # What the bare phôi already gets wrong. Reported against the phôi in
        # its own page, and not charged to any design.
        review(directory, first)
        row["inherited"] = sorted({f["code"] for f in first[0].get("findings") or ()
                                   if f["severity"] == critic.SEVERE})

        pool = pool_for(row, row["shape"])
        want = min(wanted_count(row), len(pool))
        taken, kept, dropped = list(pool[:want]), [], []
        tried = {design.id for design in taken}
        for attempt in range(RETRIES + 1):
            batch = draw(directory, row, taken, args.seed, root, baseline=False)
            measure(directory, first + batch)
            review(directory, batch)
            spare = [d for d in pool if d.id not in tried]
            taken = []
            for entry in batch:
                why = rejected(entry, set(row["inherited"]))
                if not why:
                    kept.append(entry)
                    continue
                dropped.append({"variant": entry["variant"], "why": why})
                for name in (f"{entry.get('name', '')}.jpg",
                             f"{entry.get('name', '')}.json"):
                    (directory / name).unlink(missing_ok=True)
                if spare and attempt < RETRIES:
                    replacement = spare.pop(0)
                    tried.add(replacement.id)
                    taken.append(replacement)
            if not taken:
                break
        drawn = first + kept
        row["dropped"] = dropped
        found = [f for entry in kept for f in entry.get("findings") or ()]
        severe = sum(1 for f in found if f["severity"] == critic.SEVERE)
        if not args.no_proof:
            proofs(directory, drawn, out, row["layout"])
        (directory / "bao_cao.md").write_text(
            layout_report(row, drawn, list(pool)), encoding="utf-8")
        missing = [entry for entry in drawn if not entry.get("drawn")]
        failed += len(missing)
        got = [entry["distance"]["distance"] for entry in drawn
               if entry.get("distance")]
        print(f"[gallery] {index:>2}/{len(rows)} {row['layout']:<28} "
              f"{row['klass']:<7} {row['shape']:<4} {len(got)}/{want} bản"
              + (f"  khác {min(got) * 100:.0f}-{max(got) * 100:.0f}%" if got else "")
              + (f"  bỏ {len(dropped)}" if dropped else "")
              + (f"  {severe} LỖI NẶNG" if severe else "")
              + (f"  ({len(missing)} KHÔNG VẼ ĐƯỢC)" if missing else ""))
        bad += severe
        gallery["layouts"].append({**row, "variants": drawn})

    gallery["elapsed_seconds"] = round(time.time() - started, 1)
    (out / "gallery.json").write_text(
        json.dumps(gallery, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (out / "BAO_CAO.md").write_text(overview(gallery), encoding="utf-8")
    print(f"[gallery] {out / 'BAO_CAO.md'}")
    if failed:
        print(f"[gallery] {failed} trang không vẽ được")
    if bad:
        print(f"[gallery] {bad} lỗi nặng — xem `lỗi` trong BAO_CAO.md")
    return 1 if failed or bad else 0


if __name__ == "__main__":
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    raise SystemExit(main())
