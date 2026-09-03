"""Áp một mô hình làm cũ lên VÀI Ô CHỮ, không lên cả trang.

Mười bốn mô hình có trước module này đều áp đều khắp mặt giấy. Trên ảnh thật
thì gần như không hỏng nào như thế: cây bút dạ quang chỉ tô một dòng, cái kim
gãy của máy in chỉ ăn một dải ngang, vết trống mực bẩn chỉ chạy một sọc dọc,
người ta chỉ khoanh tròn ô "Tổng cộng". Hỏng có CHỖ, và chỗ ấy gần như luôn
trùng với chỗ có chữ — vì chữ là thứ người ta đánh dấu và là thứ máy in in ra.

Module này nhận danh sách hộp nhãn của trang, bốc ra một phần trong đó theo
một trong sáu lối bốc, rồi áp hiệu ứng chỉ ở đấy.

## Hai lối áp, và vì sao phải có cả hai

`mask` — **áp hiệu ứng lên BẢN SAO CẢ TRANG rồi hoà lại qua một mặt nạ.**
Nghe vòng, nhưng đây mới là lối đúng cho hiệu ứng có cấu trúc trải dài: một
vệt trống mực bẩn vắt qua hai ô chữ phải là MỘT vệt liền. Cắt ảnh ra từng ô
rồi chạy hiệu ứng trên từng mẩu sẽ cho hai vệt lệch nhau ở chỗ giáp ranh —
nhìn là biết ghép. Chạy trên cả trang thì hoạ tiết liền mạch sẵn, mặt nạ chỉ
quyết định chỗ nào cho nó hiện ra.

`place` — **gọi mô hình một lần cho mỗi ô, đưa toạ độ ô vào.** Dành cho thứ
được VẼ THÊM chứ không phải lọc: nét gạch chân phải bám đúng chân dòng chữ,
vòng khoanh phải ôm đúng ô. Mô hình nào nhận tham số `regions` thì tự khắc đi
đường này (xem `_wants_regions`).

## Mép mặt nạ

Mặt nạ hình chữ nhật sắc cạnh là cách nhanh nhất để lộ ra ảnh tổng hợp: không
hỏng nào trên giấy có mép thẳng và góc vuông. Nên mặt nạ ở đây đi qua ba bước
trước khi dùng: **nới** ô ra (`pad`, vì hộp nhãn ôm sát chữ còn vết bẩn thì
không), **làm rách mép** bằng nhiễu tần số thấp (`ragged`), rồi **loe** mép
(`feather`). Hợp mọi ô lại RỒI mới làm ba bước ấy, nếu không hai ô cạnh nhau
sẽ để lại đường nối ở giữa.

## Không có hộp thì sao

`by_box` **báo lỗi**, chứ không lặng lẽ quay về áp cả trang. Một chuỗi khai là
áp theo ô mà thực ra áp cả trang là đúng loại hỏng ngầm mà repo này đã bị
nhiều lần. Ảnh không có nhãn — thư mục trang đã render, ảnh quét thật — thì
gọi `boxes_from_ink()` để DÒ ra hộp; đó là dò, không phải nhãn, và gọi tên nó
như thế để người đọc biết mình đang có gì.
"""

from __future__ import annotations

import inspect
import random
from typing import Any, Callable, Iterable, Sequence

# **Numpy và OpenCV nạp trong hàm, không nạp ở đầu file.** Nửa trên của module
# này -- đọc hộp, sắp thứ tự đọc, bốc ô -- là logic DỮ LIỆU: nó quyết định ô
# nào được chọn, và câu trả lời không phụ thuộc một pixel nào. Nửa dưới --
# mặt nạ, hoà ảnh, dò hộp -- mới cần tới ảnh.
#
# Tách ra thế vì bộ test của repo chỉ có pytest và PyYAML, cố ý (xem
# `tests/conftest.py`). Nạp numpy ở đầu file thì mọi test về lối bốc phải chạy
# trong virtualenv của renderer, mà một test phải dựng môi trường mới chạy
# được là một test không ai chạy.

# (x0, y0, x1, y1) trong toạ độ ảnh, kèm `kind` của hộp nhãn.
Rect = tuple[float, float, float, float]


