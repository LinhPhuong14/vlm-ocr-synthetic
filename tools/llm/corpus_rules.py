"""What a corpus line has to be before it is allowed into `rulebase/corpus/`.

Separate from the generator that calls it, and importable without a model
running, because this is the half worth testing: the model proposes, and these
rules are the only thing between it and the dataset.

## The shapes are measured, not chosen -- and the first attempt was wrong

Every number in `SHAPES` below comes from `python -m tools.llm.corpus_rules
--audit`, which walks the committed corpus and prints what it actually
contains. That command is also the test of these rules, and it is the point:

**a rule that rejects a line a person already wrote is a broken rule.**

The first version of this file guessed instead, and the audit threw out **354
of 737 committed lines, 48 %**. Every one of those was the rule being wrong:

* *"has characters this corpus does not use"* -- 184 lines. The character check
  walked a name letter by letter and normalised each one to NFD, so a combining
  mark met on its own decomposed to itself and failed the Latin test. It was
  rejecting Vietnamese for being Vietnamese.
* *"ALL CAPS"* -- 56 lines. `CẢM ƠN QUÝ KHÁCH VÀ HẸN GẶP LẠI` is what a footer
  is, and 55 % of shop names are shouted on the real receipts they came from.
  Caps is a per-family fact, not a rule.
* *"no Vietnamese diacritic"* -- 43 lines. `Natri Clorid 0,9%` is a real drug
  name with no diacritic in it. Per line the rule is simply false; what it was
  reaching for -- "the model answered in the wrong language" -- is a property
  of a whole batch, and that is where it now lives (`foreign_batch`).
* *"prices must be integers"* -- 29 lines. `wards.txt` is three columns of
  ward, district and city. Three columns does not mean prices.
* the rest were bounds set from a glance at one file: a real drug is called
  `Ama-Power` in one word, a hospital bed line runs to 122 characters, and a
  hotel's `Tiền phòng` really does span 450k to 3.2M.

Fixing those took it to **209 of 828, 25.2 %** -- and the whole of that second
round was one character. `đ` and `Đ` do not decompose under NFD, because the
bar through the stem is part of the letter rather than an accent, so a Latin
test written as a range threw out every Vietnamese word containing the most
Vietnamese letter there is. `_letters_ok` says how that is tested now.

The audit is **0 of 828** and the command exits non-zero if it ever is not, so
the next person to add a rule finds out immediately whether they have written a
rule or a bug.

## What this does not do

It does not repair a line. A validator that fixed up its input would be a
validator that let a bad line through wearing a hat -- and the repaired line
would then carry a provenance stamp saying a model wrote it, which would be
false in a way nobody could see.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parents[2] / "rulebase" / "corpus"

# The marks the committed corpus actually uses, from --audit. An em-dash, a
# smart quote or a stray asterisk is a chat model's formatting leaking into the
# data, and the page would print it.
PUNCTUATION = set("!\"%&'()+,-./:;[]")

# How far outside the measured envelope a proposed line may sit. The corpus
# should be able to grow past its own extremes -- it is 737 lines, not a
# definition of Vietnamese -- but a name three times longer than anything ever
# written is a paragraph, not a name.
SLACK = 1.5


@dataclass(frozen=True)
class Shape:
    """One family of corpus file, as the committed files actually are.

    The **structural** facts only -- how many columns, whether two of them are
    a price band, whether the names are shouted. Those are properties of a
    family: every `items_*.txt` is three columns whatever it sells.

    The size of a name is not. `items_market` runs to `Nước mắm Nam Ngư 500ml`
    and `items_eatery` is full of `Phở gà` and `Bún chả`, and a single envelope
    over both either rejects the dish or waves through a bare noun on a
    supermarket line. So `envelope()` measures each FILE, and measures only the
    lines a person wrote -- see there.
    """

    columns: tuple[int, ...]      # column counts seen; `shops` has both 1 and 2
    prices: bool                  # are columns 2 and 3 a price band?
    caps: bool                    # may the first column be ALL CAPS?
    note: str = ""


# Printed by `--audit`, which walks the committed corpus. Structural only: the
# size of a name is measured per file by `envelope()`.
SHAPES: dict[str, Shape] = {
    "items":     Shape((3,), True,  False,
                       "till lines: name, then the band a unit sells for"),
    "catalogue": Shape((3,), True,  False,
                       "a hospital bill's blocks; the longest names in the corpus"),
    "shops":     Shape((1, 2), False, True,
                       "55% are shouted on the receipts they were copied from"),
    "footers":   Shape((1,), False, True, "a slogan, and slogans are shouted"),
    "people":    Shape((1,), False, False, "full Vietnamese names"),
    "streets":   Shape((1,), False, False, ""),
    "wards":     Shape((3,), False, False,
                       "ward, district, city -- three columns and NOT prices"),
    "payments":  Shape((2,), False, True, ""),
}


@dataclass(frozen=True)
class Envelope:
    """How long a name in ONE COLUMN of ONE file may be, measured off that file.

    Three decisions worth stating, each of them learned from the audit going
    red rather than reasoned out in advance.

    **Per file, not per family.** `Phở gà` is a real menu line and `Sữa` is not
    a real supermarket line, and no single word count separates them. The file
    each belongs to does.

    **Per column.** `shops_market.txt` is a chain and a branch, and the branch
    is the longer of the two: `WinMart` beside `WM Trung Hoà Nhân Chính`.
    Holding column two to column one's measurement rejected four real branches.

    **Measured over the lines a PERSON wrote**, via `provenance.human`. If
    generated lines counted, every round would widen the envelope a little and
    the tenth round would be checked against the ninth round's mistakes -- a
    validator slowly ratifying its own drift. Anchoring to the human lines
    means the model stays inside what people actually wrote, however many
    rounds have run.
    """

    words: tuple[int, int]
    length: tuple[int, int]
    sampled: int

    def widest(self) -> tuple[int, int]:
        return (max(1, int(self.words[0] / SLACK)), int(self.words[1] * SLACK))

    def longest(self) -> tuple[int, int]:
        return (max(1, int(self.length[0] / SLACK)), int(self.length[1] * SLACK))


# What a column with too few human lines to measure is held to. Wide on
# purpose: a floor derived from three examples is not a measurement, and the
# structural rules -- columns, charset, prices, duplicates -- do the work.
FALLBACK = Envelope((1, 24), (2, 140), 0)
MIN_SAMPLE = 8


def envelopes(text: str) -> dict[int, Envelope]:
    """One envelope per text column of a corpus file, from its human lines.

    Price columns get none: they are checked as numbers, and a digit string's
    "word count" means nothing.
    """
    from tools.llm.provenance import human  # noqa: PLC0415 -- avoids a cycle

    columns: dict[int, list[str]] = {}
    for line in human(text):
        for index, cell in enumerate(line.split("\t")):
            if cell.strip() and not cell.strip().isdigit():
                columns.setdefault(index, []).append(cell)
    out: dict[int, Envelope] = {}
    for index, cells in columns.items():
        if len(cells) < MIN_SAMPLE:
            out[index] = FALLBACK
            continue
        words = [len(cell.split()) for cell in cells]
        lengths = [len(cell) for cell in cells]
        out[index] = Envelope((min(words), max(words)),
                              (min(lengths), max(lengths)), len(cells))
    return out


def envelope(text: str, column: int = 0) -> Envelope:
    """One column's envelope, `FALLBACK` when that column was never measured."""
    return envelopes(text).get(column, FALLBACK)


