"""Synthetic document generation for VLM/OCR training data.

Documents are described once (``schemas``) and rendered by interchangeable
backends (``renderers``): ``synthdog`` paints with Pillow, ``html`` lays out
in a browser and reads ground truth off the DOM.
"""

__version__ = "0.1.0"

from .schemas.document import (
    BBox,
    BlockType,
    Document,
    DocumentBlock,
    TableBlock,
    TableCell,
    TableRow,
)
from .schemas.render import RenderConfig, RenderResult

__all__ = [
    "__version__",
    "BBox",
    "BlockType",
    "Document",
    "DocumentBlock",
    "TableBlock",
    "TableCell",
    "TableRow",
    "RenderConfig",
    "RenderResult",
]
