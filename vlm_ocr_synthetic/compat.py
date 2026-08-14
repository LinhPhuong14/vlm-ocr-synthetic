"""Interpreter and dependency compatibility.

Python 3.14 is the reason this module exists. Several dependencies only
gained cp314 wheels at a specific version; below that floor pip silently
falls back to building from source, which either fails or takes minutes.
The floors below were established by installing each candidate on a real
3.14 interpreter -- see the ``note`` on each entry.

The same data drives three things, so they cannot drift apart:
the dependency pins in ``pyproject.toml``, the ``doctor`` CLI command, and
``tests/test_environment.py``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as installed_version
from typing import Literal

# The interpreter this project is tested against.
MIN_PYTHON = (3, 10)

# Floors that only apply from this version of Python onwards.
PY_314 = (3, 14)


@dataclass(frozen=True)
class Requirement:
    """A dependency, with the floor Python 3.14 forces on it."""

    distribution: str
    min_for_py314: str | None
    optional: bool
    note: str


REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        "pydantic",
        "2.12",
        optional=False,
        note="2.11 and older have no cp314 wheel for pydantic-core and fail to install",
    ),
    Requirement(
        "PyYAML",
        "6.0.3",
        optional=False,
        note="first release with a cp314 wheel",
    ),
    Requirement(
        "Pillow",
        "11.3",
        optional=True,
        note="first release with a cp314 wheel; needed by both renderers",
    ),
    Requirement(
        "Jinja2",
        None,
        optional=True,
        note="pure Python, no interpreter-specific build",
    ),
    Requirement(
        "playwright",
        "1.52",
        optional=True,
        note="1.49 and older pin greenlet==3.1.1, which has no cp314 wheel",
    ),
)

Status = Literal["ok", "too_old", "missing", "not_installed"]


def parse_version(text: str) -> tuple[int, int, int]:
    """Loose dotted-numeric parse; good enough to compare floors."""
    parts: list[int] = []
    for chunk in text.split(".")[:3]:
        digits = "".join(ch for ch in chunk if ch.isdigit())
        parts.append(int(digits) if digits else 0)
    while len(parts) < 3:
        parts.append(0)
    return parts[0], parts[1], parts[2]


def python_is_at_least(version: tuple[int, ...]) -> bool:
    return sys.version_info[: len(version)] >= version


def check_dependency(requirement: Requirement) -> dict[str, object]:
    """Report one dependency: what is installed, what this interpreter needs."""
    try:
        found = installed_version(requirement.distribution)
    except PackageNotFoundError:
        found = None

    floor = requirement.min_for_py314 if python_is_at_least(PY_314) else None

    if found is None:
        status: Status = "not_installed" if requirement.optional else "missing"
    elif floor and parse_version(found) < parse_version(floor):
        status = "too_old"
    else:
        status = "ok"

    return {
        "distribution": requirement.distribution,
        "installed": found,
        "required": floor,
        "optional": requirement.optional,
        "status": status,
        "note": requirement.note,
    }


def check_dependencies() -> list[dict[str, object]]:
    return [check_dependency(requirement) for requirement in REQUIREMENTS]


def imaging_report() -> dict[str, object]:
    """Pillow's FreeType stack -- the pygame.freetype replacement."""
    try:
        from PIL import Image, features
    except ImportError as exc:
        return {"available": False, "reason": str(exc)}

    return {
        "available": True,
        "pillow": Image.__version__,
        "freetype": features.version("freetype2"),
        # raqm gives complex-script shaping (Vietnamese diacritics, Arabic, ...)
        "raqm": features.version("raqm"),
    }


def environment_report() -> dict[str, object]:
    """Everything ``python -m vlm_ocr_synthetic doctor`` prints."""
    from .renderers import available_renderers

    return {
        "python": {
            "version": ".".join(str(part) for part in sys.version_info[:3]),
            "implementation": sys.implementation.name,
            "executable": sys.executable,
            "supported": python_is_at_least(MIN_PYTHON),
            "minimum": ".".join(str(part) for part in MIN_PYTHON),
        },
        "renderers": available_renderers(),
        "imaging": imaging_report(),
        "dependencies": check_dependencies(),
    }


def problems() -> list[str]:
    """Human-readable blockers; empty means the environment is usable."""
    issues: list[str] = []

    if not python_is_at_least(MIN_PYTHON):
        issues.append(
            f"Python {'.'.join(str(p) for p in MIN_PYTHON)}+ required, "
            f"running {sys.version.split()[0]}"
        )

    for entry in check_dependencies():
        name, status = entry["distribution"], entry["status"]
        if status == "missing":
            issues.append(f"{name} is not installed (required)")
        elif status == "too_old":
            issues.append(
                f"{name} {entry['installed']} is too old for Python "
                f"{sys.version_info.major}.{sys.version_info.minor}: "
                f"need >= {entry['required']} ({entry['note']})"
            )

    return issues
