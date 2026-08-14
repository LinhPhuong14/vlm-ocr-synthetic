# vlm-ocr-synthetic

Synthetic document pages for VLM / OCR training, with **interchangeable render
backends**. A page is described once as a `Document`; every backend consumes
that same description and returns an image plus ground-truth boxes:

| backend    | how it draws                              | good for |
| ---------- | ----------------------------------------- | -------- |
| `synthdog` | Pillow paints the page directly           | exact-by-construction boxes, scan-like noise |
| `html`     | HTML/CSS laid out in chromium, screenshot | realistic typography and layout, boxes read off the DOM |

## Layout

```
vlm_ocr_synthetic/
├── schemas/            # Document / blocks / tables / bboxes + RenderConfig, RenderResult
├── renderers/
│   ├── base.py         # BaseRenderer: the contract every backend implements
│   ├── __init__.py     # lazy registry: get_renderer("synthdog" | "html")
│   ├── synthdog/       # Pillow rasteriser (fonts.py, renderer.py)
│   └── html/           # html_builder.py, backends.py (screenshot engines), templates/
├── samples/            # ready-made documents (invoice, ...)
└── cli.py              # python -m vlm_ocr_synthetic
configs/                # one YAML per backend preset
tests/                  # test_renderers.py runs the same suite against every backend
experiments/            # scratch scripts
outputs/                # rendered pages (git-ignored)
```

Backends are imported lazily, so a missing browser never breaks synthdog and a
missing Pillow never breaks the registry.

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"        # or ".[synthdog]" / ".[html]" / ".[dev]"
playwright install chromium    # html backend only; skip if chromium is already provisioned
```

If chromium lives somewhere non-standard, point at it with
`VLM_OCR_CHROMIUM_PATH=/path/to/chromium` or `executable_path:` in the config.

## Use

```bash
python -m vlm_ocr_synthetic list                       # which backends are usable, and why not
python -m vlm_ocr_synthetic render -r all              # render the sample with both
python -m vlm_ocr_synthetic render -r html -c configs/html_flow.yaml -o outputs/
python -m vlm_ocr_synthetic render -r synthdog -d my_doc.json --scale 2.0
```

Each run writes `outputs/<backend>/<stem>.png` and `<stem>.json` (the document
with every bbox filled in).

```python
from vlm_ocr_synthetic.renderers import get_renderer
from vlm_ocr_synthetic.samples import get_sample

document = get_sample("invoice")
for name in ("synthdog", "html"):
    result = get_renderer(name, {"scale": 2.0}).render(document)
    result.save(f"outputs/{name}")
```

## Conventions

- **Bounding boxes are always in document space**, never pixels: a box is valid
  for any `scale`. Multiply by `scale` (reported in `result.metadata`) for pixel
  coordinates.
- **Input bboxes are optional.** `synthdog` and `html --layout flow` lay blocks
  out themselves and fill the boxes in; `html --layout absolute` pins each block
  to the bbox you supply, which makes the two backends directly comparable.
- **Configs are strict.** Unknown keys in a YAML config raise instead of being
  ignored.

## Test

```bash
pytest                  # whole suite
pytest -m "not slow"    # schema/registry/markup only, no rendering
pytest -k html          # one backend
```

`tests/test_renderers.py` is parametrised over the registry: both backends must
satisfy the same contract (image size, non-blank page, a bbox for every block
and table cell, non-overlapping cells, deterministic output). A backend whose
dependencies are missing is **skipped with a reason**, never silently passed.

## Add a backend

1. Subclass `BaseRenderer`, set `name` / `config_model`, implement `render()`
   and `check_available()`.
2. Register it: `register_renderer("mine", "my_pkg.renderer:MyRenderer")` (or add
   it to `_REGISTRY`).

The shared contract suite picks it up automatically.
