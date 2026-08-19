"""Every check that must pass before the first image is drawn.

    python pipeline/preflight.py            # or: make preflight

A long job that dies at minute forty because of a typo'd tag has wasted forty
minutes. The bigger reason is that most failures in this repository are
*silent*: a mistyped tag does not crash, it makes that value undrawable, and
generation runs happily to the end. Weeks later someone notices a layout that
never appeared.

This gathers the checks that already exist rather than restating them --
`tools/rules_report.check()` for the rules, layouts, paper and degradation
chains, `rulebase.corpus.check()` for the corpus -- and adds the one nobody had:
glyph coverage over the text this rule-base can actually print.

Exit 0 and nothing else has anything to say. Exit 1 and every problem is listed.

A check that could not run -- a missing library rather than a broken rule --
is prefixed `unchecked:` and still fails the run. The prefix is there so a
reader can tell "your rules are wrong" from "I was unable to look"; the exit
code does not distinguish them, because a job that starts without knowing is
the thing preflight exists to prevent.
"""

from __future__ import annotations

import argparse
import sys
import time
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import yaml  # noqa: E402

import rulebase  # noqa: E402
from rulebase import corpus  # noqa: E402
from rulebase.layout import load_layout  # noqa: E402
from rulebase.spec import RuleError, load_rules  # noqa: E402
from rulebase.text import ascii_fold  # noqa: E402

FONT_ROOT = REPO_ROOT / "fonts"
LAYOUTS_ROOT = REPO_ROOT / "rulebase" / "layouts"

# Always printable regardless of what the corpus says: the separators layouts
# draw rules with, digits, the money separators, and the currency suffixes.
ALWAYS = set("0123456789 .,:-|/%()#*=~_+") | set("đĐ") | set("VND")

# Marks a problem that is "I could not look", not "this is broken". Still a
# problem, still exit 1 -- the distinction is for the reader, not the gate.
UNCHECKED = "unchecked:"


# ------------------------------------------------------------ what gets printed


def printable_text() -> set[str]:
    """Every character this rule-base can put on a page.

    Wider than the corpus, and the gap is where the bug lives:

    * `.upper()` of every entry. `rules/content.yaml` turns uppercase on with
      high probability, and `Ậ Ầ Ế Ộ Ữ` are different glyphs from their
      lowercase forms. A font checked only against lowercase passes while
      printing boxes for exactly the characters most often missing.
    * the ascii-folded form, which an old thermal till prints instead.
    * strings the rules own rather than the corpus, which by now is most of a
      document: column titles, field labels, signature captions, the summary
      block's row labels, units, payment methods, bank and port names.

    Those last are collected by walking the WHOLE of each layout file and each
    document's `params`, minus the keys that exist only for a reader. An
    allow-list of keys was what this did before, and it aged badly: every
    section added to `rulebase/layout.py` printed strings from a key the list
    had never heard of, silently, and the check went on passing. A deny-list
    fails the other way -- a new key is covered the day it is added, and the
    worst it can do is check a few ASCII identifiers nobody prints.
    """
    seen: set[str] = set(ALWAYS)

    def add(text: str) -> None:
        if not text:
            return
        seen.update(text)
        seen.update(text.upper())
        seen.update(ascii_fold(text))
        seen.update(ascii_fold(text).upper())

    for path in sorted((REPO_ROOT / "rulebase" / "corpus" / "vi").glob("*.txt")):
        for line in path.read_text(encoding="utf-8").splitlines():
            for column in line.split("\t"):
                add(column.strip())

    def walk(node) -> None:
        if isinstance(node, str):
            add(node)
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    # Layout-owned strings: everything but the three keys that are there for
    # whoever reads the file rather than for the page.
    for path in sorted(LAYOUTS_ROOT.glob("*.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        walk({key: value for key, value in spec.items()
              if key not in ("id", "name", "source")})

    # Rule-owned strings: titles, total labels, field labels, signature
    # captions, units, bank and port names -- all of `params`.
    for option in load_rules()["document"]:
        walk(option.params)
    for option in load_rules()["content"]:
        add(str(option.params.get("money_suffix", "")))
        add(str(option.params.get("money_prefix", "")))

    # Combining marks are not drawn on their own; the composed form is what a
    # cmap is asked for, and NFC has already produced it.
    return {c for c in seen if c.strip() and unicodedata.category(c) != "Mn"}


# ------------------------------------------------------------------- fonts


