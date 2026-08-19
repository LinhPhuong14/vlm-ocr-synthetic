# taxonomy — the document hierarchy

Twelve families, 101 declared types, 98 distinct documents. This directory is
the only place any of them is written down: the sampler, the run planner, every
label and every report read the tree from here, and no Python anywhere in the
repository hard-codes a document type.

```bash
make taxonomy         # the tree, with what each type still needs
make taxonomy-check   # does the tree agree with the rules and the builders?
make coverage         # ...and which types a generated dataset actually holds
```

```
taxonomy/
├── document.yaml      the vocabulary: statuses, engines, the root
├── families/          the tree, one file per family
│   ├── 01-business.yaml … 12-visual.yaml
└── __init__.py        loader, validation, lookup
```

---

## 1. The tree, and what it costs to fill in

| # | family | types | ready | engine |
| --- | --- | ---: | ---: | --- |
| 1 | Structured Business Document | 16 | 2 | grid |
| 2 | Form & Administrative Document | 8 | 0 | grid |
| 3 | Identity & Official Document | 7 | 0 | card |
| 4 | Legal Document | 7 | 0 | flow |
| 5 | Medical / Healthcare Document | 9 | 0 | grid |
| 6 | Academic / Research Document | 8 | 0 | flow |
| 7 | Technical Document | 8 | 0 | flow |
| 8 | Report / Information Document | 6 | 0 | flow |
| 9 | Communication Document | 6 | 0 | flow |
| 10 | List / Catalog / Directory | 8 | 0 | grid |
| 11 | Log / Operational Document | 6 | 0 | grid |
| 12 | Visual / Mixed Document | 9 | 0 | canvas |

Two of ninety-eight can be generated today: `business.receipt.retail` and
`business.receipt.restaurant`, which is everything this repository could do
before the hierarchy existed. The interesting number is not the two, it is how
the remaining ninety-six break down:

| engine | built | types | what it needs |
| --- | --- | ---: | --- |
| `grid` | **yes** | 49 | corpus, a layout, a builder — no new machinery |
| `flow` | no | 33 | paginated prose: headings, reflow, page breaks, a label schema for running text |
| `card` | no | 5 | fixed geometry in millimetres, photographs, security patterns |
| `canvas` | no | 11 | free composition, and a label that can say which text belongs to which figure |

That table is the whole point of the `engine` field. "Add a hundred document
types" is not one unbounded task; it is *three engines and then a lot of
corpus*, and half the tree is reachable without writing an engine at all.

---

## 2. Five decisions, and why

### An id is a path, and paths are not all the same length

`business.receipt.retail` has three segments; `medical.prescription` has two.
Family 1 puts `Invoice` and `Receipt` between the family and the leaf because
they really are kinds of document rather than documents; the other eleven
families do not need that level and do not have it.

Nothing may assume a fixed depth. A tree forced to one shape would have to
invent a middle level for eleven families to satisfy a loop counter, and the
invented names would end up in labels.

### A name that appears twice is either an alias or a refusal to load

The hierarchy files `Certificate` under both Identity and Academic,
`Financial Report` under both Financial and Report, `Official Letter` under
both Identity and Communication. Those are one document filed in two places, so
one of each pair declares `same_as` and the other is the canonical node:

```yaml
- id: certificate
  name: Certificate
  same_as: identity.certificate       # generated there, only filed here
```

An alias carries nothing else — no status, no engine, no Vietnamese name. There
is one answer to "can we generate a Certificate", and it lives on the canonical
node. `leaves()` returns 98, not 101, so a quota cannot generate the same
document twice while reporting two types covered.

Any *other* repeated name fails to load. Two leaves with one name are two
labels a classifier cannot tell apart.

### `status` is a claim, and the claim is checked

`planned` means named here and nowhere else. `draft` renders but has not been
measured against a real page. `ready` means a run can produce it **today**, and
that is checked in both directions by `make taxonomy-check`:

* a `ready` type that no rules value realises, or that no builder is registered
  for, fails the check — the tree would be lying about the repository;
* a type that *is* generatable while still marked `planned` fails too — the
  status is stale and every coverage report is understating what exists.

Three separate places have to agree before an image can exist, which is why the
report prints all three side by side:

```
declared   status: in taxonomy/families/   the claim
rules      a value in rules/ naming it     something to draw
builder    a function in rulebase/documents.py   something to fill in
```

### English identifies, Vietnamese displays

Every node carries `name` (English) and `name_vi`. The English name is the
identifier: it appears in ids, in labels, in `doc_path`, and in every error
message. The Vietnamese name is for people reading a report about Vietnamese
documents. This is the same boundary [`rulebase/`](../rulebase/README.md) draws
— English for what the code compares, Vietnamese for what reaches the page.

### The label carries the path, not just the id

```json
{
  "doc_type": "business.receipt.retail",
  "doc_family": "business",
  "doc_path": ["Structured Business Document", "Receipt", "Retail Receipt"]
}
```

