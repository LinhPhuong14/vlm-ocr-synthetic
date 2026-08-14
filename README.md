# vlm-ocr-synthetic

Synthetic document images for training and evaluating VLM / OCR models, with
structured labels. Three generators live here, each self-contained:

| directory | what it generates | how | Python |
| --- | --- | --- | --- |
| [`synthdog/`](synthdog/README_vi_receipt.md) | Vietnamese thermal-printer receipts, with structured ground truth for Donut | [synthtiger](https://github.com/clovaai/synthtiger) templates | **3.8 – 3.12** |
| [`html-table/`](html-table/README.md) | table images with cell-level annotations | HTML rendered in a browser | 3.8+ |
| [`genalog/`](https://github.com/microsoft/genalog) | degraded document images from text | Microsoft genalog, as a submodule | 3.6 – 3.8 |

```bash
git clone --recurse-submodules https://github.com/LinhPhuong14/vlm-ocr-synthetic.git
```

Already cloned without submodules? `git submodule update --init`.

---

## Vietnamese receipts — `synthdog/`

The main generator: thermal-printer bills for restaurants and shops, with
diacritics, VAT, discounts and change, on paper that is skewed, curled and
blurred differently every time.

```bash
cd synthdog
python -m venv .venv && source .venv/bin/activate
pip install -U pip setuptools wheel      # required, see requirements.txt
pip install -r requirements.txt

synthtiger -o ./outputs/VNReceipt -c 1000 -w 4 -v \
    template_receipt.py SynthVNReceipt config_vi_receipt.yaml
```

Full instructions, including the config knobs and troubleshooting:
[`synthdog/README_vi_receipt.md`](synthdog/README_vi_receipt.md).

**Python 3.13+ will not work here**, and the version cap is not caution — the
pins in `synthdog/requirements.txt` each come from a real failure
(`pillow<10`, `numpy<2`, `opencv-python<5`). [`docs/python-314.md`](docs/python-314.md)
has the measurements, including which wheels stop existing where.

---

## Table images — `html-table/`

Vendored from [TIES_DataGeneration](https://github.com/hassan-mahmood/TIES_DataGeneration),
extended with configurable cell types, merged cells and colours. Renders tables
through a browser and writes cell-level annotations.

```bash
cd html-table
pip install -r requirements.txt
python generate_data.py --help
```

---

## Degraded documents — `genalog/`

[Microsoft genalog](https://github.com/microsoft/genalog) as a submodule: HTML
templates plus a degradation pipeline (blur, bleed-through, salt, pepper,
morphology). Useful when you have text and want scanned-looking pages from it.

---

## Repository layout

```
synthdog/      SynthDoG-VN: templates, configs, corpora, tools
html-table/    vendored HTML table generator
genalog/       submodule -> microsoft/genalog
resources/     shared corpora (wiki text for synthtiger)
docs/          notes worth keeping across generators
```

`make help` lists the tasks: `make setup` prepares the synthdog environment,
`make lint` and `make check` keep the repo's own scripts tidy.

## Licence

Not yet chosen — add one before publishing. Note that `html-table/` carries its
own `LICENSE.md`, and `genalog/` is MIT-licensed upstream.
