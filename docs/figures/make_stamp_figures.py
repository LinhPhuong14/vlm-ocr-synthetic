#!/usr/bin/env python3
"""DOCUMENTATION CODE — dựng hình minh hoạ cho `docs/co-che-sinh-con-dau.md`.

    python docs/figures/make_stamp_figures.py

Không thuộc đường sinh dữ liệu. Mỗi hình ở đây **chạy lại đúng phép đo mà tài
liệu trích**, rồi vẽ kết quả ra — nên một con số trong bài và hình minh hoạ nó
không thể lệch nhau: cả hai đến từ cùng một lần chạy.

Xuất **PNG chứ không JPG**, khác với các hình khác trong thư mục này. Phần lớn
hình dưới đây phóng to tới chỗ thấy được từng điểm ảnh, mà điều đang cần chỉ ra
là *một điểm ảnh mang giá trị gì* — nén JPEG bịa ra giá trị trung gian ở đúng
chỗ tài liệu khẳng định tập giá trị chỉ có hai phần tử.

Chỉ cần Pillow và numpy. Hai đồ thị vẽ tay bằng Pillow chứ không kéo matplotlib
về: hai đồ thị không đáng một phụ thuộc mới cho cả repo.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "tools"))

OUT = Path(__file__).resolve().parent / "con-dau"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

INK = (24, 24, 28)
ACCENT = (176, 26, 34)
BLUE = (30, 74, 148)
GREEN = (40, 132, 88)
MUTED = (118, 122, 130)
RULE = (214, 216, 220)
MARKER = (255, 120, 64)      # ô phóng, phải nổi trên nền ĐEN của các hình §2.2
PAPER = (252, 252, 250)


# ------------------------------------------------------------------ bố cục

def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REG, size)


def _wrap(text: str, font: ImageFont.FreeTypeFont, limit: float) -> list[str]:
    """Ngắt dòng theo BỀ RỘNG ĐO ĐƯỢC, không theo số ký tự.

    Bản đầu của `caption` vẽ thẳng một dòng và để Pillow cắt cụt ở mép ảnh.
    Trên loạt hình đầu tiên dựng ra, mọi chú thích đều mất chữ cuối — kể cả
    "KHÔNG khử răng cưa", tức là đúng cái kết luận hình ấy sinh ra để nói.
    """
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if font.getlength(trial) <= limit or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def caption(image: Image.Image, title: str, note: str = "", pad: int = 8,
            reserve: tuple[int, int] | None = None) -> Image.Image:
    """Dán dải chú thích lên trên ảnh, ngắt dòng cho vừa bề rộng.

    `reserve` đặt trước số dòng tiêu đề và số dòng ghi chú, để mọi ô trong cùng
    một hình có dải chú thích CAO BẰNG NHAU — nếu không, ô có chú thích ngắn sẽ
    đẩy ảnh của nó lên cao hơn ô bên cạnh và cả lưới xô lệch. `grid_of` tính
    sẵn giá trị ấy.
    """
    title_font = _font(14, bold=True)
    note_font = _font(12)
    limit = image.width - 2 * pad
    title_lines = _wrap(title, title_font, limit)
    note_lines = _wrap(note, note_font, limit) if note else []
    if reserve:
        title_lines += [""] * max(reserve[0] - len(title_lines), 0)
        note_lines += [""] * max(reserve[1] - len(note_lines), 0)
    height = pad + 18 * len(title_lines) + 15 * len(note_lines) + pad
    out = Image.new("RGB", (image.width, image.height + height), PAPER)
    draw = ImageDraw.Draw(out)
    y = pad - 4
    for line in title_lines:
        draw.text((pad, y), line, font=title_font, fill=INK)
        y += 18
    for line in note_lines:
        draw.text((pad, y), line, font=note_font, fill=MUTED)
        y += 15
    out.paste(image.convert("RGB"), (0, height))
    return out


def grid_of(items, cols: int, gap: int = 12) -> Image.Image:
    """Lưới từ các bộ (ảnh, tiêu đề, ghi chú), chú thích canh đều chiều cao."""
    title_font, note_font = _font(14, bold=True), _font(12)
    limit = min(image.width for image, _, _ in items) - 16
    reserve = (
        max(len(_wrap(title, title_font, limit)) for _, title, _ in items),
        max(len(_wrap(note, note_font, limit)) if note else 0 for _, _, note in items),
    )
    return grid([caption(image, t, n, reserve=reserve) for image, t, n in items], cols, gap)


def grid(tiles: list[Image.Image], cols: int, gap: int = 12) -> Image.Image:
    width = max(t.width for t in tiles)
    height = max(t.height for t in tiles)
    rows = (len(tiles) + cols - 1) // cols
    out = Image.new("RGB", (cols * width + (cols + 1) * gap,
                            rows * height + (rows + 1) * gap), PAPER)
    for index, tile in enumerate(tiles):
        row, col = divmod(index, cols)
        out.paste(tile, (gap + col * (width + gap), gap + row * (height + gap)))
    return out


def zoom(image: Image.Image, box: tuple[int, int, int, int], factor: int) -> Image.Image:
    """Phóng to bằng NEAREST — phải thấy từng điểm ảnh, không nội suy."""
    crop = image.convert("RGB").crop(box)
    return crop.resize((crop.width * factor, crop.height * factor), Image.NEAREST)


def framed(image: Image.Image, colour: tuple = RULE) -> Image.Image:
    out = Image.new("RGB", (image.width + 2, image.height + 2), colour)
    out.paste(image.convert("RGB"), (1, 1))
    return out


def on_paper(rgba: Image.Image, size: tuple[int, int] | None = None) -> Image.Image:
    """Ghép ảnh RGBA lên nền giấy.

    `convert("RGB")` trên RGBA cho nền ĐEN ở chỗ alpha = 0, vì kênh màu ở đó
    là (0,0,0). Con dấu vẽ ra nền đen là lỗi đã mắc một lần trong chính loạt
    hình này.
    """
    width, height = size or rgba.size
    flat = Image.new("RGB", (width, height), PAPER)
    flat.paste(rgba, ((width - rgba.width) // 2, (height - rgba.height) // 2), rgba)
    return flat


def value_set(image: Image.Image) -> int:
    """|V| — số giá trị phân biệt THỰC SỰ xuất hiện, không phải 256 mà định
    dạng cho phép. Xem §2.2 của tài liệu."""
    return int(len(np.unique(np.array(image.convert("L")))))


def edge_share(image: Image.Image) -> float:
    """p — phần trăm điểm ảnh có 0 < v < 255, tức nhận độ phủ MỘT PHẦN.

    Đây là số mang nghĩa; |V| chỉ là hệ quả của nó. Một bộ raster lấy mẫu diện
    tích phải cho p > 0 ở mọi hình có biên không trùng lưới điểm ảnh.
    """
    array = np.array(image.convert("L"))
    return 100.0 * float(((array > 0) & (array < 255)).mean())


def plot(series, *, size=(620, 320), xlabel="", ylabel="", xlog=False, title="") -> Image.Image:
    """Đồ thị đường tối giản, vẽ bằng Pillow. Đủ cho hai hình ở đây."""
    width, height = size
    left, right, top, bottom = 62, 18, 34, 42
    out = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(out)
    xs_all = [x for _, xs, _, _ in series for x in xs]
    ys_all = [y for _, _, ys, _ in series for y in ys]
    fx = (lambda v: math.log10(v)) if xlog else (lambda v: v)
    x0, x1 = fx(min(xs_all)), fx(max(xs_all))
    y0, y1 = min(ys_all), max(ys_all)
    span = max(y1 - y0, 1e-9)
    y0, y1 = y0 - span * 0.08, y1 + span * 0.08

    def px(v):
        return left + (fx(v) - x0) / max(x1 - x0, 1e-9) * (width - left - right)

    def py(v):
        return height - bottom - (v - y0) / max(y1 - y0, 1e-9) * (height - top - bottom)

    draw.rectangle([left, top, width - right, height - bottom], outline=RULE)
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        value = y0 + frac * (y1 - y0)
        draw.line([left, py(value), width - right, py(value)], fill=(235, 236, 239))
        draw.text((8, py(value) - 7), f"{value:5.1f}", font=_font(11), fill=MUTED)
    # Tối đa 9 vạch. Bản đầu vẽ một vạch cho MỌI giá trị x; trên đồ thị §2.5 --
    # 64 điểm dọc trục pixel -- nhãn chồng lên nhau thành một vệt không đọc được.
    ticks = sorted(set(xs_all))
    if len(ticks) > 9:
        stride = max(len(ticks) // 8, 1)
        ticks = ticks[::stride]
    for x in ticks:
        draw.line([px(x), height - bottom, px(x), height - bottom + 4], fill=MUTED)
        label = f"{x:g}"
        draw.text((px(x) - 3 * len(label), height - bottom + 7), label,
                  font=_font(11), fill=MUTED)
    if title:
        draw.text((left, 9), title, font=_font(13, bold=True), fill=INK)
    draw.text((width - right - 70, height - 15), xlabel, font=_font(11), fill=MUTED)
    draw.text((6, top - 16), ylabel, font=_font(11), fill=MUTED)

    for _, xs, ys, colour in series:
        points = [(px(x), py(y)) for x, y in zip(xs, ys)]
        draw.line(points, fill=colour, width=2)
        # Chấm điểm chỉ khi chuỗi thưa; trên chuỗi dày thì chấm nuốt mất đường.
        if len(points) <= 16:
            for x, y in points:
                draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=colour)
    legend_y = top + 8
    for label, _, _, colour in series:
        draw.line([width - right - 168, legend_y + 6, width - right - 144, legend_y + 6],
                  fill=colour, width=3)
        draw.text((width - right - 138, legend_y), label, font=_font(11), fill=INK)
        legend_y += 16
    return out


# -------------------------------------------- §2.2 nguyên thuỷ hình học

def fig_primitives() -> Image.Image:
    """Từng nguyên thuỷ của ImageDraw, đo bằng |V| và p (§2.2 của tài liệu).

    Có hai ô ĐỐI CHỨNG ở cuối, và chúng là phần đáng đọc nhất: `rectangle`
    thẳng trục cũng cho p = 0, mà đó là hành vi ĐÚNG kể cả với một bộ raster
    lấy mẫu diện tích hoàn hảo — biên của nó rơi đúng vào cạnh điểm ảnh nên
    không điểm nào bị biên đi xuyên qua. Nói cách khác p = 0 chỉ là bằng chứng
    khi biên không trùng lưới, và bảng này phải tự nói ra điều đó.

    Ô phóng chọn sao cho nó CẮT QUA MỘT MÉP: giữa một mảng đặc thì nguyên thuỷ
    nào cũng như nhau.
    """
    side, factor, window = 150, 6, 25
    cases = []

    def blank():
        return Image.new("L", (side, side), 0)

    image = blank()
    ImageDraw.Draw(image).ellipse([14, 14, side - 14, side - 14], outline=255, width=4)
    cases.append(("ellipse(outline=…, width=4)", image, (96, 24), "biên cong khắp nơi"))

    image = blank()
    ImageDraw.Draw(image).ellipse([14, 14, side - 14, side - 14], fill=255)
    cases.append(("ellipse(fill=…)", image, (16, 42), "biên cong khắp nơi"))

    image = blank()
    ImageDraw.Draw(image).polygon([(20, 20), (side - 20, 46), (74, side - 20)], fill=255)
    cases.append(("polygon(fill=…)", image, (58, 20), "ba cạnh đều chéo"))

    image = blank()
    ImageDraw.Draw(image).line([16, 26, side - 16, side - 30], fill=255, width=5)
    cases.append(("line(width=5), vẽ chéo", image, (60, 60), "biên chéo"))

    image = blank()
    ImageDraw.Draw(image).arc([14, 14, side - 14, side - 14], 200, 340, fill=255, width=6)
    cases.append(("arc(width=6)", image, (34, 32), "biên cong"))

    image = blank()
    ImageDraw.Draw(image).regular_polygon((side // 2, side // 2, 58), 5, fill=255)
    cases.append(("regular_polygon(…)", image, (28, 72), "bốn trong năm cạnh chéo"))

    image = blank()
    ImageDraw.Draw(image).text((8, 34), "Ag", font=_font(84, bold=True), fill=255)
    cases.append(("text('Ag', 84px)  ←  qua FreeType", image, (20, 58), "biên cong"))

    image = blank()
    ImageDraw.Draw(image).rectangle([20, 20, side - 20, side - 20], fill=255)
    cases.append(("rectangle(…) thẳng trục  ←  ĐỐI CHỨNG", image, (12, 60),
                  "biên TRÙNG cạnh điểm ảnh"))

    tiles = []
    for name, image, (bx, by), geometry in cases:
        values, edge = value_set(image), edge_share(image)
        marked = image.convert("RGB")
        ImageDraw.Draw(marked).rectangle([bx - 1, by - 1, bx + window, by + window],
                                         outline=MARKER)
        pair = Image.new("RGB", (side + 14 + window * factor,
                                 max(side, window * factor)), PAPER)
        pair.paste(marked, (0, 0))
        pair.paste(framed(zoom(image, (bx, by, bx + window, by + window), factor)),
                   (side + 14, 0))
        if "ĐỐI CHỨNG" in name:
            verdict = "p = 0 ở đây KHÔNG chứng minh gì: không điểm nào bị biên đi xuyên qua"
        elif edge > 0:
            verdict = "có lấy mẫu diện tích — biên trả về độ phủ một phần"
        else:
            verdict = "KHÔNG lấy mẫu diện tích — mọi điểm bị ép về một trong hai đầu"
        tiles.append((pair, f"{name} — |V| = {values}, p = {edge:.2f}%",
                      f"{geometry} · {verdict} · ô cam: phóng {factor}× vào "
                      f"{window}×{window} điểm ảnh cắt qua một mép"))
    return grid_of(tiles, 2)


# ------------------------------------------------- §2.3 phủ 8 bit của FreeType

def fig_freetype() -> Image.Image:
    """Trường phủ 8 bit của FreeType, và một lát cắt qua mép nét.

    Lát cắt chọn TỪ DỮ LIỆU chứ không đặt tay: quét tìm hàng có nhiều điểm phủ
    một phần nhất, rồi lấy cửa sổ quanh chỗ chuyển đầu tiên trong hàng ấy. Bản
    đầu của hình này cắm cứng `array[92]` và một dải cột đoán bằng mắt; lát cắt
    ấy rơi vào chỗ nét đặc, nên hình chỉ hiện hai khối 0 và 255 — đúng thứ
    ngược lại với điều nó sinh ra để chỉ.

    Đo trên "Ơ" 120 px, ảnh 260×150 — KHÁC bố trí của bảng §2.2 ("Ag" 84 px,
    ảnh 150×150), nên |V| và p ở đây không so trực tiếp với bảng ấy được. Cả
    hai bố trí đều ghi ra trong chú thích vì lý do đó.
    """
    image = Image.new("L", (260, 150), 0)
    ImageDraw.Draw(image).text((10, 18), "Ơ", font=_font(120, bold=True), fill=255)
    array = np.array(image)
    partial = (array > 0) & (array < 255)

    row = int(partial.sum(axis=1).argmax())
    columns = np.flatnonzero(partial[row])
    window = 22
    start = max(int(columns[0]) - window // 3, 0)
    start = min(start, array.shape[1] - window)


    # Ô phóng canh vào CHÍNH chỗ lát cắt lấy mẫu, nếu không hai nửa của hình
    # nói về hai chỗ khác nhau trên cùng một nét chữ.
    top = min(max(row - 16, 0), array.shape[0] - 32)
    left_edge = min(max(int(columns[0]) - 10, 0), array.shape[1] - 32)
    edge = zoom(image, (left_edge, top, left_edge + 32, top + 32), 9)
    marker_y = (row - top) * 9
    marked = ImageDraw.Draw(edge)
    marked.line([0, marker_y, edge.width, marker_y], fill=MARKER)

    bar_width = max(edge.width // window, 6)
    cut = Image.new("RGB", (edge.width, 140), PAPER)
    draw = ImageDraw.Draw(cut)
    draw.text((6, 4), f"lát cắt tại hàng y = {row}, {window} cột liên tiếp",
              font=_font(12, bold=True), fill=INK)
    draw.line([4, 126, edge.width - 4, 126], fill=RULE)
    for index in range(window):
        value = int(array[row, start + index])
        left = 6 + index * bar_width
        height = value * 0.34
        colour = ACCENT if 0 < value < 255 else MUTED
        draw.rectangle([left, 126 - height, left + bar_width - 2, 126], fill=colour)
        if 0 < value < 255:
            draw.text((left - 2, 126 - height - 13), str(value), font=_font(9), fill=ACCENT)
    body = Image.new("RGB", (edge.width, edge.height + cut.height + 8), PAPER)
    body.paste(edge, (0, 0))
    body.paste(cut, (0, edge.height + 8))
    return caption(
        body,
        f'FreeType, "Ơ" 120 px trên ảnh 260×150 — |V| = {value_set(image)}, '
        f"p = {edge_share(image):.2f}%",
        f"{int(partial.sum())} điểm ảnh nhận độ phủ MỘT PHẦN; cột đỏ là chúng, "
        f"kèm giá trị. Xám là 0 hoặc 255. Vạch cam trên ô phóng là hàng được cắt. "
        f"Bố trí khác bảng §2.2 nên p không so "
        f"trực tiếp — điều so được là p > 0 ở đây và p = 0 ở mọi nguyên thuỷ hình học.")


# ------------------------------------------------------- §2.4 lấy mẫu lại

def _ring(side: int, ss: int = 1) -> Image.Image:
    image = Image.new("L", (side * ss, side * ss), 0)
    radius = side * ss * 0.40
    centre = side * ss / 2
    ImageDraw.Draw(image).ellipse(
        [centre - radius, centre - radius, centre + radius, centre + radius],
        outline=255, width=max(int(side * ss * 0.018), 1))
    return image


def fig_resample() -> Image.Image:
    source = _ring(120, ss=8)
    tiles = []
    for name, method in (("NEAREST", Image.NEAREST), ("BILINEAR", Image.BILINEAR),
                         ("BICUBIC", Image.BICUBIC), ("LANCZOS", Image.LANCZOS)):
        small = source.resize((120, 120), method)
        patch = zoom(small, (52, 4, 76, 28), 6)
        pair = Image.new("RGB", (120 + 10 + patch.width, max(120, patch.height)), PAPER)
        pair.paste(small.convert("RGB"), (0, 0))
        pair.paste(framed(patch), (130, 0))
        tiles.append((pair, f"{name} — |V| = {value_set(small)}, p = {edge_share(small):.2f}%",
                      "cùng một bản dựng ở 8×, hạ về 120 px"))
    return grid_of(tiles, 2)


# ------------------------------------------------- §2.5 Gauss là ba lượt hộp

def fig_gaussian() -> Image.Image:
    n, sigma = 801, 8.0
    step = np.zeros((41, n), np.uint8)
    step[:, n // 2:] = 255
    blurred = np.array(Image.fromarray(step).filter(ImageFilter.GaussianBlur(sigma)),
                       np.float64)
    lsf = np.clip(np.diff(blurred[20]), 0, None)
    lsf = lsf / lsf.sum()
    x = np.arange(n - 1) - n // 2 + 0.5
    mean = (lsf * x).sum()
    m2 = (lsf * (x - mean) ** 2).sum()
    kurtosis = (lsf * (x - mean) ** 4).sum() / m2 ** 2
    n_box = 6 / (5 * (3 - kurtosis))

    gauss = np.exp(-x ** 2 / (2 * sigma ** 2))
    gauss = gauss / gauss.sum()

    box_width = int(round(sigma * math.sqrt(12 / 3)))
    box = np.ones(box_width) / box_width
    three = box.copy()
    for _ in range(2):
        three = np.convolve(three, box)
    three = three / three.sum()
    tx = np.arange(len(three)) - len(three) // 2

    keep = np.abs(x) <= 32
    keep3 = np.abs(tx) <= 32
    figure = plot(
        [("Pillow GaussianBlur", list(x[keep]), list(lsf[keep] / lsf.max()), ACCENT),
         ("Gauss thật", list(x[keep]), list(gauss[keep] / gauss.max()), BLUE),
         ("chập 3 hộp", list(tx[keep3]), list(three[keep3] / three.max()), GREEN)],
        xlabel="pixel", ylabel="phủ (chuẩn hoá)",
        title=f"Hàm trải rộng đường, đo tại σ = {sigma:g}")
    return caption(
        figure,
        f"σ đo được {math.sqrt(m2):.3f} · kurtosis {kurtosis:.3f} → n ≈ {n_box:.1f} lượt hộp",
        "Gauss thật có kurtosis 3,0. Chập n hộp cho 3 − 6/(5n). Đường đỏ bám "
        "đường xanh lá, không bám đường xanh lam — đuôi ngắn hơn Gauss.")


# ------------------------------------------------------------ §2.6 ghép alpha

def fig_alpha() -> Image.Image:
    side = 240
    first = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ImageDraw.Draw(first).text((14, 40), "Ô", font=_font(120, bold=True),
                               fill=ACCENT + (200,))
    second = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    ImageDraw.Draw(second).text((84, 40), "N", font=_font(120, bold=True),
                                fill=ACCENT + (200,))
    over = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    over.alpha_composite(first)
    over.alpha_composite(second)
    alpha = Image.fromarray(np.array(over)[..., 3]).convert("RGB")
    return grid_of([
        (framed(on_paper(over)), "hai glyph ghép bằng alpha_composite",
         "toán tử over của Porter–Duff, alpha 200/255 mỗi glyph"),
        (framed(alpha), "kênh alpha của kết quả",
         "chỗ giao SÁNG hơn: phủ cộng dồn theo α_o = α_a + α_b(1 − α_a), không thay thế nhau"),
    ], 2)


# ---------------------------------------------------------- §3.1 siêu lấy mẫu

def fig_supersample() -> Image.Image:
    tiles = []
    for ss in (1, 2, 4, 8):
        big = _ring(160, ss=ss)
        small = big.resize((160, 160), Image.LANCZOS) if ss > 1 else big
        patch = zoom(small, (68, 4, 92, 28), 6)
        pair = Image.new("RGB", (160 + 10 + patch.width, max(160, patch.height)), PAPER)
        pair.paste(small.convert("RGB"), (0, 0))
        pair.paste(framed(patch), (170, 0))
        array = np.array(small)
        partial = 100 * float(((array > 8) & (array < 247)).mean())
        how = "vẽ thẳng ở độ phân giải đích" if ss == 1 else f"vẽ ở {ss}× rồi hạ bằng LANCZOS"
        tiles.append((pair, f"SS = {ss} — |V| = {value_set(small)}, p = {partial:.2f}%",
                      f"bộ nhớ {ss * ss}× · {how}"))
    return grid_of(tiles, 2)


# ------------------------------------------------------ §3.2 chữ trên cung tròn

def _arc_demo(text: str, radius: float, size: int, constant_step: bool) -> Image.Image:
    """Vẽ một vành chữ theo luật đúng, hoặc theo luật bước đều để đối chứng."""
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    font = _font(int(size * 0.058), bold=True)
    widths = [font.getlength(ch) * 1.02 for ch in text]
    if constant_step:
        widths = [max(widths)] * len(text)
    centre = size / 2
    angle = -sum(widths) / radius / 2
    for ch, width in zip(text, widths):
        step = width / radius
        at = angle + step / 2
        tile = Image.new("RGBA", (int(width) + 8, int(font.size * 1.6) + 8), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((4, 4), ch, font=font, fill=ACCENT + (255,))
        tile = tile.rotate(-at * 180 / math.pi, resample=Image.BICUBIC, expand=True)
        canvas.alpha_composite(tile, (int(centre + radius * math.sin(at) - tile.width / 2),
                                      int(centre - radius * math.cos(at) - tile.height / 2)))
        angle += step
    return canvas


def _ring_backdrop(size: int, radius: float) -> Image.Image:
    plate = Image.new("RGB", (size, size), PAPER)
    draw = ImageDraw.Draw(plate)
    for grow in (16, -16):
        draw.ellipse([size / 2 - radius - grow, size / 2 - radius - grow,
                      size / 2 + radius + grow, size / 2 + radius + grow], outline=RULE)
    return plate


def fig_arc() -> Image.Image:
    size, radius = 300, 108.0
    text = "CONG TY TNHH AN PHU I"

    diagram = Image.new("RGB", (size, size), PAPER)
    draw = ImageDraw.Draw(diagram)
    centre = size / 2
    draw.ellipse([centre - radius, centre - radius, centre + radius, centre + radius],
                 outline=(200, 202, 208))
    draw.line([centre, 18, centre, size - 18], fill=(234, 235, 238))
    draw.line([18, centre, size - 18, centre], fill=(234, 235, 238))
    for index, theta in enumerate((-0.72, -0.26, 0.2)):
        x = centre + radius * math.sin(theta)
        y = centre - radius * math.cos(theta)
        draw.line([centre, centre, x, y], fill=(206, 208, 214))
        tx, ty = math.cos(theta), math.sin(theta)
        draw.line([x - tx * 28, y - ty * 28, x + tx * 28, y + ty * 28], fill=BLUE, width=2)
        draw.ellipse([x - 3, y - 3, x + 3, y + 3], fill=ACCENT)
        draw.text((x + 7, y - 17), f"θ{index}", font=_font(12, bold=True), fill=ACCENT)
    draw.text((centre + 7, centre + 7), "R", font=_font(12, bold=True), fill=MUTED)
    draw.text((12, size - 30), "xanh = tiếp tuyến tại θ, cũng là góc xoay glyph",
              font=_font(11), fill=BLUE)

    def over_ring(layer):
        plate = _ring_backdrop(size, radius)
        plate.paste(layer, (0, 0), layer)
        return plate

    return grid_of([
        (framed(diagram), "dựng hình",
         "bước góc = wᵢ / R — advance width chia bán kính; góc xoay = chính θ"),
        (framed(over_ring(_arc_demo(text, radius, size, False))),
         "luật đúng: bước ∝ advance width",
         "chữ I hẹp chiếm ít góc, chữ N rộng chiếm nhiều — như trên một dòng thẳng"),
        (framed(over_ring(_arc_demo(text, radius, size, True))),
         "bước đều — đúng luật của CurveLayout",
         "mọi glyph nhận ô rộng bằng glyph RỘNG NHẤT, nên dòng chữ giãn toác và "
         "chiếm nhiều cung hơn hẳn"),
    ], 3)


# ---------------------------------------------------------- §3.3 khớp cỡ chữ

def _ring_text(name: str, font: ImageFont.FreeTypeFont, radius: float,
               size: int) -> tuple[Image.Image, float]:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    widths = [font.getlength(ch) * 1.02 for ch in name]
    span = sum(widths) / radius
    angle = -span / 2
    for ch, width in zip(name, widths):
        step = width / radius
        at = angle + step / 2
        tile = Image.new("RGBA", (int(width) + 8, int(font.size * 1.6) + 8), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((4, 4), ch, font=font, fill=ACCENT + (255,))
        tile = tile.rotate(-at * 180 / math.pi, resample=Image.BICUBIC, expand=True)
        layer.alpha_composite(tile, (int(size / 2 + radius * math.sin(at) - tile.width / 2),
                                     int(size / 2 - radius * math.cos(at) - tile.height / 2)))
        angle += step
    return layer, span * 180 / math.pi


def fig_fit() -> Image.Image:
    import make_ornaments as M

    size, radius, ceiling = 300, 108.0, 212
    tiles = []
    for name in ("AN PHU", "CONG TY TNHH MOT THANH VIEN XUAT NHAP KHAU TAN PHAT"):
        fixed = _font(int(size * 0.062), bold=True)
        fitted = M._fit_arc(name, radius, ceiling, FONT_BOLD, size * 0.062)
        for label, font in (("cỡ cố định", fixed), ("_fit_arc", fitted)):
            layer, degrees = _ring_text(name, font, radius, size)
            plate = _ring_backdrop(size, radius)
            plate.paste(layer, (0, 0), layer)
            overflow = "  ← tràn quá 212°, đâm vào vành dưới" if degrees > ceiling else ""
            tiles.append((framed(plate), f"{label} · {font.size} px",
                          f"cung chiếm {degrees:.0f}°{overflow}"))
    return grid_of(tiles, 2)


# -------------------------------------------------------------- §3.4 mô hình mực

def fig_ink() -> Image.Image:
    import make_ornaments as M

    rng = random.Random(23)
    size = 200

    def show(field, title, note):
        array = np.clip(field * 255, 0, 255).astype(np.uint8)
        return (framed(Image.fromarray(array).convert("RGB")), title, note)

    def noise(cell):
        small = np.random.default_rng(rng.randrange(2 ** 31)).random(
            (max(size // cell, 2), max(size // cell, 2)))
        return np.array(Image.fromarray((small * 255).astype(np.uint8))
                        .resize((size, size), Image.BICUBIC), np.float32) / 255.0

    fine, mid, coarse = noise(6), noise(24), noise(90)
    grain = fine * 0.45 + mid * 0.35 + coarse * 0.20
    grain = (grain - grain.min()) / max(float(np.ptp(grain)), 1e-6)
    coverage = 0.86
    mask = np.clip((grain - (1 - coverage)) / coverage, 0, 1)
    mask = np.clip(0.62 + 0.55 * mask, 0, 1)

    holes = Image.new("L", (size, size), 255)
    hole_draw = ImageDraw.Draw(holes)
    for _ in range(4):
        r = rng.uniform(0.06, 0.16) * size
        x, y = rng.uniform(0, size), rng.uniform(0, size)
        hole_draw.ellipse([x - r, y - r, x + r, y + r], fill=rng.randint(95, 185))
    holes = holes.filter(ImageFilter.GaussianBlur(size * 0.05))
    final = mask * (np.array(holes, np.float32) / 255.0)

    seal = M.round_seal("CONG TY TNHH AN PHU", "MST 0108432911", ["HA NOI"],
                        seed=23, size=size)
    return grid_of([
        show(fine, "N(6) — hạt mực", "tần số cao"),
        show(mid, "N(24) — lực tay không đều", "tần số vừa"),
        show(coarse, "N(90) — độ vồng mặt dấu", "tần số thấp"),
        show(grain, "grain = 0,45·N(6) + 0,35·N(24) + 0,20·N(90)",
             "một tầng duy nhất cho mặt gợn đều, nhìn là biết máy sinh"),
        show(mask, "mask sau ánh xạ phủ",
             "SÀN 0,62 — chỗ mặt dấu CHẠM giấy thì mực ăn no"),
        show(final, "× lớp mảng không chạm giấy",
             "2–5 ellipse, bán kính 6–16% bề rộng, làm mờ 0,05·W"),
        (framed(on_paper(seal, (size, size))),
         "kết quả: α ← α·mask, mờ 0,4, xoay ±16°",
         "so với vành hình học đặc ở hình §2.2 — cùng một đường tròn"),
    ], 3)


# ------------------------------------------------------- §3.5 toán tử biến thể

def fig_variants() -> Image.Image:
    import make_ornaments as M

    size = 190
    base = M.round_seal("CONG TY TNHH AN PHU", "MST 0108432911", ["HA NOI"],
                        seed=23, size=size)
    box = (size + 46, size + 46)
    return grid_of([
        (framed(on_paper(base, box)), "gốc", "round_seal(…)"),
        (framed(on_paper(M.double_strike(base, seed=81), box)), "double_strike",
         "tay trượt: bản mờ α×0,45 lệch ngẫu nhiên, rồi bản gốc đè lên"),
        (framed(on_paper(M._ring_only(base), box)), "_ring_only",
         "mặt dấu vồng: α ← α·(0,18 + 0,82·fade(r)), chỉ vành chạm giấy"),
        (framed(on_paper(M.edge_seal(base), box)), "edge_seal",
         "dấu giáp lai: CẮT THẲNG giữ 42% — mép sắc là dấu hiệu nhận biết, không làm mờ dần"),
    ], 2)


# ------------------------------------------------------- §4.1 ngân sách sai số

def fig_error_budget() -> Image.Image:
    size, radius, thick = 430, 190.0, 6.0
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64) + 0.5
    distance = np.hypot(xx - size / 2, yy - size / 2)
    truth = np.clip(0.5 - (np.abs(distance - radius) - thick / 2), 0.0, 1.0)

    factors = [1, 2, 3, 4, 6, 8, 12]
    psnrs = []
    for ss in factors:
        side = size * ss
        image = Image.new("L", (side, side), 0)
        outer = (radius + thick / 2) * ss
        ImageDraw.Draw(image).ellipse(
            [side / 2 - outer, side / 2 - outer, side / 2 + outer, side / 2 + outer],
            outline=255, width=max(int(round(thick * ss)), 1))
        array = np.array(image.resize((size, size), Image.LANCZOS), np.float64) / 255.0
        rmse = float(np.sqrt(((array - truth) ** 2).mean()))
        psnrs.append(20 * math.log10(1 / rmse))

    theory = [psnrs[0] + 20 * math.log10(ss / factors[0]) for ss in factors]
    figure = plot([("đo được", factors, psnrs, ACCENT),
                   ("lý thuyết 1/SS", factors, theory, BLUE)],
                  xlabel="SS", ylabel="PSNR (dB)", xlog=True,
                  title="Sai số phủ so với chuẩn giải tích")
    draw = ImageDraw.Draw(figure)
    index = factors.index(4)
    draw.text((250, 268), f"SS = 4 (repo dùng): {psnrs[index]:.1f} dB, bộ nhớ 16×",
              font=_font(12, bold=True), fill=INK)
    worst = max(abs(p - t) for p, t in zip(psnrs, theory))
    return caption(
        figure, f"Sai số suy giảm theo 1/SS — lệch lý thuyết tối đa {worst:.2f} dB",
        "chuẩn là phủ giải tích clip(0,5 − d, 0, 1), KHÔNG phải một bản dựng ở SS "
        "cao: lưới của bản dựng có thể trùng lưới của chuẩn và làm đẹp kết quả")


FIGURES = [
    ("fig-2.2-nguyen-thuy-hinh-hoc", fig_primitives),
    ("fig-2.3-phu-freetype", fig_freetype),
    ("fig-2.4-lay-mau-lai", fig_resample),
    ("fig-2.5-gauss-ba-luot-hop", fig_gaussian),
    ("fig-2.6-ghep-alpha", fig_alpha),
    ("fig-3.1-sieu-lay-mau", fig_supersample),
    ("fig-3.2-chu-tren-cung-tron", fig_arc),
    ("fig-3.3-khop-co-chu", fig_fit),
    ("fig-3.4-mo-hinh-muc", fig_ink),
    ("fig-3.5-toan-tu-bien-the", fig_variants),
    ("fig-4.1-ngan-sach-sai-so", fig_error_budget),
]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, build in FIGURES:
        np.random.seed(7)
        random.seed(7)
        image = build().convert("RGB")
        path = OUT / f"{name}.png"
        image.save(path, optimize=True)
        print(f"[ok] {path.relative_to(REPO_ROOT)}  {image.width}×{image.height}")
    print(f"\n{len(FIGURES)} hình -> {OUT.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
