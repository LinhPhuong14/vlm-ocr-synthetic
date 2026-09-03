"""Page geometry: curl, fold, bulge -- deforms the SHEET, not just its pixels.

Every model here follows the contract `generators/synthdog/elements/warp.py`'s
``CurlWarp`` already used for thermal receipts: an analytic, invertible
displacement, applied to the image with `cv2.remap` (needs the INVERSE map,
dst -> src) and to the page's label quads with the matching FORWARD map (src
-> dst) -- one function pair, so a label quad lands on the exact pixels its
text was warped to. `degradation.regions.by_box` cannot do this: it only
chooses WHERE another model acts, it never moves a quad's own corners.

That is also why these do not live in `degradation.DEGRADATIONS`. Every entry
there is required to return an image of the SAME shape -- `generators/html/
render.py` and `generators/genalog/render.py` both assert this immediately
after `apply_recipe`, because the boxes computed before the chain runs are
trusted to still describe the page after it. A warp moves those boxes on
purpose, so it runs as its own step, after the ageing chain and its shape
check, over every one of a page's box collections at once -- see
`warp_regions` below and its call in `generators/html/render.py`.

Ported and generalised:

  `page_curl`     `generators/synthdog/elements/warp.py::CurlWarp`
                  (SynthDoG-VN, MIT), opened up from thermal receipts to any
                  page and sampled from a seeded `random.Random` instead of
                  the global numpy generator, so a page's warp is
                  reproducible from `recipe.seed` like everything else here.

  `fold_crease`,  new. The paper shapes SyntheticDoc's `fold_by_pull` and
  `corner_bulge`  `fall_on_ball` / `fall_on_roller` scenarios reach by
                  physically simulating a sheet in ARCSim and rendering it in
                  Blender (github.com/tanguymagne/SyntheticDoc). Neither tool
                  fits this repository -- ARCSim's licence is non-commercial
                  only, and Blender is a GPU path tracer with no Python
                  package, not a `pip install`. What *is* portable is the
                  shape a fold or a lifted corner leaves on a flat photo, so
                  that is what these reproduce directly: a 1D pinch along one
                  axis for a fold, a radial pinch around a corner for a
                  lift -- both inverted through a lookup table instead of a
                  physics solve.
"""

from __future__ import annotations

import math
import random
from typing import Any, Callable

import cv2
import numpy as np

# (N, 4, 2) float32, in image pixel coordinates -- the corners of every
# label quad on the page, the same shape `generators/synthdog/elements/
# warp.py::CurlWarp.apply` already takes.
Quads = np.ndarray

CORNERS = ("top_left", "top_right", "bottom_left", "bottom_right")


def _sample_range(rng: random.Random, spec: Any) -> float:
    """A fixed number is used as-is; a `(low, high)` pair is drawn from."""
    if isinstance(spec, (tuple, list)):
        low, high = spec
        return rng.uniform(low, high)
    return float(spec)


