# rulebase — the generation rules, shared by all three renderers

Everything about **what a synthetic page says** lives here. Everything about
**how it becomes pixels** lives in `generators/`. All three renderers begin
with the same three lines:

```python
recipe  = rulebase.sample_recipe(seed=7)          # draw a point in the rule space
receipt = rulebase.build_receipt(recipe)          # fill in the fields
grid    = rulebase.build_grid(receipt, recipe.layout.id)   # lay it out as cells
```

or, shorter: `recipe, receipt, grid = rulebase.make(seed=7)`.

The same seed gives the same words in the same columns, whether they are drawn
with glyphs, with Chromium or with WeasyPrint. That is the precondition for a
comparison between the three to mean anything — if each renderer invented its
own content, what you compared would be two datasets, not two ways of drawing.

```
rulebase/
├── rules/          6 ATTRIBUTES, one file each        ← tune the distribution here
├── layouts/        5 LAYOUTS measured off real receipts ← add a layout here
├── corpus/vi/      Vietnamese corpus, WITH diacritics  ← add products here
├── spec.py         weighted sampling with constraints
├── content.py      fills the fields and builds the label
├── layout.py       content + layout -> a grid of cells
└── text.py         diacritic folding, money formatting, wrapping
```

### Naming: English identifiers, Vietnamese printed text

The boundary runs in exactly one place: **what the code compares is English,
what reaches the image is Vietnamese.**

| English — an identifier | Vietnamese — content |
| --- | --- |
| `id`, `tags`, `requires`, `excludes` | `titles`, `total_labels` in `rules/document.yaml` |
| `profile: eatery \| market` | a column's `title:` in `layouts/*.yaml` |
| `paper: thermal_white` (a filename in `textures/paper/`) | the discount row's `label:`, `notes:` |
| a column's `key:`, `style:`, `money_style:` | everything in `corpus/vi/` |

Why the right-hand column is not translated too: it is **printed on the
receipt**. Turning `"Tiền hàng"` into `"Subtotal"` changes the dataset, not a
variable name — the images would stop being Vietnamese receipts. `id` and
`tags`, by contrast, exist only inside the sampler; keeping them English is
what makes `--force augmentation=torn_edges` readable without knowing
Vietnamese.

The label follows the same rule: `gt_parse.doc_type` is `receipt_eatery` /
`receipt_market`, while every field *value* stays Vietnamese.

---

## 1. The six attributes

Drawn in this order. Each attribute sees the `tags` the earlier ones set, so a
later one can rule itself out when it does not fit.

| # | attribute | decides | file |
| --- | --- | --- | --- |
| 1 | `document` | what kind of document: eatery, supermarket, VAT invoice… | [rules/document.yaml](rules/document.yaml) |
| 2 | `layout` | which columns, how many lines per item | [rules/layout.yaml](rules/layout.yaml) |
| 3 | `content` | diacritics or not, UPPER CASE, money format, VAT | [rules/content.yaml](rules/content.yaml) |
| 4 | `visual` | font, size, ink weight, **white margin**, sheet, curl | [rules/visual.yaml](rules/visual.yaml) |
| 5 | `color` | ink, paper tint, accent colour for the shop name | [rules/color.yaml](rules/color.yaml) |
| 6 | `augmentation` | ageing: the degradation chain that runs after rendering | [rules/augmentation.yaml](rules/augmentation.yaml) |

The order is not arbitrary — it follows causality. A shop decides what to print
long before the paper decides how it will crumple. So `document` is the
broadest choice and `augmentation` the narrowest.

### The shape of one value

```yaml
- id: supermarket                    # required, unique within the file
  weight: 3                          # relative frequency; 0 = never drawn
  tags: [doc_market, has_barcode]    # tags the later attributes will see
  requires: [doc_market]             # drawable only if the recipe ALREADY has these
  excludes: [ascii_only]             # not drawable if the recipe has any of these
  params:                            # passed straight to the code, unprocessed
    profile: market
    num_items: [3, 12]
```

`requires` / `excludes` is what blocks nonsense combinations. Without them the
sampler produces an eatery bill with an empty barcode column, or a 2011 thermal
printer that somehow prints "Phở" with its diacritics.

---

## 2. Tuning the distribution

Edit `weight`, not code.

```yaml
# to make 70% of receipts supermarket ones:
- id: pub_eatery          # weight: 3 -> 1
- id: supermarket         # weight: 3 -> 5
```

A weight is **relative to the candidates left after filtering**, not an
absolute probability. If `market_vat` is ruled out by
`requires: [has_vat_lines]`, its weight does not enter the denominator.

See what the distribution really is before a long run:

```bash
make distribution            # 2000 draws, counted per attribute
```

Check the rules for anything meaningless — a typo'd tag, a value that can never
be drawn. That class of mistake is silent: generation still runs, the value
simply never appears.

```bash
make check-rules
```

---

## 2b. The white margin around the content

Three keys in `rules/visual.yaml`, read by `rulebase.style.padding` and shared
by **all three renderers**:

```yaml
margin: [0.06, 0.13]         # left/right, as a FRACTION of the column count
padding_top: [2.4, 3.6]      # top, in LINE HEIGHTS
padding_bottom: [2.0, 3.2]   # bottom, in line heights
```

Top and bottom are deliberately **asymmetric**: a till feeds a long blank strip
before the print head starts, and a shorter one after.

Two things `padding` handles by itself, with nothing to declare in YAML:

* **The top margin always clears the tallest line.** The shop name and the
  title are enlarged (1.15–1.65em depending on the layout) and overflow their
  line box upwards. `padding` takes `max(padding_top, tallest + 0.5)`, so even
  a small `padding_top` cannot decapitate the shop name at the edge of the
  image.
