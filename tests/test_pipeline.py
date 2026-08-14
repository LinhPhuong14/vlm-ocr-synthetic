"""Dataset generation: the plan, the files it writes, the manifest."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from conftest import requires_renderer
from vlm_ocr_synthetic.pipeline import (
    DatasetConfig,
    build_document,
    build_space,
    dry_run,
    flatten,
    format_distribution,
    generate,
    load_dataset_config,
    plan_pages,
    read_manifest,
    render_options,
)
from vlm_ocr_synthetic.samples.corpus import assert_plain_text
from vlm_ocr_synthetic.variations import LAYOUT_AXIS, default_space
from vlm_ocr_synthetic.variations.space import Scenario

CONFIGS = Path(__file__).resolve().parent.parent / "configs"

# Small and synthdog-only, so the suite does not launch a browser per test.
FAST = DatasetConfig(
    pages=4,
    seed=5,
    scale=0.3,
    degradations_per_page=2,
    axes={"backend": {"synthdog": 1, "html-flow": 0, "html-absolute": 0}},
)


# ------------------------------------------------------------------ config


def test_shipped_dataset_config_loads():
    config = load_dataset_config(CONFIGS / "dataset.yaml")

    assert config.pages > 0
    assert config.mode in {"sample", "stratified"}
    assert set(config.axes) <= set(default_space().axis_names())


def test_shipped_config_names_only_variants_that_exist():
    """A typo in the weights must fail loudly, not silently do nothing."""
    config = load_dataset_config(CONFIGS / "dataset.yaml")
    build_space(config)  # raises KeyError on an unknown axis or variant


def test_unknown_config_key_is_rejected(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("pages: 3\npagez: 4\n", encoding="utf-8")

    with pytest.raises(Exception):
        load_dataset_config(path)


def test_weight_typo_is_reported_with_the_axis(tmp_path):
    path = tmp_path / "typo.yaml"
    path.write_text("axes:\n  degradation:\n    foldd_once: 3\n", encoding="utf-8")

    with pytest.raises(KeyError, match="foldd_once"):
        build_space(load_dataset_config(path))


# ------------------------------------------------------------------- plan


def test_every_page_gets_the_requested_number_of_ageings():
    pages = plan_pages(build_space(FAST), FAST)

    assert len(pages) == FAST.pages
    for page in pages:
        assert len(page.degradations) == FAST.degradations_per_page
        # the structural axes are shared across a page's variants
        keys = {s.key(("layout", "backend", "style")) for s in page.degradations}
        assert len(keys) == 1


def test_a_page_is_not_aged_the_same_way_twice():
    pages = plan_pages(build_space(FAST), FAST)

    for page in pages:
        names = [s["degradation"].name for s in page.degradations]
        assert len(names) == len(set(names))


def test_dry_run_reports_without_touching_the_disk(tmp_path):
    report = dry_run(FAST)

    assert report["pages"] == FAST.pages
    assert report["images"] == FAST.pages * FAST.degradations_per_page
    assert report["combinations_available"] > 0
    assert list(tmp_path.iterdir()) == []
    assert "layout" in format_distribution(report)


# --------------------------------------------------------------- documents


@pytest.mark.parametrize(
    "layout", LAYOUT_AXIS.variants, ids=lambda variant: variant.name
)
def test_every_layout_builds_a_valid_document(layout):
    """A layout that produces a broken document must fail here, not at 5000 pages."""
    space = default_space()
    scenario = Scenario(
        index=0,
        seed=11,
        choices={
            "layout": layout,
            "backend": space.axis("backend").eligible(layout.tags)[0],
            "style": space.axis("style").eligible(layout.tags)[0],
            "degradation": space.axis("degradation").eligible(layout.tags)[0],
        },
    )

    document = build_document(scenario)
    assert document.page_width > 0
    assert document.blocks
    assert_plain_text(document)


def test_receipt_totals_stay_consistent_across_random_orders():
    from vlm_ocr_synthetic.samples.corpus import format_dong
    from vlm_ocr_synthetic.variations.layouts import sample_order
    from vlm_ocr_synthetic.samples.receipt_vn import build_receipt_document, order_total

    for seed in range(20):
        order = sample_order(random.Random(seed), 3, 8)
        document = build_receipt_document(order=order)
        total = document.table_blocks()[2].table.rows[0].cells[1].content
        assert total == format_dong(order_total(order))


def test_render_options_keep_paper_off_for_the_structural_stage():
    space = default_space()
    layout = space.axis("layout").get("receipt_80mm")
    scenario = Scenario(
        index=0,
        seed=3,
        choices={
            "layout": layout,
            "backend": space.axis("backend").get("synthdog"),
            "style": space.axis("style").get("thermal_17"),
            "degradation": space.axis("degradation").get("clean"),
        },
    )
    renderer, options = render_options(scenario, scale=0.5)

    assert renderer == "synthdog"
    assert options["paper"] == {"enabled": False}
    assert options["seed"] == scenario.seed
    assert options["scale"] == 0.5


# ---------------------------------------------------------------- the run


@pytest.mark.slow
@requires_renderer("synthdog")
def test_generate_writes_an_image_and_annotation_per_scenario(tmp_path):
    report = generate(FAST, out_dir=tmp_path)
    entries = list(read_manifest(tmp_path / "manifest.jsonl"))

    assert report["images"] == FAST.pages * FAST.degradations_per_page
    assert len(entries) == report["images"]

    # every manifest row points at files that exist, and no two collide
    assert len({entry["image"] for entry in entries}) == len(entries)
    for entry in entries:
        assert (tmp_path / entry["image"]).stat().st_size > 0
        annotation = json.loads((tmp_path / entry["annotation"]).read_text())
        assert annotation["document"]["blocks"]
        assert annotation["metadata"]["paper"]["enabled"] is True


@pytest.mark.slow
@requires_renderer("synthdog")
def test_the_manifest_records_enough_to_regenerate_a_page(tmp_path):
    generate(FAST, out_dir=tmp_path)
    entry = next(read_manifest(tmp_path / "manifest.jsonl"))

    assert {"index", "seed", "layout", "backend", "style", "degradation"} <= set(entry)


@pytest.mark.slow
@requires_renderer("synthdog")
def test_the_same_seed_generates_the_same_dataset(tmp_path):
    first = generate(FAST, out_dir=tmp_path / "a")
    second = generate(FAST, out_dir=tmp_path / "b")

    assert first["distribution"] == second["distribution"]
    assert (tmp_path / "a" / "manifest.jsonl").read_text() == (
        tmp_path / "b" / "manifest.jsonl"
    ).read_text()

    changed = generate(
        FAST.model_copy(update={"seed": FAST.seed + 1}), out_dir=tmp_path / "c"
    )
    assert changed["distribution"] != first["distribution"]


@pytest.mark.slow
@requires_renderer("synthdog")
def test_summary_records_the_config_that_produced_the_run(tmp_path):
    generate(FAST, out_dir=tmp_path)
    summary = json.loads((tmp_path / "summary.json").read_text())

    assert summary["config"]["seed"] == FAST.seed
    assert summary["config"]["pages"] == FAST.pages
    assert summary["images"] == FAST.pages * FAST.degradations_per_page


@pytest.mark.slow
@requires_renderer("synthdog")
def test_ageings_of_one_page_share_a_layout_but_differ_in_pixels(tmp_path):
    from PIL import Image

    generate(FAST, out_dir=tmp_path)
    entries = [e for e in read_manifest(tmp_path / "manifest.jsonl") if e["index"] == 0]

    assert len(entries) == 2
    assert entries[0]["image_size"] == entries[1]["image_size"]

    images = [Image.open(tmp_path / entry["image"]).tobytes() for entry in entries]
    assert images[0] != images[1]  # different degradation

    annotations = [
        json.loads((tmp_path / entry["annotation"]).read_text())["document"]
        for entry in entries
    ]
    assert annotations[0] == annotations[1]  # same structure, same ground truth
