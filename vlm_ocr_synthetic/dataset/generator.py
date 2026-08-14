"""The render loop, and the dry run that plans without rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..renderers import RendererUnavailable, get_renderer
from ..variations import ScenarioSpace
from ..variations.space import realised_distribution
from .config import DEFAULT_OUT_DIR, DatasetConfig, build_space
from .planner import (
    build_document,
    flatten,
    page_stem,
    plan_pages,
    render_options,
)


def generate(
    config: DatasetConfig,
    out_dir: Path | str = DEFAULT_OUT_DIR,
    space: ScenarioSpace | None = None,
    save_images: bool = True,
    progress: Any | None = None,
) -> dict[str, Any]:
    """Render the planned pages and write ``manifest.jsonl``."""
    out_dir = Path(out_dir)
    space = build_space(config, space)
    pages = plan_pages(space, config)

    pages_dir = out_dir / "pages"
    manifest_path = out_dir / "manifest.jsonl"
    out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped: dict[str, str] = {}
    renderers: dict[str, Any] = {}

    with manifest_path.open("w", encoding="utf-8") as manifest:
        for page in pages:
            renderer_name, options = render_options(page.scenario, config.scale)

            try:
                renderer = get_renderer(renderer_name, options)
            except RendererUnavailable as exc:
                skipped[page.scenario["backend"].name] = str(exc)
                continue

            document = build_document(page.scenario)
            structure = renderer.render(document)
            renderers.setdefault(renderer_name, renderer)

            for variant_index, scenario in enumerate(page.degradations):
                paper = scenario["degradation"].value
                result = structure.with_paper(paper, seed=scenario.seed)

                entry: dict[str, Any] = {
                    **scenario.as_dict(),
                    "renderer": renderer_name,
                    "image_size": list(result.image.size),
                    "blocks": len(result.document.blocks),
                }

                if save_images:
                    image_path, annotation_path = result.save(
                        pages_dir,
                        page_stem(scenario, variant_index),
                        image_format=config.image_format,
                        quality=config.jpeg_quality,
                    )
                    entry["image"] = str(image_path.relative_to(out_dir))
                    entry["annotation"] = str(annotation_path.relative_to(out_dir))

                manifest.write(json.dumps(entry, ensure_ascii=False) + "\n")
                written += 1

                if progress is not None:
                    progress(written, scenario)

    report = {
        "config": config.model_dump(),
        "pages": len(pages),
        "images": written,
        "combinations_available": space.count_combinations(),
        "distribution": realised_distribution(flatten(pages)),
        "skipped": skipped,
        "manifest": str(manifest_path),
    }
    (out_dir / "summary.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return report


def dry_run(config: DatasetConfig, space: ScenarioSpace | None = None) -> dict[str, Any]:
    """Plan the run and report the distribution without rendering anything."""
    space = build_space(config, space)
    pages = plan_pages(space, config)
    scenarios = flatten(pages)

    return {
        "pages": len(pages),
        "images": len(scenarios),
        "combinations_available": space.count_combinations(),
        "combinations_used": len({s.key(space.axis_names()) for s in scenarios}),
        "distribution": realised_distribution(scenarios),
    }
