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

No `make` — on Windows, or anywhere — use the task runner directly. Every task
is defined there and the Makefile only forwards to it, so the two cannot drift:

```powershell
py -3.11 tasks.py setup
py tasks.py dataset
py tasks.py            # list the tasks
```

Windows needs three things installed by hand (Python 3.11, GTK for WeasyPrint,
Tesseract); [`docs/windows.md`](docs/windows.md) has the list.

---

## The three renderers

Every renderer receives the same `(recipe, receipt, grid)` from the rule-base
and is responsible for exactly one thing: turning a grid of character-positioned
cells into pixels. They disagree about everything after that, and the
disagreement is the point — a model that has only seen browser screenshots has
not seen a print engine's text shaping, and one that has only seen flat scans
has never seen a page lying under a lamp.

| | `generators/synthdog/` | `generators/html/` | `generators/genalog/` |
| --- | --- | --- | --- |
| **engine** | [synthtiger](https://github.com/clovaai/synthtiger) glyph layers | Chromium, headless | [genalog](https://github.com/microsoft/genalog) → WeasyPrint |
| **output** | a **photograph** of a receipt on a table | a **flat scan** | a **print / photocopy** |
| **text layout** | ours, per glyph | the browser's | WeasyPrint's |
| **geometry** | curl, perspective, lighting | none | page box, real pagination |
| **per-cell polygons** | yes, they follow the curl | no | no |
| **Python** | **3.8 – 3.11** | 3.9+ | 3.9+ |
| **cost per page** | ~1.6 s | ~1.2 s | ~0.7 s |
| **extra install** | — | a browser | GTK (Pango, cairo) |

### What each is good and bad at

**synthdog — glyph rendering.** It positions every text layer itself, so it is
the only one that knows where each cell ended up *after* the paper was curled
and the photograph taken. That is why it is the only renderer that emits
per-cell polygons, and it is the reason to keep it: detection and
text-spotting training needs boxes, and the other two cannot produce them
without re-running OCR on their own output. It also produces by far the hardest
images — background, perspective, lamp, shadow — which is exactly the
distribution a phone photo of a receipt falls into.

The cost is that it owns the whole text stack. No line breaking, no kerning, no
font fallback comes for free; anything the grid does not specify does not
happen. It is the slowest of the three -- roughly 1.6 s a page against
genalog's 0.7 s, measured warm on a 4-core container -- it is pinned below
Python 3.12 by
synthtiger's own dependencies (see [`docs/python-versions.md`](docs/python-versions.md)),
and its OCR scores are the lowest — not because the pages are worse but because
they are photographs.

**html — a browser.** Cheapest to work on by a wide margin: the layout is CSS,
so a change is a line of stylesheet and the result is inspectable in any
browser. Chromium brings real text shaping, real font fallback and correct
diacritic positioning for free, which matters for Vietnamese — stacked tone
marks are exactly where a hand-rolled renderer goes wrong.

The cost is that the output is *flat*. There is no camera, no paper geometry
and no lighting, so it is a scan and nothing else, and it cannot tell you where
a cell landed. Two CSS traps are load-bearing and documented in `render.py`:
`ch` units are relative to the element's own font size (so scaling a positioned
cell scales the grid under it), and an element screenshot clips at the
element's box (so a cell set above 1em is decapitated unless the sheet reserves
its overflow).

**genalog — a print engine.** WeasyPrint is a genuinely different code path
from a browser: a page box, real pagination, its own text shaper. Pages come
out looking printed rather than screenshotted, and the differences from
Chromium — hyphenation, line-break decisions, hinting — are free variety no
amount of CSS tweaking in the browser backend would produce. It scores highest
under Tesseract, which makes it the useful *upper* end of a difficulty curve.

The cost is age and dependencies. genalog is pinned to 2020 (`numpy==1.18.1`,
`WeasyPrint==51`, `scikit-image==0.16.2`), none of which has a wheel for Python
3.9+, so its source is **vendored** under `generators/genalog/genalog/` rather
than installed — the pins never apply and the dependencies come from
`requirements.txt` at versions that exist. `Document.render_png()` calls
WeasyPrint's `write_png()`, removed in WeasyPrint 53, so `render.py` goes
through `render_pdf()` and rasterises with PyMuPDF. WeasyPrint also needs Pango
and cairo, which is a system install and the only reason Windows setup is more
than `pip`.

### Where they diverge as *synthetic data*

Rendering aside, the three differ in what kind of training signal they produce:

| | synthdog | html | genalog |
| --- | --- | --- | --- |
| **what varies between two seeds** | content, paper, curl, camera, light | content, paper | content, paper, pagination |
| **degrees of freedom the renderer adds** | many — the scene is sampled | none — deterministic given the grid | few — the page engine decides breaks |
| **failure mode to watch** | text unreadable under heavy ageing | too easy; a model overfits to clean scans | a long page silently paginates |
| **labels it can support** | parsing, detection, spotting | parsing | parsing |
| **use it for** | robustness to real photos | volume, and the clean-set ceiling | shaping variety, print-like domain |

