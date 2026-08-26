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

import yaml

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
def catalogue(name: str, lang: str = DEFAULT_LANG) -> list[tuple[str, int, int]]:
    """(name, price_min, price_max), same shape as `items` and NOT a profile.

    A profile is a whole kind of document -- it needs a shop to issue it and a
    footer to end it, and `check()` says so. A catalogue is a *part* of one: the
    hospital bill draws its lines from eight of them, one per numbered block of
    the form, and there is no such thing as a shop that issues only laboratory
    tests. Naming them apart is what keeps `check()` from demanding sixteen
    files that would mean nothing.
    """
    rows = _columns(_dir(lang) / f"catalogue_{name}.txt", 3)
    return [(text, int(lo), int(hi)) for text, lo, hi in rows]


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


@functools.lru_cache(maxsize=None)
def periodical(kind: str, lang: str = DEFAULT_LANG) -> list[dict]:
    """A pool of fixed, hand-authored units for one periodical composition.

    A newspaper article or a Q&A transcript is a nested shape -- a headline
    plus a list of paragraphs, a list of question/answer pairs -- not a row
    of tab-separated columns, so this reads YAML rather than `.txt`. Variety
    works the same way it does everywhere else in this corpus: the sampler
    draws one fixed unit from the pool rather than generating new sentences
    (see `rulebase/documents/authorisation_letter.yaml`'s `notes:` for the
    same pattern applied to one document's declaration text).

    Named `periodical_<kind>.yaml` rather than `items_periodical.txt` on
    purpose: `check()`'s profile discovery globs `items_*.txt` and then
    demands a matching `shops_*`/`footers_*` pair for whatever it finds,
    which makes no sense for a newspaper page that has neither.
    """
    path = _dir(lang) / f"periodical_{kind}.yaml"
    with open(path, "r", encoding="utf-8") as fp:
        rows = yaml.safe_load(fp)
    if not isinstance(rows, list):
        raise ValueError(f"{path}: expected a YAML list of entries")
    return rows


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

        kinds = sorted(path.stem[len("periodical_"):]
                       for path in directory.glob("periodical_*.yaml"))
        for kind in kinds:
            path = directory / f"periodical_{kind}.yaml"
            try:
                rows = periodical(kind, lang)
            except ValueError as error:
                problems.append(str(error))
                continue
            if not rows:
                problems.append(f"{lang}/{path.name}: no usable rows")
            elif not all(isinstance(row, dict) and row for row in rows):
                problems.append(f"{lang}/{path.name}: every entry must be a non-empty mapping")
    return problems


__all__ = [
    "CORPUS_ROOT",
    "DEFAULT_LANG",
    "catalogue",
    "check",
    "footers",
    "items",
    "languages",
    "payments",
    "people",
    "periodical",
    "shops",
    "streets",
    "wards",
]
