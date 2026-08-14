"""Reading a finished dataset back, and reporting a planned one.

``manifest.jsonl`` is the entry point to a dataset: one line per image,
carrying the scenario and seed that produced it."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any


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
