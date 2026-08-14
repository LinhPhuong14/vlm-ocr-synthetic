"""Render the same documents through every backend and compare them.

Answers the questions you have when choosing a backend for a dataset: how
fast is it, how much ink lands on the page, does it honour the geometry it
was given, and do two backends agree on where things ended up.
"""

from .metrics import (
    count_annotations,
    cross_backend_agreement,
    ink_coverage,
    layout_fidelity,
    luminance_stats,
)
from .report import format_markdown, save_report
from .runner import (
    DEFAULT_OUT_DIR,
    BackendReport,
    BenchmarkCase,
    benchmark_case,
    default_cases,
    run_benchmark,
)

__all__ = [
    "DEFAULT_OUT_DIR",
    "BackendReport",
    "BenchmarkCase",
    "benchmark_case",
    "count_annotations",
    "cross_backend_agreement",
    "default_cases",
    "format_markdown",
    "ink_coverage",
    "layout_fidelity",
    "luminance_stats",
    "run_benchmark",
    "save_report",
]
