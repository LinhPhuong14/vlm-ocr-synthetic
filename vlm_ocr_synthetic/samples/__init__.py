"""Ready-made documents so any backend can be exercised with one command."""

from typing import Callable

from ..schemas.document import Document
from .invoice import build_invoice_document, build_invoice_table

SAMPLES: dict[str, Callable[[], Document]] = {
    "invoice": build_invoice_document,
}


def sample_names() -> list[str]:
    return sorted(SAMPLES)


def get_sample(name: str) -> Document:
    try:
        factory = SAMPLES[name]
    except KeyError:
        raise KeyError(
            f"unknown sample '{name}'; available: {', '.join(sample_names())}"
        ) from None
    return factory()


__all__ = [
    "SAMPLES",
    "build_invoice_document",
    "build_invoice_table",
    "get_sample",
    "sample_names",
]
