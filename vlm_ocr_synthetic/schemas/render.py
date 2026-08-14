"""Types shared by every renderer backend: config in, ``RenderResult`` out."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from pydantic import BaseModel

from .document import Document

if TYPE_CHECKING:  # pragma: no cover - typing only
    from PIL.Image import Image


class RenderConfig(BaseModel):
    """Options understood by every backend.

    Backends subclass this to add their own knobs (see
    ``SynthdogConfig`` / ``HtmlConfig``).  Unknown keys are rejected so a
    typo in a YAML config fails loudly instead of being silently ignored.
    """

    model_config = {"extra": "forbid"}

    # Page size in schema units. ``None`` means "take it from the document".
    page_width: Optional[int] = None
    page_height: Optional[int] = None

    # Pixels per schema unit; 2.0 renders a 1000x1400 page at 2000x2800.
    scale: float = 1.0

    # Seeds anything random in the backend (noise, jitter, ...).
    seed: int = 0

    def page_size(self, document: Document) -> tuple[int, int]:
        width = self.page_width or document.page_width
        height = self.page_height or document.page_height
        return int(width), int(height)


@dataclass
class RenderResult:
    """A rendered page plus the ground truth that goes with it."""

    image: "Image"
    document: Document
    renderer: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def annotation(self) -> dict[str, Any]:
        return {
            "renderer": self.renderer,
            "image_size": list(self.image.size),
            "metadata": self.metadata,
            "document": self.document.model_dump(exclude_none=True),
        }

    def save(self, out_dir: str | Path, stem: str = "page") -> tuple[Path, Path]:
        """Write ``<stem>.png`` and ``<stem>.json`` into ``out_dir``."""
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        image_path = out_dir / f"{stem}.png"
        annotation_path = out_dir / f"{stem}.json"

        self.image.save(image_path)
        annotation_path.write_text(
            json.dumps(self.annotation(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return image_path, annotation_path
