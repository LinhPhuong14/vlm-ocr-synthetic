from __future__ import annotations

import pytest

from vlm_ocr_synthetic.renderers import get_renderer_class
from vlm_ocr_synthetic.samples import get_sample
from vlm_ocr_synthetic.schemas.document import Document


@pytest.fixture
def invoice() -> Document:
    return get_sample("invoice")


def requires_renderer(name: str):
    """Skip a test when the backend's optional dependencies are missing."""
    try:
        reason = get_renderer_class(name).check_available()
    except Exception as exc:  # pragma: no cover - import failure path
        reason = f"{type(exc).__name__}: {exc}"
    return pytest.mark.skipif(
        reason is not None, reason=f"{name} renderer unavailable: {reason}"
    )
