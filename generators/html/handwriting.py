"""Fill a printed form's fields with real handwriting instead of type.

    from handwriting import Hand, fill
    with Hand() as hand:
        markup, report = fill(markup, hand, seed=7)

`docs/hoa-tiet-de-xuat.md` has called `handwriting_fill` the dataset's largest
gap since the ornament survey: every sheet here is printed end to end, including
`authorisation_letter`, whose own layout file says the dotted rules are *chỗ để
điền* -- the place to fill in. `docs/writevit.md` then stood up the one released
model with Vietnamese weights and measured what it can write. This is the wire
between the two.

**What it does not do is invent ink.** The rejected attempt in `ff9a9f0` took a
printed typeface and jittered it; what came out was printing with a tremor,
because the stroke shapes were still a typeface's. Nothing here draws a letter:
a mark on the page is either the WriteViT generator's or a handwriting
typeface's own outline, and no glyph is nudged, slanted or thickened after the
fact.

## Three sources, and they are not interchangeable

    Hand       WriteViT, one word at a time, pasted in as an <img> of ink
    FontHand   a licensed handwriting typeface, set by the browser as text
    BothHands  the model where it can write, the typeface where it cannot

`Hand` is the real thing -- a generative model conditioned on a writer -- and it
**cannot write digits or ALL-CAPS**, which caps it at 42 % of the fields on the
best page in the rule space. `FontHand` fills every field, because a typeface
has all ten digits and every mark, and `hoa-tiet-de-xuat.md` names "một mặt chữ
viết tay có giấy phép cho phép phát hành lại" as a legitimate path alongside
real stroke data.

What it buys is coverage, and what it costs is written down rather than hoped
past: **a typeface repeats.** Every `a` on the page is the same `a`, every page
in a run drawn from the same face is the same hand, and there are two faces, not
106 writers. Model ink varies per instance; font ink does not. A set built with
`--handwriting font` should say so, and `record["handwriting"]["source"]` does.

`BothHands` refuses to choose between them and pays for it in a different coin:
every run is ink, none is type, and **two different hands share the page**. That
is the honest trade, not a hidden one -- `record["handwriting"]["by_source"]`
counts the runs each source wrote, so a reader of the label knows which half of
a page came from where. It exists for `notebook_ledger`, where a single source
cannot work: the checkpoint writes 8 % of a sales book and a page nine parts
typed is not a notebook.

The default is `model`. Reach for `font` when the page needs its numeric fields
filled and you would rather have one hand throughout than a form that is 42 %
written and 58 % typed; reach for `both` when nothing on the page was printed
and leaving a run in type would be leaving it wrong.

A fourth source, `HybridHand`, goes one step further than `BothHands` and is
**not** wired into any renderer's `--handwriting` flag: it decides per *word*
inside one field rather than per field, so `"3.920.000 đồng"` can come back
with `đồng` in the model's ink and the digits in the typeface's, composited
into the one image `Hand` would have produced. Built for `tools/visualize/`'s
side-by-side comparison against `BothHands`, to look at whether the finer
split is worth losing `BothHands`'s per-field simplicity -- not a claim that
it is.

## The policy, and why it is per field

A word is writable when the checkpoint can actually write it:

* no digits -- `models/model.py` draws the generator's training text only from
  `lex`, and not one of the 10,131 tokens that reach `lex` contains a digit, so
  the ten digit slots in `ALPHABET` were never taught;
* not ALL-CAPS -- filtered into the same unused half of the lexicon;
* every character inside `ALPHABET`, which is letters, digits and `!` -- there
  is no comma, full stop, slash or hyphen in it.

The decision is taken **per field, not per word**. A line reading half ink and
half type is not what a form filled in by hand looks like, and mixing them
inside one labelled run would also split one ground-truth box in two.

Measured over the sixteen layouts, twenty seeds each: **432 of 2,954 field runs
(14.6 %) are writable**, and 2,075 of the 2,522 refusals are a digit. Drawing
the separators by hand -- a hyphen and a full stop are marks, not letter shapes,
so they would not be the rejected approach -- was measured too and buys 1.2
points. It is not implemented; see `docs/handwriting-html.md`.

## The box contract

An inked run keeps its `<span data-kind>` and gains `data-text`, because the
text is no longer in the DOM for `CELL_RECTS_JS` to read off it -- there is an
`<img>` there instead. The quad becomes the image's rect, which is the ink,
because `CELL_RECTS_JS` already measures `span.firstElementChild || span`.
`page.py` and `sheets/__init__.py` read `data-text` where they used to read
`textContent`; nothing else in either engine changes.
"""

from __future__ import annotations

import base64
import html
import io
import json
import os
import random
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

# numpy and Pillow are imported inside the two functions that touch pixels, and
# nowhere else, for the reason `page.py` gives for its own thinness: the policy
# -- which runs are writable, what the markup becomes, what the report says --
# is a pure function of strings, and CI runs the test suite on pytest and PyYAML
# and nothing else. A module-level `import numpy` would put a renderer's
# dependency in front of a test about a regular expression.

REPO_ROOT = Path(__file__).resolve().parents[2]

# The clone lives beside the repository, as `tools/writevit/setup.py` puts it
# and `docs/writevit.md` explains: nothing here imports WriteViT, and its
# weights and data are 294 MB.
WRITEVIT_DIR = Path(os.environ.get("WRITEVIT_DIR") or REPO_ROOT.parent / "WriteViT")
SERVE = REPO_ROOT / "tools" / "writevit" / "serve.py"

# What the VNDB checkpoint has a slot for: letters with every Vietnamese mark,
# the ten digits and `!`. Restated here rather than imported because reading it
# from `params.py` would mean importing torch into the renderer's environment
# to ask a question about a string. `Hand.open` checks the two agree, so a
# checkpoint trained on a wider alphabet cannot silently disagree with this.
ALPHABET = (
    "aáàảãạăắằẳẵặâấầẩẫậbcdđeéèẻẽẹêếềểễệfghiíìỉĩịjklmnoóòỏõọôốồổỗộơớờởỡợpqrstu"
    "úùủũụưứừửữựvwxyýỳỷỹỵzAÁÀẢÃẠĂẮẰẲẴẶÂẤẦẨẪẬBCDĐEÉÈẺẼẸÊẾỀỂỄỆFGHIÍÌỈĨỊJKLMNOÓ"
    "ÒỎÕỌÔỐỒỔỖỘƠỚỜỞỠỢPQRSTUÚÙỦŨỤƯỨỪỬỮỰVWXYÝỲỶỸỴZ0123456789!"
)
ALPHABET_SET = frozenset(ALPHABET)

