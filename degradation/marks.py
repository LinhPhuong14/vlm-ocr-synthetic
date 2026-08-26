"""Nét người ta thêm vào tờ giấy sau khi in. Chuyển thể từ Augraphy.

`Markup` và `Scribbles`. Hai mô hình này khác mười lăm mô hình còn lại trong
thư mục ở một chỗ căn bản: chúng **không phải hỏng**. Không máy nào gây ra
chúng, không thời gian nào làm chúng mọc lên. Một người cầm bút và đánh dấu
một chỗ họ quan tâm — chỗ ấy gần như luôn là một Ô CỤ THỂ chứ không phải một
vùng ngẫu nhiên trên trang. Kế toán tô vàng dòng "Tổng cộng", khoanh tròn mã
số thuế, gạch xoá một dòng ghi sai rồi viết đè.

Vì thế cả hai nhận tham số `regions`, và `regions.by_box` tự nhận ra điều đó
mà đi lối `place`: gọi một lần cho mỗi ô, đưa toạ độ ô vào, để nét bút bám
đúng chân dòng chữ. Gọi trực tiếp không có `regions` thì chúng tự bốc chỗ, cho
trường hợp ảnh không có nhãn.

**Nhãn vẫn phải đọc được.** Bút dạ quang trộn theo lối NHÂN nên chữ nằm dưới
vẫn còn; cùng lý do với `pattern_overlay`. Nét gạch xoá thì đè hẳn lên — mà
gạch xoá thì đúng là để không đọc được nữa, nên `crossed_off` là mô hình duy
nhất ở đây có quyền che chữ, và một chuỗi dùng nó là một chuỗi cố ý sinh ra ô
không đọc được.
"""

from __future__ import annotations

import math
import random
from typing import Sequence

import numpy as np

from .texture import _as_bgr, _restore

# BGR. Bút dạ quang bão hoà cao và sáng, bút bi thì tối và ngả xanh mực.
HIGHLIGHTER = {
    "yellow": (60, 245, 250),
    "green": (140, 240, 170),
    "pink": (190, 170, 250),
    "orange": (90, 200, 250),
}
PEN = {
    "blue": (150, 60, 30),
    "red": (45, 45, 205),
    "black": (35, 35, 35),
}
STYLES = ("highlight", "underline", "strikethrough", "circle", "crossed_off")


def _wobble(points: np.ndarray, amount: float, rng: random.Random) -> np.ndarray:
    """Làm run một đường: cộng nhiễu tần số thấp vuông góc với hướng đi.

    Tay người không vẽ được đường thẳng, và một đường thẳng tuyệt đối là dấu
    hiệu rõ nhất của nét do máy vẽ. Nhiễu phải TẦN SỐ THẤP — run đều từng pixel
    ra nét răng cưa, không ra nét tay.
    """
    if amount <= 0 or len(points) < 3:
        return points
    count = len(points)
    phase = rng.uniform(0, math.tau)
    waves = rng.uniform(1.2, 2.8)
    t = np.linspace(0.0, 1.0, count, dtype=np.float32)
    offset = np.sin(t * waves * math.tau + phase) * amount
    offset += np.sin(t * waves * 2.7 * math.tau + phase * 1.7) * amount * 0.4

    direction = np.gradient(points, axis=0)
    norm = np.linalg.norm(direction, axis=1, keepdims=True)
    normal = np.stack([-direction[:, 1], direction[:, 0]], axis=1) / np.maximum(norm, 1e-6)
    return points + normal * offset[:, None]


def _stroke(canvas, points, colour, width, rng):
    import cv2

    path = np.asarray(points, dtype=np.int32).reshape(-1, 1, 2)
    cv2.polylines(canvas, [path], False, colour, max(int(width), 1), cv2.LINE_AA)


def _random_regions(shape, count, rng) -> list[tuple[float, float, float, float]]:
    """Ô giả, cho ảnh không có nhãn — cỡ một dòng chữ, đặt trong lề."""
    height, width = shape[:2]
    line = max(height * 0.018, 8.0)
    out = []
    for _ in range(max(int(count), 1)):
        w = rng.uniform(width * 0.12, width * 0.45)
        x = rng.uniform(width * 0.06, max(width * 0.94 - w, width * 0.06))
        y = rng.uniform(height * 0.06, height * 0.92)
        out.append((x, y, x + w, y + line))
    return out


