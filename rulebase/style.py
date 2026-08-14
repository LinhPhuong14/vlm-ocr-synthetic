"""Turning a recipe's visual and colour attributes into concrete values.

Shared by all three renderers. Without it, each backend re-derives "what colour
is this ink" from the same two attributes and they drift: the glyph renderer
faded ink by `visual.ink_gray` while the two HTML renderers ignored it, so the
same recipe produced a faint receipt in one and a crisp one in the others --
and the comparison between renderers silently became a comparison between an
attribute being honoured and being dropped.
"""

from __future__ import annotations

import random


def fade(colour, gray: int) -> tuple[int, int, int]:
    """Pull `colour` towards white by `gray` (0 = full strength, 255 = paper).

    Towards white rather than multiplied: multiplying turns blue ink grey as it
    fades, where a real half-empty cartridge still prints blue, just paler.
    """
    return tuple(int(c + (255 - c) * (gray / 255.0)) for c in colour)  # type: ignore[return-value]


def inks(recipe, rng: random.Random | None = None) -> dict:
    """The ink, the accent ink, and the tint, for one page.

    `rng` is optional: the HTML backends want the middle of the range so a
    recipe maps to one deterministic page, while the glyph renderer draws from
    it. Passing None takes the midpoint.
    """
    visual = recipe.choices["visual"].params
    colour = recipe.choices["color"].params

    low, high = visual.get("ink_gray", [0, 60])
    gray = rng.randint(int(low), int(high)) if rng else (int(low) + int(high)) // 2

    base = colour.get("ink", [26, 26, 26])
    accent = colour.get("accent", base)
    return {
        "gray": gray,
        # The accent line -- shop name, title -- is what the printer puts most
        # ink into, so it fades at half the rate of the body.
        "ink": fade(base, gray),
        "accent": fade(accent, gray // 2),
        "tint": tuple(int(v) for v in colour.get("tint", [255, 255, 255])),
        "tint_alpha": float(colour.get("tint_alpha", 0.0)),
    }


def padding(recipe, grid, rng: random.Random | None = None) -> dict:
    """Blank paper around the content, in line-heights and in columns.

    Shared for the same reason `inks` is: this used to be three hardcoded
    numbers, one per renderer, and they disagreed -- the glyph backend drew its
    top margin from `line_h * uniform(0.6, 1.8)` while the two HTML backends
    used `line_px * (0.6 + tallest)`. The same recipe therefore sat the shop
    name at a different height on the sheet in each renderer, and sometimes
    hard against the top edge.

    Top and bottom are asymmetric on purpose: a till leaves a longer lead-in
    above the print than tail below it, because the paper has to clear the cut
    bar before the head starts printing.

    `rng` is optional; without it the midpoint is taken, which is what the two
    HTML backends want so a recipe maps to one deterministic page.
    """
    visual = recipe.choices["visual"].params

    def draw(key: str, default: list[float]) -> float:
        low, high = visual.get(key, default)
        return rng.uniform(low, high) if rng else (float(low) + float(high)) / 2.0

    top = draw("padding_top", [1.6, 2.6])
    bottom = draw("padding_bottom", [1.2, 2.2])
    columns = draw("margin", [0.04, 0.10]) * grid.ncols

    # The shop name and the title are set larger than the body, and a cell at
    # 1.7em overflows its line box upwards. Whatever the rules asked for, the
    # top padding has to clear that or the header is clipped by the edge of the
    # image -- which is exactly what a fixed number cannot guarantee, because
    # how large the header is set is itself sampled per bố cục.
    tallest = max([cell.scale for cell in grid.cells] + [1.0])
    top = max(top, tallest + 0.5)

    return {"top": top, "bottom": bottom, "columns": columns, "tallest": tallest}


def hex_colour(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


__all__ = ["fade", "hex_colour", "inks", "padding"]
