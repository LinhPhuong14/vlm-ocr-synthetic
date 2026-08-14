"""Render the same document with every available backend, side by side.

    python experiments/render_sample.py --out outputs/compare
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vlm_ocr_synthetic.renderers import (  # noqa: E402
    RendererUnavailable,
    get_renderer,
    renderer_names,
)
from vlm_ocr_synthetic.samples import get_sample  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", default="invoice")
    parser.add_argument("--out", default="outputs/compare")
    parser.add_argument("--scale", type=float, default=1.0)
    args = parser.parse_args()

    document = get_sample(args.sample)
    print(f"document: {len(document.blocks)} blocks, "
          f"{document.page_width}x{document.page_height}")

    for name in renderer_names():
        try:
            renderer = get_renderer(name, {"scale": args.scale})
            result = renderer.render(document)
        except RendererUnavailable as exc:
            print(f"[skip] {exc}")
            continue

        image_path, annotation_path = result.save(Path(args.out) / name, args.sample)
        print(f"[ok] {name}: {image_path}")
        for block in result.document.blocks:
            print(f"       {block.block_type:<14} {block.bbox}")
        print(f"       annotation: {annotation_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