# Which labelled runs a person fills in. Values and the name under a signature,
# never the furniture: a letterhead, a column title and a printed clause are
# printed on the blank form, before anybody picks up a pen.
HAND_KINDS = ("invoice.field", "invoice.words", "sign.name")

# `fill(kinds=ALL_KINDS)` writes EVERY labelled run instead of a listed few.
# For a page nobody printed: `sheets/notebook.py` is a school exercise book,
# where a heading left in type would be a heading nobody typed. The same string
# is `sheets.base.EVERY_RUN`, restated rather than imported so this module goes
# on knowing nothing about which layout families exist; `tests/test_sheets.py`
# asserts the two agree.
ALL_KINDS = "*"

# The handwriting typefaces, in `fonts/hand/`. Both are SIL OFL 1.1 and both
# pass `generators/synthdog/tools/check_fonts.py` on the full Vietnamese
# alphabet -- which is not a formality: **Caveat, the obvious casual-hand
# choice, is missing 80 of those characters** and would have printed empty boxes
# under a label claiming the word was written. `size` is the multiple of the
# printed font size that puts the face's x-height where a person's writing sits;
# it differs per face because their x-heights do.
FACES = (
    ("PatrickHand", "PatrickHand-Regular.ttf", 1.42),    # a neat print hand
    ("IndieFlower", "IndieFlower-Regular.ttf", 1.34),    # rounder, looser
)
HAND_FONT_DIR = REPO_ROOT / "fonts" / "hand"

# Ballpoint and fountain pen, as a form actually comes back: dark blue far more
# often than black, and never the paper's own near-black. RGB.
PENS = (
    ((28, 42, 104), 6),    # blue ballpoint
    ((17, 30, 78), 3),     # darker blue
    ((26, 26, 32), 3),     # black ballpoint
    ((23, 52, 96), 1),     # blue-grey, a drier pen
)

# The generator emits every word 32 px tall and 16 px per character, and crops
# tight -- so "Tiền" and "mặt" come back the same height even though "mặt" has
# nothing reaching up, and a row of such tiles reads as two sizes of writing
# rather than as one hand. Measured across three writers and three kinds of
# word, the ink fills the tile top to bottom whatever the letters are: there is
# no baseline in the image to read back.
#
# So it is worked out from the letters instead, in x-heights -- how far the word
# reaches above the x-height band and how far below it. Anything above at all
# counts, but not equally: a true ascender is `ABOVE_TALL`, the circumflex on
# `ề` only `ABOVE_MARK`; a dấu nặng is smaller than a descender loop and gets
# its own number. `compose` scales each tile to its own extent and lands them
# all on one baseline, which is what makes a row of tiles look written.
X_HEIGHT = 1.0
ABOVE_TALL, ABOVE_MARK = 0.74, 0.34      # b d đ h k l t, capitals / ` ´ ˆ ˜ ˀ ˘
BELOW_TAIL, BELOW_DOT = 0.50, 0.20       # g j p q y / dấu nặng
TALL_LETTERS = frozenset("bdđhklt")
TAIL_LETTERS = frozenset("gjpqy")
MARKS_ABOVE = frozenset("\u0300\u0301\u0302\u0303\u0306\u0309")
MARK_BELOW = "\u0323"

# Where the writing goes relative to the printed rule, and how big it is.
# `SIT_EM` is how far the ink's box hangs below the baseline the value would
# have been typed on, and it is the one number that makes a line look written
# *on* the rule rather than floating above it.
INK_HEIGHT_EM = (1.95, 2.25)   # per page: nobody writes the printed size
SIT_EM = 0.55
SIT_JITTER_EM = 0.07   # per field: nobody writes exactly on the rule either
WORD_GAP = 14          # source px between words, on a 32 px body
# How sharply partial coverage becomes opaque -- see `ink_png`. Swept at 1.0,
# 0.8, 0.65 and 0.5 and read off the pixels: mean stroke value falls 128 -> 118
# monotonically, but so does fidelity. At 0.5 the ink covers 19.2 % of the field
# against the generator's own 15.9 %, which is no longer compositing the model's
# stroke but thickening it. 0.8 lands at 16.5 % and buys about three points of
# contrast, which is the most that can be taken without inventing.
INK_GAMMA = 0.8

# `font_tile`'s native render size, in px. Arbitrary -- `compose()` sizes every
# tile off `extent()`, a function of the word's letters, not of how many
# source pixels it started with -- but generous enough that a font tile is not
# the blurriest thing on the page once everything lands on one unit.
FONT_TILE_PX = 64


# `base.span()` is text-only by contract -- `CELL_RECTS_JS` measures
# `firstElementChild` and a nested element would silently become the box -- so a
# labelled run never contains markup and this pattern is exact rather than a
# guess at parsing HTML. `_check_contract` fails loudly if that ever stops
# being true.
RUN = re.compile(r'<span data-kind="([^"]+)"((?: class="[^"]*")?)>([^<>]*)</span>')

CSS = """
/* Ink laid over a printed form. The image carries its own width in em so a
   field too narrow for the writing shrinks it whole -- `max-width` with a
   fixed `height` would squash the hand instead of scaling it. */
#sheet span.hand{white-space:nowrap;}
#sheet span.hand img{max-width:100%;height:auto;image-rendering:auto;}
"""


def words_of(text: str) -> list[str]:
    return text.split()


def extent(word: str) -> tuple[float, float]:
    """`(above, below)` the x-height band, in x-heights, for one word.

    A model of the letters, not of the ink: the tile has already been squashed
    to a fixed height and cannot be measured back. Being a model, it is
    approximate -- but it is approximate in the same direction for every word,
    which is all that matters for putting them on one line.
    """
    decomposed = unicodedata.normalize("NFD", word)
    above = below = 0.0
    for character in decomposed:
        if character in MARKS_ABOVE:
            above = max(above, ABOVE_MARK)
        elif character == MARK_BELOW:
            below = max(below, BELOW_DOT)
        elif character.isupper() or character.lower() in TALL_LETTERS:
            above = ABOVE_TALL
        elif character.lower() in TAIL_LETTERS:
            below = max(below, BELOW_TAIL)
    return above, below


