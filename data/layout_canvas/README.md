# layout_canvas — every bố cục, every renderer, on six sheets

Two contact sheets per renderer. They exist because the questions they answer
are not visible in a directory of 84 JPEGs, and are obvious in one picture.

| sheet | rows | what it answers |
| --- | --- | --- |
| `canvas_data.jpg` | 2 × 14 | **what the ageing did.** Top row: the page with an empty degradation chain. Bottom row: the *same* page, same seed, same receipt, after its chain ran. |
| `canvas_bbox.jpg` | 1 × 14 | **whether the labels still describe the pixels.** The augmented page with its `boxes` drawn on, coloured by field family. |

One column per bố cục, fourteen of them, in the dataset's own file order. The
caption under each cell is the degradation chain the rules drew for that page —
`pristine` on the clean row, and `light`, `medium`, `photocopy`, `punched`,
`real_paper` or `stains` on the augmented one.

```
layout_canvas/
├── synthdog/{canvas_data,canvas_bbox}.jpg    a photograph of a receipt
├── html/{canvas_data,canvas_bbox}.jpg        a flat scan
└── genalog/{canvas_data,canvas_bbox}.jpg     a print
```

## Why the columns pair

Both runs are the same seed (2026) and the same fourteen-image plan, so the
only attribute that differs between the two rows is `augmentation` — which is
drawn *last* of the six, so pinning it to `pristine` cannot disturb the five
attributes drawn before it. That is checkable rather than asserted: the two
runs' `text_sequence` matches for all 14 layouts in all 3 renderers.

The two rows are therefore one receipt twice, and a column is a before and an
after. What is *not* identical is the geometry of the glyph renderer's row: the
clean run also turns off its curl, perspective and camera, so its clean cell is
the flat sheet and its augmented cell is a photograph of that sheet on a table.
That difference is the point of the renderer, not an error in the pairing.

## What to look for on the bbox sheet

The boxes come from the **label**, not from the image — no OCR is involved — so
a quad that has slid off its text is a label that lies, and this is the sheet
where that shows. The glyph renderer's quads are drawn as polygons because they
are genuinely rotated by the paper curl; the other two are axis-aligned. A
`punched` page with a hole through a menu row still carries a box for the row
it ate, which is correct and worth seeing.

## Rebuild

```bash
python3 tools/layout_canvas.py --clean <clean-run> --aug <aged-run> -o data/layout_canvas
```

The two runs are fourteen images each — one per bố cục — from the ordinary
driver:

```bash
python tools/generate_dataset.py -o /tmp/run/aug   -n 14 --seed 2026
python tools/generate_dataset.py -o /tmp/run/clean -n 14 --seed 2026 --clean
```

`-n 14` is not a round number chosen for size: `split_by_layout` spreads a
run evenly over the layouts, so fourteen images over fourteen layouts is
exactly one of each, and image *k* is layout *k* in both runs.

`tools/layout_canvas.py` needs only Pillow and the standard library, so looking
at a run never depends on which renderer environment got built.
