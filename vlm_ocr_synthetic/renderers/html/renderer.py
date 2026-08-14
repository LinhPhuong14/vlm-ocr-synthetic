"""HTML/CSS backend: lay the page out in a browser, screenshot it, and read
the ground-truth boxes straight off the DOM.

Two layout modes:

``flow``
    CSS decides where blocks go; the returned document gets the resulting
    boxes.  Use this when you want realistic, varied layouts.
``absolute``
    Each block is pinned to the bbox given in the input document, which
    makes html and synthdog output directly comparable.
"""

from __future__ import annotations

import io
from typing import Literal, Optional

from ...schemas.document import BBox, Document, DocumentBlock
from ...schemas.render import RenderConfig, RenderResult
from ..base import BaseRenderer
from .backends import ScreenshotEngine, get_engine_class
from .html_builder import (
    BLOCK_ID_ATTR,
    CELL_ID_ATTR,
    block_id,
    build_html,
    cell_id,
)


class HtmlConfig(RenderConfig):
    """Knobs for the browser-based backend."""

    engine: str = "playwright"
    executable_path: Optional[str] = None
    timeout_ms: int = 30_000

    layout: Literal["flow", "absolute"] = "flow"

    font_family: str = "DejaVu Sans, Liberation Sans, Arial, sans-serif"
    mono_font_family: str = "DejaVu Sans Mono, Liberation Mono, monospace"
    font_size: int = 22
    title_font_size: int = 40
    header_font_size: int = 28
    footnote_font_size: int = 18
    line_height: float = 1.35

    margin: int = 60
    block_spacing: int = 24
    cell_padding: int = 8

    page_background: str = "#faf9f5"
    text_color: str = "#19191c"
    muted_color: str = "#55555c"
    header_background: str = "#eeece5"
    table_border: str = "1px solid #78787d"

    def style_context(self) -> dict[str, object]:
        """The subset of the config the jinja2 template interpolates."""
        keys = (
            "font_family",
            "mono_font_family",
            "font_size",
            "title_font_size",
            "header_font_size",
            "footnote_font_size",
            "line_height",
            "margin",
            "block_spacing",
            "cell_padding",
            "page_background",
            "text_color",
            "muted_color",
            "header_background",
            "table_border",
        )
        return {key: getattr(self, key) for key in keys}


class HtmlRenderer(BaseRenderer):
    name = "html"
    config_model = HtmlConfig

    config: HtmlConfig

    def __init__(self, config=None, engine: Optional[ScreenshotEngine] = None):
        super().__init__(config)
        self._engine = engine

    @classmethod
    def check_available(cls, engine_name: str = "playwright") -> Optional[str]:
        try:
            import jinja2  # noqa: F401
        except ImportError:
            return "jinja2 is not installed (pip install '.[html]')"
        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            return "Pillow is not installed (pip install '.[html]')"
        try:
            engine_cls = get_engine_class(engine_name)
        except KeyError as exc:
            return str(exc)
        return engine_cls.check_available()

    def _get_engine(self) -> ScreenshotEngine:
        if self._engine is None:
            engine_cls = get_engine_class(self.config.engine)
            self._engine = engine_cls(
                executable_path=self.config.executable_path,
                timeout_ms=self.config.timeout_ms,
            )
        return self._engine

    def build_html(self, document: Document) -> str:
        """Expose the intermediate markup (handy for debugging and tests)."""
        return build_html(document, self.config)

    def render(self, document: Document) -> RenderResult:
        reason = self.check_available(self.config.engine)
        if reason is not None:
            from ..base import RendererUnavailable

            raise RendererUnavailable(f"renderer '{self.name}' unavailable: {reason}")

        from PIL import Image

        page_width, page_height = self.config.page_size(document)
        html = self.build_html(document)

        png, boxes = self._get_engine().capture(
            html=html,
            page_width=page_width,
            page_height=page_height,
            scale=self.config.scale,
            selectors={"blocks": BLOCK_ID_ATTR, "cells": CELL_ID_ATTR},
        )

        image = Image.open(io.BytesIO(png))
        image.load()

        rendered_document = self._apply_boxes(
            document, boxes.get("blocks", {}), boxes.get("cells", {})
        )
        rendered_document.page_width = page_width
        rendered_document.page_height = page_height

        return RenderResult(
            image=image,
            document=rendered_document,
            renderer=self.name,
            metadata={
                "engine": self.config.engine,
                "layout": self.config.layout,
                "scale": self.config.scale,
                "bbox_space": "document",
            },
        )

    @staticmethod
    def _apply_boxes(
        document: Document,
        block_boxes: dict[str, dict[str, float]],
        cell_boxes: dict[str, dict[str, float]],
    ) -> Document:
        """Copy the document with DOM geometry written into every bbox."""
        blocks: list[DocumentBlock] = []

        for index, block in enumerate(document.blocks):
            raw = block_boxes.get(block_id(index))
            bbox = BBox(**raw) if raw else block.bbox
            update: dict[str, object] = {"bbox": bbox}

            if block.table is not None:
                rows = []
                for row_index, row in enumerate(block.table.rows):
                    cells = []
                    for cell_index, cell in enumerate(row.cells):
                        raw_cell = cell_boxes.get(
                            cell_id(index, row_index, cell_index)
                        )
                        cells.append(
                            cell.model_copy(
                                update={
                                    "bbox": BBox(**raw_cell) if raw_cell else cell.bbox
                                }
                            )
                        )
                    rows.append(row.model_copy(update={"cells": cells}))
                update["table"] = block.table.model_copy(
                    update={"rows": rows, "bbox": bbox}
                )

            blocks.append(block.model_copy(update=update))

        return document.model_copy(update={"blocks": blocks})
