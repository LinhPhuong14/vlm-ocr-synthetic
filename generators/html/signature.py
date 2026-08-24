"""Stretch a handwriting face's letters until they become a signature.

    from signature import Signer, svg
    Path("sig.svg").write_text(svg(Signer(seed=7).sign("Nguyễn Thị Bích Ngọc")))

A signature is not handwriting, and this module exists because of that
difference rather than in spite of it. `handwriting.py` refuses to nudge a
glyph, and `docs/handwriting-html.md` says why: the path removed in `ff9a9f0`
took a **printed** typeface, jittered each character, and called the result a
hand -- it was printing with a tremor, because the stroke shapes were still a
typeface's and no amount of jitter changes a stroke shape.

The claim here is a different one, and it is narrower. **A signature is
already a distortion.** Every source surveyed for this module describes it the
same way: an over-learned mark in which the initial is enlarged out of
proportion, the body is simplified or abandoned, the terminal is pulled out and
lifted, and a flourish is added that belongs to no letter at all. The
distortion is not a disguise laid over writing -- it *is* the signature, and it
is the one thing about a signature that can be stated as geometry.

So this engine stretches. It takes real letters -- from a licensed handwriting
face, or from the WriteViT checkpoint -- and applies the transformations the
survey named. And it draws three marks that are not letters: the terminal
flourish, the paraph, and the **scrawl** the body collapses into. The survey
says none of those three is a letter, which is exactly why they have to be
drawn rather than set.

## Two inks

    font    outlines out of `fonts/hand/`, stretched. Always there, and it
            repeats: every `a` is the same `a` and the strokes are a
            typeface's however hard they are pulled.
    model   WriteViT's own ink, traced into contours. Thin, joined up, 106
            writer styles, different every time -- and it needs the clone,
            about seven seconds a word on CPU, and it cannot write a run of
            capitals.

They are not a hierarchy with a winner. `model` writes a name beautifully and
cannot write `LQĐ` at all; `font` writes anything and writes it the same way
twice.

Where that difference lands is **in the style, not in the ink**. A source
declares which of the survey's legibility styles it can draw, and `Style`
picks from those -- so the model is never handed a monogram it will refuse.
The order used to be the other way round, and it cost eleven of eighteen
sample seeds: a style was drawn, the model refused it, and the mark came back
in typeface. `fill` still falls back per block, but as a safety net rather
than as the normal case, and the label records which ink each mark is in.

The seam that lets a raster into a vector engine is `trace`, and it is the
whole trick: once the model's pixels are contours, every warp in this file
applies to them exactly as it applies to a glyph, and nothing downstream knows
the difference.

## Letters that stop being letters

The scrawl is the part that took two passes to get right, and it is worth
saying why. Squeezing a letter and fading it leaves it a letter: the first
version of this engine produced marks that read `Nguyễn Thị Bích Ngọc` in a
slightly slanted hand, and **a signature you can read like that is not what
comes back on a form.**

The survey does say what happens instead, in several voices. The body is
"simplified or abandoned". An illegible signature is normal, and commonest in
people who sign many times a day -- which is who signs the documents this
repository generates. And the useful part, from the forensic sources: **the
movement survives when the form does not.** A degenerated `g` still dives below
the line; a degenerated `l` still throws a loop above it.

So a mark here has a head that is letters and a tail that is a running wave,
`head_and_tail` decides where the hand let go, and `_scrawl` builds the wave out
of the *classes* of the letters it replaces rather than out of noise. That is
what keeps two different names from collapsing into the same squiggle.

## The limit, said first

**With `font`**, the strokes are a typeface's strokes. This makes a
**signature-shaped mark**:
the right size, slant, baseline, connection and flourish for a signature, drawn
with a typeface's contours. That is enough to be furniture on a form -- ink a
reader must not mistake for text, sitting where a signature sits -- and it is
what `docs/hoa-tiet-de-xuat.md` asks for. It is **not** a specimen of any
person's signature, and a set built from it is not a signature-verification
corpus: two marks from one seed are identical, and the two faces are two
faces, not 106 writers. Same trade as `FontHand`, written down the same way.

**With `model`**, the strokes are generated rather than set, and that limit
lifts: the ink is a hand's, it is thin and joined up, and 106 writer styles
are not two. What replaces it is narrower and is `docs/writevit.md`'s subject
-- no digits, no ALL-CAPS, no punctuation -- and it shows up here as a
**narrower style range**: a signature in model ink is a name or a given name,
never a monogram, because a monogram is a run of capitals. Plus the cost,
which is a 1.7 GB clone and seconds a word. Still not a corpus for signature
verification: one seed is still one mark.

## What the survey established

Searched before any of this was written; `docs/chu-ky.md` keeps the sources.
Every number below is traceable to one of these, and the ones that are a
judgement rather than a measurement say so where they are defined.

    zones        an enlarged initial, a simplified body, a lifted terminal
    slant        forward, and further forward than the same hand's writing
    baseline     rising far more often than level, falling rarely
    aspect       1.8:1 to 3:1 wide -- the boxes the reference corpora capture in
    paraph       an underline or flourish that is part of the mark, not a letter
    legibility   the given name survives; the rest degenerates or is dropped
    movement     it outlives the form: a dead `g` still dives, a dead `l` loops
    connection   letters run together, and the ligature is a stroke of its own

## The shape of the code

    geometry     cubic contours and warps -- pure Python, no dependency at all
    Ink          letter outlines out of a .ttf; the one part that needs fontTools
    trace        a raster of ink -> contours; the one part that needs OpenCV
    ModelInk     WriteViT's words, traced and put on a baseline
    Style        one signer's parameters, drawn from a seed
    Signer.sign  stretch, place, connect, scrawl, warp, flourish, paraph, slant

`fontTools` is imported inside `Ink` and nowhere else, for the reason
`handwriting.py` gives for its own local imports: the geometry is a pure
function of numbers, and CI runs the suite on pytest and PyYAML alone. Every
warp in this file can be tested without a font on disk.
"""

from __future__ import annotations

import html
import math
import random
import re
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HAND_FONT_DIR = REPO_ROOT / "fonts" / "hand"

# The same two faces `handwriting.py` sets its text in, named here rather than
# imported so this module stands alone -- it has no other reason to pull in the
# WriteViT policy. `handwriting.FACES` carries a third field, the CSS size
# multiplier, which means nothing to an outline: here a face is a file.
FACES = ("PatrickHand-Regular.ttf", "IndieFlower-Regular.ttf")

# One default pen, the commonest entry in `handwriting.PENS`. `fill` draws from
# that table properly, by local import; this literal is only so that `svg()`
# and the CLI have a colour without reaching into another module's policy.
PEN = "#1c2a68"


# ---------------------------------------------------------------- geometry
#
# One representation throughout. A contour is a closed cubic polybezier held as
# 3n+1 points -- on, c1, c2, on, c1, c2, ... on -- whose last point repeats its
# first; a path is a list of contours. Straight lines are stored as cubics with
# colinear controls, which is exact, and which means every warp below is a
# single function over points instead of a switch over segment kinds.
#
# Units are x-heights with the baseline at y = 0 and **y pointing up**, as font
# units do and as `handwriting.extent` already reckons in. SVG's y points down;
# `svg()` flips once, at the end, and nothing before it has to think about it.

Point = "tuple[float, float]"


def line_controls(p0, p1):
    """The two controls that make a cubic segment draw the straight p0->p1."""
    return ((p0[0] + (p1[0] - p0[0]) / 3.0, p0[1] + (p1[1] - p0[1]) / 3.0),
            (p0[0] + 2.0 * (p1[0] - p0[0]) / 3.0, p0[1] + 2.0 * (p1[1] - p0[1]) / 3.0))


def polyline(points: list) -> list:
    """A closed contour through `points` in straight segments."""
    out = [points[0]]
    for index in range(1, len(points)):
        c1, c2 = line_controls(points[index - 1], points[index])
        out += [c1, c2, points[index]]
    if points[-1] != points[0]:
        c1, c2 = line_controls(points[-1], points[0])
        out += [c1, c2, points[0]]
    return out


def mapped(path: list, fn) -> list:
    """`fn` applied to every point of every contour, controls included.

    Applying a warp to control points rather than to the curve is an
    approximation, and it is a good one exactly when the segments are short
    relative to the warp -- which is what `subdivided` is for. Every non-linear
    warp in this file subdivides first; the affine ones do not need to, because
    an affine map of the controls *is* the affine map of the curve.
    """
    return [[fn(point) for point in contour] for contour in path]


def bounds(path: list):
    """`(x0, y0, x1, y1)` over the control points.

    The control hull, not the curve: it can be a shade wider than the ink where
    a curve bulges inward. Every use here wants a box to place something
    against, and erring outward is the safe direction for that.
    """
    xs = [point[0] for contour in path for point in contour]
    ys = [point[1] for contour in path for point in contour]
    if not xs:
        return (0.0, 0.0, 0.0, 0.0)
    return (min(xs), min(ys), max(xs), max(ys))


def affine(sx: float = 1.0, sy: float = 1.0, shear: float = 0.0,
           dx: float = 0.0, dy: float = 0.0, pivot: float = 0.0):
    """Scale, then shear about `y = pivot`, then translate.

    `shear` is the tangent of the slant, so 0.27 is 15 degrees off vertical --
    the unit the survey's slant range is written in below.
    """
    def fn(point):
        x, y = point[0] * sx, point[1] * sy
        return (x + shear * (y - pivot) + dx, y + dy)
    return fn


