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
from statistics import NormalDist
from typing import TYPE_CHECKING

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
        )


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

    sheet = Image.new("RGB", size, config.color)
    if config.grain <= 0:
        return sheet

    grain = _uniform_noise(size, rng).point(_gaussian_lut(config.grain))
    from PIL import ImageChops

    # add(a, b, scale, offset) == (a + b) / scale + offset; 128 is neutral.
    return ImageChops.add(sheet, grain.convert("RGB"), scale=1.0, offset=-128)


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

    if config.bleed_through > 0:
        result = _bleed_through(result, min(config.bleed_through, 1.0))

    if config.salt > 0 or config.pepper > 0:
        result = _salt_and_pepper(result, config, rng)

    if config.blur > 0:
        result = result.filter(ImageFilter.GaussianBlur(radius=config.blur))

    if config.vignette > 0:
        result = _vignette(result, config.vignette)

    return result
