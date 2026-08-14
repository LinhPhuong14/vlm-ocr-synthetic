"""Behaviour specific to the browser backend.

The markup step needs no browser, so those tests always run; the ones that
take a screenshot are marked ``slow`` and skipped when chromium is absent.
"""

from __future__ import annotations

import pytest

from conftest import requires_renderer
from vlm_ocr_synthetic.renderers.html import HtmlConfig, HtmlRenderer
from vlm_ocr_synthetic.renderers.html.backends import (
    ENGINES,
    PlaywrightEngine,
    ScreenshotEngine,
    resolve_chromium_path,
)
from vlm_ocr_synthetic.renderers.html.html_builder import build_html
from vlm_ocr_synthetic.schemas.document import Document

jinja2 = pytest.importorskip("jinja2")


def test_config_rejects_an_unknown_layout():
    with pytest.raises(Exception):
        HtmlConfig(layout="diagonal")


def test_engine_registry_exposes_playwright():
    assert ENGINES["playwright"] is PlaywrightEngine
    assert issubclass(PlaywrightEngine, ScreenshotEngine)


def test_chromium_lookup_reports_a_bad_explicit_path():
    with pytest.raises(FileNotFoundError):
        resolve_chromium_path("/nope/no-chromium-here")


def test_markup_carries_every_block_and_cell(invoice: Document):
    html = build_html(invoice, HtmlConfig())

    assert 'data-block-id="block-0"' in html
    assert 'data-block-id="block-3"' in html
    assert 'data-cell-id="cell-2-0-0"' in html
    assert "<th" in html and "<td" in html
    assert "INVOICE" in html
    assert "Prices include tax" in html


def test_markup_escapes_content():
    from vlm_ocr_synthetic.schemas.document import BlockType, DocumentBlock

    document = Document(
        page_width=400,
        page_height=400,
        blocks=[
            DocumentBlock(block_type=BlockType.TEXT, content="<script>alert(1)</script>")
        ],
    )
    html = build_html(document, HtmlConfig())

    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_absolute_layout_pins_blocks_with_inline_styles(invoice: Document):
    flow = build_html(invoice, HtmlConfig(layout="flow"))
    absolute = build_html(invoice, HtmlConfig(layout="absolute"))

    assert "position: absolute" in absolute
    assert "left:100.0px" in absolute or "left:100px" in absolute
    assert "position: absolute" not in flow


def test_style_context_only_exposes_template_keys():
    context = HtmlConfig().style_context()

    assert "font_family" in context and "page_background" in context
    assert "engine" not in context and "layout" not in context


@requires_renderer("html")
@pytest.mark.slow
def test_flow_layout_stacks_blocks_in_order(invoice: Document):
    result = HtmlRenderer({"layout": "flow", "scale": 0.5}).render(invoice)

    tops = [block.bbox.y1 for block in result.document.blocks]  # type: ignore[union-attr]
    assert tops == sorted(tops)


@requires_renderer("html")
@pytest.mark.slow
def test_absolute_layout_matches_the_input_geometry(invoice: Document):
    result = HtmlRenderer({"layout": "absolute", "scale": 0.5}).render(invoice)

    for original, rendered in zip(invoice.blocks, result.document.blocks):
        assert original.bbox is not None and rendered.bbox is not None
        assert rendered.bbox.x1 == pytest.approx(original.bbox.x1, abs=1.0)
        assert rendered.bbox.y1 == pytest.approx(original.bbox.y1, abs=1.0)


@requires_renderer("html")
@pytest.mark.slow
def test_dom_boxes_are_in_css_pixels_not_device_pixels(invoice: Document):
    """Boxes must stay in document space even when the screenshot is upscaled."""
    result = HtmlRenderer({"layout": "flow", "scale": 2.0}).render(invoice)

    assert result.image.size == (invoice.page_width * 2, invoice.page_height * 2)
    for block in result.document.blocks:
        assert block.bbox is not None
        assert block.bbox.x2 <= invoice.page_width + 1


@requires_renderer("html")
@pytest.mark.slow
def test_table_cell_boxes_sit_inside_the_table_box(invoice: Document):
    result = HtmlRenderer({"scale": 0.5}).render(invoice)

    block = result.document.table_blocks()[0]
    table_bbox = block.bbox
    assert table_bbox is not None

    for row in block.table.rows:  # type: ignore[union-attr]
        for cell in row.cells:
            assert cell.bbox is not None
            assert cell.bbox.x1 >= table_bbox.x1 - 1
            assert cell.bbox.x2 <= table_bbox.x2 + 1
            assert cell.bbox.y1 >= table_bbox.y1 - 1
            assert cell.bbox.y2 <= table_bbox.y2 + 1
