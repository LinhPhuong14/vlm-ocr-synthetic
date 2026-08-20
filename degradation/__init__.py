"""DocCreator's document degradations, in Python.

`DocCreator <https://github.com/DocCreator/DocCreator>`_ (Journet,
Mansencal, Kieu et al., LaBRI Bordeaux) is a C++/Qt application whose
degradation models are the strongest part: they were designed against real
degraded manuscripts, not invented to look plausible. The C++ needs Qt,
OpenGL and a build, which does not fit a Python generation pipeline, so the
models are ported here and applied to whatever a generator produced --
synthdog receipts, genalog pages, anything else.

Each module names the DocCreator file it came from and what the model is
doing, so a change can be checked against the original.

    from degradation import apply_chain, DEGRADATIONS

    aged = apply_chain(image, [("shadow_binding", {}), ("ink_degradation", {"level": 6})])
"""

from __future__ import annotations

import random
from typing import Any, Callable, Iterable

import numpy as np

from .bleed_through import bleed_through
from .blur_zones import blur, blur_zones
from .capture import halftone_screen, jpeg_blocks, scan_banding
from .holes import holes
from .ink_degradation import InkDegradationConfig, ink_degradation, seed_mix
from .shadow_binding import shadow_binding
from .texture import (
    OVERLAY_DIR,
    PAPER_DIR,
    STAIN_DIR,
    TEXTURE_ROOT,
    gradient_domain,
    paper_overlay,
    paper_texture,
    pattern_overlay,
    phantom_character,
)

# name -> (function, does it take an rng?)
DEGRADATIONS: dict[str, tuple[Callable[..., np.ndarray], bool]] = {
    "shadow_binding": (shadow_binding, False),
    "bleed_through": (bleed_through, False),
    "blur": (blur, False),
    "blur_zones": (blur_zones, True),
    "ink_degradation": (ink_degradation, True),
    "holes": (holes, True),
    # the texture models
    "paper_texture": (paper_texture, True),
    "paper_overlay": (paper_overlay, True),
    "pattern_overlay": (pattern_overlay, True),
    "gradient_domain": (gradient_domain, True),
    "phantom_character": (phantom_character, True),
    # the capture patterns: periodic marks a device leaves on the COPY, not
    # damage to the sheet. See degradation/capture.py on why they live in
    # `augmentation` and not in `ornament`.
    "halftone_screen": (halftone_screen, True),
    "scan_banding": (scan_banding, True),
    "jpeg_blocks": (jpeg_blocks, True),
}


def names() -> list[str]:
    return sorted(DEGRADATIONS)


def apply_one(
    image: np.ndarray,
    name: str,
    options: dict[str, Any] | None = None,
    rng: random.Random | None = None,
) -> np.ndarray:
    try:
        function, takes_rng = DEGRADATIONS[name]
    except KeyError:
        raise KeyError(f"unknown degradation {name!r}; have {', '.join(names())}") from None

    options = dict(options or {})
    if takes_rng and rng is not None:
        options.setdefault("rng", rng)
    return function(image, **options)


def apply_chain(
    image: np.ndarray,
    chain: Iterable[tuple[str, dict[str, Any]]],
    seed: int = 0,
) -> np.ndarray:
    """Apply degradations in order, sharing one seeded rng.

    Order matters and is not commutative: ink degradation before blur reads
    as worn ink that was then scanned badly, the other way round as a
    smudged scan. Shadow and holes come last -- they are properties of the
    sheet, not of the printing.
    """
    rng = random.Random(seed)
    out = image
    for name, options in chain:
        out = apply_one(out, name, options, rng)
    return out


# A chain that reads like a page which was printed on real paper, aged, then
# scanned. The paper goes on first because everything after it is damage to a
# sheet that already exists.
DEFAULT_CHAIN: list[tuple[str, dict[str, Any]]] = [
    ("paper_texture", {"alpha": 0.35, "grain": 0.5}),
    ("ink_degradation", {"level": 5}),
    ("bleed_through", {"intensity": 0.55, "nb_iter": 6}),
    ("blur_zones", {"radius": 1.8, "zones": 3, "coverage": 0.2}),
    ("shadow_binding", {"border": "left", "distance_ratio": 0.12, "intensity": 0.45}),
]

__all__ = [
    "DEFAULT_CHAIN",
    "DEGRADATIONS",
    "OVERLAY_DIR",
    "PAPER_DIR",
    "STAIN_DIR",
    "TEXTURE_ROOT",
    "InkDegradationConfig",
    "apply_chain",
    "halftone_screen",
    "jpeg_blocks",
    "pattern_overlay",
    "scan_banding",
    "apply_one",
    "bleed_through",
    "blur",
    "blur_zones",
    "gradient_domain",
    "holes",
    "ink_degradation",
    "names",
    "paper_overlay",
    "paper_texture",
    "phantom_character",
    "seed_mix",
    "shadow_binding",
]
