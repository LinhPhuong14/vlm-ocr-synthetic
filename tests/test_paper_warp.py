"""`degradation.paper_warp` -- the cheap page warp, and whether its LABELS survive it.

This is the first geometry engine switched on by default (`augmentation=paper_creased`),
so the question it has to answer is not "does the page look bent" but "does the box still
sit on the word". A warp that moves ink and leaves the quads behind produces a dataset
that is wrong in the one way an OCR set may not be, and silently: the picture looks
better than before.

The probe below measures exactly that -- marks drawn at known positions, warped, then
found again by connected components in the OUTPUT and compared against the quads the
engine returned. The overlay is switched off for that measurement (`alpha=lighten=0` is
an exact identity in `texture.blend_sheet`), so a mark's centroid moves because of the
warp and nothing else.

**Runs in the html renderer's virtualenv**, like `tests/test_ink_degradation.py` and for
the reason in its docstring: this needs numpy and OpenCV, the suite's own environment has
neither by design, and `pytest.importorskip` would turn that into a silent skip that
reads like coverage. Marked `slow`; unlike `tests/test_blender_warp.py` it needs no
`blender` executable, because that is the entire point of this engine.
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from paths import VENVS, venv_python  # noqa: E402

pytestmark = pytest.mark.slow

PROBE = textwrap.dedent("""
    import json, random, sys
    sys.path.insert(0, {repo!r})
    import cv2, numpy as np
    from degradation.paper_warp import NAME, apply_warp
    from degradation.warp import engine_for, names as warp_names

    W, H = 1020, 1442
    def page():
        out = np.full((H, W, 3), 245, np.uint8)
        for x, y in SPOTS:
            cv2.circle(out, (x, y), 7, (20, 20, 20), -1)
        return out

    SPOTS = [(x, y) for y in range(120, H - 120, 180) for x in range(120, W - 120, 200)]
    QUADS = np.array([[[x - 7, y - 7], [x + 7, y - 7], [x + 7, y + 7], [x - 7, y + 7]]
                      for x, y in SPOTS], dtype=np.float32)

    def measure(stretch):
        # alpha=lighten=0 -> the blend is the identity, so the only thing that
        # moved a mark is the warp, and its centroid is a clean measurement.
        warped, moved = apply_warp(NAME, page(), QUADS,
            {{"photo": "paper_6", "max_stretch": stretch, "alpha": 0.0, "lighten": 0.0}},
            random.Random(0))
        mask = (cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY) < 128).astype(np.uint8)
        n, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
        blobs = [tuple(c) for i, c in enumerate(centroids)
                 if i and stats[i, cv2.CC_STAT_AREA] > 30]
        errors, shifts = [], []
        for quad, (sx, sy) in zip(moved, SPOTS):
            cx, cy = quad.mean(axis=0)
            near = min(blobs, key=lambda p: (p[0] - cx) ** 2 + (p[1] - cy) ** 2)
            errors.append(float(np.hypot(near[0] - cx, near[1] - cy)))
            shifts.append(float(np.hypot(cx - sx, cy - sy)))
        return {{"marks": len(SPOTS), "blobs": len(blobs),
                "error_max": max(errors), "shift_max": max(shifts)}}

    out = {{"label_error": {{str(s): measure(s) for s in (0.28, 0.5)}}}}

    # Same seed, same page. The photo is DRAWN, so this also pins that the draw
    # comes from the rng handed in rather than from module state.
    a, _ = apply_warp(NAME, page(), QUADS, {{}}, random.Random(7))
    b, _ = apply_warp(NAME, page(), QUADS, {{}}, random.Random(7))
    out["reproducible"] = bool(np.array_equal(a, b))
    out["moved_pixels"] = int(cv2.absdiff(a, page()).sum()) > 0

    # No photographs -> a no-op on BOTH, not a synthetic stand-in: same contract
    # as `texture.paper_overlay`, so a missing directory stays visible.
    same, quads = apply_warp(NAME, page(), QUADS, {{}}, random.Random(0),
                             overlays_dir="/nonexistent-overlays")
    out["empty_dir_noop"] = bool(np.array_equal(same, page())
                                 and np.array_equal(quads, QUADS))

    # A page with no labels at all still warps -- `tools/augment_samples.py`
    # runs over finished images that never had quads.
    empty, no_quads = apply_warp(NAME, page(), np.zeros((0, 4, 2), np.float32), {{}},
                                 random.Random(0))
    out["no_quads_ok"] = bool(empty.shape == (H, W, 3) and len(no_quads) == 0)

    try:
        apply_warp("not_an_engine", page(), QUADS, {{}}, random.Random(0))
        out["unknown_name"] = "accepted"
    except KeyError as error:
        out["unknown_name"] = str(error)

    out["dispatch"] = engine_for(NAME).__name__.rsplit(".", 1)[-1]
    out["warp_names"] = warp_names()
    print(json.dumps(out))
""")


@pytest.fixture(scope="module")
def probe() -> dict:
    python = venv_python(VENVS["html"])
    if not python.exists():
        pytest.skip(f"{python} missing -- run `make setup-html`")
    result = subprocess.run(
        [str(python), "-c", PROBE.format(repo=str(REPO_ROOT))],
        capture_output=True, text=True, timeout=600,
    )
    if result.returncode != 0:
        pytest.fail(f"probe failed:\n{result.stdout}\n{result.stderr}")
    return json.loads(result.stdout)


def test_labels_follow_the_ink(probe):
    """Every quad still sits on the mark it labels, to well under a pixel.

    The whole reason this engine may run by default. `cv2.remap` consumes a
    BACKWARD map, so a box cannot simply be shifted by the field sampled at its
    own position -- that is off by the field's own change across the shift, which
    at these amplitudes is tens of pixels. `paper_warp._invert` iterates instead.
    """
    for stretch, measured in probe["label_error"].items():
        assert measured["blobs"] == measured["marks"], (
            f"max_stretch={stretch}: {measured['marks']} marks in, "
            f"{measured['blobs']} found after the warp -- the map folded onto itself")
        assert measured["error_max"] < 1.0, (
            f"max_stretch={stretch}: a quad sits {measured['error_max']:.2f}px off its "
            f"ink; the labels no longer describe the page")


def test_the_warp_is_worth_labelling(probe):
    """Boxes move far enough that getting them wrong would matter.

    Guards the test above from passing for the wrong reason: a field crushed to
    zero would put every quad exactly on its mark and prove nothing.
    """
    assert probe["label_error"]["0.28"]["shift_max"] > 10.0
    assert probe["label_error"]["0.5"]["shift_max"] > probe["label_error"]["0.28"]["shift_max"]
    assert probe["moved_pixels"]


def test_reproducible_from_the_seed(probe):
    assert probe["reproducible"]


def test_no_photographs_is_a_no_op(probe):
    assert probe["empty_dir_noop"]


def test_a_page_without_labels_still_warps(probe):
    assert probe["no_quads_ok"]


def test_unknown_engine_name_raises(probe):
    assert probe["unknown_name"] != "accepted"


def test_dispatcher_routes_by_name(probe):
    """`degradation.warp` is the one door: the paper field and the Blender meshes
    share a namespace, so `rulebase` names either without the renderer choosing."""
    assert probe["dispatch"] == "paper_warp"
    assert "paper_photo" in probe["warp_names"]
    assert "page_curl" in probe["warp_names"]
