"""Ink that is not a run, and the box it now gets.

`CELL_RECTS_JS` walks `span[data-kind]` and nothing else, so for as long as
this repository has existed the pictorial half of a page has been in no
annotation at all: a proof image showed the "C" logo circle at the top of every
`modern` invoice with no box round it, and the same was true of the watermark,
the rosette on a statement, the barcode, and every signature.

**Ink with no box is ink with no label**, which is the one thing
`pipeline/invariants.py` exists to refuse -- I-5 in the level-3 spec says it in
one line, and A-4 measures it. So `page.py::GRAPHIC_RECTS_JS` finds those
elements and `pipeline/record.py` turns each into one `Image` region.

The three exclusions are the whole difficulty, and each one is a real element
on a real page. They are what this file is mostly about.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "generators" / "html"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))


def _launch(playwright):
    """A browser, or None when this environment has none.

    NOT `find_chromium() is not None`: that helper returns None on the ordinary
    path and says so in its own docstring -- `launch(executable_path=None)` is
    how Playwright uses the build it manages itself, and only a container with
    a pre-installed browser overrides it. Reading None as "no browser" is why
    the check copied from `tests/test_table_bbox.py` skipped every case here on
    a machine that renders pages perfectly well.

    So the question is asked the only way it can be answered: try to launch.
    """
    from page import find_chromium

    try:
        return playwright.chromium.launch(executable_path=find_chromium())
    except Exception:                        # noqa: BLE001 -- any failure is "none"
        return None


# A page carrying one of everything: the cases that must be found, and the
# three that must not. Hand-written rather than rendered from a layout so the
# reason each element is here stays readable -- a real page has them scattered
# over nine family modules.
SHEET = """
<div id="sheet" style="position:relative;width:400px;height:600px;">
  <!-- FOUND: a CSS-drawn logo monogram (`modern.py`, `medical.py`, ...) -->
  <div class="logo" style="width:40px;height:40px;border-radius:50%;
       background:#123;color:#fff;">C</div>
  <!-- FOUND: an inline SVG rosette (`statement.py::_mark`) -->
  <svg class="mark" width="30" height="30" viewBox="0 0 30 30"><circle
       cx="15" cy="15" r="12" fill="none" stroke="#000"/></svg>
  <!-- FOUND: a barcode (`statement.py`) -->
  <svg class="bars" width="80" height="20" viewBox="0 0 80 20"><rect
       width="4" height="20"/></svg>
  <!-- FOUND: a watermark (`modern.py`, `statutory.py`) -->
  <div class="wm" style="width:120px;height:60px;color:#eee;">3601030205</div>
  <!-- FOUND: signature ink. `aria-hidden` and deliberately unlabelled, and it
       still puts ink on the paper -- see this module's docstring. -->
  <span class="sig" aria-hidden="true" style="display:inline-block;
        width:70px;height:25px;"><svg width="70" height="25"
        viewBox="0 0 70 25"><path d="M2 20 L60 5" stroke="#224"/></svg></span>

  <!-- NOT FOUND: a container of labelled runs. `.flag` on a masthead and
       `.brand` on an invoice look pictorial and are not; their box would
       swallow the runs inside them. -->
  <div class="flag" style="width:200px;"><span data-kind="masthead">Báo</span></div>
  <!-- NOT FOUND: an <img> of ink INSIDE a labelled run. A hand-filled field
       is already boxed as that run; boxing it again is two labels on one mark. -->
  <span data-kind="sign.name" data-text="Lê Văn A"><img
        src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7"
        style="width:50px;height:18px;"></span>
  <!-- NOT FOUND TWICE: `statement.py` draws `<svg class="mark">`, which
       matches both the class selector and the tag selector. The outer element
       is the picture; one box, not two. -->