def page_curl(
    image: np.ndarray,
    quads: Quads,
    rng: random.Random,
    *,
    shift: Any = (0.0, 0.03),
    squeeze: Any = (0.0, 0.08),
    wave: Any = (0.0, 0.010),
    periods_y: Any = (0.4, 2.0),
    periods_x: Any = (0.3, 0.8),
) -> tuple[np.ndarray, Quads]:
    """Cong giấy phi tuyến, hai lượt khả nghịch -- xem docstring gốc ở
    `generators/synthdog/elements/warp.py::CurlWarp` cho công thức đầy đủ.
    Đây là đúng phép toán ấy, mở rộng cho mọi trang thay vì riêng hoá đơn
    nhiệt, và bốc số từ `rng` thay vì `np.random` toàn cục.

        lượt 1 (theo hàng y): x' = a(y) * (x - cx) + cx + b(y)
        lượt 2 (theo cột x'): y' = y + c(x')

    Mỗi tham số là một số cố định hoặc một khoảng `(low, high)` để bốc.
    """
    quads = np.asarray(quads, dtype=np.float32).reshape(-1, 4, 2)
    height, width = image.shape[:2]

    shift_v = _sample_range(rng, shift)
    squeeze_v = _sample_range(rng, squeeze)
    wave_v = _sample_range(rng, wave)
    periods_y_v = _sample_range(rng, periods_y)
    periods_x_v = _sample_range(rng, periods_x)
    phase_y = rng.uniform(0, 2 * math.pi)
    phase_x = rng.uniform(0, 2 * math.pi)

    pad = int(math.ceil(max(shift_v * width, wave_v * height, squeeze_v * width) + 2))
    padded = cv2.copyMakeBorder(image, pad, pad, pad, pad, cv2.BORDER_REPLICATE)
    quads = quads + pad
    ph, pw = padded.shape[:2]
    cx = pw / 2.0

    def a_of(y):  # hệ số bóp ngang theo hàng
        t = 2 * np.pi * periods_y_v * y / max(ph, 1) + phase_y
        return 1.0 - squeeze_v * (1.0 - np.cos(t)) / 2.0

    def b_of(y):  # lệch ngang theo hàng
        t = 2 * np.pi * periods_y_v * y / max(ph, 1) + phase_y
        return shift_v * pw * np.sin(t)

    def c_of(x):  # lệch dọc theo cột
        t = 2 * np.pi * periods_x_v * x / max(pw, 1) + phase_x
        return wave_v * ph * np.sin(t)

    # --- ảnh: cần ánh xạ ngược (dst -> src) cho cv2.remap ---
    xx, yy = np.meshgrid(np.arange(pw, dtype=np.float32), np.arange(ph, dtype=np.float32))
    y1 = yy - c_of(xx)
    map_x = (xx - cx - b_of(y1)) / a_of(y1) + cx
    map_y = y1
    warped = cv2.remap(
        padded, map_x.astype(np.float32), map_y.astype(np.float32),
        interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE,
    )

    # --- toạ độ: dùng ánh xạ xuôi (src -> dst) ---
    if quads.size:
        xs, ys = quads[..., 0], quads[..., 1]
        nx = a_of(ys) * (xs - cx) + cx + b_of(ys)
        ny = ys + c_of(nx)
        quads = np.stack([nx, ny], axis=-1).astype(np.float32)

    return warped, quads


def fold_crease(
    image: np.ndarray,
    quads: Quads,
    rng: random.Random,
    *,
    axis: str = "x",
    position: Any = (0.3, 0.7),
    depth: Any = (0.01, 0.03),
    width: Any = (0.05, 0.12),
    shadow: Any = (0.15, 0.35),
) -> tuple[np.ndarray, Quads]:
    """Một nếp gấp cứng chạy hết chiều `axis` của trang, cộng bóng đổ dọc nếp.

    Biến dạng chỉ theo MỘT trục (`axis`), nên bài toán rút về một hàm số học
    theo một biến -- nội suy nghịch qua bảng tra thay vì giải 2D. Điểm gần nếp
    bị kéo VỀ PHÍA nếp từ cả hai bên (dáng giấy bị bóp lại ở chỗ gấp); độ tối
    theo cùng một hình chuông quanh nếp, vì chỗ lõm nhận ít sáng hơn mặt giấy
    quanh nó -- cùng lý lẽ với `degradation.shadow_binding`, chỉ khác nguồn.

    `position` là vị trí nếp, theo tỉ lệ chiều `axis`. `depth`/`width` là độ
    sâu và độ rộng vết bóp, cũng theo tỉ lệ đó. `shadow` trong [0, 1] là độ
    tối tại nếp, 0 là không có bóng. Cả bốn nhận số cố định hoặc `(low, high)`.
    """
    quads = np.asarray(quads, dtype=np.float32).reshape(-1, 4, 2)
    if axis not in ("x", "y"):
        raise ValueError(f"axis must be 'x' or 'y', got {axis!r}")

    height, width_px = image.shape[:2]
    length = width_px if axis == "x" else height

    position_v = _sample_range(rng, position) * length
    width_v = max(_sample_range(rng, width) * length, 1.0)
    depth_v = _sample_range(rng, depth) * length
    # Giữ map thuận đơn điệu: nếu độ sâu vượt quá độ rộng, hai điểm nguồn có
    # thể đổ vào cùng một pixel đích. Chặn theo tỉ lệ trước, rồi khoá cứng
    # bằng `np.maximum.accumulate` bên dưới -- không tin riêng phép chặn này.
    depth_v = min(depth_v, 0.5 * width_v)
    shadow_v = _sample_range(rng, shadow)

    coord = np.arange(length, dtype=np.float64)
    offset = coord - position_v
    forward = coord - depth_v * np.exp(-((offset / width_v) ** 2)) * np.sign(offset)
    forward = np.maximum.accumulate(forward)  # lưới an toàn, xem chú thích trên
    gain = (1.0 - shadow_v * np.exp(-((offset / width_v) ** 2))).astype(np.float32)

    src_coord = np.interp(coord, forward, coord).astype(np.float32)

    if axis == "x":
        map_x = np.tile(src_coord[None, :], (height, 1))
        map_y = np.tile(np.arange(height, dtype=np.float32)[:, None], (1, width_px))
        gain_map = np.tile(gain[None, :], (height, 1))
    else:
        map_y = np.tile(src_coord[:, None], (1, width_px))
        map_x = np.tile(np.arange(width_px, dtype=np.float32)[None, :], (height, 1))
        gain_map = np.tile(gain[:, None], (1, width_px))

    warped = cv2.remap(image, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REPLICATE)
    if warped.ndim == 3:
        gain_map = gain_map[:, :, None]
    warped = np.clip(warped.astype(np.float32) * gain_map, 0, 255).astype(np.uint8)

    if quads.size:
        axis_idx = 0 if axis == "x" else 1
        quads = quads.copy()
        quads[..., axis_idx] = np.interp(
            quads[..., axis_idx], coord, forward).astype(np.float32)

    return warped, quads


