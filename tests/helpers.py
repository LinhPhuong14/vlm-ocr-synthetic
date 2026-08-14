"""Shared test helpers.

Lives outside conftest.py so tests in subdirectories can import it: the
decorator is applied at import time, which a fixture cannot do.
"""

from __future__ import annotations

import pytest

from vlm_ocr_synthetic.renderers import get_renderer_class


def requires_renderer(name: str):
    """Skip a test when the backend's optional dependencies are missing."""
    try:
        reason = get_renderer_class(name).check_available()
    except Exception as exc:  # pragma: no cover - import failure path
        reason = f"{type(exc).__name__}: {exc}"
    return pytest.mark.skipif(
        reason is not None, reason=f"{name} renderer unavailable: {reason}"
    )
