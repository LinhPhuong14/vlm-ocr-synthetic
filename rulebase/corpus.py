"""Loading the shared corpus.

One corpus for every framework. The files are plain text so a Vietnamese
speaker can fix a wrong dish name without touching Python, and tab-separated
where a line carries more than a name (an item also carries its price range).
"""

from __future__ import annotations

import functools
from pathlib import Path

CORPUS_ROOT = Path(__file__).resolve().parent / "corpus" / "vi"


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
def items(profile: str) -> list[tuple[str, int, int]]:
    """(name, price_min, price_max) for a corpus profile: 'eatery' or 'market'."""
    rows = _columns(CORPUS_ROOT / f"items_{profile}.txt", 3)
    return [(name, int(lo), int(hi)) for name, lo, hi in rows]


@functools.lru_cache(maxsize=None)
def shops(profile: str) -> list[tuple[str, ...]]:
    """Shop names. 'eatery' gives bare names, 'market' gives (brand, branch)."""
    path = CORPUS_ROOT / f"shops_{profile}.txt"
    return _columns(path, 2) if profile == "market" else [(n,) for n in _lines(path)]


@functools.lru_cache(maxsize=None)
def footers(profile: str) -> list[str]:
    return _lines(CORPUS_ROOT / f"footers_{profile}.txt")


@functools.lru_cache(maxsize=None)
def streets() -> list[str]:
    return _lines(CORPUS_ROOT / "streets.txt")


@functools.lru_cache(maxsize=None)
def wards() -> list[tuple[str, str, str]]:
    return [tuple(row) for row in _columns(CORPUS_ROOT / "wards.txt", 3)]  # type: ignore[misc]


@functools.lru_cache(maxsize=None)
def payments() -> list[tuple[str, str]]:
    return [tuple(row) for row in _columns(CORPUS_ROOT / "payments.txt", 2)]  # type: ignore[misc]


def check() -> list[str]:
    """Report anything missing or empty. Used by `make check-corpus`."""
    problems = []
    expected = {
        "items_eatery.txt": lambda: items("eatery"),
        "items_market.txt": lambda: items("market"),
        "shops_eatery.txt": lambda: shops("eatery"),
        "shops_market.txt": lambda: shops("market"),
        "footers_eatery.txt": lambda: footers("eatery"),
        "footers_market.txt": lambda: footers("market"),
        "streets.txt": streets,
        "wards.txt": wards,
        "payments.txt": payments,
    }
    for name, load in expected.items():
        path = CORPUS_ROOT / name
        if not path.exists():
            problems.append(f"{name}: missing")
            continue
        rows = load()
        if not rows:
            problems.append(f"{name}: no usable rows (check the tab count)")
    return problems


__all__ = [
    "CORPUS_ROOT",
    "check",
    "footers",
    "items",
    "payments",
    "shops",
    "streets",
    "wards",
]
