"""Paper and degradation layer, shared by every backend.

A browser screenshot is pixel-perfect and a rasteriser is pixel-perfect;
scanned paper is neither.  This module turns a clean render into something
that looks like it came off a scanner, following the degradation model
genalog uses (blur / bleed-through / salt / pepper) plus a paper texture in
the spirit of synthdog's paper layer.

Both backends run the same code with the same config, so a synthdog page
and an html page can be compared without the paper treatment being a
confounding variable.

Everything is driven by a seeded ``random.Random`` and Pillow's C paths --
no numpy, no per-pixel Python loops -- so renders stay reproducible and
fast enough to sit in the default pipeline.
"""

from __future__ import annotations

import random
from pathlib import Path
from statistics import NormalDist
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL.Image import Image

_NORMAL = NormalDist()


class PaperConfig(BaseModel):
    """How much the page should look like scanned paper.

    Defaults are deliberately mild: visible as texture, harmless to OCR.
    Set ``enabled: false`` to get the raw render back.
    """

    model_config = {"extra": "forbid"}

    enabled: bool = True

    # Base sheet.
    color: tuple[int, int, int] = (250, 249, 245)
    grain: float = 4.0  # gaussian paper grain, in grey levels
    vignette: float = 0.0  # 0..1, darkening towards the corners

    # Folds: creases from a sheet that was folded before it was scanned,
    # the thing synthdog gets from its photographed paper resources.
    # fold_rows=2 is a letter tri-fold; fold_rows=1 + fold_columns=1 is a
    # quarter fold. fold_strength gates the whole effect.
    fold_rows: int = 0
    fold_columns: int = 0
    fold_strength: float = 0.0  # 0..1
    fold_softness: float = 4.0  # blur radius of the crease shading, px
    fold_jitter: float = 0.02  # crease offset, as a fraction of the page

    # A photographed sheet, the way synthdog composites resources/paper/*.
    # Path to an image, or to a directory to pick one from (seeded).
    texture: Optional[str] = None
    texture_strength: float = 1.0  # 0..1, blended towards a plain sheet

    # genalog-style degradations.
    blur: float = 0.0  # gaussian radius: scanner that cannot focus
    bleed_through: float = 0.0  # 0..1, ink seeping from the reverse side
    salt: float = 0.0  # fraction of pixels lightened (faded ink)
    pepper: float = 0.0  # fraction of pixels darkened (scanner specks)

    def is_noop(self) -> bool:
        """True only when applying this config would change nothing.

        A white sheet with every effect at zero is a no-op; a tinted sheet
        is not, even with no grain -- the colour still lands on the page.
        """
        if not self.enabled:
            return True
        if tuple(self.color) != (255, 255, 255):
            return False
        return not (
            self.grain
            or self.vignette
            or self.blur
            or self.bleed_through
            or self.salt
            or self.pepper
            or self.texture
            or self.has_folds()
        )

    def has_folds(self) -> bool:
        return self.fold_strength > 0 and bool(self.fold_rows or self.fold_columns)


def _uniform_noise(size: tuple[int, int], rng: random.Random) -> "Image":
    """A full-size plane of uniform noise, generated at C speed."""
    from PIL import Image

    width, height = size
    return Image.frombytes("L", size, rng.randbytes(width * height))


def _gaussian_lut(sigma: float) -> list[int]:
    """Map uniform bytes to gaussian grey levels centred on 128.

    A 256-entry lookup table costs nothing and keeps the noise seeded,
    unlike Pillow's own ``Image.effect_noise``.
    """
    lut = []
    for value in range(256):
        quantile = (value + 0.5) / 256
        level = 128 + sigma * _NORMAL.inv_cdf(quantile)
        lut.append(max(0, min(255, int(round(level)))))
    return lut


def paper_texture(
    size: tuple[int, int],
    config: PaperConfig,
    rng: random.Random,
) -> "Image":
    """The sheet the document is printed on: base colour plus grain."""
    from PIL import Image

    from PIL import ImageChops

    sheet = Image.new("RGB", size, config.color)

    if config.texture:
        # Multiply so the photograph's creases and shadows darken the tint
        # rather than replacing it.
        texture = load_texture(config.texture, size, config.texture_strength, rng)
        sheet = ImageChops.multiply(sheet, texture.convert("RGB"))

    if config.grain > 0:
        grain = _uniform_noise(size, rng).point(_gaussian_lut(config.grain))
        # add(a, b, scale, offset) == (a + b) / scale + offset; 128 neutral.
        sheet = ImageChops.add(sheet, grain.convert("RGB"), scale=1.0, offset=-128)

    return sheet


