"""Mực được đặt lên giấy thế nào — và hỏng thế nào. Chuyển thể từ Augraphy.

Ba mô hình của pha `ink`: `Letterpress`, `Hollow`, `DotMatrix`. Cả ba đều tác
động lên CHÍNH NÉT CHỮ chứ không lên mặt giấy, nên chúng là nhóm nguy hiểm
nhất cho nhãn — xem cảnh báo về dấu thanh ở cuối file.

Khác `ink_degradation` (DocCreator) ở chỗ: mô hình kia tả **mực đã in xong rồi
mục đi theo thời gian**, ba mô hình này tả **mực chưa bao giờ được đặt lên
giấy cho tử tế** — bản in mòn, ruy băng khô, kim gãy. Hai chuyện khác nhau, và
một tờ hoá đơn Việt Nam gặp chuyện thứ hai thường xuyên hơn.
"""

from __future__ import annotations

import random

import numpy as np

from .texture import _as_bgr, _restore

SHAPES = ("circle", "rect", "diamond")


def _ink_field(gray: np.ndarray, cell: int) -> tuple[np.ndarray, np.ndarray]:
    """Tách ảnh xám thành (mặt giấy ước lượng, lượng mực trên nó).

    Mặt giấy dựng bằng phép đóng hình thái với nhân to hơn nét chữ: chỗ nào có
    chữ thì bị lấp bằng vùng sáng quanh nó, chỗ nào là giấy thì giữ nguyên. Nhờ
    thế vân giấy, vệt ố và dải sáng tối đã có trước đều còn lại — vẽ đè một nền
    trắng phẳng lên là mất hết những thứ chuỗi phía trước vừa làm.
    """
    import cv2

    size = max(int(cell) * 2 + 1, 5)
    paper = cv2.morphologyEx(
        gray, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (size, size)))
    ink = np.clip(paper.astype(np.float32) - gray.astype(np.float32), 0, 255)
    return paper.astype(np.float32), ink


def letterpress(
    image: np.ndarray,
    clusters: int = 220,
    spread: float = 5.0,
    dots: int = 14,
    strength: float = 0.7,
    rng: random.Random | None = None,
) -> np.ndarray:
    """In typo: nét chữ rỗ hoa vì bản in ăn mực không đều.

    Chuyển thể `Letterpress`. Bản kim loại ép xuống giấy không phẳng tuyệt đối,
    nên chỗ tiếp xúc kém để lại **lỗ giấy trắng ngay giữa nét mực**. Augraphy
    dựng bằng cách rắc các cụm điểm phân phối Gauss lên trang; chỗ đắt giá là
    **cụm**, không phải điểm — điểm rắc đều là nhiễu muối tiêu, cụm mới ra vệt
    ăn mực kém.

    Lỗ chỉ đục vào chỗ CÓ mực. Rắc cả lên giấy thì ra bụi trắng trên nền trắng:
    không thấy gì, mà vẫn tốn một lượt chạy.
    """
    import cv2

    if clusters < 1 or strength <= 0:
        return image
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    _, ink = _ink_field(gray, 6)
    # Tâm cụm bốc TỪ CHÍNH CÁC ĐIỂM CÓ MỰC, không bốc đều trên trang. Chỗ này
    # là chỗ đầu tiên viết sai: rắc đều thì trên một tờ hoá đơn -- mực phủ
    # khoảng 3% mặt giấy -- chỉ ba phần trăm số cụm rơi trúng mực, và mô hình
    # chạy hết một lượt để đổi gần như không gì. Bản in ăn mực kém là hỏng
    # CỦA MỰC, nên cụm phải sinh ra ở nơi có mực.
    ys, xs = np.nonzero(ink > 40)
    if len(xs) == 0:
        return image

    holes = np.zeros((height, width), dtype=np.float32)
    for _ in range(int(clusters)):
        seed = rng.randrange(len(xs))
        cx, cy = float(xs[seed]), float(ys[seed])
        for _ in range(max(int(dots), 1)):
            x = int(rng.gauss(cx, spread))
            y = int(rng.gauss(cy, spread))
            if 0 <= x < width and 0 <= y < height:
                holes[y, x] = 1.0
    holes = cv2.GaussianBlur(holes, (0, 0), 0.7)
    holes = np.clip(holes * 2.4, 0, 1)

    # Chỉ ăn vào mực: mặt nạ mực mềm, không ngưỡng cứng, nên mép nét chữ rỗ dần
    # chứ không rỗ hẳn -- mép nét vốn đã nhạt hơn thân nét.
    where = holes * np.clip(ink / 90.0, 0, 1) * float(strength)

    out = bgr.astype(np.float32)
    paper_tone = float(np.percentile(gray, 92))
    out += (paper_tone - out) * where[..., None]
    return _restore(np.clip(out, 0, 255).astype(np.uint8), was_gray)


