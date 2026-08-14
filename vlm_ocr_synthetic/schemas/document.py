"""Renderer-agnostic description of a document page.

A ``Document`` is the single source of truth that every renderer backend
consumes: synthdog draws it with PIL, the html backend turns it into DOM
nodes.  Bounding boxes are optional on input -- renderers that lay the page
out themselves fill them in on the rendered copy they return.
"""

from typing import Optional

from pydantic import BaseModel, Field


class BlockType:
    """Block type vocabulary (DocLayNet-flavoured), used by the renderers."""

    CAPTION = "Caption"
    FOOTNOTE = "Footnote"
    FORMULA = "Formula"
    LIST_ITEM = "List-item"
    PAGE_FOOTER = "Page-footer"
    PAGE_HEADER = "Page-Header"
    PICTURE = "Picture"
    SECTION_HEADER = "Section-header"
    TABLE = "Table"
    TEXT = "Text"
    TITLE = "Title"

    ALL = (
        CAPTION,
        FOOTNOTE,
        FORMULA,
        LIST_ITEM,
        PAGE_FOOTER,
        PAGE_HEADER,
        PICTURE,
        SECTION_HEADER,
        TABLE,
        TEXT,
        TITLE,
    )


class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    def as_xyxy(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    def area(self) -> float:
        return max(0.0, self.width) * max(0.0, self.height)

    def iou(self, other: "BBox") -> float:
        """Intersection over union, for comparing two renders of a page."""
        overlap_w = min(self.x2, other.x2) - max(self.x1, other.x1)
        overlap_h = min(self.y2, other.y2) - max(self.y1, other.y1)
        if overlap_w <= 0 or overlap_h <= 0:
            return 0.0

        intersection = overlap_w * overlap_h
        union = self.area() + other.area() - intersection
        return intersection / union if union > 0 else 0.0

    def scaled(self, factor: float) -> "BBox":
        return BBox(
            x1=self.x1 * factor,
            y1=self.y1 * factor,
            x2=self.x2 * factor,
            y2=self.y2 * factor,
        )


class TableCell(BaseModel):
    content: str

    rowspan: int = 1
    colspan: int = 1

    is_header: bool = False

    bbox: Optional[BBox] = None


class TableRow(BaseModel):
    cells: list[TableCell]


class TableBlock(BaseModel):
    """Rows plus the column layout they need to read correctly.

    ``column_widths`` and ``column_align`` live on the table rather than in
    a renderer config because they are a property of *this* table: a
    document may hold several with different shapes, and the same document
    has to come out the same whether it is drawn with glyphs or laid out as
    HTML. Both are optional -- empty means equal columns, all left-aligned.
    """

    rows: list[TableRow]

    # Fractions of the table width, one per column; they are normalised, so
    # [1, 4, 1] and [0.17, 0.66, 0.17] mean the same thing.
    column_widths: tuple[float, ...] = ()

    # "left" | "center" | "right", one per column.
    column_align: tuple[str, ...] = ()

    bbox: Optional[BBox] = None

    def width_fractions(self) -> tuple[float, ...]:
        """Normalised column widths, falling back to equal columns."""
        columns = max(self.n_columns, 1)
        weights = self.column_widths
        if len(weights) != columns or sum(weights) <= 0:
            return tuple(1 / columns for _ in range(columns))

        total = sum(weights)
        return tuple(weight / total for weight in weights)

    def alignment(self, column: int) -> str:
        if column < len(self.column_align):
            return self.column_align[column]
        return "left"

    @property
    def n_columns(self) -> int:
        """Widest row, counting colspans."""
        return max(
            (sum(cell.colspan for cell in row.cells) for row in self.rows),
            default=0,
        )


class DocumentBlock(BaseModel):
    block_type: str
    content: Optional[str] = None
    bbox: Optional[BBox] = None

    # Only set when ``block_type == BlockType.TABLE``.
    table: Optional[TableBlock] = None


class Document(BaseModel):
    page_width: int
    page_height: int
    blocks: list[DocumentBlock] = Field(default_factory=list)

    def text_blocks(self) -> list[DocumentBlock]:
        return [b for b in self.blocks if b.table is None]

    def table_blocks(self) -> list[DocumentBlock]:
        return [b for b in self.blocks if b.table is not None]
