from __future__ import annotations

import pytest

from vlm_ocr_synthetic.samples import get_sample
from vlm_ocr_synthetic.schemas.document import Document


@pytest.fixture
def invoice() -> Document:
    return get_sample("invoice")
