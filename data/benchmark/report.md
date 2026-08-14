# Renderer benchmark

3 page(s) of sample `invoice` per backend, options `{"scale": 1.0}`.
Python 3.14.7 (cpython) on Linux.

| metric | html-flow | html-absolute | synthdog |
| --- | --- | --- | --- |
| seconds/page (median) | 0.2495 | 0.2566 | 0.0271 |
| seconds/page (mean) | 0.2631 | 0.2557 | 0.0259 |
| image size (px) | 1000x1400 | 1000x1400 | 1000x1400 |
| png size (bytes) | 1573131 | 1573313 | 1565237 |
| ink coverage | 0.00659 | 0.00636 | 0.00643 |
| luminance mean | 247.13 | 247.21 | 247.66 |
| luminance stdev | 15.18 | 15.03 | 15.22 |
| blocks annotated | 4 | 4 | 4 |
| cells annotated | 9 | 9 | 9 |
| all boxes present | True | True | True |
| layout fidelity (IoU) | 0.1358 | 1.0 | 0.2559 |
| deterministic | True | True | True |

## Cross-backend geometry agreement

- **html-absolute vs html-flow**: mean IoU 0.1358, min 0.0 over 4 blocks
- **html-absolute vs synthdog**: mean IoU 0.2559, min 0.1026 over 4 blocks
- **html-flow vs synthdog**: mean IoU 0.0462, min 0.0 over 4 blocks

## Paper layer

Both backends share the same paper and degradation settings, so the numbers above differ by layout engine only.

```json
{
  "bleed_through": 0.0,
  "blur": 0.0,
  "color": [
    250,
    249,
    245
  ],
  "enabled": true,
  "fold_columns": 0,
  "fold_jitter": 0.02,
  "fold_rows": 0,
  "fold_softness": 4.0,
  "fold_strength": 0.0,
  "grain": 4.0,
  "pepper": 0.0,
  "salt": 0.0,
  "texture": null,
  "texture_strength": 1.0,
  "vignette": 0.0
}
```
