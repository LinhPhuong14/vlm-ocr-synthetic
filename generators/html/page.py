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
    # `hand` belongs here for the same reason as the other three: a sheet that
    # asks for a handwriting face and does not get it falls through to whatever
    # the machine has, and the page still renders -- in type, while its label
    # says handwriting. That is the substitution this function exists to stop,
    # and leaving the group out made it certain rather than possible.
    for group in ("mono", "sans", "serif", "hand"):
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
# One text box per drawn field -- and one per LINE when a field wraps.
#
# The union rectangle of a run that broke over two lines is not a box round the
# text: it is a box round both lines *and the blank paper between their ragged
# ends*, which on a full-width block swallows whatever sits at the start of the
# first line. Measured: an invoice's "Số tiền bằng chữ:" label came out 100%
# inside the amount's box, and the overlap detector was right to call it.
#
# So a run whose `getClientRects()` has more than one entry is split per line
# with a Range, character by character, and each line becomes its own box with
# its own slice of the text. The character grid never takes this path -- its
# cells are `white-space:pre` and always one line -- so nothing about it changes.
CELL_RECTS_JS = """() => {
  const sheet = document.querySelector('#sheet').getBoundingClientRect();
  const out = [];
  const push = (kind, text, box) => {
    if (!text.trim()) return;
    out.push({kind, text, x: box.left - sheet.left, y: box.top - sheet.top,
              w: box.width, h: box.height});
  };
  const range = document.createRange();
  for (const span of document.querySelectorAll('#sheet span[data-kind]')) {
    const kind = span.dataset.kind;
    const node = span.firstChild;
    const simple = node && node.nodeType === 3 && span.childNodes.length === 1;
    // A hand-filled field holds an <img> of ink, not a text node, so its text
    // rides on `data-text`. Without this the run has no textContent, `push`
    // drops it, and the page loses the box for exactly the field a reader
    // most needs one for. Nothing that types its values sets the attribute.
    if (!simple || span.getClientRects().length < 2) {
      push(kind, span.dataset.text ?? span.textContent,
           (span.firstElementChild || span).getBoundingClientRect());
      continue;
    }
    const text = node.data;
    let line = null;
    const flush = () => {
      if (!line) return;
      push(kind, text.slice(line.from, line.to),
           {left: line.left, top: line.top, width: line.right - line.left,
            height: line.bottom - line.top});
    };
    for (let i = 0; i < text.length; i++) {
      range.setStart(node, i);
      range.setEnd(node, i + 1);
      const r = range.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;   // a collapsed break
      if (line === null || Math.abs(r.top - line.top) > 1) {
        flush();
        line = {top: r.top, left: r.left, right: r.right, bottom: r.bottom,
                from: i, to: i + 1};
      } else {
        line.left = Math.min(line.left, r.left);
        line.right = Math.max(line.right, r.right);
        line.bottom = Math.max(line.bottom, r.bottom);
        line.to = i + 1;
      }
    }
    flush();
  }
  return out;
}"""

# One box per table cell, with its position and span. A merged cell -- a totals
# row spanning six columns, a stub running down four -- has a text box that says
# nothing about the span, so the cell rect and the span are collected too. The
# idea and the token format come from TIES_DataGeneration by way of PaddleOCR.
CELL_REGIONS_JS = """() => {
  const sheet = document.querySelector('#sheet').getBoundingClientRect();
  // `textContent`, except that a hand-filled run contributes its `data-text`
  // instead of the nothing an <img> contributes. Written as a walk rather than
  // as "the first data-text in the cell" because a cell can hold a printed
  // caption AND an inked value -- taking either one alone loses the other.
  //
  // No layout puts an inked value in a table cell today: checked over all
  // sixteen layouts and twelve seeds, every field a person fills in sits
  // outside the item table. This is here so that the first one that does not
  // fails visibly rather than by reporting an empty cell into the structure
  // label. With no `data-text` anywhere it is `textContent.trim()` exactly.
  const cellText = (root) => {
    let out = '';
    const walk = (node) => {
      if (node.nodeType === 3) { out += node.data; return; }
      if (node.nodeType !== 1) return;
      if (node.dataset && node.dataset.text !== undefined) {
        out += node.dataset.text;
        return;
      }
      for (const child of node.childNodes) walk(child);
    };
    walk(root);
    return out.trim();
  };
  return [...document.querySelectorAll('#sheet [data-cell]')].map(td => {
    const box = td.getBoundingClientRect();
    return {
      kind: td.dataset.cell,
      text: cellText(td),
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
