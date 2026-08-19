# references — upstream code we port from

Three projects whose degradation models this repository borrows from. **The
sources are not committed** — only this file is. Run [Fetching](#fetching) below
and the directory fills itself in.

It follows the rule [`degradation/README.md`](../degradation/README.md) already
states for DocCreator: a port carries a citation to the file it came from, and
you fetch the original when you want to check one. That is a different thing
from **vendored** code — third-party code we actually *run*, which lives under
`generators/` and is declared in `tools/paths.py:VENDORED` and mirrored in
`pyproject.toml`. Nothing here is on either list, and nothing here is imported
by anything. Deleting the whole directory breaks no build.

| | licence | what it is | why it is here |
| --- | --- | --- | --- |
| `doccreator/` | LGPL-3.0 | C++/Qt, LaBRI Bordeaux | every module in `degradation/` is a port of one of its models |
| `augraphy/` | MIT, Sparkfish LLC | Python, 54 augmentations in three phases | the closest thing to a complete catalogue of document degradation |
| `straug/` | Apache-2.0 | Python, 36 augmentations in eight groups | the camera and post-processing side, which DocCreator has nothing on |

Three licences, none of them ours. Read them; do not paste from them. A port
that reproduces upstream line for line inherits that project's licence, and
LGPL and MIT do not mix on the same terms. What travels well is the *model* —
which seed points, which distribution, which order — and that is what the
citations in `degradation/` record.

---

## How to use this

### 1. Check a port against its original

Every module in `degradation/` names the file it came from. Follow the name:

```bash
grep -rn "\.cpp" degradation/*.py | head
sed -n '140,170p' references/doccreator/software/DocCreator/src/GenerateDocument/Assistant.cpp
```

The citations resolve exactly, line numbers included — `Assistant.cpp:153` in
`degradation/holes.py` is `QColor Hole_defaultBackgroundColor(0, 0, 0, 255)`,
the black-fill default that module is built around. If a citation stops
resolving, upstream moved and the port is now describing a file that no longer
says what it claims.

### 2. Read a model before writing our version of it

Augraphy is one class per file and the filename is the class lowercased, so the
map below is enough to find anything:

```bash
ls references/augraphy/augraphy/augmentations/ | wc -l      # 54
sed -n '1,60p' references/augraphy/augraphy/augmentations/lightinggradient.py
```

Read for the *shape* of the model — what it randomises, what it keeps fixed,
where it clamps — not for code to copy. Our version has to take its ranges from
the measured profile of `real_data_for_augment_refer/`, which upstream knows
nothing about.

### 3. See what an effect looks like before committing to it

Augraphy is pip-installable and runs standalone. Do this in a scratch venv, not
in a renderer's venv — nothing in this repository should ever import it:

```bash
python3 -m venv /tmp/aug && /tmp/aug/bin/pip install -q augraphy opencv-python-headless
/tmp/aug/bin/python -c "
from augraphy import LightingGradient
import cv2
img = cv2.imread('data/dataset60/synthdog/synthdog_000.jpg')
cv2.imwrite('/tmp/out.jpg', LightingGradient()(img))"
```

Run it on **our** receipts, not on the English A4 samples upstream ships with.
An effect that reads well on a dense office page can be invisible on a 57 mm
till roll, and that difference is the whole reason for measuring first.

### 4. Know which of the three to reach for

The three cover different halves of the problem and barely overlap:

- **DocCreator** — what happens to *paper and ink over time*. Its models were
  built against real degraded manuscripts, which is why they hold up and why
  they are the ones already ported. Nothing about cameras.
- **Augraphy** — what happens to a document *passing through office machines*:
  printing, copying, faxing, scanning. Organised as `ink → paper → post`, which
  is the same ordering argument `degradation/README.md` makes about chains.
- **STRAug** — what happens *in the camera*: focus, motion, sensor noise,
  compression, and the auto-contrast a phone applies before you ever see the
  file. The half neither of the other two models.

---

## Where the models actually live

    doccreator/framework/src/Degradations/     20 files — the models themselves
    doccreator/software/DocCreator/src/        the Qt application around them
    augraphy/augraphy/augmentations/           54 files, one class each
    straug/straug/                             8 group modules, 36 classes

DocCreator's degradation models are in `framework/`, **not** in `software/` —
`software/` is the GUI. The one exception is `Assistant.cpp`, cited by
`degradation/holes.py`, which is under `software/DocCreator/src/GenerateDocument/`.

## Map: what we have → what to read

| ours | DocCreator | Augraphy |
| --- | --- | --- |
| `bleed_through.py` | `BleedThrough.cpp` | `bleedthrough.py` |
| `blur_zones.py` | `BlurFilter.cpp` | — (Augraphy blurs the whole page) |
| `holes.py` | `HoleDegradation.cpp`, `Assistant.cpp` | — |
| `ink_degradation.py` | `GrayscaleCharsDegradationModel.cpp` | `inkbleed.py`, `letterpress.py` |
| `shadow_binding.py` | `ShadowBinding.cpp` | `bookbinding.py` |
| `texture.py` → `gradient_domain` | `GradientDomainDegradation.cpp` | `stains.py` |
| `texture.py` → `phantom_character` | `PhantomCharacter.cpp` | `letterpress.py` |
| `texture.py` → `paper_texture` | `Context::BackgroundContext` | `colorpaper.py`, `brightnesstexturize.py`, `noisetexturize.py` |

## Map: what is planned → what to read first

| planned | Augraphy | STRAug |
| --- | --- | --- |
| `illumination` | `lightinggradient.py` | — |
| `white_balance` | `colorshift.py` | `process.py:Color` |
| `cast_shadow` | `shadowcast.py` | `weather.py:Shadow` |
| `handwriting` | `scribbles.py`, `markup.py` | — |
| `redaction` | `markup.py` | — |
| `occluder` | `bindingsandfasteners.py` | — |
| `perforated_edge` | `pageborder.py` | — |
| `thermal_fade` | `lowinkrandomlines.py` | — |
| `thermal_dead_element` | `lowinkperiodiclines.py`, `lowinkline.py` | — |
| `scanner_app` | — | `process.py:AutoContrast`, `Sharpness`, `Posterize` |
| `specular` | `reflectedlight.py`, `lensflare.py` | — |
| `screen_recapture` | `moire.py`, `lcdscreenpattern.py` | — |
| `dot_matrix` | `dotmatrix.py` | — |
| `squish` / `section_shift` | `squish.py`, `sectionshift.py` | — |
| `partial_defocus` | `depthsimulatedblur.py` | `blur.py:DefocusBlur` |
| low-light noise | `lowlightnoise.py` | `noise.py:ShotNoise` |
| skew and rotation | `geometric.py` | `geometry.py:Rotate`, `Perspective` |
| downscale and JPEG | `jpeg.py`, `rescale.py` | `camera.py:JpegCompression`, `Pixelate` |
| sheet running off frame | `pageborder.py` | — |
| crease with its own shadow | `folding.py` | `warp.py:Curve`, `Distort` |

**`thermal_stripe` has no upstream anywhere.** The red end-of-roll band is
specific to till rolls, and neither project models it — that one gets written
from the photograph, not from a reference.

---

## Fetching

Tarballs, not clones: `git clone` of either large repo dies in `index-pack` on a
memory-limited machine, and a snapshot is all a read-only reference needs.

Each block below is self-contained and starts from the repository root. They
delete an existing copy first — `mv` onto a directory that already exists moves
it *inside* rather than replacing it, which silently nests a second full copy.

**Augraphy** — 160 MB fetched, 1.8 MB kept:

```bash
cd "$(git rev-parse --show-toplevel)" && mkdir -p references && rm -rf references/augraphy && curl -L -o /tmp/aug.tar.gz https://codeload.github.com/sparkfish/augraphy/tar.gz/refs/heads/dev && tar xzf /tmp/aug.tar.gz -C references && mv references/augraphy-dev references/augraphy && rm -f /tmp/aug.tar.gz && rm -rf references/augraphy/examples references/augraphy/images references/augraphy/doc references/augraphy/videos && du -sh references/augraphy
```

**DocCreator** — 300 MB fetched, 24 MB kept. `data/` is the LGPL fonts, meshes
and stain images that `degradation/README.md` explains are not redistributable,
which is why `stain_patch` and `phantom_pattern` are synthesised from a seed:

```bash
cd "$(git rev-parse --show-toplevel)" && mkdir -p references && rm -rf references/doccreator && curl -L -o /tmp/dc.tar.gz https://codeload.github.com/DocCreator/DocCreator/tar.gz/refs/heads/master && tar xzf /tmp/dc.tar.gz -C references && mv references/DocCreator-master references/doccreator && rm -f /tmp/dc.tar.gz && rm -rf references/doccreator/data references/doccreator/thirdparty references/doccreator/bundlers && du -sh references/doccreator
```

**STRAug** — small enough to clone:

```bash
cd "$(git rev-parse --show-toplevel)" && mkdir -p references && rm -rf references/straug && git clone --depth 1 --quiet https://github.com/roatienza/straug references/straug && rm -rf references/straug/.git references/straug/images && du -sh references/straug
```

Check it landed — 54, 20 and 8 are the counts to expect:

```bash
ls references/augraphy/augraphy/augmentations/*.py | wc -l
ls references/doccreator/framework/src/Degradations/ | wc -l
ls references/straug/straug/*.py | grep -vE '(__init__|ops)\.py' | wc -l
```

The last one filters `__init__.py` and `ops.py`: STRAug is 8 *groups* in 10
files, and the 36 augmentations are classes inside those 8.

`augraphy/paper_textures/` (172 KB) is kept on purpose: real paper scans, and
`textures/paper/` still wants a pink and a pale-yellow thermal stock.
