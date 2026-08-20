# samples — curated examples

Viewable straight away, with no environment to build.

| directory | contents | regenerate |
| --- | --- | --- |
| [`src/degradation/`](degradation) | every ageing model applied on its own to **the same page**, plus a contact sheet | `make showcase` |
| [`invoice-templates/`](invoice-templates) | five reference sheets, hand-built from photographs, printed with WeasyPrint | `make templates` |
| [`ornaments/`](ornaments) | every seal and flourish in `assets/textures/ornament/`, on one white page | `make ornaments` |

The full 60-image dataset — three renderers, fourteen layouts, with labels and
OCR scores — is not committed: `make dataset` builds it into
[`data/`](../data), which is where its README explains the label schema.

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
[`src/rulebase/rules/augmentation.yaml`](../src/rulebase/rules/augmentation.yaml).
