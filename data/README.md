# data — where a run writes, not what is committed

This directory is **output**. Nothing in it is tracked by git except this file;
every dataset is rebuilt from the rule-base, and the rule-base is what the
repository actually keeps.

| set | build it with | what it is |
| --- | --- | --- |
| `dataset60/` | `make dataset` | **aged** — a degradation chain drawn from the rules; the glyph renderer also curls the sheet and re-photographs it |
| `dataset60_clean/` | `make dataset-clean` | **not augmented** — the same receipts with every kind of ageing and distortion off |
| `tables60/` | `make tables` | table-structure images from the html backend |
| `profile/` | `make profile` | per-stage timings for every renderer |

```bash
make dataset                              # the aged set
make dataset-clean                        # the clean set
make proof DATASET=data/dataset60         # read it back with Tesseract and score it
make check-boxes DATASET=data/dataset60   # the boxes still describe the pixels
```

Both sets are built `paired`: all three renderers draw the *same* receipts, so
`synthdog_000.jpg`, `html_000.jpg` and `genalog_000.jpg` are one receipt
photographed, scanned and printed. That is what makes a comparison between the
renderers mean anything, and it is why twenty receipts give sixty images —
`dataset.json` reports `distinct_labels` per renderer so nobody has to work it
out.

The clean set differs from the aged set in exactly **one attribute** of the
rule-base: it pins `augmentation=pristine`, an empty degradation chain. Content,
layout, font and colour are still sampled as usual. `--clean` also turns off the
glyph renderer's curl-and-rephotograph step, which the two HTML renderers have
no equivalent of — otherwise "not augmented" would only be true for two
renderers out of three. Use the clean set as the **ceiling**: the gap to
`dataset60/` is the price of the ageing.

## Want to look at output without building anything?

Build the three environments and generate — or look at
[`samples/`](../samples), which is committed for exactly that reason: every
degradation model on the same page, the five reference invoice sheets, and every
seal and flourish. [`docs/figures/`](../docs/figures) holds the figures the
README embeds.

## Structure of a set

```
dataset60/
├── dataset.json            images per renderer, and the split by layout
├── synthdog/
│   ├── synthdog_000.jpg …  20 images
│   └── metadata.jsonl      one line per image
├── html/       …
├── genalog/    …
└── proof/
    ├── README.md           the OCR score tables
    ├── ocr_report.json     per-image scores and the most-misread fields
    └── proof_*.jpg         the image with a box round every word Tesseract read
```

## One line of `metadata.jsonl`

```json
{
  "file_name": "synthdog_000.jpg",
  "framework": "synthdog",
  "layout": "eatery_indexed",
  "ground_truth": "{\"gt_parse\": {…}}",
  "text_sequence": "QUÁN NHẬU SEN VÀNG 251 235 Phan Xích Long …",
  "recipe": {"seed": 2026, "attributes": {…}, "tags": […]},
  "boxes": [{"kind": "menu.nm", "text": "…", "quad": [[x,y],…]}]
}
```

| field | |
| --- | --- |
| `ground_truth` | CORD-style nested label, as a JSON string (Donut reads it directly) |
| `text_sequence` | flat reading label, for pre-training and for OCR scoring |
| `recipe` | **all six** sampled attributes plus the seed — enough to rebuild the exact image |
| `boxes` | one `{kind, text, quad}` per drawn field, from **all three** renderers. synthdog's quads are rotated by the paper curl; the other two are axis-aligned |

`recipe.seed` reproduces the content — but **only together with the attributes
recorded beside it**. `generate_dataset.py` pins the layout so each renderer
draws all fourteen equally often, and a pin does not merely filter: with
`layout` restricted to one value the tags it sets differ, so every attribute
drawn after it diverges. To rebuild an image exactly, pin all six ids back:

```python
force = {name: value["id"] for name, value in record["recipe"]["attributes"].items()}
recipe, receipt, grid = rulebase.make(seed=record["recipe"]["seed"], force=force)
```

`tools/check_boxes.py` does exactly this, and it is how the requirement was
found — rebuilding from the bare seed reported every field of every image as
missing a box.
