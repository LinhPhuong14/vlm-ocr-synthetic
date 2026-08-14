"""The corpus rule: content is words, layout is structure.

The two backends disagree about whitespace by nature -- Pillow lays out
glyph runs, a browser applies ``white-space`` and its own shaper -- so any
sample that aligns columns with padding spaces renders as two different
documents. These tests keep the corpus on the structural side of that line,
and check that both backends really do agree once it is.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from helpers import requires_renderer

from vlm_ocr_synthetic.corpus import (
    LAYOUT_WHITESPACE,
    assert_plain_text,
    format_dong,
    iter_text,
    layout_whitespace_offenders,
)
from vlm_ocr_synthetic.renderers import get_renderer, load_config
from vlm_ocr_synthetic.samples import get_sample, sample_names
from vlm_ocr_synthetic.schemas.document import (
    BlockType,
    Document,
    DocumentBlock,
    TableBlock,
    TableCell,
    TableRow,
)

CONFIGS = Path(__file__).resolve().parent.parent.parent / "configs" / "renderers"


# ------------------------------------------------------------- the rule


@pytest.mark.parametrize("name", sample_names())
def test_no_shipped_sample_lays_itself_out_with_whitespace(name):
    assert_plain_text(get_sample(name))


def test_offenders_are_reported_with_their_text():
    document = Document(
        page_width=100,
        page_height=100,
        blocks=[
            DocumentBlock(block_type=BlockType.TEXT, content="TIỀN MẶT     537,000"),
            DocumentBlock(block_type=BlockType.TEXT, content="a normal sentence"),
        ],
    )
    offenders = layout_whitespace_offenders(document)

    assert offenders == ["TIỀN MẶT     537,000"]
    with pytest.raises(ValueError, match="column_widths"):
        assert_plain_text(document)


def test_tabs_count_as_layout_whitespace():
    assert LAYOUT_WHITESPACE.search("STT\tTên hàng")
    assert not LAYOUT_WHITESPACE.search("Mì Xào Giòn Nhỏ")


def test_iter_text_covers_blocks_and_cells():
    document = Document(
        page_width=100,
        page_height=100,
        blocks=[
            DocumentBlock(block_type=BlockType.TEXT, content="header"),
            DocumentBlock(
                block_type=BlockType.TABLE,
                table=TableBlock(rows=[TableRow(cells=[TableCell(content="cell")])]),
            ),
        ],
    )
    assert list(iter_text(document)) == ["header", "cell"]


def test_money_formatting_is_shared():
    assert format_dong(537_000) == "537,000"
    assert format_dong(0) == "0"


# ------------------------------------------------- layout lives on the table


def test_column_widths_are_normalised():
    table = TableBlock(
        rows=[TableRow(cells=[TableCell(content=c) for c in "abc"])],
        column_widths=(1, 4, 1),
    )
    assert table.width_fractions() == pytest.approx((1 / 6, 4 / 6, 1 / 6))


def test_wrong_length_or_empty_widths_fall_back_to_equal_columns():
    rows = [TableRow(cells=[TableCell(content=c) for c in "abc"])]

    assert TableBlock(rows=rows).width_fractions() == pytest.approx((1 / 3,) * 3)
    assert TableBlock(rows=rows, column_widths=(1, 1)).width_fractions() == (
        pytest.approx((1 / 3,) * 3)
    )


def test_alignment_defaults_to_left():
    table = TableBlock(
        rows=[TableRow(cells=[TableCell(content=c) for c in "abc"])],
        column_align=("center",),
    )
    assert table.alignment(0) == "center"
    assert table.alignment(2) == "left"


# -------------------------------------------- both backends, one format


@pytest.mark.slow
@requires_renderer("synthdog")
@requires_renderer("html")
@pytest.mark.parametrize("sample", ["receipt_vn", "invoice"])
def test_both_backends_lay_the_same_table_out_the_same_way(sample):
    """The invariant this corpus exists for.

    Same document, two completely different layout engines: the table
    column geometry has to come out the same, because the document -- not
    the renderer config -- says what it should be.
    """
    # The invoice pins its blocks, so html has to be in absolute layout for
    # the comparison to be like for like; the receipt flows in both.
    presets = {
        "receipt_vn": ("synthdog_receipt_vn.yaml", "html_receipt_vn.yaml"),
        "invoice": ("synthdog_default.yaml", "html_absolute.yaml"),
    }[sample]

    document = get_sample(sample)
    geometry = {}

    for backend, preset in zip(("synthdog", "html"), presets):
        config = CONFIGS / preset
        name, options = load_config(config)
        result = get_renderer(name, options).render(document)

        geometry[backend] = [
            [round(cell.bbox.width) for cell in table.table.rows[0].cells]
            for table in result.document.table_blocks()
        ]

    assert geometry["synthdog"] == geometry["html"]


@pytest.mark.slow
@requires_renderer("synthdog")
@requires_renderer("html")
def test_both_backends_keep_the_same_text():
    document = get_sample("receipt_vn")
    rendered = {}

    for backend in ("synthdog", "html"):
        name, options = load_config(CONFIGS / f"{backend}_receipt_vn.yaml")
        rendered[backend] = list(
            iter_text(get_renderer(name, options).render(document).document)
        )

    assert rendered["synthdog"] == rendered["html"] == list(iter_text(document))


# ---------------------------------------- whitespace, if someone insists


@requires_renderer("synthdog")
def test_synthdog_preserves_whitespace_runs_like_the_browser():
    """User text may still contain padding; it must survive intact."""
    from vlm_ocr_synthetic.renderers.synthdog import SynthdogRenderer

    renderer = SynthdogRenderer()
    font = renderer._font_for(BlockType.TEXT)

    assert renderer._wrap("REG        13-11-2011", font, 10_000) == [
        "REG        13-11-2011"
    ]


@requires_renderer("synthdog")
def test_wrapping_drops_only_the_whitespace_it_broke_on():
    from vlm_ocr_synthetic.renderers.synthdog import SynthdogRenderer

    renderer = SynthdogRenderer()
    font = renderer._font_for(BlockType.TEXT)
    lines = renderer._wrap("word " * 40, font, 200)

    assert len(lines) > 1
    for line in lines:
        assert font.getlength(line) <= 200
        assert line == line.strip()  # no dangling separator at a wrap
