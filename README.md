# vlm-ocr-synthetic

Synthetic document images for training and evaluating VLM / OCR models, with
structured labels. Two generators live side by side under `generators/`, each
self-contained: its own dependencies, its own supported Python, its own README.

| generator | produces | how | Python | status |
| --- | --- | --- | --- | --- |
| [`generators/synthdog/`](generators/synthdog/README_vi_receipt.md) | Vietnamese thermal-printer receipts with structured ground truth for Donut | [synthtiger](https://github.com/clovaai/synthtiger) templates | **3.8 – 3.11** | first-party |
| [`generators/html-table/`](generators/html-table/README.md) | table images with cell-level annotations | HTML rendered in a browser | 3.8+ | vendored |

[Microsoft genalog](https://github.com/microsoft/genalog) is used too, for
degraded pages from plain text, but it is not vendored here — `pip install
genalog` when you need it. See [Augmentation](#augmentation).

```bash
git clone https://github.com/LinhPhuong14/vlm-ocr-synthetic.git
cd vlm-ocr-synthetic
make help
```

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
└── html-table/         vendored TableGeneration + its dictionaries

degradation/            DocCreator's degradation models, in Python
├── ink_degradation.py      local ink decay (the one worth having)
├── shadow_binding.py       shadow near a page's spine
├── bleed_through.py        ink from the other side of the sheet
├── blur_zones.py           blur in patches, not over the whole page
└── holes.py                holes punched or torn through

samples/degradation/    twenty before/after pairs from the port
tools/                  driver scripts (`augment_samples.py`)
docs/                   notes that outlive any one generator
Makefile                the tasks; `make help` lists them
pyproject.toml          ruff configuration (this repo is not a package)
```

Where to look for a thing:

| you want | it is in |
| --- | --- |
| to generate pages | `generators/` |
| to make pages look old or scanned | `degradation/` |
| to see what the output looks like | `samples/` |
| to run something end to end | `tools/`, or `make help` |
| why a version is pinned | `docs/` |

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
  [docs/python-versions.md](docs/python-versions.md) for the measurements.

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

## Augmentation

[`degradation/`](degradation/README.md) is a Python port of the degradation models from
[DocCreator](https://github.com/DocCreator/DocCreator) — local ink decay,
bleed-through, blur zones, binding shadow, holes. It runs on whatever a
generator produced, so the same ageing can be applied to receipts and to
genalog pages alike.

```bash
python tools/augment_samples.py --synthdog <dir> --genalog <dir> -o samples/degradation
```

[`samples/degradation/`](samples/degradation) holds twenty before/after pairs —
ten synthdog receipts, five genalog pages, five html-table tables — each with
the chain suited to it:

| source | chain | why |
| --- | --- | --- |
| synthdog receipts | ink decay, blur zones, bottom shadow | a thermal bill creased in a pocket |
| genalog pages | ink decay, bleed-through, blur zones, spine shadow, holes | an office document photocopied and bound |
| html-table tables | ink decay, blur zones, top shadow | small and sparse: page-sized settings overwhelm it, and mirrored bleed-through lands in the empty cells and reads as a double exposure |

[genalog](https://github.com/microsoft/genalog) is an external dependency, not
part of this repository:

```bash
pip install --no-deps genalog       # its opencv pin stops at cp38; skip its deps
pip install numpy "opencv-python<5" pillow scikit-image jinja2 cairocffi weasyprint pymupdf
```

It calls WeasyPrint's `write_png()`, removed in WeasyPrint 53, so
`tools/augment_samples.py` renders through PDF instead.

---

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) covers which environment to build for which
generator, the checks to run before pushing, and the constraints that are
deliberate.

## Licence

Not yet chosen — add one before publishing. `generators/html-table/` carries its
own `LICENSE.md`.