def corner_bulge(
    image: np.ndarray,
    quads: Quads,
    rng: random.Random,
    *,
    corner: str | None = None,
    radius: Any = (0.25, 0.45),
    depth: Any = (0.03, 0.07),
) -> tuple[np.ndarray, Quads]:
    """Giấy nhấc khỏi mặt phẳng gần một góc trang -- bóp bán kính về tâm góc.

    Một xấp xỉ 2D phẳng của dáng giấy `SyntheticDoc` mô phỏng 3D bằng
    `fall_on_ball`/`fall_on_roller`: không phối cảnh, chỉ nén nội dung gần
    góc vào một vùng nhỏ hơn, theo bán kính -- khả nghịch cùng cách
    `fold_crease` khả nghịch, một hàm số một biến (bán kính) qua bảng tra.

    `corner` là một trong `CORNERS`, hoặc `None` để bốc đều. `radius` là tầm
    với của vết bóp, theo tỉ lệ `min(height, width)`; `depth` là độ sâu, cùng
    đơn vị. Cả hai nhận số cố định hoặc `(low, high)`.
    """
    quads = np.asarray(quads, dtype=np.float32).reshape(-1, 4, 2)
    height, width_px = image.shape[:2]
    corner = corner or rng.choice(CORNERS)
    if corner not in CORNERS:
        raise ValueError(f"corner must be one of {CORNERS}, got {corner!r}")

    anchor_x = 0.0 if "left" in corner else float(width_px)
    anchor_y = 0.0 if "top" in corner else float(height)

    span = min(height, width_px)
    radius_v = max(_sample_range(rng, radius) * span, 1.0)
    depth_v = _sample_range(rng, depth) * span
    depth_v = min(depth_v, 0.5 * radius_v)  # đơn điệu, cùng lý do với fold_crease

    # Bảng phải phủ tới điểm XA GÓC NHẤT có thể có trên trang -- đường chéo --
    # chứ không chỉ vùng bóp (`radius_v * 3`): `np.interp` giữ nguyên giá trị
    # biên ngoài miền bảng, nên một bảng cụt sẽ kéo mọi điểm ngoài miền về
    # đúng mép bảng thay vì để chúng đứng yên như hàm số thật sự làm ở đó
    # (bump đã tắt hẳn qua vài lần `radius_v`).
    steps = 1024
    r_max = max(radius_v * 3.0, math.hypot(width_px, height)) + 1.0
    r = np.linspace(0.0, r_max, steps, dtype=np.float64)
    forward_r = r - depth_v * (r / radius_v) * np.exp(-((r / radius_v) ** 2))
    forward_r = np.maximum.accumulate(forward_r)  # lưới an toàn, xem fold_crease

    yy, xx = np.mgrid[0:height, 0:width_px].astype(np.float32)
    dx, dy = xx - anchor_x, yy - anchor_y
    dst_r = np.sqrt(dx * dx + dy * dy).astype(np.float64)
    src_r = np.interp(dst_r, forward_r, r)
    scale = np.divide(src_r, dst_r, out=np.ones_like(dst_r), where=dst_r > 1e-6)
    map_x = (anchor_x + dx * scale).astype(np.float32)
    map_y = (anchor_y + dy * scale).astype(np.float32)

    warped = cv2.remap(image, map_x, map_y, interpolation=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_REPLICATE)

    if quads.size:
        qdx = quads[..., 0] - anchor_x
        qdy = quads[..., 1] - anchor_y
        qr = np.sqrt(qdx * qdx + qdy * qdy).astype(np.float64)
        qforward = np.interp(qr, r, forward_r)
        qscale = np.divide(qforward, qr, out=np.ones_like(qr), where=qr > 1e-6)
        quads = quads.copy()
        quads[..., 0] = (anchor_x + qdx * qscale).astype(np.float32)
        quads[..., 1] = (anchor_y + qdy * qscale).astype(np.float32)

    return warped, quads


