# vlm-ocr-synthetic

Synthetic Vietnamese document images for training and evaluating VLM / OCR
models, with structured labels.

**One rule-base, three renderers.** What a page contains is decided once, in
[`rulebase/`](rulebase/README.md); how it is drawn is decided three different
ways. The same seed gives the same words in the same columns whether the page
was drawn glyph by glyph, screenshotted from a browser, or printed through
WeasyPrint — which is what makes a comparison between the three mean anything.

```bash
git clone https://github.com/LinhPhuong14/vlm-ocr-synthetic.git
cd vlm-ocr-synthetic
make setup          # three environments, one per renderer
make dataset        # 60 labelled images into data/dataset60/
make proof          # read them back with Tesseract and score the labels
```

| renderer | how it draws | looks like | Python |
| --- | --- | --- | --- |
| [`generators/synthdog/`](generators/synthdog/README_vi_receipt.md) | [synthtiger](https://github.com/clovaai/synthtiger) glyph layers, then curl + background | a **photograph** of a receipt on a table | **3.8 – 3.11** |
| [`generators/html/`](generators/html/README.md) | HTML positioned on a character grid, screenshotted in Chromium | a **flat scan** | 3.9+ |
| [`generators/genalog/`](generators/genalog/README.md) | [genalog](https://github.com/microsoft/genalog) → WeasyPrint → PDF → raster | a **print/photocopy** | 3.9+ |

Those three differences are deliberate. A model that has only seen browser
screenshots has not seen a print engine's text shaping, and one that has only
seen flat scans has not seen a page lying under a lamp.

A fourth generator, [`generators/html-table/`](generators/html-table/README.md),
is vendored upstream code for general table images. It does not read the
rule-base.

---

## Repository layout

```
rulebase/               THE RULE-BASE — one source of truth for content
├── rules/              6 thuộc tính: document, layout, content, visual,
│                       color, augmentation. Weighted, with constraints.
├── layouts/            5 bố cục measured off real Vietnamese receipts
└── corpus/vi/          Vietnamese corpus, with diacritics

generators/             THE RENDERERS — each with its own venv
├── synthdog/           glyph rendering (synthtiger)
├── html/               HTML + headless Chromium
├── genalog/            genalog + WeasyPrint
└── html-table/         vendored TableGeneration (not rule-base driven)

degradation/            DocCreator's degradation models, ported to Python
├── texture.py          paper texture, gradient-domain stains, phantom chars
├── ink_degradation.py  local ink decay
├── shadow_binding.py   shadow near a page's spine
├── bleed_through.py    ink from the other side of the sheet
├── blur_zones.py       blur in patches, not over the whole page
├── holes.py            tears and rips, the missing paper filled black
└── pipeline.py         runs a recipe's chain — all three renderers call this

textures/paper/         the sheets every renderer composites onto
fonts/                  fonts every renderer uses (Vietnamese coverage checked)
data/                   generated datasets: aged and clean, with labels and OCR proof
samples/                curated examples
tools/                  drivers: dataset, proof, previews, checks
docs/                   notes that outlive any one generator
Makefile                the tasks; `make help` lists them
```

Where to look for a thing:

| you want | it is in |
| --- | --- |
| to change what receipts say | `rulebase/corpus/`, `rulebase/rules/content.yaml` |
| to change how often something appears | the `weight:` fields in `rulebase/rules/` |
| to add a receipt layout | `rulebase/layouts/` |
| to change how a page is drawn | `generators/<renderer>/` |
| to make pages look old or scanned | `degradation/` |
| the labelled datasets | `data/dataset60/` (aged), `data/dataset60_clean/` (clean) |
| one picture per degradation model | `samples/degradation/` |
| to run something end to end | `make help` — the tasks are there, not in a directory |
| why a version is pinned | `docs/python-versions.md` |

Three names appear twice in the tree and mean different things. If you are
about to edit one, check which:

| the shared one | the glyph renderer's own |
| --- | --- |
| `rulebase/layouts/` — the five receipt bố cục (YAML) | `generators/synthdog/layouts/` — SynthDoG's grid code, used only by its original wiki template |
| `rulebase/corpus/vi/` — the Vietnamese receipt corpus | `generators/synthdog/resources/corpus/` — wiki text for those same original templates |
| `textures/paper/`, `fonts/` — committed, used by all three renderers | `generators/synthdog/resources/{paper,font}/` — yours to supply, git-ignored, overrides the shared set |

`generators/html/` and `generators/html-table/` are also easy to confuse: the
first renders receipts from the rule-base, the second is vendored code for
generic table images and does not read the rule-base at all.

---

## The rule-base

Six attributes, drawn in order, each seeing the tags the earlier ones set:

| # | thuộc tính | quyết định |
| --- | --- | --- |
| 1 | `document` | loại document — quán nhậu, siêu thị, hoá đơn GTGT |
| 2 | `layout` | bố cục — cột nào, mỗi mặt hàng mấy dòng |
| 3 | `content` | nội dung — có dấu / không dấu, IN HOA, kiểu tiền, VAT |
| 4 | `visual` | hình thức — font, cỡ chữ, độ đậm mực, lề trắng, tờ giấy, độ cong |
| 5 | `color` | màu — mực, ám giấy, màu nhấn |
| 6 | `augmentation` | làm cũ — chuỗi degradation chạy sau khi render |

Every value carries a weight, so the mix is tuned by editing numbers in
`rulebase/rules/*.yaml` and nothing else. Values also `require` and `exclude`
tags, which is what stops the sampler pairing a 2011 thermal printer with
accented Vietnamese, or a quán nhậu bill with a barcode column.

```bash
make distribution        # what 2000 draws actually look like
make check-rules         # unreachable values, typo'd tags, missing files
make preview-grid        # one sampled receipt per bố cục, as text
```

Full guide — adding attributes, layouts, corpus entries, tuning the
distribution: **[`rulebase/README.md`](rulebase/README.md)**.

### The five bố cục

Each was measured off a photograph of a real receipt; `source:` in the file
says which.

| id | dấu hiệu nhận biết |
| --- | --- |
| `quan_nhau_stt` | cột **Stt**, mỗi món hai dòng: tên trên, `SL / đơn giá / thành tiền` dưới |
| `quan_an_ascii` | máy in nhiệt đời cũ: IN HOA KHÔNG DẤU, một dòng một món, không có tiêu đề cột |
| `sieu_thi_barcode` | mã vạch + tiền ở dòng trên, tên hàng thụt xuống dòng dưới, dòng `KM` cho khuyến mãi |
| `sieu_thi_gia_sl` | tên hàng ngắt dòng ngay trong cột `Mặt hàng`, meta nối bằng `\|` |
| `sieu_thi_vat` | dòng `VAT x%` riêng cho từng mặt hàng, tiền hai chữ số thập phân |

---

## Degradation

[`degradation/`](degradation/README.md) is a Python port of the degradation
models from [DocCreator](https://github.com/DocCreator/DocCreator) (Journet,
Mansencal, Kieu et al., LaBRI Bordeaux). It runs on whatever a renderer
produced, so the same ageing applies to all three.

Three of the models work by pasting a **texture** rather than by filtering, and
they are the ones that stop a synthetic page looking synthetic:

| model | DocCreator source | what it does |
| --- | --- | --- |
| `paper_texture` | `Context::BackgroundContext` | draws the page onto a sheet of paper instead of onto white, with grain and fold creases |
| `gradient_domain` | `GradientDomainDegradation.cpp` | pastes stains with Poisson blending (`cv::seamlessClone`, `MIXED_CLONE`) — Seuret et al., ICDAR 2015 |
| `phantom_character` | `PhantomCharacter.cpp` | pastes leftover ink against the flanks of characters, sized from each character's own box |

The rest — `ink_degradation`, `bleed_through`, `blur_zones`, `shadow_binding`
— are the filtering models, and `holes` is the tear model: DocCreator's
`HoleDegradation`, which cuts paper away and fills what is missing with black,
because a page photographed over a dark surface shows dark through the tear.
`make list-degradations` prints the lot.

DocCreator ships its textures as image files under an LGPL licence; those are
not vendored. The patterns are synthesised from a seed instead, and a directory
of real scans is used in preference when you point at one.

```bash
make showcase       # one before/after image per model, on the same page
```

**Every renderer ages its pages through the same `degradation.pipeline`**, and
the paper comes from the recipe's `visual.paper`, so a recipe puts the same
sheet under a glyph render and an HTML render. Papers live in
[`textures/paper/`](textures/paper) and are generated by `make textures`;
replace them with real scans under the same names and nothing else changes.

---

## The datasets and the OCR proof

`make dataset` writes 20 images per renderer, spread evenly over the five bố
cục so a comparison is not confounded by one renderer having drawn more
supermarket receipts than another. Each image comes with a CORD-style nested
label, the full recipe that produced it, and — for the glyph renderer —
per-cell polygons that survive the paper curl.

Two sets are committed, differing in **one attribute** of the rule-base:

| set | | Tesseract token recall (synthdog / html / genalog) |
| --- | --- | --- |
| [`data/dataset60/`](data/dataset60) | ageing sampled from the rules | 0.41 / 0.68 / 0.76 |
| [`data/dataset60_clean/`](data/dataset60_clean) | `augmentation=khong_lam_gi`, no distortion | 0.85 / 0.85 / 0.87 |

```bash
make dataset          # aged
make dataset-clean    # clean
make proof DATASET=data/dataset60
```

`make proof` reads a set back with Tesseract 5 (`vie`) and scores what came
back against the labels. Scoring is order-free: Tesseract reads a two-column
receipt in whatever order its layout analysis picks, so comparing its output to
the label as one string would measure reading order rather than recognition.

The clean set is the ceiling, and it earns its place twice over. It is near
uniform across renderers (0.85–0.87), which says the spread in the aged set
comes from the ageing and not from one renderer generating worse pages. And
because a label that did not match its pixels would cap the clean score too, a
clean run is the cheapest check that the two agree.

Results, and what the numbers mean, are in
[`data/dataset60/proof/README.md`](data/dataset60/proof/README.md) and
[`data/dataset60_clean/proof/README.md`](data/dataset60_clean/proof/README.md).

---

## Table images

Vendored from [TIES_DataGeneration](https://github.com/hassan-mahmood/TIES_DataGeneration),
extended with configurable cell types, merged cells and colours. Independent of
the rule-base.

```bash
cd generators/html-table
pip install -r requirements.txt
python generate_data.py --help
```

---

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) covers which environment to build for which
renderer, the checks to run before pushing, and the constraints that are
deliberate.

## Licence

Not yet chosen — add one before publishing. `generators/html-table/` carries its
own `LICENSE.md`; the fonts in `fonts/` carry theirs (see
[`fonts/README.md`](fonts/README.md)).
