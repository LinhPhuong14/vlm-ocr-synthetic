# tables60 — table-structure images

60 table images with **PubTabNet-style structure labels**, built by
[`generators/html/tables.py`](../../generators/html/tables.py).

```bash
make setup-html
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

## Same backend as the html receipts

The generator used to be `generators/html-table/`, vendored upstream code
driven through Selenium. That was never a second rendering method: Selenium's
`element.location`/`.size` is the same Chromium and the same DOM geometry
`generators/html/render.py` reads from `getBoundingClientRect`. It cost a
second virtualenv, a `google-chrome` shim on `PATH` and a chromedriver whose
major version had to match the browser — none of which has anything to do with
generating a table.

The table model is still upstream's, and the label format is unchanged, so
anything that reads PubTabNet or PP-Structure reads this. What is different:

| | upstream | here |
| --- | --- | --- |
| cell text | random **character** slice — `ình Thọ Ng` | whole words from `rulebase/corpus/vi/` |
| money | `$123.45` | `rulebase.text.money` — `1.234.000 đ` |
| fonts | whatever the container has | the repo's own, embedded |
| seed | global, once per run | per image — rebuild #40 without #0–39 |
| file name | `border_2_HML70AUJMXO2R6MBHE4J.jpg` | `border_0002.jpg` |
| image | 226–566 px wide | up to 1200 px on the long side |

## What is in it

| | |
| --- | --- |
| images | 60 |
| cells per table | 9 – 68, mean 31.5 |
| tables with merged cells | 60 / 60 |
| border styles | `border` 14, `head_border_bottom` 10, `border_right` 9, `no_border` 8, `border_top` 7, `border_bottom` 6, `border_left` 6 |
| coloured cells | ~30% of cells |
| every cell box on its own ink | 60 / 60 |
| on disk | 5.6 MB |

```
tables60/
├── img/*.jpg           the rendered tables
├── html/*.html         the page each was screenshotted from
├── gt.txt              the PP-Structure label file, as that format defines it
├── metadata.jsonl      the same labels in this repository's shape
└── README.md
```

One line of `metadata.jsonl`:

```json
{
  "file_name": "img/border_0002.jpg",
  "task": "table_structure",
  "ground_truth": "<html><body><table><tr><td colspan=\"3\">Phạm Thị Bích</td>…",
  "structure_tokens": ["<tr>", "<td", " colspan=\"3\"", ">", "</td>", …],
  "cells": [{"tokens": ["P","h","ạ","m"," ","T","h","ị"," ","B","í","c","h"],
             "bbox": [[[5,8],[180,8],[180,74],[5,74]]]}],
  "n_cells": 39
}
```

`bbox` holds the quad rather than being it. That nesting is upstream's and is
kept on purpose: the only value this format has is that other tools already
read it.

## The text is Vietnamese, and now it is words

Cells are filled from `rulebase/corpus/vi/` — the same lists the receipts draw
from, so the glyph distribution of this set is the dataset's and not a second,
accidental one. Numbers and money are generated, not sampled; one column type in
four is ASCII-folded, which is what a form printed on a machine with no Unicode
looks like.

A cell is a run of one to three whole words, so it reads as language rather than
as `ình Thọ Ng`. What it is *not* is a sentence: the words come from a product
list, not from prose, and a row says nothing coherent across its columns. These
images are still primarily about layout. For reading, use `data/dataset60/`,
where every string is real and the label is built from the same objects the
renderer drew.

## No OCR proof for this set

`make proof` scores a reading task against a parsed label, and neither half
applies here. The check that matters for table structure is a different
metric — TEDS, against the `structure_tokens` — which this repository does not
implement yet. What is checked, on every image in this directory: the token
list promises exactly as many cells as the page has, every cell box lies inside
the frame, and every box with text under it has ink under it.
