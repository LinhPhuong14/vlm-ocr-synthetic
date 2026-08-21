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
because the stroke shapes were still a typeface's. Every mark this module puts
on a page comes out of the WriteViT generator, or the field stays printed. There
is no fallback that draws letters, and adding one would put the repository back
where that commit found it.

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


def writable(text: str) -> bool:
    """Can the checkpoint write this whole run? See the module docstring."""
    words = words_of(text)
    if not words:
        return False
    for word in words:
        if any(character.isdigit() for character in word):
            return False
        if len(word) > 1 and word.isupper():
            return False
        if any(character not in ALPHABET_SET for character in word):
            return False
    return True


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


class Hand:
    """One long-lived WriteViT worker, and the ink it has already written.

    Kept alive across a run for the same reason `HtmlReceiptRenderer` keeps one
    browser: a cold load is 11 s on CPU and almost all of it is the checkpoint
    and the 193 MB style pickle. The cache is keyed on `(writer, word)` because
    a corpus repeats -- "Nguyễn", "Chuyển khoản", "triệu" -- and one person
    writes the same word much the same way twice.
    """

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

    def line(self, text: str, writer: int, seed: int):
        """One run of text as a single grayscale image, words laid out in a row.

        The gap between words is the caller's to set and always was -- WriteViT
        generates one word at a time and says nothing about spacing.
        """
        words = words_of(text)
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

        tiles = [self._cache[(writer, word)] for word in words]
        return compose(list(zip(words, tiles)))

    def ink(self, text: str, writer: int, seed: int,
            pen: tuple[int, int, int]) -> tuple[bytes, tuple[int, int]]:
        """The run as a PNG in the pen's colour, and its size in pixels.

        The only method `fill` calls, and the reason it is here rather than
        inlined there: `fill` decides what a page says and should not have to
        hold a PIL image to do it. A test double is then four lines and needs
        neither Pillow nor a checkpoint.
        """
        line = self.line(text, writer, seed)
        return ink_png(line, pen), line.size


def compose(pairs: list) -> "object":
    """Word tiles laid out in a row, each at its own size, on one baseline.

    The unit throughout is the x-height. A tile covers `above + 1 + below` of
    them, so scaling it to `(above + 1 + below) * UNIT` px puts every word's
    x-height at the same size; placing its top at `(top - above) * UNIT` puts
    every word's baseline on the same rule.
    """
    from PIL import Image

    metrics = [extent(word) for word, _ in pairs]
    top = max(above for above, _ in metrics)
    drop = max(below for _, below in metrics)
    # One tile's own height, in px, is the reference: a word using the full
    # band keeps the generator's native 32 px and nothing is upscaled beyond it.
    unit = max(tile.height for _, tile in pairs) / (ABOVE_TALL + X_HEIGHT + BELOW_TAIL)

    scaled = []
    for (_, tile), (above, below) in zip(pairs, metrics):
        height = max(int(round((above + X_HEIGHT + below) * unit)), 1)
        width = max(int(round(tile.width * height / tile.height)), 1)
        scaled.append((tile.resize((width, height), Image.LANCZOS), above))

    canvas = Image.new(
        "L",
        (sum(tile.width for tile, _ in scaled) + WORD_GAP * (len(scaled) - 1),
         max(int(round((top + X_HEIGHT + drop) * unit)), 1)),
        255,
    )
    x = 0
    for tile, above in scaled:
        canvas.paste(tile, (x, int(round((top - above) * unit))))
        x += tile.width + WORD_GAP
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
    alpha = 255 - grey
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
         kinds: tuple[str, ...] = HAND_KINDS) -> tuple[str, dict]:
    """Fill in the form: the runs a person writes, written.

    Returns the markup and a report of what was inked and what refused, which
    the renderer puts in the record. A page that claims to be hand-filled and
    has one inked field is a fact about the checkpoint, not a rounding error,
    and it belongs in the label rather than in a log line nobody keeps.
    """
    _check_contract(markup)
    rng = random.Random(seed ^ 0x48414E44)
    # One person fills one form: one writer index, one pen and one size of
    # writing for the whole page. Only where on the rule each line lands is
    # drawn per field, because that is the part a person does not hold steady.
    writer = rng.randrange(106)
    pen = rng.choices([colour for colour, _ in PENS],
                      [weight for _, weight in PENS])[0]
    height_em = rng.uniform(*INK_HEIGHT_EM)

    report = {"writer": writer, "pen": "#%02x%02x%02x" % pen,
              "height_em": round(height_em, 3), "inked": [], "printed": {}}

    def replace(match: re.Match) -> str:
        kind, classes, escaped = match.group(1), match.group(2), match.group(3)
        text = html.unescape(escaped)
        if kind not in kinds or not text.strip():
            return match.group(0)
        if not writable(text):
            reason = refusal(text)
            report["printed"][reason] = report["printed"].get(reason, 0) + 1
            return match.group(0)
        try:
            png, size = hand.ink(text, writer, seed, pen)
        except ValueError as error:
            # The worker refused a word the policy thought fine. Keep the page
            # -- printed -- and record it, because it means these two disagree
            # and that is worth seeing rather than crashing a shard over.
            report["printed"]["worker:" + str(error)[:40]] = 1
            return match.group(0)
        report["inked"].append({"kind": kind, "text": text})
        sit = SIT_EM + rng.uniform(-SIT_JITTER_EM, SIT_JITTER_EM)
        return ink_span(kind, classes, text, png, size, height_em, sit)

    filled = RUN.sub(replace, markup)
    if report["inked"]:
        filled = filled.replace("</style>", CSS + "</style>", 1)
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


__all__ = [
    "ALPHABET", "CSS", "HAND_KINDS", "INK_HEIGHT_EM", "PENS", "SIT_EM", "Hand",
    "compose", "extent", "fill", "ink_png", "ink_span", "refusal", "writable",
    "words_of",
]

if __name__ == "__main__":
    raise SystemExit(main())
