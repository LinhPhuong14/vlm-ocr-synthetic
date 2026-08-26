"""Document degradations: DocCreator's models, and Augraphy's, in Python.

`DocCreator <https://github.com/DocCreator/DocCreator>`_ (Journet,
Mansencal, Kieu et al., LaBRI Bordeaux) is a C++/Qt application whose
degradation models are the strongest part: they were designed against real
degraded manuscripts, not invented to look plausible. The C++ needs Qt,
OpenGL and a build, which does not fit a Python generation pipeline, so the
models are ported here and applied to whatever a generator produced --
synthdog receipts, genalog pages, anything else.

`Augraphy <https://github.com/sparkfish/augraphy>`_ is the other source, and
twelve of its models are ported the same way: the marks a copier, a printer or
a person leaves. Its own three-phase pipeline (`ink -> paper -> post`) is the
same idea as `paper_texture` running first here.

Each module names the file it came from and what the model is doing, so a
change can be checked against the original.

    from degradation import apply_chain, DEGRADATIONS

    aged = apply_chain(image, [("shadow_binding", {}), ("ink_degradation", {"level": 6})])

**`by_box` is the one entry that is not a model.** It wraps any other name and
runs it over a few of the page's text boxes instead of over the whole sheet --
which is what ink on a real page does. It needs the boxes, so it is the only
model `apply_one` hands them to:

    aged = apply_chain(image, [
        ("by_box", {"effect": "markup", "params": {"style": "highlight"},
                    "select": {"policy": "run", "fraction": 0.08}}),
    ], regions=boxes)
"""

from __future__ import annotations

import random
from typing import Any, Callable, Iterable

import numpy as np

from .bad_photocopy import bad_photocopy
from .bleed_through import bleed_through
from .blur_zones import blur, blur_zones
from .capture import halftone_screen, jpeg_blocks, scan_banding
from .channel import color_shift, glitch_effect
from .dirty_drum import dirty_drum
from .dirty_rollers import dirty_rollers
from .holes import holes
from .ink_degradation import InkDegradationConfig, ink_degradation, seed_mix
from .marks import markup, scribbles
from .printing import dot_matrix, hollow, letterpress
from .regions import boxes_from_ink, by_box, region_mask, select_regions
from .shadow_binding import shadow_binding
from .tessellation import delaunay_tessellation, voronoi_tessellation
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

# name -> (function, does it take an rng?, does it take the page's boxes?)
#
# The third flag is true for exactly one entry. Every model takes an image and
# returns an image of the same shape; `by_box` is the wrapper that decides
# WHERE a model gets to act, so it is the only one that needs to know where the
# text is. Keeping that in one place is what stops twelve models each growing
# their own idea of a region.
DEGRADATIONS: dict[str, tuple[Callable[..., np.ndarray], bool, bool]] = {
    "shadow_binding": (shadow_binding, False, False),
    "bleed_through": (bleed_through, False, False),
    "blur": (blur, False, False),
    "blur_zones": (blur_zones, True, False),
    "ink_degradation": (ink_degradation, True, False),
    "holes": (holes, True, False),
    # the texture models
    "paper_texture": (paper_texture, True, False),
    "paper_overlay": (paper_overlay, True, False),
    "pattern_overlay": (pattern_overlay, True, False),
    "gradient_domain": (gradient_domain, True, False),
    "phantom_character": (phantom_character, True, False),
    # the capture patterns: periodic marks a device leaves on the COPY, not
    # damage to the sheet. See degradation/capture.py on why they live in
    # `augmentation` and not in `ornament`.
    "halftone_screen": (halftone_screen, True, False),
    "scan_banding": (scan_banding, True, False),
    "jpeg_blocks": (jpeg_blocks, True, False),
    # Augraphy: the three parts of the machine that made this copy. A file
    # each, and a rule-base ATTRIBUTE each -- `rules/toner.yaml`,
    # `rules/drum.yaml`, `rules/rollers.yaml` -- so a page draws them
    # independently instead of getting all three or none from one scenario.
    "bad_photocopy": (bad_photocopy, True, False),
    "dirty_drum": (dirty_drum, True, False),
    "dirty_rollers": (dirty_rollers, True, False),
    # Augraphy: how the ink was laid down, and how it failed (printing.py)
    "letterpress": (letterpress, True, False),
    "hollow": (hollow, True, False),
    "dot_matrix": (dot_matrix, True, False),
    # Augraphy: marks a PERSON added afterwards (marks.py). Both take
    # `regions`, so `by_box` runs them once per box rather than masking.
    "markup": (markup, True, False),
    "scribbles": (scribbles, True, False),
    # Augraphy: generated background patterns (tessellation.py)
    "voronoi_tessellation": (voronoi_tessellation, True, False),
    "delaunay_tessellation": (delaunay_tessellation, True, False),
    # Augraphy: colour channels out of register (channel.py). `glitch_effect`
    # is the only model here that moves pixels -- read its docstring.
    "color_shift": (color_shift, True, False),
    "glitch_effect": (glitch_effect, True, False),
    # not a model: the wrapper that puts a model on a few boxes only
    "by_box": (by_box, True, True),
}


def names() -> list[str]:
    return sorted(DEGRADATIONS)


def apply_one(
    image: np.ndarray,
    name: str,
    options: dict[str, Any] | None = None,
    rng: random.Random | None = None,
    regions=None,
) -> np.ndarray:
    try:
        function, takes_rng, takes_regions = DEGRADATIONS[name]
    except KeyError:
        raise KeyError(f"unknown degradation {name!r}; have {', '.join(names())}") from None

    options = dict(options or {})
    if takes_rng and rng is not None:
        options.setdefault("rng", rng)
    if takes_regions and regions is not None:
        options.setdefault("regions", regions)
    return function(image, **options)


def apply_chain(
    image: np.ndarray,
    chain: Iterable[tuple[str, dict[str, Any]]],
    seed: int = 0,
    regions=None,
) -> np.ndarray:
    """Apply degradations in order, sharing one seeded rng.

    Order matters and is not commutative: ink degradation before blur reads
    as worn ink that was then scanned badly, the other way round as a
    smudged scan. Shadow and holes come last -- they are properties of the
    sheet, not of the printing.

    `regions` is the page's label boxes, in any of the shapes
    `degradation.regions.normalise_boxes` reads. Only `by_box` uses them.
    """
    rng = random.Random(seed)
    out = image
    for name, options in chain:
        out = apply_one(out, name, options, rng, regions)
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
    "apply_one",
    "bad_photocopy",
    "bleed_through",
    "blur",
    "blur_zones",
    "boxes_from_ink",
    "by_box",
    "color_shift",
    "delaunay_tessellation",
    "dirty_drum",
    "dirty_rollers",
    "dot_matrix",
    "glitch_effect",
    "gradient_domain",
    "halftone_screen",
    "holes",
    "hollow",
    "ink_degradation",
    "jpeg_blocks",
    "letterpress",
    "markup",
    "names",
    "paper_overlay",
    "paper_texture",
    "pattern_overlay",
    "phantom_character",
    "region_mask",
    "scan_banding",
    "scribbles",
    "seed_mix",
    "select_regions",
    "shadow_binding",
    "voronoi_tessellation",
]
