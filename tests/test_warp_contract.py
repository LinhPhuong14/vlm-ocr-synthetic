"""What a geometry warp may do to a page, and what it may not.

A warp is the one step in the pipeline allowed to change a page's size --
`generators/html/render.py` asserts every degradation model leaves the shape
alone and calls `warp_regions` outside that assertion. That licence is to BEND
the sheet. It was being spent on something else.

Three findings, measured one page per scenario with every other attribute
pinned, and all three are in this file:

1. **The Blender engine was shrinking the page.** It renders on a 1536x2048
   canvas and crops to the sheet's own footprint; the camera backs off to fit a
   fold, so the sheet is small in frame and the crop keeps it small. An A4
   invoice went in at 1191x1684 and came out at 803x1036 -- two thirds of its
   linear size, every glyph shrunk with it, 8pt body text under the pixel floor
   `agent/critic.py` calls `chu_nho`.

2. **`critic.overlaps` was judging bent pages by bounding box.** A line of text
   on a warped sheet is a sheared quadrilateral whose axis-aligned box is far
   larger than the ink in it, so neighbouring lines "overlap" without touching.

3. **A missing Blender was found halfway through a run**, after the browser was
   up and shards had written images, rather than by the preflight whose whole
   job is to know that before the first page.

Before: `page_curl` 12 severe findings, `lifted_corner` 12, `folded` 11,
`crease_bundle` 7, `crumple` 3, `paper_photo` 0. After: **0 for all six**, which
is what let the four disabled Blender values be switched on.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agent import critic  # noqa: E402


def _quad(x1, y1, x2, y2):
    return {"quad": [[x1, y1], [x2, y1], [x2, y2], [x1, y2]], "kind": "menu.name"}


# ------------------------------------------------------- 2 · the overlap check


def test_two_boxes_that_really_overlap_are_still_reported():
    """The bounding-box sweep stays; only the verdict moved to the polygon, so
    an ordinary axis-aligned page must score exactly as it did."""
    found = critic.overlaps([_quad(0, 0, 100, 100), _quad(50, 50, 150, 150)])
    assert len(found) == 1
    _i, _j, share, _pixels = found[0]
    assert share == pytest.approx(0.25, abs=0.01)


def test_sheared_boxes_whose_bounding_boxes_meet_but_bodies_do_not():
    """The finding this file exists for. Two lines of a warped page: their
    bounding boxes overlap by a third, and the lines never touch."""
    # Two parallel slanted bars, 30 apart at every height, so they are 10
    # apart at every height and never meet. Their bounding boxes share 90x100
    # of the 120x100 each covers -- which is the whole trap.
    left = {"kind": "menu.name", "quad": [[0, 0], [20, 0], [120, 100], [100, 100]]}
    right = {"kind": "menu.qty", "quad": [[30, 0], [50, 0], [150, 100], [130, 100]]}
    shared_boxes = critic._intersection(critic._rect(left), critic._rect(right))
    assert shared_boxes == pytest.approx(9000.0), "the premise: the boxes overlap"
    assert shared_boxes / min(critic._area(critic._rect(left)),
                              critic._area(critic._rect(right))) > critic.OVERLAP, (
        "and by enough that the bounding-box check would have reported it")
    assert critic.overlaps([left, right]) == [], "the quads themselves do not touch"


def test_the_bounding_box_sweep_is_a_superset_of_the_polygon_answer():
    """Why the sweep stays valid: two convex quads cannot intersect unless
    their bounding boxes do, so skipping a pair whose boxes miss can never skip
    a real overlap -- and the expensive clip is only paid for by survivors."""
    far = [_quad(0, 0, 10, 10), _quad(500, 500, 510, 510)]
    assert critic._intersection(critic._rect(far[0]), critic._rect(far[1])) == 0
    assert critic.overlaps(far) == []


def test_a_mirrored_quad_still_clips():
    """Sutherland-Hodgman decides "inside" from the clipper's winding, so a
    quad that came back from a warp wound the other way would clip everything
    away and report zero overlap on the page with the most."""
    clockwise = {"kind": "a", "quad": [[0, 0], [0, 100], [100, 100], [100, 0]]}
    counter = {"kind": "b", "quad": [[50, 50], [150, 50], [150, 150], [50, 150]]}
    found = critic.overlaps([clockwise, counter])
    assert len(found) == 1 and found[0][2] == pytest.approx(0.25, abs=0.01)


def test_polygon_area_is_the_quad_not_its_bounding_box():
    sheared = {"quad": [[0, 0], [100, 0], [130, 20], [30, 20]]}
    assert critic._poly_area(critic._poly(sheared)) == pytest.approx(2000.0)
    x1, y1, x2, y2 = critic._rect(sheared)
    assert (x2 - x1) * (y2 - y1) == pytest.approx(2600.0)


# ------------------------------------------------------- 3 · the preflight


def test_preflight_names_a_warp_engine_the_machine_does_not_have(monkeypatch):
    """`degradation.blender` raises the moment a page asks for it, which is
    halfway through a run. Whether the tool is installed is a fact about the
    machine, knowable before the first page."""
    from degradation import blender
    from pipeline import preflight

    monkeypatch.setattr(blender, "available", lambda: False)
    problems = preflight.warp_engines()
    assert problems, "an enabled Blender value with no Blender must be reported"
    assert all(p.startswith(preflight.UNCHECKED) for p in problems), (
        "a missing program is a fact about the clone, not a fault in the rules")
    assert any("setup-blender" in p for p in problems), "say how to fix it"


def test_preflight_is_quiet_when_the_engine_is_there(monkeypatch):
    from degradation import blender
    from pipeline import preflight

    monkeypatch.setattr(blender, "available", lambda: True)
    assert preflight.warp_engines() == []


def test_every_enabled_warp_names_an_engine_that_exists():
    """A typo in `warp.name` is a rule that can never draw, and nothing else
    reports it until a page tries."""
    from degradation import warp
    from rulebase import load_rules

    for option in load_rules()["augmentation"]:
        name = (option.params.get("warp") or {}).get("name")
        if name and getattr(option, "enabled", True):
            warp.engine_for(name)          # raises KeyError on an unknown name


# ------------------------------------------------------- 1 · the size contract


def test_both_engines_answer_whether_they_can_run():
    """`preflight.warp_engines` asks `engine.available()`. An engine without
    one is treated as always ready, which is right for `paper_photo` (pure
    numpy, nothing to install) and would be wrong for anything that shells
    out -- so the shelling-out one must have it."""
    from degradation import blender, paper_warp

    assert callable(blender.available)
    assert isinstance(blender.available(), bool)
    # `paper_warp` needs nothing installed, so it may omit the hook entirely.
    assert not hasattr(paper_warp, "available") or callable(paper_warp.available)


def test_the_size_contract_is_written_down_where_it_is_enforced():
    """The rule is one sentence -- a warp may bend a page, not shrink it -- and
    it lives in the branch that enforces it. A reader who deletes the rescale
    should meet the reason, not a bare `cv2.resize`."""
    source = (REPO_ROOT / "degradation" / "blender" / "render.py").read_text(encoding="utf-8")
    assert "cv2.resize" in source
    assert "may not make it smaller" in source
