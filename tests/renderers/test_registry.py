"""The registry is what makes 'test both backends' a one-liner."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from vlm_ocr_synthetic.renderers import (
    available_renderers,
    get_renderer_class,
    load_config,
    register_renderer,
    renderer_names,
)
from vlm_ocr_synthetic.renderers.base import BaseRenderer

CONFIG_DIR = Path(__file__).resolve().parent.parent.parent / "configs" / "renderers"


def test_both_backends_are_registered():
    assert set(renderer_names()) >= {"synthdog", "html"}


def test_renderer_classes_implement_the_contract():
    for name in renderer_names():
        renderer_cls = get_renderer_class(name)
        assert issubclass(renderer_cls, BaseRenderer)
        assert renderer_cls.name == name
        assert callable(renderer_cls.check_available)


def test_availability_report_covers_every_backend():
    status = available_renderers()
    assert set(status) == set(renderer_names())
    for reason in status.values():
        assert reason is None or isinstance(reason, str)


def test_unknown_renderer_raises():
    with pytest.raises(KeyError):
        get_renderer_class("does-not-exist")


def test_out_of_tree_backend_can_be_registered():
    register_renderer(
        "dummy", "vlm_ocr_synthetic.renderers.synthdog.renderer:SynthdogRenderer"
    )
    try:
        assert "dummy" in renderer_names()
        assert get_renderer_class("dummy").__name__ == "SynthdogRenderer"
    finally:
        from vlm_ocr_synthetic.renderers import _REGISTRY

        _REGISTRY.pop("dummy", None)


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("synthdog_default.yaml", "synthdog"),
        ("html_flow.yaml", "html"),
        ("html_absolute.yaml", "html"),
    ],
)
def test_shipped_configs_load_and_validate(filename, expected):
    name, options = load_config(CONFIG_DIR / filename)
    assert name == expected

    config = get_renderer_class(name).config_model(**options)
    assert config.scale > 0


def test_config_without_renderer_key_is_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("scale: 2.0\n", encoding="utf-8")
    with pytest.raises(ValueError, match="renderer"):
        load_config(path)


def test_typo_in_config_is_rejected():
    from vlm_ocr_synthetic.renderers.synthdog import SynthdogConfig

    with pytest.raises(ValidationError):
        SynthdogConfig(fontsize=12)
