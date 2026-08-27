# samples — curated examples

Viewable straight away, with no environment to build.

| directory | contents | regenerate |
| --- | --- | --- |
| [`degradation/`](degradation) | every ageing model applied on its own to **the same page**, plus a contact sheet | `make showcase` |
| [`invoice-templates/`](invoice-templates) | five reference sheets, hand-built from photographs, printed with WeasyPrint | `make templates` |
| [`form-templates/`](form-templates) | two administrative forms — an authorisation letter and a three-page medical statement — hand-built from scans | `make templates` |
| [`insurance-templates/`](insurance-templates) | ten insurance documents — liability certificates, a life-policy schedule, an application form, a health-insurance ID card, and more — reference only, no engine yet | `make templates` |
| [`periodical-templates/`](periodical-templates) | ten newspaper and magazine pages — three front pages, an inside page, an opinion page, classifieds, a magazine cover, contents, feature spread and modular grid — reference only, no content model yet | `make templates` |
| [`ornaments/`](ornaments) | every seal and flourish in `textures/ornament/`, on one white page | `make ornaments` |
| [`handwriting/`](handwriting) | two **hand-filled** forms, one per ink source: a typeface fills every field, the model fills 5 of 12 and the seven it leaves are all digits | see its README |
| [`signatures/`](signatures) | synthesised **signatures** from both ink sources — a grid each, plus three signed sheets — with the name printed under the caption, with the line left blank, and in the model's own thin joined-up ink | `make signatures` |

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