# --------------------------------------------------------------- folds

TEXTURE_SUFFIXES = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def crease_positions(count: int, jitter: float, rng: random.Random) -> list[float]:
    """Evenly spaced creases as fractions of the side, nudged by jitter.

    ``count=2`` gives thirds -- a letter tri-fold; ``count=1`` gives a
    single fold down the middle.
    """
    positions = []
    for index in range(1, count + 1):
        centre = index / (count + 1)
        offset = rng.uniform(-jitter, jitter) if jitter > 0 else 0.0
        positions.append(min(0.98, max(0.02, centre + offset)))
    return positions


def _panel_shading(
    length: int,
    breadth: int,
    boundaries: list[float],
    amplitude: float,
    horizontal: bool,
) -> "Image":
    """Each panel between creases catches the light differently.

    A folded sheet never lies flat, so panels alternate between leaning
    towards and away from the light. Built from Pillow's linear gradient,
    which keeps this on the C path.
    """
    from PIL import Image

    size = (breadth, length) if horizontal else (length, breadth)
    shading = Image.new("L", size, 128)

    edges = [0.0, *boundaries, 1.0]
    for index in range(len(edges) - 1):
        start = int(round(edges[index] * length))
        end = int(round(edges[index + 1] * length))
        if end - start < 2:
            continue

        panel_size = (breadth, end - start) if horizontal else (end - start, breadth)
        gradient = Image.linear_gradient("L")
        if not horizontal:
            gradient = gradient.transpose(Image.Transpose.ROTATE_90)
        if index % 2:  # alternate the lean, like an accordion
            gradient = gradient.transpose(
                Image.Transpose.FLIP_TOP_BOTTOM
                if horizontal
                else Image.Transpose.FLIP_LEFT_RIGHT
            )

        gradient = gradient.resize(panel_size, Image.Resampling.BILINEAR).point(
            lambda value: int(round(128 + (value - 128) * amplitude / 128))
        )
        shading.paste(gradient, (0, start) if horizontal else (start, 0))

    return shading