def at(seg, t: float):
    """A point on one cubic segment `(p0, c1, c2, p1)`."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg
    u = 1.0 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (a * x0 + b * x1 + c * x2 + d * x3, a * y0 + b * y1 + c * y2 + d * y3)


def tangent(seg, t: float):
    """The unit tangent at `t`, or `(1, 0)` where the derivative vanishes."""
    (x0, y0), (x1, y1), (x2, y2), (x3, y3) = seg
    u = 1.0 - t
    a, b, c = 3 * u * u, 6 * u * t, 3 * t * t
    dx = a * (x1 - x0) + b * (x2 - x1) + c * (x3 - x2)
    dy = a * (y1 - y0) + b * (y2 - y1) + c * (y3 - y2)
    length = math.hypot(dx, dy)
    return (dx / length, dy / length) if length > 1e-9 else (1.0, 0.0)


def _split(seg):
    """de Casteljau at t = 0.5: one cubic segment as two."""
    (p0, p1, p2, p3) = seg
    mid = lambda a, b: ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)  # noqa: E731
    a, b, c = mid(p0, p1), mid(p1, p2), mid(p2, p3)
    d, e = mid(a, b), mid(b, c)
    f = mid(d, e)
    return (p0, a, d, f), (f, e, c, p3)


def subdivided(path: list, step: float = 0.12) -> list:
    """Every segment split until its control hull is shorter than `step`.

    The price of warping control points instead of curves, paid up front. 0.12
    x-heights is about a twelfth of a lowercase letter, which is finer than the
    warps here bend by an order of magnitude.
    """
    out = []
    for contour in path:
        points = [contour[0]]
        for index in range(0, len(contour) - 1, 3):
            todo = [tuple(contour[index:index + 4])]
            while todo:
                seg = todo.pop()
                hull = sum(math.dist(seg[i], seg[i + 1]) for i in range(3))
                if hull > step and len(points) < 20000:
                    first, second = _split(seg)
                    todo += [second, first]
                else:
                    points += [seg[1], seg[2], seg[3]]
        out.append(points)
    return out


def d(path: list, precision: int = 3) -> str:
    """The path as an SVG `d`. Contours are closed; that is the only kind here."""
    fmt = "%%.%df" % precision
    out = []
    for contour in path:
        if len(contour) < 4:
            continue
        pen = [f"M{fmt % contour[0][0]},{fmt % contour[0][1]}"]
        for index in range(1, len(contour) - 1, 3):
            c1, c2, end = contour[index], contour[index + 1], contour[index + 2]
            pen.append("C%s,%s %s,%s %s,%s" % (
                fmt % c1[0], fmt % c1[1], fmt % c2[0], fmt % c2[1],
                fmt % end[0], fmt % end[1]))
        out.append("".join(pen) + "Z")
    return "".join(out)


# ------------------------------------------------------------------- warps
#
# The four that the survey's findings turn into. Each is a factory returning a
# point function for `mapped`, and each is written so that identity parameters
# (`rise = arch = 0`, `k = 0`) return the identity map -- a style that draws a
# level baseline should produce exactly the unwarped ink, not a rounding of it.


def bow(x0: float, x1: float, rise: float, arch: float = 0.0):
    """The baseline: `rise` lifts the right-hand end, `arch` bellies it.

    Both in x-heights over the mark's own width, which is why they are drawn
    per signer as ratios and turned into a warp only once the width is known.
    A rising baseline is the commonest signature pattern in the survey and a
    falling one the rarest; `Style` weights them accordingly.
    """
    span = max(x1 - x0, 1e-6)

    def fn(point):
        u = (point[0] - x0) / span
        return (point[0], point[1] + rise * u + arch * math.sin(math.pi * u))
    return fn


def fade(x0: float, x1: float, k: float, base: float = 0.0):
    """Letters shrinking toward the end: vertical scale `1 -> 1 - k` about `base`.

    The survey's "simplification is a continuous process" and "letters
    degenerate toward the end" as one number. Kept under 1 so it is a squeeze
    and never a flip.
    """
    span = max(x1 - x0, 1e-6)

    def fn(point):
        u = min(max((point[0] - x0) / span, 0.0), 1.0)
        return (point[0], base + (point[1] - base) * (1.0 - k * u))
    return fn


def swell(x0: float, x1: float, k: float):
    """Progressive horizontal stretch, `k > -0.5` to stay monotone.

    x' = x0 + L(u + k u^2). Positive opens the letters out toward the end of
    the mark, negative crowds them -- the two ways a signature's spacing
    actually drifts, depending on whether the hand is finishing or running out
    of box.
    """
    span = max(x1 - x0, 1e-6)

    def fn(point):
        u = (point[0] - x0) / span
        return (x0 + span * (u + k * u * u), point[1])
    return fn


def ribbon(spine, w0: float, w1: float, *, bulge: float = 0.0,
           samples: int = 26) -> list:
    """A tapered stroke along a cubic `spine`, as one closed contour.

    The marks a signature has that letters do not -- the ligature between two
    letters, the terminal sweep, the paraph, and the scrawl the body collapses
    into -- are strokes, not outlines, and this is what turns a centreline into
    ink. Width runs `w0 -> w1` with `bulge` fattening the middle, which is the
    pointed-nib behaviour the calligraphy sources describe: thin on the entry,
    full through the pull, thin again at the lift.

    The spine is a polybezier of 3n+1 points like everything else here, so a
    four-point spine is the one-segment case and a running scrawl is the same
    call with more points. `samples` is **per segment**, so a longer stroke is
    not sampled more coarsely than a short one.
    """
    count = max((len(spine) - 1) // 3, 1)
    steps = samples * count
    left, right = [], []
    for index in range(steps + 1):
        t = index / steps
        which = min(int(t * count), count - 1)
        seg = tuple(spine[which * 3:which * 3 + 4])
        local = t * count - which
        x, y = at(seg, local)
        tx, ty = tangent(seg, local)
        width = (w0 + (w1 - w0) * t + bulge * math.sin(math.pi * t)) / 2.0
        width = max(width, 1e-4)
        left.append((x - ty * width, y + tx * width))
        right.append((x + ty * width, y - tx * width))
    return polyline(left + right[::-1])


# --------------------------------------------------------------------- Ink


class Ink:
    """Letter outlines from one handwriting face, in x-heights, baseline at 0.

    The only class here that needs `fontTools`, and it needs it for one thing:
    a `.ttf` stores contours and this file wants contours. Everything the
    engine does to them afterwards is arithmetic.
    """

    def __init__(self, filename: str = FACES[0], directory: Path = HAND_FONT_DIR):
        self.path = Path(directory) / filename
        self.name = filename
        self._font = None
        self._glyphs = None
        self._cmap = None
        self._unit = 1.0
        self._cache: dict = {}

    def open(self) -> "Ink":
        # The file first, the library second. A missing face is a setup
        # mistake with a one-line fix and should say so; reaching for
        # fontTools first would report the wrong missing thing on a machine
        # that has neither.
        if not self.path.exists():
            raise FileNotFoundError(
                f"no handwriting face at {self.path} -- see fonts/README.md")

        from fontTools.ttLib import TTFont  # noqa: PLC0415 -- see the docstring

        self._font = TTFont(self.path, fontNumber=0, lazy=True)
        self._glyphs = self._font.getGlyphSet()
        self._cmap = self._font.getBestCmap()
        self._unit = self._x_height()
        return self

    def __enter__(self) -> "Ink":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def close(self) -> None:
        if self._font is not None:
            self._font.close()
            self._font = None

    def _x_height(self) -> float:
        """Font units per x-height, measured off `x` rather than trusted to OS/2.

        `sxHeight` is optional and is zero in more shipped faces than one would
        like; a wrong unit here would scale every signature on the page wrong
        and look like a style choice rather than a bug. The letter is right
        there and has no ascender, so measuring it is both cheaper and surer.
        """
        for candidate in ("x", "o", "n"):
            outline, _advance = self._raw(candidate)
            if outline:
                _x0, y0, _x1, y1 = bounds(outline)
                if y1 - y0 > 1:
                    return y1 - y0
        return float(self._font["head"].unitsPerEm) / 2.0

    def has(self, char: str) -> bool:
        return self._cmap is not None and ord(char) in self._cmap

    def _raw(self, char: str):
        """Contours and advance in font units, or `([], 0)` for a missing glyph."""
        if ord(char) not in self._cmap:
            return ([], 0.0)
        name = self._cmap[ord(char)]
        pen = _ContourPen(self._glyphs)
        self._glyphs[name].draw(pen)
        return (pen.path, float(self._font["hmtx"][name][0]))

    def outline(self, char: str):
        """`(path, advance)` in x-heights, baseline at y = 0, y up.

        Composites are decomposed by the glyph set, so `ề` arrives as one path
        of four contours and its marks stretch with the letter they sit on --
        which is the whole reason to read outlines rather than raster a word.
        """
        if char not in self._cache:
            outline, advance = self._raw(char)
            scale = 1.0 / max(self._unit, 1e-6)
            self._cache[char] = (mapped(outline, affine(scale, scale)),
                                 advance * scale)
        return self._cache[char]

    # A print capital is stretched into a signature initial; see `_letters`.
    stretches_initial = True
    # A typeface draws every style in the survey; nothing to restrict.
    legibility = None

    def normalise(self, text: str) -> str:
        """A face draws whatever it has a glyph for; `units` skips the rest."""
        return text

    def units(self, text: str):
        """`(path, advance, char)` per drawable unit -- for a font, per letter.

        A space is not a unit: it is an advance with no ink, and it comes back
        as an empty path so `_letters` moves the pen without setting anything
        down. A character the face has no glyph for is skipped entirely, which
        is `FontHand`'s rule too.
        """
        for char in text:
            if char.isspace():
                yield ([], 0.42, char)         # a word gap, in x-heights
            elif self.has(char):
                path, advance = self.outline(char)
                yield (path, advance, char)

    def stem(self) -> float:
        """The face's stroke width in x-heights, measured off its own `l`.

        A connector or a flourish drawn at some invented width reads as a
        second pen; drawn at the face's own it reads as the same one. `l` is a
        bare stem in both shipped faces, so the width of its ink is the width
        of its stroke.
        """
        for candidate in ("l", "i", "t"):
            outline, _advance = self.outline(candidate)
            if outline:
                x0, _y0, x1, _y1 = bounds(outline)
                if 0.02 < x1 - x0 < 0.5:
                    return x1 - x0
        return 0.11


def _ContourPen(glyphset):
    """A pen that records cubic contours, one list of 3n+1 points each.

    A factory rather than a class statement, because the base class lives in
    fontTools and a `class _ContourPen(BasePen)` at module level would import
    it at module load -- which is the one thing the docstring at the top says
    this file does not do. The class is built once and cached on the function.

    `BasePen` is what makes the body short: it decomposes components, converts
    TrueType quadratics to cubics and normalises multi-point curves, leaving
    three methods to write.
    """
    from fontTools.pens.basePen import BasePen  # noqa: PLC0415

    made = getattr(_ContourPen, "_class", None)
    if made is None:
        made = type("ContourPen", (_ContourPenBody, BasePen), {})
        _ContourPen._class = made
    return made(glyphset)


# --------------------------------------------------------------- ModelInk


# Turning a raster of ink into contours. Tuned against WriteViT's own output at
# `--scale 4`, which is black-on-white, anti-aliased, and thin: a wider blur or
# a lower level closes the counter of a `g` into a blob, which is exactly what
# the first attempt did.
TRACE_BLUR = 0.6                 # sigma, in source pixels: kills the pixel grid
TRACE_LEVEL = 140                # of 255, on the inverted image
TRACE_SMOOTH = 2                 # moving-average half-width over the outline
TRACE_MIN_AREA = 4.0             # source px^2; below this it is a stray speck

# What the tile is enlarged by before it is traced, and it is not optional.
# `Hand._ask` hands back the model's **native 32 px**, where a stroke is one or
# two pixels across -- `findContours` returns nothing that survives the length
# and area filters above, so an un-enlarged tile traces to an empty path and the
# letter silently disappears. It did: the initial vanished, the "initial" role
# fell through to the rest of the word, and the vertical cap stretch turned a
# whole word into a blade. Six is enough for a 1 px stroke to become a shape
# with an inside.
TRACE_ZOOM = 6


def trace(image, *, blur: float = TRACE_BLUR, level: int = TRACE_LEVEL,
          smooth: int = TRACE_SMOOTH, min_area: float = TRACE_MIN_AREA) -> list:
    """A grayscale image of ink -> contours, in source pixels with y up.

    The seam that lets a generated raster into a vector engine. Everything
    `signature.py` does -- stretch, slant, bow, terminal, paraph -- is arithmetic
    on control points, so ink that arrives as pixels has to become points once,
    here, and then it is indistinguishable from a glyph downstream.

    Three details, each of which was a visible failure before it was a rule:

    * **Blur before threshold, and only a little.** The raster is anti-aliased,
      so a bare threshold leaves a pixel staircase on every stroke edge. 0.6
      sigma smooths that; 1.2 fattens the ink and seals the loop of a `g`.
    * **Winding by signed area, not by the library's convention.** An outer
      contour and its holes must wind opposite ways or `fill-rule:nonzero`
      fills the counter of an `o` solid -- which is what happened when this
      trusted `findContours` to return them already opposed and then reversed
      them again.
    * **y is negated.** OpenCV's rows go down, this file's y goes up.

    numpy and OpenCV are imported here and nowhere else in this module, for the
    reason the module docstring gives: the geometry is a pure function of
    numbers and CI runs the suite without either.
    """
    import cv2  # noqa: PLC0415 -- the renderer's environment, not the test one
    import numpy as np  # noqa: PLC0415

    grey = np.asarray(image.convert("L"), dtype=np.uint8)
    ink = 255 - grey
    if blur:
        ink = cv2.GaussianBlur(ink, (0, 0), blur)
    _level, mask = cv2.threshold(ink, level, 255, cv2.THRESH_BINARY)
    found, hierarchy = cv2.findContours(mask, cv2.RETR_CCOMP,
                                        cv2.CHAIN_APPROX_NONE)
    out = []
    for index, contour in enumerate(found):
        if len(contour) < 12 or cv2.contourArea(contour) < min_area:
            continue
        points = contour[:, 0, :].astype(float)
        if smooth:
            # Periodic, because an outline is a loop: averaging a closed ring
            # with its ends padded from the other end keeps the join smooth.
            window = np.ones(smooth * 2 + 1) / (smooth * 2 + 1)
            pad = smooth * 2
            wide = np.vstack([points[-pad:], points, points[:pad]])
            points = np.stack([np.convolve(wide[:, 0], window, "same"),
                               np.convolve(wide[:, 1], window, "same")],
                              axis=1)[pad:-pad]
        points = points[::2]                   # one point per two source px
        if len(points) < 4:
            continue
        area = 0.5 * float(np.sum(points[:, 0] * np.roll(points[:, 1], -1)
                                  - np.roll(points[:, 0], -1) * points[:, 1]))
        hole = hierarchy[0][index][3] != -1
        if (area > 0) != hole:
            points = points[::-1]
        out.append(polyline([(float(x), float(-y)) for x, y in points]))
    return out


class ModelInk:
    """Ink from the WriteViT checkpoint, traced into contours.

    The other ink source, and the one that answers the honest limit `Ink` is
    stuck with. A typeface repeats: every `a` is the same `a`, and the stroke
    shapes are a typeface's however hard they are stretched. WriteViT generates
    a word at a time from one of 106 writer styles, and what comes back is thin,
    joined-up and different every time -- which is what a signature is made of.

    It writes **words**, not letters, and that is the point twice over. The
    joins inside "Tuấn" are the model's, not this file's -- and asking it for
    the letters separately is measurably worse output, not merely a lost join:
    `T` and `uan` fetched apart come back as a stiff `T` and a good `uan`,
    while `Tuan` in one call comes back as one connected hand. So a unit here
    is a whole word, and the enlarged initial that `Ink` gets by stretching is
    something the model has already written.

    What it cannot do is `docs/writevit.md`'s subject and is not small: no
    digits, no ALL-CAPS, no punctuation. For a signature that matters far less
    than it does for a form field -- a signature is a name -- but a monogram of
    three capitals is a run of capitals, so `writable` refuses those and the
    caller falls back rather than getting a row of wrong letters.
    """

    source = "model"
    # A unit is a word, so the head has to be one too -- see `head_and_tail`.
    writes_words = True
    # The two of the survey's four legibility styles this ink can draw. The
    # other two -- `monogram`, `initials` -- are runs of capitals by
    # definition, and `docs/writevit.md` measures that a run of capitals is
    # exactly what the checkpoint cannot write. Declared here so `Style` picks
    # from what is drawable rather than being refused afterwards.
    legibility = ("given", "full")
    # The model's capitals are already cursive signature capitals. Stretching
    # one vertically turns a whole word into a blade -- which is what the first
    # version of this did, having also lost the initial to an empty trace.
    stretches_initial = False

    def __init__(self, writer: int = 0, seed: int = 0, hand=None,
                 writevit_dir=None):
        self.writer = writer
        self.seed = seed
        self._hand = hand
        self._owned = hand is None
        self._dir = writevit_dir
        self._cache: dict = {}
        self._stem = 0.0

    def __enter__(self) -> "ModelInk":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> "ModelInk":
        if self._hand is None:
            import handwriting  # noqa: PLC0415 -- the worker lives there

            self._hand = handwriting.Hand(writevit_dir=self._dir).open()
        return self

    def close(self) -> None:
        if self._owned and self._hand is not None:
            self._hand.close()
            self._hand = None

    # -- what it can write -------------------------------------------------

    def has(self, char: str) -> bool:
        import handwriting  # noqa: PLC0415

        return char in handwriting.ALPHABET_SET

    def normalise(self, text: str) -> str:
        """Punctuation dropped rather than the whole name refused.

        `O'Donnell` is one name in the corpus and the apostrophe is outside the
        checkpoint's alphabet, so the mark used to fall back to the typeface
        over one character. Nobody writes the apostrophe when they sign
        `O'Donnell` anyway -- a signature is a gesture, not a spelling -- so
        the character goes and the name stays. What was actually drawn is in
        `Mark.drawn`, beside the name it came from, so the label still says.

        It becomes a **space**, not nothing. Deleted, `O'Donnell` closes up
        into `ODonnell`, whose `OD` is a run of capitals the checkpoint cannot
        write either -- a refusal manufactured by the repair. The apostrophe
        was a break in the name and it stays one.
        """
        import handwriting  # noqa: PLC0415

        kept = "".join(char if char in handwriting.ALPHABET_SET or char.isspace()
                       else " " for char in text)
        kept = " ".join(kept.split())
        return kept if kept.strip() else text

    def writable(self, text: str) -> bool:
        """What the checkpoint can actually write, not merely spell.

        `handwriting.writable` checks the alphabet, which is necessary and not
        sufficient. `docs/writevit.md` measures the rest: **a leading capital
        is fine and a run of them is not** -- `Nguyễn`, `Địa`, `Một` come back
        correct while `HOA DON GIA TRI` comes back as `Hai Đồng Giữ Tư`, and
        the cause is in the training code rather than in the sampling, so it
        does not go away with another seed.

        Two capitals in a row is where it starts. That refuses exactly the
        monogram and initials styles, which is the right place to lose them:
        those are runs of capitals by definition, and `fill` hands them to the
        font, which draws capitals well and has no cursive joins to lose.
        """
        import handwriting  # noqa: PLC0415

        if not handwriting.writable(text):
            return False
        run = 0
        for char in text:
            run = run + 1 if char.isupper() else 0
            if run >= 2:
                return False
        return True

    # -- what it draws -----------------------------------------------------

    def units(self, text: str):
        """One unit per word, which is the unit the model actually writes in.

        Not per letter, and the reason is worth keeping: fetched apart, `T` and
        `uan` come back as a stiff isolated `T` and a good `uan`; fetched
        together, `Tuan` comes back as one connected hand with a proper
        signature capital on the front. The model is trained on words and it
        shows. Every join inside a unit is therefore the model's own, and this
        file adds joins only *between* units.
        """
        words = [part for part in text.split() if part]
        if not words:
            return
        for index, (word, tile) in enumerate(zip(words, self._tiles(words))):
            path, advance = self._normalise(word, tile)
            if index:
                advance += 0.28              # a word gap, in x-heights
            yield (path, advance, word[0])

    def _tiles(self, words: list):
        wanted = [word for word in words if word not in self._cache]
        if wanted:
            fresh = self._hand._ask(wanted, self.writer, self.seed)
            for word, tile in zip(wanted, fresh):
                self._cache[word] = tile
        return [self._cache[word] for word in words]

    def _normalise(self, word: str, tile):
        """One tile -> contours in x-heights, baseline at y = 0.

        The generator emits every word the same height and crops tight, so
        **there is no baseline in the image to read back** -- `handwriting.py`
        says so at length and works one out from the letters instead. The same
        model is used here: `extent` says how far this word reaches above and
        below the x-height band, so the tile's pixel height divides into
        `above + 1 + below` and the baseline sits `below` of them up from the
        bottom. Being a model it is approximate, but it is approximate in the
        same direction for every word, which is all that is needed to put them
        on one line.
        """
        import handwriting  # noqa: PLC0415

        raw = trace(self._zoom(tile))
        if not raw:
            return ([], 0.0)
        above, below = handwriting.extent(word)
        x0, y0, x1, y1 = bounds(raw)
        unit = max((y1 - y0) / (above + handwriting.X_HEIGHT + below), 1e-6)
        scale = 1.0 / unit
        placed = mapped(raw, affine(scale, scale, dx=-x0 * scale,
                                    dy=-(y0 + below * unit) * scale))
        if not self._stem:
            # The pen this hand writes with, in x-heights. Taken as twice the
            # median distance from the ink to its own edge -- a distance
            # transform is the one measurement that gives a stroke width from a
            # shape with no stems to look up, which is every word here.
            self._stem = self._measure(self._zoom(tile)) / unit
        return (placed, (bounds(placed)[2] - bounds(placed)[0]) + 0.14)

    @staticmethod
    def _zoom(tile, factor: int = TRACE_ZOOM):
        """The tile enlarged, smoothly, before anything measures it.

        LANCZOS rather than nearest: the point is to turn a two-pixel stroke
        into a smooth shape with an inside, and a nearest-neighbour blow-up
        would only make the staircase bigger.
        """
        from PIL import Image  # noqa: PLC0415

        return tile.resize((tile.width * factor, tile.height * factor),
                           Image.LANCZOS)

    @staticmethod
    def _measure(tile) -> float:
        import cv2  # noqa: PLC0415
        import numpy as np  # noqa: PLC0415

        grey = np.asarray(tile.convert("L"), dtype=np.uint8)
        mask = (255 - grey > TRACE_LEVEL).astype(np.uint8)
        if not mask.any():
            return 1.0
        distance = cv2.distanceTransform(mask, cv2.DIST_L2, 3)
        return 2.0 * float(np.median(distance[distance > 0]))

    def stem(self) -> float:
        """The width the model's own pen draws at, so the marks that are not
        letters -- ligature, terminal, paraph -- are drawn with the same pen."""
        return self._stem or 0.09


class _ContourPenBody:
    def __init__(self, glyphset):
        super().__init__(glyphset)
        self.path: list = []
        self._points: list = []

    def _moveTo(self, pt) -> None:
        self._flush()
        self._points = [pt]

    def _lineTo(self, pt) -> None:
        if not self._points:
            self._points = [pt]
            return
        c1, c2 = line_controls(self._points[-1], pt)
        self._points += [c1, c2, pt]

    def _curveToOne(self, c1, c2, pt) -> None:
        if not self._points:
            self._points = [c1]
        self._points += [c1, c2, pt]

    def _closePath(self) -> None:
        self._flush()

    def _endPath(self) -> None:
        self._flush()

    def _flush(self) -> None:
        points = self._points
        self._points = []
        if len(points) < 4:
            return
        if points[-1] != points[0]:
            c1, c2 = line_controls(points[-1], points[0])
            points += [c1, c2, points[0]]
        self.path.append(points)


# ------------------------------------------------------------------- style
#
# One signer, drawn from a seed. Every field cites the finding it comes from;
# where a range is a judgement rather than something the survey measured, it
# says so, because a number nobody can trace is a number nobody can argue with.

# How much of the name reaches the paper. The survey: an illegible or reduced
# signature is normal, and commonest in people who sign many times a day --
# which is who signs the documents this repository generates. `given` is the
# Vietnamese pattern the signature guides teach (the last word of the name,
# with its initial pulled out); `monogram` is initials alone. WEIGHTS ARE A
# JUDGEMENT: the survey establishes that all four occur and that full
# legibility is the minority, not how the four divide.
LEGIBILITY = (("given", 5), ("initials", 4), ("full", 3), ("monogram", 2))

# The baseline of the mark. Rising is the pattern every source names first --
# "nét kết thúc được nâng lên", the lift that signifies going forward -- and
# falling is named as the uncommon one. Weights, again, are a judgement over an
# ordering the survey does give.
BASELINE = (("rising", 5), ("level", 3), ("wavy", 2), ("falling", 1))

# The mark that is not a letter. The survey calls it a paraph and describes it
# as part of the signature rather than decoration on it.
PARAPH = (("underline", 4), ("swash", 4), ("none", 3), ("loop", 2), ("double", 1))

# Forward slant as a tangent: 0.09 is 5 degrees off vertical, 0.47 is 25. The
# graphology sources put ordinary writing at 60-75 degrees from the horizontal
# (15-30 off vertical) and the calligraphy sources put a formal script's oval
# at 55 degrees (35 off); a signature runs at the fast end of its own writer's
# range, so the band here is wide and its mass sits forward.
SLANT = (0.09, 0.47)

# The initial, in x-heights, against a body of 1. "Chữ ký bắt đầu với nét chữ
# lớn" -- the enlarged capital is the single most consistent structural feature
# in the survey, and 1.35-2.4 is the range read off the sample sheets rather
# than a measured distribution.
CAP_STRETCH = (1.35, 2.40)

# What the body does under speed: narrower than it is tall, and shorter as the
# hand runs on. Both are the survey's "simplification" as geometry.
BODY_SQUEEZE = (0.40, 0.88)      # horizontal scale on the letters after the first
BODY_FADE = (0.04, 0.40)         # vertical squeeze accumulated across the mark

# Connection. A ligature is a stroke in its own right in the survey's account,
# so `overlap` pulls the letters together and the connector is drawn between
# them; a signature that is not connected simply has neither.
OVERLAP = (0.05, 0.32)           # of an advance, taken back between letters
CONNECTED = 0.72                 # of signers; the rest print their mark

# ---- how much of the name stays letters at all ----------------------------
#
# The correction that mattered most. Squeezing a letter and fading it leaves it
# a letter: the first pass at this engine produced marks reading `Nguyễn Thị
# Bích Ngọc` in a slightly slanted hand, and a signature that can be read like
# that is not what comes back on a form. The survey does say what happens
# instead, and says it in several voices: the body is *simplified or
# abandoned*, an illegible signature is normal and commonest in people who sign
# many times a day, and -- the useful part -- **the movement survives when the
# form does not**. A degenerated `g` still dives below the line; a degenerated
# `l` still throws a loop above it. The letters stop being letters and go on
# being the same gesture.
#
# So a signature here has a head that is letters and a tail that is a running
# scrawl, and `_scrawl` builds the tail out of the *classes* of the letters it
# replaces rather than out of noise.
SCRAWL = 0.90                    # of signers whose body degenerates at all
SURVIVES = (1, 2)                # letters that keep their shape before it does
SCRAWL_SLOTS = 6                 # most humps a hand will actually put down
SCRAWL_STEP = (0.54, 0.95)       # x-heights of travel per slot
SCRAWL_DECAY = (0.15, 0.55)      # how far the wave has shrunk by the end

# The fewest letters a word-writing source is asked for. Read off the output,
# not off the survey: below three the model's tile is a fragment rather than a
# hand, and the mark reads as a wave with a smudge in front of it.
HEAD_LETTERS = 3

# The terminal. `reach` is how far past the last letter it travels and `rise`
# how far it lifts, both in x-heights. This is the "nét kết thúc được nâng
# lên" of the Vietnamese guides and the "emphasising line after signatures" of
# the forensic ones.
FLOURISH = 0.80                  # of signers draw one at all
REACH = (0.9, 3.2)
RISE = (0.3, 1.8)

# The other half of the same finding: the run-up into the initial. Rarer than a
# terminal, because a hand can start on the letter but has to leave it somehow.
LEAD = 0.45

# Which letters reach above the x-height band and which hang below it. The same
# two classes `handwriting.extent` reckons with, restated here rather than
# imported for the reason that module restates its own alphabet: reading them
# across would pull a renderer's policy in to answer a question about a string.
# `_scrawl` needs them because a letter that has degenerated keeps its
# direction -- that is the whole idea it is built on.
TALL_LETTERS = frozenset("bdhklt")
TAIL_LETTERS = frozenset("gjpqy")

# The capture aspect the reference corpora use -- GPDS boxes 5x1.8 cm and
# 4.5x2.5 cm, so 1.8:1 to 2.8:1 -- rounded out to 3. Nothing is forced into it;
# `Mark.aspect` reports where the mark landed so a caller can see when the
# style choices have wandered outside what a signature box holds.
ASPECT = (1.8, 3.0)


class Style:
    """One signer's parameters. Drawn once, then fixed: a person signs one way.

    Held as a plain object rather than a dict so `report()` can decide what
    belongs in a dataset's label, which is not the same as what the engine
    needs -- the label wants the categories, not the eleven floats.
    """

    def __init__(self, seed: int):
        rng = random.Random(seed ^ 0x5349474E)   # 'SIGN'
        self.seed = seed
        self.face = FACES[rng.randrange(len(FACES))]
        self.legibility = _weighted(rng, LEGIBILITY)
        self.baseline = _weighted(rng, BASELINE)
        self.paraph = _weighted(rng, PARAPH)
        self.slant = rng.uniform(*SLANT)
        self.cap = rng.uniform(*CAP_STRETCH)
        self.squeeze = rng.uniform(*BODY_SQUEEZE)
        self.body_fade = rng.uniform(*BODY_FADE)
        self.overlap = rng.uniform(*OVERLAP)
        self.connected = rng.random() < CONNECTED
        self.flourish = rng.random() < FLOURISH
        self.reach = rng.uniform(*REACH)
        self.rise = rng.uniform(*RISE)
        self.lead = rng.random() < LEAD
        self.lead_at = rng.uniform(0.35, 0.85)   # where on the initial it lands
        # Spacing drift across the mark: opening out or crowding in, equally
        # often. Bounded well inside `swell`'s monotonicity limit of -0.5.
        self.swell = rng.uniform(-0.22, 0.22)
        # Marks (dấu) survive or are dropped. The survey's simplification
        # finding covers "the diacritic is the first thing a fast hand loses";
        # THE SPLIT IS A JUDGEMENT, not a count.
        # Marks are dropped far more often than they are kept: a hand moving
        # fast enough to abandon the letters is not going back for the dấu.
        self.marks = rng.random() < 0.20
        self.scrawl = rng.random() < SCRAWL
        self.survives = rng.randint(*SURVIVES)
        self.step = rng.uniform(*SCRAWL_STEP)
        self.decay = rng.uniform(*SCRAWL_DECAY)
        self.bow = _bow(rng, self.baseline)
        # One number per slot of the scrawl, drawn here for the reason `wobble`
        # is: a mark is a pure function of `(seed, name)`, and a draw taken
        # while the wave is being laid down would break that.
        self.pulse = tuple(rng.random() for _ in range(SCRAWL_SLOTS * 2))
        # The paraph's own wobble, drawn HERE rather than while it is being
        # laid down. Everything a signer is has to be settled by the end of
        # this constructor: a mark is a pure function of `(seed, name)`, and it
        # stops being one the moment `sign()` touches the generator -- signing
        # two names would advance it and the second underline would sag
        # differently from the first for no reason a dataset could explain.
        self.wobble = tuple(rng.uniform(-1.0, 1.0) for _ in range(6))
        # Which of WriteViT's 106 writer styles signs, when the ink comes from
        # the model. Drawn **last**, and the position is load-bearing: every
        # draw above it has to keep the stream position it already had, or
        # adding a second ink source silently restyles every signature the
        # first one had already produced. It did -- put in one line higher, it
        # moved `wobble` and shifted the paraph jitter on half the sample grid.
        self.writer = rng.randrange(106)

    @property
    def rng(self) -> random.Random:
        raise AttributeError(
            "Style draws everything in __init__ on purpose -- see `wobble`. "
            "Add a field there rather than a draw at sign time.")

    def restrict(self, allowed) -> None:
        """Re-pick the legibility from what the ink can actually draw.

        The order used to be the wrong way round: a style was drawn, and only
        then was the ink asked whether it could write it. With the model that
        refused eleven of eighteen seeds -- `monogram` and `initials` build
        runs of capitals, and the checkpoint has none -- so most marks came
        back in the other ink and a run asking for model ink got mostly
        typeface.

        Choosing from what the source can draw is not the same as hiding the
        limit, and the limit is not smaller for being moved: **the model
        cannot make a monogram at all**, so a set signed with it has no
        monograms in it. That is a real narrowing of the style range and
        `docs/chu-ky.md` says so. What it is not is a signature drawn in the
        wrong ink.

        Drawn from its own stream off the seed, so restricting disturbs no
        other field and a signer is still a pure function of `(seed, source)`.
        """
        if not allowed or self.legibility in allowed:
            return
        table = [(name, weight) for name, weight in LEGIBILITY if name in allowed]
        if not table:
            return
        self.legibility = _weighted(random.Random(self.seed ^ 0x4C454749), table)

    def report(self) -> dict:
        """What a dataset's label should carry about this mark."""
        return {"face": self.face, "legibility": self.legibility,
                "baseline": self.baseline, "paraph": self.paraph,
                "connected": self.connected, "flourish": self.flourish,
                "lead": self.lead, "scrawl": self.scrawl,
                "writer": self.writer,
                "slant_deg": round(math.degrees(math.atan(self.slant)), 1),
                "marks": self.marks}


