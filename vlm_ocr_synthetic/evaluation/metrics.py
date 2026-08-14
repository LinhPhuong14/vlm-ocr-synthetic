"""What we measure on a rendered page.

Pure functions over an image or a document, so they can be reused for
dataset QA, not just for the backend comparison.
"""

from __future__ import annotations

import statistics

from ..schemas.document import Document

INK_THRESHOLD = 128  # a pixel darker than this counts as ink


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


def layout_fidelity(source: Document, rendered: Document) -> float | None:
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


def cross_backend_agreement(left: Document, right: Document) -> dict[str, float] | None:
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
