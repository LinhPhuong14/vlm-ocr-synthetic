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
| [`textures/background/`](../textures/background) | nothing reads it now | the scene the sheet is photographed on, from SynthDoG's `resources/background/`. Only the glyph renderer composited onto it, through `background.image.paths` in its config; that renderer is deleted. The HTML renderer produces flat scans with no surround, so no current page sits on a desk. |

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

**The dose is a fraction of theirs** (`DENSITY = 0.35`). Two regions per
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
The figure was settled by eye against a rendered A4 invoice over three passes —
0.25, then 0.175, then back up to 0.35 — so nothing derives it and nothing but
a test would notice it drifting. `density` is a parameter, so a chain in
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

## What is not here

Fourteen models are registered and every one of them is reached by at least one
chain in `rulebase/rules/augmentation.yaml`. What is *not* reached is a good
deal larger: parameters no chain passes (`blur_zones.feather`,
`shadow_binding.angle`, `bleed_through.verso`, `holes.below`), valid values
never drawn (`ink_degradation` levels 5–10, `fill: paper`, `border: right`),
and two resource directories the code reads but the tree does not have
(`textures/stain/`, real hole masks).

The inventory — what is used, what is dead, and what is worth adding from
Augraphy, straug, ocrodeg, graphic-design practice and the Vietnamese paper
trail — is in [`docs/lam-cu-de-xuat.md`](../docs/lam-cu-de-xuat.md).

The biggest gap it names: **not one model here moves a pixel.** The chain is
asserted not to resize the page, so the dataset had every kind of dirt and no
sheet that was skewed, curled or photographed at an angle.

