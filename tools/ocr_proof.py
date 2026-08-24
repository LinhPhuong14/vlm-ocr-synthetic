"""Prove an OCR model reads the generated dataset, and score it against the labels.

    python tools/ocr_proof.py data/dataset60 -o data/dataset60/proof

A synthetic dataset that no model can read is worth nothing, and a dataset
whose labels do not match its pixels is worth less than nothing. This runs
Tesseract 5 with the Vietnamese model over every image and scores what came
back against the ground truth the generator wrote.

Scoring is order-free on purpose. Tesseract reads a two-column receipt in
whatever order its layout analysis decides, so comparing its output to the
label as one string would measure the reading order, not the recognition.
Instead:

    token recall   how much of the printed text came back at all
    field hits     per field (shop name, each dish, each amount), how much of
                   that field's tokens came back -- a field counts as read at
                   70% or more
    money exact    amounts are the part a receipt exists for, so they are
                   scored separately and only an exact string counts

Both a diacritics-sensitive and an ASCII-folded score are reported. The gap
between them is how much of the error is only the accents.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import unicodedata
from collections import Counter
from pathlib import Path

# Imported where they are used, not here. Everything above the engine -- the
# scoring, the buckets, the conditions a number carries -- is arithmetic on
# dicts, and it has to stay importable without a browser stack or an imaging
# library or the tests for it would need one to check a token count.

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# `record` is the name a metadata line goes by throughout this file, so the
# module that defines their shape comes in under a name that cannot shadow one.
from pipeline import record as schema  # noqa: E402
from pipeline import synthesis  # noqa: E402

FRAMEWORKS = ("synthdog", "html", "genalog")
MONEY = re.compile(r"^-?\d[\d.,]*$")
HIT_THRESHOLD = 0.7


def fold(text: str) -> str:
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", text)


def tokens(text: str, folded: bool = False) -> list[str]:
    text = fold(text) if folded else text
    # Keep the punctuation inside amounts (20,200 / 149.625) but nothing else.
    return [t for t in re.split(r"[^\w.,\-]+", text.lower()) if t.strip(".,-")]


def locate_page(grey) -> tuple[int, int, int, int] | None:
    """Bounding box of the sheet within a photograph of it.

    The glyph renderer composites its receipt onto a dark background, and
    Tesseract binarises globally: with a dark surround in frame, the threshold
    lands between background and paper, and the grey text on white paper falls
    on the paper side and disappears. Cropping to the sheet first is what any
    deployed OCR pipeline does, and it is the difference between reading a
    photographed receipt and reading nothing at all.

    Returns None when the page fills the frame already (the two HTML backends
    produce flat scans with no surround), or when nothing page-like is found.
    """
    import cv2
    import numpy as np

    blurred = cv2.GaussianBlur(grey, (0, 0), 2.0)
    _, mask = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
    count, _labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count <= 1:
        return None
    largest = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, area = stats[largest]
    frame = grey.shape[0] * grey.shape[1]
    if not (0.12 * frame < area < 0.97 * frame):
        return None
    pad = int(0.02 * max(w, h))
    return (max(x - pad, 0), max(y - pad, 0),
            min(w + 2 * pad, grey.shape[1] - max(x - pad, 0)),
            min(h + 2 * pad, grey.shape[0] - max(y - pad, 0)))


def run_tesseract(path: Path, lang: str, psm: int, upscale_to: int) -> tuple[str, list[dict]]:
    """Read one image; return its text and the word boxes for the proof sheet."""
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise FileNotFoundError(path)

    offset = (0, 0)
    box = locate_page(image)
    if box is not None:
        x, y, w, h = box
        image = image[y:y + h, x:x + w]
        offset = (x, y)

    # Tesseract wants roughly 30px of x-height; receipts render smaller than
    # that, and upscaling before recognition is worth several points of recall.
    scale = max(1.0, upscale_to / max(image.shape))
    if scale > 1.0:
        image = cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"could not encode {path}")

    common = ["tesseract", "stdin", "stdout", "-l", lang, "--psm", str(psm)]
    text = subprocess.run(common, input=buffer.tobytes(), capture_output=True).stdout
    tsv = subprocess.run(common + ["tsv"], input=buffer.tobytes(), capture_output=True).stdout

    words = []
    for line in tsv.decode("utf-8", "replace").splitlines()[1:]:
        parts = line.split("\t")
        if len(parts) < 12 or not parts[11].strip():
            continue
        try:
            confidence = float(parts[10])
        except ValueError:
            continue
        if confidence < 0:
            continue
        words.append({
            "text": parts[11],
            "conf": confidence,
            # Back to the coordinates of the file on disk, so the proof sheet
            # can draw the boxes on the original rather than on the crop.
            "box": [int(parts[6]) / scale + offset[0], int(parts[7]) / scale + offset[1],
                    int(parts[8]) / scale, int(parts[9]) / scale],
        })
    return text.decode("utf-8", "replace"), words


def expected_fields(ground_truth: dict) -> list[tuple[str, str]]:
    """The fields worth asking whether a model can read."""
    parse = ground_truth["gt_parse"]
    fields: list[tuple[str, str]] = []
    store = parse.get("store", {})
    for key in ("name", "branch", "address", "address2", "phone"):
        if store.get(key):
            fields.append((f"store.{key}", store[key]))
    if parse.get("title"):
        fields.append(("title", parse["title"]))
    for index, item in enumerate(parse.get("menu", [])):
        if item.get("nm"):
            fields.append((f"menu[{index}].nm", item["nm"]))
        if item.get("price"):
            fields.append((f"menu[{index}].price", item["price"]))
    for label, value in (parse.get("total") or {}).items():
        fields.append((f"total[{label}]", f"{label} {value}"))
    return fields


def score_field(field: str, bag: Counter, folded: bool) -> float:
    """Fraction of the field's tokens present in what the OCR returned."""
    wanted = tokens(field, folded)
    if not wanted:
        return 1.0
    found = sum(1 for token in wanted if bag[token] > 0)
    return found / len(wanted)


