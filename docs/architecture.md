# Architecture

How the pieces fit, and why the seams are where they are.

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
│   ├── html/
│   │   ├── html_builder.py  # Document -> HTML (no browser involved, unit-testable)
│   │   ├── backends.py      # screenshot engines; PlaywrightEngine + chromium lookup
│   │   ├── renderer.py      # HtmlConfig + HtmlRenderer
│   │   └── templates/       # jinja2 page template
│   └── paper.py        # the paper + degradation layer both backends share
├── samples/            # ready-made documents + corpus.py (shared text + the format rule)
├── variations/         # the scenario space: layouts, styles, degradations, weights
├── pipeline.py         # sample scenarios -> render -> manifest.jsonl
├── benchmark.py        # render through every backend and compare
├── compat.py           # interpreter and dependency floors
├── cli.py              # python -m vlm_ocr_synthetic
└── __main__.py
configs/                # one strict YAML preset per backend
tests/                  # contract suite shared by all backends + per-backend tests
experiments/            # scratch scripts, safe to break
data/                   # everything generated (see below)
```

Backends are imported **lazily** through the registry, so a missing browser
never breaks `synthdog`, a missing Pillow never breaks the registry, and
`python -m vlm_ocr_synthetic list` still explains what is wrong.

## Output format

Every render writes a pair into `<out>/<backend>/`, and `<out>` defaults to
`data/`:

```
data/html/page.png     # the rendered page
data/html/page.json    # the document, with every bbox filled in
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

## Documents

```python
from vlm_ocr_synthetic.schemas.document import (
    BBox,
    BlockType,
    Document,
    DocumentBlock,
    TableBlock,
    TableCell,
    TableRow,
)

Document(
    page_width=1000,
    page_height=1400,
    blocks=[
        DocumentBlock(block_type=BlockType.TITLE, content="Quarterly report"),
        DocumentBlock(block_type=BlockType.TEXT, content="Body text ..."),
        DocumentBlock(
            block_type=BlockType.TABLE,
            table=TableBlock(
                rows=[
                    TableRow(cells=[TableCell(content="Item", is_header=True)]),
                    TableRow(cells=[TableCell(content="Apple")]),
                ]
            ),
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

## Corpus rule: content is words, layout is structure

A content string holds the words and nothing else — no padding spaces to line
columns up, no tabs, no manual right-alignment. Alignment lives in the table's
`column_widths` / `column_align`, which **both backends read from the
document**.

The rule exists because the two backends cannot agree about whitespace: Pillow
lays out glyph runs, a browser applies `white-space` and its own shaper, and a
proportional font makes padded "alignment" drift anyway. This string rendered as
two different documents:

```python
DocumentBlock(block_type="Section-header", content="TIỀN MẶT        537,000")
# synthdog collapsed it to  "TIỀN MẶT 537,000"
# the browser kept it as    "TIỀN MẶT        537,000"
```

It is now a two-cell row, and both backends place it identically:

```python
TableBlock(
    rows=[TableRow(cells=[TableCell(content="TIỀN MẶT"), TableCell(content="537,000")])],
    column_widths=(0.5, 0.5),
    column_align=("left", "right"),
)
```

`vlm_ocr_synthetic/corpus/rules.py` holds the shared text — Vietnamese invoice
column headings, labels, money formatting — and `assert_plain_text(document)`
enforces the rule. `tests/corpus/test_rules.py` runs it over every shipped sample, so
a future generator cannot quietly reintroduce padded strings.

Two more things keep the backends aligned:

- **The table carries its own layout.** `column_widths` are normalised, so
  `(1, 4, 1)` and `(0.17, 0.66, 0.17)` mean the same thing. A renderer config
  (`table_column_widths` / `table_column_align` on synthdog, CSS on html) is
  only a fallback for documents that describe nothing — when the document does,
  it wins.
- **synthdog preserves whitespace runs**, exactly like `white-space: pre-wrap`
  in the browser, so text that *does* contain padding survives intact in both.
  A wrap swallows only the whitespace it broke on.

The invariant is tested, not just documented: the same document rendered through
both backends must produce **the same table column geometry**.

```
receipt header row, cell widths in document space
  synthdog  [41, 188, 41, 107, 132]
  html      [41, 188, 41, 107, 132]
```
