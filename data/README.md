# data — the generated datasets

| set | images | what it is |
| --- | ---: | --- |
| [`dataset60/`](dataset60) | 60 | **aged** — a degradation chain drawn from the rules; the glyph renderer also curls the sheet and re-photographs it |
| [`dataset60_clean/`](dataset60_clean) | 60 | **not augmented** — same rule-base, same 5 layouts, every kind of ageing and distortion off |

20 images per renderer (synthdog / html / genalog) in each set, spread evenly
over the 5 layouts.

**60 images, 20 receipts.** Both sets are built `paired`: all three renderers
draw the *same* twenty receipts, so `synthdog_000.jpg`, `html_000.jpg` and
`genalog_000.jpg` are one receipt photographed, scanned and printed. That is
what makes a comparison between the renderers mean anything, and it is also why
the sample is twenty and not sixty — `dataset.json` reports
`distinct_labels` per renderer so nobody has to work it out.

Both sets also carry the *same* twenty receipts as each other, so the aged set
and the clean set differ in exactly one thing: the ageing.

Before W1b neither of those was true. The three renderers sat on disjoint seed
blocks and drew three different sets of receipts, and a pinned draw walked to
the next fitting seed, so twenty images held ten or thirteen distinct labels.
Every side-by-side number published from those sets compared three different
corpora over a sample half the size it claimed.

Regenerate:

```bash
make dataset                              # the aged set
make dataset-clean                        # the clean set
make proof DATASET=data/dataset60         # read it back with Tesseract and score it
```

## What separates the two sets

Exactly **one attribute** of the rule-base: the clean set pins
`augmentation=pristine`, an empty degradation chain. Content, layout, font and
colour are still sampled as usual.

The glyph renderer has one more source of distortion that the two HTML
renderers do not: it curls the sheet, warps the perspective, drops it on a
background and "re-photographs" it. `--clean` turns that off as well —
otherwise "not augmented" would only be true for two renderers out of three.
The result is an image exactly the size of the sheet, with no background
visible.

Use the clean set as the **ceiling**: does the label match the pixels, and how
much can OCR read when nothing is in the way. The gap to `dataset60/` is the
price of the ageing.

Both sets are **committed to git**. The point of the repository is that you can
open it and look without building three environments first, so the images, the
labels and the OCR report are all in the repo. Anything a renderer writes to
`outputs/` is not.

## Structure

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
draws all five equally often, and a pin does not merely filter: with `layout`
restricted to one value the tags it sets differ, so every attribute drawn after
it diverges. To rebuild an image exactly, pin all six ids back:

```python
force = {name: value["id"] for name, value in record["recipe"]["attributes"].items()}
recipe, receipt, grid = rulebase.make(seed=record["recipe"]["seed"], force=force)
```

`tools/check_boxes.py` does exactly this, and it is how the requirement was
found — rebuilding from the bare seed reported every field of every image as
missing a box.

Verify a set after regenerating it:

```bash
make check-boxes DATASET=data/dataset60
```
