from pydantic import BaseModel
from typing import Optional


class BBox(BaseModel):
    x1: float
    y1: float
    x2: float
    y2: float

class TableCell(BaseModel):
    content: str

    rowspan: int = 1
    colspan: int = 1

    is_header: bool = False

    bbox: Optional[BBox] = None

class TableRow(BaseModel):
    cells: list[TableCell]


class TableBlock(BaseModel):
    rows: list[TableRow]

    bbox: Optional[BBox] = None
    
class DocumentBlock(BaseModel):
    block_type: str
    content: Optional[str] = None
    bbox: Optional[BBox] = None


class Document(BaseModel):
    page_width: int
    page_height: int
    blocks: list[DocumentBlock]