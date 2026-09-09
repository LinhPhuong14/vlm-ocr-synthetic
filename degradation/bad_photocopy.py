"""Bụi mực của một cái máy photocopy đã hỏng.

Chuyển thể từ `BadPhotoCopy` của [Augraphy](https://github.com/sparkfish/augraphy),
pha `post`. Mã của họ không vendor: mô hình viết lại ở đây, ghi rõ chuyển thể
từ đâu, đúng lối đã làm với các mô hình của DocCreator.

Mô hình **cái hộp mực**: bụi mực bám thành mảng đậm, đèn quét cháy trắng
chỗ khác, và dải xám bị đẩy về hai đầu vì máy không giữ nổi trung gian.

Ba mô hình `bad_photocopy`, `dirty_drum` và `dirty_rollers` ở chung một file
cho tới khi mỗi cái thành một **thuộc tính riêng** của rule-base. Từ lúc ấy,
để chung một file là nói sai về cấu trúc: chúng không còn là ba bước của một
kịch bản "máy photo hỏng" nữa mà là ba bộ phận độc lập của cái máy, bốc riêng
và ghép được với nhau — xem `rulebase/rules/toner.yaml`.
"""

from __future__ import annotations

import random

import cv2
import numpy as np

from .texture import _as_bgr, _restore, _value_noise


def _fbm(shape: tuple[int, int], cell: int, octaves: int, rng: random.Random) -> np.ndarray:
    """Nhiễu nhiều tầng: tầng thô cho mảng lớn, tầng mịn cho hạt.

    Một tầng cho ra mặt phẳng gợn đều, nhìn là biết máy sinh. Mực bẩn thật có
    mảng to lẫn hạt nhỏ cùng lúc, nên cộng vài tầng với biên độ giảm dần.
    """
    field = np.zeros(shape, dtype=np.float32)
    amplitude, total = 1.0, 0.0
    for octave in range(max(octaves, 1)):
        step = max(cell >> octave, 2)
        field += _value_noise(shape, step, rng) * amplitude
        total += amplitude
        amplitude *= 0.5
    return field / max(total, 1e-6)


def bad_photocopy(
    image: np.ndarray,
    blotch: float = 0.45,
    wash: float = 0.25,
    contrast: float = 0.35,
    cell: int = 48,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Máy photocopy hỏng: mảng bụi mực đậm, mảng cháy trắng, mực bệt.

    Chuyển thể `BadPhotoCopy`. Ba thứ cùng lúc và phải cùng lúc mới ra dáng bản
    photo hỏng:

    * `blotch` — bụi mực bám thành **mảng đậm**, chỗ đậm nhất gần như đen. Lấy
      từ đuôi TRÊN của mặt nhiễu, nên mảng thưa và có hình dạng riêng chứ không
      phải hạt rải đều.
    * `wash`   — mảng **cháy trắng**, chỗ đèn quét quá sáng hoặc trống mực hết
      mực. Lấy từ đuôi DƯỚI của cùng mặt nhiễu, nên đậm và cháy không bao giờ
      chồng lên nhau — đúng như trên tờ thật.
    * `contrast` — máy photo không giữ được xám: nó đẩy về hai đầu. Đây là thứ
      ăn mất **dấu thanh** trước tiên, vì dấu là nét mảnh nên xám hơn thân chữ.

    Ba tham số đều 0 thì trang đi qua nguyên vẹn.
    """
    import cv2

    if blotch <= 0 and wash <= 0 and contrast <= 0:
        return image
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]
    out = bgr.astype(np.float32)

    if contrast > 0:
        # Kéo giãn quanh mức xám giữa: sáng lên sáng nữa, tối xuống tối nữa.
        gain = 1.0 + 2.2 * float(contrast)
        out = np.clip((out - 128.0) * gain + 128.0, 0, 255)

    if blotch > 0 or wash > 0:
        field = _fbm((height, width), cell, 3, rng)
        field = cv2.GaussianBlur(field, (0, 0), 2.0)
        low, high = np.percentile(field, [30, 70])

    if blotch > 0:
        # Chuẩn hoá theo phân vị chứ không theo min/max: min/max bị một điểm
        # cực trị kéo đi, nên cùng một `blotch` sẽ ra liều khác nhau mỗi hạt
        # giống, và không ai chỉnh được một con số như thế.
        dark = np.clip((field - high) / max(1.0 - high, 1e-3), 0, 1) ** 1.6
        out *= (1.0 - float(blotch) * dark)[..., None]

    if wash > 0:
        bright = np.clip((low - field) / max(low, 1e-3), 0, 1) ** 1.6
        out += (255.0 - out) * (float(wash) * bright)[..., None]

    return _restore(np.clip(out, 0, 255).astype(np.uint8), was_gray)



def monochrome(image: np.ndarray, warmth: float = 0.0) -> np.ndarray:
    """Bỏ hết màu khỏi trang: máy photo chỉ có MỘT hộp mực.

    Cái máy không có màu nào để in ra, nên bản photo của một tờ hoá đơn mực
    xanh, một con dấu đỏ và một dấu "BẢN SAO" xanh lam đều ra cùng một thang
    xám. Không có bước này thì chuỗi `photocopy*` cho ra tờ giấy **có màu mà
    lại mang lưới tram** — hai thứ không bao giờ đi cùng nhau trên giấy thật.

    Trọng số luminance (BT.601, đúng cái `cv2.COLOR_BGR2GRAY` dùng) chứ không
    phải trung bình ba kênh: mắt người và cảm biến CCD của máy quét đều nhạy
    với lục hơn lam gấp nhiều lần, nên trung bình cộng làm chữ đỏ ra quá nhạt
    và chữ lam ra quá đậm so với bản photo thật.

    **Đặt CUỐI chuỗi, không phải đầu.** `paper_texture` và `paper_overlay`
    dán một tấm ảnh giấy thật lên trang, và ảnh ấy có màu; `pattern_overlay`
    đóng con dấu cũng có màu. Chuyển xám trước chúng thì màu quay lại ngay sau
    đó. Cuối chuỗi là chỗ duy nhất bảo đảm được điều đầu đề nói.

    `warmth` (0..1) pha lại một chút ám vàng của giấy đã ngả, cho tờ photo cũ.
    0 là xám thuần, và đó là mặc định — **cũng là giá trị duy nhất giữ được
    lời hứa "cả ảnh là greyscale"**. Đo được: ở `warmth: 0.25` kênh chroma còn
    khác 0, và JPEG 4:2:0 lúc ghi ảnh dội quanh các chấm halftone thành viền
    bão hoà 255 trên 0,5-0,7% pixel — mắt thường không thấy, `cv2.cvtColor(...,
    BGR2HSV)[...,1].max()` thấy ngay. Muốn giấy ngả vàng thì làm ở
    `paper_texture`, nơi nó không phải đi qua chroma của một ảnh nén.
    """
    out, was_gray = _as_bgr(image)
    grey = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    out = cv2.cvtColor(grey, cv2.COLOR_GRAY2BGR).astype(np.float32)
    warmth = float(np.clip(warmth, 0.0, 1.0))
    if warmth:
        # BGR: hạ lam, giữ lục, nâng đỏ -- ám vàng, không phải ám nâu.
        tint = np.array([1.0 - 0.16 * warmth, 1.0, 1.0 + 0.06 * warmth],
                        dtype=np.float32)
        out *= tint
    return _restore(np.clip(out, 0, 255).astype(np.uint8), was_gray)


__all__ = ["bad_photocopy", "monochrome"]
