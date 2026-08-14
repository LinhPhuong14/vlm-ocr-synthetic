"""Running the comparison: one case per column of the report."""

from __future__ import annotations

import platform
import statistics
import sys
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any

from ..renderers import RendererUnavailable, get_renderer, renderer_names
from ..samples import get_sample
from ..schemas.document import Document
from ..schemas.render import RenderResult
from .metrics import (
    count_annotations,
    cross_backend_agreement,
    ink_coverage,
    layout_fidelity,
    luminance_stats,
)

DEFAULT_OUT_DIR = Path("data/benchmark")


def _timing_summary(timings: list[float]) -> dict[str, float]:
    return {
        "mean": round(statistics.fmean(timings), 4),
        "median": round(statistics.median(timings), 4),
        "min": round(min(timings), 4),
        "max": round(max(timings), 4),
    }


@dataclass(frozen=True)
class BenchmarkCase:
    """One column of the report: a backend plus the options it ran with.

    The html backend appears twice by default -- ``flow`` is how you would
    generate varied training pages, ``absolute`` pins the same geometry
    synthdog uses, which is the only setting where a cross-backend IoU
    means anything.
    """

    label: str
    renderer: str
    options: dict[str, Any] = field(default_factory=dict)


def default_cases(options: dict[str, Any] | None = None) -> list[BenchmarkCase]:
    base = dict(options or {})
    cases: list[BenchmarkCase] = []

    for name in renderer_names():
        if name == "html":
            cases.append(BenchmarkCase("html-flow", name, {**base, "layout": "flow"}))
            cases.append(
                BenchmarkCase("html-absolute", name, {**base, "layout": "absolute"})
            )
        else:
            cases.append(BenchmarkCase(name, name, dict(base)))

    return cases


@dataclass
class BackendReport:
    label: str
    renderer: str
    pages: int
    seconds_per_page: dict[str, float]
    image_size: list[int]
    png_bytes: int
    ink_coverage: float
    luminance: dict[str, float]
    blocks: int
    cells: int
    boxes_complete: bool
    layout_fidelity: float | None
    deterministic: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "renderer": self.renderer,
            "pages": self.pages,
            "seconds_per_page": self.seconds_per_page,
            "image_size": self.image_size,
            "png_bytes": self.png_bytes,
            "ink_coverage": self.ink_coverage,
            "luminance": self.luminance,
            "blocks": self.blocks,
            "cells": self.cells,
            "boxes_complete": self.boxes_complete,
            "layout_fidelity": self.layout_fidelity,
            "deterministic": self.deterministic,
            "metadata": self.metadata,
        }


# ---------------------------------------------------------------- the runner


def benchmark_case(
    case: BenchmarkCase,
    documents: list[Document],
    out_dir: Path | None = None,
    save_images: bool = True,
) -> tuple[BackendReport, list[RenderResult]]:
    """Render every document once, timing each page, and save the output."""
    renderer = get_renderer(case.renderer, case.options)

    timings: list[float] = []
    results: list[RenderResult] = []

    # session() keeps a browser alive across pages, so the timings measure
    # rendering rather than process startup.
    with renderer.session():
        for index, document in enumerate(documents):
            started = perf_counter()
            result = renderer.render(document)
            timings.append(perf_counter() - started)
            results.append(result)

            if save_images and out_dir is not None:
                result.save(Path(out_dir) / case.label, f"page_{index:03d}")
                if index == 0:
                    # A JPEG small enough to keep in git next to the report.
                    result.save(out_dir, f"preview-{case.label}", image_format="jpeg")

        repeat = renderer.render(documents[0])

    last = results[-1]
    blocks, cells, complete = count_annotations(last.document)
    png_path = None
    if save_images and out_dir is not None:
        png_path = Path(out_dir) / case.label / f"page_{len(documents) - 1:03d}.png"

    report = BackendReport(
        label=case.label,
        renderer=case.renderer,
        pages=len(documents),
        seconds_per_page=_timing_summary(timings),
        image_size=list(last.image.size),
        png_bytes=png_path.stat().st_size if png_path and png_path.exists() else 0,
        ink_coverage=round(ink_coverage(last.image), 5),
        luminance=luminance_stats(last.image),
        blocks=blocks,
        cells=cells,
        boxes_complete=complete,
        layout_fidelity=layout_fidelity(documents[-1], last.document),
        deterministic=(
            repeat.image.tobytes() == results[0].image.tobytes()
            and repeat.document == results[0].document
        ),
        metadata=dict(last.metadata),
    )
    return report, results


def run_benchmark(
    documents: Iterable[Document] | None = None,
    pages: int = 3,
    sample: str = "invoice",
    options: dict[str, Any] | None = None,
    backends: list[str] | None = None,
    cases: list[BenchmarkCase] | None = None,
    out_dir: Path | str = DEFAULT_OUT_DIR,
    save_images: bool = True,
) -> dict[str, Any]:
    """Benchmark every available backend and return the report."""
    out_dir = Path(out_dir)
    documents = list(documents) if documents is not None else [get_sample(sample)] * pages
    if not documents:
        raise ValueError("benchmark needs at least one document")

    cases = cases if cases is not None else default_cases(options)
    if backends is not None:
        cases = [case for case in cases if case.renderer in backends]

    reports: list[dict[str, Any]] = []
    skipped: dict[str, str] = {}
    last_documents: dict[str, Document] = {}

    for case in cases:
        try:
            report, results = benchmark_case(case, documents, out_dir, save_images)
        except RendererUnavailable as exc:
            skipped[case.label] = str(exc)
            continue

        reports.append(report.as_dict())
        last_documents[case.label] = results[-1].document

    agreement = {}
    names = sorted(last_documents)
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            scores = cross_backend_agreement(last_documents[left], last_documents[right])
            if scores:
                agreement[f"{left} vs {right}"] = scores

    return {
        "environment": {
            "python": platform.python_version(),
            "implementation": sys.implementation.name,
            "platform": platform.system(),
        },
        "settings": {
            "pages": len(documents),
            "sample": sample,
            "options": options or {},
        },
        "backends": reports,
        "skipped": skipped,
        "agreement": agreement,
    }
