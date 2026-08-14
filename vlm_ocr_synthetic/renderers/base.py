"""The contract every renderer backend implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import nullcontext
from pathlib import Path
from typing import Any, ClassVar, Iterable, Optional

from ..schemas.document import Document
from ..schemas.render import RenderConfig, RenderResult


class RendererUnavailable(RuntimeError):
    """Raised when a backend's optional dependencies are missing."""


class BaseRenderer(ABC):
    """Turns a :class:`Document` into an image + ground-truth annotation.

    Subclasses declare their own config model via ``config_model`` and are
    constructed either directly or through
    :func:`vlm_ocr_synthetic.renderers.get_renderer`.
    """

    name: ClassVar[str] = "base"
    config_model: ClassVar[type[RenderConfig]] = RenderConfig

    def __init__(self, config: Optional[RenderConfig | dict[str, Any]] = None):
        self.config = self._coerce_config(config)

    @classmethod
    def _coerce_config(
        cls, config: Optional[RenderConfig | dict[str, Any]]
    ) -> RenderConfig:
        if config is None:
            return cls.config_model()
        if isinstance(config, dict):
            return cls.config_model(**config)
        if isinstance(config, cls.config_model):
            return config
        # A plain RenderConfig passed to a backend with a richer model.
        return cls.config_model(**config.model_dump(exclude_unset=True))

    @classmethod
    def check_available(cls) -> Optional[str]:
        """Return ``None`` when usable, else a human-readable reason why not.

        Backends override this to probe optional dependencies (Pillow, a
        browser, ...) *without* importing them at module import time.
        """
        return None

    @classmethod
    def is_available(cls) -> bool:
        return cls.check_available() is None

    @classmethod
    def ensure_available(cls) -> None:
        reason = cls.check_available()
        if reason is not None:
            raise RendererUnavailable(f"renderer '{cls.name}' unavailable: {reason}")

    @abstractmethod
    def render(self, document: Document) -> RenderResult:
        """Render one page."""

    def session(self):
        """Context in which several renders share expensive setup.

        No-op by default; backends with a costly startup (a browser)
        override it so a batch pays that cost once instead of per page.
        """
        return nullcontext(self)

    def render_many(
        self,
        documents: Iterable[Document],
        out_dir: Optional[str | Path] = None,
        stem: str = "page",
    ) -> list[RenderResult]:
        results = []
        with self.session():
            for index, document in enumerate(documents):
                result = self.render(document)
                if out_dir is not None:
                    result.save(out_dir, f"{stem}_{index:05d}")
                results.append(result)
        return results
