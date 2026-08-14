# Generating datasets

## Generating a dataset

One page is a point in a **scenario space** — four axes, sampled per page with
weights you control:

| axis | what it decides | declared in |
| ---- | --------------- | ----------- |
| `layout` (10) | what the page *is*: page size, which blocks, table shape — anything that changes the ground truth | `variations/layouts.py` |
| `backend` (3) | `synthdog`, `html-flow`, `html-absolute` | `variations/__init__.py` |
| `style` (15) | how it looks before ageing: fonts, margins, borders, CSS | `variations/styles.py` |
| `degradation` (10) | what happened to it after printing: a `PaperConfig` | `variations/degradations.py` |

```bash
# Plan the run and print the distribution you would actually get — renders nothing
python -m vlm_ocr_synthetic generate -c configs/datasets/default.yaml --dry-run

# Render it
python -m vlm_ocr_synthetic generate -c configs/datasets/default.yaml -o data/dataset

# Overrides for a quick look
python -m vlm_ocr_synthetic generate -n 20 --scale 0.5 --mode stratified -o /tmp/peek
```

`--dry-run` first, every time. It catches weight typos, impossible combinations
and a distribution that is not what you meant, before you spend an hour
rendering:

```
pages                  200
images                 400
combinations available 1505
combinations used      307

layout
  receipt_80mm                    66   16.5%  ########
  receipt_58mm                    62   15.5%  ########
  ...
```

### Output

```
data/dataset/
├── pages/000123-0-light_scan.png    # image
├── pages/000123-0-light_scan.json   # the document, every bbox filled in
├── manifest.jsonl                   # one line per image
└── summary.json                     # the config, and the realised distribution
```

Each manifest line records everything that produced the page, so any single one
can be reproduced without rerunning the batch:

```json
{"index": 123, "seed": 1234003702, "layout": "receipt_80mm", "backend": "html-flow",
 "style": "thermal_17", "degradation": "light_scan", "renderer": "html",
 "image_size": [576, 1000], "blocks": 9,
 "image": "pages/000123-0-light_scan.png", "annotation": "pages/000123-0-light_scan.json"}
```

### Tuning the distribution

`configs/datasets/default.yaml` holds **only weights** — variants live in Python because
their values are objects (a `PaperConfig`, a callable, a dict of renderer
options). Weights are relative, not probabilities:

```yaml
axes:
  layout:
    receipt_80mm: 5      # picked 5x as often as a weight of 1
    receipt_58mm: 3
    invoice_a4_flow: 0   # switched off, but still declared
  degradation:
    clean: 3
    light_scan: 5
```

- **A weight of 0** disables a variant without deleting it — the usual way to
  narrow a run.
- **An unknown name raises.** `foldd_once: 3` is a typo that would otherwise
  silently change nothing; instead it fails on load.
- **Only the axes you mention are changed**; everything else keeps its
  in-code default weight.

Two sampling modes, and the difference matters:

| mode | behaviour | use when |
| ---- | --------- | -------- |
| `sample` | independent draws honouring the weights | you want a realistic mix |
| `stratified` | walks every compatible combination before repeating one | you want coverage |

With 1500 combinations and a skewed distribution, `sample` will leave some
combinations out entirely — at 200 pages the shipped config touches ~307 of
them. If a rare combination has to appear, use `stratified`.

### Keeping impossible combinations out

The cross product contains nonsense: an A4 office style on 58mm thermal paper,
absolute layout for a document that pins nothing. Variants declare `tags` and
`requires`, and axes are resolved in order — `layout` first — so each later axis
only sees variants compatible with what came before:

```python
Variant("receipt_58mm", ..., tags=frozenset({"thermal", "narrow"}))
Variant("thermal_20_large", ..., requires=frozenset({"wide_thermal"}))  # 80mm only
Variant("html-absolute", ..., requires=frozenset({"pinned"}))
```

This is why `html-absolute` is only ~2.5% of a run even at weight 1: only the
`invoice_a4` layout pins its blocks. That is the constraint working, not a bug.

### Cost

A page is laid out **once** and aged `degradations_per_page` times, because the
paper layer is a separate stage. With the browser backend that turns a ~0.2 s
layout into ~0.01 s per extra variant:

```yaml
pages: 5000
degradations_per_page: 3   # 15000 images, 5000 layout passes
```

## Adding your own attributes and resources

### A new degradation

Append a `Variant` to `DEGRADATIONS` in `variations/degradations.py`:

