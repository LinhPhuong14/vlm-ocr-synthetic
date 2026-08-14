# Python 3.14, and why there is no pygame


The suite passes unchanged on **CPython 3.14.7** (and on 3.11), both backends
included. Two things make that true, and both are enforced by tests rather than
just claimed.

### Dependency floors

Python 3.14 needs newer dependencies than older interpreters: below these
versions there is no cp314 wheel, so pip falls back to a source build that fails
or takes minutes. `pyproject.toml` applies them with `python_version >= '3.14'`
markers, and `vlm_ocr_synthetic/compat.py` re-checks them at runtime.

| dependency | floor on 3.14 | what happens below it |
| ---------- | ------------- | --------------------- |
| `pydantic` | 2.12    | 2.11 and older have no cp314 wheel for `pydantic-core` — install fails outright |
| `PyYAML`   | 6.0.3   | first release with a cp314 wheel |
| `Pillow`   | 11.3    | first release with a cp314 wheel |
| `playwright` | 1.52  | 1.49 and older pin `greenlet==3.1.1`, which has no cp314 wheel |

Older interpreters keep the loose floors, so nothing is forced on 3.10 – 3.13.

### The original synthdog does not run on 3.14

The synthdog from donut renders through `synthtiger`, which pins
`pygame==2.6.1`. Measured on CPython 3.14.7:

| attempt | result |
| ------- | ------ |
| `pip install pygame` | no cp314 wheel → source build **fails** |
| `pip install synthtiger` | pulls `pygame==2.6.1` → same failure |
| `pip install pygame-ce` | **works** (2.5.8, ships cp314 wheels, same `import pygame` API) |
| synthtiger + pygame-ce + NumPy 2 | `import synthtiger` → `AttributeError: np.sctypes was removed in NumPy 2.0` (via `imgaug`) |
| synthtiger + pygame-ce + NumPy 1.26 (2 min source build) | `import synthtiger` → scipy dies on `np.long`, removed in NumPy 2 |

So **pygame is only the first wall.** Swapping in `pygame-ce` clears it, but
`imgaug` (unmaintained since 2020) needs NumPy 1.x APIs while every scipy build
that exists for 3.14 needs NumPy ≥ 2 — a conflict no pin resolves. The last
interpreter where that whole stack installs from wheels is **CPython 3.12**
(`numpy 1.26.4` and `scipy 1.13.1` stop at cp312).

### What replaces pygame here

Our `synthdog` backend never depended on pygame — it draws with Pillow, whose
FreeType binding covers everything synthtiger used pygame for:

| synthtiger / pygame | here |
| ------------------- | ---- |
| `pygame.freetype` glyph rasterisation | `PIL.ImageFont` on FreeType 2.14, with **raqm 0.10** for complex-script shaping (Vietnamese diacritics, Arabic, Indic) |
| pygame surfaces and blitting for layers | `PIL.Image` / `ImageDraw` layers |
| `imgaug` noise and effects | the `paper` layer: `PIL.ImageChops` + a seeded `random.Random`, so output stays reproducible |
| synthtiger text layout | the wrapping and flow layout in `renderers/synthdog/renderer.py` |

`tests/test_compat.py` runs a real render in a clean interpreter and fails
if `pygame`, `synthtiger` or `imgaug` ever appear in `sys.modules`.

If you specifically need the original synthdog, run it on Python ≤ 3.12 in its
own environment and keep this package on 3.14 — they exchange data as plain
images plus JSON.
