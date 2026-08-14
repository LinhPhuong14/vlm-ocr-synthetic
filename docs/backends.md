# Render backends

## Configs

Presets live in `configs/`, one per backend flavour, and are **strict**: an
unknown key raises instead of being silently ignored, so a typo cannot quietly
change nothing.

```yaml
# configs/renderers/html_flow.yaml
renderer: html          # required: picks the backend
scale: 1.0
seed: 42
layout: flow
font_size: 22
```

```bash
python -m vlm_ocr_synthetic render -c configs/renderers/html_flow.yaml
```

| preset | what it gives you |
| ------ | ----------------- |
| `synthdog_default.yaml` | Pillow, off-white paper, table grid, light scan noise |
| `html_flow.yaml` | browser, CSS decides the layout — realistic and varied |
| `html_absolute.yaml` | browser, blocks pinned to the input bboxes — comparable to synthdog |
| `html_scanned.yaml` | browser, genalog-style degradations turned up: blur, bleed-through, specks, vignette, tri-fold |
| `html_folded.yaml` | browser, a sheet quarter-folded before it was scanned |
| `html_receipt_vn.yaml` | browser, 80mm thermal receipt (mono font, centred, borderless) |
| `synthdog_receipt_vn.yaml` | the same receipt through Pillow, for side-by-side checks |

Shared knobs (`RenderConfig`): `page_width`, `page_height`, `scale`, `seed`.
`SynthdogConfig` adds fonts, margins, spacing, colours, `noise_sigma`,
`draw_table_grid`. `HtmlConfig` adds `engine`, `executable_path`, `timeout_ms`,
`layout`, and the CSS-facing typography/colour settings.

### HTML layout modes

- `flow` — CSS lays the page out; boxes come back from the DOM. Use this for
  realistic, varied training pages.
- `absolute` — every block is pinned to the bbox in the input document. Use this
  to render identical geometry through both backends and diff the results.

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