```python
(
    Variant(
        "rain_damage",
        PaperConfig(color=(240, 238, 230), grain=8.0, blur=0.8, salt=0.006),
        weight=1,
        requires=frozenset({"thermal"}),  # optional: only on receipts
    ),
)
```

It is immediately sampleable, weightable from YAML, and covered by the
`--dry-run` report. Nothing else needs touching.

### A new style

Append to `STYLES` in `variations/styles.py`. A style carries one dict per
backend because they take different keys, and `common` for what they share:

```python
(
    Variant(
        "thermal_narrow_bold",
        Style(
            common={"margin": 28, "block_spacing": 10},
            synthdog={"font_path": MONO_BOLD, "font_size": 16},
            html={"font_family": MONO, "font_size": 16, "extra_css": RECEIPT_CSS},
        ),
        weight=2,
        requires=frozenset({"thermal"}),
    ),
)
```

**A style must never change the ground truth** — no new blocks, no different
text. If your change would alter the annotation, it belongs on the layout axis.

### A new layout

A layout's value is a callable `(rng) -> Document`. Build it from the corpus so
the numbers stay consistent, and declare the tags styles will filter on:

```python
def _delivery_note() -> DocumentFactory:
    def factory(rng: random.Random) -> Document:
        order = sample_order(rng, 3, 8)
        return build_receipt_document(order=order, table_number=rng.randint(1, 40))

    return factory


Variant("delivery_note", _delivery_note(), weight=2, tags=frozenset({"thermal"}))
```

`tests/dataset/test_generate.py::test_every_layout_builds_a_valid_document` picks it up
automatically and will fail if it produces a document that breaks the corpus
rule.

### A whole new axis

Add an `Axis` and put it in `DEFAULT_SPACE` in `variations/__init__.py`, after
the axes whose tags it depends on:

```python
LANGUAGE_AXIS = Axis("language", (Variant("vi", weight=4), Variant("en", weight=1)))
DEFAULT_SPACE = ScenarioSpace(axes=(LAYOUT_AXIS, LANGUAGE_AXIS, BACKEND_AXIS, ...))
```

Then read it wherever it applies — `pipeline.build_document` for content,
`render_options` for anything the renderer needs. The CLI, `--dry-run`, the
manifest and the summary pick up new axes without changes.

### Resources: fonts, paper photographs

Nothing binary is shipped with the package; resources are referenced by path.

**Fonts** — set `font_path` / `bold_font_path` on synthdog and `font_family` on
html, in a style variant. Check coverage before a big run: a font missing
Vietnamese diacritics renders boxes and no test would notice.

**Paper photographs** — point `texture` at a file or a directory and one is
picked per page from the seed. This is how you use synthdog's own
`resources/paper`, or your own scans:

```python
(
    Variant(
        "real_paper",
        PaperConfig(texture="resources/paper", texture_strength=0.8, grain=3.0),
        weight=2,
    ),
)
```

Keep resources out of git (`.gitignore` already excludes `assets/fonts/`,
`*.ttf`, `resources/backgrounds/`) and record the path in your run config so a
dataset can be traced back to what produced it.

## Using the dataset

`manifest.jsonl` is the entry point — stream it, do not glob the directory:

```python
from vlm_ocr_synthetic.dataset import read_manifest

for entry in read_manifest("data/dataset/manifest.jsonl"):
    image_path = f"data/dataset/{entry['image']}"
    annotation = json.load(open(f"data/dataset/{entry['annotation']}"))

    document = annotation["document"]  # blocks, tables, every bbox filled in
    scale = annotation["metadata"]["scale"]  # bboxes are in document space
```

Filter by scenario before training — the manifest carries the axes, so a
held-out split by degradation or layout is one comprehension:

```python
entries = list(read_manifest("data/dataset/manifest.jsonl"))
train = [e for e in entries if e["degradation"] != "photocopy_dark"]
test = [e for e in entries if e["degradation"] == "photocopy_dark"]
```

**Boxes are in document space, not pixels** — multiply by
`metadata["scale"]` for pixel coordinates (`BBox.scaled(scale)` does it). This
is what lets one annotation serve renders at several resolutions.

What you build from there depends on the task: layout detection wants the block
boxes and `block_type`; table recognition wants the cell boxes with
`rowspan`/`colspan`; a text-generation target wants the content serialised in
reading order. That serialisation step is deliberately not in this package yet —
it is the one choice that depends entirely on the model you are training.
