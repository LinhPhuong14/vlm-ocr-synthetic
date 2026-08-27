"""Sọc của trống mực bẩn — chạy dọc theo hướng giấy đi.

Chuyển thể từ `DirtyDrum` của [Augraphy](https://github.com/sparkfish/augraphy),
pha `post`. Mã của họ không vendor: mô hình viết lại ở đây, ghi rõ chuyển thể
từ đâu, đúng lối đã làm với các mô hình của DocCreator.

Mô hình **cái trống mực**: một vết xước hay một chỗ bám mực trên chu vi
trống, in lại vào đúng một vị trí ngang mỗi vòng quay, cho ra sọc liền
suốt chiều dài tờ giấy.

Ba mô hình `bad_photocopy`, `dirty_drum` và `dirty_rollers` ở chung một file
cho tới khi mỗi cái thành một **thuộc tính riêng** của rule-base. Từ lúc ấy,
để chung một file là nói sai về cấu trúc: chúng không còn là ba bước của một
kịch bản "máy photo hỏng" nữa mà là ba bộ phận độc lập của cái máy, bốc riêng
và ghép được với nhau — xem `rulebase/rules/drum.yaml`.
"""

from __future__ import annotations

import random

import numpy as np

from .texture import _as_bgr, _restore, _value_noise


def dirty_drum(
    image: np.ndarray,
    lines: int = 6,
    direction: str = "vertical",
    intensity: float = 0.5,
    line_width: int = 3,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Sọc của trống mực bẩn — chạy DỌC theo hướng giấy đi.

    Chuyển thể `DirtyDrum`. Trống mực có vết xước hoặc bám mực ở một chỗ trên
    chu vi thì mỗi vòng quay nó in lại vết ấy vào đúng một vị trí ngang, cho ra
    **sọc liền suốt chiều dài tờ giấy**. Đó là hình dạng phải giữ: một sọc đứt
    quãng ngẫu nhiên là nhiễu, một sọc liền là cái trống.

    Độ đậm dọc theo sọc thì có thay đổi — mực không bám đều — nên mỗi sọc mang
    một mặt cắt riêng chứ không phải một đường thẳng cùng màu.

    `direction` đổi được sang `horizontal` cho máy nạp giấy quay ngang.
    """
    import cv2

    if lines < 1 or intensity <= 0:
        return image
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]
    if direction not in ("vertical", "horizontal"):
        raise ValueError(f"direction must be 'vertical' or 'horizontal'; got {direction!r}")

    along, across = (height, width) if direction == "vertical" else (width, height)
    field = np.zeros((along, across), dtype=np.float32)
    for _ in range(int(lines)):
        centre = rng.uniform(0, across)
        thickness = max(rng.uniform(0.4, 1.6) * line_width, 0.8)
        # Mặt cắt Gauss ngang sọc: mép sọc phải nhoè, vì mực nhoè.
        offset = np.arange(across, dtype=np.float32) - centre
        profile = np.exp(-((offset / thickness) ** 2))
        # Độ đậm thay đổi chậm dọc theo sọc, và có thể tắt hẳn ở vài đoạn.
        wobble = _value_noise((along, 8), max(along // 24, 2), rng)[:, 0]
        strength = np.clip(wobble * 1.6 - 0.25, 0, 1) * rng.uniform(0.5, 1.0)
        field = np.maximum(field, strength[:, None] * profile[None, :])

    if direction == "horizontal":
        field = field.T
    field = cv2.GaussianBlur(field, (0, 0), 0.8)
    out = bgr.astype(np.float32) * (1.0 - float(intensity) * field)[..., None]
    return _restore(np.clip(out, 0, 255).astype(np.uint8), was_gray)



__all__ = ["dirty_drum"]
