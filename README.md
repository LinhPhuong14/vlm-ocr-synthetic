# vlm-ocr-synthetic

Synthetic document pages for training and evaluating VLM / OCR models — with
pixel-accurate ground truth, and enough variation to make a dataset out of.

A page is described **once** as a `Document`; interchangeable backends turn that
description into an image plus annotations, and a shared paper layer makes it
look like it came off a scanner.

| `synthdog` | `html` | `html`, quarter-folded |
| --- | --- | --- |
| ![Vietnamese receipt rendered by synthdog](data/samples/receipt_vn-synthdog.jpg) | ![the same receipt via HTML](data/samples/receipt_vn-html.jpg) | ![an invoice, folded and scanned](data/samples/invoice-html-folded.jpg) |

---

## Quickstart

Python **3.10 – 3.14**.

```bash
make setup                                  # venv, dependencies, chromium, health check
make test                                   # the whole suite
python -m vlm_ocr_synthetic render -r all   # sample pages into data/
```

Without `make`:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[all]"
playwright install chromium          # html backend only
python -m vlm_ocr_synthetic doctor   # interpreter, dependencies, backends
```

`make help` lists every task. If anything is off, `doctor` says what and why.

---

## What it does

```bash
python -m vlm_ocr_synthetic list                  # which backends are usable
python -m vlm_ocr_synthetic render -r all         # one document, every backend
python -m vlm_ocr_synthetic benchmark --pages 3   # compare them, with numbers
python -m vlm_ocr_synthetic generate --dry-run    # plan a dataset run
python -m vlm_ocr_synthetic generate -o data/set  # render it
```

Two backends consume the same `Document` and return the same `RenderResult`:

| backend | how it draws | strengths | costs |
| --- | --- | --- | --- |
| `synthdog` | Pillow paints the page directly | ~10x faster per page, boxes exact by construction, no browser | basic typography, simple stacking |
| `html` | HTML/CSS laid out in chromium, screenshotted | real typography, tables and wrapping; boxes read off the DOM | needs chromium, slower |

A dataset comes from sampling a **scenario space** — 10 layouts × 3 backends ×
15 styles × 10 degradations — with weights you set in
[`configs/datasets/default.yaml`](configs/datasets/default.yaml).

---

## Structure

```
vlm_ocr_synthetic/
├── schemas/      Document, blocks, tables, bboxes; RenderConfig / RenderResult
├── corpus/       shared text, and the rule that keeps layout out of it
├── samples/      ready-made documents (invoice, Vietnamese receipt)
├── renderers/    the backend contract, synthdog, html, and the paper layer
├── variations/   the scenario space: layouts, styles, degradations, weights
├── dataset/      plan -> render -> manifest.jsonl
├── evaluation/   benchmark the backends against each other
├── cli/          python -m vlm_ocr_synthetic
└── compat.py     interpreter and dependency floors
configs/renderers/   one preset per look
configs/datasets/    weights for a dataset run
docs/                the long-form documentation
tests/               mirrors the package
data/                everything generated (git-ignored, bar previews + report)
```

---

## Documentation

| | |
| --- | --- |
| [Architecture](docs/architecture.md) | how a page is described, rendered and annotated; the corpus rule |
| [Backends](docs/backends.md) | presets, chromium lookup, writing a new backend |
| [Paper and degradation](docs/paper.md) | grain, folds, bleed-through, real paper textures |
| [Generating datasets](docs/datasets.md) | the scenario space, distributions, adding attributes and resources, using the output |
| [Benchmark](docs/benchmark.md) | what is measured, and what the numbers say |
| [Samples](docs/samples.md) | the shipped documents |
| [Python 3.14](docs/python-314.md) | dependency floors, and why the original synthdog cannot run there |
| [Contributing](CONTRIBUTING.md) | repo layout, tests, style |

---

## Design in one page

- **One document, many renders.** Ground truth is written once and every
  backend must reproduce it; `tests/renderers/test_contract.py` holds them all
  to the same standard.
- **Content is words, layout is structure.** No aligning columns with padding
  spaces — the two backends disagree about whitespace by nature. Alignment
  lives on the table.
- **Paper is a stage after the structure.** A page is laid out once and can be
  aged many ways for almost nothing.
- **Boxes are in document space, not pixels.** One annotation stays valid at
  every scale.
- **Configs are strict.** An unknown key raises; a mistyped variant weight
  raises. A typo must never quietly change a dataset.

---

## Licence

Not yet chosen — add one before publishing.
