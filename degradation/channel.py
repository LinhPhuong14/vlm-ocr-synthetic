"""Kênh màu lệch nhau, và dòng ảnh trượt đi. Chuyển thể từ Augraphy.

`ColorShift` và `GlitchEffect`. Cả hai đều tả cùng một loại hỏng — **các phần
của ảnh không còn nằm đúng chỗ so với nhau** — nhưng ở hai tầng khác nhau:
`color_shift` làm ba kênh màu lệch nhau tại chỗ, `glitch_effect` làm cả một dải
dòng ảnh trượt ngang.

Vì sao đáng có: mười sáu mô hình trước đó trong thư mục này **đều chỉ đổi độ
sáng**. Không cái nào tạo ra viền màu. Một mô hình OCR học trên bộ dữ liệu như
thế sẽ gặp viền màu lần đầu trên ảnh thật — mà viền màu thì có ở khắp nơi: bản
in offset lệch bản, ống kính điện thoại quang sai ở rìa ảnh, ảnh chụp lại màn
hình mang viền subpixel RGB.

⚠️ **`glitch_effect` là mô hình DUY NHẤT trong cả thư mục làm pixel đổi chỗ.**
Xem cảnh báo trong docstring của nó trước khi đưa vào một chuỗi sinh dữ liệu.
"""

from __future__ import annotations

import random

import numpy as np

from .texture import _as_bgr, _restore