def _entry(glyph: list):
    """A point the letter is actually drawn through, low and to the left.

    Where a pen arriving from below-left first meets the letter. Taken as the
    leftmost **on-curve** point in the bottom third of the ink rather than the
    corner of the bounding box, because a box corner is empty for most capitals
    -- which is exactly how an entry stroke ends up floating beside a `T`
    instead of running into it.
    """
    x0, y0, _x1, y1 = bounds(glyph)
    cut = y0 + (y1 - y0) / 3.0
    on_curve = [contour[index]
                for contour in glyph
                for index in range(0, len(contour) - 1, 3)]
    low = [point for point in on_curve if point[1] <= cut]
    return min(low or on_curve or [(x0, y0)], key=lambda point: point[0])


def _bow(rng: random.Random, baseline: str) -> tuple:
    """`(rise, arch)` as ratios of the mark's own width, for `bow()`.

    Ratios rather than x-heights, because the width is not known until the
    letters are down and a lift measured in absolute units would tilt a
    monogram off the page and leave a full name flat.
    """
    if baseline == "rising":
        return (rng.uniform(0.12, 0.55), rng.uniform(0.0, 0.10))
    if baseline == "falling":
        return (-rng.uniform(0.08, 0.30), rng.uniform(0.0, 0.08))
    if baseline == "wavy":
        return (rng.uniform(-0.08, 0.14), rng.uniform(0.12, 0.34))
    return (rng.uniform(-0.03, 0.05), rng.uniform(0.0, 0.05))