def fold_shading(
    size: tuple[int, int],
    config: PaperConfig,
    rng: random.Random,
) -> "Image":
    """A 128-neutral map: panel shading plus a valley and ridge per crease."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

    width, height = size
    strength = max(0.0, min(config.fold_strength, 1.0))
    amplitude = 24 * strength

    rows = crease_positions(config.fold_rows, config.fold_jitter, rng)
    columns = crease_positions(config.fold_columns, config.fold_jitter, rng)

    shading = Image.new("L", size, 128)
    if rows:
        shading = ImageChops.add(
            shading,
            _panel_shading(height, width, rows, amplitude, horizontal=True),
            scale=1.0,
            offset=-128,
        )
    if columns:
        shading = ImageChops.add(
            shading,
            _panel_shading(width, height, columns, amplitude, horizontal=False),
            scale=1.0,
            offset=-128,
        )

    # The crease itself: a dark valley with a lighter ridge beside it.
    valley = Image.new("L", size, 0)
    ridge = Image.new("L", size, 0)
    valley_draw, ridge_draw = ImageDraw.Draw(valley), ImageDraw.Draw(ridge)
    line_width = max(2, int(round(min(width, height) / 300)))

    def crease_width() -> int:
        # No two creases are pressed equally hard.
        return max(1, int(round(line_width * rng.uniform(0.7, 1.4))))

    for fraction in rows:
        y = fraction * height
        thickness = crease_width()
        valley_draw.line([(0, y), (width, y)], fill=255, width=thickness)
        ridge_draw.line(
            [(0, y - 2 * thickness), (width, y - 2 * thickness)],
            fill=255,
            width=thickness,
        )
    for fraction in columns:
        x = fraction * width
        thickness = crease_width()
        valley_draw.line([(x, 0), (x, height)], fill=255, width=thickness)
        ridge_draw.line(
            [(x - 2 * thickness, 0), (x - 2 * thickness, height)],
            fill=255,
            width=thickness,
        )

    # Blur spreads the line and drops its peak; autocontrast puts the peak
    # back so fold_strength means the same thing at any softness.
    softness = max(0.5, config.fold_softness)
    valley = ImageOps.autocontrast(
        valley.filter(ImageFilter.GaussianBlur(softness))
    ).point(lambda value: int(value * 0.75 * strength))
    ridge = ImageOps.autocontrast(
        ridge.filter(ImageFilter.GaussianBlur(softness * 0.6))
    ).point(lambda value: int(value * 0.45 * strength))

    shading = ImageChops.subtract(shading, valley)
    return ImageChops.add(shading, ridge)


def load_texture(
    source: str,
    size: tuple[int, int],
    strength: float,
    rng: random.Random,
) -> "Image":
    """A photographed sheet, resized to the page.

    ``source`` is an image or a directory of them -- point it at a synthdog
    ``resources/paper`` checkout and the pages get the same real creases and
    shadows those images carry. The picture is desaturated and pulled
    towards neutral by ``strength``, so it tints the sheet instead of
    replacing it.
    """
    from PIL import Image

    path = Path(source)
    if path.is_dir():
        candidates = sorted(
            child
            for child in path.iterdir()
            if child.suffix.lower() in TEXTURE_SUFFIXES
        )
        if not candidates:
            raise FileNotFoundError(f"no texture images in {path}")
        path = candidates[rng.randrange(len(candidates))]
    elif not path.exists():
        raise FileNotFoundError(f"texture not found: {path}")

    with Image.open(path) as handle:
        texture = handle.convert("L").resize(size, Image.Resampling.BILINEAR)

    blend = max(0.0, min(strength, 1.0))
    return texture.point(lambda value: int(round(255 - (255 - value) * blend)))


def _bleed_through(image: "Image", alpha: float) -> "Image":
    """Ink from the back of the sheet, mirrored and faint (genalog)."""
    from PIL import Image, ImageChops, ImageFilter

    reverse = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    reverse = reverse.filter(ImageFilter.GaussianBlur(radius=1.5))
    # Fade it towards white so multiplying only ever darkens a little.
    faded = Image.blend(Image.new("RGB", image.size, (255, 255, 255)), reverse, alpha)
    return ImageChops.multiply(image, faded)


def _salt_and_pepper(
    image: "Image",
    config: PaperConfig,
    rng: random.Random,
) -> "Image":
    """Random light/dark specks, thresholded out of a uniform plane."""
    from PIL import Image, ImageChops

    result = image

    if config.salt > 0:
        threshold = 255 - max(1, int(round(255 * min(config.salt, 1.0))))
        mask = _uniform_noise(image.size, rng).point(
            lambda value: 255 if value > threshold else 0
        )
        result = ImageChops.lighter(result, mask.convert("RGB"))

    if config.pepper > 0:
        threshold = max(1, int(round(255 * min(config.pepper, 1.0))))
        mask = _uniform_noise(image.size, rng).point(
            lambda value: 0 if value < threshold else 255
        )
        result = ImageChops.darker(result, mask.convert("RGB"))

    return result


def _vignette(image: "Image", strength: float) -> "Image":
    """Corner darkening, built from Pillow's radial gradient."""
    from PIL import Image, ImageChops

    gradient = Image.radial_gradient("L").resize(image.size, Image.Resampling.BILINEAR)
    # radial_gradient is black at the centre; invert so corners darken.
    falloff = gradient.point(
        lambda value: 255 - int(round(value * max(0.0, min(strength, 1.0))))
    )
    return ImageChops.multiply(image, falloff.convert("RGB"))


def apply_paper(
    image: "Image",
    config: PaperConfig,
    rng: random.Random,
) -> "Image":
    """Composite ``image`` onto textured paper and degrade it.

    The render is multiplied onto the sheet, so dark ink stays dark while
    the background picks up the paper colour and grain -- the same trick
    synthtiger uses, without needing pygame surfaces.
    """
    from PIL import ImageChops, ImageFilter

    if config.is_noop():
        return image

    if image.mode != "RGB":
        image = image.convert("RGB")

    result = ImageChops.multiply(image, paper_texture(image.size, config, rng))

    if config.has_folds():
        # Creases shade the whole page, ink included.
        result = ImageChops.add(
            result,
            fold_shading(image.size, config, rng).convert("RGB"),
            scale=1.0,
            offset=-128,
        )

    if config.bleed_through > 0:
        result = _bleed_through(result, min(config.bleed_through, 1.0))

    if config.salt > 0 or config.pepper > 0:
        result = _salt_and_pepper(result, config, rng)

    if config.blur > 0:
        result = result.filter(ImageFilter.GaussianBlur(radius=config.blur))

    if config.vignette > 0:
        result = _vignette(result, config.vignette)

    return result