</div>
"""


@pytest.fixture(scope="module")
def found():
    """`GRAPHIC_RECTS_JS` over `SHEET`, in a real browser."""
    playwright_api = pytest.importorskip("playwright.sync_api")
    from page import GRAPHIC_RECTS_JS, served

    markup = f"<!doctype html><html><body>{SHEET}</body></html>"
    with playwright_api.sync_playwright() as playwright:
        browser = _launch(playwright)
        if browser is None:
            pytest.skip("no browser in this environment")
        try:
            page = browser.new_page()
            try:
                with served(markup) as uri:
                    page.goto(uri, wait_until="load")
                page.wait_for_timeout(30)
                return page.evaluate(GRAPHIC_RECTS_JS)
            finally:
                page.close()
        finally:
            browser.close()


pytestmark = pytest.mark.slow


def test_every_kind_of_ink_that_is_not_a_run_is_found(found):
    kinds = [str(g["kind"]) for g in found]
    for wanted in ("logo", "mark", "bars", "wm", "sig"):
        assert any(wanted in kind for kind in kinds), (kinds, wanted)


def test_the_logo_is_found_because_that_is_what_started_this(found):
    """The "C" circle at the top of every `modern` invoice, unboxed until now."""
    logo = next(g for g in found if "logo" in str(g["kind"]))
    assert logo["w"] > 0 and logo["h"] > 0


def test_signature_ink_gets_a_box_too(found):
    """`aria-hidden` marks it as not-content for a screen reader; it is still
    ink on paper, and ink outside the annotation is ink with no label."""
    assert any("sig" in str(g["kind"]) for g in found)


def test_a_container_of_labelled_runs_is_not_a_picture(found):
    """`.flag` holds a `span[data-kind]`. Boxing it would claim a masthead is
    an image and swallow the run inside it."""
    assert not any("flag" in str(g["kind"]) for g in found)


def test_ink_already_boxed_as_a_run_is_not_boxed_again(found):
    """A hand-filled field is an `<img>` inside a labelled span -- two labels
    on one mark is worse than none."""
    for graphic in found:
        assert graphic["w"] < 400 and graphic["h"] < 600
    assert len(found) == 5, [g["kind"] for g in found]


def test_a_graphic_inside_another_graphic_is_counted_once(found):
    """`<svg class="mark">` matches the class selector AND the tag selector."""
    marks = [g for g in found if str(g["kind"]) in ("mark", "bars")]
    assert len(marks) == 2, [g["kind"] for g in found]


def test_every_box_is_inside_the_sheet(found):
    for graphic in found:
        assert graphic["x"] >= -1 and graphic["y"] >= -1, graphic
        assert graphic["w"] > 0 and graphic["h"] > 0, graphic


# ------------------------------------------------------- the record side


def test_a_graphic_becomes_one_image_region_and_no_block():
    """The distinction the label contract turns on: a block promises a reader
    some text, and a logo has none. So it gets a region and not a block."""
    from pipeline import record

    graphics = [{"kind": "logo",
                 "quad": [[10, 10], [50, 10], [50, 50], [10, 50]]}]
    regions = record.regions_from_words([], graphics=graphics,
                                        page_size=(600, 800))
    assert len(regions) == 1
    assert regions[0]["layout_class"] == record.GRAPHIC_LABEL == "Image"
    assert regions[0]["text"] == ""
    assert regions[0]["bbox_strategy"] == "dom_element_perimeter"

    built = record.build(filename="x.jpg", width=600, height=800, parser="html",
                         boxes=[], words=[], graphics=graphics)
    assert [r["layout_class"] for r in built["layout_annotations"]] == ["Image"]
    assert built["blocks"] == [], "a graphic must not promise text to read"


def test_the_image_label_is_the_vocabulary_the_regions_speak():
    """`layout_annotations` speaks `DOCSYNTH_LABELS`; `blocks` speaks
    `PAGE_LABELS`, which calls the same idea `Picture`."""
    from pipeline.record import DOCSYNTH_LABELS, GRAPHIC_LABEL, PAGE_LABELS

    assert GRAPHIC_LABEL in DOCSYNTH_LABELS
    assert GRAPHIC_LABEL not in PAGE_LABELS


def test_a_backend_that_draws_no_graphics_is_unchanged():
    """The character grid has no DOM to measure, and every existing caller
    passes nothing -- both must behave exactly as before."""
    from pipeline import record

    words = record.words_from_boxes([])
    assert record.regions_from_words(words) == record.regions_from_words(
        words, graphics=[])


def test_a_malformed_quad_is_skipped_rather_than_crashing():
    from pipeline import record

    regions = record.regions_from_words(
        [], graphics=[{"kind": "logo", "quad": [[1, 2]]}, {"kind": "x"}],
        page_size=(600, 800))
    assert regions == []
