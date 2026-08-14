"""Renderer registry.

Backends are imported lazily so that a missing optional dependency (a
browser for the html backend, Pillow for synthdog) never breaks importing
the package or the other backend.

    from vlm_ocr_synthetic.renderers import get_renderer

    renderer = get_renderer("synthdog")
    result = renderer.render(document)
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from ..schemas.render import RenderConfig
from .base import BaseRenderer, RendererUnavailable

# name -> "module:ClassName"
_REGISTRY: dict[str, str] = {
    "synthdog": "vlm_ocr_synthetic.renderers.synthdog.renderer:SynthdogRenderer",
    "html": "vlm_ocr_synthetic.renderers.html.renderer:HtmlRenderer",
}


def register_renderer(name: str, target: str) -> None:
    """Register an out-of-tree backend as ``"package.module:ClassName"``."""
    _REGISTRY[name] = target


def renderer_names() -> list[str]:
    return sorted(_REGISTRY)


def get_renderer_class(name: str) -> type[BaseRenderer]:
    try:
        target = _REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"unknown renderer '{name}'; available: {', '.join(renderer_names())}"
        ) from None

    module_path, _, class_name = target.partition(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def get_renderer(
    name: str,
    config: RenderConfig | dict[str, Any] | None = None,
) -> BaseRenderer:
    """Instantiate a backend, raising ``RendererUnavailable`` if unusable."""
    renderer_cls = get_renderer_class(name)
    renderer_cls.ensure_available()
    return renderer_cls(config)


def available_renderers() -> dict[str, str | None]:
    """Map every registered name to ``None`` (usable) or a reason string."""
    status: dict[str, str | None] = {}
    for name in renderer_names():
        try:
            status[name] = get_renderer_class(name).check_available()
        except Exception as exc:  # import error counts as unavailable
            status[name] = f"{type(exc).__name__}: {exc}"
    return status


def load_config(path: str | Path) -> tuple[str, dict[str, Any]]:
    """Read a YAML/JSON renderer config -> ``(renderer_name, options)``.

    The file holds a ``renderer:`` key naming the backend; every other key
    is passed to that backend's config model.
    """
    import json

    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    if path.suffix in {".yaml", ".yml"}:
        import yaml

        data = yaml.safe_load(raw) or {}
    else:
        data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError(f"{path}: config must be a mapping")

    data = dict(data)
    name = data.pop("renderer", None)
    if not name:
        raise ValueError(f"{path}: missing required 'renderer' key")
    return name, data


def renderer_from_config(path: str | Path) -> BaseRenderer:
    name, options = load_config(path)
    return get_renderer(name, options)


__all__ = [
    "BaseRenderer",
    "RendererUnavailable",
    "available_renderers",
    "get_renderer",
    "get_renderer_class",
    "load_config",
    "register_renderer",
    "renderer_from_config",
    "renderer_names",
]
