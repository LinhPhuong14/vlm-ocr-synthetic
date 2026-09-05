#!/usr/bin/env python3
"""Render `page.html` and measure it with the renderer's own box code.

    generators/html/.venv/bin/python samples/label-axes/measure.py

The point is not the picture. It is that the three-axis vocabulary has to
survive the same measurement every shipped page goes through: the boxes come
off the DOM *after* CSS has run, read by the same `CELL_RECTS_JS` in
`generators/html/page.py`, with `data-region` / `data-role` / `data-ink` read
alongside `data-kind`.

A tag that produces no box is a tag the dataset cannot carry, and this script
is what says so out loud -- per axis, per value, with the count.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

from page import CELL_RECTS_JS, find_chromium, font_faces, served  # noqa: E402

HERE = Path(__file__).resolve().parent

# The renderer's own measurement, with the three axes read beside `kind`. The
# body stays `CELL_RECTS_JS` verbatim apart from three splices, so this cannot
# drift into measuring something the renderer does not.
#
# `push` is a closure that never sees `span` -- it is called from two places
# inside the loop and takes only (kind, text, box). So the axes are lifted into
# a variable the loop sets and the closure reads, rather than added as
# parameters at two call sites written differently.
AXES_JS = CELL_RECTS_JS
for _old, _new in (
    ("const push = (kind, text, box) => {",
     "let axes = {};\n  const push = (kind, text, box) => {"),
    ("out.push({kind, text,", "out.push({kind, text, ...axes,"),
    ("const kind = span.dataset.kind;",
     "const kind = span.dataset.kind;\n"
     "    axes = {region: span.dataset.region ?? '',"
     " role: span.dataset.role ?? '', ink: span.dataset.ink ?? ''};"),
):
    assert AXES_JS.count(_old) == 1, _old
    AXES_JS = AXES_JS.replace(_old, _new)

# Trục 1 là từ vựng của BÊN DÙNG dữ liệu, không phải của kho này -- cùng lý do
# `PAGE_LABELS` bị khoá: một lớp thứ 21 ở đây là một lớp không ai có class cho.
# Ba sửa so với danh sách nhận được:
#   + `Title`       — danh sách có `Section-Header` nhưng không có tên tài liệu
#   ~ `Blank-Page`  — xuống mức TRANG: trang trắng không có hộp nào để gắn nhãn
#   ~ `Formula`     — gộp `Equation-Block` + `Chemical-Block`. Mô hình dò bố cục
#                     nhìn hình dạng, và trên trang hai thứ ấy là CÙNG một hình:
#                     dòng ngắn căn giữa, có chỉ số dưới, đôi khi đánh số bên
#                     phải. Tách chúng đòi hiểu nội dung — việc của chặng sau.
REGIONS = ("Caption", "Footnote", "Formula", "List-Group", "Page-Header",
           "Page-Footer", "Image", "Section-Header", "Table", "Text",
           "Complex-Block", "Code-Block", "Form", "Table-Of-Contents", "Figure",
           "Diagram", "Bibliography", "Title")
PAGE_ONLY = ("Blank-Page",)
# Vùng chưa có ví dụ, và KHAI RA thay vì chế một ví dụ cho vừa cái nhãn.
#
# `Complex-Block` định nghĩa là "khối con có region khác nhau và tách ra thì mất
# nghĩa". Ba trang này không có trường hợp nào như thế: bảng có chú thích trên và
# ghi chú dưới tách ra được sạch sẽ, và mọi bộ dữ liệu bố cục đều tách. Bản trước
# gán khối ấy là `Complex-Block` chỉ để lớp này xuất hiện — chế nội dung cho vừa
# cái nhãn, đúng thứ đầu độc bộ dữ liệu huấn luyện.
#
# Ứng viên thật cho lớp này là khối mà cái khung MANG NGHĨA "đây là một đơn vị":
# một mẩu rao vặt trên báo (tiêu đề + thân + số điện thoại + logo nhỏ, đóng
# khung, tách ra là mất "đây là MỘT mẩu quảng cáo"). Kho có phôi báo, nên đó là
# chỗ nó nên xuất hiện — không phải ở đây.
DECLARED_GAP = ("Complex-Block",)
# Trục 2 là từ vựng của kho này: nó chia nhỏ BÊN TRONG một region, nên nó tự do
# hơn -- không ai ở ngoài đọc nó, và nó là chỗ 158 `kind` rút về một bộ chuẩn.
ROLES = ("key", "value", "heading", "subheading", "colhdr", "rowhdr", "cell",
         "total", "body", "item", "caption", "note", "mark")
INKS = ("print", "hand", "stamp", "dotmatrix", "thermal", "reversed")
PAGES = ("page.html", "page2.html", "page3.html")

# Trục 1 đo ở mức KHỐI, không phải mức run. Một `region` là một vùng của trang,
# nên hộp của nó phải là hộp của khối -- với một bảng, đó là hộp theo ĐƯỜNG KẺ,
# không phải bao lồi của chữ trong bảng. Cái đó không suy ra được từ hộp của các
# run bên trong: bao lồi của chữ nằm gọn bên trong đường kẻ, thiếu mất lề ô, và
# thiếu cả hàng nào tình cờ rỗng.
#
# Nhưng cũng KHÔNG phải hộp của thẻ chứa: một `<div>` tiêu đề là block, nên nó
# rộng cả khổ giấy trong khi chữ căn giữa chỉ chiếm một phần ba -- và chỗ trống
# hai bên không có gì được vẽ ra cả.
#
# Định nghĩa đúng là thứ một người gán nhãn sẽ khoanh: **mực, cộng với hình mà
# vùng ấy tự vẽ ra**. Nên hộp vùng là hợp của hai thứ -- hộp của mọi run bên
# trong, và hộp của mọi phần tử CÓ viền hoặc CÓ nền. Bảng lấy theo đường kẻ vì
# đường kẻ là hình nó vẽ; tiêu đề bám sát chữ vì nó không vẽ gì.
REGION_BOX_JS = """() => {
  const sheet = document.querySelector('#sheet').getBoundingClientRect();
  // Có vẽ ra gì không: viền thấy được, hoặc nền không trong suốt. Đây là phép
  // thử phân biệt "khối này CÓ hình" với "khối này chỉ là chỗ xếp chữ".
  const paints = (el) => {
    const st = getComputedStyle(el);
    const bg = st.backgroundColor;
    if (bg && bg !== 'transparent' && !/rgba\(0,\s*0,\s*0,\s*0\)/.test(bg)) return true;
    for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
      const w = parseFloat(st['border' + side + 'Width']);
      const style = st['border' + side + 'Style'];
      if (w > 0 && style && style !== 'none' && style !== 'hidden') return true;
    }
    return false;
  };
  const grow = (u, r) => {
    if (r.width < 1 && r.height < 1) return u;
    return u === null ? {l: r.left, t: r.top, r: r.right, b: r.bottom}
      : {l: Math.min(u.l, r.left), t: Math.min(u.t, r.top),
         r: Math.max(u.r, r.right), b: Math.max(u.b, r.bottom)};
  };
  const out = [];
  for (const el of document.querySelectorAll('#sheet [data-region-box]')) {
    let u = null;
    // 1. mực: hợp của mọi run có nhãn bên trong. Một tiêu đề căn giữa thì đây
    //    là chính chữ ấy, không phải cả bề ngang tờ giấy.
    for (const run of el.querySelectorAll('[data-kind]')) u = grow(u, run.getBoundingClientRect());
    if (el.hasAttribute('data-kind')) u = grow(u, el.getBoundingClientRect());
    // 2. hình: hộp của chính khối và của mọi con CÓ VẼ ra gì -- đường kẻ bảng,
    //    dải nền, khung ảnh. Đó là phần thuộc về vùng mà mực không chạm tới.
    if (paints(el)) u = grow(u, el.getBoundingClientRect());
    for (const kid of el.querySelectorAll('*')) {
      if (paints(kid)) u = grow(u, kid.getBoundingClientRect());
    }
    if (u === null) continue;
    out.push({region: el.dataset.regionBox,
              x: u.l - sheet.left, y: u.t - sheet.top,
              w: u.r - u.l, h: u.b - u.t});
  }
  return out;
}"""


def measure(name: str) -> tuple[list[dict], list[dict]]:
    from playwright.sync_api import sync_playwright

    html = (HERE / name).read_text(encoding="utf-8")
    markup = (f"<!doctype html><meta charset='utf-8'><style>{font_faces()}"
              f"body{{margin:0;background:#e9edf1;padding:20px}}</style>{html}")
    chromium = find_chromium()
    # `served`, not `set_content`: an `about:blank` origin will not fetch a
    # `file://` @font-face, and it fails silently -- the face registers, stays
    # `unloaded` forever, and the page is drawn in whatever the machine has.
    # The symptom is Vietnamese, not Latin: the container's fallback draws
    # `tử gốc` as `tư` with a spacing hook after it, eating the space. Every
    # font then renders identically, which is the tell.
    with served(markup) as url, sync_playwright() as play:
        browser = play.chromium.launch(
            executable_path=str(chromium) if chromium else None)
        page = browser.new_page(viewport={"width": 900, "height": 1200},
                                device_scale_factor=2)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(250)
        rects = page.evaluate(AXES_JS)
        blocks = page.evaluate(REGION_BOX_JS)
        page.locator("#sheet").screenshot(
            path=str(HERE / name.replace(".html", ".png")))
        browser.close()
    return rects, blocks


def _overlap(a: dict, b: dict) -> float:
    """Diện tích giao nhau của hai hộp."""
    x = max(0.0, min(a["x"] + a["w"], b["x"] + b["w"]) - max(a["x"], b["x"]))
    y = max(0.0, min(a["y"] + a["h"], b["y"] + b["h"]) - max(a["y"], b["y"]))
    return x * y


# In đè là thuộc tính của MỰC, không phải của vùng.
#
# Bản trước khai ngoại lệ theo tên vùng (`Image`, `Figure`), và nó vỡ ngay khi
# con dấu "ĐÃ SOÁT XÉT" được sửa từ `Image` sang `Text` -- đúng chỗ nó thuộc
# về, vì chữ trong dấu đọc được. Cái làm một thứ "in đè" không phải là nó thuộc
# vùng nào, mà là mực của nó: dấu đóng lên trên, hoạ tiết in chồng. Nên phép
# thử hỏi trục 3 và trục 2, không hỏi trục 1.
OVERPRINT_INK = frozenset({"stamp"})
OVERPRINT_ROLE = frozenset({"mark"})


def _overprints(runs: list[dict]) -> bool:
    """Cả cụm run này có phải mực in đè lên chỗ khác không."""
    return bool(runs) and all(
        r["ink"] in OVERPRINT_INK or r["role"] in OVERPRINT_ROLE for r in runs)

# Vùng được phép CHỨA vùng khác, khai tường minh. Một `Figure` theo định nghĩa
# là ảnh cộng chú thích, nên nó chứa một `Caption` -- đó là cấu trúc, không phải
# lỗi. Khai ở đây thay vì bỏ qua mọi trường hợp lồng nhau: một cái lồng KHÔNG
# khai vẫn phải báo lỗi, vì phần lớn cái lồng là lỗi thật.
MAY_NEST = {
    # `Figure` = ảnh CỘNG chú thích, một khối. Ảnh bên trong KHÔNG gắn thêm
    # nhãn `Image`: hai vùng khác lớp phủ cùng một vùng pixel là hai đích mâu
    # thuẫn cho mô hình. Phân biệt: có chú thích -> `Figure`; không có -> `Image`.
    "Figure": {"Caption"},
    "Complex-Block": {"Table", "Caption", "Text", "Section-Header"},
}

# Dưới ngưỡng này thì hỏi lại: vùng gần như trống. Không phải lỗi -- một bảng
# phần lớn là giấy trắng giữa các đường kẻ, một khối chữ ký phần lớn là chỗ
# trống để ký -- nhưng là chỗ phải giải thích được.
THIN = 0.30


def audit(runs: list[dict], blocks: list[dict]) -> int:
    """Ba phép kiểm mà một bộ dữ liệu dò bố cục phải qua.

    Kiểm "mọi tag đều ra hộp" là kiểm CƠ HỌC: nó nói bộ từ vựng dùng được, không
    nói bộ chú thích đúng. Ba phép dưới đây hỏi câu của người gán nhãn.
    """
    print("── kiểm chú thích ───────────────────────────────────────────")
    bad = 0

    # 1. Một vùng không được chứa run của vùng khác. Đây là phép bắt được lỗi
    #    thật: tiêu đề của một danh sách nằm trong hộp List-Group thì mô hình
    #    học rằng tiêu đề là một mục của danh sách.
    inside_of: dict[int, list[dict]] = {}
    for i, blk in enumerate(blocks):
        inside_of[i] = [r for r in runs if r["page"] == blk["page"]
                        and _overlap(blk, r) > 0.6 * r["w"] * r["h"]]
    for i, blk in enumerate(blocks):
        inside = inside_of[i]
        allowed = {blk["region"]} | MAY_NEST.get(blk["region"], set())
        # Mực in đè rơi vào vùng khác là chuyện thường trên giấy, không phải lỗi.
        alien = sorted({r["region"] for r in inside
                        if not (r["ink"] in OVERPRINT_INK
                                or r["role"] in OVERPRINT_ROLE)} - allowed)
        if alien:
            bad += 1
            print(f"  !! {blk['page']} {blk['region']}: chứa run của {alien}")

    # 2. Hai vùng không được chồng nhau, trừ khi một bên là thứ in đè.
    for i, a in enumerate(blocks):
        for j, b in enumerate(blocks[i + 1:], start=i + 1):
            if a["page"] != b["page"]:
                continue
            small = min(a["w"] * a["h"], b["w"] * b["h"])
            if small and _overlap(a, b) > 0.15 * small:
                if _overprints(inside_of[i]) or _overprints(inside_of[j]):
                    continue
                # Lồng nhau đã khai thì chồng lấn là hệ quả tất yếu: `Figure`
                # chứa `Caption` thì hai hộp phải chồng. Khai một lần ở
                # `MAY_NEST`, dùng cho cả hai phép thử.
                if b["region"] in MAY_NEST.get(a["region"], set()) \
                        or a["region"] in MAY_NEST.get(b["region"], set()):
                    continue
                bad += 1
                print(f"  !! {a['page']} {a['region']} × {b['region']}: chồng nhau")

    # 3. Vùng gần như trống thì phải giải thích được, nên nó được liệt kê chứ
    #    không bị coi là lỗi.
    thin = []
    for blk in blocks:
        area = blk["w"] * blk["h"]
        if not area:
            continue
        ink = sum(_overlap(blk, r) for r in runs if r["page"] == blk["page"])
        if ink / area < THIN:
            thin.append((blk, ink / area))
    print(f"  {len(thin)} vùng mực phủ dưới {THIN:.0%} — phải giải thích được:")
    for blk, cover in sorted(thin, key=lambda t: t[1]):
        print(f"     {blk['page']:11s} {blk['region']:18s} {cover * 100:5.1f}%")
    print(f"\n  lỗi chú thích: {bad}\n")
    return bad


def report(rects: list[dict]) -> int:
    counts = {"region": collections.Counter(), "role": collections.Counter(),
              "ink": collections.Counter()}
    for box in rects:
        for axis in counts:
            counts[axis][box[axis]] += 1

    print(f"{len(rects)} hộp đo được từ DOM, trên {len(PAGES)} trang\n")
    missing = []
    for axis, expected in (("region", REGIONS), ("role", ROLES), ("ink", INKS)):
        seen = counts[axis]
        print(f"── {axis} ── {len(seen)}/{len(expected)} giá trị có hộp")
        for value in expected:
            n = seen.get(value, 0)
            mark = "  " if n else ("--" if value in DECLARED_GAP else "!!")
            print(f"  {mark} {value:14s} {n:4d}")
            if not n and value not in DECLARED_GAP:
                missing.append(f"{axis}={value}")
        extra = sorted(set(seen) - set(expected) - {""})
        if extra:
            print(f"     ngoài từ vựng: {extra}")
        print()
    print(f"chỉ ở mức trang, không thể là hộp: {', '.join(PAGE_ONLY)}")
    print(f"chưa có ví dụ, khai ra chứ không chế: {', '.join(DECLARED_GAP)}\n")

    # Every box must carry all three axes. A box missing one is a box a
    # consumer cannot filter, which is the whole failure this design exists
    # to remove.
    bare = [b for b in rects if not (b["region"] and b["role"] and b["ink"])]
    print(f"hộp thiếu ít nhất một trục: {len(bare)}")
    for box in bare[:5]:
        print(f"   {box['kind']}: region={box['region']!r} "
              f"role={box['role']!r} ink={box['ink']!r}")

    (HERE / "boxes.json").write_text(
        json.dumps(rects, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n-> {HERE / 'boxes.json'}\n-> {HERE / 'page.png'}")
    return 1 if (missing or bare) else 0


if __name__ == "__main__":
    boxes: list[dict] = []
    blocks: list[dict] = []
    for _name in PAGES:
        got, block = measure(_name)
        for _row in (*got, *block):
            _row["page"] = _name
        print(f"{_name:14s} {len(got):4d} run · {len(block):3d} khối")
        boxes += got
        blocks += block
    (HERE / "regions.json").write_text(
        json.dumps(blocks, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print()
    _bad = report(boxes)
    raise SystemExit(_bad + audit(boxes, blocks))
