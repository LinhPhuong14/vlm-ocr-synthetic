"""Loading the shared corpus.

One corpus for every framework. The files are plain text so a Vietnamese
speaker can fix a wrong dish name without touching Python, and tab-separated
where a line carries more than a name (an item also carries its price range).

The corpus is split by **language** and then by **profile**. Vietnamese is the
whole of it bar one document kind: the English tax invoice prints English, so
its words live in `corpus/en/`. Everything reads through the same functions
with `lang` defaulting to Vietnamese, which is what keeps a caller that has
never heard of the second language working unchanged.
"""

from __future__ import annotations

import functools
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent / "corpus"
DEFAULT_LANG = "vi"


def languages(root: Path | str = CORPUS_ROOT) -> list[str]:
    """The language directories that exist, so nothing has to hard-code them."""
    return sorted(path.name for path in Path(root).iterdir() if path.is_dir())


def _dir(lang: str) -> Path:
    return CORPUS_ROOT / lang


def _lines(path: Path) -> list[str]:
    with open(path, "r", encoding="utf-8") as fp:
        rows = [line.strip() for line in fp]
    return [row for row in rows if row and not row.startswith("#")]


def _columns(path: Path, count: int) -> list[tuple[str, ...]]:
    """Read a tab-separated file, skipping rows with the wrong column count.

    Skipping rather than raising: a corpus is edited by hand, and one
    malformed line should cost that line, not the whole run.
    """
    out = []
    for row in _lines(path):
        parts = row.split("\t")
        if len(parts) == count:
            out.append(tuple(part.strip() for part in parts))
    return out


@functools.lru_cache(maxsize=None)
def items(profile: str, lang: str = DEFAULT_LANG) -> list[tuple[str, int, int]]:
    """(name, price_min, price_max) for a corpus profile: 'eatery', 'market'..."""
    rows = _columns(_dir(lang) / f"items_{profile}.txt", 3)
    return [(name, int(lo), int(hi)) for name, lo, hi in rows]


@functools.lru_cache(maxsize=None)
def shops(profile: str, lang: str = DEFAULT_LANG) -> list[tuple[str, ...]]:
    """Shop names: one column, or two where the profile carries a branch.

    Which it is comes from the file, not from a list of profile names in here.
    `rulebase/README.md` promises that adding a profile is three corpus files
    and nothing else; a `profile == "market"` test in this function is exactly
    the Python edit that promise rules out, and the tab is a perfectly good
    signal for what the file holds.
    """
    rows = _lines(_dir(lang) / f"shops_{profile}.txt")
    if any("\t" in row for row in rows):
        return _columns(_dir(lang) / f"shops_{profile}.txt", 2)
    return [(row,) for row in rows]


@functools.lru_cache(maxsize=None)
def footers(profile: str, lang: str = DEFAULT_LANG) -> list[str]:
    return _lines(_dir(lang) / f"footers_{profile}.txt")


@functools.lru_cache(maxsize=None)
def people(lang: str = DEFAULT_LANG) -> list[str]:
    """Personal names. A till prints none; a VAT invoice names its buyer."""
    return _lines(_dir(lang) / "people.txt")


@functools.lru_cache(maxsize=None)
def streets(lang: str = DEFAULT_LANG) -> list[str]:
    return _lines(_dir(lang) / "streets.txt")


@functools.lru_cache(maxsize=None)
def wards(lang: str = DEFAULT_LANG) -> list[tuple[str, str, str]]:
    return [tuple(row) for row in _columns(_dir(lang) / "wards.txt", 3)]  # type: ignore[misc]


@functools.lru_cache(maxsize=None)
def payments(lang: str = DEFAULT_LANG) -> list[tuple[str, str]]:
    return [tuple(row) for row in _columns(_dir(lang) / "payments.txt", 2)]  # type: ignore[misc]


# Which files a language directory has to carry, and how to read each one. The
# profiles are discovered from the filenames rather than listed, so a new
# `items_x.txt` + `shops_x.txt` + `footers_x.txt` is checked without an edit
# here -- and a set that is missing one of the three is reported.
_SHARED = {
    "streets.txt": streets,
    "wards.txt": wards,
    "payments.txt": payments,
    "people.txt": people,
}


def check(root: Path | str = CORPUS_ROOT) -> list[str]:
    """Report anything missing or empty. Used by `make check-corpus`."""
    problems: list[str] = []
    for lang in languages(root):
        directory = Path(root) / lang
        for name, load in _SHARED.items():
            if not (directory / name).exists():
                problems.append(f"{lang}/{name}: missing")
            elif not load(lang):
                problems.append(f"{lang}/{name}: no usable rows (check the tab count)")

        profiles = sorted(path.stem[len("items_"):] for path in directory.glob("items_*.txt"))
        if not profiles:
            problems.append(f"{lang}/: no items_<profile>.txt, so no profile can be built")
        for profile in profiles:
            for prefix, load in (
                ("items", items), ("shops", shops), ("footers", footers)
            ):
                path = directory / f"{prefix}_{profile}.txt"
                if not path.exists():
                    problems.append(
                        f"{lang}/{path.name}: missing, but {lang}/items_{profile}.txt "
                        f"declares the {profile!r} profile"
                    )
                elif not load(profile, lang):
                    problems.append(f"{lang}/{path.name}: no usable rows (check the tab count)")
    return problems


__all__ = [
    "CORPUS_ROOT",
    "DEFAULT_LANG",
    "check",
    "footers",
    "items",
    "languages",
    "payments",
    "people",
    "shops",
    "streets",
    "wards",
]
