"""The shape of one `metadata.jsonl` line, checked where it is written.

Each renderer builds its own dict today, so a key can drift in one of the three
and nothing says so until somebody loads the dataset and finds a field missing
for a fifth of it. This is the one definition, and `validate` is called on the
way out.

The keys and their meanings are **fixed by what already exists**. W1 is a change
of scheduling; renaming or dropping a key would break every committed dataset
and every loader written against them. New keys may be added.

    file_name       the image, relative to the backend's directory
    ground_truth    CORD-style nested label, as a JSON *string*
    text_sequence   flat reading order, for pre-training and OCR scoring
    recipe          all six sampled attributes plus the seed
    boxes           one {kind, text, quad} per drawn field
    framework       which renderer drew it
    layout          which layout it used
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

# Written by the renderers themselves.
RENDERER_KEYS = {"file_name", "ground_truth", "text_sequence", "recipe", "boxes"}
# Added by whatever assembles the dataset.
ASSEMBLY_KEYS = {"framework", "layout"}
REQUIRED = RENDERER_KEYS | ASSEMBLY_KEYS


class RecordError(ValueError):
    """A metadata line is not what a loader will expect."""


def validate(record: dict[str, Any], *, strict: bool = True) -> list[str]:
    """Everything wrong with one record, most important first.

    `strict=False` allows a record straight from a renderer, before `framework`
    and `layout` have been attached.
    """
    problems: list[str] = []
    required = REQUIRED if strict else RENDERER_KEYS
    for key in sorted(required - set(record)):
        problems.append(f"missing key {key!r}")

    name = record.get("file_name")
    if name is not None:
        if not isinstance(name, str) or not name:
            problems.append("file_name must be a non-empty string")
        elif Path(name).is_absolute() or ".." in Path(name).parts:
            # An absolute path here would make the dataset unmovable, and would
            # differ between two machines that produced identical images.
            problems.append(f"file_name must be relative and simple, got {name!r}")

    truth = record.get("ground_truth")
    if truth is not None:
        if not isinstance(truth, str):
            problems.append("ground_truth must be a JSON *string* (Donut reads it directly)")
        else:
            try:
                parsed = json.loads(truth)
            except json.JSONDecodeError as error:
                problems.append(f"ground_truth is not valid JSON: {error}")
            else:
                if "gt_parse" not in parsed:
                    problems.append("ground_truth has no 'gt_parse' key")

    recipe = record.get("recipe")
    if recipe is not None:
        if not isinstance(recipe, dict):
            problems.append("recipe must be a mapping")
        else:
            if "seed" not in recipe:
                problems.append("recipe has no seed, so the image cannot be rebuilt")
            if not recipe.get("attributes"):
                problems.append("recipe has no attributes")

    boxes = record.get("boxes")
    if boxes is not None:
        if not isinstance(boxes, list):
            problems.append("boxes must be a list")
        else:
            for position, box in enumerate(boxes):
                if not isinstance(box, dict) or {"kind", "text", "quad"} - set(box):
                    problems.append(f"boxes[{position}] needs kind, text and quad")
                    break
                quad = box["quad"]
                if not isinstance(quad, list) or len(quad) != 4:
                    problems.append(f"boxes[{position}].quad must be four corners")
                    break
    return problems


def check(record: dict[str, Any], *, strict: bool = True, where: str = "") -> dict[str, Any]:
    """Return the record, or raise naming what is wrong with it."""
    problems = validate(record, strict=strict)
    if problems:
        prefix = f"{where}: " if where else ""
        raise RecordError(prefix + "; ".join(problems))
    return record


def write(records: Iterable[dict[str, Any]], path: Path, *, strict: bool = True) -> int:
    """Write `metadata.jsonl`, validating on the way out.

    Streamed, not accumulated: a run of 100k images must not need all of them in
    memory at once, which is what the sequential driver did.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            check(record, strict=strict, where=str(record.get("file_name", "?")))
            json.dump(record, handle, ensure_ascii=False)
            handle.write("\n")
            written += 1
    return written


def read(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


__all__ = [
    "ASSEMBLY_KEYS",
    "RENDERER_KEYS",
    "REQUIRED",
    "RecordError",
    "check",
    "read",
    "validate",
    "write",
]
