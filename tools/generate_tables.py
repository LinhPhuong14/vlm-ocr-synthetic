"""Drive the vendored table generator, with Vietnamese text and a found browser.

    python tools/generate_tables.py -o data/tables60 -n 60

`generators/html-table/` is upstream code (TIES_DataGeneration, by way of
PaddleOCR's TableGeneration) and is deliberately left untouched. It solves a
*different problem* from the three receipt renderers: its label is table
**structure** -- the `<td>` tokens, the row/col spans and a box per cell -- not
a parsed document. Nothing here reads `rulebase/`.

This script exists because running that code needs three things it does not do
itself:

**A browser it can find.** It builds `ChromeOptions()` with no
`binary_location`, so chromedriver looks for `google-chrome` on PATH. A
container that ships Chromium under `/opt/pw-browsers` has no such name, so a
shim is written to a temporary directory and PATH is prepended. Editing the
vendored file would have been one line, but then every future upstream diff
carries it.

**A chromedriver whose major version matches that browser.** Selenium Manager
normally downloads one, which fails behind a proxy that blocks
`googlechromelabs.github.io` -- and its fallback is whatever `chromedriver` is
on PATH, even when the versions cannot talk to each other. `--chromedriver` or
`$CHROMEDRIVER` pins it; otherwise a matching one on PATH is used and a
mismatch is reported before the run rather than as a stack trace during it.

**Text that is not Chinese news.** Upstream fills cells from
`dict/ch_news.txt` (13 MB). The default here is `dict/vi_corpus.txt`, built
from `rulebase/corpus/vi/` by `--rebuild-dict`, so the glyph distribution
matches the rest of the repository -- tone marks included.

One property to know before using the text for anything: `Table.generate_text`
takes a random **character slice** of the corpus, so cell contents are
fragments, not phrases. That is upstream's design and it is the right one for
structure recognition -- but it means these images teach layout, not language.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TABLE_ROOT = REPO_ROOT / "generators" / "html-table"
DICT_DIR = TABLE_ROOT / "dict"
VI_DICT = DICT_DIR / "vi_corpus.txt"

sys.path.insert(0, str(REPO_ROOT))


# ------------------------------------------------------------------ browser


def find_chromium() -> str | None:
    """The same search `generators/html/render.py` does, for the same reason."""
    candidates = [
        Path("/usr/bin/google-chrome"),
        Path("/usr/bin/chromium"),
        Path("/usr/bin/chromium-browser"),
        Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    for path in sorted(Path("/opt/pw-browsers").glob("chromium*/chrome-linux/chrome")):
        return str(path)
    found = shutil.which("google-chrome") or shutil.which("chromium")
    return found


def _major(text: str) -> str | None:
    match = re.search(r"(\d+)\.", text)
    return match.group(1) if match else None


def _version_of(binary: str) -> str:
    try:
        out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=30)
        return (out.stdout or out.stderr).strip()
    except Exception:  # noqa: BLE001 - any failure here just means "unknown"
        return ""


def shim_browser(browser: str, workspace: Path) -> None:
    """Put a `google-chrome` on PATH that runs `browser`.

    chromedriver resolves the browser by name, and the vendored generator never
    sets `binary_location`. On Windows the shim is a .bat; on POSIX a sh script.
    """
    workspace.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        shim = workspace / "google-chrome.bat"
        shim.write_text(f'@echo off\r\n"{browser}" %*\r\n', encoding="utf-8")
    else:
        shim = workspace / "google-chrome"
        shim.write_text(f'#!/bin/sh\nexec "{browser}" "$@"\n', encoding="utf-8")
        shim.chmod(0o755)
    os.environ["PATH"] = f"{workspace}{os.pathsep}{os.environ.get('PATH', '')}"


def resolve_chromedriver(explicit: str | None, browser: str) -> str | None:
    """A chromedriver whose major version matches the browser, or None.

    None means "let Selenium Manager decide", which is right on a machine with
    open network access. It is the wrong answer behind a proxy, and the caller
    prints why.
    """
    want = _major(_version_of(browser))
    candidate = explicit or os.environ.get("CHROMEDRIVER") or shutil.which("chromedriver")
    if not candidate:
        return None
    have = _major(_version_of(candidate))
    if want and have and want != have:
        print(
            f"[warn] chromedriver {have}.x at {candidate} cannot drive Chrome {want}.x;\n"
            f"       ignoring it and letting Selenium Manager fetch a match.\n"
            f"       Behind a proxy that will fail -- download\n"
            f"       https://storage.googleapis.com/chrome-for-testing-public/"
            f"<version>/linux64/chromedriver-linux64.zip\n"
            f"       and pass --chromedriver, or set $CHROMEDRIVER."
        )
        return None
    return candidate


# ------------------------------------------------------------------- corpus


def build_dict(path: Path) -> int:
    """Write a Vietnamese cell corpus from `rulebase/corpus/vi/`.

    Every entry ends with a space on purpose. `Table.load_courp` joins the
    lines with the empty string, so without it "Phở gà" and "Bún bò" would fuse
    into "Phở gàBún bò" and no character slice could ever contain a space.
    """
    from rulebase import corpus

    words: list[str] = [name for name, _lo, _hi in corpus.items("eatery") + corpus.items("market")]
    for row in corpus.shops("market"):
        words.extend(row)
    words.extend(row[0] for row in corpus.shops("eatery"))
    words.extend(corpus.streets())
    words.extend(ward[0] for ward in corpus.wards())
    words.extend(payment[0] for payment in corpus.payments())
    words.extend(corpus.footers("eatery") + corpus.footers("market"))

    seen: set[str] = set()
    unique: list[str] = []
    for word in words:
        word = " ".join(word.split())
        if word and word not in seen:
            seen.add(word)
            unique.append(word)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{word} \n" for word in unique), encoding="utf-8")
    return len(unique)


# -------------------------------------------------------------------- labels


def write_metadata(out: Path) -> int:
    """Turn upstream's `gt.txt` into the `metadata.jsonl` the repo reads.

    Deliberately NOT the receipt renderers' schema. Their `ground_truth` is a
    parsed document; a table's is its structure, and flattening one into the
    other would produce a label that claims to be something it is not. What is
    shared is the file name of the index and the `file_name` key, so a loader
    can find it the same way.
    """
    source = out / "gt.txt"
    if not source.exists():
        return 0

    records = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        # `html` is a repr-like string in some upstream versions and a dict in
        # others; accept both rather than depend on which one is vendored.
        html = raw.get("html")
        if isinstance(html, str):
            try:
                html = json.loads(html)
            except json.JSONDecodeError:
                html = {}
        cells = (html or {}).get("cells", [])
        records.append({
            "file_name": raw["filename"],
            "task": "table_structure",
            "ground_truth": raw.get("gt", ""),
            "structure_tokens": (html or {}).get("structure", {}).get("tokens", []),
            "cells": cells,
            "n_cells": len(cells),
        })

    with open(out / "metadata.jsonl", "w", encoding="utf-8") as handle:
        for record in records:
            json.dump(record, handle, ensure_ascii=False)
            handle.write("\n")
    return len(records)


# ---------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--out", type=Path, default=REPO_ROOT / "data" / "tables60")
    parser.add_argument("-n", "--count", type=int, default=60)
    parser.add_argument("--dict", type=Path, default=VI_DICT,
                        help="cell corpus; default is the Vietnamese one")
    parser.add_argument("--rebuild-dict", action="store_true",
                        help="regenerate it from rulebase/corpus/vi/ first")
    parser.add_argument("--chromedriver", help="path to a chromedriver matching your Chrome")
    parser.add_argument("--min-row", type=int, default=3)
    parser.add_argument("--max-row", type=int, default=12)
    parser.add_argument("--min-col", type=int, default=3)
    parser.add_argument("--max-col", type=int, default=7)
    parser.add_argument("--color-prob", type=float, default=0.3,
                        help="fraction of tables with coloured cells")
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()

    if args.rebuild_dict or not args.dict.exists():
        count = build_dict(args.dict)
        print(f"[dict] {count} entries -> {args.dict.relative_to(REPO_ROOT)}")

    browser = find_chromium()
    if not browser:
        raise SystemExit(
            "no Chrome or Chromium found. Install one, or point this at it by\n"
            "putting it on PATH as `google-chrome`."
        )
    print(f"[browser] {browser}  ({_version_of(browser) or 'version unknown'})")

    workspace = Path(tempfile.mkdtemp(prefix="tablegen-"))
    try:
        shim_browser(browser, workspace)
        driver = resolve_chromedriver(args.chromedriver, browser)
        if driver:
            os.environ["PATH"] = f"{Path(driver).parent}{os.pathsep}{os.environ['PATH']}"
            print(f"[driver]  {driver}  ({_version_of(driver) or 'version unknown'})")

        # Imported here, not at module scope: it constructs a WebDriver in its
        # __init__, so importing it earlier would launch a browser during
        # --help.
        sys.path.insert(0, str(TABLE_ROOT))
        import random

        from TableGeneration.GenerateTable import GenerateTable

        random.seed(args.seed)
        args.out.mkdir(parents=True, exist_ok=True)

        generator = GenerateTable(
            output=str(args.out),
            ch_dict_path=str(args.dict),
            en_dict_path=str(args.dict),
            cell_box_type="cell",
            min_row=args.min_row, max_row=args.max_row,
            min_col=args.min_col, max_col=args.max_col,
            min_txt_len=2, max_txt_len=10,
            max_span_row_count=3, max_span_col_count=3, max_span_value=10,
            color_prob=args.color_prob,
            cell_max_width=0, cell_max_height=0,
            brower="chrome", brower_width=1920, brower_height=2440,
        )
        try:
            generator.gen_table_img(args.count)
        finally:
            generator.close()
    finally:
        shutil.rmtree(workspace, ignore_errors=True)

    written = write_metadata(args.out)
    print(f"\n{written} bảng -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
