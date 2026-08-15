# tables60 — table-structure images

60 table images with **PubTabNet-style structure labels**, from the vendored
generator in [`generators/html-table/`](../../generators/html-table).

```bash
make setup-tables
make tables                  # or: py tasks.py tables -n 60 -o data/tables60
```

## This is a different task from the receipt sets

`data/dataset60/` teaches a model to **parse a document**: its label is a
nested CORD record — shop, items, totals. This set teaches a model to
**recover a table's structure**: its label is the `<td>` token sequence, the
row and column spans, and a box per cell.

They share no schema, and flattening one into the other would produce a label
that claims to be something it is not. What they do share is the index file
name (`metadata.jsonl`) and the `file_name` key, so a loader finds them the
same way.

Nothing here reads `rulebase/`. The vendored generator has its own sampler.

## What is in it

| | |
| --- | --- |
| images | 60 |
| cells per table | 7 – 67, mean 29.3 |
| tables with merged cells | 60 / 60 |
| border styles | `no_border`, `border`, `border_top`, `border_bottom`, `border_left`, `border_right`, `head_border_bottom` |
| coloured cells | ~30% of tables |
| on disk | 1.9 MB |

```
tables60/
├── img/*.jpg           the rendered tables
├── html/*.html         the page each was screenshotted from
├── gt.txt              upstream's own label file, untouched
├── metadata.jsonl      the same labels in this repository's shape
└── README.md
```

One line of `metadata.jsonl`:

```json
{
  "file_name": "img/border_2_Y7648YTHML70AUJMXO2R.jpg",
  "task": "table_structure",
  "ground_truth": "<html><body><table><tr><td rowspan=\"2\">Lão Độ</td>…",
  "structure_tokens": ["<tr>", "<td", " rowspan=\"2\"", ">", "</td>", …],
  "cells": [{"tokens": ["L","ã","o"," ","Đ","ộ"], "bbox": [[[5,8],[180,8],[180,74],[5,74]]]}],
  "n_cells": 39
}
```

## The text is Vietnamese, and it is deliberately not meaningful

Cells are filled from `generators/html-table/dict/vi_corpus.txt`, built out of
`rulebase/corpus/vi/` by `tools/generate_tables.py --rebuild-dict`. Upstream's
default is 13 MB of Chinese news, which would put the wrong glyphs in a
Vietnamese dataset.

But read a cell and it says `ình Thọ Ng`, not a phrase. That is upstream's
design, not a bug: `Table.generate_text` takes a random **character slice** of
the corpus, and for structure recognition that is the right call — a model that
learns to segment cells should not also be learning which words go in them.
Upstream's English behaves identically (`Lersbu`).

The consequence is worth stating plainly: **these images teach layout, not
language.** Do not use them to train or evaluate reading. For that, use
`data/dataset60/`, where every string is real Vietnamese and the label is built
from the same objects the renderer drew.

## No OCR proof for this set

`make proof` scores a reading task against a parsed label, and neither half
applies here. The check that matters for table structure is a different
metric — TEDS, against the `structure_tokens` — which this repository does not
implement yet.
