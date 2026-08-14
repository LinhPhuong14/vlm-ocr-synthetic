"""Degradation axis: what happened to the page after it was printed.

Each variant is a :class:`PaperConfig`, applied by the paper stage after the
structure is rendered. Because that stage is separate, one structural render
can be aged several ways for almost nothing -- see ``pipeline.py``.

Point ``texture`` at real paper photographs (synthdog's ``resources/paper``,
your own scans) to add a resource-backed variant; see the README.
"""

from __future__ import annotations

from ..renderers.paper import PaperConfig
from .space import Axis, Variant

THERMAL = frozenset({"thermal"})
A4 = frozenset({"a4"})

DEGRADATIONS: tuple[Variant, ...] = (
    Variant(
        "clean",
        PaperConfig(grain=2.0),
        weight=3,
    ),
    Variant(
        "light_scan",
        PaperConfig(grain=5.0, blur=0.3, vignette=0.12),
        weight=5,
    ),
    Variant(
        "office_copier",
        PaperConfig(
            color=(246, 245, 240), grain=7.0, blur=0.45, pepper=0.0012, vignette=0.2
        ),
        weight=4,
    ),
    Variant(
        "photocopy_dark",
        PaperConfig(
            color=(232, 230, 224), grain=9.0, blur=0.5, pepper=0.003, vignette=0.35
        ),
        weight=2,
    ),
    Variant(
        "sun_faded",
        PaperConfig(color=(250, 246, 228), grain=4.0, salt=0.004, blur=0.25),
        weight=2,
    ),
    Variant(
        "bleed_back",
        PaperConfig(grain=5.0, bleed_through=0.16, blur=0.3),
        weight=2,
    ),
    # --- folded -----------------------------------------------------------
    Variant(
        "folded_once",
        PaperConfig(grain=5.0, fold_rows=1, fold_strength=0.45, fold_softness=4.0),
        weight=3,
    ),
    Variant(
        "pocket_worn",
        PaperConfig(
            color=(245, 243, 236),
            grain=7.0,
            fold_rows=1,
            fold_strength=0.7,
            fold_softness=3.0,
            pepper=0.0015,
            blur=0.35,
            vignette=0.22,
        ),
        weight=2,
        requires=THERMAL,
    ),
    Variant(
        "folded_quarter",
        PaperConfig(
            color=(248, 246, 240),
            grain=5.0,
            fold_rows=1,
            fold_columns=1,
            fold_strength=0.6,
            fold_softness=5.0,
            blur=0.3,
            vignette=0.2,
        ),
        weight=2,
        requires=A4,
    ),
    Variant(
        "trifold_mailed",
        PaperConfig(
            color=(246, 243, 232),
            grain=6.0,
            fold_rows=2,
            fold_strength=0.5,
            fold_softness=6.0,
            bleed_through=0.1,
            pepper=0.001,
            vignette=0.25,
        ),
        weight=2,
        requires=A4,
    ),
)

DEGRADATION_AXIS = Axis(name="degradation", variants=DEGRADATIONS)
