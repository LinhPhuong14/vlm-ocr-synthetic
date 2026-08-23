# data — the generated datasets

| set | images | what it is |
| --- | ---: | --- |
| [`dataset60/`](dataset60) | 60 | **aged** — a degradation chain drawn from the rules; the glyph renderer also curls the sheet and re-photographs it |
| [`dataset60_clean/`](dataset60_clean) | 60 | **not augmented** — same receipts, every kind of ageing and distortion off |
| [`invoices54/`](invoices54) | 54 | the nine **commercial invoice** layouts drawn as **CSS sheets** rather than as a character grid, by the two HTML backends — see its own [README](invoices54/README.md) |
| [`forms16/`](forms16) | 16 | the two documents that are **not a sale**: a hospital's statement of treatment costs and an authorisation to collect money — see its own [README](forms16/README.md) |
| [`hand12/`](hand12) | 12 | **điền tay** — the first pages here whose values are real handwriting rather than type, filled into printed form fields by WriteViT; see its own [README](hand12/README.md) and [`docs/handwriting-html.md`](../docs/handwriting-html.md) |
| [`dataset_test/`](dataset_test) | 45 | a **scratch set for looking at**, one image per working layout per renderer. Regenerated whenever the ageing is retuned, and not a fixed comparison point — see below |

20 images per renderer (synthdog / html / genalog) in each `dataset60*` set,
spread evenly over the layouts. `invoices54/` is a different shape and says so
in its own README: two renderers, nine layouts, and a different page model.

**Which page model drew a set is in its `dataset.json`**, under `template`.
Absent or empty is the character grid — what every set built before
`generators/html/sheets/` existed was drawn from. Do not infer it from the
pixels; a ruled invoice looks much the same either way until you measure it.

Both sets span the **fourteen layouts that existed when they were built**: five thermal receipts on a continuous
roll and nine commercial invoices on A4. `dataset.json` in each set records the
layouts it was built from — read that rather than this table if the two ever
disagree.

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

## `dataset_test/` — what it is for, and what it is not

Fifteen layouts, one image each, three renderers: a spread wide enough to see
what a change to the ageing did, small enough to regenerate in about two
minutes. It exists to be **looked at** after tuning something visual — most
recently `DENSITY` in `degradation/ink_degradation.py`, which decides how much
speckle an aged page carries.

It is deliberately **not** a comparison point. It carries no `proof/`, nothing
is fingerprinted against it, and it is overwritten in place. Use `dataset60/`
for a number anyone will quote and `tests/golden/baseline.json` for a claim
that pixels did not move; a set that is regenerated whenever someone retunes a
constant cannot do either job, and pretending otherwise is how a moving target
ends up cited as evidence.

It holds **fifteen of the sixteen** layouts. `authorisation_letter` is left out
because it fails the box-coverage invariant on the genalog backend — the
right-hand address is in the label with no box under it, on 2 of 3 seeds. That
is a real defect, reproduced on a clean checkout and unrelated to the ageing;
html and synthdog draw the same layout cleanly.

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
│   ├── metadata.jsonl      one line per image — the converter's schema
│   └── synthesis.json      how those images were made — seed, attributes, tags
├── html/       …
├── genalog/    …
└── proof/
    ├── README.md           the OCR score tables
    ├── ocr_report.json     per-image scores and the most-misread fields
    └── proof_*.jpg         the image with a box round every word Tesseract read
