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

So this engine stretches. It takes real letter outlines from the licensed
handwriting faces in `fonts/hand/` and applies the transformations the survey
named -- and it invents exactly two marks that are not letters, the terminal
flourish and the paraph, both of which the survey says are not letters either.

## The limit, said first

The strokes are a typeface's strokes. This makes a **signature-shaped mark**:
the right size, slant, baseline, connection and flourish for a signature, drawn
with a typeface's contours. That is enough to be furniture on a form -- ink a
reader must not mistake for text, sitting where a signature sits -- and it is
what `docs/hoa-tiet-de-xuat.md` asks for. It is **not** a specimen of any
person's signature, and a set built from it is not a signature-verification
corpus: two marks from one seed are identical, and the two faces are two
faces, not 106 writers. Same trade as `FontHand`, written down the same way.

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
    connection   letters run together, and the ligature is a stroke of its own

## The shape of the code

    geometry     cubic contours and warps -- pure Python, no dependency at all
    Ink          letter outlines out of a .ttf, the one part that needs fontTools
    Style        one signer's parameters, drawn from a seed
    Signer.sign  the composition: stretch, place, connect, flourish, warp

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
    """A tapered stroke along one cubic `spine`, as a closed contour.

    The marks a signature has that letters do not -- the ligature between two
    letters, the terminal sweep, the paraph -- are strokes, not outlines, and
    this is what turns a centreline into ink. Width runs `w0 -> w1` with
    `bulge` fattening the middle, which is the pointed-nib behaviour the
    calligraphy sources describe: thin on the entry, full through the pull,
    thin again at the lift.
    """
    left, right = [], []
    for index in range(samples + 1):
        t = index / samples
        x, y = at(spine, t)
        tx, ty = tangent(spine, t)
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
BODY_SQUEEZE = (0.55, 0.95)      # horizontal scale on the letters after the first
BODY_FADE = (0.00, 0.28)         # vertical squeeze accumulated across the mark

