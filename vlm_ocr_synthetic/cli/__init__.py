"""Command line entry point.

python -m vlm_ocr_synthetic doctor                     # is this environment usable?
python -m vlm_ocr_synthetic list                       # backend status
python -m vlm_ocr_synthetic render --renderer all      # side-by-side check
python -m vlm_ocr_synthetic benchmark --pages 3        # compare the backends
python -m vlm_ocr_synthetic generate --dry-run         # plan a dataset
"""

from __future__ import annotations

from collections.abc import Sequence

from .parser import build_parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


__all__ = ["build_parser", "main"]
