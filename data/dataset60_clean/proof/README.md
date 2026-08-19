# OCR proof

Engine: `tesseract 5.3.4`, language `vie`, page segmentation mode 4.

Scores are order-free: Tesseract reads a two-column receipt in whatever
order its layout analysis picks, so comparing its output to the label as
one string would measure reading order rather than recognition. See
`tools/ocr_proof.py` for the definitions.

| framework | images | token recall | recall (folded) | field hit | field hit (folded) | money read exactly |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| synthdog | 20 | 0.851 | 0.875 | 0.774 | 0.798 | 62/101 (61%) |
| html | 20 | 0.881 | 0.891 | 0.813 | 0.813 | 60/101 (59%) |
| genalog | 20 | 0.882 | 0.895 | 0.804 | 0.821 | 60/101 (59%) |

## By layout

| value | images | token recall |
| --- | ---: | ---: |
| eatery_indexed | 6 | 0.966 |
| invoice_hotel_compact | 6 | 0.957 |
| invoice_brand | 6 | 0.950 |
| invoice_hotel_stay | 6 | 0.945 |
| invoice_vat_summary | 3 | 0.885 |
| invoice_vat_form | 3 | 0.883 |
| market_vat | 3 | 0.875 |
| invoice_tax_en | 3 | 0.865 |
| invoice_power | 3 | 0.844 |
| invoice_water | 3 | 0.829 |
| invoice_export | 6 | 0.812 |
| market_barcode | 3 | 0.785 |
| eatery_ascii | 6 | 0.774 |
| market_compact | 3 | 0.649 |

## By level of ageing

| value | images | token recall |
| --- | ---: | ---: |
| pristine | 60 | 0.871 |

## By kind of printer

| value | images | token recall |
| --- | ---: | ---: |
| laser_sharp | 3 | 0.963 |
| laser_invoice | 33 | 0.899 |
| impact_invoice | 6 | 0.872 |
| thermal_narrow | 6 | 0.815 |
| thermal_dark | 12 | 0.799 |

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

**The ageing ladder cannot be read from this dataset.** No layout in
it was drawn at two different levels of ageing, so every rung of the
pooled table is a different set of layouts and the ordering between
rungs says nothing about ageing. Compare against the matching clean
set instead: `--against <its ocr_report.json>`.

**The pooled numbers above are a score of this layout set, not of the
generator.** Ageing costs different layouts between 0.03 and 0.55 of
their recall, so changing which layouts are in a dataset moves the
pooled score on its own. This one holds 14 layouts: `eatery_ascii`, `eatery_indexed`, `invoice_brand`, `invoice_export`, `invoice_hotel_compact`, `invoice_hotel_stay`, `invoice_power`, `invoice_tax_en`, `invoice_vat_form`, `invoice_vat_summary`, `invoice_water`, `market_barcode`, `market_compact`, `market_vat`.

Comparing this table with an older one is only meaningful when both
were taken over the same set; `tools/ocr_proof.py --against <report>`
checks that and refuses the pooled comparison when they differ, while
still giving the per-layout one, which holds the layout fixed and is
therefore the quantity that measures a change.

**However much higher the "folded" column is than the plain one is how
much of the error is tone marks alone.** The gap here is small, which means
the errors are mostly mis-recognised characters rather than lost diacritics.

These are **Tesseract's** scores -- a general-purpose engine that has not
been fine-tuned on Vietnamese thermal receipts. It is a floor, not a
ceiling: a low score on a heavily aged image is evidence the image is hard,
not evidence the label is wrong. To check whether a label matches its
pixels, look at `worst_fields` in `ocr_report.json` -- a field that is
wrong systematically across EVERY image is a broken label.