# ------------------------------------------------------------------ hộp vào


def normalise_boxes(boxes: Iterable[Any] | None) -> list[tuple[Rect, str]]:
    """Về một dạng duy nhất, từ mọi dạng hộp mà repo này có.

    Nhận được: `{"kind": ..., "quad": [[x, y] x 4]}` (renderer HTML và glyph
    đều ghi dạng này), `{"x", "y", "w", "h"}` (rect thô của trình duyệt),
    `(x0, y0, x1, y1)`, và mảng numpy (N, 4, 2).

    Hộp bẹp — rộng hoặc cao không quá 1 pixel — bị bỏ: nó không phải chữ, và
    nới nó ra thành một vùng thì chỉ tổ bôi bẩn chỗ trống.
    """
    out: list[tuple[Rect, str]] = []
    # `is None`, không phải `boxes or []`: mảng numpy (N, 4, 2) là một trong bốn
    # dạng hàm này khai nhận, mà `or` phải hỏi mảng ấy đúng-hay-sai và numpy
    # ném ValueError cho mảng nhiều phần tử. Nghĩa là dạng thứ tư trong danh
    # sách ngay trên KHÔNG dùng được, ở đúng dòng đầu tiên chạm vào nó.
    for box in (() if boxes is None else boxes):
        kind = ""
        if isinstance(box, dict):
            kind = str(box.get("kind") or "")
            if "quad" in box:
                found = _extent(box["quad"])
            elif {"x", "y", "w", "h"} <= set(box):
                x, y = float(box["x"]), float(box["y"])
                found = (x, y, x + float(box["w"]), y + float(box["h"]))
            else:
                continue
        else:
            found = _extent(box)
        if found is None:
            continue
        x0, y0, x1, y1 = found
        if x1 - x0 <= 1 or y1 - y0 <= 1:
            continue
        out.append(((x0, y0, x1, y1), kind))
    return out


def _extent(values) -> Rect | None:
    """(x0, y0, x1, y1) từ bốn góc, hay từ một bộ bốn số đã là hộp.

    Phân biệt hai dạng bằng cách THỬ đọc `p[0]`, không bằng cách kiểm kiểu: một
    quad của numpy chứa `np.float32`, mà `np.float32` không phải `float` của
    Python, nên kiểm kiểu sẽ đẩy quad numpy sang nhánh sai.
    """
    try:
        points = list(values)
    except TypeError:
        return None
    if not points:
        return None
    try:
        xs = [float(point[0]) for point in points]
        ys = [float(point[1]) for point in points]
    except (TypeError, IndexError, KeyError):
        if len(points) != 4:
            return None
        try:
            x0, y0, x1, y1 = (float(value) for value in points)
        except (TypeError, ValueError):
            return None
        return x0, y0, x1, y1
    return min(xs), min(ys), max(xs), max(ys)