def _weighted(rng: random.Random, table) -> str:
    return rng.choices([name for name, _ in table],
                       [weight for _, weight in table])[0]


# -------------------------------------------------------------------- name


def parts_of(name: str) -> list:
    """A Vietnamese name as its words, in the order it is written.

    `[họ] [đệm...] [tên]` -- family name first, given name **last**, which is
    the opposite end from an English name and is the whole reason this is a
    function rather than a `split()` at the call site. Everything downstream
    that says "the given name" means `parts_of(name)[-1]`.
    """
    return [part for part in name.replace(".", " ").split() if part]


def undiacritic(text: str) -> str:
    """The letters with their marks dropped, `đ`/`Đ` included.

    NFD strips the combining marks; `đ` is not a composition and has to be
    named. A signature that drops its dấu still keeps its consonants.
    """
    swapped = text.replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", swapped)
                   if not unicodedata.combining(c))


def letters_of(name: str, style: Style) -> str:
    """The characters that actually get drawn, per the signer's legibility."""
    parts = parts_of(name)
    if not parts:
        return ""
    if style.legibility == "full":
        text = " ".join(parts)
    elif style.legibility == "given":
        text = parts[-1]
    elif style.legibility == "initials":
        text = "".join(part[0] for part in parts[:-1]) + parts[-1]
    else:                                            # monogram
        text = "".join(part[0] for part in parts)
    return text if style.marks else undiacritic(text)


