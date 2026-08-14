"""Dataset generation: plan scenarios, render them, write a manifest.

The loop is shaped by one fact: paper is a stage *after* the structural
render, so a page is laid out once and aged ``degradations_per_page``
times. For the browser backend that turns a ~0.2 s layout into ~0.01 s per
extra variant.
"""

from .config import DEFAULT_OUT_DIR, DatasetConfig, build_space, load_dataset_config
from .generator import dry_run, generate
from .manifest import format_distribution, read_manifest
from .planner import (
    PagePlan,
    build_document,
    flatten,
    page_stem,
    plan_pages,
    render_options,
)

__all__ = [
    "DEFAULT_OUT_DIR",
    "DatasetConfig",
    "PagePlan",
    "build_document",
    "build_space",
    "dry_run",
    "flatten",
    "format_distribution",
    "generate",
    "load_dataset_config",
    "page_stem",
    "plan_pages",
    "read_manifest",
    "render_options",
]
