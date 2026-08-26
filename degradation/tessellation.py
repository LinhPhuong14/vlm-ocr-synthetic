"""Hoạ tiết nền chia ô: Voronoi và Delaunay. Chuyển thể từ Augraphy.

`VoronoiTessellation` và `DelaunayTessellation` của pha `paper`. Cả hai sinh
một mặt phẳng chia thành các mảnh, mỗi mảnh một sắc độ hơi khác nhau, rồi phủ
lên trang theo lối NHÂN.

Chúng tả cái gì trên giấy thật, và vì sao đáng có:

* **Voronoi** — mảnh có cạnh chung, hình đa giác lồi bất kỳ. Đây là hình dạng
  của bột giấy tái chế đóng vón, của giấy có vân đá, và của nền bảo an in chìm
  trên tờ hoá đơn đặt in.
* **Delaunay** — tam giác. Đúng là đối ngẫu của Voronoi (cùng một tập điểm
  sinh ra cả hai), nhưng phủ lên trang thì cho hoạ tiết khác hẳn: mảng tam
  giác nhọn đọc ra như nền in trang trí, không như thớ giấy.

Đây là hai mô hình **hiền nhất** trong đợt chuyển thể này: chúng chỉ làm tối
đi vài phần trăm và không đụng tới nét chữ. Giá trị của chúng là dạy mô hình
OCR rằng **nền có cấu trúc không phải là chữ** — một tờ giấy có vân ô rõ mà mô
hình chưa từng thấy sẽ sinh ra hàng loạt hộp giả ở chỗ không có gì.

Vì cả hai chỉ nhân một mặt sáng tối vào trang, chúng cũng là hai mô hình hợp
nhất để thử `by_box`: phủ vân lên đúng vùng bảng mà chừa phần đầu trang, thay
vì phủ đều cả tờ.
"""

from __future__ import annotations

import random

import numpy as np

from .texture import _as_bgr, _restore


def _seeds(shape: tuple[int, int], scale: float, rng: random.Random) -> np.ndarray:
    """Điểm sinh, rải theo lưới có xê dịch chứ không rải hoàn toàn ngẫu nhiên.

    Rải hoàn toàn ngẫu nhiên thì các điểm vón cục: chỗ có ba bốn điểm sát nhau
    cho ra mảnh bé xíu, chỗ trống cho ra mảnh to bằng nửa trang. Thớ giấy không
    thế. Lưới xê dịch giữ cỡ mảnh quanh một giá trị mà vẫn không lộ ra lưới.
    """
    height, width = shape
    step = max(float(scale), 4.0)
    points = []
    for row in range(int(height / step) + 2):
        for col in range(int(width / step) + 2):
            x = (col + rng.uniform(0.1, 0.9)) * step
            y = (row + rng.uniform(0.1, 0.9)) * step
            if 0 <= x < width and 0 <= y < height:
                points.append((x, y))
    return np.asarray(points, dtype=np.float32)


def _apply_field(bgr: np.ndarray, field: np.ndarray, alpha: float, was_gray: bool):
    """Nhân mặt sáng tối vào trang. `field` quanh 1.0, dưới 1 là tối đi."""
    gain = 1.0 - float(alpha) * (1.0 - field)
    out = np.clip(bgr.astype(np.float32) * gain[..., None], 0, 255).astype(np.uint8)
    return _restore(out, was_gray)


def voronoi_tessellation(
    image: np.ndarray,
    scale: float = 34.0,
    alpha: float = 0.16,
    contrast: float = 0.55,
    edges: float = 0.0,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Ô Voronoi: mỗi điểm ảnh mang sắc độ của điểm sinh gần nó nhất.

    Chuyển thể `VoronoiTessellation`. Dựng bằng `cv2.distanceTransformWithLabels`
    chứ không so khoảng cách tới từng điểm sinh: phép biến đổi khoảng cách đã
    trả về sẵn NHÃN của điểm gần nhất, mà đó đúng là định nghĩa của ô Voronoi.
    Một lượt quét ảnh thay cho một vòng lặp trên vài nghìn điểm sinh.

    * `scale`    cỡ mảnh trung bình, tính bằng pixel.
    * `alpha`    mức phủ. Trên 0.3 thì ô lấn át chữ.
    * `contrast` chênh lệch sắc độ giữa các mảnh.
    * `edges`    vẽ thêm đường biên giữa hai mảnh — thớ giấy tái chế có, nền
                 bảo an in chìm thì không.
    """
    import cv2

    if alpha <= 0 or scale < 2:
        return image
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]

    marks = np.full((height, width), 255, np.uint8)
    points = _seeds((height, width), scale, rng)
    marks[points[:, 1].astype(int), points[:, 0].astype(int)] = 0

    distance, labels = cv2.distanceTransformWithLabels(
        marks, cv2.DIST_L2, 3, labelType=cv2.DIST_LABEL_PIXEL)
    tones = np.asarray(
        [1.0] + [1.0 - rng.uniform(0.0, 1.0) * float(contrast) * 0.35
                 for _ in range(int(labels.max()))],
        dtype=np.float32)
    field = tones[np.clip(labels, 0, len(tones) - 1)]

    if edges > 0:
        # Biên là chỗ nhãn đổi: giãn ảnh nhãn rồi so với chính nó. Rẻ hơn dò
        # biên trên ảnh sắc độ, và không bỏ sót hai mảnh tình cờ cùng sắc độ.
        grown = cv2.dilate(labels.astype(np.float32), np.ones((3, 3), np.uint8))
        border = (grown != labels.astype(np.float32)).astype(np.float32)
        field -= cv2.GaussianBlur(border, (0, 0), 0.6) * float(edges)

    return _apply_field(bgr, np.clip(field, 0.0, 1.5), alpha, was_gray)


def delaunay_tessellation(
    image: np.ndarray,
    scale: float = 46.0,
    alpha: float = 0.14,
    contrast: float = 0.55,
    edges: float = 0.0,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Mảng tam giác Delaunay trên cùng tập điểm sinh.

    Chuyển thể `DelaunayTessellation`. `cv2.Subdiv2D` dựng phép chia; các tam
    giác nó trả về gồm cả những tam giác dính vào bộ khung ảo bao ngoài ảnh, và
    những cái ấy có đỉnh nằm rất xa khung hình — lọc bỏ, nếu không `fillConvexPoly`
    sẽ tô một mảng khổng lồ đè lên nửa trang.
    """
    import cv2

    if alpha <= 0 or scale < 2:
        return image
    rng = rng or random.Random(0)
    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]

    subdiv = cv2.Subdiv2D((0, 0, width, height))
    for x, y in _seeds((height, width), scale, rng):
        subdiv.insert((float(x), float(y)))

    field = np.ones((height, width), dtype=np.float32)
    for triangle in subdiv.getTriangleList():
        corners = triangle.reshape(3, 2)
        if (corners[:, 0] < 0).any() or (corners[:, 0] > width).any():
            continue
        if (corners[:, 1] < 0).any() or (corners[:, 1] > height).any():
            continue
        tone = 1.0 - rng.uniform(0.0, 1.0) * float(contrast) * 0.35
        cv2.fillConvexPoly(field, corners.astype(np.int32), tone, cv2.LINE_8)
        if edges > 0:
            cv2.polylines(field, [corners.astype(np.int32)], True,
                          max(tone - float(edges), 0.0), 1, cv2.LINE_AA)

    return _apply_field(bgr, np.clip(field, 0.0, 1.5), alpha, was_gray)


__all__ = ["delaunay_tessellation", "voronoi_tessellation"]