def head_and_tail(text: str, style: "Style", whole_words: bool = False) -> tuple:
    """`(letters that stay letters, letters that become a wave)`.

    `whole_words` keeps the hand from letting go mid-word, and it exists for
    the model source. WriteViT is trained on words: asked for `Ng` it returns a
    stiff fragment, asked for `Nguyễn` it returns a connected hand with a
    proper signature capital. Cutting a two-letter head out of a name would
    hand the model its weakest case on every signature. So with words the split
    lands on a space -- the first word survives, the rest becomes the wave,
    which is also a shape real signatures come in.

    Three rules otherwise, and each is something the survey says rather than
    something that looked right:

    * the first `survives` characters are formed, because a hand starts a
      signature deliberately and lets go of it afterwards -- "simplification is
      a continuous process";
    * **a capital never degenerates.** Initials are the part of a signature
      meant to be read, and a monogram whose letters had collapsed would be a
      squiggle with nothing left to identify it;
    * once the hand has let go it does not pick the letters back up, so the
      tail is everything from the first degenerated character on, spaces
      included.
    """
    if not style.scrawl:
        return text, ""
    if whole_words:
        # Words are taken until the head is at least `HEAD_LETTERS` long. The
        # model writes a short fragment badly -- `N` on its own comes back a
        # scribble where `Nguyen` comes back a hand -- and a two-letter head
        # is nearly as thin: `Lê` followed by ten slots of wave read as an
        # empty mark. So a short first word reaches for the next one instead of
        # handing the model its weakest case.
        words = text.split(" ")
        take = 1
        while (take < len(words)
               and len("".join(words[:take]).strip()) < HEAD_LETTERS):
            take += 1
        head, rest = " ".join(words[:take]), words[take:]
        return head, (" " + " ".join(rest)) if rest else ""
    kept = 0
    for index, char in enumerate(text):
        if index < style.survives or char.isupper() or char.isspace():
            kept = index + 1
        else:
            break
    return text[:kept], text[kept:]


# ------------------------------------------------------------------- marks


class Mark:
    """A finished signature: contours in x-heights, plus what made it.

    `path` is everything -- letters, connectors, flourish, paraph -- in one
    list, because they are one mark and a caller that could paint them
    separately would be a caller that could paint them wrong.
    """

    def __init__(self, path: list, style: Style, text: str, name: str,
                 head: str = "", tail: str = "", source: str = "font"):
        self.path = path
        self.source = source
        self.style = style
        self.text = text
        self.name = name
        # What stayed letters and what became a wave. In the label because it
        # is the one honest answer to "how much of this is readable" -- and a
        # reader-training set wants to know that about its own ink.
        self.head = head or text
        self.tail = tail
        self.box = bounds(path)

    @property
    def width(self) -> float:
        return self.box[2] - self.box[0]

    @property
    def height(self) -> float:
        return self.box[3] - self.box[1]

    @property
    def aspect(self) -> float:
        return self.width / max(self.height, 1e-6)

    def report(self) -> dict:
        report = self.style.report()
        report.update({"source": self.source, "name": self.name, "drawn": self.text,
                       "legible": self.head, "degenerated": self.tail,
                       "aspect": round(self.aspect, 2),
                       "in_capture_box": ASPECT[0] <= self.aspect <= ASPECT[1]})
        return report

    def __repr__(self) -> str:
        return (f"<Mark {self.head!r}+{len(self.tail)} {self.style.legibility}/"
                f"{self.style.baseline}/{self.style.paraph} "
                f"aspect={self.aspect:.2f}>")