def line_extent(text: str) -> tuple[float, float]:
    """How far a whole composed run reaches above and below the x-height band.

    The same maxima `compose` takes over its tiles, worked out from the letters
    alone -- so a caller can know how tall the ink will be before any of it is
    generated. `BothHands` needs exactly that to size one hand against another.
    """
    metrics = [extent(word) for word in words_of(text)] or [(0.0, 0.0)]
    return max(a for a, _ in metrics), max(b for _, b in metrics)


def writable_word(word: str) -> bool:
    """Can the checkpoint write this one word? The per-word half of `writable`.

    Pulled out on its own for `hybrid_line`, which needs these same three
    checks at word granularity rather than across a whole run.
    """
    if any(character.isdigit() for character in word):
        return False
    if len(word) > 1 and word.isupper():
        return False
    if any(character not in ALPHABET_SET for character in word):
        return False
    return True


def writable(text: str) -> bool:
    """Can the checkpoint write this whole run? See the module docstring."""
    words = words_of(text)
    return bool(words) and all(writable_word(word) for word in words)


def refusal(text: str) -> str:
    """Why a run stays printed, in one word, for the report.

    Ordered by what a reader should be told first: a digit blocks 82 % of the
    refusals and no amount of alphabet-widening fixes it, so it is named even
    when the run is also all-caps.
    """
    words = words_of(text)
    if not words:
        return "empty"
    if any(character.isdigit() for word in words for character in word):
        return "digit"
    if any(len(word) > 1 and word.isupper() for word in words):
        return "allcaps"
    if any(character not in ALPHABET_SET for word in words for character in word):
        return "alphabet"
    return "none"


def _interpreter(writevit_dir: Path) -> str:
    """WriteViT's own venv, whichever platform built it.

    `tools/paths.py` already answers this question for the three renderer
    environments and is the only place in the repository that knows Windows
    keeps its interpreter somewhere else. Reached through sys.path rather than
    copied, so a fourth `bin/python` cannot drift from the other three.
    """
    tools = REPO_ROOT / "tools"
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))
    from paths import venv_python  # noqa: PLC0415 -- see the docstring

    return str(venv_python(writevit_dir / ".venv"))


class Page:
    """One person, one pen, one sitting -- whichever source draws the ink.

    Drawn once per page and handed to the source, because these are facts about
    the person filling the form rather than about how the ink is made: a form
    comes back in one hand and one colour. Only where each line lands on its
    rule is drawn per field, since that is the part nobody holds steady.
    """

    def __init__(self, seed: int):
        self.rng = random.Random(seed ^ 0x48414E44)
        self.seed = seed
        self.writer = self.rng.randrange(106)
        self.pen = self.rng.choices([colour for colour, _ in PENS],
                                    [weight for _, weight in PENS])[0]
        self.height_em = self.rng.uniform(*INK_HEIGHT_EM)
        # How many runs each source actually inked, filled in by `BothHands`
        # and reported by `fill`. A page written by two hands must say which
        # half came from where -- see that class for why they do not match.
        self.by_source: dict[str, int] = {}

    @property
    def pen_hex(self) -> str:
        return "#%02x%02x%02x" % self.pen

    def sit(self) -> float:
        return SIT_EM + self.rng.uniform(-SIT_JITTER_EM, SIT_JITTER_EM)


def _classes(classes: str, extra: str) -> str:
    existing = re.search(r'class="([^"]*)"', classes)
    return ((existing.group(1) + " ") if existing else "") + extra


