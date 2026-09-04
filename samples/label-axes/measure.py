#!/usr/bin/env python3
"""Render `page.html` and measure it with the renderer's own box code.

    generators/html/.venv/bin/python samples/label-axes/measure.py

The point is not the picture. It is that the three-axis vocabulary has to
survive the same measurement every shipped page goes through: the boxes come
off the DOM *after* CSS has run, read by the same `CELL_RECTS_JS` in
`generators/html/page.py`, with `data-region` / `data-role` / `data-ink` read
alongside `data-kind`.

A tag that produces no box is a tag the dataset cannot carry, and this script
is what says so out loud -- per axis, per value, with the count.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

from page import CELL_RECTS_JS, find_chromium, font_faces, served  # noqa: E402

HERE = Path(__file__).resolve().parent

# The renderer's own measurement, with the three axes read beside `kind`. The
# body stays `CELL_RECTS_JS` verbatim apart from three splices, so this cannot
# drift into measuring something the renderer does not.
#
# `push` is a closure that never sees `span` -- it is called from two places
# inside the loop and takes only (kind, text, box). So the axes are lifted into
# a variable the loop sets and the closure reads, rather than added as
# parameters at two call sites written differently.
AXES_JS = CELL_RECTS_JS
for _old, _new in (
    ("const push = (kind, text, box) => {",
     "let axes = {};\n  const push = (kind, text, box) => {"),
    ("out.push({kind, text,", "out.push({kind, text, ...axes,"),
    ("const kind = span.dataset.kind;",
     "const kind = span.dataset.kind;\n"
     "    axes = {region: span.dataset.region ?? '',"
     " role: span.dataset.role ?? '', ink: span.dataset.ink ?? ''};"),
):
    assert AXES_JS.count(_old) == 1, _old
    AXES_JS = AXES_JS.replace(_old, _new)

REGIONS = ("Letterhead", "DocTitle", "FieldGroup", "ItemTable", "Summary",
           "Prose", "ListGroup", "Signature", "Mark", "RunningHead",
           "RunningFoot", "Caption", "Note")
ROLES = ("key", "value", "heading", "subheading", "colhdr", "rowhdr", "cell",
         "total", "body", "item", "caption", "note", "mark")
INKS = ("print", "hand", "stamp", "dotmatrix", "thermal", "reversed")


def measure(html: str) -> list[dict]:
    from playwright.sync_api import sync_playwright

    markup = (f"<!doctype html><meta charset='utf-8'><style>{font_faces()}"
              f"body{{margin:0;background:#e9edf1;padding:20px}}</style>{html}")
    chromium = find_chromium()
    # `served`, not `set_content`: an `about:blank` origin will not fetch a
    # `file://` @font-face, and it fails silently -- the face registers, stays
    # `unloaded` forever, and the page is drawn in whatever the machine has.
    # The symptom is Vietnamese, not Latin: the container's fallback draws
    # `tử gốc` as `tư` with a spacing hook after it, eating the space. Every
    # font then renders identically, which is the tell.
    with served(markup) as url, sync_playwright() as play:
        browser = play.chromium.launch(
            executable_path=str(chromium) if chromium else None)
        page = browser.new_page(viewport={"width": 900, "height": 1200},
                                device_scale_factor=2)
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(250)
        rects = page.evaluate(AXES_JS)
        page.locator("#sheet").screenshot(path=str(HERE / "page.png"))
        browser.close()
    return rects


def report(rects: list[dict]) -> int:
    counts = {"region": collections.Counter(), "role": collections.Counter(),
              "ink": collections.Counter()}
    for box in rects:
        for axis in counts:
            counts[axis][box[axis]] += 1

    print(f"{len(rects)} hộp đo được từ DOM\n")
    missing = []
    for axis, expected in (("region", REGIONS), ("role", ROLES), ("ink", INKS)):
        seen = counts[axis]
        print(f"── {axis} ── {len(seen)}/{len(expected)} giá trị có hộp")
        for value in expected:
            n = seen.get(value, 0)
            mark = "  " if n else "!!"
            print(f"  {mark} {value:14s} {n:4d}")
            if not n:
                missing.append(f"{axis}={value}")
        extra = sorted(set(seen) - set(expected) - {""})
        if extra:
            print(f"     ngoài từ vựng: {extra}")
        print()

    # Every box must carry all three axes. A box missing one is a box a
    # consumer cannot filter, which is the whole failure this design exists
    # to remove.
    bare = [b for b in rects if not (b["region"] and b["role"] and b["ink"])]
    print(f"hộp thiếu ít nhất một trục: {len(bare)}")
    for box in bare[:5]:
        print(f"   {box['kind']}: region={box['region']!r} "
              f"role={box['role']!r} ink={box['ink']!r}")

    (HERE / "boxes.json").write_text(
        json.dumps(rects, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\n-> {HERE / 'boxes.json'}\n-> {HERE / 'page.png'}")
    return 1 if (missing or bare) else 0


if __name__ == "__main__":
    raise SystemExit(report(measure((HERE / "page.html").read_text(encoding="utf-8"))))