def _reading_order(rects: Sequence[tuple[Rect, str]]) -> list[int]:
    """Chỉ số các hộp theo thứ tự đọc: dòng từ trên xuống, trong dòng trái sang phải.

    Cụm theo tâm dọc chứ không sắp thẳng theo `y0`: hai ô cùng một dòng trên
    hoá đơn hiếm khi có `y0` bằng nhau — cỡ chữ khác nhau thì đỉnh chữ khác
    nhau — nên sắp theo `y0` sẽ băm một dòng thành mấy dòng. Ngưỡng gộp lấy
    theo chiều cao TRUNG VỊ của hộp, nên nó tự co giãn theo cỡ chữ của trang.
    """
    if not rects:
        return []
    heights = sorted(r[3] - r[1] for r, _ in rects)
    tolerance = max(heights[len(heights) // 2] * 0.6, 1.0)
    order = sorted(range(len(rects)), key=lambda i: rects[i][0][1])
    lines: list[list[int]] = []
    for index in order:
        centre = (rects[index][0][1] + rects[index][0][3]) * 0.5
        if lines:
            last = lines[-1][-1]
            last_centre = (rects[last][0][1] + rects[last][0][3]) * 0.5
            if abs(centre - last_centre) <= tolerance:
                lines[-1].append(index)
                continue
        lines.append([index])
    flat: list[int] = []
    for line in lines:
        flat += sorted(line, key=lambda i: rects[i][0][0])
    return flat


# --------------------------------------------------------------- lối bốc ô


def _kind_matches(kind: str, wanted) -> bool:
    """Khớp theo TIỀN TỐ, vì vai trò của ô là tên có dấu chấm.

    Nhãn ghi `total.grand`, `total.line`, `store.name`, `sign.title`. Một chuỗi
    khai `kinds: [total]` là muốn nói "mọi ô thuộc khối tổng cộng" — bắt khớp
    đúng từng chữ thì chuỗi ấy phải liệt kê tên vai trò của từng bố cục một, và
    sẽ lặng lẽ bốc rỗng ngay khi ai đó thêm một bố cục có `total.vat`.

    Khớp cả tên đầy đủ, nên `kinds: [total.grand]` vẫn chỉ trúng đúng ô ấy.
    """
    return any(kind == want or kind.startswith(f"{want}.") for want in wanted)


def _filtered(rects, kinds, min_area) -> list[int]:
    keep = []
    for index, (rect, kind) in enumerate(rects):
        if kinds and not _kind_matches(kind, kinds):
            continue
        if (rect[2] - rect[0]) * (rect[3] - rect[1]) < min_area:
            continue
        keep.append(index)
    return keep


def _count_from(pool: int, count: int | None, fraction: float | None, default: float) -> int:
    """Bao nhiêu ô, cho `count` tuyệt đối hoặc `fraction` tương đối."""
    if count is not None:
        return max(0, min(int(count), pool))
    share = default if fraction is None else float(fraction)
    return max(1, min(pool, int(round(pool * max(share, 0.0))))) if pool else 0


def _scatter(rects, pool, shape, rng, *, count=None, fraction=None, **_):
    """Rải rác: bốc ngẫu nhiên, không quan tâm ô nào cạnh ô nào.

    Cho thứ rơi xuống trang một cách tình cờ — vết mực, chỗ mực bệt của máy
    photo, một nét bút gạch đại.
    """
    picked = list(pool)
    rng.shuffle(picked)
    return picked[: _count_from(len(pool), count, fraction, 0.25)]


def _run(rects, pool, shape, rng, *, length=None, fraction=None, **_):
    """Một đoạn LIỀN NHAU theo thứ tự đọc.

    Người ta tô bút dạ quang mấy dòng liền, không tô ba dòng cách quãng. Đây là
    khác biệt giữa nhiễu trông có lý và nhiễu trông ngẫu nhiên.
    """
    order = [i for i in _reading_order(rects) if i in set(pool)]
    if not order:
        return []
    span = _count_from(len(order), length, fraction, 0.12)
    if span <= 0:
        return []
    start = rng.randrange(max(len(order) - span + 1, 1))
    return order[start : start + span]


def _band(rects, pool, shape, rng, *, thickness=0.06, count=1, **_):
    """Mọi ô cắt qua một DẢI NGANG.

    Kim gãy của máy in kim, vệt trục lăn, nếp gấp ngang: những thứ này ăn theo
    một dải trên tờ giấy chứ không chọn ô. Bốc theo dải rồi mới lấy ô là cách
    duy nhất ra được hình dạng ấy.

    Dải đặt trong KHOẢNG CÓ CHỮ, không đặt trên cả chiều cao tờ giấy. Vệt thật
    thì chạy suốt tờ, đúng — nhưng nó chỉ THẤY được ở chỗ có mực, nên một dải
    rơi vào lề dưới là một bước trong chuỗi lặng lẽ không làm gì. Với một tờ
    A4 có nửa dưới để trắng thì chuyện ấy xảy ra ở một phần ba số lần bốc, và
    không có gì báo. Bó vào khoảng có chữ không làm lệch phân phối theo ô: mọi
    dòng vẫn có cơ hội như nhau.
    """
    height = shape[0]
    thick = max(int(height * float(thickness)), 2)
    inked_top = min(rects[i][0][1] for i in pool)
    inked_bottom = max(rects[i][0][3] for i in pool)
    chosen: set[int] = set()
    for _ in range(max(int(count), 1)):
        top = rng.uniform(inked_top - thick * 0.5, max(inked_bottom - thick * 0.5, inked_top))
        bottom = top + thick
        for index in pool:
            y0, y1 = rects[index][0][1], rects[index][0][3]
            if y1 >= top and y0 <= bottom:
                chosen.add(index)
    return sorted(chosen)


def _column(rects, pool, shape, rng, *, thickness=0.08, count=1, **_):
    """Mọi ô cắt qua một DẢI DỌC — sọc trống mực, mép giấy, bóng gáy.

    Bó vào khoảng có chữ theo trục ngang, cùng lý do với `_band`.
    """
    width = shape[1]
    thick = max(int(width * float(thickness)), 2)
    inked_left = min(rects[i][0][0] for i in pool)
    inked_right = max(rects[i][0][2] for i in pool)
    chosen: set[int] = set()
    for _ in range(max(int(count), 1)):
        left = rng.uniform(inked_left - thick * 0.5, max(inked_right - thick * 0.5, inked_left))
        right = left + thick
        for index in pool:
            x0, x1 = rects[index][0][0], rects[index][0][2]
            if x1 >= left and x0 <= right:
                chosen.add(index)
    return sorted(chosen)


def _by_kind(rects, pool, shape, rng, *, kinds=(), fraction=None, count=None, **_):
    """Bốc theo LOẠI ô, không theo chỗ đứng.

    Người ta khoanh tròn ô tiền, không khoanh tròn một ô bất kỳ. `kinds` ở đây
    lọc lần nữa trên chính nhóm đã lọc, nên khai được "một nửa số ô `total`".
    """
    wanted = set(kinds)
    subset = [i for i in pool if not wanted or _kind_matches(rects[i][1], wanted)]
    rng.shuffle(subset)
    return subset[: _count_from(len(subset), count, fraction, 1.0)]


def _all(rects, pool, shape, rng, **_):
    """Mọi ô có chữ — vẫn KHÁC cả trang: lề và khoảng trống không dính."""
    return list(pool)


POLICIES: dict[str, Callable[..., list[int]]] = {
    "scatter": _scatter,
    "run": _run,
    "band": _band,
    "column": _column,
    "kind": _by_kind,
    "all": _all,
}


def select_regions(
    boxes,
    shape: tuple[int, int],
    policy: str = "scatter",
    rng: random.Random | None = None,
    kinds: Sequence[str] = (),
    min_area: float = 0.0,
    **options,
) -> list[Rect]:
    """Những ô hiệu ứng sẽ ăn vào, theo `policy`.

    `kinds` và `min_area` lọc trước khi bốc; các tham số còn lại đi thẳng vào
    lối bốc (`fraction`, `count`, `length`, `thickness`, …).
    """
    rng = rng or random.Random(0)
    rects = normalise_boxes(boxes)
    if not rects:
        return []
    try:
        pick = POLICIES[policy]
    except KeyError:
        raise KeyError(
            f"unknown selection policy {policy!r}; have {', '.join(sorted(POLICIES))}"
        ) from None
    pool = _filtered(rects, set(kinds), float(min_area))
    if not pool:
        return []
    chosen = pick(rects, pool, shape, rng, kinds=kinds, **options)
    return [rects[i][0] for i in chosen]


# ------------------------------------------------------------------ mặt nạ


def region_mask(
    shape: tuple[int, int],
    rects: Sequence[Rect],
    pad: float = 0.35,
    feather: float = 0.5,
    ragged: float = 0.6,
    rng: random.Random | None = None,
):
    """Mặt nạ mềm phủ `rects`, mép đã nới, làm rách và loe.

    Ba tham số đều tính THEO CHIỀU CAO Ô chứ không theo pixel, nên một chuỗi
    chỉnh trên hoá đơn nhiệt cỡ chữ 22 vẫn ra đúng hình dạng ấy trên tờ A4 cỡ
    chữ 11 — pixel thì không, và đó là lý do không nhận số pixel ở đây.

    * `pad`     nới mỗi ô ra, tính theo phần chiều cao ô (0.35 = 35%).
    * `ragged`  biên độ làm rách mép, cũng theo chiều cao ô. 0 cho mép thẳng.
    * `feather` độ loe của mép sau khi đã rách.
    """
    import cv2
    import numpy as np

    rng = rng or random.Random(0)
    height, width = shape[:2]
    mask = np.zeros((height, width), dtype=np.float32)
    if not rects:
        return mask

    heights = sorted(r[3] - r[1] for r in rects)
    scale = float(heights[len(heights) // 2])
    grow = pad * scale
    for x0, y0, x1, y1 in rects:
        cv2.rectangle(
            mask,
            (int(round(x0 - grow)), int(round(y0 - grow))),
            (int(round(x1 + grow)), int(round(y1 + grow))),
            1.0, -1,
        )

    # Làm rách mép: cộng nhiễu tần số thấp rồi cắt lại ở 0.5. Cộng vào SAU khi
    # đã hợp mọi ô, nên đường nối giữa hai ô cạnh nhau biến mất cùng lúc với
    # mép ngoài. Ô nhiễu lấy theo chiều cao ô để vết rách to bằng nét chữ chứ
    # không bằng cả dòng.
    if ragged > 0 and scale > 1:
        cell = max(int(scale * 0.9), 2)
        coarse = np.asarray(
            [[rng.random() for _ in range(max(width // cell, 2))]
             for _ in range(max(height // cell, 2))],
            dtype=np.float32,
        )
        field = cv2.resize(coarse, (width, height), interpolation=cv2.INTER_CUBIC)
        blurred = cv2.GaussianBlur(mask, (0, 0), max(scale * 0.25, 0.8))
        mask = (blurred + (field - 0.5) * float(ragged) > 0.5).astype(np.float32)

    softness = max(feather * scale, 0.6)
    mask = cv2.GaussianBlur(mask, (0, 0), softness)
    return np.clip(mask, 0.0, 1.0)


def blend(base, effect, mask):
    """`base` ở ngoài mặt nạ, `effect` ở trong, hoà mềm ở mép."""
    import numpy as np

    weight = mask[:, :, None] if base.ndim == 3 else mask
    out = base.astype(np.float32) * (1.0 - weight) + effect.astype(np.float32) * weight
    return np.clip(out, 0, 255).astype(base.dtype)


# ------------------------------------------------------------- dò hộp từ ảnh


def boxes_from_ink(
    image,
    min_height: int = 6,
    max_height_ratio: float = 0.08,
    gap: int = 6,
) -> list[dict]:
    """DÒ ra các cụm chữ trên một ảnh không có nhãn.

    Không phải nhãn và đừng dùng thay nhãn: đây là ngưỡng hoá cộng một phép
    giãn ngang để nối các ký tự trong cùng một dòng thành một cụm. Có mặt để
    `by_box` chạy được trên thư mục trang đã render và trên bản quét thật —
    những chỗ không ai phát cho ta toạ độ.

    `max_height_ratio` chặn các mảng lớn: khung bảng và mảng nền tối cũng qua
    được ngưỡng, mà nới một mảng nửa trang ra thì mặt nạ phủ kín cả tờ.
    """
    import cv2

    gray = image if image.ndim == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    ink = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12)
    joined = cv2.dilate(ink, cv2.getStructuringElement(cv2.MORPH_RECT, (max(gap, 1), 1)))
    count, _, stats, _ = cv2.connectedComponentsWithStats(joined, 8)

    ceiling = image.shape[0] * max_height_ratio
    found = []
    for index in range(1, count):
        x, y, w, h, area = stats[index]
        if h < min_height or h > ceiling or w < min_height:
            continue
        if area < w * h * 0.05:      # khung rỗng: viền mỏng bao quanh chỗ trống
            continue
        found.append({"kind": "detected", "text": "",
                      "quad": [[float(x), float(y)], [float(x + w), float(y)],
                               [float(x + w), float(y + h)], [float(x), float(y + h)]]})
    return found


# ----------------------------------------------------------------- by_box


def _wants_regions(function: Callable) -> bool:
    """Mô hình có nhận `regions` không — tức là nó VẼ vào ô chứ không lọc ô."""
    try:
        return "regions" in inspect.signature(function).parameters
    except (TypeError, ValueError):       # hàm C, không đọc được chữ ký
        return False


def by_box(
    image,
    effect: str = "",
    params: dict[str, Any] | None = None,
    select: dict[str, Any] | None = None,
    pad: float = 0.35,
    feather: float = 0.5,
    ragged: float = 0.6,
    mode: str = "auto",
    regions=None,
    rng: random.Random | None = None,
):
    """Chạy `effect` chỉ trên những ô mà `select` bốc ra.

    Bọc được BẤT KỲ tên nào trong registry, kể cả mười bốn mô hình có từ
    trước — `by_box` với `ink_degradation` cho ra một trang mòn mực loang lổ
    theo dòng thay vì mòn đều, mà không phải sửa gì trong `ink_degradation`.

        - [by_box, {effect: markup, select: {policy: run, fraction: 0.1},
                    params: {style: highlight}}]

    `mode` để `auto` thì tự chọn: mô hình nhận `regions` đi lối `place` (vẽ vào
    từng ô), còn lại đi lối `mask` (chạy cả trang rồi hoà qua mặt nạ). Ép tay
    được, và ép `place` lên một mô hình không nhận `regions` là lỗi chứ không
    phải im lặng chạy lối kia.
    """
    rng = rng or random.Random(0)
    # Kiểm tham số TRƯỚC khi nạp registry, vì nạp registry là nạp cả numpy và
    # OpenCV. Nhờ thế cái chốt quan trọng nhất ở đây -- "không có hộp thì báo
    # lỗi" -- kiểm được bằng một test chạy trong môi trường trần.
    if not effect:
        raise ValueError("by_box needs `effect`: the name of the model to run")
    if effect == "by_box":
        raise ValueError("by_box cannot wrap itself")
    # `len(...) == 0`, not `not regions`: một trong ba renderer truyền hộp vào
    # dưới dạng mảng numpy (`template_receipt.py` gửi `quads`), mà `not` trên
    # mảng nhiều phần tử thì ném `ValueError: truth value ... is ambiguous`.
    # Lỗi ấy nổ ở ĐÚNG chỗ đang định báo "không có hộp nào", nên thông điệp
    # người đọc nhận được là một traceback của numpy thay vì câu giải thích
    # ngay bên dưới. `None` vẫn phải bắt riêng vì nó không có `len`.
    if regions is None or len(regions) == 0:
        raise ValueError(
            f"by_box({effect!r}) has no boxes to work on. The renderer passes them "
            "through `apply_recipe(image, recipe, seed, boxes=...)`; for an image "
            "with no labels call `degradation.regions.boxes_from_ink(image)` and "
            "pass the result. Falling back to the whole page would make a chain "
            "that says `by_box` do the one thing it says it does not.")

    from . import DEGRADATIONS, apply_one

    if effect not in DEGRADATIONS:
        raise KeyError(
            f"by_box: unknown effect {effect!r}; have {', '.join(sorted(DEGRADATIONS))}")

    params = dict(params or {})
    rects = select_regions(regions, image.shape[:2], rng=rng, **dict(select or {}))
    if not rects:
        # Bốc ra rỗng là chuyện thường -- `kind: total` trên tờ không có ô tổng
        # cộng -- và không phải lỗi. Trang đi qua nguyên vẹn.
        return image

    function = DEGRADATIONS[effect][0]
    chosen = mode
    if mode == "auto":
        chosen = "place" if _wants_regions(function) else "mask"
    if chosen == "place":
        if not _wants_regions(function):
            raise ValueError(
                f"by_box(mode='place') needs a model that takes `regions`; "
                f"{effect!r} does not. Use mode='mask'.")
        return apply_one(image, effect, {**params, "regions": rects}, rng)
    if chosen != "mask":
        raise ValueError(f"by_box: mode must be 'auto', 'mask' or 'place'; got {mode!r}")

    whole = apply_one(image, effect, params, rng)
    if whole.shape != image.shape:
        raise RuntimeError(
            f"by_box({effect!r}): the model changed the page shape "
            f"({image.shape} -> {whole.shape}), so it cannot be masked back in")
    mask = region_mask(image.shape[:2], rects, pad, feather, ragged, rng)
    return blend(image, whole, mask)


__all__ = [
    "POLICIES",
    "blend",
    "boxes_from_ink",
    "by_box",
    "normalise_boxes",
    "region_mask",
    "select_regions",
]