# Measured over items and catalogue together. The spread ceiling is 15.11x --
# `Tiền phòng` at a hotel, 450k to 3.2M -- and it is a real range, so the
# ceiling is that with slack rather than the 6x a glance suggested.
PRICE_MIN, PRICE_MAX = 340, 45_000_000
SPREAD_MAX = 16.0

# An insurance sum is not a purchase price: a travel benefit cap and a
# factory's rebuild cost are both real, both `catalogue`-shaped, and four
# orders of magnitude apart -- neither fits the 340..45M band this file's own
# comment says was measured over retail items and a hospital bill's line
# items. Filed as its own, much wider band rather than raising `PRICE_MAX`
# globally, which would silently stop catching a garbled retail price too.
INSURANCE_PRICE_MIN, INSURANCE_PRICE_MAX = 300, 40_000_000_000

# How many digits a bare-number cell may have outside a price column. Two: a
# Vietnamese district is `1` or `12`, and anything longer in a name column is
# an id somebody pasted where a word goes.
DISTRICT_DIGITS = 2


def family_of(stem: str) -> str:
    """`items_market` -> `items`. The file's family decides its shape."""
    return stem.split("_")[0]


def shape_of(stem: str) -> Shape:
    family = family_of(stem)
    if family not in SHAPES:
        raise KeyError(
            f"no shape for corpus family {family!r} (file {stem}); "
            f"have {', '.join(sorted(SHAPES))}. Measure it with --audit and add it "
            "rather than letting an unmeasured file through unchecked.")
    return SHAPES[family]


@dataclass(frozen=True)
class Rejected:
    line: str
    why: str