class Signer:
    """One person's hand, over as many names as you like.

    The ink is opened once and cached, so a page with four signature blocks
    costs one font parse -- or, with the model, one worker. Reused across names
    deliberately: the same seed is the same signer, and a signer signing two
    different names should differ only in the letters.

    `source` names where the letters come from, the same two words
    `handwriting.py` uses for the same two things:

        font    outlines from `fonts/hand/` -- always available, and repeats
        model   WriteViT, traced -- thin, joined-up, 106 writers, needs the
                clone and about seven seconds a word on CPU
    """

    def __init__(self, seed: int = 0, ink=None,
                 directory: Path = HAND_FONT_DIR, source: str = "font"):
        self.style = Style(seed)
        if ink is not None:
            self.ink = ink
        elif source == "model":
            self.ink = ModelInk(writer=self.style.writer, seed=seed)
        elif source == "font":
            self.ink = Ink(self.style.face, directory)
        else:
            raise KeyError(f"no ink source {source!r}; have font, model")
        self.source = getattr(self.ink, "source", "font")
        self.style.restrict(getattr(self.ink, "legibility", None))
        self._opened = ink is None

    def __enter__(self) -> "Signer":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> "Signer":
        if self._opened:
            self.ink.open()
        return self

    def close(self) -> None:
        if self._opened:
            self.ink.close()

    # -- the composition ---------------------------------------------------

    def sign(self, name: str) -> Mark:
        """The whole engine, in the order a hand does it.

        Stretch and place the letters the hand still forms, run the ligatures
        between them, let the rest collapse into a wave, warp the line they all
        sit on, pull the terminal out, then lay the paraph under the finished
        thing.

        The order is not cosmetic. The scrawl leaves the last formed letter, so
        it has to be built before the warps rather than after -- it rides the
        baseline with the letters instead of being laid across it. The flourish
        leaves the mark *after* the baseline has bowed, so it leaves from where
        the ink actually ended up. And the paraph is measured against the whole
        mark including its flourish: an underline that stopped politely short of
        the terminal sweep would read as two marks rather than one.
        """
        style = self.style
        # The ink gets a say in the letters before the letters are placed. It
        # is the last chance to keep a name rather than refuse it, and it is
        # cheaper than a fallback: one character the checkpoint cannot write
        # used to cost a whole mark.
        text = self.ink.normalise(letters_of(name, style))
        if not text.strip():
            raise ValueError(f"nothing to sign in {name!r}")
        head, tail = head_and_tail(
            text, style, whole_words=getattr(self.ink, "writes_words", False))
        refuse = getattr(self.ink, "writable", None)
        if refuse is not None and not refuse(head):
            # The model has no digits, no ALL-CAPS and no punctuation, and a
            # monogram is a run of capitals. Raised rather than approximated:
            # `fill` counts it and leaves the block blank, which is the same
            # bargain `handwriting.fill` strikes with the same checkpoint.
            raise ValueError(f"this ink source cannot write {head!r}")

        glyphs = self._letters(head)
        if not glyphs:
            # Every character of the head was outside the face. Falling back to
            # a scrawl alone would be a mark that stands for nothing, so this
            # is an error the caller sees rather than ink nobody can account
            # for -- `fill` counts it and leaves the block blank.
            raise ValueError(f"the face has no glyph for anything in {head!r}")

        path = [contour for _box, sub, _char in glyphs for contour in sub]
        if style.connected:
            path += self._connectors(glyphs)
        if style.lead:
            path += self._lead(glyphs[0][1])
        if tail:
            last = glyphs[-1][0]
            path += self._scrawl(tail, (last[2] - self.ink.stem() * 0.5, last[1]))

        path = self._warp(path, len(glyphs) + len(tail))
        if style.flourish:
            path += self._terminal(path)
        path += self._paraph(path)
        return Mark(mapped(path, affine(shear=style.slant)), style, text, name,
                    head=head, tail=tail, source=self.source)

    def _letters(self, text: str) -> list:
        """Each unit stretched to its role and set down at the pen's x.

        Three roles, which is the survey's three zones: the initial is pulled
        up out of proportion, the body is squeezed narrow, and the last unit
        keeps the body's width but is where the terminal will leave from. The
        stretch is applied about the baseline and the unit's own left edge, so
        a taller initial grows upward off the line rather than floating.

        A **unit** is whatever the ink source hands back, and the two sources
        disagree about it on purpose. `Ink` splits a font into one unit per
        letter, because that is what a glyph is. `ModelInk` splits into the
        initial and then the rest, because WriteViT writes a *word* at a time
        and the joins inside that word are the whole reason to use it -- asking
        it for one letter at a time would throw away the thing it is good at.
        Everything below works the same either way.
        """
        style, ink = self.style, self.ink
        # Whether the first unit gets the vertical cap stretch. A PRINT capital
        # has no signature form of its own, so it is pulled up out of
        # proportion; a capital the model wrote is already a cursive signature
        # capital, and stretching it only makes a blade. The source knows which
        # it is, and it is the source's call.
        stretch = getattr(ink, "stretches_initial", True)
        drawn, pen = [], 0.0
        for path, advance, char in ink.units(text):
            if not path:
                pen += advance
                continue
            initial = not drawn
            sx = 1.0 if initial else style.squeeze
            sy = style.cap if initial and stretch else 1.0
            x0 = bounds(path)[0]
            placed = mapped(path, affine(sx, sy, dx=pen - x0 * sx))
            drawn.append((bounds(placed), placed, char))
            # Capitals are pulled together harder than lowercase. `_connectors`
            # refuses to join two of them -- a print face gives them no exit
            # stroke -- so overlap is the only thing that can make a monogram
            # read as one mark instead of three letters set side by side.
            close = style.overlap * (1.35 if char.isupper() and not initial else 1.0)
            pen += advance * sx - (0.0 if initial else min(close, 0.38) * advance)
        return drawn

    def _scrawl(self, tail: str, start: tuple) -> list:
        """The body once it has stopped being letters: one running stroke.

        Built from the *classes* of the characters it replaces, not from noise.
        The forensic sources make the point that what identifies a hand is the
        movement rather than the form, and it survives the form: a `g` that has
        degenerated still dives below the line and an `l` still throws a loop
        above it. So each dead character contributes one slot, and its slot is
        chosen by what the letter would have done -- which is why the scrawl for
        "uyễn" and the scrawl for "ọc" are different scrawls rather than the
        same squiggle twice.

        The wave is **shorter than the name it stands for**. A hand that has
        given up on nine letters does not put down nine humps; it puts down
        five or six and lifts off. `SCRAWL_SLOTS` caps it, and the cap samples
        the classes evenly rather than truncating, so a descender near the end
        of a long name still reaches the paper.
        """
        style = self.style
        slots = [char for char in tail if not char.isspace()]
        if not slots:
            return []
        if len(slots) > SCRAWL_SLOTS:
            step = len(slots) / SCRAWL_SLOTS
            slots = [slots[min(int(index * step), len(slots) - 1)]
                     for index in range(SCRAWL_SLOTS)]

        width = self.ink.stem()
        x, foot = start
        spine = [(x, foot)]
        for index, char in enumerate(slots):
            # Amplitude decays along the wave: the hand is running down, which
            # is the same finding `fade` applies to the letters.
            scale = 1.0 - style.decay * (index / max(len(slots) - 1, 1))
            # Two independent draws: one for how far this slot travels, one for
            # how high it reaches. Sharing one number made width and height
            # rise and fall together, and a wave whose humps all grow at once
            # is a sawtooth rather than writing.
            wide = style.pulse[(index * 2) % len(style.pulse)]
            jog = style.pulse[(index * 2 + 1) % len(style.pulse)]
            step = style.step * (0.62 + 0.78 * wide)
            plain = undiacritic(char).lower()
            if plain in TAIL_LETTERS:
                spine += self._slot_down(x, foot, step, scale, jog)
            elif plain in TALL_LETTERS or char.isupper():
                spine += self._slot_up(x, foot, step, scale, jog)
            elif jog < 0.22:
                # A letter that has gone completely: barely a ripple.
                spine += self._slot_hump(x, foot, step, scale * 0.34, jog)
            else:
                spine += self._slot_hump(x, foot, step, scale, jog)
            x += step
        # Lighter than the letters and never fattened in the middle. A hand
        # that has stopped forming letters has stopped pressing too, and a
        # steep wave stroked at full width closes its own gaps into a wedge --
        # which is exactly what the first attempt at this drew.
        return [ribbon(spine, width * 0.58, width * 0.36, samples=12)]

    @staticmethod
    def _slot_hump(x: float, foot: float, step: float, scale: float,
                   jog: float) -> list:
        """`n`, `m`, `u`, `a`, `o`, `e` -- an arch up and back to the line.

        The calligraphy sources' overturn-into-underturn, which is what most
        lowercase letters are once the detail that told them apart is gone.
        """
        rise = (0.38 + 0.52 * jog) * scale
        return [(x + step * 0.08, foot + rise * 0.92),
                (x + step * 0.92, foot + rise),
                (x + step, foot + 0.03 * scale)]

    @staticmethod
    def _slot_up(x: float, foot: float, step: float, scale: float,
                 jog: float) -> list:
        """`b d h k l t` and any capital: a loop thrown above the band.

        Two segments, and they cross -- the second control leans back left of
        where the first left off, which is what makes an ascender loop a loop
        rather than a spike.
        """
        top = foot + (1.20 + 0.50 * jog) * scale
        return [(x - step * 0.30, foot + (top - foot) * 0.55),
                (x + step * 0.34, top),
                (x + step * 0.52, foot + (top - foot) * 0.72),
                (x + step * 0.66, foot + (top - foot) * 0.42),
                (x + step * 0.90, foot + 0.10 * scale),
                (x + step, foot + 0.03 * scale)]

    @staticmethod
    def _slot_down(x: float, foot: float, step: float, scale: float,
                   jog: float) -> list:
        """`g j p q y`: a loop dropped below the line and pulled back up."""
        drop = foot - (0.55 + 0.30 * jog) * scale
        return [(x + step * 0.10, foot + 0.30 * scale),
                (x + step * 0.46, drop * 0.55 + foot * 0.45),
                (x + step * 0.30, drop),
                (x + step * 0.14, drop),
                (x + step * 0.86, drop * 0.30 + foot * 0.70),
                (x + step, foot + 0.05 * scale)]

    def _lead(self, glyph: list) -> list:
        """The entry stroke into the initial, swung up from below and left.

        The forensic sources put "initial and terminal strokes" together as one
        pair of individual characteristics, and the Vietnamese guides describe
        the same thing from the other side -- the initial is where the mark
        starts big, and a hand that starts big starts with a run-up. Without
        it an enlarged capital sits on the line like a dropped cap; with it,
        it is entered.

        It has to **land on ink**, which is the whole difficulty: aimed at the
        left edge of the letter's box it ends in mid-air for any letter whose
        box is wider than its stroke there -- a `T` grew a floating tick. So
        the target is `_entry`, a point the letter actually passes through.
        """
        target = _entry(glyph)
        width = self.ink.stem()
        drop = max(0.30, (target[1] + 0.30) * 0.55)
        spine = ((target[0] - 0.66, target[1] - drop),
                 (target[0] - 0.40, target[1] - drop * 0.35),
                 (target[0] - 0.22, target[1] - drop * 0.05),
                 (target[0] + width * 0.25, target[1]))
        return [ribbon(spine, width * 0.12, width * 0.72, bulge=width * 0.08)]

    def _connectors(self, glyphs: list) -> list:
        """A ligature between each pair of letters: a stroke, not a kern.

        The survey is explicit that a connection stroke is its own mark --
        "smoothly stroked and indistinguishable as to the beginning and ending
        of various individual letters" -- and drawing one is the difference
        between a print face set tight and a print face joined up.

        Two rules learned from looking at the output rather than from the
        survey. The join rides **just above** the baseline and sags barely at
        all: an earlier version dipped below it, and a short dip between two
        narrow letters is not a ligature, it is a full stop -- a monogram came
        out reading `P.MT`. And capitals are left unjoined, because in a print
        hand they have no exit stroke to join with and a rule drawn between two
        of them reads as a hyphen.
        """
        width = self.ink.stem() * 0.85
        out = []
        for (left, _a, left_char), (right, _b, right_char) in zip(glyphs, glyphs[1:]):
            if left_char.isupper() and right_char.isupper():
                continue
            gap = right[0] - left[2]
            if gap < -0.30 or gap > 1.20:    # already crossing, or a word apart
                continue
            foot = min(left[1], right[1])
            start, end = (left[2] - width * 0.2, foot + 0.10), (right[0], foot + 0.14)
            span = max(end[0] - start[0], 0.04)
            sag = foot + 0.02
            spine = (start,
                     (start[0] + span * 0.35, sag),
                     (end[0] - span * 0.35, sag),
                     end)
            out.append(ribbon(spine, width * 0.5, width * 0.5, bulge=width * 0.12))
        return out

    def _warp(self, path: list, letters: int) -> list:
        """The line the letters sit on: spacing drift, then fade, then bow.

        Subdivided first and once, for all three: they are non-linear, they act
        on control points, and re-subdividing between them would multiply the
        point count for nothing.

        The fade is scaled by how many letters there are, because the survey's
        finding is that simplification **accumulates** -- "a continuous
        process". Four letters barely degenerate; a full name written out has
        the whole length of itself to degenerate over, and it should look it.
        """
        style = self.style
        x0, _y0, x1, _y1 = bounds(path)
        fine = subdivided(path)
        fine = mapped(fine, swell(x0, x1, style.swell))
        x0, _y0, x1, _y1 = bounds(fine)
        run = min(1.0, 0.25 + 0.12 * max(letters - 2, 0))
        fine = mapped(fine, fade(x0, x1, style.body_fade * run))
        rise, arch = style.bow
        return mapped(fine, bow(x0, x1, rise * (x1 - x0) * 0.28,
                                arch * (x1 - x0) * 0.18))

    def _terminal(self, path: list) -> list:
        """The exit stroke: out past the last letter, and up.

        One stroke, tapering to nothing, leaving from the right edge of the ink
        at about the height a pen leaves a letter. Its reach and lift are the
        signer's, so the same hand ends every signature the same way -- which
        is what the forensic sources say a terminal is for.
        """
        style = self.style
        x0, y0, x1, y1 = bounds(path)
        width = self.ink.stem()
        start = (x1 - width * 0.4, y0 + (y1 - y0) * 0.12)
        reach, rise = style.reach, style.rise
        spine = (start,
                 (start[0] + reach * 0.35, start[1] - 0.28),
                 (start[0] + reach * 0.70, start[1] + rise * 0.55),
                 (start[0] + reach, start[1] + rise))
        return [ribbon(spine, width * 1.05, width * 0.12, bulge=width * 0.1)]

    def _paraph(self, path: list) -> list:
        """The mark under the name, which is not a letter and never was.

        Four kinds, all of them one or two tapered strokes under the finished
        mark. `swash` is the one that reads as a single gesture with the
        terminal: it starts where a terminal would have finished, at the right,
        and sweeps back left under the whole name.
        """
        style = self.style
        if style.paraph == "none":
            return []
        x0, y0, x1, _y1 = bounds(path)
        span = x1 - x0
        width = self.ink.stem()
        under = y0 - 0.30
        wobble = style.wobble

        if style.paraph == "swash":
            spine = ((x1 + span * 0.06, under + 0.42),
                     (x1 - span * 0.25, under - 0.30),
                     (x0 + span * 0.20, under + 0.24),
                     (x0 - span * 0.08, under - 0.06))
            return [ribbon(spine, width * 0.85, width * 0.10, bulge=width * 0.15)]

        if style.paraph == "loop":
            spine = ((x0 - span * 0.10, under + 0.30),
                     (x0 + span * 0.30, under - 0.62),
                     (x1 - span * 0.10, under + 0.48),
                     (x1 + span * 0.10, under - 0.02))
            return [ribbon(spine, width * 0.55, width * 0.75, bulge=width * 0.25)]

        rules = [(under, width * 0.62, width * 0.16)]
        if style.paraph == "double":
            rules.append((under - 0.24, width * 0.42, width * 0.12))
        out = []
        for index, (y, w0, w1) in enumerate(rules):
            sag = -0.03 + wobble[index * 3] * 0.07
            spine = ((x0 - span * 0.05, y + wobble[index * 3 + 1] * 0.04),
                     (x0 + span * 0.30, y + sag),
                     (x1 - span * 0.25, y + sag),
                     (x1 + span * 0.10, y + 0.08 + wobble[index * 3 + 2] * 0.08))
            out.append(ribbon(spine, w0, w1, bulge=width * 0.06))
        return out