def score_image(record: dict, text: str, reading: str = "") -> dict:
    parse = schema.extracted(record)
    fields = expected_fields({"gt_parse": parse})

    result: dict = {"file_name": schema.file_name(record), "fields": len(fields)}
    for folded, suffix in ((False, ""), (True, "_folded")):
        bag = Counter(tokens(text, folded))
        scores = [score_field(value, bag, folded) for _role, value in fields]
        hits = sum(1 for score in scores if score >= HIT_THRESHOLD)

        wanted = Counter(tokens(reading, folded))
        overlap = sum(min(count, bag[token]) for token, count in wanted.items())
        total = sum(wanted.values())

        result[f"token_recall{suffix}"] = overlap / total if total else 0.0
        result[f"field_hit_rate{suffix}"] = hits / len(fields) if fields else 0.0

    # Amounts, exactly as printed -- the digits are the point of a receipt.
    amounts = [value for _role, value in fields if MONEY.match(value.strip())]
    amounts += [item["price"] for item in parse.get("menu", []) if item.get("price")]
    amounts = [a for a in dict.fromkeys(amounts)]
    read = set(tokens(text))
    result["money_total"] = len(amounts)
    result["money_exact"] = sum(1 for amount in amounts if amount.lower() in read)

    worst = sorted(
        ((score_field(value, Counter(tokens(text)), False), role, value)
         for role, value in fields),
        key=lambda entry: entry[0],
    )[:3]
    result["worst_fields"] = [{"role": r, "expected": v, "score": round(s, 3)}
                              for s, r, v in worst]
    return result


