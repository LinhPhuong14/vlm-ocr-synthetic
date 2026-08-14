# vlm-ocr-synthetic

Synthetic document pages for training and evaluating VLM / OCR models.

A page is described **once** as a `Document` — blocks, tables, optional
positions — and any render backend can turn that description into an image
plus pixel-accurate ground truth. Two backends ship today:

| backend    | how it draws                                | strengths | costs |
| ---------- | ------------------------------------------- | --------- | ----- |
| `synthdog` | Pillow paints the page directly             | boxes exact by construction, scan-like noise, no browser needed | typography is basic, layout is simple stacking |
| `html`     | HTML/CSS laid out in chromium, screenshotted | real typography, tables, wrapping and CSS layout; boxes read off the DOM | needs a chromium binary, slower per page |

Because both consume the same `Document` and return the same `RenderResult`,
you can render one document through both and compare, or mix backends within a
single dataset.

---

## Layout

```
vlm_ocr_synthetic/
├── schemas/
│   ├── document.py     # BBox, TableCell/Row/Block, DocumentBlock, Document, BlockType
│   └── render.py       # RenderConfig (shared knobs), RenderResult (image + ground truth)
├── renderers/
│   ├── base.py         # BaseRenderer: the contract every backend implements
│   ├── __init__.py     # lazy registry: get_renderer(), available_renderers(), load_config()
│   ├── synthdog/
│   │   ├── fonts.py    # font lookup with sensible per-platform defaults
│   │   └── renderer.py # SynthdogConfig + SynthdogRenderer (Pillow)
│   └── html/
│       ├── html_builder.py  # Document -> HTML (no browser involved, unit-testable)
│       ├── backends.py      # screenshot engines; PlaywrightEngine + chromium lookup
│       ├── renderer.py      # HtmlConfig + HtmlRenderer
│       └── templates/       # jinja2 page template
├── samples/            # ready-made documents (invoice, ...)
├── cli.py              # python -m vlm_ocr_synthetic
└── __main__.py
configs/                # one strict YAML preset per backend
tests/                  # contract suite shared by all backends + per-backend tests
experiments/            # scratch scripts, safe to break
outputs/                # rendered pages (git-ignored)
```

Backends are imported **lazily** through the registry, so a missing browser
never breaks `synthdog`, a missing Pillow never breaks the registry, and
`python -m vlm_ocr_synthetic list` still explains what is wrong.

---

## Install

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
```

Extras let you install only what you need:

| extra        | pulls in                        | for |
| ------------ | ------------------------------- | --- |
| *(none)*     | pydantic, PyYAML                | schemas, registry, configs |
| `synthdog`   | + Pillow                        | the Pillow backend |
| `html`       | + Pillow, Jinja2, playwright    | the browser backend |
| `dev`        | + pytest                        | the test suite |
| `all`        | everything above                | |

The `html` backend needs a chromium binary:

```bash
playwright install chromium          # if you have no system chromium
```

It is looked up in this order — first hit wins:

1. `executable_path:` in the renderer config
2. `$VLM_OCR_CHROMIUM_PATH`
3. `/opt/pw-browsers/chromium`, `/usr/bin/chromium`, `/usr/bin/chromium-browser`, `/usr/bin/google-chrome`
4. `chromium` / `chromium-browser` / `google-chrome` on `$PATH`
5. playwright's own bundled browser

Useful when the pre-provisioned browser and the playwright version disagree:

```bash
export VLM_OCR_CHROMIUM_PATH=/opt/pw-browsers/chromium
```

---

## Quickstart

```bash
# Which backends are usable right now, and why the others are not?
python -m vlm_ocr_synthetic list

# Render the built-in sample with every available backend
python -m vlm_ocr_synthetic render -r all -o outputs/

# One backend, a shipped preset, 2x resolution
python -m vlm_ocr_synthetic render -r html -c configs/html_flow.yaml --scale 2.0

# Your own document
python -m vlm_ocr_synthetic render -r synthdog -d my_doc.json -o outputs/ --stem my_doc
```

Both backends side by side, with the boxes printed:

```bash
python experiments/render_sample.py --out outputs/compare
```

From Python:

```python
from vlm_ocr_synthetic.renderers import get_renderer
from vlm_ocr_synthetic.samples import get_sample

document = get_sample("invoice")

for name in ("synthdog", "html"):
    result = get_renderer(name, {"scale": 2.0, "seed": 7}).render(document)
    result.save(f"outputs/{name}", stem="invoice")   # -> invoice.png + invoice.json