# ------------------------------------------------------------------ output


def view(mark: Mark, pad: float = 0.08):
    """`(d, width, height)` -- the mark flipped into SVG space, with a margin.

    Both writers of SVG go through this, and they have to: `mark_span` used to
    slice the tag off `svg()`'s output and re-declare a `viewBox` from the
    unpadded box, which put the ink a margin's width down and right of the
    frame that was supposed to hold it. One function, one frame, one answer to
    where the origin is.

    The y flip lives here and only here: the geometry above is y-up because
    fonts and baselines are, and SVG's y points down.
    """
    x0, y0, x1, y1 = mark.box
    margin = pad * max(y1 - y0, 1e-6)
    x0, y0, x1, y1 = x0 - margin, y0 - margin, x1 + margin, y1 + margin
    flipped = mapped(mark.path, lambda point: (point[0] - x0, y1 - point[1]))
    return d(flipped), x1 - x0, y1 - y0


def svg(mark: Mark, *, colour: str = PEN, height: float = 64.0,
        pad: float = 0.08, background: str = "") -> str:
    """The mark as a standalone SVG, `height` px tall including padding.

    `fill-rule` is nonzero because that is what a TrueType contour's winding
    means -- the counter of an `o` stays a hole, and two letters that overlap
    merge rather than cancelling each other out.
    """
    body, w, h = view(mark, pad)
    scale = height / max(h, 1e-6)
    paper = (f'<rect width="{w:.3f}" height="{h:.3f}" fill="{background}"/>'
             if background else "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{w * scale:.1f}" height="{height:.1f}" '
            f'viewBox="0 0 {w:.3f} {h:.3f}">{paper}'
            f'<path d="{body}" fill="{colour}" fill-rule="nonzero"/></svg>')


def sheet(names: list, seeds: list, *, colour: str = PEN,
          columns: int = 3, cell: float = 130.0) -> str:
    """A contact sheet of marks, to look at a run of styles side by side.

    What the engine is judged by is not one signature but the spread of them,
    and a grid is the only way to see a parameter range doing its job -- or
    doing it too hard, which is the failure this is for catching.
    """
    rows = (len(seeds) + columns - 1) // columns
    row_h, ink_h = cell * 0.66, cell * 0.44
    tiles = []
    for index, seed in enumerate(seeds):
        name = names[index % len(names)]
        with Signer(seed) as signer:
            mark = signer.sign(name)
        x0, y0, x1, y1 = mark.box
        scale = min(cell * 0.86 / max(x1 - x0, 1e-6), ink_h / max(y1 - y0, 1e-6))
        flipped = mapped(mark.path, lambda p: ((p[0] - x0) * scale,
                                               (y1 - p[1]) * scale))
        left, top = (index % columns) * cell, (index // columns) * row_h
        cx = left + (cell - (x1 - x0) * scale) / 2.0
        cy = top + (ink_h - (y1 - y0) * scale) / 2.0 + cell * 0.06
        tiles.append(
            f'<g transform="translate({cx:.1f},{cy:.1f})">'
            # One decimal: these are pixels on a contact sheet, and three
            # decimals is a thousand times finer than a screen can show --
            # paid for in a file twice the size.
            f'<path d="{d(flipped, 1)}" fill="{colour}" fill-rule="nonzero"/></g>'
            # The caption sits under the ink, never across it: a label drawn
            # over the thing it labels is a contact sheet you cannot read.
            f'<text x="{left + cell / 2:.0f}" y="{top + row_h - 7:.0f}" '
            f'text-anchor="middle" font-family="monospace" font-size="7.5" '
            f'fill="#8a8a92">{html.escape(seed_label(mark, seed))}</text>')
    height = rows * row_h + 8
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{columns * cell:.0f}" height="{height:.0f}" '
            f'viewBox="0 0 {columns * cell:.0f} {height:.0f}">'
            f'<rect width="100%" height="100%" fill="#fbfbf7"/>'
            f'{"".join(tiles)}</svg>')


def seed_label(mark: Mark, seed: int) -> str:
    style = mark.style
    return (f"{seed} {mark.head}+{len(mark.tail)} {style.baseline[:4]} "
            f"{style.paraph[:4]} {mark.aspect:.1f}")


