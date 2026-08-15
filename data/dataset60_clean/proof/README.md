# OCR proof

Engine: `tesseract 5.3.4`, language `vie`, page segmentation mode 4.

Scores are order-free: Tesseract reads a two-column receipt in whatever
order its layout analysis picks, so comparing its output to the label as
one string would measure reading order rather than recognition. See
`tools/ocr_proof.py` for the definitions.

| framework | images | token recall | recall (folded) | field hit | field hit (folded) | money read exactly |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| synthdog | 20 | 0.829 | 0.856 | 0.753 | 0.781 | 105/144 (73%) |
| html | 20 | 0.853 | 0.865 | 0.792 | 0.802 | 114/141 (81%) |
| genalog | 20 | 0.869 | 0.877 | 0.805 | 0.805 | 109/149 (73%) |

## By layout

| value | images | token recall |
| --- | ---: | ---: |
| eatery_indexed | 12 | 0.913 |
| market_barcode | 12 | 0.907 |
| market_vat | 12 | 0.887 |
| market_compact | 12 | 0.783 |
| eatery_ascii | 12 | 0.761 |

## By level of ageing

| value | images | token recall |
| --- | ---: | ---: |
| pristine | 60 | 0.850 |

## By kind of printer

| value | images | token recall |
| --- | ---: | ---: |
| laser_sharp | 14 | 0.942 |
| thermal_narrow | 13 | 0.839 |
| thermal_dark | 10 | 0.817 |
| thermal_faint | 22 | 0.817 |
| dot_matrix | 1 | 0.786 |

## The illustrations

`proof_<framework>_NN.jpg` is the original image with a box round every
word Tesseract read -- green where its confidence is >= 70%, orange below.

## How to read these tables

**The spread between the three renderers is real, not a bug.** The glyph
renderer produces a *photograph* of a receipt lying on a table -- with
perspective, a lamp and a dark background; the two HTML renderers produce
a *flat scan* and a *print*. A photograph is markedly harder, and that is
precisely why all three are kept: a model that has only seen flat scans
has never met the hard case.

**The order of the "ageing" table is the evidence that the rule-base
really does control difficulty**: `pristine` and `real_paper` at the top,
`crumpled` at the bottom, monotone across the range. Editing `weight` in
`rulebase/rules/augmentation.yaml` shifts the whole dataset easier or
harder.

**However much higher the "folded" column is than the plain one is how
much of the error is tone marks alone.** The gap here is small, which means
the errors are mostly mis-recognised characters rather than lost diacritics.

These are **Tesseract's** scores -- a general-purpose engine that has not
been fine-tuned on Vietnamese thermal receipts. It is a floor, not a
ceiling: a low score on a heavily aged image is evidence the image is hard,
not evidence the label is wrong. To check whether a label matches its
pixels, look at `worst_fields` in `ocr_report.json` -- a field that is
wrong systematically across EVERY image is a broken label.

