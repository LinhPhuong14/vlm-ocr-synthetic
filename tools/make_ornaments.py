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

**No hand marks here.** Signatures, handwritten field values, pen underlines
and highlighter swipes were drawn and then dropped: a typeface jittered per
glyph is not handwriting, and a procedural squiggle is not a signature. Both
read as what they are the moment you put them beside a scan. Doing it properly
needs stroke data or a hand-drawn face with a licence to redistribute, not more
jitter -- see docs/hoa-tiet-de-xuat.md.

Company names, tax codes and addresses below are invented for synthetic data.
They are not real businesses.
"""

from __future__ import annotations

import io
import math
import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

REPO_ROOT = Path(__file__).resolve().parent.parent
ASSETS = REPO_ROOT / "textures" / "ornament"
CONTACT = REPO_ROOT / "samples" / "ornaments" / "contact.jpg"
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


def _fit_width(text: str, limit: float, path: str, start_px: float) -> ImageFont.FreeTypeFont:
    """Cỡ chữ lớn nhất mà dòng vẫn nằm gọn trong `limit` pixel."""
    size = start_px
    while size > start_px * 0.45:
        font = ImageFont.truetype(path, int(size))
        if font.getlength(text) <= limit:
            return font
        size *= 0.95
    return ImageFont.truetype(path, int(size))


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

    sizes = [h * 0.34, h * 0.19]
    inside = w - pad2 * 2 - w * 0.05
    y = h * 0.26
    for index, line in enumerate(lines):
        font = _fit_width(line, inside, FONT_BOLD, sizes[min(index, len(sizes) - 1)])
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


# ------------------------------------------------------- dấu: các kiểu đóng

def _ring_only(image: Image.Image, keep: float = 0.78) -> Image.Image:
    """Bỏ mực phần ruột, giữ vành ngoài -- mặt dấu vồng nên chỉ vành chạm giấy."""
    array = np.array(image).astype(np.float32)
    height, width = array.shape[:2]
    yy, xx = np.mgrid[0:height, 0:width]
    radius = np.hypot(xx - width / 2, yy - height / 2) / (min(height, width) / 2)
    # 1.0 ở vành, tắt dần vào trong; `keep` là chỗ bắt đầu tắt
    fade = np.clip((radius - keep * 0.55) / max(keep * 0.45, 1e-6), 0, 1)
    array[..., 3] *= 0.18 + 0.82 * fade
    return Image.fromarray(np.clip(array, 0, 255).astype(np.uint8), "RGBA")


def double_strike(image: Image.Image, *, seed: int) -> Image.Image:
    """Đóng hai lần: tay trượt nên bản thứ hai lệch vài milimét và mờ hơn.

    Không phải một con dấu khác -- là cùng con dấu ấy in hai lần, nên nó nhận
    ảnh vào chứ không vẽ lại từ đầu.
    """
    rng = random.Random(seed)
    pad = int(max(image.size) * 0.10)
    canvas = Image.new("RGBA", (image.width + pad, image.height + pad), (0, 0, 0, 0))
    faint = image.copy()
    faint.putalpha(faint.getchannel("A").point(lambda v: int(v * 0.45)))
    canvas.alpha_composite(faint, (rng.randint(pad // 2, pad), rng.randint(0, pad // 2)))
    canvas.alpha_composite(image, (0, rng.randint(pad // 2, pad)))
    return canvas


def edge_seal(image: Image.Image, *, keep: float = 0.42) -> Image.Image:
    """Dấu giáp lai: đóng vắt qua mép hai tờ nên mỗi tờ chỉ giữ được một phần.

    Cắt thẳng chứ không làm mờ dần: mép giấy cắt mực dứt khoát, và chính cái
    cạnh sắc ấy là dấu hiệu người đọc nhận ra đây là dấu giáp lai chứ không
    phải một con dấu đóng hụt.
    """
    width = max(int(image.width * keep), 8)
    return image.crop((image.width - width, 0, image.width, image.height))


def name_block_seal(name: str, title: str, *, seed: int, width: int = 620,
                    height: int = 200, colour=(30, 74, 148)) -> Image.Image:
    """Dấu chức danh: khung chữ nhật in tên và chức vụ người ký.

    Đóng ngay cạnh chữ ký tay, gần như mọi chứng từ doanh nghiệp Việt Nam đều
    có. Chữ ở đây là chữ IN LÊN dấu nên viết tiếng Việt.
    """
    rng = random.Random(seed)
    w, h = width * SS, height * SS
    canvas = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    ink = colour + (255,)

    pad = int(w * 0.018)
    draw.rectangle([pad, pad, w - pad, h - pad], outline=ink, width=int(h * 0.028))

    # Tên người dài ngắn khác nhau; khung dấu thì khắc sẵn. Co chữ cho vừa,
    # đúng như `_fit_arc` co chữ cho vừa vành dấu tròn.
    inside = w - pad * 2 - w * 0.06
    name_font = _fit_width(name.upper(), inside, FONT_BOLD, h * 0.27)
    title_font = _fit_width(title, inside, FONT_REG, h * 0.185)
    name_width = draw.textlength(name.upper(), font=name_font)
    draw.text((w / 2 - name_width / 2, h * 0.20), name.upper(), font=name_font, fill=ink)
    # nét kẻ ngăn tên với chức vụ, đúng lối khắc dấu tên
    draw.line([(w * 0.18, h * 0.55), (w * 0.82, h * 0.55)], fill=ink, width=int(h * 0.012))
    title_width = draw.textlength(title, font=title_font)
    draw.text((w / 2 - title_width / 2, h * 0.62), title, font=title_font, fill=ink)

    canvas = canvas.resize((width, height), Image.LANCZOS)
    canvas = _ink(canvas, rng, coverage=rng.uniform(0.82, 0.95))
    return canvas.rotate(rng.uniform(-6, 6), resample=Image.BICUBIC, expand=True)


# ----------------------------------------------------- chữ chìm và hoa văn

def diagonal_watermark(text: str, *, seed: int, width: int = 1240, height: int = 1754,
                       colour=(120, 120, 132), alpha: int = 34) -> Image.Image:
    """Chữ chìm lặp chéo khắp trang, rất nhạt, nằm dưới chữ in.

    Kích thước mặc định là một trang A4 ở 150 dpi: chữ chìm phủ CẢ TRANG chứ
    không phải một hình dán vào một chỗ, nên nó là hoạ tiết duy nhất trong bộ
    này sinh ra đúng bằng khổ trang.
    """
    rng = random.Random(seed)
    w, h = width, height
    diagonal = int(math.hypot(w, h))
    tile = Image.new("RGBA", (diagonal, diagonal), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    font = ImageFont.truetype(FONT_BOLD, int(h * 0.055))
    step_x = int(draw.textlength(text, font=font) * 1.55)
    step_y = int(font.size * 3.1)

    for row, y in enumerate(range(0, diagonal, step_y)):
        offset = (row % 2) * step_x // 2          # so le, không xếp thành cột
        for x in range(-step_x, diagonal, step_x):
            draw.text((x + offset, y), text, font=font, fill=colour + (alpha,))

    tile = tile.rotate(-rng.uniform(28, 36), resample=Image.BICUBIC)
    left, top = (diagonal - w) // 2, (diagonal - h) // 2
    return tile.crop((left, top, left + w, top + h))


def dong_son_motif(size: int, *, seed: int, colour=(47, 82, 51)) -> Image.Image:
    """Hoa văn trống đồng: mặt trời giữa, chim Lạc bay vòng, vành răng cưa.

    Dựng bằng toạ độ cực, cùng cách con dấu tròn được dựng. Chim Lạc vẽ thành
    bóng chứ không thành nét: trên mặt trống thật chúng là hình khắc đặc, và ở
    cỡ in trên tờ hoá đơn thì nét mảnh sẽ mất hết.
    """
    rng = random.Random(seed)
    side = size * SS
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    centre = side / 2
    ink = colour + (255,)

    def ring(radius: float, weight: float, opacity: int = 255) -> None:
        draw.ellipse([centre - radius, centre - radius, centre + radius, centre + radius],
                     outline=colour + (opacity,), width=max(int(side * weight), SS))

    # mặt trời giữa: nhân tròn và một vành tia nhọn
    core = side * 0.075
    draw.ellipse([centre - core, centre - core, centre + core, centre + core], fill=ink)
    rays = 14
    for index in range(rays):
        angle = index * math.tau / rays
        tip = side * 0.155
        spread = math.tau / rays * 0.30
        draw.polygon([
            (centre + tip * math.cos(angle), centre + tip * math.sin(angle)),
            (centre + core * math.cos(angle - spread), centre + core * math.sin(angle - spread)),
            (centre + core * math.cos(angle + spread), centre + core * math.sin(angle + spread)),
        ], fill=ink)

    ring(side * 0.20, 0.004)
    ring(side * 0.215, 0.004)

    # vành chim Lạc: mỏ dài, cổ vươn, đuôi xoè, bay ngược chiều kim đồng hồ
    # Bảy con, không mười: ở cỡ in trên tờ hoá đơn, mười con chạm cánh nhau và
    # cả vành biến thành một đường răng cưa -- mất hẳn con chim.
    birds, orbit = 7, side * 0.288
    for index in range(birds):
        angle = index * math.tau / birds + rng.uniform(-0.02, 0.02)
        bird = Image.new("RGBA", (int(side * 0.26), int(side * 0.15)), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bird)
        bw, bh = bird.size
        # mỏ dài thẳng, đầu có mào, thân dày, đuôi xoè thành ba nhánh
        bd.polygon([(bw * 0.02, bh * 0.40), (bw * 0.26, bh * 0.34), (bw * 0.30, bh * 0.10),
                    (bw * 0.38, bh * 0.32), (bw * 0.56, bh * 0.30), (bw * 0.72, bh * 0.44),
                    (bw * 0.98, bh * 0.46), (bw * 0.80, bh * 0.60), (bw * 0.98, bh * 0.74),
                    (bw * 0.70, bh * 0.68), (bw * 0.44, bh * 0.86), (bw * 0.30, bh * 0.60)],
                   fill=ink)
        bird = bird.rotate(-angle * 180 / math.pi - 90, resample=Image.BICUBIC, expand=True)
        canvas.alpha_composite(bird, (int(centre + orbit * math.cos(angle) - bird.width / 2),
                                      int(centre + orbit * math.sin(angle) - bird.height / 2)))

    draw = ImageDraw.Draw(canvas)
    ring(side * 0.355, 0.004)
    ring(side * 0.375, 0.006)

    # vành răng cưa ngoài cùng
    teeth = 48
    inner, outer = side * 0.395, side * 0.445
    for index in range(teeth):
        a0 = index * math.tau / teeth
        a1 = (index + 0.5) * math.tau / teeth
        a2 = (index + 1) * math.tau / teeth
        draw.polygon([(centre + inner * math.cos(a0), centre + inner * math.sin(a0)),
                      (centre + outer * math.cos(a1), centre + outer * math.sin(a1)),
                      (centre + inner * math.cos(a2), centre + inner * math.sin(a2))], fill=ink)
    ring(side * 0.465, 0.006)

    return canvas.resize((size, size), Image.LANCZOS)


# ------------------------------------------------------------ mã máy đọc

# EAN-13. Ba bảng mã bảy vạch, và bảng chẵn lẻ mà CHỮ SỐ ĐẦU quyết định -- số
# đầu không có vạch riêng, nó được mã hoá bằng cách sáu số bên trái dùng bảng
# nào. Đó là chỗ dễ làm sai nhất khi tự dựng EAN-13.
_EAN_L = ("0001101", "0011001", "0010011", "0111101", "0100011",
          "0110001", "0101111", "0111011", "0110111", "0001011")
_EAN_G = ("0100111", "0110011", "0011011", "0100001", "0011101",
          "0111001", "0000101", "0010001", "0001001", "0010111")
_EAN_R = tuple("".join("1" if bit == "0" else "0" for bit in code) for code in _EAN_L)
_EAN_PARITY = ("LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG",
               "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL")


def ean13_check_digit(twelve: str) -> str:
    """Chữ số kiểm tra: cộng có trọng số 1 và 3, xen kẽ, rồi bù cho tròn chục."""
    if len(twelve) != 12 or not twelve.isdigit():
        raise ValueError(f"EAN-13 cần đúng 12 chữ số, nhận {twelve!r}")
    total = sum(int(digit) * (3 if index % 2 else 1) for index, digit in enumerate(twelve))
    return str((10 - total % 10) % 10)


def ean13(digits: str, *, width: int = 480, height: int = 200,
          colour=(0, 0, 0)) -> Image.Image:
    """Mã vạch EAN-13 thật: đúng bảng mã, đúng chẵn lẻ, đúng số kiểm tra.

    Nhận 12 hoặc 13 chữ số. Nhận 13 thì chữ số cuối được KIỂM TRA lại chứ không
    tin: một mã vạch sai số kiểm tra là mã vạch mà máy quét từ chối, và ảnh
    huấn luyện mang nó thì đang dạy sai.
    """
    digits = digits.strip()
    if len(digits) == 12:
        digits += ean13_check_digit(digits)
    elif len(digits) == 13:
        if digits[12] != ean13_check_digit(digits[:12]):
            raise ValueError(f"{digits}: sai chữ số kiểm tra, phải là "
                             f"{ean13_check_digit(digits[:12])}")
    else:
        raise ValueError(f"EAN-13 cần 12 hoặc 13 chữ số, nhận {len(digits)}")

    parity = _EAN_PARITY[int(digits[0])]
    modules = "101"
    for index, digit in enumerate(digits[1:7]):
        modules += (_EAN_L if parity[index] == "L" else _EAN_G)[int(digit)]
    modules += "01010"
    for digit in digits[7:]:
        modules += _EAN_R[int(digit)]
    modules += "101"

    quiet = 9                                   # vùng trắng bắt buộc hai bên
    total = len(modules) + quiet * 2
    scale = max(width // total, 1)
    w, h = total * scale, height
    canvas = Image.new("RGBA", (w, h), (255, 255, 255, 255))
    draw = ImageDraw.Draw(canvas)

    # vạch bảo vệ dài hơn vạch dữ liệu, thò xuống dưới hàng số
    guards = set(range(0, 3)) | set(range(45, 50)) | set(range(92, 95))
    bar_bottom = h * 0.78
    for index, module in enumerate(modules):
        if module == "1":
            x = (quiet + index) * scale
            bottom = h * 0.92 if index in guards else bar_bottom
            draw.rectangle([x, h * 0.06, x + scale - 1, bottom], fill=colour + (255,))

    font = ImageFont.truetype(FONT_REG, int(h * 0.17))
    baseline = h * 0.79
    draw.text((scale * 0.5, baseline), digits[0], font=font, fill=colour + (255,))
    for group, start_module, first in ((digits[1:7], 3, True), (digits[7:], 50, False)):
        span = 42 * scale
        left = (quiet + start_module) * scale
        step = span / 6
        for offset, digit in enumerate(group):
            cx = left + step * (offset + 0.5)
            dw = draw.textlength(digit, font=font)
            draw.text((cx - dw / 2, baseline), digit, font=font, fill=colour + (255,))
    return canvas


def qr_code(data: str, *, size: int = 420, colour=(0, 0, 0),
            error: str = "m") -> Image.Image:
    """Mã QR thật, mã hoá `data`. Cần `segno`.

    Con dấu QR giả ở bản trước chỉ đúng chỗ và đúng sắc độ mực; cái này quét
    được. Với ảnh huấn luyện thì khác biệt ấy có nghĩa: một mã quét ra đúng mã
    hoá đơn là một nhãn nữa mà ảnh tự mang theo.
    """
    try:
        import segno
    except ImportError as error_:
        raise SystemExit(
            "qr_code cần segno: pip install -r tools/requirements.txt") from error_

    code = segno.make(data, error=error)
    scale = max(size // (code.symbol_size()[0]), 1)
    buffer = io.BytesIO()
    code.save(buffer, kind="png", scale=scale, border=2,
              dark="#%02x%02x%02x" % colour, light="#ffffff")
    buffer.seek(0)
    return Image.open(buffer).convert("RGBA")


# ------------------------------------------------------------------------ main

def contact_sheet(made: list[tuple[str, Image.Image]], *, cell: int = 300,
                  columns: int = 6) -> Image.Image:
    """Every ornament on one white page, named.

    Composited onto WHITE and not onto the checkerboard an image viewer shows
    for transparency: each of these is meant to sit on paper, and a guilloche
    that reads as a delicate lace on white reads as a solid disc on black.
    """
    pad, caption = 18, 26
    rows = (len(made) + columns - 1) // columns
    sheet = Image.new("RGB",
                      (columns * (cell + pad) + pad, rows * (cell + pad + caption) + pad),
                      "#ffffff")
    draw = ImageDraw.Draw(sheet)
    label_font = ImageFont.truetype(FONT_REG, 13)
    for index, (name, art) in enumerate(made):
        column, row = index % columns, index // columns
        x, y = pad + column * (cell + pad), pad + row * (cell + pad + caption)
        draw.rectangle([x, y, x + cell, y + cell], outline="#e0e0e6")
        thumb = art.convert("RGBA")
        thumb.thumbnail((cell - 16, cell - 16), Image.LANCZOS)
        sheet.paste(thumb, (x + (cell - thumb.width) // 2, y + (cell - thumb.height) // 2),
                    thumb)
        draw.text((x + 1, y + cell + 6), name, font=label_font, fill="#55555f")
    return sheet


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    GREEN, TEAL, VIOLET, BLUE = (47, 82, 51), (15, 76, 92), (111, 90, 168), (30, 74, 148)
    RED = (196, 30, 38)

    company = round_seal("CÔNG TY TNHH BÁN LẺ AN PHÚ VIỆT NAM", "MST 0108432911",
                         ["HÀ NỘI"], seed=23, star=True)
    hotel = round_seal("CÔNG TY TNHH KHÁCH SẠN THÁI AN", "MST 4201234567",
                       ["THÁI AN", "HOTEL"], seed=44, star=False, colour=(178, 34, 40))
    export = round_seal("CÔNG TY TNHH DỆT MAY TÂN PHÁT VINA", "ĐỒNG NAI",
                        ["TÂN PHÁT", "VINA"], seed=37, star=False, colour=BLUE)

    made: list[tuple[str, Image.Image]] = [
        # --- dấu: mực ép lên tờ giấy đã in xong
        ("seal_round_company", company),
        ("seal_round_hotel", hotel),
        ("seal_round_export", export),
        ("seal_square_paid", rectangular_seal(["ĐÃ THU TIỀN", "PAID"], seed=5)),
        ("seal_square_copy", rectangular_seal(["BẢN SAO", "COPY"], seed=9, colour=BLUE)),
        ("seal_accounting_posted", rectangular_seal(
            ["ĐÃ HẠCH TOÁN", "Ngày ...... / ...... / 20......"], seed=61, colour=BLUE)),
        ("seal_name_block", name_block_seal("Nguyễn Văn Thành", "GIÁM ĐỐC", seed=71)),
        ("seal_name_block_chief", name_block_seal(
            "Trần Thị Bích Hạnh", "KẾ TOÁN TRƯỞNG", seed=73, colour=RED)),
        # cùng con dấu ấy, đóng hỏng theo hai kiểu khác nhau
        ("seal_round_company_double", double_strike(company, seed=81)),
        ("seal_round_company_faint", _ring_only(company)),
        ("seal_edge_half", edge_seal(export)),


        # --- nét in bảo an
        ("watermark_ban_sao", diagonal_watermark("BẢN SAO", seed=141)),
        ("watermark_hoa_don_mau", diagonal_watermark(
            "HOÁ ĐƠN MẪU", seed=142, colour=(190, 120, 120), alpha=40)),

        # --- hoạ tiết thiết kế
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

        # --- hoa văn Việt
        ("motif_dong_son", dong_son_motif(700, seed=151, colour=(122, 92, 48))),
        ("motif_dong_son_teal", dong_son_motif(700, seed=152, colour=TEAL)),

        # --- mã máy đọc. Hai file này là ẢNH MẪU: nội dung thật phải dựng lại
        # từ chính con số mà `rulebase` đã bốc cho tờ giấy, nếu không ảnh và
        # nhãn sẽ nói hai chuyện khác nhau. Xem `from_receipt` trong
        # rules/ornament.yaml.
        ("barcode_ean13_sample", ean13("2607609009502")),
        ("qr_verify_sample", qr_code(
            "https://hoadondientu.gdt.gov.vn/tra-cuu?mhd=1K25TAE00006830")),
    ]

    for name, image in made:
        path = ASSETS / f"{name}.png"
        image.save(path)
        print(f"{name + '.png':30} {image.width}x{image.height}  "
              f"{path.stat().st_size / 1024:.0f} KB")
    print(f"\n{len(made)} ornaments -> {ASSETS.relative_to(REPO_ROOT)}")

    sheet = contact_sheet(made)
    CONTACT.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(CONTACT, quality=88, optimize=True)
    print(f"contact sheet   -> {CONTACT.relative_to(REPO_ROOT)}  "
          f"{CONTACT.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