def hollow(
    image: np.ndarray,
    rim: float = 0.0,
    strength: float = 0.85,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Chữ rỗng ruột: chỉ còn viền, ruột nét bay mất mực.

    Chuyển thể `Hollow`. Ruy băng khô, bút dạ hết mực, máy photocopy chỉnh sai
    làm nổi biên: nét chữ mất phần giữa và chỉ còn đường viền.

    Dựng bằng **phép biến đổi khoảng cách**, không bằng phép co hình thái. Chỗ
    khác nhau không phải chuyện tối ưu: `distanceTransform` trả về, cho từng
    điểm mực, khoảng cách tới điểm giấy gần nhất — tức là điểm ấy nằm sâu bao
    nhiêu trong nét. Ruột là chỗ sâu hơn `rim`, và định nghĩa ấy đúng với mọi
    bề dày nét cùng lúc. Co hình thái thì dùng một nhân cho cả trang, nên nhân
    vừa cho tiêu đề sẽ xoá sạch dòng chữ nhỏ.

    `rim` là bề dày viền còn lại, tính bằng pixel. **`0` nghĩa là tự đo**: lấy
    theo bề dày nét của chính trang này (phân vị 85 của khoảng cách), nên một
    chuỗi khai `hollow` cho ra viền đúng cỡ trên tờ hoá đơn nhiệt cỡ chữ 22 lẫn
    trên tờ A4 cỡ chữ 11. Đây là lý do tham số không còn là số pixel cố định
    như bản đầu: mặc định 2 pixel không làm gì trên chính cỡ chữ mà repo này
    sinh ra, mà một mặc định không làm gì là một mô hình không ai kiểm được.

    Đây là mô hình **ăn dấu thanh mạnh nhất** trong cả thư mục. Dấu sắc và dấu
    huyền là nét mảnh một hai pixel: chúng nông hơn `rim` nên KHÔNG bị rỗng
    ruột — nhưng thân chữ thì rỗng, nên tương quan đậm nhạt giữa dấu và chữ đảo
    ngược lại so với mọi tờ giấy thật. Nhãn thì vẫn khai đủ dấu.
    """
    import cv2

    if strength <= 0:
        return image
    bgr, was_gray = _as_bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    _, ink = _ink_field(gray, 6)

    mask = (ink > 40).astype(np.uint8)
    if not mask.any():
        return image
    depth = cv2.distanceTransform(mask, cv2.DIST_L2, 3)

    edge = float(rim)
    if edge <= 0:
        # Nửa bề dày nét, đo trên chính trang này. Phân vị chứ không phải max:
        # một khung bảng đặc hay một mảng nền tối cho ra khoảng cách hàng chục
        # pixel và kéo lệch mọi thứ.
        edge = max(float(np.percentile(depth[mask > 0], 85)) * 0.55, 0.8)

    core = np.clip((depth - edge) / 0.9, 0, 1)
    where = core * np.clip(ink / 90.0, 0, 1) * float(strength)
    out = bgr.astype(np.float32)
    paper_tone = float(np.percentile(gray, 92))
    out += (paper_tone - out) * where[..., None]
    return _restore(np.clip(out, 0, 255).astype(np.uint8), was_gray)


def dot_matrix(
    image: np.ndarray,
    cell: float = 3.0,
    shape: str = "circle",
    coverage: float = 0.8,
    strength: float = 0.85,
    dead_pins: int = 0,
    ribbon: float = 0.0,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Máy in kim: chữ dựng lại bằng lưới chấm của đầu kim.

    Chuyển thể `DotMatrix`. **Khác `halftone_screen` ở bản chất, không ở tham
    số.** Lưới tram của máy photocopy đổi CỠ chấm theo độ đậm (tram AM), còn
    đầu kim chỉ có một cỡ chấm — cỡ của cái kim — và mỗi ô lưới chỉ có bắn hoặc
    không bắn. Nên chữ máy kim rỗ theo lưới đều tăm tắp, còn chữ photocopy rỗ
    theo mảng đậm nhạt. Hai hoạ tiết ấy khác nhau và mô hình OCR học được cả
    hai, nếu dữ liệu có cả hai.

    `dead_pins` là số **kim gãy**: mỗi kim gãy để lại một vạch trắng ngang chạy
    suốt mọi dòng chữ, đúng một độ cao trong mỗi ký tự. Đây là nhiễu CÓ CẤU
    TRÚC — đều đặn, cùng độ cao, không ngẫu nhiên — nên nó là dữ liệu tốt chứ
    không phải nhiễu vô nghĩa. Trên chứng từ Việt Nam nó rất thường gặp: phiếu
    xuất kho và hoá đơn bán lẻ vẫn in máy kim.

    `ribbon` là độ mòn ruy băng, 0 tới 1: nửa dưới của mỗi chấm nhạt dần vì
    băng mực mòn không đều theo chiều cao đầu in.
    """
    import cv2

    if cell < 1 or strength <= 0:
        return image
    if shape not in SHAPES:
        raise ValueError(f"shape must be one of {SHAPES}; got {shape!r}")
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    paper, ink = _ink_field(gray, int(max(cell, 2)) * 2)

    step = float(cell)
    rows = max(int(height / step), 1)
    cols = max(int(width / step), 1)
    # Lượng mực trung bình mỗi ô lưới. INTER_AREA vì đây đúng là phép lấy trung
    # bình trên ô, chứ không phải lấy mẫu một điểm giữa ô.
    per_cell = cv2.resize(ink, (cols, rows), interpolation=cv2.INTER_AREA)

    fires = (per_cell > (1.0 - float(coverage)) * 90.0).astype(np.float32)
    if dead_pins > 0:
        # Kim xếp thành một cột trên đầu in, in ra thì thành HÀNG trên giấy.
        for _ in range(int(dead_pins)):
            fires[rng.randrange(rows), :] = 0.0
    fired = cv2.resize(fires, (width, height), interpolation=cv2.INTER_NEAREST)

    # Hình cái chấm, dựng một lần cho cả trang bằng toạ độ theo modulo -- rẻ
    # hơn vẽ vài trăm nghìn hình tròn, và ra đúng cùng một thứ.
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    dx = (xx % step) - step * 0.5
    dy = (yy % step) - step * 0.5
    if shape == "circle":
        distance = np.sqrt(dx * dx + dy * dy)
    elif shape == "rect":
        distance = np.maximum(np.abs(dx), np.abs(dy))
    else:
        distance = np.abs(dx) + np.abs(dy)
    radius = step * 0.42
    dot = np.clip((radius - distance) / max(radius * 0.6, 0.5), 0, 1)

    amount = dot * fired
    if ribbon > 0:
        amount *= 1.0 - float(ribbon) * np.clip((dy + step * 0.5) / step, 0, 1)

    # Xoá mực cũ về mặt giấy rồi in lại bằng chấm. Giữ nguyên sắc của mực: một
    # tờ mực xanh in kim vẫn phải ra chấm xanh.
    darkest = np.clip(np.percentile(ink, 99.5), 40.0, 255.0)
    # Xoá CHỈ Ở CHỖ CÓ MỰC, chứ không lấy thẳng `paper` làm nền cả trang. Phép
    # đóng hình thái dựng ra `paper` đã san phẳng vân giấy, nên lấy nguyên nó
    # thì mọi thứ chuỗi phía trước vừa làm cho mặt giấy -- vân, ố, dải sáng
    # tối -- biến mất dưới lớp chấm. Đo được, chứ không phải chuyện thẩm mỹ:
    # trên trang mẫu, độ lệch chuẩn ở một vùng không có chữ tụt từ 2.9 xuống
    # 1.2 khi lấy `paper` thẳng, và giữ nguyên 2.9 với hai dòng này.
    lift = np.clip(ink / 40.0, 0, 1)
    blank = gray.astype(np.float32) * (1.0 - lift) + paper * lift
    dotted = blank - amount * darkest
    ratio = np.divide(dotted, np.maximum(gray.astype(np.float32), 1.0))[..., None]
    printed = np.clip(bgr.astype(np.float32) * ratio, 0, 255)

    out = bgr.astype(np.float32) * (1.0 - strength) + printed * strength
    return _restore(np.clip(out, 0, 255).astype(np.uint8), was_gray)


__all__ = ["SHAPES", "dot_matrix", "hollow", "letterpress"]
