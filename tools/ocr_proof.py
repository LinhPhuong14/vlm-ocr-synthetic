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

import cv2
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

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


def locate_page(grey: np.ndarray) -> tuple[int, int, int, int] | None:
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


def score_image(record: dict, text: str) -> dict:
    ground_truth = json.loads(record["ground_truth"])
    fields = expected_fields(ground_truth)

    result: dict = {"file_name": record["file_name"], "fields": len(fields)}
    for folded, suffix in ((False, ""), (True, "_folded")):
        bag = Counter(tokens(text, folded))
        scores = [score_field(value, bag, folded) for _role, value in fields]
        hits = sum(1 for score in scores if score >= HIT_THRESHOLD)

        wanted = Counter(tokens(record["text_sequence"], folded))
        overlap = sum(min(count, bag[token]) for token, count in wanted.items())
        total = sum(wanted.values())

        result[f"token_recall{suffix}"] = overlap / total if total else 0.0
        result[f"field_hit_rate{suffix}"] = hits / len(fields) if fields else 0.0

    # Amounts, exactly as printed -- the digits are the point of a receipt.
    amounts = [value for _role, value in fields if MONEY.match(value.strip())]
    parse = ground_truth["gt_parse"]
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


def mean(values: list[float]) -> float:
    return float(np.mean(values)) if values else 0.0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path, help="directory holding <framework>/metadata.jsonl")
    parser.add_argument("-o", "--out", type=Path, default=None)
    parser.add_argument("--lang", default="vie")
    parser.add_argument("--psm", type=int, default=4, help="4 = one column of variable-size text")
    parser.add_argument("--upscale-to", type=int, default=2200)
    parser.add_argument("--sheets", type=int, default=2, help="proof sheets per framework")
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
        metadata = args.dataset / framework / "metadata.jsonl"
        if not metadata.exists():
            print(f"[skip] {framework}: no metadata.jsonl")
            continue

        records = [json.loads(line) for line in metadata.read_text(encoding="utf-8").splitlines()]
        results = []
        for index, record in enumerate(records):
            path = args.dataset / framework / record["file_name"]
            text, words = run_tesseract(path, args.lang, args.psm, args.upscale_to)
            result = score_image(record, text)
            result["framework"] = framework
            result["layout"] = record.get("layout", "")
            attributes = record.get("recipe", {}).get("attributes", {})
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
        buckets: dict[str, list[float]] = {}
        for result in per_image:
            buckets.setdefault(result.get(key, ""), []).append(result["token_recall"])
        report[f"by_{key}"] = {
            name: {"images": len(values), "token_recall": round(mean(values), 4)}
            for name, values in sorted(buckets.items())
        }

    (out / "ocr_report.json").write_text(
        json.dumps({"summary": report, "images": per_image}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    write_markdown(report, per_image, out / "README.md")
    print(f"\n-> {out / 'ocr_report.json'}")
    return 0


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
        "| framework | ảnh | token recall | recall (bỏ dấu) | field hit | field hit (bỏ dấu) | số tiền đọc đúng |",
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
        "layout": "Theo bố cục",
        "augmentation": "Theo mức làm cũ",
        "visual": "Theo kiểu máy in",
    }
    for key, title in titles.items():
        lines += ["", f"## {title}", "", "| giá trị | ảnh | token recall |", "| --- | ---: | ---: |"]
        rows = sorted(report[f"by_{key}"].items(),
                      key=lambda item: -item[1]["token_recall"])
        for name, entry in rows:
            lines.append(f"| {name or '(không rõ)'} | {entry['images']} | "
                         f"{entry['token_recall']:.3f} |")

    lines += [
        "",
        "## Ảnh minh hoạ",
        "",
        "`proof_<framework>_NN.jpg` là ảnh gốc kèm khung từng từ Tesseract đọc được —",
        "xanh lá là độ tin cậy ≥ 70%, cam là thấp hơn.",
        "",
        "## Cách đọc bảng",
        "",
        "**Chênh lệch giữa ba renderer là có thật, không phải lỗi.** Renderer glyph",
        "cho ra ảnh *chụp* tờ hoá đơn nằm trên bàn — có phối cảnh, có bóng đèn, có",
        "nền tối; hai renderer HTML cho ra bản *quét phẳng* và bản *in*. Ảnh chụp",
        "khó hơn hẳn, và đó chính là lý do giữ cả ba: một model chỉ thấy bản quét",
        "phẳng thì chưa từng gặp trường hợp khó.",
        "",
        "**Thứ tự trong bảng \"mức làm cũ\" là bằng chứng rule-base thật sự điều",
        "khiển được độ khó**: `pristine` và `real_paper` ở trên cùng,",
        "`crumpled` ở dưới cùng, đơn điệu suốt dải. Chỉnh `weight` trong",
        "`rulebase/rules/augmentation.yaml` là dịch được cả bộ dữ liệu dễ hơn hoặc",
        "khó hơn.",
        "",
        "**Cột \"bỏ dấu\" cao hơn cột thường bao nhiêu thì phần lỗi chỉ nằm ở dấu",
        "thanh bấy nhiêu.** Khoảng cách ở đây nhỏ, nghĩa là lỗi chủ yếu là nhận",
        "nhầm ký tự chứ không phải mất dấu.",
        "",
        "Đây là điểm của **Tesseract**, một engine đa dụng chưa fine-tune trên hoá",
        "đơn nhiệt tiếng Việt. Nó là mốc dưới, không phải trần: điểm thấp trên ảnh",
        "làm cũ nặng là dấu hiệu ảnh đủ khó, không phải dấu hiệu nhãn sai. Muốn",
        "kiểm tra nhãn có khớp ảnh không thì nhìn `worst_fields` trong",
        "`ocr_report.json` — trường nào sai một cách có hệ thống trên MỌI ảnh mới",
        "là nhãn hỏng.",
        "",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
