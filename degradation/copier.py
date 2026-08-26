"""Ba vết mà cái máy để lại, chuyển thể từ Augraphy.

[Augraphy](https://github.com/sparkfish/augraphy) là thư viện làm cũ ảnh tài
liệu, chia chuỗi thành ba pha `ink -> paper -> post` — cùng một ý với việc
`paper_texture` chạy đầu chuỗi ở đây. Ba mô hình dưới đây chuyển thể từ pha
`post` của họ: `BadPhotoCopy`, `DirtyDrum`, `DirtyRollers`.

Không vendor mã của họ. Lý do giống hệt lý do không vendor DocCreator: mã ấy
kéo theo phụ thuộc, và lối viết ở đây là mỗi mô hình một hàm đọc được, ghi rõ
nó chuyển thể từ đâu, để đối chiếu lại được với bản gốc.

Cả ba đều là **vết của bộ truyền giấy**, không phải hỏng của tờ giấy — cùng họ
với `capture.py`. Khác `scan_banding` ở chỗ quan trọng: `scan_banding` tuần
hoàn đều (trục lăn quay đều), ba cái này thì KHÔNG — trống mực bẩn chỗ nào thì
bẩn chỗ ấy, và đó là dấu hiệu để phân biệt hai loại hỏng trên ảnh thật.
"""

from __future__ import annotations

import random

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


__all__ = ["bad_photocopy", "dirty_drum", "dirty_rollers"]
