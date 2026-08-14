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

    def with_paper(self, paper, seed: Optional[int] = None) -> "RenderResult":
        """Return a copy with the paper layer applied on top.

        Rendering is two stages: a backend produces the *structure* -- glyphs,
        rules, table geometry -- and the paper layer is applied to the finished
        page afterwards. Keeping them separate means you can check the
        structure on a clean sheet, then try several paper presets against the
        same render without paying for the layout again (no browser involved).

        The annotations are carried over untouched: paper moves no geometry.
        """
        import random

        from ..renderers.paper import apply_paper

        if seed is None:
            seed = int(self.metadata.get("seed", 0) or 0)

        return RenderResult(
            image=apply_paper(self.image, paper, random.Random(seed)),
            document=self.document,
            renderer=self.renderer,
            metadata={**self.metadata, "paper": paper.model_dump()},
        )

    def annotation(self) -> dict[str, Any]:
        return {
            "renderer": self.renderer,
            "image_size": list(self.image.size),
            "metadata": self.metadata,
            "document": self.document.model_dump(exclude_none=True),
        }

    def save(
        self,
        out_dir: str | Path,
        stem: str = "page",
        image_format: str = "png",
        quality: int = 88,
    ) -> tuple[Path, Path]:
        """Write ``<stem>.<ext>`` and ``<stem>.json`` into ``out_dir``.

        PNG is the default because it is lossless; ``image_format="jpeg"``
        is for previews that have to be small enough to keep in git (a
        grainy page is roughly 5x smaller as JPEG at the same size).
        """
        out_dir = Path(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        suffix = "jpg" if image_format.lower() in {"jpg", "jpeg"} else image_format
        image_path = out_dir / f"{stem}.{suffix}"
        annotation_path = out_dir / f"{stem}.json"

        if suffix == "jpg":
            self.image.convert("RGB").save(image_path, quality=quality, optimize=True)
        else:
            self.image.save(image_path)
        annotation_path.write_text(
            json.dumps(self.annotation(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return image_path, annotation_path