* **All three renderers produce the same margin.** Each used to pick its own
  number: the glyph renderer `uniform(0.6, 1.8)` line heights, the two HTML
  renderers `0.6 + tallest`. The same recipe put the shop name at a different
  height in each.

> One trap in the HTML renderers: **CSS `padding` does not move
> `position:absolute` children** — they anchor to the parent's *padding box*,
> so no amount of `padding-top` shifts them. The top margin has to be added
> directly to each cell's `top`.

---

## 3. Adding a layout

1. Create `layouts/<name>.yaml`. Copy the closest existing file and edit it;
   record in `source:` which photograph it was measured from.
2. Declare it in `rules/layout.yaml` with the right `requires`.
3. Preview it as text, with no image rendering:

```bash
make preview-grid LAYOUT=<name>
```

### The grammar of a layout file

```yaml
width: [40, 48]        # paper width in CHARACTERS (80mm thermal ≈ 42-48)
gutter: 1              # characters left between two columns (0 = touching)
rule_char: "-"         # the character horizontal rules are drawn with

header:                # shop name, address, title
  name_scale: [1.15, 1.45]
  title: true
  branch: false        # drop a line entirely: WinMart prints no branch

meta:
  style: pairs         # pairs | two_column | pipes
  rule_after: false

columns:               # width 0 = "take what is left" (only for the name column)
  - {key: stt,        title: "Stt",      width: 4,  align: right}
  - {key: qty,        title: "Số lượng", width: 11, align: right}

item:
  wrap_name: true      # false = truncate long names, like an old till
  rows:                # each element is ONE printed line
    - - {col: stt, from: stt}
      - {from: name, span: [qty, amount]}   # spans from the qty column to the amount column
    - - {col: qty, from: qty}
      - {col: unit_price, from: unit_price}
  note_row: {indent: 2}                 # the indented item-name line (supermarket style)
  discount_row: {label: "KM"}
  original_price_row: {label: "Giá gốc:"}

totals:
  emphasise_grand: true
  grand_scale: [1.20, 1.55]
  grand_two_lines: true    # label on one line, the amount on the next
```

Sources usable in `from:`: `stt`, `name`, `qty`, `unit_price`, `amount`,
`barcode`, `barcode_name`, `vat`, `unit`, `note`.

A row whose every field is empty is skipped — which is what lets one template
serve both weighed goods (with a weight line) and packaged ones (without).

---

## 4. Adding products and shops

`corpus/vi/` is plain text, **TAB**-separated. Always write Vietnamese **with
diacritics** — the `content` attribute is what decides whether they are folded
away at render time, and folding is one-way: "Hẹn gặp lại" → "Hen gap lai"
works, the reverse does not.

| file | columns |
| --- | --- |
| `items_eatery.txt`, `items_market.txt` | name ⇥ min price ⇥ max price |
| `shops_eatery.txt` | name |
| `shops_market.txt` | brand ⇥ branch |
| `streets.txt`, `footers_*.txt` | one value per line |
| `wards.txt` | ward ⇥ district ⇥ province/city |
| `payments.txt` | label ⇥ group (`tienmat`/`the`/`vi`/`qr`) |

The `profile` in `rules/document.yaml` **is** the filename suffix:
`profile: market` reads `items_market.txt`. Adding a profile means adding three
corpus files with a matching suffix, not editing `corpus.py`.

A row with the wrong number of columns is skipped rather than failing the whole
run — a corpus is edited by hand, and one bad line should cost that line.
Check with `make check-corpus`.

---

## 5. Adding an ageing effect

Write the model in `degradation/`, register it in `DEGRADATIONS`, then use that
name in `rules/augmentation.yaml`:

```yaml
- id: new_scenario
  weight: 2
  requires: [thermal]
  params:
    chain:
      - [paper_texture, {alpha: 0.4, grain: 0.6}]
      - [new_effect_name, {some_param: 1.0}]
```

The order in `chain` **does not commute**: ink decaying and then blurring reads
as "old text, badly scanned"; blurring and then decaying reads as a smear.
`paper_texture` always comes first — everything after it is damage to a sheet
that already exists. `paper_overlay`, if used, comes last: it is the
photograph of a real sheet laid over the finished page.

List what is available: `make list-degradations`.

---

## 6. The label

`receipt.ground_truth()` returns a CORD-style nested label, built from **the
same objects the renderer draws from**, so the label cannot describe something
the image does not contain.

```json
{
  "doc_type": "receipt_market",
  "title": "HOÁ ĐƠN BÁN HÀNG",
  "store": {"name": "VinCommerce", "branch": "VM Royal City", "address": "..."},
  "menu": [
    {"nm": "Nho đỏ không hạt Mỹ", "cnt": "1", "price": "149.625",
     "unitprice": "149.625", "barcode": "2607609009502",
     "weight": "0,950 KG", "unitprice_per_unit": "157.500",
     "discountprice": "-64.125"}
  ],
  "total": {"TỔNG TIỀN PHẢI T.TOÁN": "353.300", "TIỀN TRẢ LẠI": "0"},
  "footer": ["CẢM ƠN QUÝ KHÁCH VÀ HẸN GẶP LẠI"]
}
```

Weighed goods (`weight`) print a quantity of **1** and a unit price that is
**the amount for that weighing**, with the per-kilo price on the item-name line
— which is what a real till prints. The label records what was printed, and
carries the true weight in its own field.

The glyph renderer also emits `boxes`: a polygon per cell, still correct after
the sheet has been curled.
