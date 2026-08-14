"""synthdog-style rasteriser: the document is painted directly with Pillow.

Layers follow the synthdog recipe -- a paper background, then the text /
table content on top, then a light noise pass so the page does not look
synthetic-clean.  Because we place every glyph ourselves, the ground-truth
boxes are exact by construction.
"""

from __future__ import annotations

import random
from typing import Optional

from ...schemas.document import BBox, BlockType, Document, DocumentBlock, TableBlock
from ...schemas.render import RenderConfig, RenderResult
from ..base import BaseRenderer
from ..paper import PaperConfig
from .fonts import find_font, load_font


class SynthdogConfig(RenderConfig):
    """Knobs for the Pillow-based backend."""

    font_path: Optional[str] = None
    bold_font_path: Optional[str] = None

    font_size: int = 22
    title_font_size: int = 40
    section_font_size: int = 28
    footnote_font_size: int = 18

    margin: int = 60
    line_spacing: float = 1.35
    block_spacing: int = 24
    cell_padding: int = 8

    text_color: tuple[int, int, int] = (25, 25, 28)
    rule_color: tuple[int, int, int] = (120, 120, 125)

    # The sheet and its degradations, shared with the html backend.
    paper: PaperConfig = PaperConfig()

    draw_table_grid: bool = True

    # Column widths as fractions of the table width; empty means equal
    # columns. A receipt wants a narrow STT column and a wide item one.
    table_column_widths: tuple[float, ...] = ()

    # Per-column "left" / "center" / "right"; empty means all left. Money
    # columns on an invoice read as right-aligned.
    table_column_align: tuple[str, ...] = ()

    # Rule drawn under titles and section headers (off for receipts).
    underline_headers: bool = True

    # Block types drawn centred in the content width (receipt headers,
    # thank-you footers). The html backend does this with extra_css.
    center_block_types: tuple[str, ...] = ()


