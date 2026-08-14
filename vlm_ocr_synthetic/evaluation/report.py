"""The benchmark report: a table a human can read in a PR diff."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
