"""The Vietnamese receipt sample, and the knobs it needed.

Diacritics are the point of this sample: if font shaping breaks, the page
still renders but the text is wrong, and no other test would notice.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import requires_renderer
from vlm_ocr_synthetic.renderers import load_config
from vlm_ocr_synthetic.samples import get_sample
from vlm_ocr_synthetic.samples.receipt_vn import (
    COLUMN_HEADERS,
    ORDER,
    OrderLine,
    build_receipt_document,
    format_dong,
    order_total,
)
from vlm_ocr_synthetic.schemas.document import BlockType, Document

CONFIG_DIR = Path(__file__).resolve().parent.parent / "configs"

DIACRITICS = "ÁĂÂĐÊÔƠƯáăâđêôơư"


@pytest.fixture
def receipt() -> Document:
    return get_sample("receipt_vn")


def test_receipt_is_thermal_paper_shaped(receipt: Document):
    assert receipt.page_width == 576  # 80mm at 203 dpi
    assert receipt.page_height > receipt.page_width


def test_total_matches_the_line_items(receipt: Document):
    total_block = next(
        block
        for block in receipt.blocks
        if block.content and block.content.startswith("TIỀN MẶT")
    )
    expected = format_dong(order_total())

    assert expected == "537,000"
    assert expected in total_block.content


def test_table_uses_the_vietnamese_invoice_columns(receipt: Document):
    table = receipt.table_blocks()[0].table

    assert table is not None
    assert table.n_columns == 5
    assert [cell.content for cell in table.rows[0].cells] == list(COLUMN_HEADERS)
    assert all(cell.is_header for cell in table.rows[0].cells)
    assert COLUMN_HEADERS[0] == "STT"


def test_first_column_numbers_the_lines(receipt: Document):
    table = receipt.table_blocks()[0].table
    body = table.rows[1:]  # type: ignore[union-attr]

    assert len(body) == len(ORDER)
    assert [row.cells[0].content for row in body] == [
        str(index) for index in range(1, len(ORDER) + 1)
    ]


def test_amount_column_is_quantity_times_unit_price(receipt: Document):
    table = receipt.table_blocks()[0].table

    for row, line in zip(table.rows[1:], ORDER):  # type: ignore[union-attr]
        quantity, unit_price, amount = (cell.content for cell in row.cells[2:5])
        assert quantity == str(line.quantity)
        assert unit_price == format_dong(line.unit_price)
        assert amount == format_dong(line.quantity * line.unit_price)


def test_line_total_is_derived_not_stored():
    line = OrderLine("Cơm Bát Bửu", 4, 43_000)
    assert line.amount == 172_000


def test_sample_carries_vietnamese_diacritics(receipt: Document):
    text = " ".join(block.content or "" for block in receipt.blocks)
    text += " ".join(
        cell.content
        for block in receipt.table_blocks()
        for row in block.table.rows  # type: ignore[union-attr]
        for cell in row.cells
    )
    assert any(char in text for char in DIACRITICS)


def test_order_can_be_overridden():
    document = build_receipt_document(
        order=(OrderLine("Phở Bò", 3, 30_000),), table_number=9
    )
    total = next(b for b in document.blocks if b.content and "TIỀN MẶT" in b.content)

    assert "90,000" in total.content
    assert any("BÀN SỐ: 9" == block.content for block in document.blocks)


@pytest.mark.parametrize(
    "filename", ["html_receipt_vn.yaml", "synthdog_receipt_vn.yaml"]
)
def test_receipt_presets_load(filename):
    from vlm_ocr_synthetic.renderers import get_renderer_class

    name, options = load_config(CONFIG_DIR / filename)
    config = get_renderer_class(name).config_model(**options)

    assert config.paper.enabled
    assert config.paper.grain > 0


# ------------------------------------------------------------ rendering it


@requires_renderer("synthdog")
@pytest.mark.slow
def test_synthdog_renders_the_receipt(receipt: Document):
    from vlm_ocr_synthetic.renderers.synthdog import SynthdogRenderer

    name, options = load_config(CONFIG_DIR / "synthdog_receipt_vn.yaml")
    result = SynthdogRenderer(options).render(receipt)

    assert result.image.size == (receipt.page_width, receipt.page_height)
    for block in result.document.blocks:
        assert block.bbox is not None


@requires_renderer("synthdog")
@pytest.mark.slow
def test_centred_blocks_are_centred(receipt: Document):
    from vlm_ocr_synthetic.renderers.synthdog import SynthdogRenderer

    options = {"center_block_types": ["Page-Header"], "margin": 34}
    result = SynthdogRenderer(options).render(receipt)

    header = result.document.blocks[0].bbox
    assert header is not None
    left_gap = header.x1
    right_gap = receipt.page_width - header.x2
    assert left_gap == pytest.approx(right_gap, abs=1.0)


@requires_renderer("synthdog")
@pytest.mark.slow
def test_column_widths_are_honoured(receipt: Document):
    from vlm_ocr_synthetic.renderers.synthdog import SynthdogRenderer

    result = SynthdogRenderer(
        {"table_column_widths": [0.09, 0.38, 0.09, 0.21, 0.23], "margin": 34}
    ).render(receipt)

    cells = result.document.table_blocks()[0].table.rows[0].cells  # type: ignore[union-attr]
    widths = [cell.bbox.width for cell in cells]  # type: ignore[union-attr]

    assert widths[1] > widths[4] > widths[0]  # item column widest, STT narrowest
    ratios = [width / sum(widths) for width in widths]
    assert ratios[0] == pytest.approx(0.09, abs=0.01)
    assert ratios[1] == pytest.approx(0.38, abs=0.01)


@requires_renderer("synthdog")
@pytest.mark.slow
def test_underline_headers_can_be_switched_off(receipt: Document):
    from vlm_ocr_synthetic.renderers.synthdog import SynthdogRenderer

    ruled = SynthdogRenderer({"underline_headers": True}).render(receipt)
    bare = SynthdogRenderer({"underline_headers": False}).render(receipt)

    assert ruled.image.tobytes() != bare.image.tobytes()


@requires_renderer("html")
@pytest.mark.slow
def test_html_renders_the_receipt(receipt: Document):
    from vlm_ocr_synthetic.renderers.html import HtmlRenderer

    name, options = load_config(CONFIG_DIR / "html_receipt_vn.yaml")
    result = HtmlRenderer(options).render(receipt)

    assert result.image.size == (receipt.page_width, receipt.page_height)
    cells = [
        cell
        for block in result.document.table_blocks()
        for row in block.table.rows  # type: ignore[union-attr]
        for cell in row.cells
    ]
    assert len(cells) == (len(ORDER) + 1) * 5  # header row included
    assert all(cell.bbox is not None for cell in cells)


def test_extra_css_reaches_the_stylesheet(receipt: Document):
    pytest.importorskip("jinja2")
    from vlm_ocr_synthetic.renderers.html import HtmlConfig
    from vlm_ocr_synthetic.renderers.html.html_builder import build_html

    css = ".block-Page-Header { text-align: center; }"
    html = build_html(receipt, HtmlConfig(extra_css=css))

    assert css in html  # not html-escaped
    assert "white-space: pre-wrap" in html  # newlines and padding survive