Denormalised on purpose. A label is written once and read for years, usually far
from this repository; a reader who has to fetch `taxonomy/` to find out what
`business.receipt.retail` means has a label that only half describes the image.
`doc_family` is there so a coarse "business or medical" model does not have to
recover the family by splitting a string.

---

## 3. Adding a document type

Take `medical.prescription` — declared, `grid`, and the best next candidate:
a header, a four-column table, a signature line, all of which the existing
engine already draws.

**1. Promote it in the tree.** `taxonomy/families/05-medical.yaml`:

```yaml
  - id: prescription
    name: Prescription
    name_vi: Đơn thuốc
    status: draft            # ready once it has been checked against a real form
```

**2. Give it rules.** A new file, one per family, so nobody edits somebody
else's — `rulebase/rules/document/medical.yaml`:

```yaml
options:
  - id: hospital_prescription
    doc_type: medical.prescription
    weight: 3
    tags: [doc_medical, has_signature]
    params:
      profile: prescription
      titles: ["ĐƠN THUỐC"]
```

**3. Give it a layout.** `rulebase/layouts/prescription_a5.yaml`, declared in
`rules/layout.yaml` with `requires: [doc_medical]` so no receipt can draw it and
it can draw no receipt. Preview it with no image rendering:
`make preview-grid LAYOUT=prescription_a5`.

**4. Give it a corpus.** `rulebase/corpus/vi/items_prescription.txt` and
friends — the `profile` is the filename suffix, so no Python changes.

**5. Register a builder.** In `rulebase/documents.py`:

```python
@register("medical.prescription")
def prescription(recipe, rng):
    ...
```

Then `make taxonomy-check` should be silent, and

```bash
python generators/html/render.py --doc prescription -c 5 -o /tmp/rx
```

should produce five of them.

> **The honest catch on step 5.** `rulebase/layout.py` still builds its grid
> from a *receipt's* parts — header, meta pairs, item rows, totals, footer.
> Those parts generalise (a prescription is a header, meta pairs, drug rows and
> a signature) but the generalisation has not been done. The second grid-engine
> document is the one that will do it, and that is a known piece of work rather
> than a surprise waiting in step 5.

### Adding a whole family

Same five steps, plus `taxonomy/families/NN-<id>.yaml`. The number is the file
prefix and the `number:` field, and a test checks they agree.

---

## 4. The file format

```yaml
id: medical                  # required; lower-case, digits, underscores
number: 5                    # families only; matches the filename prefix
name: Medical / Healthcare Document
name_vi: Tài liệu y tế
engine: grid                 # grid | flow | card | canvas; inherited if absent
status: planned              # ready | draft | planned; inherited if absent
notes: >                     # free text, printed by nothing, read by everyone
  ...
children:
  - id: prescription
    name: Prescription
    name_vi: Đơn thuốc
  - id: certificate          # an alias: id, name, same_as, notes -- nothing else
    name: Certificate
    same_as: identity.certificate
```

`engine` and `status` are inherited from the parent, so "this whole family is
planned" is one line and a leaf that differs says so — family 3 is `card`
overall and holds two `flow` documents.

Unknown keys fail to load. `enigne: grid` would otherwise leave a node silently
on its parent's engine and look exactly like a node that meant to inherit it.

---

## 5. Using the tree from Python

```python
import taxonomy

tree = taxonomy.tree()                       # memoised
tree.resolve("prescription").id              # 'medical.prescription'
tree.resolve("receipt.retail").id            # 'business.receipt.retail'
tree.resolve("certificate")                  # TaxonomyError: matches 2 types

tree.node("business.receipt.retail").names   # ('Structured Business…', 'Receipt', 'Retail Receipt')
tree.leaves(under="business.receipt")        # the four receipt types
tree.generatable()                           # the ones a run can produce
tree.select(["medical", "business.receipt"], exclude=["business.receipt.atm"])
tree.by_engine()                             # the roadmap table above
```

`resolve` takes any unambiguous suffix, because `--doc business.receipt.retail`
on every command line is a tax on the common case. It never guesses: the tree
deliberately contains three names that appear twice, and quietly picking one of
them is how a run produces a school certificate when it was asked for a
government one.

---

## 6. Balancing a run over the tree

[`pipeline.yaml`](../pipeline.yaml):

```yaml
taxonomy:
  include: [business.receipt, medical]   # subtrees, or single types
  exclude: [business.receipt.atm]
  balance: family                        # family | equal | weight
```

`family` — the default — gives every family the same budget and then splits it
evenly inside. `equal` gives every *type* the same number, which hands family 1
nearly three times family 11's images purely because it has more branches.
`weight` reproduces the mix the rules already describe. See
[`pipeline/quota.py`](../pipeline/quota.py).

A type in the selected subtree that cannot be generated yet is dropped and
named. A type asked for **by name** that cannot be generated stops the run:
asking for prescriptions and quietly getting receipts is the worst possible
answer.
