"""Dataset generation: sample scenarios, render them, write a manifest.

The loop is deliberately boring, and its shape comes from one fact: paper
is a stage *after* the structural render. So a page is laid out once and
aged ``degradations_per_page`` times, which for the browser backend turns a
~0.2 s layout into ~0.01 s per extra variant.

Everything a page needed is recorded in the manifest -- layout, backend,
style, degradation, and the seed -- so any single page can be regenerated
without rerunning the batch.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional

from pydantic import BaseModel

from .renderers import RendererUnavailable, get_renderer
from .samples.corpus import assert_plain_text
from .schemas.document import Document
from .variations import ScenarioSpace, default_space
from .variations.space import Scenario, plan, realised_distribution, seed_for

DEFAULT_OUT_DIR = Path("data/dataset")

# Axes that decide the structural render; scenarios agreeing on all of them
# and on the page index can share one layout pass.
STRUCTURE_AXES = ("layout", "backend", "style")


class DatasetConfig(BaseModel):
    """A run: how many pages, sampled how, written where."""

    model_config = {"extra": "forbid"}

    pages: int = 100
    seed: int = 0
    scale: float = 1.0
    mode: str = "sample"  # "sample" | "stratified"

    # Each rendered page is aged this many ways. The structural render is
    # shared, so extra variants are nearly free.
    degradations_per_page: int = 1

    image_format: str = "png"  # "png" (lossless) | "jpeg" (small)
    jpeg_quality: int = 88

    # {axis: {variant: weight}} -- the only thing you normally edit.
    axes: dict[str, dict[str, float]] = {}


def load_dataset_config(path: str | Path) -> DatasetConfig:
    path = Path(path)
    raw = path.read_text(encoding="utf-8")

    if path.suffix in {".yaml", ".yml"}:
        import yaml

        data = yaml.safe_load(raw) or {}
    else:
        data = json.loads(raw)

    if not isinstance(data, dict):
        raise ValueError(f"{path}: dataset config must be a mapping")
    return DatasetConfig(**data)


def build_space(config: DatasetConfig, space: Optional[ScenarioSpace] = None):
    """Apply the config's weights to the space; unknown names raise."""
    return (space or default_space()).with_weights(config.axes)


# ------------------------------------------------------------------- planning


@dataclass
class PagePlan:
    """One structural render plus the degradations applied to it."""

    page: int
    scenario: Scenario
    degradations: list[Scenario] = field(default_factory=list)


def plan_pages(
    space: ScenarioSpace,
    config: DatasetConfig,
) -> list[PagePlan]:
    """Scenarios for the whole run, grouped by structural render."""
    scenarios = plan(space, config.pages, config.seed, config.mode)
    pages: list[PagePlan] = []

    for scenario in scenarios:
        page = PagePlan(page=scenario.index, scenario=scenario)
        page.degradations.append(scenario)

        # Extra ageings of the same structure, drawn from the same axis.
        # Prefer variants this page has not used yet: ageing one page the
        # same way twice is a wasted sample, not a second sample.
        extra_rng = random.Random(scenario.seed ^ 0x5EED)
        axis = space.axis("degradation")
        eligible = len(axis.eligible(scenario.tags))
        used = {scenario["degradation"].name}

        for variant_index in range(1, config.degradations_per_page):
            variant = axis.sample(extra_rng, scenario.tags)
            for _ in range(8):  # a few tries, then accept the repeat
                if len(used) >= eligible or variant.name not in used:
                    break
                variant = axis.sample(extra_rng, scenario.tags)
            used.add(variant.name)

            page.degradations.append(
                Scenario(
                    index=scenario.index,
                    seed=seed_for(scenario.seed, variant_index),
                    choices={**scenario.choices, "degradation": variant},
                )
            )
        pages.append(page)

    return pages


def flatten(pages: list[PagePlan]) -> list[Scenario]:
    return [scenario for page in pages for scenario in page.degradations]


# ------------------------------------------------------------------ rendering


def build_document(scenario: Scenario) -> Document:
    """Run the layout factory, then check it obeys the corpus rule."""
    factory = scenario["layout"].value
    document = factory(random.Random(scenario.seed))
    assert_plain_text(document)
    return document


def render_options(scenario: Scenario, scale: float) -> tuple[str, dict[str, Any]]:
    """(renderer name, options) for the structural stage -- paper stays off."""
    renderer_name, backend_options = scenario["backend"].value
    style = scenario["style"].value.options_for(renderer_name)

    options: dict[str, Any] = {
        **style,
        **backend_options,
        "scale": scale,
        "seed": scenario.seed,
        # Stage one only; the degradation is applied afterwards.
        "paper": {"enabled": False},
    }
    return renderer_name, options


def _stem(scenario: Scenario, variant_index: int) -> str:
    """Unique per image: two ageings of one page never collide."""
    return f"{scenario.index:06d}-{variant_index}-{scenario['degradation'].name}"


def generate(
    config: DatasetConfig,
    out_dir: Path | str = DEFAULT_OUT_DIR,
    space: Optional[ScenarioSpace] = None,
    save_images: bool = True,
    progress: Optional[Any] = None,
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
                        _stem(scenario, variant_index),
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


def dry_run(
    config: DatasetConfig, space: Optional[ScenarioSpace] = None
) -> dict[str, Any]:
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


def format_distribution(report: dict[str, Any]) -> str:
    """The realised distribution as a table, for ``--dry-run``."""
    lines = [
        f"pages                  {report['pages']}",
        f"images                 {report['images']}",
        f"combinations available {report['combinations_available']}",
    ]
    if "combinations_used" in report:
        lines.append(f"combinations used      {report['combinations_used']}")

    total = report["images"] or 1
    for axis, counts in report["distribution"].items():
        lines.append(f"\n{axis}")
        for name, count in sorted(counts.items(), key=lambda item: -item[1]):
            share = 100 * count / total
            bar = "#" * max(1, round(share / 2))
            lines.append(f"  {name:<26} {count:>7}  {share:5.1f}%  {bar}")

    if report.get("skipped"):
        lines.append("\nskipped")
        for name, reason in report["skipped"].items():
            lines.append(f"  {name}: {reason}")

    return "\n".join(lines)


def read_manifest(path: str | Path) -> Iterator[dict[str, Any]]:
    """Stream ``manifest.jsonl`` back, one entry per image."""
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)
