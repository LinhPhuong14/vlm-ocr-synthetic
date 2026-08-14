# vlm-ocr-synthetic

Synthetic document images for training and evaluating VLM / OCR models, with
structured labels. Three generators live side by side under `generators/`, each
self-contained: its own dependencies, its own supported Python, its own README.

| generator | produces | how | Python | status |
| --- | --- | --- | --- | --- |
| [`generators/synthdog/`](generators/synthdog/README_vi_receipt.md) | Vietnamese thermal-printer receipts with structured ground truth for Donut | [synthtiger](https://github.com/clovaai/synthtiger) templates | **3.8 – 3.11** | first-party |
| [`generators/html-table/`](generators/html-table/README.md) | table images with cell-level annotations | HTML rendered in a browser | 3.8+ | vendored |
| [`generators/genalog/`](https://github.com/microsoft/genalog) | degraded document images from plain text | Microsoft genalog | 3.6 – 3.8 | submodule |

```bash
git clone --recurse-submodules https://github.com/LinhPhuong14/vlm-ocr-synthetic.git
cd vlm-ocr-synthetic
make help
```

Cloned without `--recurse-submodules`? `make submodules`.

---

## Repository layout

```
generators/
├── synthdog/           SynthDoG-VN — the main generator
│   ├── template_receipt.py     the receipt template (SynthVNReceipt)
│   ├── template.py             the original SynthDoG template
│   ├── config_vi_receipt.yaml  what a Vietnamese receipt looks like
│   ├── config_{en,ja,ko,zh}.yaml
│   ├── elements/               background, paper, content, textbox, warp
│   ├── layouts/                grid and stacked-grid layouts
│   ├── resources/              corpora in git; fonts and paper are not
│   ├── tools/                  font coverage check, preview grid
│   └── requirements.txt        pinned, and each pin has a reason
├── html-table/         vendored TableGeneration + its dictionaries
└── genalog/            submodule -> microsoft/genalog

augment/                DocCreator's degradations, in Python -- applied to any generator's output
scripts/                one-off drivers (augmentation demo)
docs/                   notes that outlive any one generator
.github/workflows/      lint, byte-compile, and a real synthtiger install
Makefile                the tasks; `make help` lists them
pyproject.toml          ruff configuration (this repo is not a package)
```

**Every generator is run from its own directory**, because the paths inside
their configs are relative to it. `make receipts` and `make preview` already
`cd` for you.

---

## Vietnamese receipts

The main generator: thermal-printer bills for restaurants and shops, with
diacritics, VAT, discounts and change, on paper skewed, curled and blurred
differently every time.

```bash
make setup      # a 3.11 venv with the pinned dependencies
make receipts   # 100 receipts into generators/synthdog/outputs/
make preview    # a grid of 8, to eyeball a config change
```

Two things to know before the first run:

- **Fonts, paper and background images are not in the repository** — they are
  not redistributable. Put them in `generators/synthdog/resources/` first;
  [that directory's README](generators/synthdog/resources/README.md) says what
  goes where. Without them synthtiger **hangs rather than failing**, because it
  swallows exceptions and retries.
- **Python 3.13+ will not work**, and the cap is not caution: the pins in
  `requirements.txt` each come from a real failure. See
  [docs/python-314.md](docs/python-314.md) for the measurements.

Everything else — config knobs, the label format, troubleshooting — is in
[`generators/synthdog/README_vi_receipt.md`](generators/synthdog/README_vi_receipt.md).

---

## Table images

Vendored from [TIES_DataGeneration](https://github.com/hassan-mahmood/TIES_DataGeneration),
extended with configurable cell types, merged cells and colours.

```bash
cd generators/html-table
pip install -r requirements.txt
python generate_data.py --help
```

---

## Degraded documents

[Microsoft genalog](https://github.com/microsoft/genalog) as a submodule: HTML
templates plus a degradation pipeline (blur, bleed-through, salt, pepper,
morphology). Useful when you already have text and want scanned-looking pages
from it. Work on it upstream, not in place.

---

## Augmentation

[`augment/`](augment/README.md) is a Python port of the degradation models from
[DocCreator](https://github.com/DocCreator/DocCreator) — local ink decay,
bleed-through, blur zones, binding shadow, holes. It runs on whatever a
generator produced, so the same ageing can be applied to receipts and to
genalog pages alike.

```bash
python scripts/augment_samples.py --synthdog <dir> --genalog <dir> -o data/augment
```

[`data/augment/`](data/augment) holds ten before/after pairs, five from each
generator.

---

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) covers which environment to build for which
generator, what CI checks, and the constraints that are deliberate.

## Licence

Not yet chosen — add one before publishing. `generators/html-table/` carries its
own `LICENSE.md`; `genalog` is MIT upstream.