That gap now has a fix, in [`geometry.py`](geometry.py) — but deliberately not
inside `DEGRADATIONS`/`apply_recipe`. The shape assertion above is exactly what
a page-geometry model cannot satisfy, so it runs as ITS OWN step, after the
chain and after that assertion, moving the sheet's box collections (`boxes`,
`words`, `cells`) along with the pixels instead of trusting them to still
describe the page. Three models: `page_curl` (generalised from
`generators/synthdog/elements/warp.py::CurlWarp`, since deleted — see
[`docs/renderers.md`](../docs/renderers.md)), `fold_crease` and
`corner_bulge` (both a flat, invertible approximation of the paper shapes
[SyntheticDoc](https://github.com/tanguymagne/SyntheticDoc) gets by physically
simulating a sheet in ARCSim and rendering it in Blender — neither tool fits
here, ARCSim's licence is non-commercial only and Blender needs a GPU and no
`pip` package exists for it, so the *shape*, not the code, is what is reused).
See the module's own docstring for the maths, and `rulebase/rules/
augmentation.yaml`'s "HÌNH HỌC" section for how a recipe opts in through
`augmentation.warp`. All three ship `enabled: false` — reachable with
`--force augmentation=page_curl` (or `folded`, `lifted_corner`) but not yet in
a default run, until someone has looked at samples.

**The geometry alone reads as noise, not as paper — the shading is what makes
it read as a surface.** SyntheticDoc's own `media/teaser.jpg` lines up six
panels — rendered image, albedo, *shading*, normal map, 3D coordinates, UV
map — and it is the shading panel, not the pixel displacement, that carries
most of what makes a sample look like curved paper rather than a flat photo
with a mild geometric wobble. Each of the three functions therefore derives
an analytic height-field gradient from its own displacement formula (no 3D
mesh, no renderer) and shades it with a one-line Lambertian model — random
light direction every call, on purpose: `docs/lam-cu-de-xuat.md` already
names a fixed light angle (`shadow_binding.angle`) as a defect a model would
learn and then fail on real photos lit from elsewhere.

---

# Augraphy's models, and putting one on a box instead of a page

[Augraphy](https://github.com/sparkfish/augraphy) is the second source. Its
pipeline runs in three phases — `ink → paper → post` — which is the same idea
as `paper_texture` going first here. Twelve of its models are ported, on the
same terms as DocCreator's: not vendored, rewritten per model, each naming what
it came from.

| here | file | what it models |
| --- | --- | --- |
| `bad_photocopy` | [`bad_photocopy.py`](bad_photocopy.py) | a worn copier: toner dust in blotches, burnt-out patches, grey crushed to black and white |
| `dirty_drum` | [`dirty_drum.py`](dirty_drum.py) | streaks **along the feed direction** — one mark on the drum, printed once per revolution, so the streak is continuous |
| `dirty_rollers` | [`dirty_rollers.py`](dirty_rollers.py) | roller bands across the feed. Unlike `scan_banding` these are aperiodic and ridged, which is how you tell the two apart on a real scan |
| `letterpress` | [`printing.py`](printing.py) | ink that did not transfer: clusters of paper showing through the middle of strokes |
| `hollow` | [`printing.py`](printing.py) | a dry ribbon — only the outline of each stroke survives |
| `dot_matrix` | [`printing.py`](printing.py) | an impact printer's pin grid, with **dead pins** and ribbon wear |
| `markup` | [`marks.py`](marks.py) | a person's pen: highlight, underline, strikethrough, circle, crossed off |
| `scribbles` | [`marks.py`](marks.py) | a squiggle in the margin |
| `voronoi_tessellation` | [`tessellation.py`](tessellation.py) | cell patterns — recycled fibre, security backgrounds |
| `delaunay_tessellation` | [`tessellation.py`](tessellation.py) | the triangular dual of the same seed points; reads as printed decoration rather than as fibre |
| `color_shift` | [`channel.py`](channel.py) | channels out of register — a misaligned press plate, or a lens's chromatic aberration |
| `glitch_effect` | [`channel.py`](channel.py) | bands of scanlines slid sideways |

Three things these add that nothing here had:

1. **Ink that failed at printing time**, as opposed to ink that decayed
   afterwards. `ink_degradation` is DocCreator's model of a page that was
   printed properly and then aged; `letterpress`, `hollow` and `dot_matrix` are
   pages that were never printed properly at all. On Vietnamese paperwork the
   second is the commoner case.
2. **Colour.** Every model that predates them changes brightness only, so a
   model trained on this set met its first colour fringe on real data.
3. **Marks a person made.** Not damage: somebody highlighted a line.

## The machine is three attributes, not one scenario

**Currently switched off.** `toner.yaml`, `drum.yaml` and `rollers.yaml` each
kept only their `no_*` value; `bad_photocopy`, `dirty_drum` and `dirty_rollers`
are unregistered in `degradation/__init__.py`'s `DEGRADATIONS` table, so no
chain in `rules/` can reach them any more. The 25.2%-of-pages figure below is
what this used to draw, not what it draws today. The three functions
themselves are untouched -- re-enabling means restoring an option to each of
the three YAML files (git history has the old ones) and putting their three
`DEGRADATIONS` entries back.

The first three models above are the only ones here that were not reached
from `rules/augmentation.yaml`. They had a rule-base **attribute each** —
[`toner.yaml`](../rulebase/rules/toner.yaml),
[`drum.yaml`](../rulebase/rules/drum.yaml),
[`rollers.yaml`](../rulebase/rules/rollers.yaml) — and a file each, for the same
reason: they are three parts of one machine, and the parts fail independently.
A copier can score its drum while its cartridge is fine.

Bundled into one `augmentation` value, every combination of the three would be
a scenario somebody had to write, and the number to write is the product rather
than the sum. As attributes they compose for free: a page draws one value from
each, `chain_of` concatenates them in draw order, and the marks land after the
sheet has been aged rather than under it.

They were not quite independent, and one tag said so. `toner`'s worn values
set `worn_machine`; `drum_scored` and `rollers_worn` required it, so the
severe grades only appeared on a machine that was already dirty. Drawing all
three freely would produce pages with a shredded drum and a brand-new
cartridge — possible, but not at the rate independence would give. The tag
itself is gone now along with the values that set and required it; restoring
the old options (see `tests/test_spec.py`'s git history for the ordering test
that checked this) brings it back too.

Measured over 3,000 draws, back when all three were live: **25.2%** of pages
carried at least one machine mark.

Two consequences worth knowing, from when the three carried real chains:

* **`--clean` pinned all four.** `pipeline.invariants.CLEAN_FORCES` names the
  empty value of every chain-bearing attribute. A clean run that pinned only
  `augmentation` would have gone on calling itself clean with a drum streak
  drawn across it — and the clean set is the ceiling every ageing number is
  measured against, so that moves the baseline silently. The dict still names
  `toner`/`drum`/`rollers`'s clean values today, harmlessly -- `make
  preflight`'s check (next bullet) only requires a chain-bearing attribute to
  be named, never forbids naming one that no longer chains.
* **`make preflight` checks that dict against the rules both ways**: every
  chain-bearing attribute must be named in it, and every value it names must
  have an empty chain. Rename a value in the YAML and preflight fails.

## `dot_matrix` is not `halftone_screen`

They look adjacent and are not. A copier's screen varies the *size* of a dot
with local darkness (AM screening). An impact printer has one dot size — the
pin — and each grid cell either fires or does not. So dot-matrix text breaks up
on an even lattice and photocopied text breaks up in clumps. Both patterns are
learnable, and only if the data has both.

`dead_pins` is the part worth having. A broken pin leaves a white line running
through every character on the page at the same height. That is **structured**
noise — regular, repeatable, learnable — and it is on a great many Vietnamese
delivery notes and till receipts.

## `by_box` — an effect on part of the page

Every model above ages the whole sheet. Almost nothing on a real page does. A
highlighter covers one line. A dead pin cuts one stripe. Somebody circles the
totals row and nothing else.

`by_box` is the entry in `DEGRADATIONS` that is not a model. It wraps any other
name, takes the page's label boxes, picks some of them, and lets the model act
only there:

```yaml
- [by_box, {effect: markup,
            params: {style: highlight},
            select: {policy: run, fraction: 0.08}}]
```

Six policies, and they differ in **shape**, not in how many boxes they take:

| policy | shape | for |
| --- | --- | --- |
| `scatter` | any boxes, anywhere | blots, a stray pen mark |
| `run` | consecutive boxes in reading order | a highlighter swipe; nobody highlights every other line |
| `band` | every box a horizontal stripe crosses | a dead pin, a roller mark, a fold |
| `column` | every box a vertical stripe crosses | a drum streak, a spine shadow |
| `kind` | boxes by role, matched on the dotted prefix | somebody circles `total`, not a random cell |
| `all` | every text box | still not the whole page: margins and gaps stay clean |

Two ways of acting, chosen automatically:

* **`mask`** — run the effect over a copy of the **whole page**, then blend it
  back through a soft mask of the chosen boxes. Sounds roundabout, and is the
  only correct way for anything with structure that runs across the sheet: a
  drum streak crossing two boxes has to be *one* streak. Cropping each box and
  running the model on the pieces gives you two streaks that do not line up.
* **`place`** — call the model once per box with the box's coordinates, for
  things that are *drawn* rather than filtered. An underline has to sit under
  that line of text. A model that takes a `regions` argument gets this route.

The mask is padded, roughened with low-frequency noise and feathered before
use, all in units of box height rather than pixels — a rectangle with clean
corners is the fastest way to make a synthetic page look synthetic, and a
figure in pixels stops being right the moment the font size changes.

**With no boxes, `by_box` raises.** Quietly falling back to the whole page
would make a chain that says `by_box` do the one thing it says it does not.
For an image with no labels — a directory of finished renders, a real scan —
`regions.boxes_from_ink()` finds text clusters by thresholding. That is
detection, not labels, and it is named so you can tell.

## Does a chain age the text out of its own labels?

```bash
make legibility          # every chain in rules/augmentation.yaml, on a probe page
```

A box asserts there is text at those coordinates. A chain that erases the text
while the label still claims it is not hard data — it is **poisoned** data, and
a model trained on it learns to see text in blank paper.

`--sample N` is the mode that matters now that four attributes contribute
steps. The per-value table measures one value at a time; a real page draws one
of each, and the product of 24 x 4 x 4 x 4 is not a table anyone reads. So it
draws real recipes at their real weights and reports the compositions that
actually occur. Sixty draws: median 0.86 of contrast kept, worst 0.51, none
losing a box.

[`tools/legibility.py`](../tools/legibility.py) measures ink-versus-paper
contrast inside every box, before and after, and reports the share of boxes
that fall below a readability floor. It found two things while the Augraphy
models were being tuned: `letterpress` was scattering its clusters uniformly
over a page that is 97% paper, so it changed almost nothing; and `dot_matrix`
was flattening the paper grain it printed over.

`docs/lam-cu-de-xuat.md` ranks this check first, ahead of adding any model —
diacritics are a few pixels each, `mà` and `mã` differ by one of them, and
until this existed nothing here measured whether a chain had eaten one.

## A model with no chain is a model that has never been used

`tools/rules_report.py` — which is what `make preflight` and `make check-rules`
run — now compares the registry with `rules/augmentation.yaml` **in both
directions**. Naming a model that does not exist was always an error. Now so is
the reverse: a model no chain names, `by_box`'s `effect:` included.

That is the whole subject of `docs/lam-cu-de-xuat.md`, turned into a check.
Before it, `holes` could take a `below` image and nothing used it, `textures/stain/`
was read by code and absent from the tree, and `ink_degradation` had never been
run above level 4 — none of which anything reported.