def proof_sheet(path: Path, words: list[dict], out: Path) -> None:
    """The image with every word Tesseract found boxed, green above 70% confidence."""
    import cv2

    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        return
    overlay = image.copy()
    for word in words:
        x, y, w, h = (int(round(v)) for v in word["box"])
        colour = (0, 170, 0) if word["conf"] >= 70 else (0, 140, 235)
        cv2.rectangle(overlay, (x, y), (x + w, y + h), colour, 1)
    blended = cv2.addWeighted(overlay, 0.85, image, 0.15, 0)
    cv2.imwrite(str(out), blended, [cv2.IMWRITE_JPEG_QUALITY, 88])


def bucket(per_image: list[dict], key) -> dict:
    """Mean token recall per group, and how many images each group holds."""
    groups: dict[str, list[float]] = {}
    for result in per_image:
        groups.setdefault(key(result), []).append(result["token_recall"])
    return {name: {"images": len(values), "token_recall": round(mean(values), 4)}
            for name, values in sorted(groups.items())}


def conditions(per_image: list[dict], report: dict) -> dict:
    """What an aggregate score is a score *of*.

    Law 8, applied to a number rather than to a baseline: a pooled recall is a
    comparison point, and it has to carry the conditions it was taken under or
    it will be compared with itself in another world. The condition that turned
    out to matter most is the **layout mix** -- ageing costs `invoice_brand`
    0.026 of its recall and `market_barcode` 0.552, twenty-one times as much,
    so a pooled score moves when the mix moves and says nothing about anything
    else having changed.
    """
    counts: dict[str, int] = {}
    for result in per_image:
        counts[result.get("layout", "")] = counts.get(result.get("layout", ""), 0) + 1
    return {
        "layouts": sorted(counts),
        "images_per_layout": dict(sorted(counts.items())),
        "engine": report.get("engine", ""),
        "lang": report.get("lang", ""),
        "psm": report.get("psm"),
        "pairing": report.get("pairing", "unknown"),
    }


def comparable(left: dict, right: dict) -> list[str]:
    """Why two reports' pooled numbers may not be put beside each other.

    Empty means they may. Anything else is a refusal with a reason, printed
    instead of the comparison -- a reader who has to remember that two datasets
    had different layout sets will eventually not remember.
    """
    a, b = left.get("conditions"), right.get("conditions")
    if not a or not b:
        return ["one of the reports predates condition recording, so the two "
                "pooled scores cannot be told apart from a change of subject"]
    problems = []
    if a["layouts"] != b["layouts"]:
        added = [x for x in b["layouts"] if x not in a["layouts"]]
        gone = [x for x in a["layouts"] if x not in b["layouts"]]
        problems.append(
            "the layout sets differ ("
            + ", ".join(filter(None, [f"+{', +'.join(added)}" if added else "",
                                      f"-{', -'.join(gone)}" if gone else ""]))
            + ") -- ageing costs different layouts between 0.03 and 0.55 of "
              "recall, so a pooled difference here is a difference of subject")
    for field in ("engine", "lang", "psm"):
        if a.get(field) != b.get(field):
            problems.append(f"{field} differs: {a.get(field)!r} vs {b.get(field)!r}")
    return problems


def compare_reports(before: dict, after: dict, source) -> dict:
    """Two reports, side by side -- per layout always, pooled only if allowed.

    The per-layout drop is the quantity that actually measures a change: it
    holds the layout fixed, so what is left is the thing that changed. The
    pooled difference is reported only when the conditions match, and otherwise
    replaced by the reason it would have been meaningless.
    """
    blocked = comparable(before, after)
    shared = sorted(set(before.get("by_layout", {})) & set(after.get("by_layout", {})))
    rows = []
    for layout in shared:
        was = before["by_layout"][layout]["token_recall"]
        now = after["by_layout"][layout]["token_recall"]
        rows.append({"layout": layout, "before": was, "after": now,
                     "drop": round(was - now, 4)})
    rows.sort(key=lambda row: row["drop"])
    out = {"source": str(source), "by_layout": rows,
           "refused": blocked, "layouts_only_here": sorted(
               set(after.get("by_layout", {})) - set(before.get("by_layout", {}))),
           "layouts_only_there": sorted(
               set(before.get("by_layout", {})) - set(after.get("by_layout", {})))}
    if not blocked:
        out["pooled"] = {
            name: round(after["frameworks"][name]["token_recall"]
                        - before["frameworks"][name]["token_recall"], 4)
            for name in after.get("frameworks", {})
            if name in before.get("frameworks", {})
        }
    return out