def _letters_ok(text: str) -> bool:
    """Latin, digits, the corpus's own punctuation, and combining marks.

    Two clauses that both had to be learned from the audit rather than reasoned
    out, and both about Vietnamese specifically:

    * **combining marks.** Vietnamese may be stored decomposed, so `ề` can
      arrive as two characters and the second is a mark with no base of its
      own. Guessing otherwise rejected 184 committed lines.
    * **`đ` and `Đ`.** `NFD` does not decompose them -- the bar through the
      stem is part of the letter, not a combining accent -- so a check written
      as `"a" <= base <= "z"` throws out every Vietnamese word containing the
      most Vietnamese letter there is. That rejected another 209.

    Hence the test is Unicode's own name for the character rather than a range:
    `LATIN SMALL LETTER D WITH STROKE` is Latin, and so is every precomposed
    Vietnamese vowel, while Cyrillic, CJK and emoji are not.
    """
    for character in text:
        if character.isspace() or character in PUNCTUATION or character.isdigit():
            continue
        if unicodedata.combining(character):
            continue
        base = unicodedata.normalize("NFD", character)[0]
        if not unicodedata.name(base, "").startswith("LATIN"):
            return False
    return True


def check_name(name: str, shape: Shape, size: Envelope = FALLBACK) -> str:
    """'' when the name is fine, else why it is not."""
    if not name or name != name.strip():
        return "empty or padded"
    if "�" in name or "□" in name:
        return "carries a replacement or missing-glyph character"
    if not _letters_ok(name):
        bad = sorted({c for c in name if not _letters_ok(c)})
        return f"has characters this corpus does not use: {''.join(bad)!r}"
    low, high = size.longest()
    if not low <= len(name) <= high:
        return f"{len(name)} characters; this file runs {low}..{high}"
    low, high = size.widest()
    if not low <= len(name.split()) <= high:
        return f"{len(name.split())} words; this file runs {low}..{high}"
    if name.isupper() and len(name.split()) > 1 and not shape.caps:
        return "ALL CAPS, and this family stores names cased"
    stutter = _repeated_phrase(name)
    if stutter:
        return f"says {stutter!r} twice in a row"
    return ""


def _repeated_phrase(name: str) -> str:
    """`Cà phê hòa tan hòa tan 250g` -> `hòa tan`. '' when there is none.

    A small model padding to a length repeats the phrase it just wrote, and
    the result reads as a product name until you read it.

    **Two words minimum, and that is not an arbitrary floor.** A single word
    repeating is ordinary Vietnamese and the audit says so: `HẢO HẢO Mì tôm
    chua cay` is a real brand and `Dịch vụ in ấn ấn phẩm quảng cáo` is `in ấn`
    followed by `ấn phẩm`. Both were rejected by the first version of this
    check, which is the same class of mistake the rest of this file is a
    catalogue of.

    Only an IMMEDIATE repeat, too: `Cà phê Trung Nguyên cà phê sữa` is a
    different and rarer mistake, and this would rather miss it than reject a
    real name with a legitimate echo in it.
    """
    words = name.split()
    for size in (3, 2):
        for start in range(len(words) - 2 * size + 1):
            first = words[start:start + size]
            if first == words[start + size:start + 2 * size] and len(first[0]) > 1:
                return " ".join(first)
    return ""


def check_price(low: str, high: str, *, stem: str = "") -> str:
    if not (low.isdigit() and high.isdigit()):
        return "prices must be plain integers, no separators and no đ"
    lo, hi = int(low), int(high)
    # `catalogue_insurance_*` -- a coverage sum, not a purchase price. See
    # `INSURANCE_PRICE_MIN`/`_MAX`'s own comment.
    price_min, price_max = (
        (INSURANCE_PRICE_MIN, INSURANCE_PRICE_MAX) if "insurance" in stem
        else (PRICE_MIN, PRICE_MAX)
    )
    if not price_min <= lo <= price_max or not price_min <= hi <= price_max:
        return f"price outside {price_min}..{price_max}"
    if lo >= hi:
        return "the low price is not below the high one"
    if hi / lo > SPREAD_MAX:
        return f"the band spans more than {SPREAD_MAX:g}x, which is not a band"
    return ""


