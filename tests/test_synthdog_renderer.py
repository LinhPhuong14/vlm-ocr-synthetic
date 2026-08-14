"""Behaviour specific to the Pillow rasteriser."""

from __future__ import annotations

import pytest

from conftest import requires_renderer
from vlm_ocr_synthetic.renderers.synthdog import SynthdogConfig, SynthdogRenderer
from vlm_ocr_synthetic.schemas.document import (
    BlockType,
    Document,
    DocumentBlock,
)

pytestmark = requires_renderer("synthdog")


def test_config_defaults_are_sane():
    config = SynthdogConfig()
    assert config.scale == 1.0
    assert config.margin > 0
    assert config.font_size > 0


@pytest.mark.slow
def test_scale_multiplies_the_pixel_size(invoice: Document):
    small = SynthdogRenderer({"scale": 0.5}).render(invoice)
    large = SynthdogRenderer({"scale": 1.0}).render(invoice)

    assert large.image.size[0] == small.image.size[0] * 2
    assert large.image.size[1] == small.image.size[1] * 2


@pytest.mark.slow
def test_bboxes_are_scale_invariant(invoice: Document):
    """Annotations live in document space, so they must not move with scale."""
    small = SynthdogRenderer({"scale": 0.5}).render(invoice)
    large = SynthdogRenderer({"scale": 1.0}).render(invoice)

    for a, b in zip(small.document.blocks, large.document.blocks):
        assert a.bbox is not None and b.bbox is not None
        assert a.bbox.x1 == pytest.approx(b.bbox.x1, abs=2.0)
        assert a.bbox.y1 == pytest.approx(b.bbox.y1, abs=2.0)


@pytest.mark.slow
def test_blocks_without_bbox_flow_down_the_page():
    document = Document(
        page_width=800,
        page_height=1000,
        blocks=[
            DocumentBlock(block_type=BlockType.TITLE, content="Report"),
            DocumentBlock(block_type=BlockType.TEXT, content="First paragraph."),
            DocumentBlock(block_type=BlockType.TEXT, content="Second paragraph."),
        ],
    )
    result = SynthdogRenderer({"paper": {"enabled": False}}).render(document)

    tops = [block.bbox.y1 for block in result.document.blocks]  # type: ignore[union-attr]
    assert tops == sorted(tops)
    assert len(set(tops)) == 3


@pytest.mark.slow
def test_explicit_bbox_pins_the_block(invoice: Document):
    result = SynthdogRenderer().render(invoice)

    header = result.document.blocks[0]
    assert header.bbox is not None
    assert header.bbox.x1 == pytest.approx(invoice.blocks[0].bbox.x1)  # type: ignore[union-attr]
    assert header.bbox.y1 == pytest.approx(invoice.blocks[0].bbox.y1)  # type: ignore[union-attr]


@pytest.mark.slow
def test_paper_changes_pixels_but_not_annotations(invoice: Document):
    clean = SynthdogRenderer({"paper": {"enabled": False}}).render(invoice)
    noisy = SynthdogRenderer({"paper": {"grain": 12}}).render(invoice)

    assert clean.image.tobytes() != noisy.image.tobytes()
    assert clean.document == noisy.document


@pytest.mark.slow
def test_seed_controls_the_paper_grain(invoice: Document):
    a = SynthdogRenderer({"seed": 1, "paper": {"grain": 12}}).render(invoice)
    b = SynthdogRenderer({"seed": 2, "paper": {"grain": 12}}).render(invoice)

    assert a.image.tobytes() != b.image.tobytes()


def test_long_text_wraps_into_multiple_lines():
    renderer = SynthdogRenderer()
    font = renderer._font_for(BlockType.TEXT)
    lines = renderer._wrap("word " * 200, font, max_width=300)

    assert len(lines) > 1
    assert all(font.getlength(line) <= 300 for line in lines)


def test_missing_font_is_reported():
    with pytest.raises(FileNotFoundError):
        SynthdogRenderer({"font_path": "/nope/does-not-exist.ttf"})._font_for(
            BlockType.TEXT
        )