def mark_span(mark: Mark, *, colour: str = PEN, height_em: float = 3.4,
              overlap_em: float = 0.30, classes: str = "sig") -> str:
    """The markup a sheet drops above a printed name.

    Inline SVG rather than a data-URI `<img>`, and **no `data-kind`**: this is
    not a labelled run and must never become one. A signature is ink a reader
    has to learn to leave alone, so it has to be on the page and absent from
    the boxes -- `ink_span` in `handwriting.py` is the opposite case, ink that
    *is* a value, and it carries `data-text` for exactly that reason.

    Both margins are negative, and they do different jobs. The top one lets the
    mark rise into the blank the form already prints above the name instead of
    pushing the rest of the block down a page whose every other block is placed
    in millimetres. The bottom one is the overlap: a signature crosses the name
    printed under it, and one that stopped politely short of it reads as a
    picture of a signature rather than as ink on a form.
    """
    body, w, h = view(mark)
    width_em = height_em * w / max(h, 1e-6)
    return (f'<span class="{html.escape(classes)}" aria-hidden="true" '
            f'style="width:{width_em:.2f}em;height:{height_em:.2f}em;'
            f'margin-top:{-(height_em - overlap_em):.2f}em;'
            f'margin-bottom:{-overlap_em:.2f}em;">'
            f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'viewBox="0 0 {w:.3f} {h:.3f}" preserveAspectRatio="xMidYMax meet" '
            f'width="100%" height="100%">'
            f'<path d="{body}" fill="{colour}" fill-rule="nonzero"/>'
            f'</svg></span>')


CSS = """
/* A signature sits above the printed name and overlaps it, because that is
   where a pen puts one: `.sign .who` already opens a 13-14 mm gap under the
   caption -- the blank the form prints for exactly this -- and the mark rises
   into it with a negative top margin rather than pushing the name down the
   page. `overflow:visible` so a terminal sweep that leaves the box is drawn
   rather than clipped; it always leaves the box. */
#sheet span.sig{display:block;overflow:visible;pointer-events:none;
  margin-left:auto;margin-right:auto;}
#sheet span.sig svg{display:block;overflow:visible;}
"""

# The line a person signs on, as `base.signature_block` writes it -- and it
# comes in **two shapes**, which is the thing worth knowing about this repo's
# signature blocks. Only documents with `signature_names` print a name under
# the caption; the rest emit an empty `<div class="who"></div>` under a note
# that literally reads *(Ký, ghi rõ họ tên)*, and those are the blocks most in
# need of a signature. Both shapes match here, and `fill` treats the empty one
# as "somebody signs this, we are not told who".
#
# Tolerant of attributes on the span because `handwriting.FontHand` adds a
# class and a style to the same run -- but NOT of an `<img>` inside it, which
# is what `handwriting.Hand` leaves behind. That is why `fill` runs first;
# `render.py` orders them that way and the docstring below says so.
WHO = re.compile(
    r'<div class="who">'
    r'((?:<span data-kind="sign\.name"[^>]*>([^<>]*)</span>)?)'
    r'</div>')


def _signer(seed: int, source: str, directory: Path, hand) -> "Signer":
    """One opened `Signer`, sharing the caller's WriteViT worker if there is one.

    A page has two signature blocks and a run has many pages; standing up a
    second worker per block would pay the 11-second checkpoint load again for
    nothing. `render.py` already keeps one alive for `--handwriting`, so when
    both are on there is exactly one.
    """
    if source == "model":
        # Built and opened HERE, not by `Signer`: a `Signer` handed an ink
        # treats it as the caller's and neither opens nor closes it, which is
        # right -- and makes opening and closing this one `fill`'s job.
        ink = ModelInk(writer=Style(seed).writer, seed=seed, hand=hand).open()
        return Signer(seed, ink=ink)
    return Signer(seed, directory=directory, source=source).open()


def fill(markup: str, *, seed: int = 0, names=(), colour: str = "",
         directory: Path = HAND_FONT_DIR, height_em: float = 3.4,
         source: str = "font", hand=None):
    """Sign the sheet: a mark above every printed name in a signature block.

    Returns the markup and a report, the same shape and for the same reason as
    `handwriting.fill` -- a page that claims to be signed and has no mark on it
    is a fact about the run, and it belongs in the label rather than in a log
    line nobody keeps.

    Two orderings matter and neither is arbitrary:

    * **Before `handwriting.fill`.** That pass can replace a `sign.name` run
      with an `<img>` of model ink, and `WHO` above deliberately will not match
      a run containing markup. Signing first sees the name as text; signing
      second would silently sign nothing on exactly the pages that got the most
      handwriting.
    * **Each block is a different person.** Two signature columns on an invoice
      are the seller and the buyer, and they do not share a hand, so the seed
      is mixed with the column index rather than reused.

    `names` is who signs the blocks that print no name -- most of them, on most
    layouts. Nothing is invented when it is empty: those blocks are left blank
    and counted as `unnamed` in the report, because a page that could not be
    signed should say so rather than quietly come back unsigned. `render.py`
    fills it from `rulebase.corpus.people`, which is the same corpus the
    documents draw their buyers from; this module deliberately does not know
    where names come from.

    The mark carries no `data-kind` and never will. It is ink a reader must
    learn to leave alone: on the page, absent from the boxes, and absent from
    `labelled_runs`, so inking a sheet cannot change what the sheet says.

    `source` is `font` or `model`. The model is only ever asked for styles it
    can draw -- `Style.restrict` sees to that -- so the fallback below is a
    safety net for a name nobody anticipated rather than the normal path; it
    fires on none of the corpus. When it does fire it falls back **per block**,
    because refusing a whole page would throw away the model's ink on the other
    block and printing nothing would leave a form unsigned for a reason that
    has nothing to do with the form. The report says which ink each mark is
    actually in either way.
    """
    from handwriting import PENS  # noqa: PLC0415 -- one table, not two

    # The pen is drawn here rather than taken from `handwriting.Page`, and the
    # two therefore differ on a page that is both filled and signed. That is
    # the right way round: the clerk who fills a form in and the customer who
    # signs it are not holding the same pen. A caller who wants them to match
    # passes `colour=`.
    rng = random.Random(seed ^ 0x50454E53)
    pen = colour or "#%02x%02x%02x" % rng.choices(
        [rgb for rgb, _ in PENS], [weight for _, weight in PENS])[0]
    report = {"pen": pen, "source": source, "marks": [], "skipped": {}}
    column = [0]
    signers: dict = {}
    shared = hand

    def replace(match: "re.Match") -> str:
        inner, escaped = match.group(1), match.group(2)
        index, column[0] = column[0], column[0] + 1
        name = html.unescape(escaped or "")
        if not parts_of(name):
            # The block prints no name. Somebody still signs it -- that is what
            # the "(Ký, ghi rõ họ tên)" under the caption is for -- but only
            # the caller knows who, and an engine that made one up would be
            # writing fiction into a dataset's label.
            if not names:
                report["skipped"]["unnamed"] = report["skipped"].get("unnamed", 0) + 1
                return match.group(0)
            name = names[index % len(names)]
        # 0x9E3779B1 is the golden-ratio constant every hash mixer reaches for:
        # what is wanted is only that column 0 and column 1 land far apart in
        # the seed space, so that two people on one page are two people.
        key = seed ^ (index * 0x9E3779B1)
        mark = None
        for attempt in ((source, "font") if source != "font" else ("font",)):
            token = (key, attempt)
            try:
                if token not in signers:
                    signers[token] = _signer(key, attempt, directory, shared)
                mark = signers[token].sign(name)
                break
            except (ValueError, FileNotFoundError, RuntimeError) as error:
                reason = f"{attempt}:{type(error).__name__}:{str(error)[:32]}"
                report["skipped"][reason] = report["skipped"].get(reason, 0) + 1
        if mark is None:
            return match.group(0)
        entry = mark.report()
        entry["printed"] = bool(escaped)
        report["marks"].append(entry)
        drawn = mark_span(mark, colour=pen, height_em=height_em)
        return f'<div class="who">{drawn}{inner}</div>' 

    try:
        filled = WHO.sub(replace, markup)
    finally:
        for signer in signers.values():
            signer.close()
            # And the ink `_signer` built, which a `Signer` handed an ink does
            # not own. Closing twice is a no-op on both sources; not closing at
            # all leaks a WriteViT worker per block on a long run.
            signer.ink.close()
    if report["marks"]:
        filled = filled.replace("</style>", CSS + "</style>", 1)
    return filled, report


def main() -> int:
    """Draw a signature, or a sheet of them, to look at the engine on its own.

        python generators/html/signature.py --name "Nguyễn Thị Bích Ngọc" \\
            --seed 7 --out /tmp/sig.svg
        python generators/html/signature.py --name "Lê Quang Đạo" \\
            --grid 12 --out /tmp/sheet.svg
    """
    import argparse

    parser = argparse.ArgumentParser(description="Synthesise a signature.")
    parser.add_argument("--name", required=True, help="the name to sign")
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--grid", type=int, default=0,
                        help="draw N signatures as a contact sheet instead")
    parser.add_argument("--colour", default=PEN)
    parser.add_argument("--out", default="signature.svg")
    args = parser.parse_args()

    out = Path(args.out)
    if args.grid:
        names = [part.strip() for part in args.name.split("|") if part.strip()]
        seeds = list(range(args.seed, args.seed + args.grid))
        out.write_text(sheet(names, seeds, colour=args.colour), encoding="utf-8")
        print(f"{out}  {args.grid} marks")
        return 0

    with Signer(args.seed) as signer:
        mark = signer.sign(args.name)
    out.write_text(svg(mark, colour=args.colour), encoding="utf-8")
    print(f"{out}  {mark!r}")
    return 0


SOURCES = ("font", "model")

__all__ = [
    "ASPECT", "BASELINE", "CAP_STRETCH", "CSS", "FACES", "LEAD", "LEGIBILITY",
    "HEAD_LETTERS", "OVERLAP", "PARAPH", "PEN", "SCRAWL", "SLANT",
    "SOURCES", "SURVIVES",
    "TRACE_ZOOM", "WHO", "ModelInk", "trace",
    "Ink", "Mark", "Signer",
    "Style", "affine", "at", "bounds", "bow", "d", "fade", "fill",
    "head_and_tail", "letters_of", "line_controls", "mapped", "mark_span",
    "parts_of",
    "polyline", "ribbon", "sheet", "subdivided", "svg", "swell", "tangent",
    "undiacritic", "view",
]

if __name__ == "__main__":
    raise SystemExit(main())