WARPS: dict[str, Callable[..., tuple[np.ndarray, Quads]]] = {
    "page_curl": page_curl,
    "fold_crease": fold_crease,
    "corner_bulge": corner_bulge,
}


def names() -> list[str]:
    return sorted(WARPS)


def apply_warp(
    name: str,
    image: np.ndarray,
    quads: Quads,
    params: dict[str, Any] | None = None,
    rng: random.Random | None = None,
) -> tuple[np.ndarray, Quads]:
    try:
        fn = WARPS[name]
    except KeyError:
        raise KeyError(f"unknown warp {name!r}; have {', '.join(names())}") from None
    return fn(image, quads, rng or random.Random(), **(params or {}))


def warp_regions(
    name: str,
    image: np.ndarray,
    params: dict[str, Any] | None,
    rng: random.Random,
    *region_lists: list[dict[str, Any]],
) -> tuple[Any, ...]:
    """Cong `image` và MỌI quad trong `region_lists`, cùng một phép biến dạng.

    Mỗi list trong `region_lists` là dạng hộp quen thuộc của repo này --
    `{"kind": ..., "quad": [[x, y]] * 4, ...}`, đúng cái `generators/html/
    render.py`'s `quads_from_rects` và `regions_from_rects` ghi ra. Một phép
    warp được bốc MỘT lần rồi áp cho mọi list cùng lúc -- gộp hết quad lại
    trước khi gọi thay vì warp từng list riêng, vì `boxes`, `words` và `cells`
    tả CÙNG một trang: bốc một góc cho `boxes` rồi bốc lại, khác đi, cho
    `words` sẽ làm hai bộ nhãn nói khác nhau về cùng một trang mà không bộ
    nào sai một mình.

    Trả về `(new_image, *new_region_lists)`, cùng độ dài và cùng khoá mỗi
    dict như đưa vào, chỉ `quad` được thay bằng góc đã warp.
    """
    counts = [len(regions) for regions in region_lists]
    flat = [box["quad"] for regions in region_lists for box in regions]
    quads = (np.asarray(flat, dtype=np.float32).reshape(-1, 4, 2)
              if flat else np.zeros((0, 4, 2), dtype=np.float32))

    new_image, new_quads = apply_warp(name, image, quads, params, rng)

    out: list[list[dict[str, Any]]] = []
    offset = 0
    for regions, count in zip(region_lists, counts):
        updated = []
        for box, quad in zip(regions, new_quads[offset:offset + count].tolist()):
            updated.append({**box, "quad": [[round(x, 1), round(y, 1)] for x, y in quad]})
        out.append(updated)
        offset += count
    return (new_image, *out)


__all__ = [
    "CORNERS",
    "WARPS",
    "apply_warp",
    "corner_bulge",
    "fold_crease",
    "names",
    "page_curl",
    "warp_regions",
]