All three write the same `metadata.jsonl` — `file_name`, `ground_truth`
(CORD-style nested), `text_sequence`, `recipe` — so a training script does not
need to know which produced a file.

A fourth generator, `generators/html-table/`, is vendored upstream code for
table images. It does not read the rule-base, and it solves a different problem
— see [Table images](#table-images) below.

---

## Repository layout

```
rulebase/               THE RULE-BASE — one source of truth for content
├── rules/              6 attributes: document, layout, content, visual,
│                       color, augmentation. Weighted, with constraints.
├── layouts/            5 layouts measured off real Vietnamese receipts
└── corpus/vi/          Vietnamese corpus, with diacritics

generators/             THE RENDERERS — each with its own venv
├── synthdog/           glyph rendering (synthtiger)
├── html/               HTML + headless Chromium
├── genalog/            genalog + WeasyPrint (source vendored)
└── html-table/         vendored TableGeneration (not rule-base driven)

degradation/            DocCreator's degradation models, ported to Python
├── texture.py          paper texture and overlay, stains, phantom chars
├── ink_degradation.py  local ink decay
├── shadow_binding.py   shadow near a page's spine
├── bleed_through.py    ink from the other side of the sheet
├── blur_zones.py       blur in patches, not over the whole page
├── holes.py            tears and rips, the missing paper filled black
└── pipeline.py         runs a recipe's chain — all three renderers call this

textures/paper/         the sheets a page is printed ON (generated)
textures/background/    the scenes a sheet is photographed on (photographs)
augmentations/data/image/  paper photographs laid OVER a finished render
fonts/                  fonts every renderer uses (Vietnamese coverage checked)
data/                   generated datasets: aged, clean, and table structure
samples/                curated examples
tools/                  drivers: dataset, proof, previews, checks
docs/                   notes that outlive any one generator
tasks.py                every task, and the only definition of them
Makefile                forwards to tasks.py; `make help` lists them
```

Where to look for a thing:

| you want | it is in |
| --- | --- |
| to change what receipts say | `rulebase/corpus/`, `rulebase/rules/content.yaml` |
| to change how often something appears | the `weight:` fields in `rulebase/rules/` |
| to add a receipt layout | `rulebase/layouts/` |
| to change how a page is drawn | `generators/<renderer>/render.py` |
| to make pages look old or scanned | `degradation/` |
| the labelled datasets | `data/dataset60/` (aged), `data/dataset60_clean/` (clean) |
| one picture per degradation model | `samples/degradation/` |
| to run something end to end | `make help` — the tasks are there, not in a directory |
| why a version is pinned | `docs/python-versions.md` |
| to run it on Windows | [`docs/windows.md`](docs/windows.md) |
| how a renderer works, function by function | [`docs/huong-dan-va-giai-thich.md`](docs/huong-dan-va-giai-thich.md) |

### Three directories of images, and which is which

They are all photographs of surfaces and they are easy to mix up. What
separates them is **where in the pipeline they enter**, not what they show:

| directory | when it is used | what it does |
| --- | --- | --- |
| `textures/paper/` | before anything is drawn | the sheet the text is printed on. `paper_texture` is multiplicative, so it darkens and never lightens — ink stays ink. Named by `visual.paper`. |
| `augmentations/data/image/` | last step of the chain | a photograph of a real sheet laid over the finished page, ink included. This is what gives fibre, fold shadow and the off-white cast. Used by `paper_overlay`. |
| `textures/background/` | after ageing, glyph renderer only | the scene the sheet is photographed on. Only synthdog composites onto one; the other two produce a sheet with no surroundings. |

`generators/html/` and `generators/html-table/` are also easy to confuse: the
first renders receipts from the rule-base, the second is vendored code for
generic table images and does not read the rule-base at all.

---

## The rule-base

Six attributes, drawn in order, each seeing the tags the earlier ones set:

| # | attribute | decides |
| --- | --- | --- |
| 1 | `document` | what kind of document — eatery, supermarket, VAT invoice |
| 2 | `layout` | which columns, how many lines per item |
| 3 | `content` | diacritics or not, upper case, money format, VAT |
| 4 | `visual` | font, size, ink weight, white margin, sheet, curl |
| 5 | `color` | ink, paper tint, accent colour |
| 6 | `augmentation` | the degradation chain that runs after rendering |

Identifiers are English, printed strings are Vietnamese — the boundary and the
reason for it are in [`rulebase/README.md`](rulebase/README.md).

Every value carries a weight, so the mix is tuned by editing numbers in
`rulebase/rules/*.yaml` and nothing else. Values also `require` and `exclude`
tags, which is what stops the sampler pairing a 2011 thermal printer with
accented Vietnamese, or an eatery bill with a barcode column.

```bash
make distribution        # what 2000 draws actually look like
make check-rules         # unreachable values, typo'd tags, missing files
make preview-grid        # one sampled receipt per layout, as text
```

Full guide — adding attributes, layouts, corpus entries, tuning the
distribution: **[`rulebase/README.md`](rulebase/README.md)**.

A line-by-line walkthrough of all three renderers, in Vietnamese, with the
reasoning behind each decision and a Q&A:
**[`docs/huong-dan-va-giai-thich.md`](docs/huong-dan-va-giai-thich.md)**.

### The five layouts

Each was measured off a photograph of a real receipt; `source:` in the file
says which.

| id | how to recognise it |
| --- | --- |
| `eatery_indexed` | an **Stt** (index) column; two lines per item — name above, `qty / unit price / amount` below |
| `eatery_ascii` | old thermal printer: UPPER CASE, NO DIACRITICS, one line per item, no column header |
| `market_barcode` | barcode and money on the first line, item name indented on the next, a `KM` line for promotions |
| `market_compact` | the item name wraps inside the `Mặt hàng` column, meta joined with `\|` |
| `market_vat` | a `VAT x%` line per item, money to two decimal places |

---

## Degradation

[`degradation/`](degradation/README.md) is a Python port of the degradation
models from [DocCreator](https://github.com/DocCreator/DocCreator) (Journet,
Mansencal, Kieu et al., LaBRI Bordeaux). It runs on whatever a renderer
produced, so the same ageing applies to all three.

Four of the models work by pasting a **texture** rather than by filtering, and
they are the ones that stop a synthetic page looking synthetic:

| model | DocCreator source | what it does |
| --- | --- | --- |
| `paper_texture` | `Context::BackgroundContext` | draws the page onto a sheet of paper instead of onto white, with grain and fold creases |
| `paper_overlay` | — (SynthDoG's `resources/paper/`) | lays a photograph of a real sheet over the finished page, ink included |
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
sheet under a glyph render and an HTML render. `visual.paper` may name one
sheet or a shortlist to draw from. Sheets live in
[`textures/paper/`](textures/paper) and are generated by `make textures`;
replace them with real scans under the same names and nothing else changes.

---

## The datasets and the OCR proof

`make dataset` writes 20 images per renderer, spread evenly over the five
layouts so a comparison is not confounded by one renderer having drawn more
supermarket receipts than another. Each image comes with a CORD-style nested
label, the full recipe that produced it, and — for the glyph renderer —
per-cell polygons that survive the paper curl.

Two sets are committed, differing in **one attribute** of the rule-base:

| set | | Tesseract token recall (synthdog / html / genalog) |
| --- | --- | --- |
| [`data/dataset60/`](data/dataset60) | ageing sampled from the rules | see the proof report |
| [`data/dataset60_clean/`](data/dataset60_clean) | `augmentation=pristine`, no distortion | see the proof report |

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
uniform across renderers, which says the spread in the aged set comes from the
ageing and not from one renderer generating worse pages. And because a label
that did not match its pixels would cap the clean score too, a clean run is the
cheapest check that the two agree.

Results, and what the numbers mean, are in
[`data/dataset60/proof/README.md`](data/dataset60/proof/README.md) and
[`data/dataset60_clean/proof/README.md`](data/dataset60_clean/proof/README.md).

---

## Table images

Vendored from [TIES_DataGeneration](https://github.com/hassan-mahmood/TIES_DataGeneration),
extended with configurable cell types, merged cells and colours. Independent of
the rule-base.

```bash
make setup-tables
make tables              # 60 tables into data/tables60/
```

**A different task, not more of the same data.** The receipt sets teach a model
to *parse a document* (a nested CORD record); this one teaches it to *recover a
table's structure* (the `<td>` tokens, the spans, a box per cell). The two
labels share no schema — only the `metadata.jsonl` file name, so a loader finds
them the same way. Published set and its caveats:
[`data/tables60/`](data/tables60).

`tools/generate_tables.py` wraps the vendored code without editing it, and
supplies the three things it does not do itself: a browser it can find (it
never sets `binary_location`, so a `google-chrome` shim goes on PATH), a
chromedriver whose major version matches that browser, and Vietnamese cell text
in place of upstream's 13 MB of Chinese news.

Cell text is a random *character slice* of the corpus, upstream's design and
the right one for structure recognition — so these images teach **layout, not
language**. Use `data/dataset60/` for anything about reading.

---

## Contributing

[CONTRIBUTING.md](CONTRIBUTING.md) covers which environment to build for which
renderer, the checks to run before pushing, and the constraints that are
deliberate.

## Licence

Not yet chosen — add one before publishing. `generators/html-table/` carries its
own `LICENSE.md`; `generators/genalog/` carries genalog's (MIT); the fonts in
`fonts/` carry theirs (see [`fonts/README.md`](fonts/README.md)).