def _translate(plane: np.ndarray, dx: float, dy: float) -> np.ndarray:
    """Dịch một kênh, nhân bản mép để không sinh viền đen ở rìa ảnh."""
    import cv2

    matrix = np.float32([[1, 0, dx], [0, 1, dy]])
    return cv2.warpAffine(
        plane, matrix, (plane.shape[1], plane.shape[0]),
        flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


def color_shift(
    image: np.ndarray,
    shift: float = 1.6,
    radial: float = 0.0,
    blur: float = 0.0,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Ba kênh màu lệch nhau: chữ đen viền xanh một bên, đỏ bên kia.

    Chuyển thể `ColorShift`. Hai cơ chế, chọn bằng `radial`:

    * `radial: 0` — **lệch đều toàn ảnh**. Đây là lệch bản in: máy offset in
      từng màu một bản, bản lệch nhau vài chục micron thì mọi chỗ trên tờ lệch
      như nhau. Cũng là hình dạng của viền subpixel khi chụp lại màn hình.
    * `radial > 0` — **lệch tăng dần theo bán kính**, giữa ảnh đúng chồng khít
      còn bốn góc lệch nhiều nhất. Đây là quang sai màu của ống kính, và nó
      phụ thuộc bán kính chứ không phải hằng số — chỗ khác nhau giữa hai cơ chế
      nằm đúng ở đấy.

    `shift` tính bằng pixel. Trên 3 pixel ở cỡ chữ hoá đơn thì nét chữ tách hẳn
    thành ba nét màu, đọc ra như lỗi hiển thị chứ không như bản in lệch.

    Ảnh xám đi qua nguyên vẹn: không có ba kênh thì không có gì để làm lệch, và
    trả về ảnh y nguyên trung thực hơn là bịa ra màu.
    """
    import cv2

    if shift <= 0 or image.ndim == 2:
        return image
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    if was_gray:
        return image
    height, width = bgr.shape[:2]

    # Hai kênh ngoài lệch ngược chiều nhau quanh kênh giữa; đó là cách bản in
    # ba màu lệch thật, và cũng là cách viền màu ra được cả hai phía nét chữ.
    angle = rng.uniform(0, 6.283)
    dx, dy = np.cos(angle) * shift, np.sin(angle) * shift
    planes = list(cv2.split(bgr.astype(np.float32)))

    if radial <= 0:
        planes[0] = _translate(planes[0], dx, dy)
        planes[2] = _translate(planes[2], -dx, -dy)
    else:
        # Phóng to/thu nhỏ hai kênh ngoài quanh tâm ảnh: một phép co giãn
        # quanh tâm CHÍNH LÀ độ lệch tỉ lệ với bán kính, không cần dựng lưới
        # ánh xạ riêng.
        centre = (width * 0.5, height * 0.5)
        amount = shift * float(radial) / max(width, height) * 2.0
        for index, sign in ((0, 1.0), (2, -1.0)):
            matrix = cv2.getRotationMatrix2D(centre, 0.0, 1.0 + sign * amount)
            planes[index] = cv2.warpAffine(
                planes[index], matrix, (width, height),
                flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

    if blur > 0:
        # Ống kính không lấy nét được cả ba bước sóng cùng lúc: kênh xanh lam
        # thường mềm nhất. Chi tiết nhỏ, nhưng nó là chỗ phân biệt viền màu của
        # ống kính với viền màu dựng bằng phép dịch.
        planes[0] = cv2.GaussianBlur(planes[0], (0, 0), float(blur))

    out = cv2.merge(planes)
    return _restore(np.clip(out, 0, 255).astype(np.uint8), False)


def glitch_effect(
    image: np.ndarray,
    bands: int = 6,
    max_shift: float = 0.004,
    direction: str = "horizontal",
    separation: float = 0.5,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Dải dòng ảnh trượt ngang: ảnh xé, truyền lỗi, chụp lại màn hình đang quét.

    Chuyển thể `GlitchEffect`. Một dải dòng ảnh bị dịch ngang vài pixel so với
    phần còn lại, và ở mép dải thường có tách kênh màu vì bộ giải mã trượt trên
    dữ liệu màu trước dữ liệu sáng.

    ⚠️ **Mô hình này làm pixel ĐỔI CHỖ, và đó là mô hình duy nhất ở đây làm thế.**
    Chữ nằm trong một dải bị dịch sẽ không còn nằm trong hộp nhãn của nó nữa,
    mà nhãn thì không biết điều đó. Ba hệ quả, phải cân nhắc trước khi dùng:

    1. `max_shift` mặc định để rất nhỏ — **0.004 bề rộng trang**, cỡ 6 pixel
       trên trang 1500 pixel, tức là dưới nửa bề rộng một ký tự. Hộp nhãn vẫn
       phủ gần hết nét chữ ở mức ấy.
    2. Đẩy `max_shift` lên cho dễ nhìn là đang **đánh đổi bằng nhãn**, không
       phải bằng thẩm mỹ. Một chuỗi đặt 0.02 là một chuỗi cố ý sinh ra nhãn
       lệch, và nên có lý do viết kèm.
    3. Cách sửa đúng — mô hình hình học trả về phép biến hình để `apply_recipe`
       kéo hộp nhãn theo — nằm ở mục C của `docs/lam-cu-de-xuat.md` và chưa
       làm. Cho tới lúc ấy, đây là mô hình phải dùng dè.

    `separation` là mức tách kênh màu ở dải bị dịch, tính theo `max_shift`.
    """
    import cv2

    if bands < 1 or max_shift <= 0:
        return image
    if direction not in ("horizontal", "vertical"):
        raise ValueError(f"direction must be 'horizontal' or 'vertical'; got {direction!r}")
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]

    span = height if direction == "horizontal" else width
    reach = max(float(max_shift) * (width if direction == "horizontal" else height), 1.0)
    out = bgr.copy()

    for _ in range(int(bands)):
        thick = max(int(rng.uniform(0.004, 0.03) * span), 2)
        start = rng.randrange(max(span - thick, 1))
        stop = start + thick
        offset = rng.uniform(-reach, reach)
        if abs(offset) < 0.5:
            continue

        strip = out[start:stop] if direction == "horizontal" else out[:, start:stop]
        dx, dy = (offset, 0.0) if direction == "horizontal" else (0.0, offset)
        moved = _translate(strip.astype(np.float32), dx, dy)

        if separation > 0:
            # Kênh đỏ trượt thêm một chút: bộ giải mã mất đồng bộ giữa hai mặt
            # phẳng màu, nên mép dải bao giờ cũng ám một màu.
            planes = list(cv2.split(moved))
            planes[2] = _translate(planes[2], dx * float(separation), dy * float(separation))
            moved = cv2.merge(planes)

        moved = np.clip(moved, 0, 255).astype(out.dtype)
        if direction == "horizontal":
            out[start:stop] = moved
        else:
            out[:, start:stop] = moved

    return _restore(out, was_gray)


__all__ = ["color_shift", "glitch_effect"]