class SynthdogRenderer(BaseRenderer):
    name = "synthdog"
    config_model = SynthdogConfig

    config: SynthdogConfig

    @classmethod
    def check_available(cls) -> Optional[str]:
        try:
            import PIL  # noqa: F401
        except ImportError:
            return "Pillow is not installed (pip install '.[synthdog]')"
        return None

    # ---------------------------------------------------------------- setup

    def _font_for(self, block_type: str):
        cfg = self.config
        bold = block_type in {
            BlockType.TITLE,
            BlockType.SECTION_HEADER,
            BlockType.PAGE_HEADER,
        }
        size = {
            BlockType.TITLE: cfg.title_font_size,
            BlockType.PAGE_HEADER: cfg.section_font_size,
            BlockType.SECTION_HEADER: cfg.section_font_size,
            BlockType.FOOTNOTE: cfg.footnote_font_size,
            BlockType.PAGE_FOOTER: cfg.footnote_font_size,
        }.get(block_type, cfg.font_size)

        path = find_font(
            cfg.bold_font_path if bold else cfg.font_path,
            bold=bold,
        )
        return load_font(path, int(round(size * cfg.scale)))

    # --------------------------------------------------------------- layout

    @staticmethod
    def _wrap(text: str, font, max_width: float) -> list[str]:
        """Greedy word wrap; falls back to one word per line when too narrow."""
        lines: list[str] = []
        for paragraph in text.split("\n"):
            words = paragraph.split()
            if not words:
                lines.append("")
                continue
            current = words[0]
            for word in words[1:]:
                candidate = f"{current} {word}"
                if font.getlength(candidate) <= max_width:
                    current = candidate
                else:
                    lines.append(current)
                    current = word
            lines.append(current)
        return lines

    def _line_height(self, font) -> float:
        ascent, descent = font.getmetrics()
        return (ascent + descent) * self.config.line_spacing

    # --------------------------------------------------------------- render

    def render(self, document: Document) -> RenderResult:
        self.ensure_available()
        from PIL import Image, ImageDraw

        cfg = self.config
        rng = random.Random(cfg.seed)

        page_width, page_height = cfg.page_size(document)
        px_width = int(round(page_width * cfg.scale))
        px_height = int(round(page_height * cfg.scale))

        # Draw on white; apply_paper() supplies the sheet colour and texture.
        image = Image.new("RGB", (px_width, px_height), (255, 255, 255))
        draw = ImageDraw.Draw(image)

        margin = cfg.margin * cfg.scale
        cursor_y = margin
        rendered_blocks: list[DocumentBlock] = []

        for block in document.blocks:
            if block.table is not None:
                rendered, cursor_y = self._draw_table(
                    draw, block, cursor_y, px_width, margin
                )
            else:
                rendered, cursor_y = self._draw_text_block(
                    draw, block, cursor_y, px_width, margin
                )
            rendered_blocks.append(rendered)
            cursor_y += cfg.block_spacing * cfg.scale

        rendered_document = Document(
            page_width=page_width,
            page_height=page_height,
            blocks=rendered_blocks,
        )
        structure = RenderResult(
            image=image,
            document=rendered_document,
            renderer=self.name,
            metadata={
                "scale": cfg.scale,
                "seed": cfg.seed,
                "bbox_space": "document",  # multiply by scale for pixels
                "paper": PaperConfig(enabled=False).model_dump(),
            },
        )
        # Stage two: the finished structure goes onto paper.
        return structure.with_paper(cfg.paper, seed=cfg.seed)

    def _column_edges(
        self, left: float, table_width: float, n_columns: int
    ) -> list[float]:
        """Left edge of every column, plus the table's right edge."""
        weights = self.config.table_column_widths
        if len(weights) != n_columns or sum(weights) <= 0:
            weights = tuple(1 / n_columns for _ in range(n_columns))

        total = sum(weights)
        edges = [left]
        for weight in weights:
            edges.append(edges[-1] + table_width * weight / total)
        return edges

    def _align_for(self, column: int) -> str:
        alignments = self.config.table_column_align
        return alignments[column] if column < len(alignments) else "left"

    @staticmethod
    def _align_offset(align: str, available: float, text_width: float) -> float:
        if align == "right":
            return max(0.0, available - text_width)
        if align == "center":
            return max(0.0, (available - text_width) / 2)
        return 0.0

    def _px_box(self, x1, y1, x2, y2) -> BBox:
        """Pixel coordinates -> document-space bbox."""
        scale = self.config.scale
        return BBox(x1=x1 / scale, y1=y1 / scale, x2=x2 / scale, y2=y2 / scale)

    def _draw_text_block(
        self,
        draw,
        block: DocumentBlock,
        cursor_y: float,
        px_width: float,
        margin: float,
    ) -> tuple[DocumentBlock, float]:
        cfg = self.config
        font = self._font_for(block.block_type)

        # An explicit bbox pins the block; otherwise it flows below the previous one.
        if block.bbox is not None:
            left = block.bbox.x1 * cfg.scale
            top = block.bbox.y1 * cfg.scale
            max_width = max(block.bbox.width * cfg.scale, 1.0)
        else:
            left = margin
            top = cursor_y
            max_width = max(px_width - 2 * margin, 1.0)

        text = block.content or ""
        lines = self._wrap(text, font, max_width) if text else []
        line_height = self._line_height(font)

        centered = block.block_type in cfg.center_block_types

        y = top
        widest = 0.0
        for line in lines:
            line_width = font.getlength(line)
            x = left + (max_width - line_width) / 2 if centered else left
            draw.text((x, y), line, font=font, fill=cfg.text_color)
            widest = max(widest, line_width)
            y += line_height

        bottom = y if lines else top
        width = max_width if centered else max(widest, 1.0)
        bbox = self._px_box(left, top, left + width, max(bottom, top + 1.0))

        if cfg.underline_headers and block.block_type in {
            BlockType.TITLE,
            BlockType.SECTION_HEADER,
        }:
            rule_y = bottom + 4 * cfg.scale
            draw.line(
                [(left, rule_y), (left + max_width, rule_y)],
                fill=cfg.rule_color,
                width=max(1, int(cfg.scale)),
            )
            bottom = rule_y

        rendered = block.model_copy(update={"bbox": bbox})
        next_cursor = max(cursor_y, bottom) if block.bbox is not None else bottom
        return rendered, next_cursor

    def _draw_table(
        self,
        draw,
        block: DocumentBlock,
        cursor_y: float,
        px_width: float,
        margin: float,
    ) -> tuple[DocumentBlock, float]:
        cfg = self.config
        table: TableBlock = block.table  # type: ignore[assignment]
        anchor = block.bbox or table.bbox

        if anchor is not None:
            left = anchor.x1 * cfg.scale
            top = anchor.y1 * cfg.scale
            table_width = max(anchor.width * cfg.scale, 1.0)
        else:
            left = margin
            top = cursor_y
            table_width = max(px_width - 2 * margin, 1.0)

        n_columns = max(table.n_columns, 1)
        column_edges = self._column_edges(left, table_width, n_columns)
        padding = cfg.cell_padding * cfg.scale

        body_font = self._font_for(BlockType.TEXT)
        # Header cells use the body size, just bold.
        header_font = load_font(
            find_font(cfg.bold_font_path, bold=True),
            int(round(cfg.font_size * cfg.scale)),
        )

        y = top
        rendered_rows = []
        for row in table.rows:
            row_height = 0.0
            cell_boxes = []
            column_index = 0

            for cell in row.cells:
                font = header_font if cell.is_header else body_font
                first = min(column_index, n_columns - 1)
                last = min(column_index + cell.colspan, n_columns)
                cell_left = column_edges[first]
                cell_width = max(column_edges[last] - cell_left, 1.0)

                lines = self._wrap(
                    cell.content, font, max(cell_width - 2 * padding, 1.0)
                )
                line_height = self._line_height(font)
                height = len(lines) * line_height + 2 * padding
                row_height = max(row_height, height)

                cell_boxes.append(
                    (cell, cell_left, cell_width, lines, font, self._align_for(first))
                )
                column_index += cell.colspan

            rendered_cells = []
            for cell, cell_left, cell_width, lines, font, align in cell_boxes:
                text_y = y + padding
                inner = max(cell_width - 2 * padding, 1.0)
                for line in lines:
                    offset = self._align_offset(align, inner, font.getlength(line))
                    draw.text(
                        (cell_left + padding + offset, text_y),
                        line,
                        font=font,
                        fill=cfg.text_color,
                    )
                    text_y += self._line_height(font)

                if cfg.draw_table_grid:
                    draw.rectangle(
                        [cell_left, y, cell_left + cell_width, y + row_height],
                        outline=cfg.rule_color,
                        width=max(1, int(cfg.scale)),
                    )
                rendered_cells.append(
                    cell.model_copy(
                        update={
                            "bbox": self._px_box(
                                cell_left, y, cell_left + cell_width, y + row_height
                            )
                        }
                    )
                )

            rendered_rows.append(row.model_copy(update={"cells": rendered_cells}))
            y += row_height

        table_bbox = self._px_box(left, top, left + table_width, max(y, top + 1.0))
        rendered_table = table.model_copy(
            update={"rows": rendered_rows, "bbox": table_bbox}
        )
        rendered = block.model_copy(update={"table": rendered_table, "bbox": table_bbox})
        next_cursor = max(cursor_y, y) if anchor is not None else y
        return rendered, next_cursor