def font_coverage(characters: set[str]) -> list[str]:
    """Report any font in `fonts/` that cannot draw a character we may print.

    `docs/` ranks this the number-one risk and it has already bitten: DejaVu
    Sans Mono -- the obvious monospace choice -- is missing 46 of these, and a
    missing glyph renders as a box while the label still claims the character
    was printed. Nothing crashes.
    """
    try:
        from fontTools.ttLib import TTFont
    except ImportError:
        return [
            f"{UNCHECKED} fontTools is not installed, so glyph coverage was not "
            "checked. That is the highest-risk check here -- a missing glyph "
            "prints a box while the label claims the character. "
            "`pip install fonttools`."
        ]

    problems: list[str] = []
    fonts = sorted(FONT_ROOT.rglob("*.ttf")) + sorted(FONT_ROOT.rglob("*.otf"))
    if not fonts:
        return [f"no fonts in {FONT_ROOT}"]

    for path in fonts:
        try:
            cmap = TTFont(path, fontNumber=0, lazy=True).getBestCmap()
        except Exception as error:  # noqa: BLE001 - a corrupt font is a problem too
            problems.append(f"{path.relative_to(REPO_ROOT)}: unreadable ({error})")
            continue
        missing = sorted(c for c in characters if ord(c) not in cmap)
        if missing:
            shown = "".join(missing[:24])
            problems.append(
                f"{path.relative_to(REPO_ROOT)}: missing {len(missing)} glyphs "
                f"the corpus can print: {shown}"
                + (" ..." if len(missing) > 24 else "")
            )
    return problems


# A monospace advance as a fraction of the font size. The same estimate
# `generators/genalog/render.py` has always used to size its page; good to a few
# per cent for every font in `fonts/`, which is all this check needs -- it is
# looking for a page half again too tall, not for a rounding error.
ADVANCE = 0.62
SHEET_SEEDS = 12


def sheet_overflow(seeds: int = SHEET_SEEDS) -> list[str]:
    """Layouts whose content does not fit the paper they declare.

    A cut sheet's height is fixed before printing, so `style.sheet_height` only
    ever grows the page: an invoice that needs more rows than A4 has gets a
    taller-than-A4 sheet rather than a cropped one. That is the right failure --
    nothing is hidden -- but it is still a failure, and it belongs here rather
    than in a renderer, where it would be found one image at a time.

    Drawn rather than reasoned about: how many rows a page needs depends on how
    many items were sampled and how the name wrapped, so the only honest way to
    ask is to build some.
    """
    problems: list[str] = []
    for layout_id in rulebase.available_layouts():
        # Read the declaration before building anything: five of the fourteen
        # layouts are on a roll and have nothing to overflow, and building two
        # dozen pages to discover that is most of this check's cost.
        if not load_layout(layout_id).get("sheet"):
            continue
        worst = 0.0
        worst_seed = 0
        for seed in range(seeds):
            recipe, _receipt, grid = rulebase.make(
                seed=seed, force={"layout": layout_id})
            ratio = rulebase.sheet_ratio(grid)
            visual = recipe.visual.params
            size_lo, size_hi = visual.get("font_size", [22, 30])
            font_px = (size_lo + size_hi) / 2.0
            spacing_lo, spacing_hi = visual.get("line_spacing", [1.05, 1.35])
            line_px = font_px * (spacing_lo + spacing_hi) / 2.0
            pad = rulebase.padding(recipe, grid)
            width_px = (grid.ncols + pad["columns"] * 2) * font_px * ADVANCE
            content = grid.nrows * line_px + (pad["top"] + pad["bottom"]) * line_px
            over = content / (width_px / ratio)
            if over > worst:
                worst, worst_seed = over, seed
        if worst > 1.0:
            problems.append(
                f"{layout_id}: content is {worst:.0%} of the {grid.sheet} sheet it "
                f"declares (seed {worst_seed}), so the page grows past its paper"
            )
    return problems


# ------------------------------------------------------------------- checks


def check() -> list[str]:
    """Every problem, in the order a person would want to fix them."""
    problems: list[str] = []

    # Rules, layouts, papers, degradation chains -- already implemented, and
    # restating them here is how the two copies start disagreeing.
    try:
        from rules_report import check as check_rules

        problems += check_rules()
    except RuleError as error:
        # The rules are broken badly enough that they will not load, so nothing
        # downstream can be checked either. Say so and stop guessing.
        return [f"rules will not load: {error}"]

    # `rules_report` reports a missing `degradation` the same way it reports a
    # broken rule. Relabel it so the two read differently.
    problems = [f"{UNCHECKED} {p}" if "not importable" in p else p for p in problems]

    problems += [f"corpus: {problem}" for problem in corpus.check()]
    problems += font_coverage(printable_text())
    problems += sheet_overflow()
    return problems


def unchecked(problems: list[str]) -> list[str]:
    """The subset that means "a library was missing", not "this is wrong"."""
    return [problem for problem in problems if problem.startswith(UNCHECKED)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quiet", action="store_true", help="print nothing when clean")
    args = parser.parse_args()

    started = time.time()
    problems = check()
    elapsed = time.time() - started

    if problems:
        print(f"PREFLIGHT: {len(problems)} vấn đề\n")
        for problem in problems:
            print(f"  - {problem}")
        print(f"\n({elapsed:.1f}s)")
        return 1
    if not args.quiet:
        print(f"preflight sạch ({elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
