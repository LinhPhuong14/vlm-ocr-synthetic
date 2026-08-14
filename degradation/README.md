# degradation — DocCreator's models, in Python

[DocCreator](https://github.com/DocCreator/DocCreator) (Journet, Mansencal,
Kieu et al., LaBRI Bordeaux) is a C++/Qt application whose degradation models
were designed against real degraded manuscripts. The models are the valuable
part; the Qt application is not something a Python generation pipeline can
call. So they are ported here and applied to whatever a generator produced.

DocCreator itself is not vendored here: the models carry citations to the file
each came from, which is what you need to check one. Read the original with
`git clone https://github.com/DocCreator/DocCreator.git`.

## What is ported

| here | from | what it models |
| --- | --- | --- |
| `ink_degradation` | `GrayscaleCharsDegradationModel.cpp` | Kieu's local noise model: ellipse-shaped noise regions around seed points, faded by a Gaussian |
| `shadow_binding` | `ShadowBinding.cpp` | the shadow a bound page casts near its spine |
| `bleed_through` | `BleedThrough.cpp` | ink from the other side of the sheet |
| `blur_zones` | `BlurFilter.cpp` | blur in patches, not over the whole page |
| `holes` | `HoleDegradation.cpp` | holes punched or torn through the sheet |

Each module's docstring names the file it came from and what the model does,
so a change can be checked against the original.

### The one that matters

`ink_degradation` is why DocCreator is worth copying. Additive noise looks like
noise; this looks like ink that decayed, because of three choices:

1. **Seed points are placed relative to the characters** — some on the paper,
   some straddling a character edge, some inside the ink — and the proportions
   shift with the level (50/30/20 up to level 4, 30/50/20 to 7, 20/30/50 above).
   Low levels speckle the page; high levels eat the glyphs.
2. **The number of noise regions scales with the amount of ink**
   (`2 x connected_components x level / 5`), so a sparse page gets sparse damage.
3. **Each region fades from its centre by a Gaussian**, so regions have no hard
   edges and overlapping ones compound.

One deviation from the original, and the reason for it: DocCreator's input is a
scanned page that fills the frame, so its "background" is the sheet. A
generator's output often is not — a receipt sits on a dark surface — and
placing specks there puts white dots in mid-air. Independent seed points are
confined to the sheet, found by thresholding and closing.

## Use

```python
from degradation import apply_chain

aged = apply_chain(image, [
    ("ink_degradation", {"level": 6}),
    ("bleed_through", {"intensity": 0.6}),
    ("blur_zones", {"radius": 2.0, "zones": 3}),
    ("shadow_binding", {"border": "left", "intensity": 0.5}),
], seed=7)
```

Order is not commutative: ink degradation before blur reads as worn ink that
was then scanned badly; the other way round it reads as a smudged scan. Shadow
and holes come last — they belong to the sheet, not to the printing.

`apply_chain` takes one seed and threads it through every step, so a chain is
reproducible.

## Seeing it

```bash
python tools/augment_samples.py --synthdog <dir> --genalog <dir> -o samples/degradation
```

Writes a before/after pair per page and a contact sheet.
[`samples/degradation/`](../samples/degradation) holds twenty of them: ten synthdog receipts, five genalog pages and
five pages from [genalog](https://github.com/microsoft/genalog), which is an
external dependency here rather than part of the repository.
