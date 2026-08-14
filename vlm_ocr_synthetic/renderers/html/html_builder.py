"""Document -> HTML string.

Kept apart from the screenshot step so the markup can be unit-tested (and
eyeballed in a browser) without launching anything.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ...schemas.document import Document, DocumentBlock

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "document.html.j2"

BLOCK_ID_ATTR = "data-block-id"
CELL_ID_ATTR = "data-cell-id"


def block_id(index: int) -> str:
    return f"block-{index}"


def cell_id(block_index: int, row_index: int, cell_index: int) -> str:
    return f"cell-{block_index}-{row_index}-{cell_index}"


def _absolute_style(block: DocumentBlock) -> str:
    if block.bbox is None:
        return ""
    bbox = block.bbox
    return (
        f"left:{bbox.x1}px;top:{bbox.y1}px;"
        f"width:{bbox.width}px;min-height:{bbox.height}px;"
    )


def _prepare_blocks(document: Document, layout: str) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []

    for index, block in enumerate(document.blocks):
        entry: dict[str, Any] = {
            "id": block_id(index),
            "block_type": block.block_type,
            "content": block.content or "",
            "style": _absolute_style(block) if layout == "absolute" else "",
            "table": None,
        }

        if block.table is not None:
            entry["table"] = {
                "rows": [
                    {
                        "cells": [
                            {
                                "id": cell_id(index, row_index, cell_index),
                                "tag": "th" if cell.is_header else "td",
                                "content": cell.content,
                                "rowspan": cell.rowspan,
                                "colspan": cell.colspan,
                            }
                            for cell_index, cell in enumerate(row.cells)
                        ]
                    }
                    for row_index, row in enumerate(block.table.rows)
                ]
            }

        prepared.append(entry)

    return prepared


def build_html(document: Document, config) -> str:
    """Render the jinja2 template for ``document`` using ``HtmlConfig``."""
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "j2"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(TEMPLATE_NAME)

    page_width, page_height = config.page_size(document)
    return template.render(
        page_width=page_width,
        page_height=page_height,
        layout=config.layout,
        style=config.style_context(),
        blocks=_prepare_blocks(document, config.layout),
    )
