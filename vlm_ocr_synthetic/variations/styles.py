"""Style axis: how the page looks before it is aged.

A style is renderer options -- fonts, sizes, margins, borders, CSS. The two
backends take different keys, so a style carries one dict per backend and
the pipeline asks for the one it needs. Nothing here may change the ground
truth; that is the layout axis's job.

Styles use ``requires`` to stay on paper they suit: thermal styles need a
``thermal`` layout, office styles need ``a4``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .space import Axis, Variant

MONO = "DejaVu Sans Mono, Liberation Mono, monospace"
SANS = "DejaVu Sans, Liberation Sans, Arial, sans-serif"
SERIF = "DejaVu Serif, Liberation Serif, Times New Roman, serif"

MONO_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
MONO_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"
SERIF_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"

# CSS shared by every receipt style: centred shop block, bare table.
RECEIPT_CSS = """
.block-Page-Header, .block-Section-header, .block-Footnote { text-align: center; }
.block-Text:nth-of-type(-n+4) { text-align: center; }
td, th { padding: 1px 2px; white-space: pre-wrap; }
th { background: transparent; border-bottom: 1px dashed #4a4a4a; }
table:last-of-type th { border: none; padding-top: 8px; }
"""


@dataclass(frozen=True)
class Style:
    """Renderer options per backend, plus what they have in common."""

    common: dict[str, Any] = field(default_factory=dict)
    synthdog: dict[str, Any] = field(default_factory=dict)
    html: dict[str, Any] = field(default_factory=dict)

    def options_for(self, renderer: str) -> dict[str, Any]:
        specific = self.synthdog if renderer == "synthdog" else self.html
        return {**self.common, **specific}


def _thermal(
    font_size: int,
    *,
    margin: int = 34,
    line: float = 1.4,
    spacing: int = 12,
    css: str = "",
) -> Style:
    return Style(
        common={"margin": margin, "block_spacing": spacing, "cell_padding": 2},
        synthdog={
            "font_path": MONO_PATH,
            "bold_font_path": MONO_BOLD,
            "font_size": font_size,
            "section_font_size": font_size + 7,
            "footnote_font_size": font_size + 1,
            "line_spacing": line,
            "draw_table_grid": False,
            "underline_headers": False,
            "center_block_types": ["Page-Header", "Section-header", "Footnote"],
            "text_color": [20, 20, 20],
        },
        html={
            "font_family": MONO,
            "font_size": font_size,
            "header_font_size": font_size + 7,
            "footnote_font_size": font_size + 1,
            "line_height": line,
            "table_border": "none",
            "text_color": "#141414",
            "extra_css": RECEIPT_CSS + css,
        },
    )


def _office(
    font_size: int,
    family: str,
    font_path: str,
    bold_path: str,
    *,
    margin: int = 60,
    grid: bool = True,
) -> Style:
    return Style(
        common={"margin": margin, "block_spacing": 24, "cell_padding": 8},
        synthdog={
            "font_path": font_path,
            "bold_font_path": bold_path,
            "font_size": font_size,
            "title_font_size": font_size + 18,
            "section_font_size": font_size + 6,
            "draw_table_grid": grid,
        },
        html={
            "font_family": family,
            "font_size": font_size,
            "title_font_size": font_size + 18,
            "header_font_size": font_size + 6,
            "table_border": "1px solid #78787d" if grid else "none",
        },
    )


THERMAL = frozenset({"thermal"})
WIDE_THERMAL = frozenset({"wide_thermal"})  # 80mm only: too big for 58mm
A4 = frozenset({"a4"})

STYLES: tuple[Variant, ...] = (
    # --- thermal receipts -------------------------------------------------
    Variant("thermal_17", _thermal(17), weight=5, requires=THERMAL),
    Variant(
        "thermal_15_tight", _thermal(15, margin=26, spacing=8), weight=3, requires=THERMAL
    ),
    Variant(
        "thermal_19_airy",
        _thermal(19, margin=40, spacing=16),
        weight=2,
        requires=WIDE_THERMAL,
    ),
    Variant(
        "thermal_faint",
        _thermal(17, css=".block, td, th { color: #4a4a4a; }"),
        weight=2,
        requires=THERMAL,
    ),
    Variant(
        "thermal_bold_header",
        _thermal(17, css=".block-Page-Header { font-size: 30px; letter-spacing: 2px; }"),
        weight=2,
        requires=WIDE_THERMAL,
    ),
    Variant("thermal_wide_line", _thermal(17, line=1.7), weight=2, requires=THERMAL),
    Variant(
        "thermal_13_dense",
        _thermal(13, margin=22, spacing=6, line=1.25),
        weight=2,
        requires=THERMAL,
    ),
    Variant(
        "thermal_sans",
        Style(
            common={"margin": 34, "block_spacing": 12, "cell_padding": 2},
            synthdog={
                "font_size": 17,
                "draw_table_grid": False,
                "underline_headers": False,
                "center_block_types": ["Page-Header", "Section-header", "Footnote"],
            },
            html={
                "font_family": SANS,
                "font_size": 17,
                "table_border": "none",
                "extra_css": RECEIPT_CSS,
            },
        ),
        weight=2,
        requires=THERMAL,
    ),
    Variant(
        "thermal_ruled",
        _thermal(17, css="td { border-bottom: 1px dotted #9a9a9a; }"),
        weight=1,
        requires=THERMAL,
    ),
    Variant("thermal_20_large", _thermal(20, margin=30), weight=1, requires=WIDE_THERMAL),
    # --- A4 documents -----------------------------------------------------
    Variant("office_sans_22", _office(22, SANS, "", ""), weight=4, requires=A4),
    Variant(
        "office_sans_18_tight",
        _office(18, SANS, "", "", margin=44),
        weight=2,
        requires=A4,
    ),
    Variant(
        "office_serif_22",
        _office(22, SERIF, SERIF_PATH, SERIF_BOLD),
        weight=3,
        requires=A4,
    ),
    Variant(
        "office_mono_20",
        _office(20, MONO, MONO_PATH, MONO_BOLD),
        weight=1,
        requires=A4,
    ),
    Variant(
        "office_borderless",
        _office(22, SANS, "", "", grid=False),
        weight=2,
        requires=A4,
    ),
)

STYLE_AXIS = Axis(name="style", variants=STYLES)
