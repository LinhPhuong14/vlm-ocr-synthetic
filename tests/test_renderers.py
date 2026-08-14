"""Contract tests every backend must satisfy.

Each test is parametrised over the registry, so synthdog and html are held
to exactly the same standard: same input document, same output shape, same
ground-truth guarantees.  A backend whose optional dependencies are missing
is skipped, never silently passed.
"""

from __future__ import annotations

import json

import pytest

from vlm_ocr_synthetic.renderers import (
    get_renderer,
    get_renderer_class,
    renderer_names,
)
from vlm_ocr_synthetic.schemas.document import BBox, Document

BACKENDS = renderer_names()


def _skip_if_unavailable(name: str) -> None:
    reason = get_renderer_class(name).check_available()
    if reason is not None:
        pytest.skip(f"{name} renderer unavailable: {reason}")


@pytest.fixture(params=BACKENDS)
def renderer(request):
    _skip_if_unavailable(request.param)
    # scale 0.5 keeps the suite fast; geometry assertions are scale-free.
    return get_renderer(request.param, {"scale": 0.5, "seed": 7})


@pytest.fixture
def result(renderer, invoice):
    return renderer.render(invoice)


def _inside_page(bbox: BBox, document: Document, tolerance: float = 2.0) -> bool:
    return (
        bbox.x1 >= -tolerance
        and bbox.y1 >= -tolerance
        and bbox.x2 <= document.page_width + tolerance
        and bbox.y2 <= document.page_height + tolerance
    )


@pytest.mark.slow
def test_render_returns_an_image_of_the_requested_size(result, invoice):
    assert result.renderer in BACKENDS
    expected = (invoice.page_width * 0.5, invoice.page_height * 0.5)
    assert result.image.size == (int(expected[0]), int(expected[1]))


@pytest.mark.slow
def test_page_is_not_blank(result):
    """A uniform image means nothing was drawn."""
    grayscale = result.image.convert("L")
    darkest, lightest = grayscale.getextrema()
    assert darkest != lightest
    assert darkest < 200  # some dark ink on the page


@pytest.mark.slow
def test_every_block_comes_back_with_a_bbox(result, invoice):
    assert len(result.document.blocks) == len(invoice.blocks)
    for block in result.document.blocks:
        assert block.bbox is not None, f"missing bbox for {block.block_type}"
        assert block.bbox.width > 0 and block.bbox.height > 0
        assert _inside_page(block.bbox, result.document)


@pytest.mark.slow
def test_table_cells_are_annotated(result):
    table_blocks = result.document.table_blocks()
    assert table_blocks, "sample document should contain a table"

    for block in table_blocks:
        table = block.table
        assert table is not None and table.bbox is not None
        for row in table.rows:
            for cell in row.cells:
                assert cell.bbox is not None, f"missing bbox for cell {cell.content!r}"
                assert cell.bbox.width > 0 and cell.bbox.height > 0


@pytest.mark.slow
def test_cells_in_a_row_do_not_overlap(result):
    for block in result.document.table_blocks():
        for row in block.table.rows:  # type: ignore[union-attr]
            boxes = sorted(
                (cell.bbox for cell in row.cells if cell.bbox), key=lambda b: b.x1
            )
            for left, right in zip(boxes, boxes[1:]):
                assert left.x2 <= right.x1 + 1.0


@pytest.mark.slow
def test_content_is_preserved_through_rendering(result, invoice):
    assert [b.content for b in result.document.blocks] == [
        b.content for b in invoice.blocks
    ]


@pytest.mark.slow
def test_metadata_documents_the_bbox_space(result):
    assert result.metadata["bbox_space"] == "document"
    assert result.metadata["scale"] == 0.5


@pytest.mark.slow
def test_save_writes_image_and_annotation(result, tmp_path):
    image_path, annotation_path = result.save(tmp_path, stem="sample")

    assert image_path.exists() and image_path.stat().st_size > 0
    payload = json.loads(annotation_path.read_text(encoding="utf-8"))

    assert payload["renderer"] == result.renderer
    assert payload["image_size"] == list(result.image.size)
    assert len(payload["document"]["blocks"]) == len(result.document.blocks)


@pytest.mark.slow
def test_render_is_deterministic(renderer, invoice):
    first = renderer.render(invoice)
    second = renderer.render(invoice)

    assert first.image.tobytes() == second.image.tobytes()
    assert first.document == second.document


@pytest.mark.slow
def test_render_many_writes_one_pair_per_document(renderer, invoice, tmp_path):
    results = renderer.render_many([invoice, invoice], out_dir=tmp_path, stem="doc")

    assert len(results) == 2
    assert sorted(p.name for p in tmp_path.glob("*.png")) == [
        "doc_00000.png",
        "doc_00001.png",
    ]
    assert len(list(tmp_path.glob("*.json"))) == 2
