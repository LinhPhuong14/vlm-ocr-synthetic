# OCR proof

Engine: `tesseract 5.3.4`, language `vie`, page segmentation mode 4.

Scores are order-free: Tesseract reads a two-column receipt in whatever
order its layout analysis picks, so comparing its output to the label as
one string would measure reading order rather than recognition. See
`tools/ocr_proof.py` for the definitions.

| framework | images | token recall | recall (folded) | field hit | field hit (folded) | money read exactly |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| synthdog | 20 | 0.454 | 0.495 | 0.339 | 0.382 | 17/101 (17%) |
| html | 20 | 0.611 | 0.645 | 0.459 | 0.513 | 26/101 (26%) |
| genalog | 20 | 0.578 | 0.612 | 0.441 | 0.476 | 28/101 (28%) |

## By layout

| value | images | token recall |
| --- | ---: | ---: |
| invoice_brand | 6 | 0.924 |
| invoice_hotel_compact | 6 | 0.698 |
| market_vat | 3 | 0.667 |
| eatery_indexed | 6 | 0.658 |
| invoice_water | 3 | 0.633 |
| eatery_ascii | 6 | 0.592 |
| invoice_tax_en | 3 | 0.583 |
| invoice_power | 3 | 0.461 |
| invoice_hotel_stay | 6 | 0.424 |
| invoice_vat_form | 3 | 0.396 |
| market_compact | 3 | 0.395 |
| invoice_vat_summary | 3 | 0.394 |
| invoice_export | 6 | 0.296 |
| market_barcode | 3 | 0.234 |

## By level of ageing

| value | images | token recall |
| --- | ---: | ---: |
| pristine | 3 | 0.927 |
| real_paper | 12 | 0.850 |
| light | 9 | 0.644 |
| stains | 3 | 0.633 |
| photocopy | 3 | 0.395 |
| punched | 9 | 0.387 |
| medium | 18 | 0.375 |
| torn_edges | 3 | 0.248 |

## By kind of printer

| value | images | token recall |
| --- | ---: | ---: |
| laser_sharp | 3 | 0.898 |
| thermal_narrow | 6 | 0.638 |
| laser_invoice | 33 | 0.565 |
| impact_invoice | 6 | 0.465 |
| thermal_dark | 12 | 0.405 |

## The illustrations

`proof_<framework>_NN.jpg` is the original image with a box round every
word Tesseract read -- green where its confidence is >= 70%, orange below.

## How to read these tables

**Every renderer drew the same receipts** (`pairing: paired`), so a
difference between two rows of the first table is a difference in
drawing and nothing else. The 60 images are 20 receipts
drawn 3 ways -- count the sample as 20, not 60.

**The spread between the three renderers is real, not a bug.** The glyph
renderer produces a *photograph* of a receipt lying on a table -- with
perspective, a lamp and a dark background; the two HTML renderers produce
a *flat scan* and a *print*. A photograph is markedly harder, and that is
precisely why all three are kept: a model that has only seen flat scans
has never met the hard case.

**The ageing table is where difficulty is supposed to be controlled.**
Easiest here is `pristine` at 0.927 over 3 images, hardest is `torn_edges` at 0.248 over 3 images --
a spread of 0.679 between them, so the rule-base is controlling difficulty. Editing `weight` in `rulebase/rules/augmentation.yaml` shifts
the whole dataset. Values missing from the table were never drawn in this
sample rather than scoring zero.

**However much higher the "folded" column is than the plain one is how
much of the error is tone marks alone.** The gap here is small, which means
the errors are mostly mis-recognised characters rather than lost diacritics.

These are **Tesseract's** scores -- a general-purpose engine that has not
been fine-tuned on Vietnamese thermal receipts. It is a floor, not a
ceiling: a low score on a heavily aged image is evidence the image is hard,
not evidence the label is wrong. To check whether a label matches its
pixels, look at `worst_fields` in `ocr_report.json` -- a field that is
wrong systematically across EVERY image is a broken label.

