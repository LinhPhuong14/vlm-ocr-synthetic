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
src/rulebase/
├── rules/          7 ATTRIBUTES, one file each         ← tune the distribution here
├── layouts/        14 LAYOUTS measured off real paper  ← add a layout here
├── corpus/vi/      Vietnamese corpus, WITH diacritics  ← add products here
├── corpus/en/      one document kind prints English
├── spec.py         weighted sampling with constraints
├── content.py      fills the fields and builds the label
├── layout.py       content + layout -> a grid of cells
└── text.py         diacritic folding, money formatting, wrapping
```

The fourteen layouts are not fourteen variations on a receipt. A thermal till
receipt, a printed VAT form, a metered utility bill, a hotel folio and a
self-designed order confirmation share a character grid and very little else,
so `rules/layout.yaml` sorts them into **parent nodes** — see §1b.

### Naming: English identifiers, Vietnamese printed text

The boundary runs in exactly one place: **what the code compares is English,
what reaches the image is Vietnamese.**

| English — an identifier | Vietnamese — content |
| --- | --- |
| `id`, `tags`, `requires`, `excludes` | `titles`, `total_labels` in `rules/document.yaml` |
| `profile: eatery \| market` | a column's `title:` in `layouts/*.yaml` |
| `paper: thermal_white` (a filename in `assets/textures/paper/`) | the discount row's `label:`, `notes:` |
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

## 1. The seven attributes

Drawn in this order. Each attribute sees the `tags` the earlier ones set, so a
later one can rule itself out when it does not fit.

| # | attribute | decides | file |
| --- | --- | --- | --- |
| 1 | `document` | what kind of document: eatery, supermarket, VAT invoice… | [rules/document.yaml](rules/document.yaml) |
| 2 | `layout` | which columns, how many lines per item | [rules/layout.yaml](rules/layout.yaml) |
| 3 | `content` | diacritics or not, UPPER CASE, money format, VAT | [rules/content.yaml](rules/content.yaml) |
| 4 | `visual` | font, size, ink weight, **white margin**, sheet, curl | [rules/visual.yaml](rules/visual.yaml) |
| 5 | `color` | ink, paper tint, accent colour for the shop name | [rules/color.yaml](rules/color.yaml) |
| 6 | `ornament` | seals and flourishes: the ink that is not text | [rules/ornament.yaml](rules/ornament.yaml) |
| 7 | `augmentation` | ageing: the degradation chain that runs after rendering | [rules/augmentation.yaml](rules/augmentation.yaml) |

**The list is not in the Python.** Attributes are discovered from `rules/*.yaml`
and ordered by [rules/_order.yaml](rules/_order.yaml), so a seventh criterion is
a new YAML file and a line in that manifest -- nothing else.

The manifest is not a formality. Discovery alone would be a downgrade: a
hard-coded tuple cannot forget a file, a directory listing can. Three mistakes
raise rather than pass silently -- a rules file the manifest never mentions
(which would simply never be drawn), a manifest entry with no file behind it,
and the same attribute listed twice.

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

## 1b. Parent nodes

A file may list its values flat under `options:`, or sort them into `groups:` —
each node an `id`, a `label` a reader can understand, and its own `options:`.

```yaml
groups:
  - id: retail_receipt
    label: "Hoá đơn tiêu dùng — giấy tính tiền in tại quầy"
    excludes: [doc_invoice]        # inherited by every value below
    tags: [till_receipt]           # likewise
    options:
      - id: market_barcode
        weight: 3
        requires: [has_barcode]
```

The node is **not decoration**. `tags`, `requires` and `excludes` written on it
are merged into every value beneath it, so a constraint that holds for the whole
family is written once — and the next layout added to that family cannot forget
it. `Option.group` records which node a value came from, and it is stored next
to the image in `metadata.jsonl`, which is what lets a finished dataset be
filtered by document family.

A file uses `options:` **or** `groups:`, never both: two places to add a value
is two places to forget one.

`rules/layout.yaml` is the file that needed this. Its five nodes:

| node | what the family is |
| --- | --- |
| `retail_receipt` | giấy tính tiền in tại quầy — thermal roll, names nobody, signed by nobody |
| `statutory_invoice` | tờ mẫu in sẵn — Mẫu số / Ký hiệu / Số, a ruled table, signatures |
| `utility_invoice` | điện, nước — charges a meter reading rather than a basket |
| `lodging_invoice` | khách sạn — one line per night, dated rows, paid/outstanding |
| `modern_invoice` | tờ tự thiết kế — no frame, totals against the right margin |

```bash
make distribution        # the mix per node, then per value
```

Reading the mix per node is what a weight change should be judged by: a weight
is relative to the candidates left after filtering, so a family of five rare
layouts and a family of one common one can read identically value by value and
be nothing alike as a mix.

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
2. Declare it in `rules/layout.yaml`, **under the node whose family it joins**,
   with whatever `requires` the node does not already give it.
3. Preview it as text, with no image rendering:

```bash
make preview-grid LAYOUT=<name>
```

4. Check that the label still describes only what the page shows. A layout that
   drops a column keeps the field in `ground_truth()` — that is the one defect
   this rule-base measures rather than assumes:

```bash
python -m pytest tests/test_content.py -q     # the budget on unprinted fields
make preflight                                # glyph coverage over the new strings
```

### The sections of a page

A page is a **sequence of sections**, and `sections:` in the layout file says
which of them run and in what order. A till receipt is one such sequence and
stays the default, so the five thermal layouts declare none:

```yaml
sections: [header, meta, columns, items, totals, footer]     # the default
```

| section | what it draws |
| --- | --- |
| `header` | shop name, address, title — all centred, the thermal opening |
| `meta` | the till's key/value block (`Số phiếu`, `Bàn`, `Thời gian`) |
| `columns` / `items` | column titles and the item rows, unruled |
| `letterhead` | the issuer on the left, `Mẫu số / Ký hiệu / Số` on the right |
| `doctitle` | the centred title, its subtitle, and the period it covers |
| `strip` | the run of keys across the top of a designed invoice |
| `parties` | who is billed — two columns, or stacked full-width dotted fields |
| `table` | the item table, ruled or not, with blank rows if the form has them |
| `totals` | the totals, in the frame or against the right margin |
| `vat_summary` | "Tổng hợp": the money regrouped by tax rate |
| `words` | the amount spelled out, so the figure cannot be altered |
| `notes` | a block of lines; `style: two_column` splits it on a blank line |
| `signatures` | the signature titles, the names under them, the e-signature box |
| `footer` | the closing lines |

Every invoice-only section checks `Receipt.invoice` before drawing, so listing
one on a till layout costs nothing but draws nothing.

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

columns:               # width 0 = "take what is left" — exactly one column
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
  indent: 0.42             # a designed invoice hugs the right margin instead
```

Sources usable in `from:`: `stt`, `name`, `qty`, `unit_price`, `amount`,
`barcode`, `barcode_name`, `vat`, `vat_rate`, `vat_amount`, `amount_with_vat`,
`unit`, `note`, `meter_now`, `meter_prev`, `quota`, `tier`, `tier_price`,
`date`, `ref`.

A row whose every field is empty is skipped — which is what lets one template
serve both weighed goods (with a weight line) and packaged ones (without), and
one folio template serve a night with a note under it and one without.

### A form, rather than a receipt

The keys an A4 document adds:

```yaml
letterhead:
  frame: true            # the boxed seller block of an e-invoice rendition
  serial_width: 30       # how much of the top-right the Mẫu số block takes
  serial: false          # drop that row: the number is in the `strip` instead
  labels: {address: "Địa chỉ:", tax_code: "Mã số thuế:"}

parties:
  style: stacked         # stacked | two_column
  leader: "."            # the dotted run of a blank form
  split: 0.55            # where the two columns divide

table:
  frame: true            # a ruled table rather than a block of items
  column_numbers: true   # the "(1) (2) ... (6 = 4 x 5)" row a form carries
  row_rules: true        # a rule under every item, not just under the block
  blank_rows: 4          # a form has the rows it was printed with
  header_rules: true     # unframed: rule above and below the column titles
  shade: 0.10            # a tint under the column titles, as a fraction of ink
  border: 1.8            # the outer boundary, in hairlines (1.0 = no emphasis)

vat_summary:             # its own columns, resolved on their own
  frame: true
  shade: 0.10
  columns:
    - {key: label, title: "Tổng hợp", width: 0, align: left}
    - {key: rate,  title: "Thuế suất (VAT rate)", width: 14, align: center}
```

### The paper, or no paper at all

```yaml
sheet: a4              # a4 | a4_landscape | a5 | a5_landscape | letter
```

Absent means a **continuous roll**, which is what the five thermal layouts are
on: a till roll has no bottom edge until the cutter makes one, so the page
really is as tall as the sale and nothing else.

A layout that names a sheet is on **cut paper**, whose height was decided
before anything was printed. A three-item invoice therefore fills a whole A4
page with blank paper under the signatures — that whitespace is part of what
the document looks like, not something to crop away. The nine invoice layouts
all declare `sheet: a4`.

The rule-base states the width-over-height ratio and no more; turning it into
pixels needs a character advance and a line height, and those belong to each
renderer — measured from the font by the glyph backend, `ch` in the browser, an
estimate in WeasyPrint. Same division of labour as `Mark`.

The sheet is a **floor, never a crop**: a page whose content outgrows its paper
keeps its full height, so the overflow stays visible instead of being trimmed
into looking correct. `make preflight` samples twelve seeds of every layout
that declares a sheet and reports any that do not fit.

### Drawn rules, or typed ones

```yaml
rules: marks             # default: ascii
```

A till roll really does print its rules as rows of `-` and `|`, because a
thermal head prints characters. A page printer does not: it *draws* the line,
and a drawn line costs no line of text, which is why a real form fits more on a
page than its ASCII rendering of the same fields does.

`rules: marks` says which of the two this layout is. It turns every rule on the
page into a `Mark` — a rectangle on the **same (row, column) grid the cells
use**, so no renderer needs a second coordinate system for it. All three draw
it: the glyph backend as a `RectLayer`, the two HTML backends as a `div`. Three
kinds:

| kind | what it is | who emits it |
| --- | --- | --- |
| `rule` | a line, degenerate on one axis; `weight` in hairlines | every `_rule_row` and every vertical of a framed table |
| `fill` | a tint, `tone` a fraction of the page's ink | `shade:` under column titles or under the amount owed |
| `frame` | a hollow border, `weight` in hairlines | `border:` around a framed table |

Marks are listed back to front — shading, then the lines on it, then the text
over both.

The nine layouts a page printer produces set `rules: marks`; the five thermal
ones deliberately do not, and `shade:` is ignored without it, because a till
roll can print a line of `-` and cannot print a grey box.

An ASCII-ruled table is drawn with `+ - |` and never with U+2500 box-drawing:
two of the fonts in `assets/fonts/` have no box-drawing block at all, so a frame drawn
with `─` would render as a row of empty rectangles in a fifth of the dataset —
with the label still claiming a table.

---

## 4. Adding products and shops

`corpus/vi/` is plain text, **TAB**-separated. Always write Vietnamese **with
diacritics** — the `content` attribute is what decides whether they are folded
away at render time, and folding is one-way: "Hẹn gặp lại" → "Hen gap lai"
works, the reverse does not.

| file | columns |
| --- | --- |
| `items_<profile>.txt` | name ⇥ min price ⇥ max price |
| `shops_<profile>.txt` | name — or brand ⇥ branch, where the profile has one |
| `footers_<profile>.txt`, `streets.txt` | one value per line |
| `wards.txt` | ward ⇥ district ⇥ province/city |
| `payments.txt` | label ⇥ group (`tienmat`/`the`/`vi`/`qr`) |
| `people.txt` | one name per line — a till prints none, an invoice names its buyer |

The `profile` in `rules/document.yaml` **is** the filename suffix:
`profile: market` reads `items_market.txt`. Adding a profile means adding three
corpus files with a matching suffix, not editing `corpus.py`. The eight so far:

| profile | what it stocks |
| --- | --- |
| `eatery`, `market` | dishes and shelf goods, priced as a customer sees them |
| `invoice` | goods and services sold between businesses, priced accordingly |
| `utility_water`, `utility_power` | tariff bands — **order matters**, they are consecutive |
| `hotel` | room charges then extras — **order matters**, `room_items` counts the leading room lines |
| `export` | goods named bilingually, because the export form prints both |
| `bakery` | cakes and drinks, ordered ahead rather than eaten at a table |

`corpus/en/` holds the one document kind that prints English. It is a different
document, not a translated one — see the naming rule at the top of this file.

A row with the wrong number of columns is skipped rather than failing the whole
run — a corpus is edited by hand, and one bad line should cost that line.
Check with `make check-corpus`.

---

## 4b. Seals and flourishes

The `ornament` attribute is the ink on a page that is **not text**: the round
company seal seated over a signature, the wave band under a coloured masthead,
the guilloche rosette printed faintly behind a table, a corner bracket, a grid
of pale rectangles in the footer.

```bash
make ornaments           # regenerate assets/textures/ornament/*.png
```

`tools/make_ornaments.py` draws them; `rules/ornament.yaml` says which page gets
which, where it sits, how big and how opaque. A rule names a file by stem, and
`make preflight` checks both directions — a rule naming a file that does not
exist, and a file no rule names.

**Why they are drawn here rather than by synthtiger.** synthtiger builds text
images out of flat layers: a `TextLayer` is one horizontal run with effects
stacked on it — perspective, elastic distortion, shadow, colour. There is no
text-on-a-path primitive, and a round seal is exactly that — every glyph rotated
to the tangent of a circle. So the drawing happens once, into PNGs with an alpha
channel, and the ageing and compositing that synthtiger and `src/degradation/` are
good at treat the result like any other overlay.

Position is named, not measured: `anchor: signature_seller` rather than a pair
of coordinates. A seal belongs over the seller's signature on a 148mm folio and
on a 210mm form alike, and the two have that place in different millimetres.

Two marks carry `from_receipt: true`: the shelf barcode and the verification
QR. Their content comes from the values the rule-base already drew for that
page, so the file in `assets/textures/ornament/` is a sample to look at and not the
thing to composite — a fixed barcode pasted onto a receipt whose label says a
different number is the exact defect `src/pipeline/invariants.py` exists to catch.

**There are no hand marks.** Signatures, handwritten field values, pen
underlines and highlighter swipes were drawn and then removed: a typeface
jittered per glyph is not handwriting, and a procedural squiggle is not a
signature. Doing it properly wants stroke data or a hand-drawn face licensed
for redistribution.

Twenty-three ornaments were surveyed and not built — those four among them.
Each is written down with the reason it was left, in
[docs/hoa-tiet-de-xuat.md](../../docs/hoa-tiet-de-xuat.md).

> **Not yet drawn.** The attribute is sampled and recorded in `metadata.jsonl`,
> and every asset it names exists. No renderer composites it onto the page yet —
> that is the next piece of work, and it is why `make baseline-verify` needs a
> recapture after this change.

---

## 5. Adding an ageing effect

Write the model in `src/degradation/`, register it in `DEGRADATIONS`, then use that
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

An invoice adds a second block, because an invoice carries what a till receipt
does not — both parties, a serial the tax office can look up, the amount in
words, who signed:

```json
{
  "doc_type": "receipt_invoice",
  "invoice": {
    "serial": "1K25TAE", "number": "00006830", "form_no": "01GTKT0/001",
    "subtitle": "Bản thể hiện của hoá đơn điện tử",
    "period": "Ngày (date) 09/01/2025",
    "strip": {"Số hoá đơn:": "INV001421", "Mã đặt phòng:": "001421"},
    "left":  {"Tên người mua hàng:": "Lê Quang Đạo", "Mã số thuế:": "3709983607"},
    "right": {"Số bảo mật:": "6244075"},
    "summary": [
      {"label": "Hàng hoá chịu thuế suất:", "rate": "10%",
       "net": "39.124.000", "vat": "3.912.400", "gross": "43.036.400"},
      {"label": "Tổng cộng tiền thanh toán:",
       "net": "48.022.000", "vat": "4.357.300", "gross": "52.379.300"}
    ],
    "words": "Năm mươi hai triệu ... đồng",
    "signed_by": "Được ký bởi: CÔNG TY ...", "signed_at": "Ngày ký: 09/01/2025"
  }
}
```

Every entry here is something a layout prints. That is not a style rule:
`tests/test_content.py` measures how much of the label the page never shows, and
`src/pipeline/invariants.py` treats an unprinted field as an error unless the layout
is on a list of known suppressions. A field recorded but not drawn teaches a
model to hallucinate it.

A stay invoice adds `date` and `ref` to each line — the night it covers and the
room it was slept in — because its table rules a column for each.

Weighed goods (`weight`) print a quantity of **1** and a unit price that is
**the amount for that weighing**, with the per-kilo price on the item-name line
— which is what a real till prints. The label records what was printed, and
carries the true weight in its own field.

The glyph renderer also emits `boxes`: a polygon per cell, still correct after
the sheet has been curled.
