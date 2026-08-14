"""Schema round-trips -- the contract both renderers read from."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vlm_ocr_synthetic.schemas.document import (
    BBox,
    BlockType,
    Document,
    DocumentBlock,
    TableBlock,
    TableCell,
    TableRow,
)


def test_bbox_geometry():
    bbox = BBox(x1=100, y1=50, x2=900, y2=120)
    assert bbox.width == 800
    assert bbox.height == 70
    assert bbox.as_xyxy() == (100, 50, 900, 120)
    assert bbox.scaled(2).as_xyxy() == (200, 100, 1800, 240)


def test_table_block_is_kept_on_the_block(invoice: Document):
    table_blocks = invoice.table_blocks()
    assert len(table_blocks) == 1

    table = table_blocks[0].table
    assert table is not None
    assert table.n_columns == 3
    assert [cell.content for cell in table.rows[0].cells] == ["Item", "Qty", "Price"]
    assert all(cell.is_header for cell in table.rows[0].cells)


def test_text_and_table_blocks_partition_the_page(invoice: Document):
    assert len(invoice.text_blocks()) + len(invoice.table_blocks()) == len(
        invoice.blocks
    )


def test_n_columns_accounts_for_colspan():
    table = TableBlock(
        rows=[
            TableRow(cells=[TableCell(content="wide", colspan=3)]),
            TableRow(cells=[TableCell(content="a"), TableCell(content="b")]),
        ]
    )
    assert table.n_columns == 3


def test_document_json_round_trip(invoice: Document):
    restored = Document.model_validate_json(invoice.model_dump_json())
    assert restored == invoice


def test_unknown_field_is_rejected():
    with pytest.raises(ValidationError):
        BBox(x1=0, y1=0, x2=1)  # type: ignore[call-arg]


def test_block_type_vocabulary_is_used_by_samples(invoice: Document):
    assert {block.block_type for block in invoice.blocks} <= set(BlockType.ALL)


def test_block_defaults():
    block = DocumentBlock(block_type=BlockType.TEXT)
    assert block.content is None
    assert block.bbox is None
    assert block.table is None
