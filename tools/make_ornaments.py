#!/usr/bin/env python3
"""Generate the seals and flourishes in `textures/ornament/`.

    python tools/make_ornaments.py

The `ornament` attribute (`rulebase/rules/ornament.yaml`) names these files, so
a rules file and a directory listing have to agree; `pipeline/preflight.py`
checks that they do. They are generated rather than scanned for the same reason
`tools/make_textures.py` generates paper: a scan of somebody's real company seal
is neither redistributable nor reproducible from a seed, and a fresh clone would
have nothing to composite.

**Why these are drawn here and not by synthtiger.** synthtiger builds text
images out of FLAT LAYERS -- a `TextLayer` is one horizontal run of text with
effects stacked on it: perspective, elastic distortion, shadow, colour. It has
no text-on-a-path primitive, and a round seal is exactly that: every glyph
rotated to the tangent of a circle. So the drawing happens once, here, into PNGs
with an alpha channel; the ageing and compositing that synthtiger and
`degradation/` are good at then treat the result like any other overlay.

Company names, tax codes and addresses below are invented for synthetic data.
They are not real businesses.
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "textures" / "ornament"
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SS = 4                                  # vẽ ở 4x rồi thu nhỏ, cho mép mượt


# --------------------------------------------------------------- chữ theo cung

def _arc_text(draw_on: Image.Image, text: str, centre: tuple[float, float],
              radius: float, font: ImageFont.FreeTypeFont, mid_deg: float,
              fill: tuple[int, int, int, int], outward: bool = True,
              spacing: float = 1.0) -> None:
    """Đặt `text` chạy theo cung tròn, mỗi ký tự xoay theo tiếp tuyến.

    `mid_deg` là góc giữa của dòng chữ, 0 độ ở đỉnh và tăng theo chiều kim đồng
    hồ. `outward=True` cho vành trên (đọc xuôi khi nhìn từ ngoài vào);
    `outward=False` cho vành dưới, chữ lộn lại để vẫn đọc xuôi.
    """
    widths = [font.getlength(ch) * spacing for ch in text]
    total = sum(widths)
    # cung mà cả dòng chiếm, quy từ bề rộng pixel sang góc
    span = total / radius
    angle = mid_deg * math.pi / 180.0 - (span / 2 if outward else -span / 2)

    for ch, width in zip(text, widths):
        step = width / radius
        at = angle + (step / 2 if outward else -step / 2)

        glyph = Image.new("RGBA", (int(width) + 8, int(font.size * 1.6) + 8), (0, 0, 0, 0))
        ImageDraw.Draw(glyph).text((4, 4), ch, font=font, fill=fill)
        # 0 độ ở đỉnh: quay -at (PIL quay ngược kim đồng hồ) rồi lật cho vành dưới
        rotation = -at * 180.0 / math.pi
        glyph = glyph.rotate(rotation if outward else rotation + 180,
                             resample=Image.BICUBIC, expand=True)

        # tâm ký tự nằm trên đường tròn bán kính `radius`
        cx = centre[0] + radius * math.sin(at)
        cy = centre[1] - radius * math.cos(at)
        draw_on.alpha_composite(glyph, (int(cx - glyph.width / 2), int(cy - glyph.height / 2)))
        angle += step if outward else -step


def _fit_arc(text: str, radius: float, max_deg: float, path: str,
             start_px: float, spacing: float = 1.02) -> ImageFont.FreeTypeFont:
    """Cỡ chữ lớn nhất mà cả dòng vẫn nằm gọn trong `max_deg` độ của cung.

    Tên doanh nghiệp Việt Nam dài ngắn rất khác nhau -- "CÔNG TY TNHH MỘT THÀNH
    VIÊN..." gấp đôi một cái tên ngắn. Cỡ chữ cố định thì tên dài chạy vòng quá
    nửa vòng tròn và đâm vào chữ của vành dưới. Con dấu thật xử lý y hệt: thợ
    khắc co chữ lại cho vừa vành.
    """
    size = start_px
    while size > start_px * 0.55:
        font = ImageFont.truetype(path, int(size))
        span = sum(font.getlength(ch) * spacing for ch in text) / radius
        if span * 180.0 / math.pi <= max_deg:
            return font
        size *= 0.96
    return ImageFont.truetype(path, int(size))


def _star(draw: ImageDraw.ImageDraw, centre: tuple[float, float], radius: float,
          fill: tuple[int, int, int, int]) -> None:
    """Ngôi sao năm cánh giữa dấu."""
    points = []
    for index in range(10):
        r = radius if index % 2 == 0 else radius * 0.42
        a = -math.pi / 2 + index * math.pi / 5
        points.append((centre[0] + r * math.cos(a), centre[1] + r * math.sin(a)))
    draw.polygon(points, fill=fill)


# ------------------------------------------------------------------- mực dấu

def _ink(image: Image.Image, rng: random.Random, coverage: float = 0.86) -> Image.Image:
    """Làm mực đóng dấu: chỗ đậm chỗ nhạt, vài mảng mất hẳn, mép hơi nhoè.

    Một con dấu đóng tay không bao giờ phủ đều: mặt dấu cong, lực tay lệch, mực
    trên tấm lót không đều. Đó là ba thứ tạo ra ba lớp nhiễu dưới đây.
    """
    array = np.array(image).astype(np.float32)
    height, width = array.shape[:2]

    def noise(cell: int) -> np.ndarray:
        small = np.array(Image.fromarray(
            (np.random.default_rng(rng.randrange(2 ** 31))
             .random((max(height // cell, 2), max(width // cell, 2))) * 255).astype(np.uint8)
        ).resize((width, height), Image.BICUBIC)).astype(np.float32) / 255.0
        return small

    grain = noise(6) * 0.45 + noise(24) * 0.35 + noise(90) * 0.20
    grain = (grain - grain.min()) / max(float(np.ptp(grain)), 1e-6)
    mask = np.clip((grain - (1.0 - coverage)) / max(coverage, 1e-6), 0, 1)
    # Sàn 0.62 chứ không 0.35: chỗ mặt dấu chạm giấy thì mực ăn no, phần
    # loang lổ là do chỗ KHÔNG chạm, và chỗ đó xử lý riêng bằng `holes`.
    mask = np.clip(0.62 + 0.55 * mask, 0, 1)

    # vài mảng trắng: chỗ mặt dấu không chạm giấy
    holes = Image.new("L", (width, height), 255)
    hole_draw = ImageDraw.Draw(holes)
    for _ in range(rng.randint(2, 5)):
        r = rng.uniform(0.06, 0.16) * width
        x, y = rng.uniform(0, width), rng.uniform(0, height)
        hole_draw.ellipse([x - r, y - r, x + r, y + r], fill=rng.randint(95, 185))
    holes = holes.filter(ImageFilter.GaussianBlur(width * 0.05))
    mask *= np.array(holes).astype(np.float32) / 255.0

    array[..., 3] *= mask
    out = Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGBA")
    return out.filter(ImageFilter.GaussianBlur(0.4))


# ------------------------------------------------------------------ con dấu

def round_seal(top: str, bottom: str, middle: list[str], *, seed: int,
                 size: int = 520, colour=(196, 30, 38), star: bool = True) -> Image.Image:
    """Dấu tròn: hai vành, chữ chạy vành trên và vành dưới, giữa là sao hoặc chữ."""
    rng = random.Random(seed)
    side = size * SS
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    centre = (side / 2, side / 2)
    ink = colour + (255,)

    outer = side * 0.47
    draw.ellipse([centre[0] - outer, centre[1] - outer, centre[0] + outer, centre[1] + outer],
                 outline=ink, width=int(side * 0.022))
    inner = side * 0.415
    draw.ellipse([centre[0] - inner, centre[1] - inner, centre[0] + inner, centre[1] + inner],
                 outline=ink, width=int(side * 0.007))

    top_radius = side * 0.355
    top_text = top.upper()
    top_font = _fit_arc(top_text, top_radius, 212, FONT_BOLD, side * 0.062)
    _arc_text(canvas, top_text, centre, top_radius, top_font, mid_deg=0,
              fill=ink, outward=True, spacing=1.02)
    top_span = sum(top_font.getlength(ch) * 1.02 for ch in top_text) / top_radius * 180 / math.pi

    if bottom:
        bottom_text = bottom.upper()
        bottom_font = _fit_arc(bottom_text, side * 0.360, 110, FONT_BOLD, side * 0.050)
        _arc_text(canvas, bottom_text, centre, side * 0.360, bottom_font, mid_deg=180,
                  fill=ink, outward=False, spacing=1.02)
        bottom_span = (sum(bottom_font.getlength(ch) * 1.02 for ch in bottom_text)
                       / (side * 0.360) * 180 / math.pi)
        # Dấu sao ngăn hai vành, đặt vào GIỮA khoảng trống còn lại chứ không cố
        # định ở 90 và 270 -- chỗ trống dịch theo độ dài của hai dòng chữ.
        gap_mid = (top_span / 2 + (180 - bottom_span / 2)) / 2
        star_font = ImageFont.truetype(FONT_BOLD, int(side * 0.055))
        for angle in (gap_mid, 360 - gap_mid):
            _arc_text(canvas, "*", centre, side * 0.360, star_font, mid_deg=angle,
                      fill=ink, outward=True)

    draw = ImageDraw.Draw(canvas)
    if star:
        _star(draw, centre, side * 0.115, ink)
        text_top = centre[1] + side * 0.135
    else:
        text_top = centre[1] - side * 0.06

    line_font = ImageFont.truetype(FONT_BOLD, int(side * 0.058))
    for index, line in enumerate(middle):
        w = draw.textlength(line, font=line_font)
        draw.text((centre[0] - w / 2, text_top + index * side * 0.062), line,
                  font=line_font, fill=ink)

    canvas = canvas.resize((size, size), Image.LANCZOS)
    canvas = _ink(canvas, rng, coverage=rng.uniform(0.78, 0.93))
    return canvas.rotate(rng.uniform(-16, 16), resample=Image.BICUBIC, expand=True)


def rectangular_seal(lines: list[str], *, seed: int, width: int = 560, height: int = 220,
                  colour=(196, 30, 38)) -> Image.Image:
    """Dấu chữ nhật -- "ĐÃ THU TIỀN", "BẢN SAO" -- đóng chồng lên tờ hoá đơn."""
    rng = random.Random(seed)
    w, h = width * SS, height * SS
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    ink = colour + (255,)

    pad = int(w * 0.02)
    draw.rectangle([pad, pad, w - pad, h - pad], outline=ink, width=int(h * 0.045))
    pad2 = int(w * 0.038)
    draw.rectangle([pad2, pad2, w - pad2, h - pad2], outline=ink, width=int(h * 0.016))

    sizes = [int(h * 0.34), int(h * 0.19)]
    y = h * 0.26
    for index, line in enumerate(lines):
        font = ImageFont.truetype(FONT_BOLD, sizes[min(index, len(sizes) - 1)])
        tw = draw.textlength(line, font=font)
        draw.text((w / 2 - tw / 2, y), line, font=font, fill=ink)
        y += font.size * 1.25

    canvas = canvas.resize((width, height), Image.LANCZOS)
    canvas = _ink(canvas, rng, coverage=rng.uniform(0.80, 0.94))
    return canvas.rotate(rng.uniform(-9, 9), resample=Image.BICUBIC, expand=True)


# ------------------------------------------------------------------ hoạ tiết

def wave_band(width: int, height: int, *, seed: int, colour=(47, 82, 51),
             bands: int = 4) -> Image.Image:
    """Dải sóng: mấy đường hình sin lệch pha, dùng làm nẹp đầu hoặc chân trang."""
    rng = random.Random(seed)
    w, h = width * SS, height * SS
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for band in range(bands):
        phase = rng.uniform(0, math.tau)
        amp = h * rng.uniform(0.16, 0.30)
        period = w / rng.uniform(1.4, 3.2)
        mid = h * (band + 0.5) / bands
        alpha = int(235 - band * (150 / max(bands, 1)))
        points = [(x, mid + amp * math.sin(x / period * math.tau + phase))
                  for x in range(0, w + 1, max(w // 400, 1))]
        draw.line(points, fill=colour + (alpha,), width=max(int(h * 0.035), SS))
    return canvas.resize((width, height), Image.LANCZOS)


def guilloche(size: int, *, seed: int, colour=(47, 82, 51),
                      loops: int = 7) -> Image.Image:
    """Hoa văn guilloche: đường xoắn kín như trên giấy tờ có giá.

    Hai chuyển động tròn chồng nhau -- một quay nhanh trên một quay chậm -- là
    cách máy khắc guilloche thật vẽ ra hoa thị này.
    """
    rng = random.Random(seed)
    side = size * SS
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    centre = side / 2
    for ring in range(3):
        big = centre * (0.92 - ring * 0.17)
        small = big * rng.uniform(0.18, 0.30)
        petals = loops + ring * 2
        alpha = 46 - ring * 10
        # Một vành là cả CHÙM đường lệch pha, không phải một đường. Máy khắc
        # guilloche quay bánh răng nhích từng nấc, mỗi nấc một đường; chỗ các
        # đường cắt nhau mới thành mảng ren dày mà một đường đơn không có.
        strands = 14 - ring * 2
        for strand in range(strands):
            phase = strand / strands * math.tau / petals
            points = []
            for step in range(1400):
                t = step / 1400 * math.tau
                r = big - small + small * math.cos(petals * (t + phase))
                points.append((centre + r * math.cos(t), centre + r * math.sin(t)))
            draw.line(points + [points[0]], fill=colour + (alpha,),
                      width=max(int(side * 0.0016), SS))
    return canvas.resize((size, size), Image.LANCZOS)


def corner_bracket(size: int, *, colour=(47, 82, 51)) -> Image.Image:
    """Hoạ tiết góc: mấy chữ nhật lồng nhau, cắt góc -- nẹp bốn góc tờ giấy."""
    side = size * SS
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for index, (inset, alpha, weight) in enumerate(
            ((0.06, 235, 0.030), (0.16, 180, 0.016), (0.26, 130, 0.010))):
        a, b = side * inset, side * (1 - inset)
        draw.line([(a, b), (a, a), (b, a)], fill=colour + (alpha,),
                  width=max(int(side * weight), SS), joint="curve")
    draw.rectangle([side * 0.36, side * 0.36, side * 0.44, side * 0.44],
                   fill=colour + (200,))
    return canvas.resize((size, size), Image.LANCZOS)


def rect_grid(width: int, height: int, *, seed: int,
                  colour=(47, 82, 51)) -> Image.Image:
    """Lưới chữ nhật lệch nhau -- nền mờ cho khối tiêu đề."""
    rng = random.Random(seed)
    w, h = width * SS, height * SS
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    for _ in range(rng.randint(16, 26)):
        x = rng.uniform(0, w * 0.9)
        y = rng.uniform(0, h * 0.85)
        rw = rng.uniform(w * 0.05, w * 0.22)
        rh = rng.uniform(h * 0.12, h * 0.55)
        alpha = rng.randint(28, 90)
        if rng.random() < 0.45:
            draw.rectangle([x, y, x + rw, y + rh], fill=colour + (alpha,))
        else:
            draw.rectangle([x, y, x + rw, y + rh], outline=colour + (alpha + 40,),
                           width=max(int(h * 0.012), SS))
    return canvas.resize((width, height), Image.LANCZOS)


# ------------------------------------------------------------------------ main

def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    GREEN, TEAL, VIOLET, BLUE = (47, 82, 51), (15, 76, 92), (111, 90, 168), (30, 74, 148)
    made: list[tuple[str, Image.Image]] = [
        # --- seals: the ink a document is closed with
        ("seal_round_company", round_seal(
            "CÔNG TY TNHH BÁN LẺ AN PHÚ VIỆT NAM", "MST 0108432911", ["HÀ NỘI"],
            seed=23, star=True)),
        ("seal_round_hotel", round_seal(
            "CÔNG TY TNHH KHÁCH SẠN THÁI AN", "MST 4201234567", ["THÁI AN", "HOTEL"],
            seed=44, star=False, colour=(178, 34, 40))),
        ("seal_round_export", round_seal(
            "CÔNG TY TNHH DỆT MAY TÂN PHÁT VINA", "ĐỒNG NAI", ["TÂN PHÁT", "VINA"],
            seed=37, star=False, colour=BLUE)),
        ("seal_square_paid", rectangular_seal(["ĐÃ THU TIỀN", "PAID"], seed=5)),
        ("seal_square_copy", rectangular_seal(["BẢN SAO", "COPY"], seed=9, colour=BLUE)),

        # --- flourishes: the ink a document is designed with
        ("wave_band_green", wave_band(1400, 150, seed=3, colour=GREEN)),
        ("wave_band_red", wave_band(1400, 150, seed=8, colour=(179, 38, 30))),
        ("wave_band_teal", wave_band(1400, 150, seed=15, colour=TEAL)),
        ("guilloche_green", guilloche(700, seed=4, colour=GREEN)),
        ("guilloche_violet", guilloche(700, seed=12, colour=VIOLET)),
        ("guilloche_teal", guilloche(700, seed=17, colour=TEAL)),
        ("corner_bracket_green", corner_bracket(360, colour=GREEN)),
        ("corner_bracket_teal", corner_bracket(360, colour=TEAL)),
        ("rect_grid_green", rect_grid(1200, 320, seed=6, colour=GREEN)),
        ("rect_grid_teal", rect_grid(1200, 320, seed=19, colour=TEAL)),
    ]

    for name, image in made:
        path = ASSETS / f"{name}.png"
        image.save(path)
        print(f"{name + '.png':26} {image.width}x{image.height}  "
              f"{path.stat().st_size / 1024:.0f} KB")
    print(f"\n{len(made)} ornaments -> {ASSETS.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
