"""Font lookup for the synthdog backend."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional

# Reasonable defaults on Linux/macOS CI boxes; the config can override.
DEFAULT_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/Library/Fonts/Arial.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
)

DEFAULT_BOLD_FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
)


def find_font(explicit: Optional[str] = None, bold: bool = False) -> Optional[str]:
    """First existing font path, or ``None`` to fall back to PIL's bitmap font."""
    if explicit:
        if not Path(explicit).exists():
            raise FileNotFoundError(f"font not found: {explicit}")
        return explicit

    candidates = DEFAULT_BOLD_FONT_CANDIDATES if bold else DEFAULT_FONT_CANDIDATES
    for candidate in candidates:
        if Path(candidate).exists():
            return candidate
    return None


@lru_cache(maxsize=64)
def load_font(path: Optional[str], size: int):
    from PIL import ImageFont

    if path is None:
        return ImageFont.load_default()
    return ImageFont.truetype(path, size)