class FontHand:
    """Ink from a licensed handwriting typeface, set by the browser as text.

    No image and no `data-text`: the run keeps its text node, so `CELL_RECTS_JS`
    boxes it exactly as it boxes printed text -- per line when it wraps, which
    an `<img>` of ink cannot do -- and neither box reader needs to know this
    source exists. That is the whole reason this is a CSS change rather than a
    second raster pipeline.

    The honest limit is in the module docstring: a typeface repeats. Nothing
    here jitters a glyph to hide that, because hiding it is what `ff9a9f0`
    removed.
    """

    source = "font"
    device = "browser"

    def __init__(self, faces=FACES, directory: Path = HAND_FONT_DIR,
                 mark: str = "hand"):
        self.directory = Path(directory)
        self.faces = [f for f in faces if (self.directory / f[1]).exists()]
        self._cmaps: dict[str, frozenset] = {}
        self._x_heights: dict[str, float] = {}
        # The class this source's runs carry AND the selector its CSS uses --
        # one name, so the two cannot drift apart. It exists for `BothHands`:
        # the font rule sets `font-size` on the runs it matches, and the model
        # source states its image width in `em`, so a font rule that reached
        # the model's runs would resize the model's ink. Scoping the font to
        # its own class leaves the model's runs at the sheet's own size,
        # exactly as `--handwriting model` alone leaves them.
        self.mark = mark

    # -- lifecycle: there is no process, so these are the shape of `Hand`'s --

    def __enter__(self) -> "FontHand":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> "FontHand":
        if not self.faces:
            raise RuntimeError(
                f"no handwriting faces in {self.directory}. Expected "
                + ", ".join(name for _, name, _ in FACES)
                + " -- see fonts/README.md.")
        return self

    def close(self) -> None:
        pass

    # -- what it can write -------------------------------------------------

    def cmap(self, face: str) -> frozenset:
        """Which characters the face actually has a glyph for.

        Read from the font rather than assumed. A missing glyph renders as an
        empty box while the label still claims the word was written, which is
        the exact failure `fonts/README.md` exists to prevent.
        """
        if face not in self._cmaps:
            from fontTools.ttLib import TTFont  # noqa: PLC0415 -- only this path

            name = dict((f[0], f[1]) for f in self.faces)[face]
            self._cmaps[face] = frozenset(
                chr(code) for code in TTFont(self.directory / name).getBestCmap())
        return self._cmaps[face]

    def face_for(self, page: "Page") -> tuple[str, str, float]:
        return self.faces[page.writer % len(self.faces)]

    def x_height_em(self, page: "Page") -> float:
        """How tall this page's writing is at the x-height, in the sheet's em.

        Read off the face's own OS/2 table rather than assumed, and it exists
        for `BothHands`: two hands on one page must be one SIZE even when they
        cannot be one style, and the x-height is the size a reader judges
        writing by. See `BothHands._matched_height`.
        """
        face, _filename, size = self.face_for(page)
        return size * page.height_em / 2.1 * self._x_height(face)

    def _x_height(self, face: str) -> float:
        if face not in self._x_heights:
            from fontTools.ttLib import TTFont  # noqa: PLC0415 -- see `cmap`

            name = dict((f[0], f[1]) for f in self.faces)[face]
            font = TTFont(self.directory / name)
            units = font["head"].unitsPerEm
            # `sxHeight` is optional in OS/2 version 0 and 1. Falling back to
            # the height of `x` itself rather than to a constant: a guessed
            # x-height would silently mis-size one half of every page.
            raw = getattr(font["OS/2"], "sxHeight", None)
            if not raw:
                glyph = font.getBestCmap().get(ord("x"))
                raw = font["glyf"][glyph].yMax if glyph else units * 0.5
            self._x_heights[face] = raw / units
        return self._x_heights[face]

    def writable(self, text: str, page: "Page") -> bool:
        if not text.strip():
            return False
        covered = self.cmap(self.face_for(page)[0])
        return all(c in covered or c.isspace() for c in text)

    def refusal(self, text: str, page: "Page") -> str:
        return "empty" if not text.strip() else "noglyph"

    # -- what it draws -----------------------------------------------------

    def span(self, kind: str, classes: str, text: str, page: "Page") -> str:
        # The text stays a text node, and the nudge off the rule is
        # `vertical-align` -- NOT `position:relative`, which was the first
        # attempt and broke WeasyPrint. Relative positioning paints in a later
        # stacking pass, so every inked run landed at the END of the PDF's text
        # layer instead of in document order; `match_runs` walks the runs beside
        # that layer, so it desynchronised at the first filled field and a page
        # came back with 16 boxes instead of 97. `vertical-align` is an inline
        # shift with no stacking context, and it costs nothing in the browser.
        style = f"vertical-align:{SIT_EM - page.sit():.3f}em;"
        extra = "hand" if self.mark == "hand" else f"hand {self.mark}"
        return (f'<span data-kind="{html.escape(kind)}" '
                f'class="{_classes(classes, extra)}" style="{style}">'
                f'{html.escape(text)}</span>')

    def css(self, page: "Page") -> str:
        face, filename, size = self.face_for(page)
        path = (self.directory / filename).resolve()
        return f"""
/* Handwriting set as text, not pasted as an image -- see FontHand. The face is
   embedded from {filename} the same way `page.font_faces()` embeds the printed
   ones: a CSS stack that fell through to the system is how a page ends up in a
   font with no Vietnamese diacritics. */
@font-face{{font-family:'{face}';font-weight:400;
  src:url('{path.as_uri()}') format('truetype');}}
#sheet span.{self.mark}{{
  font-family:'{face}',cursive;
  font-size:{size * page.height_em / 2.1:.3f}em;
  color:{page.pen_hex};
  font-weight:400;
}}
#sheet span.{self.mark} b,#sheet span.{self.mark} strong{{font-weight:400;}}
"""


