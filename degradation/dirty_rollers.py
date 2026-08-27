"""Vệt trục lăn: dải sáng tối không đều, có gờ.

Chuyển thể từ `DirtyRollers` của [Augraphy](https://github.com/sparkfish/augraphy),
pha `post`. Mã của họ không vendor: mô hình viết lại ở đây, ghi rõ chuyển thể
từ đâu, đúng lối đã làm với các mô hình của DocCreator.

Mô hình **bộ trục lăn kéo giấy**: dải đậm nhạt vuông góc với hướng giấy
đi. Khác `scan_banding` ở hai chỗ đo được — không tuần hoàn đều, và mặt
cắt có gờ chứ không mượt như sin — và cả hai đều là cách phân biệt vệt
trục lăn với vân quét trên một bản scan thật.

Ba mô hình `bad_photocopy`, `dirty_drum` và `dirty_rollers` ở chung một file
cho tới khi mỗi cái thành một **thuộc tính riêng** của rule-base. Từ lúc ấy,
để chung một file là nói sai về cấu trúc: chúng không còn là ba bước của một
kịch bản "máy photo hỏng" nữa mà là ba bộ phận độc lập của cái máy, bốc riêng
và ghép được với nhau — xem `rulebase/rules/rollers.yaml`.
"""

from __future__ import annotations

import random

import numpy as np

from .texture import _as_bgr, _restore, _value_noise


def dirty_rollers(
    image: np.ndarray,
    intensity: float = 0.35,
    period: float = 90.0,
    direction: str = "horizontal",
    rng: random.Random | None = None,
) -> np.ndarray:
    """Vệt trục lăn: dải sáng tối KHÔNG đều, có gờ.

    Chuyển thể `DirtyRollers`. Trục lăn bẩn ép lên tờ giấy để lại dải đậm nhạt
    vuông góc với hướng giấy đi. Khác `scan_banding` ở hai chỗ đo được, và cả
    hai đều đáng giữ vì chúng là cách phân biệt hai loại hỏng:

    1. **Không tuần hoàn đều.** `scan_banding` là tổng hai sóng sin. Cái này là
       nhiễu trơn, nên khoảng cách giữa hai dải không đoán trước được.
    2. **Có gờ.** Mặt cắt đi qua một hàm gờ (`1 - |2u - 1|`) nên chỗ chuyển
       sáng-tối gấp khúc chứ không mượt như sin — dấu vết của mép trục lăn.
    """
    import cv2

    if intensity <= 0:
        return image
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]
    if direction not in ("horizontal", "vertical"):
        raise ValueError(f"direction must be 'horizontal' or 'vertical'; got {direction!r}")

    length = height if direction == "horizontal" else width
    cell = max(int(period), 2)
    profile = _value_noise((length, 8), cell, rng)[:, 0]
    profile = cv2.GaussianBlur(profile[:, None], (0, 0), 1.5)[:, 0]
    ridge = 1.0 - np.abs(2.0 * profile - 1.0)          # gờ, không phải sin
    gain = 1.0 + float(intensity) * (ridge - ridge.mean())

    gain = gain[:, None] if direction == "horizontal" else gain[None, :]
    out = bgr.astype(np.float32) * gain[..., None]
    return _restore(np.clip(out, 0, 255).astype(np.uint8), was_gray)



__all__ = ["dirty_rollers"]
