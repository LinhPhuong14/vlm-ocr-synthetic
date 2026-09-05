"""Where things live, on Windows as well as on Linux and macOS.

The only genuinely platform-dependent fact in this repository is where a
virtualenv keeps its interpreter: `bin/python` on POSIX, `Scripts/python.exe`
on Windows. Everything else is `pathlib`, which already does the right thing.

Kept in one module because it is needed from two places -- `tasks.py` at the
repository root and `tools/generate_dataset.py` -- and a wrong answer in either
is a confusing failure ("no interpreter at ...") rather than an obvious one.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

WINDOWS = os.name == "nt"

# Third-party code that is checked in as-is. It keeps its own style, so linting
# and byte-compiling skip it. The six `generators/genalog/` entries that used to
# head this list went with that backend; `augmentations/` is what is left.
# Mirrored by `extend-exclude` in pyproject.toml, which ruff reads directly.
VENDORED = (
    "augmentations/",
    "degradation/blender/vendor/",
)

# One environment, because there is one renderer. `synthdog` and `genalog` had
# entries here until they were deleted -- see `pipeline/config.py::GONE_BACKENDS`
# for what that means for the pages they drew, which are still committed.
VENVS = {
    "html": REPO_ROOT / "generators" / "html" / ".venv",
}


def venv_python(venv: Path | str) -> Path:
    """The interpreter inside a virtualenv, whichever platform made it.

    Checks for the Windows layout by looking on disk rather than by asking the
    *running* platform: a repository can be inspected from WSL while the venvs
    were built by Windows Python, and vice versa. Falling back to this
    platform's convention when neither exists keeps the error message useful.
    """
    venv = Path(venv)
    windows = venv / "Scripts" / "python.exe"
    posix = venv / "bin" / "python"
    if windows.exists():
        return windows
    if posix.exists():
        return posix
    return windows if WINDOWS else posix


def venv_tool(venv: Path | str, name: str) -> Path:
    """An executable installed into a virtualenv, e.g. `ruff`, `synthtiger`."""
    venv = Path(venv)
    if WINDOWS:
        return venv / "Scripts" / f"{name}.exe"
    return venv / "bin" / name


def first_available_python() -> Path:
    """Any built venv, for the tools that only need numpy/opencv/PyYAML.

    Preferred over `sys.executable` because the interpreter running a task
    script is often the bare system Python, which has none of them.
    """
    for venv in VENVS.values():
        candidate = venv_python(venv)
        if candidate.exists():
            return candidate
    return Path(sys.executable)


__all__ = [
    "REPO_ROOT",
    "VENDORED",
    "VENVS",
    "WINDOWS",
    "first_available_python",
    "venv_python",
    "venv_tool",
]
