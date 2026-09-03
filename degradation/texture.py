"""DocCreator's texture degradations.

Three of DocCreator's models work by pasting a *texture* onto the page rather
than by filtering it, and they are the ones that make a synthetic page stop
looking synthetic:

``paper_texture``
    The document is drawn onto a photograph of paper rather than onto white.
    In DocCreator this is ``Context::BackgroundContext`` -- the background
    image chosen in the generation assistant, applied before any degradation.

``gradient_domain``
    ``GradientDomainDegradation.cpp``, which implements Seuret, Chen,
    Eichenberger, Liwicki and Ingold, *Gradient-domain degradations for
    improving historical documents images layout analysis*, ICDAR 2015.
    Stain images are pasted at random positions with ``cv::seamlessClone`` in
    ``MIXED_CLONE`` mode, so the stain takes the page's own gradients at its
    edge and has no visible seam.

``phantom_character``
    ``PhantomCharacter.cpp``: leftover ink from a worn press, pasted against
    the left or right flank of a character, sized from that character's own
    bounding box.

DocCreator ships the textures as image files (``data/Image/stainImages``,
``data/Image/phantomPatterns``). Those are LGPL data and are not vendored
here; the patterns are synthesised instead -- same placement and blending
logic, textures generated from a seed. Point ``stains_dir`` or ``patterns``
at real scans when you have them and they are used in preference.
"""

from __future__ import annotations

import random
from pathlib import Path

import cv2
import numpy as np

# Shared with the generators: `rules/visual.yaml` names a file in here, and
# all three renderers composite onto the same sheet as a result.
TEXTURE_ROOT = Path(__file__).resolve().parent.parent / "textures"
PAPER_DIR = TEXTURE_ROOT / "paper"
STAIN_DIR = TEXTURE_ROOT / "stain"

# SynthDoG's `resources/paper/`. These are photographs of real sheets, and they
# are used differently from `textures/paper/`: a file in PAPER_DIR is the sheet
# the text is printed ON, chosen before anything is drawn, while a file here is
# laid OVER a finished render. Same pictures could serve either purpose; the
# distinction is where in the pipeline they enter, so they get separate homes.
OVERLAY_DIR = Path(__file__).resolve().parent.parent / "augmentations" / "data" / "image"

# PhantomCharacter.cpp
SPACING_MIN = 10          # closer than this and there is no room for a pattern
SPACING_MAX = 20          # further than this and the characters are not one word
MIN_WIDTH_PRC = 10        # pattern width, as a percentage of the character's
MAX_WIDTH_PRC = 30
COEFF_MIN_HEIGHT = 0.9    # pattern height, as a fraction of the character's
COEFF_MAX_HEIGHT = 1.05
MIN_WIDTH = 3
MIN_HEIGHT = 3
FREQUENCIES = {"rare": 15, "frequent": 40, "very_frequent": 70}


# ---------------------------------------------------------------- helpers


def _as_bgr(image: np.ndarray) -> tuple[np.ndarray, bool]:
    """seamlessClone and the blends below all want 3 channels."""
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR), True
    if image.shape[2] == 4:
        return cv2.cvtColor(image, cv2.COLOR_BGRA2BGR), False
    return image, False


def _restore(out: np.ndarray, was_gray: bool) -> np.ndarray:
    return cv2.cvtColor(out, cv2.COLOR_BGR2GRAY) if was_gray else out


