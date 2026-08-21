"""Hoạ tiết sinh ra lúc CHỤP LẠI tờ giấy, không phải lúc in nó.

Ba mẫu ở đây khác mọi thứ còn lại trong `degradation/` ở chỗ chúng không làm
hỏng tờ giấy: tờ giấy vẫn nguyên, chỉ có bản sao của nó mang thêm một hoạ tiết
tuần hoàn mà thiết bị áp lên. Máy photocopy áp lưới tram, máy quét phẳng và máy
fax áp dải sáng tối theo trục lăn, và JPEG áp lưới 8×8 của phép biến đổi cosin.

Vì sao xếp vào `augmentation` chứ không vào `ornament`: `ornament` là mực CỐ Ý
có mặt trên giấy — ai đó in nó, đóng nó. Ba thứ dưới đây không ai muốn có; đó
là dấu vết của đường đi từ tờ giấy tới tệp ảnh. Thứ tự bốc cũng nói điều đó:
`ornament` trước, `augmentation` sau.

Với dữ liệu hoá đơn Việt Nam thì đây không phải trường hợp hiếm. Một tờ hoá đơn
đi qua máy photocopy ở phòng kế toán, rồi được chụp bằng điện thoại, rồi gửi
qua ứng dụng nhắn tin nén lại lần nữa — ảnh tới tay người đọc đã mang cả ba.
"""

from __future__ import annotations

import math
import random

import numpy as np

from .texture import _as_bgr, _restore


def halftone_screen(
    image: np.ndarray,
    cell: float = 4.0,
    angle: float = 45.0,
    strength: float = 0.65,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Lưới tram của máy photocopy: vùng đậm thành chấm to, vùng nhạt thành chấm nhỏ.

    Dựng bằng một mặt sàng tuần hoàn nghiêng `angle` độ rồi so ngưỡng với độ
    sáng từng điểm — đúng cách máy in tram thật quyết định chấm nào ăn mực.
    Nghiêng 45 độ vì đó là góc tram tiêu chuẩn cho bản đen trắng: mắt người ít
    nhận ra hoạ tiết nhất ở góc ấy, nên máy nào cũng chọn nó.

    `strength` là mức pha trở lại ảnh gốc. 1.0 cho ảnh hai mức đúng nghĩa; các
    máy photocopy đời mới giữ lại chút xám, nên mặc định để dưới 1.
    """
    import cv2

    if strength <= 0 or cell <= 0:
        return image
    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]

    # Mặt sàng: tích hai sóng sin lệch trục cho ra cụm chấm tròn, không phải
    # lưới ô vuông. Xoay trục TRƯỚC khi lấy sin, nên hoạ tiết nghiêng thật chứ
    # không phải ảnh vuông rồi xoay đi (xoay ảnh sẽ làm nhoè mép chấm).
    radians = math.radians(angle)
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    u = (xx * math.cos(radians) + yy * math.sin(radians)) / cell
    v = (-xx * math.sin(radians) + yy * math.cos(radians)) / cell
    screen = (np.sin(u * math.tau) * np.sin(v * math.tau) + 1.0) * 0.5 * 255.0

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    dotted = np.where(gray > screen, 255.0, 0.0)
    mixed = gray * (1.0 - strength) + dotted * strength

    # Giữ nguyên sắc: chỉ đổi độ sáng, nên tờ giấy ngả vàng vẫn ngả vàng.
    ratio = np.divide(mixed, np.maximum(gray, 1.0))[..., None]
    out = np.clip(bgr.astype(np.float32) * ratio, 0, 255).astype(np.uint8)
    return _restore(out, was_gray)


def scan_banding(
    image: np.ndarray,
    period: float = 38.0,
    amplitude: float = 0.055,
    tilt: float = 0.0,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Dải sáng tối chạy ngang, do trục lăn của máy quét hoặc máy fax.

    Một chu kỳ chính cộng một chu kỳ dài hơn nhiều: trục lăn quay đều cho vân
    mau, còn đèn quét rọi không đều cho vân thưa. Chỉ một chu kỳ thì ra hoạ tiết
    quá đều, nhìn là biết máy sinh.

    `tilt` nghiêng dải đi vài độ, cho trường hợp tờ giấy đặt lệch trên mặt kính.
    """
    if amplitude <= 0 or period <= 1:
        return image
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]

    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    axis = yy + xx * math.tan(math.radians(tilt))
    phase = rng.uniform(0, math.tau)
    fine = np.sin(axis / period * math.tau + phase)
    coarse = np.sin(axis / (period * rng.uniform(7.0, 13.0)) * math.tau + phase * 0.5)
    gain = 1.0 + amplitude * (0.72 * fine + 0.28 * coarse)

    out = np.clip(bgr.astype(np.float32) * gain[..., None], 0, 255).astype(np.uint8)
    return _restore(out, was_gray)


def jpeg_blocks(
    image: np.ndarray,
    quality: int = 28,
    passes: int = 2,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Lưới 8×8 của JPEG, sau vài lần nén lại.

    Một tờ hoá đơn chụp bằng điện thoại rồi chuyển tiếp qua ứng dụng nhắn tin
    bị nén lại mỗi chặng, và sai số dồn lên: chữ mọc quầng, biên ô bảng rung,
    nền phẳng vỡ thành ô vuông. `passes` là số chặng ấy.

    Nén lại nhiều lần KHÔNG giống nén một lần ở chất lượng thấp hơn — mỗi lần
    lượng tử hoá trên kết quả đã lượng tử hoá của lần trước, nên hoạ tiết bám
    vào lưới 8×8 rõ dần thay vì chỉ mờ đi.
    """
    import cv2

    if passes < 1:
        return image
    out = image
    for index in range(passes):
        # Chặng sau nén mạnh hơn chặng trước một chút, như đường đi thật.
        step = max(int(quality) - index * 4, 5)
        ok, buffer = cv2.imencode(".jpg", out, [int(cv2.IMWRITE_JPEG_QUALITY), step])
        if not ok:
            return out
        decoded = cv2.imdecode(buffer, cv2.IMREAD_UNCHANGED)
        if decoded is None:
            return out
        out = decoded
    return out


__all__ = ["halftone_screen", "jpeg_blocks", "scan_banding"]