def markup(
    image: np.ndarray,
    style: str = "highlight",
    colour: str = "auto",
    opacity: float = 0.75,
    width: float = 0.14,
    wobble: float = 0.35,
    count: int = 2,
    regions: Sequence[tuple[float, float, float, float]] | None = None,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Bút đánh dấu lên một ô: tô, gạch chân, gạch ngang, khoanh tròn, gạch xoá.

    Chuyển thể `Markup`. Năm lối, và bốn tham số hình học đều tính THEO CHIỀU
    CAO Ô — nét bút to bằng bao nhiêu là so với cỡ chữ, không so với pixel, nên
    cùng một chuỗi cho ra nét đúng cỡ trên tờ hoá đơn nhiệt lẫn tờ A4.

    * `highlight`     tô phủ, trộn NHÂN, chữ dưới còn đọc được.
    * `underline`     gạch chân, ngay dưới chân chữ.
    * `strikethrough` gạch ngang giữa ô.
    * `circle`        khoanh tròn quanh ô, nét không khép kín hẳn.
    * `crossed_off`   gạch chéo hai nét — **che mất chữ**, xem ghi chú đầu file.

    `colour: auto` bốc bút dạ quang cho `highlight` và bút bi cho các lối còn
    lại; đó là cách người ta thật sự dùng hai loại bút ấy.
    """
    import cv2

    if style not in STYLES:
        raise ValueError(f"style must be one of {STYLES}; got {style!r}")
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    rects = list(regions) if regions else _random_regions(bgr.shape, count, rng)
    if not rects:
        return image

    if colour == "auto":
        palette = HIGHLIGHTER if style == "highlight" else PEN
        ink = palette[rng.choice(sorted(palette))]
    elif colour in HIGHLIGHTER:
        ink = HIGHLIGHTER[colour]
    elif colour in PEN:
        ink = PEN[colour]
    else:
        raise ValueError(
            f"unknown colour {colour!r}; have 'auto', "
            f"{', '.join(sorted(HIGHLIGHTER) + sorted(PEN))}")

    # MỘT lớp phủ duy nhất, mang độ đậm chứ không mang màu. Bản đầu dựng hai
    # lớp -- một lớp màu, một lớp alpha -- và sai ở hai chỗ cùng lúc: hai lớp
    # bốc bề rộng nét riêng nên lệch nhau, và lớp alpha loe rộng hơn lớp màu
    # sau khi làm mềm, nên quanh vệt bút dạ quang có một quầng ĐEN (chỗ alpha
    # đã lớn hơn 0 mà màu vẫn còn là 0). Một lớp thì không có chỗ cho hai thứ
    # ấy lệch nhau.
    layer = np.zeros(bgr.shape[:2], dtype=np.float32)

    for x0, y0, x1, y1 in rects:
        tall = max(y1 - y0, 2.0)
        pen = max(width * tall, 1.0)
        run = max(int(x1 - x0), 8)
        # Nét bút vượt qua hai đầu ô: người ta bắt đầu trước chữ và kết thúc
        # sau chữ, không bao giờ khớp đúng mép.
        over = tall * rng.uniform(0.1, 0.45)
        xs = np.linspace(x0 - over, x1 + over, max(run // 3, 6), dtype=np.float32)

        if style == "highlight":
            # Tô là một nét bút RẤT dày, không phải một hình chữ nhật: đầu bút
            # dạ quang bè ngang, tô một lượt thì hai mép cũng run theo tay.
            mid = np.full_like(xs, (y0 + y1) * 0.5 + tall * rng.uniform(-0.06, 0.06))
            path = _wobble(np.stack([xs, mid], axis=1), tall * wobble * 0.25, rng)
            _stroke(layer, path, (1.0,), tall * rng.uniform(1.0, 1.25), rng)
        elif style in ("underline", "strikethrough"):
            base = y1 + tall * rng.uniform(0.05, 0.2) if style == "underline" \
                else (y0 + y1) * 0.5
            ys = np.full_like(xs, base) + np.linspace(
                0, tall * rng.uniform(-0.12, 0.12), len(xs), dtype=np.float32)
            path = _wobble(np.stack([xs, ys], axis=1), tall * wobble, rng)
            _stroke(layer, path, (1.0,), pen, rng)
        elif style == "circle":
            cx, cy = (x0 + x1) * 0.5, (y0 + y1) * 0.5
            rx = (x1 - x0) * 0.5 + tall * 0.5
            ry = tall * rng.uniform(0.85, 1.3)
            # Không khép kín: bắt đầu và kết thúc lệch nhau, như tay quay một
            # vòng rồi nhấc bút.
            start = rng.uniform(0, math.tau)
            sweep = math.tau * rng.uniform(0.88, 1.06)
            angle = np.linspace(start, start + sweep, 90, dtype=np.float32)
            path = np.stack([cx + rx * np.cos(angle), cy + ry * np.sin(angle)], axis=1)
            path = _wobble(path, tall * wobble * 0.6, rng)
            _stroke(layer, path, (1.0,), pen, rng)
        else:                                            # crossed_off
            for x_start, x_end in ((x0 - over, x1 + over), (x1 + over, x0 - over)):
                xs2 = np.linspace(x_start, x_end, 24, dtype=np.float32)
                ys2 = np.linspace(y0, y1, 24, dtype=np.float32)
                path = _wobble(np.stack([xs2, ys2], axis=1), tall * wobble, rng)
                _stroke(layer, path, (1.0,), pen, rng)

    layer = cv2.GaussianBlur(layer, (0, 0), 0.6) * float(opacity)
    weight = np.clip(layer, 0, 1)[..., None]
    base = bgr.astype(np.float32)
    tint = np.float32(ink) / 255.0
    if style == "highlight":
        # NHÂN: mực bút phủ lên thì chỗ đã tối vẫn tối, chữ không bị lấp. Hệ số
        # nhân đi từ 1 (không phủ) tới `tint` (phủ hết) theo chính `weight`, nên
        # mép vệt nhạt dần đúng bằng lượng mực có ở đấy.
        out = base * (1.0 - weight * (1.0 - tint))
    else:
        out = base * (1.0 - weight) + np.float32(ink) * weight
    return _restore(np.clip(out, 0, 255).astype(np.uint8), was_gray)


def scribbles(
    image: np.ndarray,
    count: int = 2,
    colour: str = "auto",
    opacity: float = 0.8,
    width: float = 0.17,
    turns: int = 7,
    reach: float = 1.6,
    regions: Sequence[tuple[float, float, float, float]] | None = None,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Nét nguệch ngoạc: một đường bút đi lòng vòng rồi nhấc lên.

    Chuyển thể `Scribbles`. Khác `markup` ở chỗ nó không đánh dấu gì cả — đây
    là nét thử bút, nét tính nhẩm bên lề, chữ ký nháp, vết bút trẻ con. Nên nó
    KHÔNG bám theo hình dạng ô: `regions` chỉ cho biết vẽ ở QUANH đâu, còn nét
    thì tràn ra ngoài (`reach` là mức tràn, tính theo chiều cao ô).

    Đường đi dựng bằng bước ngẫu nhiên có quán tính — hướng đi lệch dần chứ
    không bốc lại từ đầu mỗi bước — rồi làm trơn. Bốc lại hướng mỗi bước cho ra
    nét gãy khúc như tia sét, không ra nét bút.
    """
    import cv2

    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    rects = list(regions) if regions else _random_regions(bgr.shape, count, rng)
    if not rects:
        return image

    if colour == "auto":
        ink = PEN[rng.choice(sorted(PEN))]
    elif colour in PEN:
        ink = PEN[colour]
    elif colour in HIGHLIGHTER:
        ink = HIGHLIGHTER[colour]
    else:
        raise ValueError(f"unknown colour {colour!r}; have 'auto', {', '.join(sorted(PEN))}")

    layer = np.zeros(bgr.shape[:2], dtype=np.float32)
    height, width_px = bgr.shape[:2]
    for x0, y0, x1, y1 in rects:
        tall = max(y1 - y0, 2.0)
        step = tall * float(reach) * 0.5
        x, y = (x0 + x1) * 0.5, (y0 + y1) * 0.5
        heading = rng.uniform(0, math.tau)
        path = [(x, y)]
        for _ in range(max(int(turns), 2) * 4):
            heading += rng.gauss(0, 0.9)              # quán tính: lệch, không bốc lại
            x += math.cos(heading) * step * rng.uniform(0.5, 1.0)
            y += math.sin(heading) * step * rng.uniform(0.5, 1.0)
            x = min(max(x, 2.0), width_px - 3.0)
            y = min(max(y, 2.0), height - 3.0)
            path.append((x, y))
        points = np.asarray(path, dtype=np.float32)
        # Làm trơn bằng trung bình trượt: nét bút có bán kính cong, bước ngẫu
        # nhiên thì không.
        kernel = np.ones(5, dtype=np.float32) / 5.0
        smooth = np.stack([np.convolve(points[:, 0], kernel, "same"),
                           np.convolve(points[:, 1], kernel, "same")], axis=1)[2:-2]
        if len(smooth) >= 2:
            _stroke(layer, smooth, (1.0,), max(width * tall, 1.0), rng)

    layer = cv2.GaussianBlur(layer, (0, 0), 0.5) * float(opacity)
    weight = np.clip(layer, 0, 1)[..., None]
    out = bgr.astype(np.float32) * (1.0 - weight) + np.float32(ink) * weight
    return _restore(np.clip(out, 0, 255).astype(np.uint8), was_gray)


__all__ = ["HIGHLIGHTER", "PEN", "STYLES", "markup", "scribbles"]