```

### CLI reference

| command | what it does |
| ------- | ------------ |
| `list` | backend availability (`--json` for machine-readable output) and sample names |
| `render` | render one document |

`render` flags: `-r/--renderer` (name or `all`, default `all`) · `-c/--config`
(YAML/JSON preset) · `-d/--document` (a `Document` JSON file) · `-s/--sample`
(built-in document, default `invoice`) · `-o/--out` (default `outputs`) ·
`--stem` (file stem, default `page`) · `--scale` (override the config) ·
`--strict` (exit non-zero when a backend is unavailable, for CI).

---

## Output format

Every render writes a pair into `<out>/<backend>/`:

```
outputs/html/page.png     # the rendered page
outputs/html/page.json    # the document, with every bbox filled in
```

```jsonc
{
  "renderer": "html",
  "image_size": [1000, 1400],            // pixels
  "metadata": {
    "engine": "playwright",
    "layout": "flow",
    "scale": 1.0,
    "bbox_space": "document"             // NOT pixels -- see below
  },
  "document": {
    "page_width": 1000,
    "page_height": 1400,
    "blocks": [
      {
        "block_type": "Page-Header",
        "content": "INVOICE",
        "bbox": {"x1": 60.0, "y1": 60.0, "x2": 940.0, "y2": 97.79}
      },
      {
        "block_type": "Table",
        "bbox": {"x1": 60.0, "y1": 175.48, "x2": 940.0, "y2": 316.54},
        "table": {
          "bbox": {"x1": 60.0, "y1": 175.48, "x2": 940.0, "y2": 316.54},
          "rows": [
            {"cells": [
              {"content": "Item", "is_header": true, "rowspan": 1, "colspan": 1,
               "bbox": {"x1": 60.5, "y1": 175.98, "x2": 427.6, "y2": 222.67}}
            ]}
          ]
        }
      }
    ]
  }
}
```

### Coordinate convention

Boxes are always in **document space** (`page_width` x `page_height`), never in
pixels. The same annotation is therefore valid for every `scale`; convert when
you need pixels:

```python
scale = result.metadata["scale"]
pixel_bbox = block.bbox.scaled(scale)
```

---

## Documents

```python
from vlm_ocr_synthetic.schemas.document import (
    BBox, BlockType, Document, DocumentBlock, TableBlock, TableCell, TableRow,
)

Document(
    page_width=1000,
    page_height=1400,
    blocks=[
        DocumentBlock(block_type=BlockType.TITLE, content="Quarterly report"),
        DocumentBlock(block_type=BlockType.TEXT, content="Body text ..."),
        DocumentBlock(
            block_type=BlockType.TABLE,
            table=TableBlock(rows=[
                TableRow(cells=[TableCell(content="Item", is_header=True)]),
                TableRow(cells=[TableCell(content="Apple")]),
            ]),
        ),
    ],
)
```

- `block_type` uses the DocLayNet-flavoured vocabulary in `BlockType`
  (`Title`, `Section-header`, `Text`, `List-item`, `Table`, `Footnote`, ...).
- `content` holds the text; `table` holds structure and is only set for table
  blocks.
- **`bbox` is optional on input.** Leave it out and the backend lays the block
  out itself, then reports where it landed. Provide it and the block is pinned
  there (`synthdog`, and `html` with `layout: absolute`).

Documents are pydantic models, so `Document.model_validate_json(...)` /
`document.model_dump_json()` round-trip cleanly through disk.

---

## Configs

Presets live in `configs/`, one per backend flavour, and are **strict**: an
unknown key raises instead of being silently ignored, so a typo cannot quietly
change nothing.

```yaml
# configs/html_flow.yaml
renderer: html          # required: picks the backend
scale: 1.0
seed: 42
layout: flow
font_size: 22
```

```bash
python -m vlm_ocr_synthetic render -c configs/html_flow.yaml
```

| preset | what it gives you |
| ------ | ----------------- |
| `synthdog_default.yaml` | Pillow, off-white paper, table grid, light scan noise |
| `html_flow.yaml` | browser, CSS decides the layout — realistic and varied |
| `html_absolute.yaml` | browser, blocks pinned to the input bboxes — comparable to synthdog |

Shared knobs (`RenderConfig`): `page_width`, `page_height`, `scale`, `seed`.
`SynthdogConfig` adds fonts, margins, spacing, colours, `noise_sigma`,
`draw_table_grid`. `HtmlConfig` adds `engine`, `executable_path`, `timeout_ms`,
`layout`, and the CSS-facing typography/colour settings.

### HTML layout modes

- `flow` — CSS lays the page out; boxes come back from the DOM. Use this for
  realistic, varied training pages.
- `absolute` — every block is pinned to the bbox in the input document. Use this
  to render identical geometry through both backends and diff the results.

---

## Testing

```bash
pytest                  # everything (renders through both backends)
pytest -m "not slow"    # schemas, registry, markup only -- no rendering, <1s
pytest -k html          # one backend
```

`tests/test_renderers.py` is parametrised over the registry, so **every backend
is held to the same contract**: correct image size, a non-blank page, a bbox for
every block and every table cell, cells that do not overlap within a row,
content preserved through rendering, annotations that survive a save/reload, and
byte-identical output across two runs with the same seed.

A backend whose dependencies are missing is **skipped with the reason attached**
— never silently passed:

```
SKIPPED [1] tests/test_renderers.py:102: html renderer unavailable: chromium not found: /nope/chromium
```

Per-backend files cover what only that backend can get wrong: font lookup, text
wrapping and noise determinism for `synthdog`; HTML escaping, `data-*`
annotation, absolute-vs-flow layout and CSS-pixel (not device-pixel) boxes for
`html`.

---

## Adding a backend

1. Subclass `BaseRenderer`; set `name` and `config_model`; implement
   `render(document) -> RenderResult` and `check_available()` (return `None`
   when usable, else a human-readable reason).
2. Register it:

```python
from vlm_ocr_synthetic.renderers import register_renderer

register_renderer("weasyprint", "my_pkg.renderer:WeasyPrintRenderer")
```

   In-tree backends go straight into `_REGISTRY` in
   `vlm_ocr_synthetic/renderers/__init__.py`.

3. Emit boxes in document space and set `metadata["bbox_space"] = "document"`.

The shared contract suite, the CLI (`list`, `render -r all`) and config loading
pick the new backend up with no further changes.

To add only a new *screenshot engine* for the HTML backend (weasyprint, a
different browser driver), subclass `ScreenshotEngine` in
`renderers/html/backends.py` and add it to `ENGINES`; the engine is selected via
`engine:` in the config.
