# samples — curated examples

Viewable straight away, with no environment to build.

| directory | contents | regenerate |
| --- | --- | --- |
| [`degradation/`](degradation) | every ageing model applied on its own to **the same page**, plus a contact sheet | `make showcase` |
| [`invoice-templates/`](invoice-templates) | five reference sheets, hand-built from photographs, printed with WeasyPrint | `make templates` |
| [`ornaments/`](ornaments) | every seal and flourish in `textures/ornament/`, on one white page | `make ornaments` |
| [`handwriting/`](handwriting) | one **hand-filled** form at the most ink the model can put on a page — 5 of 12 field values in real ink, and the seven that stay printed are all digits | see its README |

The full 60-image dataset — three renderers, five layouts, with labels and OCR
scores — is in [`data/dataset60/`](../data/dataset60), not here.

## Reading the degradation showcase

`showcase-before.jpg` is the original page; each `showcase-<name>.jpg` is that
page after **one** model. `showcase-contact.jpg` tiles them all for a quick
comparison, and `showcase.json` records the parameters used.

Applying one model at a time is the whole point of this set: pasting a paper
texture, blending a stain in the gradient domain, and stamping leftover ink
against a character's flank look nothing alike — run the whole chain and you
cannot tell which step caused what.

The parameters here are chosen to be **clearly visible**, not to be realistic.
The ones actually used are in
[`rulebase/rules/augmentation.yaml`](../rulebase/rules/augmentation.yaml).
