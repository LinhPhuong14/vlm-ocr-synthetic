"""What every page this backend renders needs, and nothing that needs a browser.

Two producers now sit on this backend -- `render.py` for receipts and invoices,
`tables.py` for table-structure pages -- and both need the same three things: a
Chromium to launch, the repository's fonts embedded so the browser cannot
substitute, and the snippet that reads boxes off the laid-out DOM. Keeping them
here means a change to any of the three happens once.

This module imports nothing heavy on purpose. `render.py` pulls in Playwright
and OpenCV at import time, so anything that wanted `find_chromium` had to pay
for a browser stack it was not going to use -- including the tests, which check
the markup and the labels and never open a page.
"""

from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FONT_ROOT = REPO_ROOT / "fonts"

# Linux containers that ship a browser system-wide, this repository's own
# included. Elsewhere -- Windows, macOS, a plain `pip install playwright` --
# there is nothing here and Playwright resolves its own download instead.
CHROMIUM_CANDIDATES = [
    Path("/opt/pw-browsers/chromium/chrome-linux/chrome"),
    Path("/opt/pw-browsers/chromium-1194/chrome-linux/chrome"),
    Path("/usr/bin/chromium"),
    Path("/usr/bin/chromium-browser"),
]


def find_chromium() -> str | None:
    """A browser to launch, or None to let Playwright pick its own.

    Returning None is not a failure: `launch(executable_path=None)` is the
    normal path, and the only reason to override it is a container that already
    has a build and must not download a second one.
    """
    for path in CHROMIUM_CANDIDATES:
        if path.exists():
            return str(path)
    for path in sorted(Path("/opt/pw-browsers").glob("chromium*/chrome-linux/chrome")):
        return str(path)
    return None


def font_faces() -> str:
    """Embed the repo's fonts so the browser cannot silently substitute.

    A CSS stack that falls through to whatever the container happens to have
    is how a receipt ends up rendered in a font with no Vietnamese diacritics,
    with the label still claiming they were printed.

    The family name is the file stem: `LiberationMono-Regular.ttf` is
    `LiberationMono`, with no space. A stack that asks for "Liberation Mono"
    matches none of these and falls straight through to the system.
    """
    faces = []
    for group in ("mono", "sans", "serif"):
        directory = FONT_ROOT / group
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.ttf")):
            family = path.stem.replace("-Regular", "").replace("-Bold", "")
            weight = "700" if path.stem.endswith("-Bold") else "400"
            faces.append(
                "@font-face{font-family:'%s';font-weight:%s;src:url('file://%s') format('truetype');}"
                % (family.replace("-", " "), weight, path)
            )
    return "\n".join(faces)


@contextmanager
def served(markup: str):
    """The markup as a `file://` page, so its `@font-face` sources actually load.

    `set_content` puts the page on an `about:blank` origin, and Chromium will
    not fetch a `file://` subresource from there. It fails *silently*: the rule
    parses, the face is registered, `document.fonts` lists it as `unloaded`
    forever, and the text is drawn in whatever the machine happens to have
    installed under a matching name. Which is exactly the substitution
    `font_faces` exists to prevent -- and it was measurable, not theoretical:
    the container's fallback draws `tố` as `tô` with a spacing acute after it,
    eating the following space, while the repo's own faces draw it correctly.
    """
    directory = tempfile.mkdtemp(prefix="vlm-page-")
    try:
        path = Path(directory) / "page.html"
        path.write_text(markup, encoding="utf-8")
        yield path.as_uri()
    finally:
        shutil.rmtree(directory, ignore_errors=True)


# Boxes are measured in the browser, off the page that was laid out, and both
# snippets return every rect in one `evaluate` rather than one round trip per
# element -- which is the whole speed difference between this and driving the
# same browser through Selenium.
#
# One text box per drawn field, for the character-grid receipts.
CELL_RECTS_JS = """() => {
  const sheet = document.querySelector('#sheet').getBoundingClientRect();
  return [...document.querySelectorAll('#sheet span[data-kind]')].map(span => {
    const box = (span.firstElementChild || span).getBoundingClientRect();
    return {
      kind: span.dataset.kind,
      text: span.textContent,
      x: box.left - sheet.left,
      y: box.top - sheet.top,
      w: box.width,
      h: box.height,
    };
  });
}"""

# One box per table cell, with its position and span. A merged cell -- a totals
# row spanning six columns, a stub running down four -- has a text box that says
# nothing about the span, so the cell rect and the span are collected too. The
# idea and the token format come from TIES_DataGeneration by way of PaddleOCR.
CELL_REGIONS_JS = """() => {
  const sheet = document.querySelector('#sheet').getBoundingClientRect();
  return [...document.querySelectorAll('#sheet [data-cell]')].map(td => {
    const box = td.getBoundingClientRect();
    return {
      kind: td.dataset.cell,
      text: td.textContent.trim(),
      row: Number(td.dataset.row), col: Number(td.dataset.col),
      colspan: td.colSpan || 1, rowspan: td.rowSpan || 1,
      x: box.left - sheet.left, y: box.top - sheet.top,
      w: box.width, h: box.height,
    };
  });
}"""

__all__ = [
    "CELL_RECTS_JS", "CELL_REGIONS_JS", "CHROMIUM_CANDIDATES", "FONT_ROOT",
    "REPO_ROOT", "find_chromium", "font_faces", "served",
]