def _cover(texture: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    """Scale a texture to cover (width, height), cropping the overflow.

    Cover rather than stretch: paper grain has a real scale, and stretching a
    512px tile across a 2000px page turns the fibre into smears.
    """
    width, height = size
    th, tw = texture.shape[:2]
    scale = max(width / tw, height / th)
    resized = cv2.resize(
        texture, (max(int(tw * scale + 0.5), width), max(int(th * scale + 0.5), height)),
        interpolation=cv2.INTER_LINEAR,
    )
    return resized[:height, :width]


def _pick_texture(directory: Path, name: str | None, rng: random.Random) -> np.ndarray | None:
    if not directory.exists():
        return None
    files = sorted(p for p in directory.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
    if not files:
        return None
    if name and name != "auto":
        wanted = [p for p in files if p.stem == name]
        if wanted:
            files = wanted
    return cv2.imread(str(rng.choice(files)), cv2.IMREAD_COLOR)


def _value_noise(shape: tuple[int, int], cell: int, rng: random.Random) -> np.ndarray:
    """Smooth noise: a small random field scaled up. Used for grain and stains."""
    height, width = shape
    small = np.asarray(
        [[rng.random() for _ in range(max(width // cell, 2))]
         for _ in range(max(height // cell, 2))],
        dtype=np.float32,
    )
    return cv2.resize(small, (width, height), interpolation=cv2.INTER_CUBIC)


# ------------------------------------------------------------ paper texture


def _synthetic_paper(shape: tuple[int, int], rng: random.Random) -> np.ndarray:
    """A fallback sheet, for when `textures/paper/` is empty."""
    height, width = shape
    base = 0.86 + 0.10 * _value_noise((height, width), 64, rng)
    fibre = _value_noise((height, width), 3, rng)
    field = np.clip(base * (0.96 + 0.08 * fibre), 0, 1)
    return (field * 255).astype(np.uint8)[:, :, None].repeat(3, axis=2)


def _creases(shape: tuple[int, int], count: int, rng: random.Random) -> np.ndarray:
    """Fold lines: a bright ridge with a dark valley beside it.

    A crease is not a dark line. Light catches the raised side and misses the
    other, which is why a scanned fold shows as a light/dark pair -- copying
    that is what makes it read as a fold rather than as a pen stroke.
    """
    height, width = shape
    field = np.zeros((height, width), dtype=np.float32)
    for _ in range(count):
        horizontal = rng.random() < 0.6
        length = height if horizontal else width
        position = rng.uniform(0.15, 0.85) * length
        # A fold is never perfectly straight; let it wander a few pixels.
        axis = np.arange(width if horizontal else height, dtype=np.float32)
        wander = (
            rng.uniform(2, 10)
            * np.sin(axis / max(len(axis), 1) * rng.uniform(1.5, 4.0) * np.pi + rng.random() * 6.28)
        )
        centre = position + wander
        grid = np.arange(length, dtype=np.float32)[:, None] if horizontal else \
            np.arange(length, dtype=np.float32)[None, :]
        offset = (grid - (centre[None, :] if horizontal else centre[:, None]))
        sharpness = rng.uniform(1.5, 4.0)
        ridge = np.exp(-((offset / sharpness) ** 2))
        valley = np.exp(-(((offset - sharpness * 1.8) / (sharpness * 1.6)) ** 2))
        field += ridge * rng.uniform(0.5, 1.0) - valley * rng.uniform(0.3, 0.7)
    return field


def paper_texture(
    image: np.ndarray,
    paper: str | None = None,
    papers_dir: str | Path | None = None,
    alpha: float = 0.35,
    grain: float = 0.5,
    creases: int = 0,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Composite the page onto a sheet of paper.

    Multiplicative, not a cross-fade: the sheet becomes a field the finished
    render is multiplied by, so ink stays ink. A cross-fade at alpha 0.4 would
    wash 40% of the paper's brightness over every black glyph and grey the text
    out. It runs early in the chain -- before the wear, not before the text,
    which is already drawn by the time any degradation sees the image.

    `alpha` is how much of the paper's own shading comes through and only ever
    darkens (`1 - alpha*(1 - sheet)` is at most 1). `grain` and `creases`
    multiply that field by `1 ± something` and so go both ways, up to the 1.25
    clip below: a fibre or a fold catching the light is brighter than the sheet
    around it, and a paper model that could only darken would have neither.
    """
    rng = rng or random.Random(0)
    out, was_gray = _as_bgr(image)
    height, width = out.shape[:2]

    directory = Path(papers_dir) if papers_dir else PAPER_DIR
    texture = _pick_texture(directory, paper, rng)
    texture = _cover(texture, (width, height)) if texture is not None else \
        _synthetic_paper((height, width), rng)

    sheet = cv2.cvtColor(texture, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    field = 1.0 - float(alpha) * (1.0 - sheet)

    if grain > 0:
        noise = _value_noise((height, width), 2, rng) - 0.5
        field = field * (1.0 + float(grain) * 0.10 * noise)
    if creases > 0:
        field = field * (1.0 + 0.16 * _creases((height, width), int(creases), rng))

    field = np.clip(field, 0.0, 1.25)[:, :, None]
    return _restore(np.clip(out.astype(np.float32) * field, 0, 255).astype(np.uint8), was_gray)


def pattern_overlay(
    image: np.ndarray,
    pattern: str | None = None,
    patterns_dir: str | Path | None = None,
    scale: float = 0.28,
    opacity: float = 0.6,
    anchor: str = "random",
    rotate: float = 0.0,
    box: tuple[float, float, float, float] | None = None,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Đóng một hoạ tiết có kênh alpha lên trang đã dựng xong.

    Đây là cầu nối giữa thư viện `textures/ornament/` và chuỗi làm cũ. Thuộc
    tính `ornament` mô tả hoạ tiết CỐ Ý có mặt trên tờ giấy và bốc trước
    `augmentation`; hàm này là đường vào cho trường hợp ngược lại — con dấu
    đóng lên bản sao chứ không đóng lên bản gốc, chữ chìm của máy photocopy in
    đè lên tất cả.

    Alpha của file quyết định chỗ nào ăn mực; `opacity` nhân thêm vào đó. Trộn
    theo lối NHÂN chứ không phủ đè: mực dấu là mực trong, chữ nằm dưới vẫn phải
    đọc được. Phủ đè sẽ xoá mất phần chữ dưới dấu, mà nhãn dữ liệu thì vẫn khai
    là có chữ ở đó.

    Thiếu file thì không làm gì, giống `paper_overlay`: bịa ra một hoạ tiết
    thay thế sẽ giấu mất chuyện thư mục bị thiếu.
    """
    import cv2

    rng = rng or random.Random(0)
    directory = Path(patterns_dir) if patterns_dir else (
        Path(__file__).resolve().parent.parent / "textures" / "ornament")
    if not directory.is_dir():
        return image
    if pattern:
        path = directory / f"{pattern}.png"
        if not path.exists():
            return image
    else:
        choices = sorted(directory.glob("*.png"))
        if not choices:
            return image
        path = choices[rng.randrange(len(choices))]

    art = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if art is None or art.ndim != 3 or art.shape[2] != 4:
        return image                       # không có alpha thì không phải hoạ tiết

    bgr, was_gray = _as_bgr(image)
    height, width = bgr.shape[:2]
    target_w = max(int(width * float(scale)), 8)
    target_h = max(int(art.shape[0] * target_w / art.shape[1]), 8)
    if target_w >= width or target_h >= height:
        target_w = min(target_w, width - 2)
        target_h = min(target_h, height - 2)
    art = cv2.resize(art, (max(target_w, 4), max(target_h, 4)), interpolation=cv2.INTER_AREA)

    if rotate:
        angle = rng.uniform(-abs(rotate), abs(rotate))
        matrix = cv2.getRotationMatrix2D((art.shape[1] / 2, art.shape[0] / 2), angle, 1.0)
        art = cv2.warpAffine(art, matrix, (art.shape[1], art.shape[0]),
                             flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))

    art_h, art_w = art.shape[:2]
    spots = {
        "top_left": (int(width * 0.06), int(height * 0.06)),
        "top_right": (width - art_w - int(width * 0.06), int(height * 0.06)),
        "bottom_left": (int(width * 0.06), height - art_h - int(height * 0.08)),
        "bottom_right": (width - art_w - int(width * 0.08), height - art_h - int(height * 0.10)),
        "centre": ((width - art_w) // 2, (height - art_h) // 2),
    }
    if box is not None:
        # Một hình chữ nhật cụ thể trên trang: hoạ tiết đặt vào GIỮA nó.
        #
        # Đây là đường mà thuộc tính `ornament` đi vào (xem
        # `generators/html/ornament.py`): luật khai chỗ đóng dấu theo NGHĨA —
        # "khối chữ ký bên bán", "măng-sét" — còn người gọi mới biết khối ấy
        # nằm ở đâu trên trang này, vì nó vừa đo từ DOM. `scale` vẫn tính theo
        # bề rộng TRANG chứ không theo ô: một con dấu co theo khối chữ ký sẽ
        # to nhỏ khác nhau ở từng bố cục, mà luật thì viết theo tờ giấy.
        x0, y0, x1, y1 = (float(v) for v in box)
        x = int(round((x0 + x1) / 2 - art_w / 2))
        y = int(round((y0 + y1) / 2 - art_h / 2))
    elif anchor == "random":
        x, y = spots[sorted(spots)[rng.randrange(len(spots))]]
    else:
        x, y = spots.get(anchor, spots["centre"])
    x = int(np.clip(x, 0, max(width - art_w, 0)))
    y = int(np.clip(y, 0, max(height - art_h, 0)))

    # `_as_bgr` hands back the caller's own array when the page is already BGR,
    # and the assignment below writes through it. Every other model here returns
    # a new image and leaves its input alone; this one quietly did not, which
    # made `out.mean() < page.mean()` compare a page with itself — the assertion
    # in `tests/test_ornament.py` that has been red for exactly this reason.
    bgr = bgr.copy()
    patch = bgr[y:y + art_h, x:x + art_w].astype(np.float32)
    alpha = (art[..., 3:4].astype(np.float32) / 255.0) * float(np.clip(opacity, 0, 1))
    ink = art[..., :3].astype(np.float32)
    # Nhân: chỗ mực đậm thì tối đi theo màu mực, chỗ alpha bằng 0 thì y nguyên.
    blended = patch * (1.0 - alpha) + (patch * (ink / 255.0)) * alpha
    bgr[y:y + art_h, x:x + art_w] = np.clip(blended, 0, 255).astype(np.uint8)
    return _restore(bgr, was_gray)


def paper_overlay(
    image: np.ndarray,
    overlay: str | None = None,
    overlays_dir: str | Path | None = None,
    alpha: float = 0.30,
    lighten: float = 0.35,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Lay a photograph of paper OVER a finished render.

    `paper_texture` runs at the head of the chain and multiplies, so the sheet
    shows through the page without flattening a glyph. This runs at the end and
    is the other half of the effect: the fibre, the fold shadows and the
    off-white cast of a real sheet sitting on top of everything, ink included.
    A page that has been through both reads as *printed on* paper rather than
    *pasted onto* a picture of paper.

    Two blends, because paper does two things to what is under it. `alpha`
    multiplies -- fibre and shadow darken. `lighten` screens, which is what
    stops the result from just going dim: real paper scatters light back.

    The screen is **gated by the page's own brightness**, and that gate is the
    whole difficulty. A flat screen lifts the darkest pixels the most, which is
    the exact opposite of how a sheet behaves -- ink absorbs, paper scatters --
    and on faint thermal text it washed the glyphs out until Tesseract's recall
    on the mid-ageing scenario fell by nearly half. Weighting the screen by
    luminance means bare paper gets the lift and ink keeps its contrast.

    With no overlay images present this is a no-op rather than a synthetic
    fallback: the effect is meaningless without a photograph, and silently
    substituting noise would make a missing directory invisible.
    """
    rng = rng or random.Random(0)
    directory = Path(overlays_dir) if overlays_dir else OVERLAY_DIR
    texture = _pick_texture(directory, overlay, rng)
    if texture is None:
        return image

    out, was_gray = _as_bgr(image)
    height, width = out.shape[:2]
    sheet = cv2.cvtColor(_cover(texture, (width, height)), cv2.COLOR_BGR2GRAY)
    sheet = sheet.astype(np.float32)[:, :, None] / 255.0

    page = out.astype(np.float32) / 255.0
    multiplied = page * (1.0 - float(alpha) * (1.0 - sheet))
    screened = 1.0 - (1.0 - multiplied) * (1.0 - float(lighten) * sheet)

    # The gate: 1 on bare paper, 0 on ink. Squared so that mid-greys -- the
    # anti-aliased rim of a glyph -- stay closer to the ink than to the paper,
    # which is what keeps a thin stroke from dissolving into its own halo.
    luma = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY).astype(np.float32)[:, :, None] / 255.0
    gate = float(lighten) * np.clip(luma, 0.0, 1.0) ** 2

    blended = multiplied * (1.0 - gate) + screened * gate
    return _restore(np.clip(blended * 255.0, 0, 255).astype(np.uint8), was_gray)


# ------------------------------------------------------- gradient domain


def stain_patch(size: int, rng: random.Random) -> np.ndarray:
    """One synthetic stain: a damp ring with a darker rim, as tea or water leaves.

    Stands in for DocCreator's `data/Image/stainImages`. What matters for the
    Poisson blend is the stain's *gradients*, so the rim -- where the liquid
    dried and left its load -- is the part worth getting right.
    """
    radius = np.hypot(
        *np.meshgrid(np.linspace(-1, 1, size), np.linspace(-1, 1, size), indexing="xy")
    )
    edge = rng.uniform(0.55, 0.9)
    body = np.clip(1.0 - radius / edge, 0, 1) ** rng.uniform(0.5, 1.5)
    rim = np.exp(-(((radius - edge) / rng.uniform(0.05, 0.14)) ** 2))
    blotch = _value_noise((size, size), max(size // 6, 2), rng)

    density = np.clip(body * (0.35 + 0.5 * blotch) + rim * rng.uniform(0.4, 0.9), 0, 1)
    density *= np.clip(1.4 - radius, 0, 1)  # fade out well before the tile edge

    hue = np.array(rng.choice([(28, 46, 74), (34, 40, 52), (46, 62, 86)]), dtype=np.float32)
    patch = 255.0 - density[:, :, None] * hue[None, None, :]
    return np.clip(patch, 0, 255).astype(np.uint8)


def gradient_domain(
    image: np.ndarray,
    count: int = 5,
    strength: float = 0.75,
    stains_dir: str | Path | None = None,
    rotate: bool = True,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Paste stains with Poisson blending (Seuret et al. 2015, ICDAR).

    `strength` is a deviation from DocCreator: their stains are photographs
    of real damage and go on as they are, ours are synthetic and need to be
    dialled back towards the page before cloning, or every receipt comes out
    looking soaked.
    """
    rng = rng or random.Random(0)
    out, was_gray = _as_bgr(image)
    height, width = out.shape[:2]
    short = min(height, width)

    directory = Path(stains_dir) if stains_dir else STAIN_DIR
    available = (
        sorted(p for p in directory.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        if directory.exists()
        else []
    )

    for _ in range(int(count)):
        size = max(int(short * rng.uniform(0.10, 0.30)), 24)
        if available:
            stain = cv2.imread(str(rng.choice(available)), cv2.IMREAD_COLOR)
            stain = cv2.resize(stain, (size, size), interpolation=cv2.INTER_LINEAR)
        else:
            stain = stain_patch(size, rng)
        if rotate:
            turns = rng.randrange(4)
            if turns:
                stain = np.rot90(stain, turns).copy()
        if was_gray:
            stain = cv2.cvtColor(cv2.cvtColor(stain, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)

        # Pull the stain towards white so `strength` controls how wet it looks.
        stain = np.clip(
            255.0 - (255.0 - stain.astype(np.float32)) * float(strength), 0, 255
        ).astype(np.uint8)

        half = size // 2 + 1
        if width - half <= half or height - half <= half:
            continue  # page smaller than the stain: nothing sensible to do
        centre = (rng.randrange(half, width - half), rng.randrange(half, height - half))
        mask = np.full(stain.shape[:2], 255, dtype=np.uint8)
        try:
            out = cv2.seamlessClone(stain, out, mask, centre, cv2.MIXED_CLONE)
        except cv2.error:
            # seamlessClone is fussy about degenerate ROIs; skipping one stain
            # is better than failing a whole dataset run.
            continue

    return _restore(out, was_gray)


# ------------------------------------------------------ phantom characters


def phantom_pattern(width: int, height: int, rng: random.Random) -> np.ndarray:
    """One blob of leftover ink, as a grey image where 0 is solid ink.

    Stands in for DocCreator's `data/Image/phantomPatterns`: those are small
    greyscale crops of ink residue, and what they have in common is a ragged
    vertical smear that is denser at one end.
    """
    width, height = max(int(width), 1), max(int(height), 1)
    field = _value_noise((height, width), max(min(width, height) // 2, 1), rng)
    ramp = np.linspace(1.0, 0.15, height, dtype=np.float32)[:, None]
    if rng.random() < 0.5:
        ramp = ramp[::-1]
    density = np.clip(field * ramp * rng.uniform(1.2, 2.2), 0, 1)
    density[density < rng.uniform(0.25, 0.45)] = 0.0
    return ((1.0 - density) * 255).astype(np.uint8)


def phantom_character(
    image: np.ndarray,
    frequency: str = "frequent",
    patterns: str | Path | None = None,
    rng: random.Random | None = None,
) -> np.ndarray:
    """Paste ink residue against the flanks of characters.

    Follows PhantomCharacter.cpp: find the connected components, keep the ones
    whose area looks like a character, and for the chosen fraction of them
    paste a pattern to the left or right, sized from that character's own box
    and never wider than the gap to its neighbour.
    """
    rng = rng or random.Random(0)
    if frequency not in FREQUENCIES:
        raise ValueError(f"frequency must be one of {', '.join(FREQUENCIES)}")
    probability = FREQUENCIES[frequency] / 100.0

    out, was_gray = _as_bgr(image)
    grey = cv2.cvtColor(out, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(grey, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    count, _, stats, _ = cv2.connectedComponentsWithStats(binary, connectivity=8)
    if count <= 1:
        return _restore(out, was_gray)

    boxes = stats[1:, :5]
    areas = boxes[:, cv2.CC_STAT_AREA].astype(np.float32)
    if len(areas) == 0:
        return _restore(out, was_gray)

    # DocCreator keeps components whose area sits around the median; a rule
    # separates glyphs from both speckles and the ruled lines across the page.
    median = float(np.median(areas))
    keep = (areas > median * 0.25) & (areas < median * 6.0)
    boxes = boxes[keep]

    directory = Path(patterns) if patterns else None
    files = (
        sorted(p for p in directory.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png"})
        if directory and directory.exists()
        else []
    )

    height_img, width_img = out.shape[:2]
    xs = boxes[:, cv2.CC_STAT_LEFT]
    order = np.argsort(xs)

    for index in order:
        if rng.random() >= probability:
            continue
        x, y, w, h, _area = boxes[index]
        if h < MIN_HEIGHT or w < 2:
            continue

        for side in (0, 1):                     # 0 = left flank, 1 = right
            if rng.randrange(2) != 1:
                continue
            # Only where a neighbour was actually measured. Without this, a
            # component that is a whole word (which is what dense small text
            # gives) sizes its pattern from the *word* width and stamps it over
            # the glyphs next door instead of into the gap between them.
            gap = _gap_to_neighbour(boxes, index, side, y, h)
            if gap is None or gap < SPACING_MIN:
                continue
            # Residue is squeezed out sideways by a character, so it can never
            # be wider than the character is tall, whatever the box says.
            ceiling = max(int(h * 0.4), MIN_WIDTH + 1)
            min_width = max((w * MIN_WIDTH_PRC) // 100, MIN_WIDTH)
            min_width = min(min_width, ceiling - 1)
            max_width = min(gap // 2, (w * MAX_WIDTH_PRC) // 100, ceiling)
            max_width = max(max_width, min_width + 1)

            pw = rng.randrange(min_width, max_width + 1)
            ph = rng.randrange(
                max(int(h * COEFF_MIN_HEIGHT), MIN_HEIGHT),
                max(int(h * COEFF_MAX_HEIGHT), MIN_HEIGHT) + 1,
            )
            if files:
                pattern = cv2.imread(str(rng.choice(files)), cv2.IMREAD_GRAYSCALE)
                pattern = cv2.resize(pattern, (pw, ph), interpolation=cv2.INTER_LINEAR)
            else:
                pattern = phantom_pattern(pw, ph, rng)

            px = x - pw - 1 if side == 0 else x + w + 1
            py = y + rng.randrange(-1, 2)
            if px < 0 or py < 0 or px + pw > width_img or py + ph > height_img:
                continue

            # Darken only: residue never lightens the paper under it.
            region = out[py:py + ph, px:px + pw]
            stamp = pattern[:, :, None].astype(np.float32)
            out[py:py + ph, px:px + pw] = np.minimum(region.astype(np.float32), stamp).astype(
                np.uint8
            )

    return _restore(out, was_gray)


def _gap_to_neighbour(boxes, index, side, y, h) -> int | None:
    """Horizontal distance to the nearest component on the same text line.

    None when there is no neighbour close enough to count as the same word,
    which is DocCreator's SPACING_MAX rule: past that the "gap" is margin, and
    a pattern sized to it would be a blot rather than an artefact of printing.
    """
    x, _y, w = boxes[index][cv2.CC_STAT_LEFT], y, boxes[index][cv2.CC_STAT_WIDTH]
    same_line = (boxes[:, cv2.CC_STAT_TOP] < y + h) & (
        boxes[:, cv2.CC_STAT_TOP] + boxes[:, cv2.CC_STAT_HEIGHT] > y
    )
    best = None
    for other in np.nonzero(same_line)[0]:
        if other == index:
            continue
        ox, ow = boxes[other][cv2.CC_STAT_LEFT], boxes[other][cv2.CC_STAT_WIDTH]
        gap = (x - (ox + ow)) if side == 0 else (ox - (x + w))
        if 0 < gap <= SPACING_MAX and (best is None or gap < best):
            best = int(gap)
    return best


__all__ = [
    "OVERLAY_DIR",
    "PAPER_DIR",
    "STAIN_DIR",
    "TEXTURE_ROOT",
    "gradient_domain",
    "paper_overlay",
    "paper_texture",
    "phantom_character",
    "phantom_pattern",
    "stain_patch",
]
