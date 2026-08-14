"""The benchmark: every image lands in the output folder, numbers add up."""

from __future__ import annotations

import json

import pytest

from vlm_ocr_synthetic.evaluation import (
    BenchmarkCase,
    count_annotations,
    cross_backend_agreement,
    default_cases,
    format_markdown,
    ink_coverage,
    layout_fidelity,
    luminance_stats,
    run_benchmark,
    save_report,
)
from vlm_ocr_synthetic.renderers import get_renderer_class, renderer_names
from vlm_ocr_synthetic.schemas.document import BBox, Document

FAST = {"scale": 0.3}


def _available_cases(options):
    return [
        case
        for case in default_cases(options)
        if get_renderer_class(case.renderer).check_available() is None
    ]


# ------------------------------------------------------------ pure functions


def test_default_cases_split_html_by_layout():
    labels = [case.label for case in default_cases()]

    assert "synthdog" in labels
    assert {"html-flow", "html-absolute"} <= set(labels)
    assert len(labels) >= len(renderer_names())


def test_default_cases_carry_shared_options():
    for case in default_cases({"scale": 2.0}):
        assert case.options["scale"] == 2.0


def test_bbox_iou_is_symmetric_and_bounded():
    a = BBox(x1=0, y1=0, x2=10, y2=10)
    b = BBox(x1=5, y1=0, x2=15, y2=10)

    assert a.iou(a) == 1.0
    assert a.iou(b) == pytest.approx(b.iou(a))
    assert a.iou(b) == pytest.approx(1 / 3)
    assert a.iou(BBox(x1=100, y1=100, x2=110, y2=110)) == 0.0


def test_layout_fidelity_is_none_without_requested_geometry():
    from vlm_ocr_synthetic.schemas.document import BlockType, DocumentBlock

    flowed = Document(
        page_width=100,
        page_height=100,
        blocks=[DocumentBlock(block_type=BlockType.TEXT, content="x")],
    )
    rendered = flowed.model_copy(
        update={
            "blocks": [
                flowed.blocks[0].model_copy(
                    update={"bbox": BBox(x1=0, y1=0, x2=10, y2=10)}
                )
            ]
        }
    )
    assert layout_fidelity(flowed, rendered) is None


def test_layout_fidelity_is_one_when_geometry_is_honoured(invoice: Document):
    assert layout_fidelity(invoice, invoice) == 1.0


def test_cross_backend_agreement_needs_boxes_on_both_sides(invoice: Document):
    scores = cross_backend_agreement(invoice, invoice)

    assert scores is not None
    assert scores["mean_iou"] == 1.0
    assert scores["blocks_compared"] == len(invoice.blocks)


def test_annotation_counts_match_the_sample(invoice: Document):
    blocks, cells, complete = count_annotations(invoice)

    assert blocks == len(invoice.blocks)
    assert cells == 9
    assert complete is False  # the sample leaves cell boxes to the renderer


def test_image_metrics_read_a_synthetic_page():
    Image = pytest.importorskip("PIL.Image")

    page = Image.new("RGB", (10, 10), (255, 255, 255))
    assert ink_coverage(page) == 0.0
    assert luminance_stats(page) == {"mean": 255.0, "stdev": 0.0}

    dark = Image.new("RGB", (10, 10), (0, 0, 0))
    assert ink_coverage(dark) == 1.0


# ------------------------------------------------------------------ the run


@pytest.mark.slow
def test_benchmark_writes_images_and_reports(tmp_path):
    cases = _available_cases(FAST)
    if not cases:
        pytest.skip("no renderer available")

    report = run_benchmark(pages=2, cases=cases, out_dir=tmp_path)
    json_path, markdown_path = save_report(report, tmp_path)

    labels = [entry["label"] for entry in report["backends"]]
    assert labels == [case.label for case in cases]

    for label in labels:
        # every generated image is kept next to the report
        images = sorted((tmp_path / label).glob("page_*.png"))
        assert len(images) == 2, label
        assert all(path.stat().st_size > 0 for path in images)
        assert len(list((tmp_path / label).glob("page_*.json"))) == 2

    assert json.loads(json_path.read_text())["backends"]
    assert "Renderer benchmark" in markdown_path.read_text()


@pytest.mark.slow
def test_benchmark_report_shape(tmp_path):
    cases = _available_cases(FAST)
    if not cases:
        pytest.skip("no renderer available")

    report = run_benchmark(pages=1, cases=cases, out_dir=tmp_path, save_images=False)

    for entry in report["backends"]:
        assert entry["pages"] == 1
        assert entry["seconds_per_page"]["median"] > 0
        assert entry["boxes_complete"] is True
        assert entry["deterministic"] is True
        assert entry["cells"] == 9
        # both backends must record the paper settings they used
        assert "paper" in entry["metadata"]

    assert set(report) == {
        "environment",
        "settings",
        "backends",
        "skipped",
        "agreement",
    }


@pytest.mark.slow
def test_html_absolute_honours_geometry_better_than_flow(tmp_path):
    """The comparison the report exists to make."""
    cases = [case for case in _available_cases(FAST) if case.renderer == "html"]
    if len(cases) < 2:
        pytest.skip("html renderer unavailable")

    report = run_benchmark(pages=1, cases=cases, out_dir=tmp_path, save_images=False)
    fidelity = {entry["label"]: entry["layout_fidelity"] for entry in report["backends"]}

    assert fidelity["html-absolute"] > fidelity["html-flow"]


@pytest.mark.slow
def test_markdown_report_lists_every_case(tmp_path):
    cases = _available_cases(FAST)
    if not cases:
        pytest.skip("no renderer available")

    report = run_benchmark(pages=1, cases=cases, out_dir=tmp_path, save_images=False)
    markdown = format_markdown(report)

    for case in cases:
        assert case.label in markdown
    assert "seconds/page" in markdown
    assert "Paper layer" in markdown


def test_unavailable_backend_is_reported_not_raised(tmp_path):
    case = BenchmarkCase("nope", "synthdog", {"scale": 0.3})
    object.__setattr__(case, "renderer", "does-not-exist")

    with pytest.raises(KeyError):
        run_benchmark(pages=1, cases=[case], out_dir=tmp_path, save_images=False)
