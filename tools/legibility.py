"""Chuỗi làm cũ có xoá mất chữ trong hộp nhãn không — đo, thay vì đoán.

    python tools/legibility.py                      # trang mẫu, mọi chuỗi trong luật
    python tools/legibility.py --source page.jpg --boxes page.json
    python tools/legibility.py --chain heavy --chain copier_worn

Một hộp nhãn khai là có chữ ở đấy. Nếu chuỗi làm cũ xoá mất chữ mà nhãn vẫn
khai đủ, thì đó không phải dữ liệu khó — đó là **dữ liệu độc**: mô hình bị dạy
rằng chỗ trống có chữ, và mọi ảnh sạch sau đó cũng bị nó nhìn ra chữ.

`docs/lam-cu-de-xuat.md` xếp phép đo này là việc số 1, trước mọi mô hình mới,
vì không có nó thì mọi tham số làm cũ đều chỉnh bằng mắt trên vài tờ.

## Đo cái gì

Trong mỗi hộp, lấy **phân vị 5 của độ xám** làm mức mực và **phân vị 75** làm
mức giấy. Hiệu hai số ấy là `contrast`, tính theo mức xám 0–255.

Phân vị chứ không phải min và max: một điểm nhiễu đơn lẻ kéo min xuống 0 và
làm mọi hộp trông như còn đọc tốt. Phân vị 75 chứ không phải trung vị, vì hộp
ôm sát chữ nên hơn nửa số điểm trong hộp có thể là mực.

Hai con số báo ra:

* `kept`   — `contrast` sau chia cho `contrast` trước. Không thứ nguyên, nên
             so được giữa các bố cục và các cỡ chữ.
* `lost`   — phần trăm hộp tụt xuống dưới `--floor`. Đây mới là con số phải
             nhìn: một chuỗi giữ `kept` trung bình 0.8 mà xoá sạch 12% số hộp
             thì trung bình ấy đang che đi đúng chỗ hỏng.

`--floor` mặc định 28 mức xám. Đó là mức mà bản thân JPEG chất lượng thấp và
lưới tram còn để lại được, đo trên chính các chuỗi của repo này; dưới nó thì
nét chữ chìm vào hạt giấy. Nó là ngưỡng chọn bằng tay, không phải hằng số của
tự nhiên — chỗ này ghi ra để ai đổi nó biết mình đang đổi cái gì.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from degradation import apply_chain  # noqa: E402
from degradation.regions import normalise_boxes  # noqa: E402

RULES = REPO_ROOT / "rulebase" / "rules" / "augmentation.yaml"


def probe_page(width: int = 900, height: int = 1200):
    """Một tờ hoá đơn dựng bằng OpenCV, kèm hộp nhãn thật của chính nó.

    Dựng ở đây chứ không đọc từ `data/`: phép đo phải chạy được trên một bản
    clone chưa sinh ảnh nào, nếu không nó là phép đo không ai chạy. Vai trò ô
    đặt theo đúng lối đặt tên của rule-base (`total.grand`, `menu.nm`) để lối
    bốc `kind` của `by_box` có cái mà bốc.
    """
    image = np.full((height, width, 3), 238, np.uint8)
    boxes = []

    def line(x, y, text, scale=0.55, weight=1, kind="menu.nm"):
        (w, h), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, weight)
        cv2.putText(image, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, scale, (25, 25, 25),
                    weight, cv2.LINE_AA)
        boxes.append({"kind": kind, "text": text,
                      "quad": [[x, y - h], [x + w, y - h], [x + w, y + 4], [x, y + 4]]})

    line(240, 70, "CONG TY TNHH ABC", 0.9, 2, "store.name")
    line(230, 100, "HOA DON GIA TRI GIA TANG", 0.6, 1, "invoice.title")
    y = 170
    for index in range(28):
        line(60, y, f"Mat hang so {index:02d} loai A", 0.5, 1, "menu.nm")
        line(600, y, f"{(index + 1) * 1250:,}", 0.5, 1, "menu.price")
        y += 32
    line(60, y + 30, "TONG CONG", 0.7, 2, "total.grand")
    line(600, y + 30, "1,234,500", 0.7, 2, "total.grand")
    return image, boxes


def contrasts(image: np.ndarray, boxes) -> np.ndarray:
    """Độ tương phản mực/giấy trong từng hộp, theo mức xám."""
    grey = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    height, width = grey.shape[:2]
    out = []
    for (x0, y0, x1, y1), _ in normalise_boxes(boxes):
        a, b = max(int(y0), 0), min(int(round(y1)) + 1, height)
        c, d = max(int(x0), 0), min(int(round(x1)) + 1, width)
        patch = grey[a:b, c:d]
        if patch.size < 4:
            out.append(0.0)
            continue
        ink, paper = np.percentile(patch, [5, 75])
        out.append(float(paper - ink))
    return np.asarray(out, dtype=np.float32)


def measure(base, boxes, chain, seed: int, floor: float) -> dict:
    before = contrasts(base, boxes)
    aged = apply_chain(base.copy(), chain, seed=seed, regions=boxes)
    after = contrasts(aged, boxes)
    # Chỉ tính trên những hộp VỐN đã đọc được: một hộp trống từ đầu không phải
    # lỗi của chuỗi làm cũ, và để nó vào mẫu thì mọi chuỗi đều xấu như nhau.
    live = before >= floor
    if not live.any():
        return {"boxes": 0, "kept": 1.0, "worst": 1.0, "lost": 0.0}
    kept = after[live] / np.maximum(before[live], 1e-6)
    return {
        "boxes": int(live.sum()),
        "kept": round(float(kept.mean()), 3),
        "worst": round(float(kept.min()), 3),
        "lost": round(100.0 * float((after[live] < floor).mean()), 1),
        "image": aged,
    }


def chains_from_rules(only) -> list[tuple[str, list]]:
    rules = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    out = []
    for option in rules["options"]:
        if only and option["id"] not in only:
            continue
        chain = []
        for entry in option["params"].get("chain") or []:
            name = entry[0]
            options = dict(entry[1]) if len(entry) > 1 and entry[1] else {}
            if name == "paper_texture":
                # `apply_recipe` fills this in from `visual.paper`; here there is
                # no recipe, so name a sheet or the model picks a different one
                # per run and the numbers stop being comparable.
                options.setdefault("paper", "office_a5")
            chain.append((name, options))
        out.append((option["id"], chain))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", type=Path, help="a rendered page; default is a probe page")
    parser.add_argument("--boxes", type=Path, help="JSON with a `boxes` list, for --source")
    parser.add_argument("--chain", action="append", default=[],
                        help="only these chain ids (repeatable)")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--floor", type=float, default=28.0,
                        help="grey levels below which a box counts as unreadable")
    parser.add_argument("--out", type=Path, help="write each aged page here")
    args = parser.parse_args()

    if args.source:
        base = cv2.imread(str(args.source), cv2.IMREAD_COLOR)
        if base is None:
            raise SystemExit(f"cannot read {args.source}")
        if not args.boxes:
            raise SystemExit("--source needs --boxes: without labels there is nothing to check")
        boxes = json.loads(args.boxes.read_text(encoding="utf-8"))
        boxes = boxes.get("boxes", boxes) if isinstance(boxes, dict) else boxes
    else:
        base, boxes = probe_page()

    chains = chains_from_rules(set(args.chain))
    if not chains:
        raise SystemExit(f"no chain matched {args.chain}")
    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)

    print(f"{len(boxes)} boxes, floor {args.floor:.0f} grey levels, seed {args.seed}\n")
    print(f"{'chain':22} {'boxes':>5} {'kept':>6} {'worst':>6} {'lost %':>7}")
    worst = []
    for name, chain in chains:
        result = measure(base, boxes, chain, args.seed, args.floor)
        flag = ""
        if result["lost"] >= 5.0:
            flag = "  <-- poisons labels"
            worst.append((name, result["lost"]))
        elif result["lost"] > 0:
            flag = "  <-- some"
        print(f"{name:22} {result['boxes']:5} {result['kept']:6.2f} "
              f"{result['worst']:6.2f} {result['lost']:7.1f}{flag}")
        if args.out and "image" in result:
            cv2.imwrite(str(args.out / f"legibility-{name}.jpg"), result["image"],
                        [cv2.IMWRITE_JPEG_QUALITY, 88])

    if worst:
        print("\nChains losing 5% or more of their boxes to the ageing:")
        for name, lost in sorted(worst, key=lambda pair: -pair[1]):
            print(f"  {name:22} {lost:5.1f}%")
        return 1
    print("\nEvery chain keeps every box above the floor.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
