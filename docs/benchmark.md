# Benchmarking the backends

## Benchmark

```bash
python -m vlm_ocr_synthetic benchmark --pages 3          # -> data/benchmark/
python -m vlm_ocr_synthetic benchmark --no-paper         # measure without paper
python -m vlm_ocr_synthetic benchmark -r synthdog -n 20
```

It renders the same documents through every case, saves **every image it
generates** under `data/benchmark/<case>/`, and writes `report.md` +
`report.json` next to them. The committed
[`data/benchmark/report.md`](../data/benchmark/report.md) is the current numbers.

The html backend appears twice, because comparing it to synthdog only makes
sense when both are asked for the same geometry:

| case | what it is |
| ---- | ---------- |
| `synthdog` | Pillow rasteriser |
| `html-flow` | browser, CSS decides the layout |
| `html-absolute` | browser, blocks pinned to the input bboxes |

Measured: seconds/page (median and mean), image and PNG size, ink coverage,
luminance mean/stdev, blocks and cells annotated, whether every box is present,
**layout fidelity** (mean IoU between requested and achieved geometry),
determinism, and pairwise cross-backend IoU.

Two findings worth knowing before you pick a backend:

- **synthdog renders ~10x faster per page.** The browser is one process for a
  whole batch — `render_many()` and the benchmark keep chromium alive via
  `renderer.session()` — but a page still costs ~0.25 s against ~0.03 s.
- **The two backends report boxes by different conventions.** `html-absolute`
  scores 1.0 on layout fidelity because a pinned block *is* its CSS box;
  synthdog scores ~0.26 on the same document because it reports the **tight ink
  extent** rather than the requested slot. Neither is wrong — but if you mix
  backends in one dataset, the boxes are not describing the same thing.

## What is in `data/`

Every image any command generates lands under `data/`:

```
data/<backend>/page.png            # python -m vlm_ocr_synthetic render
data/samples/*.jpg + *.json        # python experiments/build_gallery.py
data/benchmark/<case>/page_*.png   # python -m vlm_ocr_synthetic benchmark
data/benchmark/report.md + .json
data/benchmark/preview-<case>.jpg
```

Full-resolution PNGs are regenerable and large — paper grain is close to
incompressible, so a 1000x1400 page is ~1.5 MB. What git tracks is the small,
reviewable subset: the JPEG previews (~200 KB each at full resolution), their
annotations, and the benchmark report. Everything else under `data/` is ignored.
