"""Turning a config into a list of scenarios, before anything renders.

A page is planned once and aged several ways; that grouping is what lets
the pipeline reuse one structural render."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from ..corpus import assert_plain_text
from ..schemas.document import Document
from ..variations import ScenarioSpace
from ..variations.space import Scenario, plan, seed_for
from .config import DatasetConfig

# Axes that decide the structural render; scenarios agreeing on all of them
# and on the page index can share one layout pass.
STRUCTURE_AXES = ("layout", "backend", "style")


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


def page_stem(scenario: Scenario, variant_index: int) -> str:
    """Unique per image: two ageings of one page never collide."""
    return f"{scenario.index:06d}-{variant_index}-{scenario['degradation'].name}"