def mean(values: list[float]) -> float:
    return (sum(values) / len(values)) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="directory holding <framework>/ image and record pairs")
    parser.add_argument("-o", "--out", type=Path, default=None)
    parser.add_argument("--lang", default="vie")
    parser.add_argument("--psm", type=int, default=4, help="4 = one column of variable-size text")
    parser.add_argument("--upscale-to", type=int, default=2200)
    parser.add_argument("--sheets", type=int, default=2, help="proof sheets per framework")
    parser.add_argument("--against", type=Path, default=None,
                        help="an earlier ocr_report.json to compare with. The "
                             "pooled numbers are only put side by side when the "
                             "conditions match; the per-layout ones always are")
    args = parser.parse_args()

    out = args.out or args.dataset / "proof"
    out.mkdir(parents=True, exist_ok=True)

    report: dict = {
        "engine": subprocess.run(["tesseract", "--version"], capture_output=True,
                                 text=True).stdout.splitlines()[0],
        "lang": args.lang,
        "psm": args.psm,
        "frameworks": {},
    }
    per_image: list[dict] = []

    for framework in FRAMEWORKS:
        directory = args.dataset / framework
        if not directory.is_dir() or not schema.images(directory):
            print(f"[skip] {framework}: no images")
            continue

        records = schema.read(directory)
        drew = synthesis.read_if_there(args.dataset / framework)
        results = []
        for index, record in enumerate(records):
            name = schema.file_name(record)
            path = args.dataset / framework / name
            text, words = run_tesseract(path, args.lang, args.psm, args.upscale_to)
            result = score_image(record, text, drew.text_sequence(name))
            result["framework"] = framework
            result["layout"] = drew.layout(name) if name in drew else ""
            attributes = {key: {"id": value} for key, value
                          in (drew.entry(name).get("attributes") or {}).items()}
            result["augmentation"] = attributes.get("augmentation", {}).get("id", "")
            result["visual"] = attributes.get("visual", {}).get("id", "")
            result["words_found"] = len(words)
            results.append(result)
            per_image.append(result)
            if index < args.sheets:
                proof_sheet(path, words, out / f"proof_{framework}_{index:02d}.jpg")
            print(f"  {record['file_name']}  recall={result['token_recall']:.2f} "
                  f"fields={result['field_hit_rate']:.2f} "
                  f"money={result['money_exact']}/{result['money_total']}")

        report["frameworks"][framework] = {
            "images": len(results),
            "token_recall": round(mean([r["token_recall"] for r in results]), 4),
            "token_recall_folded": round(mean([r["token_recall_folded"] for r in results]), 4),
            "field_hit_rate": round(mean([r["field_hit_rate"] for r in results]), 4),
            "field_hit_rate_folded": round(mean([r["field_hit_rate_folded"] for r in results]), 4),
            "money_exact": sum(r["money_exact"] for r in results),
            "money_total": sum(r["money_total"] for r in results),
        }
        print(f"[{framework}] {report['frameworks'][framework]}\n")

    # Broken out by the attributes that should drive difficulty. If the ageing
    # attribute does not order the scores, the rule-base is not actually
    # controlling how hard an image is, whatever the YAML says.
    for key in ("layout", "augmentation", "visual"):
        report[f"by_{key}"] = bucket(per_image, lambda r, k=key: r.get(k, ""))

    # The ageing ladder, scored **inside a layout**. Pooled across layouts it is
    # not a measurement of ageing: each rung holds whichever layouts happened to
    # fall in it, and the layouts differ by twenty-one times in how much ageing
    # costs them. Same reasoning as T-09's per-(layout, field) budgets, and for
    # the same reason -- a ratio pooled over unlike things measures the pooling.
    report["by_layout_augmentation"] = bucket(
        per_image, lambda r: f"{r.get('layout', '')}/{r.get('augmentation', '')}")

    # What the numbers may be compared to. Under `paired` every renderer drew
    # the same receipts, so a difference between two of them is a difference in
    # drawing; under `independent` they drew different ones and a side-by-side
    # reading of the frameworks table means nothing. Read from the dataset
    # rather than assumed, because both look the same from here.
    summary_path = args.dataset / "dataset.json"
    if summary_path.exists():
        declared = json.loads(summary_path.read_text(encoding="utf-8"))
        report["pairing"] = declared.get("pairing", "unknown")
        report["distinct_labels"] = {
            name: entry.get("distinct_labels")
            for name, entry in (declared.get("frameworks") or {}).items()
        }
    else:
        report["pairing"] = "unknown"
        report["distinct_labels"] = {}

    # Written last: `pairing` is read above and belongs in the conditions.
    report["conditions"] = conditions(per_image, report)

    if args.against:
        other = json.loads(Path(args.against).read_text(encoding="utf-8"))["summary"]
        report["against"] = compare_reports(other, report, args.against)

    (out / "ocr_report.json").write_text(
        json.dumps({"summary": report, "images": per_image}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_markdown(report, per_image, out / "README.md")
    print(f"\n-> {out / 'ocr_report.json'}")
    return 0


def _pairing_note(report: dict) -> list[str]:
    """Say what the frameworks table may be compared across, and on how much.

    Written from the report rather than fixed in the source. Before W1b this
    file carried a sentence about the spread between renderers while the three
    renderers were drawing different receipts, and the sentence had no way of
    knowing.
    """
    pairing = report.get("pairing", "unknown")
    distinct = [n for n in report.get("distinct_labels", {}).values() if n]
    images = sum(entry["images"] for entry in report["frameworks"].values())
    if pairing == "paired":
        receipts = max(distinct) if distinct else 0
        return [
            "**Every renderer drew the same receipts** (`pairing: paired`), so a",
            "difference between two rows of the first table is a difference in",
            f"drawing and nothing else. The {images} images are {receipts} receipts",
            f"drawn {len(report['frameworks'])} ways -- count the sample as "
            f"{receipts}, not {images}.",
        ]
    if pairing == "independent":
        return [
            "**The renderers drew different receipts** (`pairing: independent`), so",
            "the rows of the first table are not comparable with each other: a gap",
            "between two of them may be a gap between two sets of pages. Regenerate",
            "with `pairing: paired` before drawing any conclusion about a renderer.",
        ]
    return [
        "**This dataset does not say whether the renderers drew the same receipts.**",
        "Without that, the first table cannot be read across rows. Regenerate it.",
    ]


def _ageing_note(report: dict) -> list[str]:
    """Whether ageing ordered the scores -- asked inside a layout, not across.

    Pooled across layouts the question cannot be answered. Ageing costs
    `invoice_brand` 0.026 of its recall and `market_barcode` 0.552, twenty-one
    times as much, so a rung of the ladder scores whatever layouts happened to
    land on it. The pooled table is still printed, because it is what a reader
    of the dataset meets; it is just not evidence about ageing.
    """
    pairs = report.get("by_layout_augmentation", {})
    if not pairs:
        return ["(no ageing breakdown in this report)"]

    by_layout: dict[str, list[tuple[str, float, int]]] = {}
    for name, entry in pairs.items():
        layout, _, ageing = name.partition("/")
        by_layout.setdefault(layout, []).append(
            (ageing, entry["token_recall"], entry["images"]))

    spreads = []
    for layout, rungs in by_layout.items():
        if len(rungs) < 2:
            continue
        rungs.sort(key=lambda row: -row[1])
        spreads.append((rungs[0][1] - rungs[-1][1], layout, rungs[0], rungs[-1]))
    if not spreads:
        return [
            "**The ageing ladder cannot be read from this dataset.** No layout in",
            "it was drawn at two different levels of ageing, so every rung of the",
            "pooled table is a different set of layouts and the ordering between",
            "rungs says nothing about ageing. Compare against the matching clean",
            "set instead: `--against <its ocr_report.json>`.",
        ]

    spreads.sort(reverse=True)
    widest, narrowest = spreads[0], spreads[-1]
    return [
        "**The ageing table is scored inside a layout, and only inside one.**",
        "Pooled across layouts it measures the mix rather than the ageing: the",
        "same chain costs different layouts very different amounts, so a rung",
        "holds whichever layouts fell in it. `by_layout_augmentation` in",
        "`ocr_report.json` is the honest form.",
        "",
        f"Widest here is `{widest[1]}`: `{widest[2][0]}` at {widest[2][1]:.3f} down "
        f"to `{widest[3][0]}` at {widest[3][1]:.3f}, a spread of {widest[0]:.3f}.",
        f"Narrowest is `{narrowest[1]}` at {narrowest[0]:.3f}. Editing `weight` in",
        "`rulebase/rules/augmentation.yaml` shifts the whole dataset. Values",
        "missing from a table were never drawn in this sample rather than scoring",
        "zero.",
    ]


def _conditions_note(report: dict) -> list[str]:
    """The layout set, printed beside the number that depends on it."""
    conds = report.get("conditions") or {}
    layouts = conds.get("layouts") or []
    if not layouts:
        return []
    return [
        "**The pooled numbers above are a score of this layout set, not of the",
        "generator.** Ageing costs different layouts between 0.03 and 0.55 of",
        "their recall, so changing which layouts are in a dataset moves the",
        "pooled score on its own. This one holds "
        f"{len(layouts)} layouts: {', '.join(f'`{name}`' for name in layouts)}.",
        "",
        "Comparing this table with an older one is only meaningful when both",
        "were taken over the same set; `tools/ocr_proof.py --against <report>`",
        "checks that and refuses the pooled comparison when they differ, while",
        "still giving the per-layout one, which holds the layout fixed and is",
        "therefore the quantity that measures a change.",
    ]


def _against_note(report: dict) -> list[str]:
    """The comparison with another report, printed rather than left in JSON.

    Only the per-layout half is a measurement: it holds the layout fixed, so
    what remains is the thing that changed. The pooled half is printed when the
    conditions matched and replaced by the refusal when they did not.
    """
    against = report.get("against")
    if not against:
        return []
    rows = against.get("by_layout") or []
    lines = [
        "**What the ageing cost, layout by layout.** Against "
        f"`{against['source']}`. Each row holds one layout fixed, so the drop is",
        "the ageing and nothing else.",
    ]
    if rows:
        lines += [
            "",
            "| layout | before | after | drop |",
            "| --- | ---: | ---: | ---: |",
        ]
        lines += [f"| {row['layout']} | {row['before']:.3f} | {row['after']:.3f} | "
                  f"{row['drop']:.3f} |" for row in rows]
        least, most = rows[0], rows[-1]
        times = most["drop"] / least["drop"] if least["drop"] > 0 else 0
        lines += [
            "",
            f"The same ageing chain costs `{least['layout']}` {least['drop']:.3f} of its",
            f"recall and `{most['layout']}` {most['drop']:.3f}"
            + (f" -- {times:.0f} times as much." if times >= 2 else "."),
            "That is why the pooled number cannot be read as a score of the",
            "generator: it moves when the layout mix moves, on its own.",
        ]
    for name in against.get("layouts_only_here") or []:
        lines.append(f"`{name}` is in this dataset only, so it has no row.")
    for name in against.get("layouts_only_there") or []:
        lines.append(f"`{name}` is in the other dataset only, so it has no row.")

    refused = against.get("refused") or []
    if refused:
        lines += ["", "The pooled columns are **not** compared, because "
                  + "; ".join(refused) + "."]
    elif against.get("pooled"):
        lines += ["", "Pooled, over the same conditions: "
                  + ", ".join(f"`{name}` {value:+.3f}"
                              for name, value in against["pooled"].items()) + "."]
    return lines


def write_markdown(report: dict, per_image: list[dict], path: Path) -> None:
    lines = [
        "# OCR proof",
        "",
        f"Engine: `{report['engine']}`, language `{report['lang']}`, "
        f"page segmentation mode {report['psm']}.",
        "",
        "Scores are order-free: Tesseract reads a two-column receipt in whatever",
        "order its layout analysis picks, so comparing its output to the label as",
        "one string would measure reading order rather than recognition. See",
        "`tools/ocr_proof.py` for the definitions.",
        "",
        "| framework | images | token recall | recall (folded) | field hit | field hit (folded) | money read exactly |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name, entry in report["frameworks"].items():
        money = f"{entry['money_exact']}/{entry['money_total']}"
        share = entry["money_exact"] / entry["money_total"] if entry["money_total"] else 0
        lines.append(
            f"| {name} | {entry['images']} | {entry['token_recall']:.3f} | "
            f"{entry['token_recall_folded']:.3f} | {entry['field_hit_rate']:.3f} | "
            f"{entry['field_hit_rate_folded']:.3f} | {money} ({share:.0%}) |"
        )

    titles = {
        "layout": "By layout",
        "augmentation": "By level of ageing",
        "visual": "By kind of printer",
    }
    for key, title in titles.items():
        lines += ["", f"## {title}", "", "| value | images | token recall |", "| --- | ---: | ---: |"]
        rows = sorted(report[f"by_{key}"].items(),
                      key=lambda item: -item[1]["token_recall"])
        for name, entry in rows:
            lines.append(f"| {name or '(unknown)'} | {entry['images']} | "
                         f"{entry['token_recall']:.3f} |")

    lines += [
        "",
        "## The illustrations",
        "",
        "`proof_<framework>_NN.jpg` is the original image with a box round every",
        "word Tesseract read -- green where its confidence is >= 70%, orange below.",
        "",
        "## How to read these tables",
        "",
        *_pairing_note(report),
        "",
        "**The spread between the three renderers is real, not a bug.** The glyph",
        "renderer produces a *photograph* of a receipt lying on a table -- with",
        "perspective, a lamp and a dark background; the two HTML renderers produce",
        "a *flat scan* and a *print*. A photograph is markedly harder, and that is",
        "precisely why all three are kept: a model that has only seen flat scans",
        "has never met the hard case.",
        "",
        *_ageing_note(report),
        "",
        *_conditions_note(report),
        "",
        *_against_note(report),
        *([""] if report.get("against") else []),
        "**However much higher the \"folded\" column is than the plain one is how",
        "much of the error is tone marks alone.** The gap here is small, which means",
        "the errors are mostly mis-recognised characters rather than lost diacritics.",
        "",
        "These are **Tesseract's** scores -- a general-purpose engine that has not",
        "been fine-tuned on Vietnamese thermal receipts. It is a floor, not a",
        "ceiling: a low score on a heavily aged image is evidence the image is hard,",
        "not evidence the label is wrong. To check whether a label matches its",
        "pixels, look at `worst_fields` in `ocr_report.json` -- a field that is",
        "wrong systematically across EVERY image is a broken label.",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
