"""Apply a whole degradation chain to directories of already-rendered pages.

    python tools/augment_samples.py --synthdog <dir> --genalog <dir> -o /tmp/aged

Writes one before/after pair per page plus a contact sheet, so a *chain* can
be judged by looking rather than by reading parameters. For judging one model
at a time, use `tools/degradation_showcase.py` instead.

The chains here are hand-written, unlike the ones in
`rulebase/rules/augmentation.yaml` that the renderers actually use: this tool
exists to try a chain on pages you already have, including pages that did not
come from this repository.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from degradation import DEFAULT_CHAIN, apply_chain  # noqa: E402

# One chain per source: receipts are thermal prints that get crumpled in a
# pocket; genalog pages are office documents that get photocopied and bound.
CHAINS = {
    # A table is a small, sparse image: page-sized settings overwhelm it, and
    # bleed-through is worse than useless -- the mirrored text lands in the
    # empty cells and reads as a double exposure rather than as ink. What is
    # left is a printed table that went through a copier.
    "tables": [
        ("ink_degradation", {"level": 3}),
        ("blur_zones", {"radius": 1.1, "zones": 2, "coverage": 0.18}),
        ("shadow_binding", {"border": "top", "distance_ratio": 0.07, "intensity": 0.3}),
    ],
    "synthdog": [
        ("ink_degradation", {"level": 6}),
        ("blur_zones", {"radius": 1.6, "zones": 2, "coverage": 0.18}),
        ("shadow_binding", {"border": "bottom", "distance_ratio": 0.10, "intensity": 0.4}),
    ],
    "genalog": [
        ("ink_degradation", {"level": 4}),
        ("bleed_through", {"intensity": 0.6, "nb_iter": 8}),
        ("blur_zones", {"radius": 2.0, "zones": 3, "coverage": 0.22}),
        ("shadow_binding", {"border": "left", "distance_ratio": 0.14, "intensity": 0.5}),
        ("holes", {"count": 2, "placement": "border", "size_ratio": 0.035}),
    ],
}


def collect(directory: Path, limit: int) -> list[Path]:
    files = sorted(
        p for p in directory.rglob("*") if p.suffix.lower() in {".png", ".jpg", ".jpeg"}
    )
    return files[:limit]


def contact_sheet(pairs: list[tuple[np.ndarray, np.ndarray]], width: int = 320):
    tiles = []
    for before, after in pairs:
        row = []
        for image in (before, after):
            scale = width / image.shape[1]
            row.append(cv2.resize(image, (width, int(image.shape[0] * scale))))
        height = max(t.shape[0] for t in row)
        row = [
            cv2.copyMakeBorder(t, 0, height - t.shape[0], 0, 8, cv2.BORDER_CONSTANT, value=(255,) * 3)
            for t in row
        ]
        tiles.append(np.hstack(row))

    height = max(t.shape[0] for t in tiles)
    tiles = [
        cv2.copyMakeBorder(t, 0, height - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255,) * 3)
        for t in tiles
    ]
    return np.hstack(tiles)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--synthdog", type=Path, help="directory of synthdog renders")
    parser.add_argument("--genalog", type=Path, help="directory of genalog renders")
    parser.add_argument("--tables", type=Path,
                        help="directory of table renders, e.g. data/tables60/img")
    parser.add_argument("-n", "--per-source", type=int, default=5)
    parser.add_argument("-o", "--out", type=Path, default=Path("samples/degradation"))
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    manifest = []
    sheets = {}

    for source in ("synthdog", "genalog", "tables"):
        directory = getattr(args, source.replace("-", "_"))
        if directory is None or not directory.exists():
            print(f"[skip] {source}: no directory")
            continue

        chain = CHAINS.get(source, DEFAULT_CHAIN)
        pairs = []
        for index, path in enumerate(collect(directory, args.per_source)):
            before = cv2.imread(str(path), cv2.IMREAD_COLOR)
            if before is None:
                continue
            after = apply_chain(before, chain, seed=args.seed + index)

            stem = f"{source}_{index:02d}"
            cv2.imwrite(str(args.out / f"{stem}-before.jpg"), before, [cv2.IMWRITE_JPEG_QUALITY, 88])
            cv2.imwrite(str(args.out / f"{stem}-after.jpg"), after, [cv2.IMWRITE_JPEG_QUALITY, 88])
            pairs.append((before, after))

            manifest.append({
                "source": source,
                "origin": str(path),
                "before": f"{stem}-before.jpg",
                "after": f"{stem}-after.jpg",
                "size": [before.shape[1], before.shape[0]],
                "chain": [name for name, _ in chain],
                "seed": args.seed + index,
            })
            print(f"[ok] {stem}  {before.shape[1]}x{before.shape[0]}  {[n for n, _ in chain]}")

        if pairs:
            sheets[source] = contact_sheet(pairs)
            cv2.imwrite(str(args.out / f"contact-{source}.jpg"), sheets[source],
                        [cv2.IMWRITE_JPEG_QUALITY, 86])

    (args.out / "manifest.json").write_text(
        json.dumps({"chains": {k: [[n, o] for n, o in v] for k, v in CHAINS.items()},
                    "images": manifest}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\n{len(manifest)} pairs -> {args.out}")
    return 0 if manifest else 1


if __name__ == "__main__":
    raise SystemExit(main())