```

## Two files per backend directory

`metadata.jsonl` is the document converter's schema, so a drawn page and a
converted one load the same way. Its keys are fixed by
[`pipeline/record.py`](../pipeline/record.py), and a key that is not in that
schema is as much an error as one that is missing.

`synthesis.json` beside it is how those pages were made — the half no converter
could return, and the half nothing can redraw a committed image without. See
[below](#synthesisjson).

### One line of `metadata.jsonl`

```json
{
  "schema_version": 8,
  "job_id": "c95630e9-7613-58d2-a948-781f8ffa636d",
  "task": "convert",
  "parser": "synthdog",
  "filename": "synthdog_000.jpg",
  "source_files": ["synthdog_000.jpg"],
  "settings": {"convert_mode": "synthdog", "target_language": "Vietnamese", …},
  "documents": [],
  "pages": [{"page_number": 1, "width": 629, "height": 572, …}],
  "blocks": [{"id": "p1-b6", "index_in_page": 6, "label": "Table",
              "bbox": {"x1": 68, "y1": 350, "x2": 92, "y2": 380},
              "content": "…", "kind": "menu.nm", "text": "…",
              "quad": [[x,y],…]}],
  "markdown": "QUÁN NHẬU SEN VÀNG\n\n251 235 Phan Xích Long …",
  "html": "<p>QUÁN NHẬU SEN VÀNG</p>…",
  "extracted": {"doc_type": "receipt_eatery", …}
}
```

| field | |
| --- | --- |
| `job_id` | uuid5 of `parser\|layout\|seed\|filename` — the same page gets the same id twice, because this file is hashed by the golden baseline |
| `extracted` | CORD-style nested label, as an **object** (`record.ground_truth()` gives back the JSON string a Donut loader reads) |
| `blocks` | one per drawn field, from **all three** renderers. `label` + `bbox` is the converter's vocabulary; `kind` + `quad` is this repository's, and synthdog's quads are rotated by the paper curl where the other two are axis-aligned |
| `markdown`, `html` | the blocks grouped into the lines they were printed on. Derived — nothing is in them that is not in a block |
| `settings` | the converter's job options. `max_pixels` is `null` — the page was drawn at the size it is, and that size is in `pages[0]` |

### `synthesis.json`

Everything the converter has no field for: the flat reading order, and **all
six** sampled attributes plus the seed — enough to rebuild the exact image. It
is one file rather than a key on every line because most of it was the same text
over and over: `ornament` and `augmentation` are recipes for a *background*, and
twenty pages sharing one chain wrote that chain out twenty times. Here the
params behind an option id are written **once**, and a page names ids.

```json
{
  "schema_version": 8,
  "framework": "synthdog",
  "pages": {
    "synthdog_000.jpg": {
      "job_id": "c95630e9-…", "seed": 2026, "layout": "eatery_indexed",
      "attributes": {"document": "street_eatery", "layout": "eatery_indexed",
                     "visual": "thermal_narrow", "augmentation": "real_paper", "…": "…"},
      "tags": ["thermal", "till_receipt", "…"],
      "text_sequence": "QUÁN NHẬU SEN VÀNG 251 235 Phan Xích Long …"
    }
  },
  "attributes": {
    "augmentation": {"real_paper": {"params": {"chain": [["paper_texture", {"…": "…"}]]}}},
    "layout": {"eatery_indexed": {"group": "retail_receipt", "params": {}}}
  },
  "images": 20
}
```

`Synthesis.recipe(filename)` folds the two halves back into exactly the
`recipe.to_dict()` the rule-base produced. The seed reproduces the content —
but **only together with the attributes recorded beside it**.
`generate_dataset.py` pins the layout so each renderer draws all five equally
often, and a pin does not merely filter: with `layout` restricted to one value
the tags it sets differ, so every attribute drawn after it diverges. To rebuild
an image exactly, pin all six ids back:

```python
from pipeline import record, synthesis

drew = synthesis.read("data/dataset60/synthdog")
recipe = drew.recipe(record.file_name(item))
force = {name: value["id"] for name, value in recipe["attributes"].items()}
recipe, receipt, grid = rulebase.make(seed=recipe["seed"], force=force)
```

An older dataset — anything written before the two files were split — is brought
forward with `python tools/migrate_metadata.py data`, which re-renders nothing.

`tools/check_boxes.py` does exactly this, and it is how the requirement was
found — rebuilding from the bare seed reported every field of every image as
missing a box.

Verify a set after regenerating it:

```bash
make check-boxes DATASET=data/dataset60
```