# Connection. A ligature is a stroke in its own right in the survey's account,
# so `overlap` pulls the letters together and the connector is drawn between
# them; a signature that is not connected simply has neither.
OVERLAP = (0.02, 0.20)           # of an advance, taken back between letters
CONNECTED = 0.72                 # of signers; the rest print their mark

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
        self.marks = rng.random() < 0.45
        self.bow = _bow(rng, self.baseline)
        # The paraph's own wobble, drawn HERE rather than while it is being
        # laid down. Everything a signer is has to be settled by the end of
        # this constructor: a mark is a pure function of `(seed, name)`, and it
        # stops being one the moment `sign()` touches the generator -- signing
        # two names would advance it and the second underline would sag
        # differently from the first for no reason a dataset could explain.
        self.wobble = tuple(rng.uniform(-1.0, 1.0) for _ in range(6))

    @property
    def rng(self) -> random.Random:
        raise AttributeError(
            "Style draws everything in __init__ on purpose -- see `wobble`. "
            "Add a field there rather than a draw at sign time.")

    def report(self) -> dict:
        """What a dataset's label should carry about this mark."""
        return {"face": self.face, "legibility": self.legibility,
                "baseline": self.baseline, "paraph": self.paraph,
                "connected": self.connected, "flourish": self.flourish,
                "lead": self.lead,
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


# ------------------------------------------------------------------- marks


class Mark:
    """A finished signature: contours in x-heights, plus what made it.

    `path` is everything -- letters, connectors, flourish, paraph -- in one
    list, because they are one mark and a caller that could paint them
    separately would be a caller that could paint them wrong.
    """

    def __init__(self, path: list, style: Style, text: str, name: str):
        self.path = path
        self.style = style
        self.text = text
        self.name = name
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
        report.update({"name": self.name, "drawn": self.text,
                       "aspect": round(self.aspect, 2),
                       "in_capture_box": ASPECT[0] <= self.aspect <= ASPECT[1]})
        return report

    def __repr__(self) -> str:
        return (f"<Mark {self.text!r} {self.style.legibility}/"
                f"{self.style.baseline}/{self.style.paraph} "
                f"aspect={self.aspect:.2f}>")


class Signer:
    """One person's hand, over as many names as you like.

    The face is opened once and the outlines cached, so a page with four
    signature blocks costs one font parse. Reused across names deliberately:
    the same seed is the same signer, and a signer signing two different names
    should differ only in the letters.
    """

    def __init__(self, seed: int = 0, ink: "Ink | None" = None,
                 directory: Path = HAND_FONT_DIR):
        self.style = Style(seed)
        self.ink = ink if ink is not None else Ink(self.style.face, directory)
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

        Stretch and place the letters, run the ligatures between them, warp
        the line they sit on, pull the terminal out, then lay the paraph under
        the finished thing. The order is not cosmetic: the flourish leaves the
        last letter *after* the baseline has bowed, so it leaves from where the
        letter actually ended up, and the paraph is measured against the mark
        including its flourish -- an underline that stopped short of the
        terminal sweep would read as two marks rather than one.
        """
        style = self.style
        text = letters_of(name, style)
        if not text.strip():
            raise ValueError(f"nothing to sign in {name!r}")

        glyphs = self._letters(text)
        if not glyphs:
            raise ValueError(f"the face has no glyph for anything in {text!r}")

        path = [contour for _box, sub, _char in glyphs for contour in sub]
        if style.connected:
            path += self._connectors(glyphs)
        if style.lead:
            path += self._lead(glyphs[0][1])

        path = self._warp(path, len(glyphs))
        if style.flourish:
            path += self._terminal(path)
        path += self._paraph(path)
        return Mark(mapped(path, affine(shear=style.slant)), style, text, name)

    def _letters(self, text: str) -> list:
        """Each letter stretched to its role and set down at the pen's x.

        Three roles, which is the survey's three zones: the initial is pulled
        up out of proportion, the body is squeezed narrow, and the last letter
        keeps the body's width but is where the terminal will leave from. The
        stretch is applied about the baseline and the letter's own left edge,
        so a taller initial grows upward off the line rather than floating.
        """
        style, ink = self.style, self.ink
        drawn, pen = [], 0.0
        for index, char in enumerate(text):
            if char.isspace():
                pen += 0.42                    # a word gap, in x-heights
                continue
            if not ink.has(char):
                continue
            outline, advance = ink.outline(char)
            if not outline:
                pen += advance
                continue
            initial = not drawn
            sx = 1.0 if initial else style.squeeze
            sy = style.cap if initial else 1.0
            x0 = bounds(outline)[0]
            placed = mapped(outline, affine(sx, sy, dx=pen - x0 * sx))
            drawn.append((bounds(placed), placed, char))
            pen += advance * sx - (0.0 if initial else style.overlap * advance)
        return drawn

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
    return (f"{seed} {style.legibility[:4]} {style.baseline[:4]} "
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


def fill(markup: str, *, seed: int = 0, names=(), colour: str = "",
         directory: Path = HAND_FONT_DIR, height_em: float = 3.4):
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
    report = {"pen": pen, "marks": [], "skipped": {}}
    column = [0]
    signers: dict = {}

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
        try:
            if key not in signers:
                signers[key] = Signer(key, directory=directory).open()
            mark = signers[key].sign(name)
        except (ValueError, FileNotFoundError) as error:
            reason = type(error).__name__ + ":" + str(error)[:40]
            report["skipped"][reason] = report["skipped"].get(reason, 0) + 1
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


__all__ = [
    "ASPECT", "BASELINE", "CAP_STRETCH", "CSS", "FACES", "LEAD", "LEGIBILITY",
    "OVERLAP", "PARAPH", "PEN", "SLANT", "WHO", "Ink", "Mark", "Signer",
    "Style", "affine", "at", "bounds", "bow", "d", "fade", "fill",
    "letters_of", "line_controls", "mapped", "mark_span", "parts_of",
    "polyline", "ribbon", "sheet", "subdivided", "svg", "swell", "tangent",
    "undiacritic", "view",
]

if __name__ == "__main__":
    raise SystemExit(main())
