# OCR proof

Engine: `tesseract 5.3.4`, language `vie`, page segmentation mode 4.

Scores are order-free: Tesseract reads a two-column receipt in whatever
order its layout analysis picks, so comparing its output to the label as
one string would measure reading order rather than recognition. See
`tools/ocr_proof.py` for the definitions.

| framework | images | token recall | recall (folded) | field hit | field hit (folded) | money read exactly |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| synthdog | 20 | 0.506 | 0.561 | 0.333 | 0.403 | 36/128 (28%) |
| html | 20 | 0.729 | 0.747 | 0.605 | 0.627 | 62/128 (48%) |
| genalog | 20 | 0.659 | 0.681 | 0.532 | 0.552 | 53/128 (41%) |

## By layout

| value | images | token recall |
| --- | ---: | ---: |
| eatery_indexed | 12 | 0.758 |
| market_barcode | 12 | 0.681 |
| market_vat | 12 | 0.622 |
| eatery_ascii | 12 | 0.576 |
| market_compact | 12 | 0.519 |

## By level of ageing

| value | images | token recall |
| --- | ---: | ---: |
| ghost_text | 3 | 0.804 |
| light | 3 | 0.766 |
| real_paper | 18 | 0.757 |
| pristine | 3 | 0.672 |
| torn_edges | 9 | 0.622 |
| medium | 6 | 0.580 |
| photocopy | 12 | 0.496 |
| stains | 6 | 0.412 |

## By kind of printer

| value | images | token recall |
| --- | ---: | ---: |
| laser_sharp | 9 | 0.820 |
| thermal_dark | 15 | 0.623 |
| thermal_faint | 21 | 0.620 |
| dot_matrix | 6 | 0.592 |
| thermal_narrow | 9 | 0.507 |

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
Easiest here is `ghost_text` at 0.804 over 3 images, hardest is `stains` at 0.412 over 6 images --
a spread of 0.392 between them, so the rule-base is controlling difficulty. Editing `weight` in `rulebase/rules/augmentation.yaml` shifts
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

