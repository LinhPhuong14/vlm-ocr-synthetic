"""The default scenario space, assembled from the four axes.

Axis order matters: earlier axes contribute tags that later ones filter on.
``layout`` goes first because it decides what kind of paper this is, and
everything else follows from that.
"""

from __future__ import annotations

from .degradations import DEGRADATION_AXIS
from .layouts import LAYOUT_AXIS
from .space import (
    Axis,
    IncompatibleSpace,
    Scenario,
    ScenarioSpace,
    Variant,
    plan,
    realised_distribution,
    seed_for,
)
from .styles import STYLE_AXIS, Style

# Backends are an axis too: the same document through a different engine is
# a different training sample. html-absolute only makes sense for documents
# that carry bboxes, hence the requires.
BACKEND_AXIS = Axis(
    name="backend",
    variants=(
        Variant("synthdog", ("synthdog", {}), weight=3),
        Variant("html-flow", ("html", {"layout": "flow"}), weight=4),
        Variant(
            "html-absolute",
            ("html", {"layout": "absolute"}),
            weight=1,
            requires=frozenset({"pinned"}),
        ),
    ),
)

DEFAULT_SPACE = ScenarioSpace(
    axes=(LAYOUT_AXIS, BACKEND_AXIS, STYLE_AXIS, DEGRADATION_AXIS)
)


def default_space() -> ScenarioSpace:
    return DEFAULT_SPACE


__all__ = [
    "Axis",
    "BACKEND_AXIS",
    "DEFAULT_SPACE",
    "DEGRADATION_AXIS",
    "IncompatibleSpace",
    "LAYOUT_AXIS",
    "STYLE_AXIS",
    "Scenario",
    "ScenarioSpace",
    "Style",
    "Variant",
    "default_space",
    "plan",
    "realised_distribution",
    "seed_for",
]
