# degradation — DocCreator's models, in Python

[DocCreator](https://github.com/DocCreator/DocCreator) (Journet, Mansencal,
Kieu et al., LaBRI Bordeaux) is a C++/Qt application whose degradation models
were designed against real degraded manuscripts. The models are the valuable
part; the Qt application is not something a Python generation pipeline can
call. So they are ported here and applied to whatever a renderer produced.

DocCreator itself is not vendored: the modules carry citations to the file each
came from, which is what you need to check one. Read the original with
`git clone https://github.com/DocCreator/DocCreator.git`.

## What is ported

### Texture models — the ones that paste rather than filter

| here | from | what it models |
| --- | --- | --- |
| `paper_texture` | `Context::BackgroundContext` | the page drawn onto a sheet of paper rather than onto white, with grain and fold creases |
| `paper_overlay` | — (SynthDoG's `resources/paper/`) | a photograph of a real sheet laid over the finished page, ink included |
| `gradient_domain` | `GradientDomainDegradation.cpp` | stains pasted with Poisson blending (`cv::seamlessClone`, `MIXED_CLONE`) — Seuret, Chen, Eichenberger, Liwicki & Ingold, ICDAR 2015 |
| `phantom_character` | `PhantomCharacter.cpp` | leftover ink from a worn press, pasted against the flanks of characters |
| `pattern_overlay` | — (this repository) | a seal or flourish from `textures/ornament/` struck onto the finished page, blended by multiply so text under it stays readable |

### Filtering models

| here | from | what it models |
| --- | --- | --- |
| `ink_degradation` | `GrayscaleCharsDegradationModel.cpp` | Kieu's local noise model: ellipse-shaped noise regions around seed points, faded by a Gaussian |
| `shadow_binding` | `ShadowBinding.cpp` | the shadow a bound page casts near its spine |
| `bleed_through` | `BleedThrough.cpp` | ink from the other side of the sheet |
| `blur_zones` | `BlurFilter.cpp` | blur in patches, not over the whole page |
| `holes` | `HoleDegradation.cpp` | tears, rips and punched holes — the missing paper filled with **black** by default |

### Capture patterns — what the copy carries, not what the sheet suffers

| here | from | what it models |
| --- | --- | --- |
| `halftone_screen` | — (this repository) | the dot screen a photocopier lays down: a periodic screen at 45°, thresholded against local brightness |
| `scan_banding` | — (this repository) | the light and dark bands a flatbed roller or a fax leaves, one fine period over one slow one |
| `jpeg_blocks` | — (this repository) | the 8×8 grid of repeated JPEG compression, error accumulating over several passes |

These three are the odd family here, and the docstring in
[`capture.py`](capture.py) says why: **nothing happens to the paper.** The sheet
is intact; only its copy carries a periodic mark the device imposed. That is
also why they sit in `augmentation` rather than in the `ornament` attribute —
`ornament` is ink somebody meant to put on the page, and nobody wants these.

For Vietnamese invoice data this is the common case rather than the exotic one.
A sheet goes through the photocopier in the accounts office, is photographed
with a phone, and is forwarded through a messaging app that recompresses it —
the image that reaches a reader carries all three.

`make list-degradations` prints the registry.

## The textures

DocCreator ships its textures as image files — `data/Image/stainImages`,
`data/Image/phantomPatterns` — under an LGPL licence. Those are not vendored.
The patterns are synthesised from a seed instead (`stain_patch`,
`phantom_pattern`), so a fresh clone can render without downloading anything,
and a directory of real scans is used in preference whenever you point
`stains_dir` or `patterns` at one.

Paper is different: it is shared with the renderers, so it lives in
[`textures/paper/`](../textures/paper) and is named by
`rulebase/rules/visual.yaml` — as one sheet, or as a shortlist to draw from.
Regenerate with `make textures`; replace the files with real scans under the
same names and nothing else changes.

There are three directories of surface images and the difference between them
is **where in the pipeline they enter**, not what they show:

| directory | when | what it is |
| --- | --- | --- |
| [`textures/paper/`](../textures/paper) | before anything is drawn | the sheet the text is printed on. `paper_texture` only ever darkens, so ink stays ink. Eight sheets, all generated: four smooth (thermal, recycled, office) and four coarse (wood, stone, weave) whose grain reads as rough stock under a 0.3–0.5 alpha. |
| [`augmentations/data/image/`](../augmentations/data/image) | last step of the chain | photographs of real sheets, from SynthDoG's `resources/paper/`, laid over the finished page. `paper_overlay` multiplies *and* screens, so fibre darkens while the sheet's own scatter lifts the page — a render that has been through both reads as printed on paper rather than pasted onto a picture of paper. |
| [`textures/background/`](../textures/background) | after ageing, glyph renderer only | the scene the sheet is photographed on, from SynthDoG's `resources/background/`. The two HTML renderers produce flat scans with no surround. `background.image.paths` in `generators/synthdog/config_vi_receipt.yaml` points at it. |

DocCreator ships desk tops of its own in `data/Mesh/Background/wood00..04.jpg`,
which is the same idea as the third row. Their images are LGPL data, the same
reason the stain and phantom patterns are not vendored, so the wood, stone and
weave here are generated — and, being generated, they earn their keep better as
coarse *paper* than as a table a photograph would give away.

## The two that were hardest to get right

**`ink_degradation`** is why DocCreator is worth copying. Additive noise looks
like noise; this looks like ink that decayed, because of three choices:

1. **Seed points are placed relative to the characters** — some on the paper,
   some straddling a character edge, some inside the ink — and the proportions
   shift with the level (50/30/20 up to level 4, 30/50/20 to 7, 20/30/50 above).
   Low levels speckle the page; high levels eat the glyphs.
2. **The number of noise regions scales with the number of connected
   components of ink** (`2 × components × level / 5`), which is *not* the same
   as the amount of ink — see the second deviation below.
3. **Each region fades from its centre by a Gaussian**, so regions have no hard
   edges and overlapping ones compound.

Two deviations, and the reasons for them.

**Independent seed points are confined to the sheet.** DocCreator's input is a
scanned page that fills the frame, so its "background" is the sheet. A
renderer's output often is not — a receipt sits on a dark surface — and placing
specks there puts white dots in mid-air. The sheet is found by thresholding,
opening, closing and keeping the largest component.

**The dose is a fraction of theirs** (`DENSITY = 0.25 * 0.7`). Two regions per
component was tuned on scanned prose, where a component is a letter. On a
Vietnamese invoice a *dotted leader line* — the row of full stops after `Mã số
thuế:` — makes every dot its own component, so the count measures the layout
rather than the ink. Measured at `level: 5`, one page per layout:

| layout | components | seed points | of them dots ≤12px |
| --- | ---: | ---: | ---: |
| `eatery_ascii` | 403 | 806 | 0% |
| `invoice_brand` | 544 | 1,088 | 8% |
| `market_compact` | 476 | 952 | 23% |
| `invoice_hotel_stay` | 2,250 | 4,500 | 70% |
| `invoice_export` | 3,132 | 6,264 | 49% |
| `invoice_vat_form` | 3,233 | 6,466 | 74% |

Eight times the speckle on an invoice as on a receipt, for a reason unrelated
to how much ink is on the page — and those are, in that order, the layouts that
lose most recall to ageing (0.026 for `invoice_brand` against 0.487–0.521 for
the three dotted ones; see [`data/dataset60/proof/README.md`](../data/dataset60/proof/README.md)).
The figure was set by eye against a rendered A4 invoice, in two passes — a
quarter first, then 30% off that — and it is written as an expression so both
passes stay legible. `density` is a parameter, so a chain in
`rules/augmentation.yaml` can ask for more. The deeper repair — not deriving the
dose from a component count at all — is still open.

**`holes`** is the tear model, and three of its four ideas are easy to get
wrong. A hole is a **pattern image, not a shape formula** — DocCreator ships
binary masks (18 border, 18 centre, 28 corner) in which black marks the paper
that is gone, which is why theirs look torn and a drawn ellipse never does. The
missing paper is filled with a flat colour whose application default is
**black** (`Assistant.cpp:153`), because a page photographed over a dark
surface shows dark through the tear. And a tear has a **shaded rim**
(`drawBorder`/`isInMarge`), without which it reads as a sticker laid on top.

The port generates the masks rather than vendoring them, and the three
placements are genuinely different shapes rather than one shape moved about. A
border tear removes *everything from the page edge inwards* to a ragged line: a
torn edge is not a hole that happens to sit near the border, and drawing it as
a blob near the edge is exactly what makes a synthetic tear look pasted on. The
ragged line is a smoothed random walk, not summed sines — sines are periodic,
and a periodic tear line comes out as evenly spaced battlements.

One deviation, on their own advice: DocCreator applies the rim only when
filling with an image, and a comment in their source flags the colour path as
an oversight (`//B:TODO: why don't we also pass "shadowBorderWidth &
shadowBorderIntensity" to fillHoleWithColor ?`). The rim is applied in both here.

**`phantom_character`** needs a real gap to work in. DocCreator sizes the
pattern from the character's bounding box and from the distance to its
neighbour; on dense small text the connected components are whole *words*, so
sizing from the box gives a pattern as wide as the word and stamps it over the
glyphs next door. The port therefore places a pattern only where a neighbour
gap was actually measured, and caps the width at 40% of the character height —
residue squeezed out sideways by a character cannot be wider than the character
is tall.

## Use

```python
from degradation import apply_chain

aged = apply_chain(image, [
    ("paper_texture", {"paper": "thermal_cream", "alpha": 0.4, "creases": 3}),
    ("ink_degradation", {"level": 3}),
    ("gradient_domain", {"count": 5, "strength": 0.75}),
    ("blur_zones", {"radius": 1.4, "zones": 3}),
    ("shadow_binding", {"border": "left", "intensity": 0.5}),
], seed=7)
```

Order is not commutative: ink degradation before blur reads as worn ink that
was then scanned badly; the other way round it reads as a smudged scan.
`paper_texture` comes first — everything after it is damage to a sheet that
already exists. Shadow and holes come last: they belong to the sheet, not to
the printing.

`apply_chain` takes one seed and threads it through every step, so a chain is
reproducible.

### From a recipe

All three renderers call this rather than building their own chain, which is
what keeps the ageing one implementation instead of three:

```python
from degradation.pipeline import apply_recipe

aged = apply_recipe(image, recipe, seed=recipe.seed)
```

`apply_recipe` fills in the sheet from the recipe's `visual.paper`, so a recipe
puts the same paper under a glyph render and an HTML render. The chain itself
comes from `rulebase/rules/augmentation.yaml`.

## Seeing it

```bash
make showcase        # one before/after image per model, on the same page
```

Writes `samples/degradation/showcase-*.jpg` and a contact sheet. Applying each
model alone is the point: a paper composite, a Poisson-blended stain and pasted
ink residue look nothing alike, and a chain hides that.

`tools/augment_samples.py` is the other driver — it applies a per-source chain
to directories of rendered pages, for judging a chain rather than a model.