def check(line: str, shape: Shape, sizes: dict[int, Envelope] | None = None, *,
         stem: str = "") -> str:
    """One candidate line against its file's shape. '' means keep it."""
    sizes = sizes or {}
    if line != line.strip() or "\t\t" in line:
        return "padded, or an empty column"
    parts = line.split("\t")
    if len(parts) not in shape.columns:
        return (f"{len(parts)} columns; this family has "
                f"{' or '.join(str(c) for c in shape.columns)}")
    problem = check_name(parts[0], shape, sizes.get(0, FALLBACK))
    if problem:
        return problem
    if shape.prices and len(parts) == 3:
        return check_price(parts[1], parts[2], stem=stem)
    # A branch, a district, a city: measured in its own right, and never held
    # to the first column's casing -- a branch on a receipt is often shouted.
    for index, extra in enumerate(parts[1:], start=1):
        # A Vietnamese district really is called `1`. Eight rows of
        # `wards.txt` are exactly that -- `Bến Nghé  1  TPHCM` -- so a bare
        # number is a legitimate cell here, and only here: two digits is a
        # district, and a long digit string in a name column is a model
        # pasting an id where a word goes.
        if extra.isdigit() and len(extra) <= DISTRICT_DIGITS:
            continue
        problem = check_name(extra, Shape(shape.columns, False, True),
                             sizes.get(index, FALLBACK))
        if problem:
            return f"column {index + 1}: {problem}"
    return ""


def foreign_batch(lines: list[str]) -> bool:
    """Did the model answer in the wrong language?

    Per line, "has no diacritic" is simply false -- `Natri Clorid 0,9%` is a
    real drug and `Ama-Power` is a real one too. Over a batch it is the signal
    it was reaching for: a local model asked for Vietnamese sometimes answers
    in English or in unaccented Vietnamese, and when it does, *nothing* in the
    batch carries a mark.
    """
    if len(lines) < 4:
        return False
    marked = sum(
        1 for line in lines
        if any(unicodedata.combining(c)
               for c in unicodedata.normalize("NFD", line.split("\t")[0])))
    return marked == 0


def key(line: str) -> str:
    """What counts as the same entry, for dedup.

    The first column, folded: two price bands for one product is one product,
    and the corpus should not carry `Sữa tươi Vinamilk 1L` twice because a
    model gave it a different band the second time.
    """
    return " ".join(line.split("\t")[0].split()).casefold()


def sift(candidates: list[str], existing, shape: Shape,
         sizes: dict[int, Envelope] | None = None
         ) -> tuple[list[str], list[Rejected]]:
    """(kept, rejected). Order preserved; the first of a duplicate pair wins."""
    seen = {key(line) for line in existing}
    kept: list[str] = []
    thrown: list[Rejected] = []
    for line in candidates:
        problem = check(line, shape, sizes)
        if problem:
            thrown.append(Rejected(line, problem))
            continue
        if key(line) in seen:
            thrown.append(Rejected(line, "already in the corpus"))
            continue
        seen.add(key(line))
        kept.append(line)
    return kept, thrown


# ------------------------------------------------------------------- the audit


def rows_of(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def audit(root: Path = CORPUS_ROOT) -> tuple[int, list[Rejected]]:
    """Run these rules over the committed corpus. Rejections are OUR bugs."""
    total = 0
    thrown: list[Rejected] = []
    for path in sorted(root.rglob("*.txt")):
        try:
            shape = shape_of(path.stem)
        except KeyError as error:
            thrown.append(Rejected(path.name, str(error).split(";")[0]))
            continue
        text = path.read_text(encoding="utf-8")
        sizes = envelopes(text)
        for line in rows_of(path):
            total += 1
            problem = check(line, shape, sizes, stem=path.stem)
            if problem:
                thrown.append(Rejected(f"{path.name}: {line[:60]}", problem))
    return total, thrown


def main() -> int:
    import argparse
    import collections

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--audit", action="store_true",
                        help="check these rules against the committed corpus")
    args = parser.parse_args()
    if not args.audit:
        parser.error("nothing to do; --audit is the only mode")

    total, thrown = audit()
    print(f"{total} committed lines over {len(SHAPES)} families")
    counts = collections.Counter(item.why for item in thrown)
    first = {}
    for item in thrown:
        first.setdefault(item.why, item.line)
    for why, count in counts.most_common():
        print(f"  {count:4}  {why}\n        e.g. {first[why]}")
    share = 100 * len(thrown) / total if total else 0.0
    print(f"\n{len(thrown)} rejected = {share:.1f}%")
    if thrown:
        print("Every one of these is a rule that is wrong, not a line that is. "
              "See the module docstring.")
    return 1 if thrown else 0


__all__ = ["DISTRICT_DIGITS", "FALLBACK", "INSURANCE_PRICE_MAX", "INSURANCE_PRICE_MIN",
           "MIN_SAMPLE", "PRICE_MAX", "PRICE_MIN", "PUNCTUATION",
           "SHAPES", "SLACK", "SPREAD_MAX", "Envelope", "Rejected", "Shape",
           "audit", "check", "check_name", "check_price", "envelope", "envelopes",
           "family_of", "foreign_batch", "key", "rows_of", "shape_of", "sift"]

if __name__ == "__main__":
    raise SystemExit(main())
