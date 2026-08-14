"""Render the same documents through every backend and compare them.

Answers the questions you actually have when choosing a backend for a
dataset: how fast is it, how much ink lands on the page, does it honour the
geometry it was given, and do two backends agree on where things ended up.

Images and annotations are written under the output directory (``data/``
by default) so the numbers can be eyeballed, and the report is saved as
both JSON and Markdown.
"""

from __future__ import annotations

import json
import platform
import statistics
import sys
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable, Optional

from .renderers import RendererUnavailable, get_renderer, renderer_names
from .samples import get_sample
from .schemas.document import Document
from .schemas.render import RenderResult

DEFAULT_OUT_DIR = Path("data/benchmark")
INK_THRESHOLD = 128  # a pixel darker than this counts as ink


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


def default_cases(options: Optional[dict[str, Any]] = None) -> list[BenchmarkCase]:
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
    layout_fidelity: Optional[float]
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


# ------------------------------------------------------------------ metrics


def ink_coverage(image) -> float:
    """Fraction of pixels dark enough to be ink."""
    histogram = image.convert("L").histogram()
    dark = sum(histogram[:INK_THRESHOLD])
    total = sum(histogram)
    return dark / total if total else 0.0


def luminance_stats(image) -> dict[str, float]:
    """Mean and spread of brightness -- how 'papery' the sheet looks."""
    grayscale = image.convert("L")
    histogram = grayscale.histogram()
    total = sum(histogram)
    if not total:
        return {"mean": 0.0, "stdev": 0.0}

    mean = sum(value * count for value, count in enumerate(histogram)) / total
    variance = (
        sum(count * (value - mean) ** 2 for value, count in enumerate(histogram)) / total
    )
    return {"mean": round(mean, 2), "stdev": round(variance**0.5, 2)}


def count_annotations(document: Document) -> tuple[int, int, bool]:
    """(blocks, cells, every box present)."""
    blocks = len(document.blocks)
    cells = 0
    complete = True

    for block in document.blocks:
        complete = complete and block.bbox is not None
        if block.table is not None:
            for row in block.table.rows:
                for cell in row.cells:
                    cells += 1
                    complete = complete and cell.bbox is not None

    return blocks, cells, complete


def layout_fidelity(source: Document, rendered: Document) -> Optional[float]:
    """Mean IoU between requested and achieved block geometry.

    ``None`` when the source document pinned nothing, which is the normal
    case for flow layouts -- there is no requested geometry to honour.
    """
    scores = [
        want.bbox.iou(got.bbox)
        for want, got in zip(source.blocks, rendered.blocks)
        if want.bbox is not None and got.bbox is not None
    ]
    return round(statistics.fmean(scores), 4) if scores else None


def cross_backend_agreement(
    left: Document, right: Document
) -> Optional[dict[str, float]]:
    """How closely two backends place the same blocks."""
    scores: list[float] = []
    for a, b in zip(left.blocks, right.blocks):
        if a.bbox is not None and b.bbox is not None:
            scores.append(a.bbox.iou(b.bbox))

    if not scores:
        return None
    return {
        "mean_iou": round(statistics.fmean(scores), 4),
        "min_iou": round(min(scores), 4),
        "blocks_compared": len(scores),
    }


def _timing_summary(timings: list[float]) -> dict[str, float]:
    return {
        "mean": round(statistics.fmean(timings), 4),
        "median": round(statistics.median(timings), 4),
        "min": round(min(timings), 4),
        "max": round(max(timings), 4),
    }


# ---------------------------------------------------------------- the runner


def benchmark_case(
    case: BenchmarkCase,
    documents: list[Document],
    out_dir: Optional[Path] = None,
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
                    result.save(
                        out_dir, f"preview-{case.label}", image_format="jpeg"
                    )

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
    documents: Optional[Iterable[Document]] = None,
    pages: int = 3,
    sample: str = "invoice",
    options: Optional[dict[str, Any]] = None,
    backends: Optional[list[str]] = None,
    cases: Optional[list[BenchmarkCase]] = None,
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
            scores = cross_backend_agreement(
                last_documents[left], last_documents[right]
            )
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


# ------------------------------------------------------------------ reporting

_ROWS: tuple[tuple[str, str], ...] = (
    ("seconds/page (median)", "seconds_per_page.median"),
    ("seconds/page (mean)", "seconds_per_page.mean"),
    ("image size (px)", "image_size"),
    ("png size (bytes)", "png_bytes"),
    ("ink coverage", "ink_coverage"),
    ("luminance mean", "luminance.mean"),
    ("luminance stdev", "luminance.stdev"),
    ("blocks annotated", "blocks"),
    ("cells annotated", "cells"),
    ("all boxes present", "boxes_complete"),
    ("layout fidelity (IoU)", "layout_fidelity"),
    ("deterministic", "deterministic"),
)


def _lookup(entry: dict[str, Any], path: str) -> Any:
    value: Any = entry
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    if isinstance(value, list):
        return "x".join(str(part) for part in value)
    return "-" if value is None else value


def format_markdown(report: dict[str, Any]) -> str:
    """A table a human can read in a PR diff."""
    backends = report["backends"]
    if not backends:
        return "# Renderer benchmark\n\nNo backend was available.\n"

    names = [entry["label"] for entry in backends]
    settings, environment = report["settings"], report["environment"]

    lines = [
        "# Renderer benchmark",
        "",
        f"{settings['pages']} page(s) of sample `{settings['sample']}` per backend, "
        f"options `{json.dumps(settings['options'], sort_keys=True)}`.",
        f"Python {environment['python']} ({environment['implementation']}) "
        f"on {environment['platform']}.",
        "",
        "| metric | " + " | ".join(names) + " |",
        "| --- | " + " | ".join("---" for _ in names) + " |",
    ]

    for label, path in _ROWS:
        cells = [str(_lookup(entry, path)) for entry in backends]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")

    if report.get("agreement"):
        lines += ["", "## Cross-backend geometry agreement", ""]
        for pair, scores in report["agreement"].items():
            lines.append(
                f"- **{pair}**: mean IoU {scores['mean_iou']}, "
                f"min {scores['min_iou']} over {scores['blocks_compared']} blocks"
            )

    if report.get("skipped"):
        lines += ["", "## Skipped", ""]
        for name, reason in report["skipped"].items():
            lines.append(f"- `{name}`: {reason}")

    paper = next(
        (entry["metadata"].get("paper") for entry in backends if entry["metadata"]),
        None,
    )
    if paper:
        lines += [
            "",
            "## Paper layer",
            "",
            "Both backends share the same paper and degradation settings, so the "
            "numbers above differ by layout engine only.",
            "",
            "```json",
            json.dumps(paper, indent=2, sort_keys=True),
            "```",
        ]

    return "\n".join(lines) + "\n"


def save_report(report: dict[str, Any], out_dir: Path | str) -> tuple[Path, Path]:
    """Write ``report.json`` and ``report.md``; returns both paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "report.json"
    markdown_path = out_dir / "report.md"

    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    markdown_path.write_text(format_markdown(report), encoding="utf-8")
    return json_path, markdown_path