class Hand:
    """One long-lived WriteViT worker, and the ink it has already written.

    Kept alive across a run for the same reason `HtmlReceiptRenderer` keeps one
    browser: a cold load is 11 s on CPU and almost all of it is the checkpoint
    and the 193 MB style pickle. The cache is keyed on `(writer, word)` because
    a corpus repeats -- "Nguyễn", "Chuyển khoản", "triệu" -- and one person
    writes the same word much the same way twice.
    """

    source = "model"

    def __init__(self, writevit_dir: Path | None = None, python: str | None = None):
        self.dir = Path(writevit_dir or WRITEVIT_DIR)
        self.python = python or _interpreter(self.dir)
        self._process: subprocess.Popen | None = None
        self._cache: dict[tuple[int, str], object] = {}
        self.device = ""
        self.calls = 0
        self.words_written = 0

    # -- lifecycle ---------------------------------------------------------

    def __enter__(self) -> "Hand":
        self.open()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> "Hand":
        if self._process is not None:
            return self
        if not self.dir.is_dir():
            raise RuntimeError(
                f"WriteViT is not at {self.dir}. Run `python tools/writevit/setup.py`, "
                "or set WRITEVIT_DIR. Handwriting is not faked when the model is "
                "missing -- see handwriting.py."
            )
        if not Path(self.python).exists():
            raise RuntimeError(
                f"no interpreter at {self.python}; `tools/writevit/setup.py` builds "
                "the venv that has torch in it. The renderer's own environment "
                "deliberately does not."
            )
        # stderr is left attached to ours: the model's own chatter and any
        # traceback should reach whoever is watching the run, and the protocol
        # is on stdout alone.
        self._process = subprocess.Popen(
            [self.python, str(SERVE), "--writevit-dir", str(self.dir)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            text=True, bufsize=1, cwd=str(REPO_ROOT),
        )
        hello = self._process.stdout.readline()
        if not hello:
            raise RuntimeError(
                "the WriteViT worker died before it was ready; its stderr is above")
        ready = json.loads(hello)
        self.device = ready.get("device", "")
        # The policy above is a copy of the checkpoint's alphabet, kept here so
        # the renderer can decide what to ask for without importing torch. A
        # copy that has drifted would refuse writable words, or worse ask for
        # unwritable ones, so the two are compared once per run.
        theirs = ready.get("alphabet")
        if theirs is not None and set(theirs) != ALPHABET_SET:
            raise RuntimeError(
                "handwriting.ALPHABET disagrees with the checkpoint's: "
                f"only here {sorted(ALPHABET_SET - set(theirs))}, "
                f"only there {sorted(set(theirs) - ALPHABET_SET)}"
            )
        return self

    def close(self) -> None:
        if self._process is None:
            return
        try:
            self._process.stdin.write('{"stop": true}\n')
            self._process.stdin.flush()
            self._process.wait(timeout=20)
        except Exception:  # noqa: BLE001 -- shutting down; killing is enough
            self._process.kill()
        finally:
            self._process = None

    # -- writing -----------------------------------------------------------

    def _ask(self, words: list[str], writer: int, seed: int) -> list:
        from PIL import Image

        if self._process is None:
            raise RuntimeError("the worker is not open; use `with Hand() as hand`")
        request = {"words": words, "writer": writer, "seed": seed}
        self._process.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
        self._process.stdin.flush()
        line = self._process.stdout.readline()
        if not line:
            raise RuntimeError("the WriteViT worker died mid-run; its stderr is above")
        reply = json.loads(line)
        if "error" in reply:
            raise ValueError(reply["error"])
        self.calls += 1
        self.words_written += len(reply["words"])
        return [Image.open(io.BytesIO(base64.b64decode(item["png"]))).convert("L")
                for item in reply["words"]]

    def tiles(self, words: list[str], writer: int, seed: int) -> dict[str, object]:
        """Raw per-word grayscale tiles, cached by `(writer, word)`, not composed.

        `line()` below is exactly this plus `compose()`. Split out because
        `hybrid_line` needs the tiles on their own, to lay them out beside a
        font-drawn tile in one `compose_with_boxes()` call rather than two
        separate images that would then need stitching back together.
        """
        wanted = [word for word in words if (writer, word) not in self._cache]
        # Deduplicated before asking: a field can repeat a word, and the model
        # would otherwise be run twice for one tile.
        seen: list[str] = []
        for word in wanted:
            if word not in seen:
                seen.append(word)
        if seen:
            for word, tile in zip(seen, self._ask(seen, writer, seed)):
                self._cache[(writer, word)] = tile
        return {word: self._cache[(writer, word)] for word in words}

    def line(self, text: str, writer: int, seed: int):
        """One run of text as a single grayscale image, words laid out in a row.

        The gap between words is the caller's to set and always was -- WriteViT
        generates one word at a time and says nothing about spacing.
        """
        words = words_of(text)
        tiles = self.tiles(words, writer, seed)
        return compose([(word, tiles[word]) for word in words])

    def ink(self, text: str, writer: int, seed: int,
            pen: tuple[int, int, int]) -> tuple[bytes, tuple[int, int]]:
        """The run as a PNG in the pen's colour, and its size in pixels.

        The pixels stop here: `fill` decides what a page says and should not
        have to hold a PIL image to do it. A test double is then four lines and
        needs neither Pillow nor a checkpoint.
        """
        line = self.line(text, writer, seed)
        return ink_png(line, pen), line.size

    # -- the source interface, shared with FontHand ------------------------

    def writable(self, text: str, page: "Page") -> bool:
        return writable(text)

    def refusal(self, text: str, page: "Page") -> str:
        return refusal(text)

    def span(self, kind: str, classes: str, text: str, page: "Page",
             height_em: float | None = None) -> str:
        # `height_em` is an override, and only `BothHands` passes one: sharing
        # a page with a typeface means matching its x-height rather than
        # keeping the size a printed form's field was calibrated for.
        png, size = self.ink(text, page.writer, page.seed, page.pen)
        return ink_span(kind, classes, text, png, size,
                        page.height_em if height_em is None else height_em,
                        page.sit())

    def css(self, page: "Page") -> str:
        return CSS


class BothHands:
    """The checkpoint where it can write, the typeface where it cannot.

    WriteViT refuses every run containing a digit and every ALL-CAPS word --
    not a guard of ours but a fact about the checkpoint: `models/model.py`
    draws its training text from a lexicon in which not one of 10,131 tokens
    contains a digit, so the ten digit slots in `ALPHABET` were never taught,
    and there is no full stop, comma, hyphen or slash in `ALPHABET` at all.

    On a form that costs 85% of the fields. On a **ledger** it costs almost
    everything: measured over five seeds of `notebook_ledger`, the checkpoint
    can write **17 of 226 runs (8%)** and 9% of the characters, because a sales
    book is amounts, dates and quantities. A page filled by the checkpoint
    alone would be nine parts typed.

    So this pairs them, per run: whatever the model will write, it writes;
    everything else goes to the typeface, which has all ten digits and every
    mark. Both are ink, so no run is left in type.

    **The two hands do not match, and this class does not pretend they do.**
    That is a real cost and it is recorded rather than hidden: `report` counts
    the runs each source inked, so a reader of the label knows which half of a
    page came from where. Making them match would need a model that is
    style-conditioned *and* writes digits, and as of this writing there is no
    such release -- VATr++, One-DM and DiffusionPen are all style-conditioned
    and all trained on IAM word crops, which do not contain digits either. See
    `docs/handwriting-html.md`.
    """

    source = "both"

    # The class the typeface half writes under. NOT `hand`, which is what the
    # model half also carries: the font rule sets a `font-size`, and the model
    # states its image width in `em`, so one rule reaching both would resize
    # the model's ink. See `FontHand.mark`.
    FONT_MARK = "hand-font"

    def __init__(self, primary=None, fallback=None, **kwargs):
        # Built here when not supplied, so `source("both")` is the same one
        # call as `source("model")` and the renderer needs no special case.
        self.primary = primary if primary is not None else Hand(**kwargs)
        self.fallback = (fallback if fallback is not None
                         else FontHand(mark=self.FONT_MARK))
        self.device = getattr(self.primary, "device", "?")

    def __enter__(self) -> "BothHands":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> "BothHands":
        self.primary.open()
        self.fallback.open()
        # After opening, not before: `Hand.device` is whatever the worker
        # reported it loaded on, and it is empty until the worker says hello.
        self.device = getattr(self.primary, "device", "?") or "?"
        return self

    def close(self) -> None:
        # Both, and the model even if the typeface throws: it owns a
        # subprocess, and leaking one per page is how a shard runs out of
        # file handles halfway through a run.
        try:
            self.fallback.close()
        finally:
            self.primary.close()

    def writable(self, text: str, page: "Page") -> bool:
        return (self.primary.writable(text, page)
                or self.fallback.writable(text, page))

    def refusal(self, text: str, page: "Page") -> str:
        """Only reached when BOTH refuse, so the typeface's reason is the one
        that matters -- the model's is already known and expected."""
        return self.fallback.refusal(text, page)

    def _matched_height(self, text: str, page: "Page") -> float | None:
        """The em height that puts the model's x-height on the typeface's.

        Without it the two halves of a page are two SIZES as well as two
        hands, which is worse than either alone. `INK_HEIGHT_EM` and
        `FontHand`'s per-face factor were each calibrated against a printed
        field, separately, and nothing ever made them agree with each other --
        measured on a `notebook_ledger` page the model's x-height came out
        about 1.5x the typeface's, and it read as a second, larger hand rather
        than as the same person.

        A tile covers `above + 1 + below` x-heights, so an em height of
        `x_height * (above + 1 + below)` is the one that lands the model's
        x-height exactly on the face's. `None` when the fallback cannot say
        what its x-height is, which leaves the model at its own size.
        """
        x_height = getattr(self.fallback, "x_height_em", None)
        if x_height is None:
            return None
        above, below = line_extent(text)
        return x_height(page) * (above + X_HEIGHT + below)

    def _count(self, page: "Page", which) -> None:
        # Keyed on the source's own name rather than on "model"/"font", so the
        # count says which source actually wrote the run whatever pair this is
        # holding.
        name = getattr(which, "source", "?")
        page.by_source[name] = page.by_source.get(name, 0) + 1

    def span(self, kind: str, classes: str, text: str, page: "Page") -> str:
        if self.primary.writable(text, page):
            try:
                height = self._matched_height(text, page)
                out = (self.primary.span(kind, classes, text, page)
                       if height is None else
                       self.primary.span(kind, classes, text, page,
                                         height_em=height))
                self._count(page, self.primary)
                return out
            except ValueError:
                # The model refused a run its own policy allowed. Fall through
                # rather than lose the run: the typeface can write it, and the
                # disagreement is counted below like any other fallback.
                pass
        out = self.fallback.span(kind, classes, text, page)
        self._count(page, self.fallback)
        return out

    def css(self, page: "Page") -> str:
        return self.primary.css(page) + self.fallback.css(page)


class HybridHand:
    """WriteViT where it can write, the typeface where it cannot -- per WORD.

    `BothHands` makes this choice per field: a run with one digit anywhere in
    it is typed in full, because mixing sources inside one labelled run would
    split a ground-truth box in two -- see the module docstring's "per field"
    policy. This goes one step further and mixes them anyway, inside a single
    field, by compositing both into the one image `Hand` alone would have
    produced rather than writing mixed markup: `"3.920.000 đồng"` comes back
    as one `<img>` with `đồng` in the model's ink and the digits in the
    typeface's. See `hybrid_line` for the actual per-word decision.

    Built for `tools/visualize/`'s side-by-side comparison against
    `BothHands`, and **not** wired into any renderer's `--handwriting` flag --
    doing that is real production wiring outside what this class answers,
    which is only "does the finer split look worth it".
    """

    source = "hybrid"

    def __init__(self, primary=None, fallback=None, **kwargs):
        # Built here when not supplied, so `source("hybrid")` is one call, the
        # same as `source("model")` -- see `BothHands.__init__`.
        self.primary = primary if primary is not None else Hand(**kwargs)
        self.fallback = fallback if fallback is not None else FontHand()
        self.device = getattr(self.primary, "device", "?")

    def __enter__(self) -> "HybridHand":
        return self.open()

    def __exit__(self, *exc) -> None:
        self.close()

    def open(self) -> "HybridHand":
        self.primary.open()
        self.fallback.open()
        self.device = getattr(self.primary, "device", "?") or "?"
        return self

    def close(self) -> None:
        try:
            self.fallback.close()
        finally:
            self.primary.close()

    def writable(self, text: str, page: "Page") -> bool:
        # The typeface is the ceiling, exactly as in `BothHands`: it checks
        # every character in the whole run against its cmap, which is the
        # same condition as "every word is coverable by one engine or the
        # other" -- whatever it cannot draw, no per-word split rescues either,
        # since `hybrid_line` falls back to this same source per word.
        return self.fallback.writable(text, page)

    def refusal(self, text: str, page: "Page") -> str:
        return self.fallback.refusal(text, page)

    def span(self, kind: str, classes: str, text: str, page: "Page") -> str:
        image, _boxes = hybrid_line(text, self.primary, self.fallback, page)
        png = ink_png(image, page.pen)
        return ink_span(kind, classes, text, png, image.size,
                        page.height_em, page.sit())

    def css(self, page: "Page") -> str:
        # No extra font-face rule needed, unlike `BothHands`: every word here
        # is rasterized into the one image, none stays live text.
        return CSS


def hybrid_line(text: str, hand: "Hand", font: "FontHand",
                page: "Page") -> tuple["object", list[dict]]:
    """One run, word by word: the model's ink where it can write, the
    typeface's where it cannot -- composited into one image, not two markups.

    Batches every model-writable word into one `hand.tiles()` call rather than
    asking word by word, for the same reason `Hand.line` always did: one
    round trip to the WriteViT worker per run, not one per word.

    Returns the image and, per word, which engine drew it and where it landed
    in the final image -- `HybridHand.span()` uses the image alone and drops
    the rest; `tools/visualize/` uses both, for the per-word overlay its
    comparison tab draws. Raises if neither engine can write a single word in
    `text`, which `HybridHand.writable()` guards against for `fill()`'s own
    caller but not for one that calls this directly.
    """
    words = words_of(text)
    model_words = [word for word in words if writable_word(word)]
    tiles = hand.tiles(model_words, page.writer, page.seed) if model_words else {}

    pairs: list[tuple[str, object]] = []
    engine_of: list[str] = []
    skipped: list[dict] = []
    for word in words:
        if word in tiles:
            pairs.append((word, tiles[word]))
            engine_of.append("model")
        elif font.writable(word, page):
            pairs.append((word, font_tile(word, font.face_for(page))))
            engine_of.append("font")
        else:
            skipped.append({"word": word, "engine": "skipped",
                            "reason": font.refusal(word, page)})

    if not pairs:
        raise ValueError(f"neither source can write any word in {text!r}")

    image, placements = compose_with_boxes(pairs)
    report = [{"word": word, "engine": engine, **box}
             for (word, _tile), engine, box in zip(pairs, engine_of, placements)]
    return image, report + skipped


def model_of(hand):
    """The WriteViT worker inside a source, or None if there is not one.

    `--signature model` traces the checkpoint's own ink, and borrows the worker
    the page is already writing with rather than standing up a second one: an
    11 s load and 294 MB of weights, twice, for one checkpoint. `BothHands`
    keeps its worker one layer down, so the borrow has to reach through it --
    otherwise `--handwriting both --signature model` quietly pays twice.
    """
    if getattr(hand, "source", "") == "model":
        return hand
    inner = getattr(hand, "primary", None)
    return inner if getattr(inner, "source", "") == "model" else None


def _compose_layout(pairs: list) -> tuple["object", list[dict]]:
    """The layout math shared by `compose` and `compose_with_boxes`.

    See `compose` for why it works the way it does. Returns each word's
    `(left, top, width, height)` in the finished image alongside it, which
    `compose` throws away and `compose_with_boxes`/`hybrid_line` need.
    """
    from PIL import Image

    metrics = [extent(word) for word, _ in pairs]
    top = max(above for above, _ in metrics)
    drop = max(below for _, below in metrics)
    # No tile may be DOWNSCALED, and that is the whole of this line.
    #
    # The obvious reference -- "a word using the full band keeps the native
    # 32 px" -- is wrong, because most words do not use the full band. `Chu Văn
    # Lâm` has no descender at all, so under that rule the whole line came out
    # 25 px, and the browser then scaled it back up to the ~35 px the field
    # gives it: a downscale followed by an upscale, which is where the ink lost
    # its edge. Measured on one field, mean stroke value went from 91 in the
    # generator's own output to 133 on the page.
    #
    # Taking the maximum of `height / extent` instead means the word that would
    # have shrunk most keeps its pixels and every other tile is upscaled. A
    # Composing ABOVE the display size and letting the browser scale down was
    # tried too, on the theory that downscaling keeps a harder edge. Measured at
    # 1x, 2x, 3x and 4x it moved the mean stroke value by 7 points with no
    # ordering -- noise, not signal, because the source is 32 px and the field
    # gives it 35. It is not here.
    unit = max(tile.height / max(above + X_HEIGHT + below, 0.01)
               for (_, tile), (above, below) in zip(pairs, metrics))

    scaled = []
    for (_, tile), (above, below) in zip(pairs, metrics):
        height = max(int(round((above + X_HEIGHT + below) * unit)), 1)
        width = max(int(round(tile.width * height / tile.height)), 1)
        scaled.append((tile.resize((width, height), Image.LANCZOS), above))

    # `WORD_GAP` is quoted on the generator's own 32 px body, so it follows the
    # scale rather than staying 14 px of a now-much-taller line.
    gap = max(int(round(WORD_GAP * unit * (ABOVE_TALL + X_HEIGHT + BELOW_TAIL) / 32)), 1)
    canvas = Image.new(
        "L",
        (sum(tile.width for tile, _ in scaled) + gap * (len(scaled) - 1),
         max(int(round((top + X_HEIGHT + drop) * unit)), 1)),
        255,
    )
    x = 0
    placements = []
    for (word, _tile), (tile, above) in zip(pairs, scaled):
        top_px = int(round((top - above) * unit))
        canvas.paste(tile, (x, top_px))
        placements.append({"left": x, "top": top_px,
                           "width": tile.width, "height": tile.height})
        x += tile.width + gap
    return canvas, placements


def compose(pairs: list) -> "object":
    """Word tiles laid out in a row, each at its own size, on one baseline.

    The unit throughout is the x-height. A tile covers `above + 1 + below` of
    them, so scaling it to `(above + 1 + below) * UNIT` px puts every word's
    x-height at the same size; placing its top at `(top - above) * UNIT` puts
    every word's baseline on the same rule.
    """
    return _compose_layout(pairs)[0]


def compose_with_boxes(pairs: list) -> tuple["object", list[dict]]:
    """`compose`, plus each word's placement in the finished image.

    For `hybrid_line`, which has to say which pixels came from which engine --
    `compose` alone pastes every tile down and forgets where.
    """
    return _compose_layout(pairs)


def font_tile(word: str, face: tuple[str, str, float], *,
             directory: Path = HAND_FONT_DIR) -> "object":
    """One word, drawn with a handwriting typeface, as a grayscale tile.

    Matches the convention `compose()` expects of a WriteViT tile: white
    background, dark ink, cropped to the glyphs' own bounding box. Tight
    cropping is what makes this drop into `compose()` unchanged -- it sizes
    every tile off `extent()`, a function of the word's *letters*, not of how
    many source pixels it started with, so all that has to be true of the
    pixels themselves is that the ink is present and not padded. `hybrid_line`
    is the only caller; `face` is whatever `FontHand.face_for(page)` returns.
    """
    from PIL import Image, ImageDraw, ImageFont

    _name, filename, _size = face
    font = ImageFont.truetype(str(Path(directory) / filename), FONT_TILE_PX)
    # A 1x1 scratch canvas only to measure: `textbbox` already accounts for a
    # font's own ascenders and descenders, which is exactly what "tight" means
    # here -- there is no separate metric to crop against.
    box = ImageDraw.Draw(Image.new("L", (1, 1))).textbbox((0, 0), word, font=font)
    width, height = max(box[2] - box[0], 1), max(box[3] - box[1], 1)
    canvas = Image.new("L", (width, height), 255)
    ImageDraw.Draw(canvas).text((-box[0], -box[1]), word, font=font, fill=0)
    return canvas


def ink_png(line, pen: tuple[int, int, int]) -> bytes:
    """Grayscale-on-white -> the pen's colour on transparent paper.

    `alpha = 255 - value`, which `docs/writevit.md` names as the one way to
    composite this ink: the generator's background is white, so pasting the
    tile over the page would print a white block with the field's rule and
    whatever else is under it wiped out.
    """
    import numpy as np
    from PIL import Image

    grey = np.asarray(line, dtype=np.uint8)
    # Ink saturates paper: a fibre half-covered by a ballpoint is darker than
    # half-covered paint. `INK_GAMMA` below 1 bends partial coverage towards
    # opaque, which is what keeps a 32 px stroke reading as a stroke once the
    # browser has resampled it into a 35 px field.
    alpha = 255.0 * np.power((255.0 - grey) / 255.0, INK_GAMMA)
    alpha = alpha.astype(np.uint8)
    rgba = np.zeros(grey.shape + (4,), dtype=np.uint8)
    rgba[..., 0], rgba[..., 1], rgba[..., 2] = pen
    rgba[..., 3] = alpha
    buffer = io.BytesIO()
    Image.fromarray(rgba, mode="RGBA").save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def ink_span(kind: str, classes: str, text: str, png: bytes,
             size: tuple[int, int], height_em: float = 2.1,
             sit_em: float = SIT_EM) -> str:
    """The `<span data-kind>` an inked run becomes.

    Width is stated in `em` and height is left to follow, so a field narrower
    than the writing scales the whole hand down instead of compressing it
    sideways -- which is what `height` plus `max-width` would do.
    """
    width, tall = size
    width_em = height_em * width / max(tall, 1)
    # `vertical-align` moves the image's BOTTOM edge relative to the baseline,
    # so the whole placement is this one number: the box hangs `sit_em` below
    # the line the value would have been printed on.
    style = f"width:{width_em:.2f}em;vertical-align:{-sit_em:.3f}em;"
    existing = re.search(r'class="([^"]*)"', classes)
    cls = ((existing.group(1) + " ") if existing else "") + "hand"
    data = base64.b64encode(png).decode("ascii")
    return (f'<span data-kind="{html.escape(kind)}" class="{cls}" '
            f'data-text="{html.escape(text, quote=True)}">'
            f'<img alt="{html.escape(text, quote=True)}" style="{style}" '
            f'src="data:image/png;base64,{data}"></span>')


def _check_contract(markup: str) -> None:
    """Every labelled run must be text-only, or the pattern above is wrong.

    Cheap, and it fails at the seam rather than three steps downstream as a
    field that quietly refused to be inked.
    """
    for match in re.finditer(r'<span data-kind="[^"]+"[^>]*>', markup):
        rest = markup[match.end():match.end() + 4000]
        end = rest.find("</span>")
        if end == -1 or "<" in rest[:end]:
            raise RuntimeError(
                "a labelled run contains markup; handwriting.RUN cannot match it. "
                f"Near: {markup[match.start():match.start() + 120]!r}")


def fill(markup: str, hand: Hand, *, seed: int = 0,
         kinds: tuple[str, ...] | str = HAND_KINDS) -> tuple[str, dict]:
    """Fill in the form: the runs a person writes, written.

    Returns the markup and a report of what was inked and what refused, which
    the renderer puts in the record. A page that claims to be hand-filled and
    has one inked field is a fact about the checkpoint, not a rounding error,
    and it belongs in the label rather than in a log line nobody keeps.
    """
    _check_contract(markup)
    page = Page(seed)
    every = kinds == ALL_KINDS
    report = {"source": getattr(hand, "source", "model"), "writer": page.writer,
              "pen": page.pen_hex, "height_em": round(page.height_em, 3),
              # Which runs were offered to the pen at all. Without it, a page
              # reading "3 inked, 40 printed" cannot be told from one where the
              # other 40 were never a person's to write.
              "kinds": "all" if every else list(kinds),
              "inked": [], "printed": {}}

    def replace(match: re.Match) -> str:
        kind, classes, escaped = match.group(1), match.group(2), match.group(3)
        text = html.unescape(escaped)
        if not text.strip() or not (every or kind in kinds):
            return match.group(0)
        if not hand.writable(text, page):
            reason = hand.refusal(text, page)
            report["printed"][reason] = report["printed"].get(reason, 0) + 1
            return match.group(0)
        try:
            drawn = hand.span(kind, classes, text, page)
        except ValueError as error:
            # The source refused a run the policy thought fine. Keep the page
            # -- printed -- and record it, because it means these two disagree
            # and that is worth seeing rather than crashing a shard over.
            report["printed"]["worker:" + str(error)[:40]] = 1
            return match.group(0)
        report["inked"].append({"kind": kind, "text": text})
        return drawn

    filled = RUN.sub(replace, markup)
    if page.by_source:
        # Only `BothHands` fills this in, and only it needs to: a single source
        # inked everything in `inked` and saying so twice would invite the two
        # numbers to disagree.
        report["by_source"] = dict(sorted(page.by_source.items()))
    if report["inked"]:
        filled = filled.replace("</style>", hand.css(page) + "</style>", 1)
    return filled, report


def main() -> int:
    """Write one line of handwriting to a PNG, to look at the seam on its own.

        generators/html/.venv/bin/python generators/html/handwriting.py \\
            --text "Ba triệu chín trăm nghìn đồng" --out /tmp/ink.png
    """
    import argparse

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--text", required=True)
    parser.add_argument("--writer", type=int, default=30)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--out", default="ink.png")
    parser.add_argument("--pen", default="#1c2a68")
    args = parser.parse_args()

    if not writable(args.text):
        print(f"not writable ({refusal(args.text)}): {args.text}", file=sys.stderr)
        return 1
    pen = tuple(int(args.pen.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4))
    with Hand() as hand:
        line = hand.line(args.text, args.writer, args.seed)
    Path(args.out).write_bytes(ink_png(line, pen))
    print(f"{args.out}  {line.width}x{line.height}")
    return 0


SOURCES = {"model": Hand, "font": FontHand, "both": BothHands, "hybrid": HybridHand}


def source(name: str = "model", **kwargs):
    """One of the ink sources by name, unopened."""
    try:
        return SOURCES[name](**kwargs)
    except KeyError:
        raise KeyError(f"no ink source {name!r}; have "
                       + ", ".join(sorted(SOURCES))) from None


__all__ = [
    "ALL_KINDS", "ALPHABET", "CSS", "FACES", "FONT_TILE_PX", "HAND_KINDS",
    "INK_HEIGHT_EM", "PENS", "SIT_EM", "SOURCES", "BothHands", "FontHand",
    "Hand", "HybridHand", "Page", "compose", "compose_with_boxes", "extent",
    "fill", "font_tile", "hybrid_line", "ink_png", "ink_span", "line_extent",
    "model_of", "refusal", "source", "writable", "writable_word", "words_of",
]

if __name__ == "__main__":
    raise SystemExit(main())
