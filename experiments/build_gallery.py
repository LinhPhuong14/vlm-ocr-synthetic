"""Rebuild data/samples: one preview per sample x preset.

    python experiments/build_gallery.py

Previews are JPEG so they are small enough to keep in git; the lossless
PNG plus annotations come back with `python -m vlm_ocr_synthetic render`.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vlm_ocr_synthetic.renderers import (  # noqa: E402
    RendererUnavailable,
    get_renderer,
    load_config,
)
from vlm_ocr_synthetic.samples import get_sample  # noqa: E402

OUT_DIR = Path("data/samples")

# (sample, preset, output stem)
GALLERY = (
    ("receipt_vn", "configs/synthdog_receipt_vn.yaml", "receipt_vn-synthdog"),
    ("receipt_vn", "configs/html_receipt_vn.yaml", "receipt_vn-html"),
    # Stage one on its own: the structure before any paper is applied.
    ("receipt_vn", "configs/html_receipt_vn.yaml", "receipt_vn-html-structure"),
    ("invoice", "configs/synthdog_default.yaml", "invoice-synthdog"),
    ("invoice", "configs/html_flow.yaml", "invoice-html-flow"),
    ("invoice", "configs/html_scanned.yaml", "invoice-html-scanned"),
    ("invoice", "configs/html_folded.yaml", "invoice-html-folded"),
)


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for sample, config_path, stem in GALLERY:
        name, options = load_config(config_path)
        if stem.endswith("-structure"):
            options = {**options, "paper": {"enabled": False}}
        try:
            result = get_renderer(name, options).render(get_sample(sample))
        except RendererUnavailable as exc:
            print(f"[skip] {stem}: {exc}")
            continue

        image_path, annotation_path = result.save(
            OUT_DIR, stem, image_format="jpeg"
        )
        size_kb = image_path.stat().st_size / 1024
        print(f"[ok] {stem:<24} {size_kb:6.0f} KB  {result.image.size}")
        print(f"     {annotation_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
