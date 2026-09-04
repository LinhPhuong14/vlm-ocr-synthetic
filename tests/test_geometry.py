"""`degradation.geometry` -- page curl, fold crease, corner bulge.

**These run in a renderer's virtualenv, not in the suite's**, same reason as
`tests/test_ink_degradation.py`: the module needs numpy and OpenCV, and the
suite environment is pytest + PyYAML only, on purpose (`tests/conftest.py`).
`pytest.importorskip("cv2")` is the trap documented there -- a module that
skips everywhere reads like coverage and is not. So this shells out to the
html renderer's virtualenv instead, and is marked `slow`.
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
    import numpy as np
    from degradation import geometry as G

    def page(w=900, h=1200):
        return np.full((h, w, 3), 250, np.uint8)

    def grid(w, h, nx=5, ny=6):
        xs = np.linspace(50, w - 50, nx)
        ys = np.linspace(50, h - 50, ny)
        out = [[[x - 20, y - 10], [x + 20, y - 10], [x + 20, y + 10], [x - 20, y + 10]]
               for y in ys for x in xs]
        return np.array(out, dtype=np.float32)

    img = page()
    h, w = img.shape[:2]
    quads = grid(w, h)
    out = {{}}

    # 1. shape and finiteness, one trial per warp, several seeds
    out["shapes"] = {{}}
    out["finite"] = {{}}
    for name in G.names():
        shapes, finite = [], True
        for seed in range(8):
            oi, oq = G.apply_warp(name, img.copy(), quads.copy(), {{}}, random.Random(seed))
            shapes.append(list(oi.shape[:2]))
            finite = finite and bool(np.isfinite(oq).all())
        out["shapes"][name] = shapes
        out["finite"][name] = finite

    # 2. page_curl never shrinks the canvas (it pads, it does not crop)
    oi, _ = G.apply_warp("page_curl", img.copy(), quads.copy(), {{}}, random.Random(1))
    out["page_curl_grew"] = oi.shape[0] >= h and oi.shape[1] >= w

    # 3. fold_crease / corner_bulge keep the canvas size (no padding needed)
    for name in ("fold_crease", "corner_bulge"):
        oi, _ = G.apply_warp(name, img.copy(), quads.copy(), {{}}, random.Random(2))
        out[f"{{name}}_same_shape"] = list(oi.shape[:2]) == [h, w]

    # 4. depth at zero is the identity map on the quads (shading never moves
    # a quad -- it only multiplies pixel brightness, checked separately below)
    oi, oq = G.apply_warp("fold_crease", img.copy(), quads.copy(),
                           {{"depth": 0.0}}, random.Random(3))
    out["fold_crease_identity_diff"] = float(np.abs(oq - quads).max())
    oi, oq = G.apply_warp("corner_bulge", img.copy(), quads.copy(),
                           {{"depth": 0.0}}, random.Random(3))
    out["corner_bulge_identity_diff"] = float(np.abs(oq - quads).max())

    # 4b. shading changes pixels but never a quad, and a stronger light does
    # more work than a weaker one -- the mechanism this whole change was
    # about (see the module docstring on why shading is not decoration here).
    out["shading"] = {{}}
    for name in G.names():
        base = img.copy()
        no_shade = G.apply_warp(name, base.copy(), quads.copy(),
                                 {{"shade_strength": 0.0}}, random.Random(5))[0]
        full_shade = G.apply_warp(name, base.copy(), quads.copy(),
                                   {{"shade_strength": 1.0, "shade_ambient": 0.2}},
                                   random.Random(5))[0]
        _, q_no = G.apply_warp(name, base.copy(), quads.copy(),
                                {{"shade_strength": 0.0}}, random.Random(9))
        _, q_full = G.apply_warp(name, base.copy(), quads.copy(),
                                  {{"shade_strength": 1.0}}, random.Random(9))
        out["shading"][name] = {{
            "pixels_changed": bool(np.abs(
                no_shade.astype(np.int16) - full_shade.astype(np.int16)).max() > 3),
            "quads_identical": bool(np.array_equal(q_no, q_full)),
        }}

    # 5. same seed -> same output (reproducible from a recipe's seed)
    a = G.apply_warp("page_curl", img.copy(), quads.copy(), {{}}, random.Random(7))[1]
    b = G.apply_warp("page_curl", img.copy(), quads.copy(), {{}}, random.Random(7))[1]
    out["reproducible"] = bool(np.array_equal(a, b))
    c = G.apply_warp("page_curl", img.copy(), quads.copy(), {{}}, random.Random(8))[1]
    out["seed_matters"] = not bool(np.array_equal(a, c))

    # 6. unknown warp name fails loudly
    try:
        G.apply_warp("not_a_warp", img.copy(), quads.copy(), {{}}, random.Random(0))
        out["unknown_warp"] = "accepted"
    except KeyError as error:
        out["unknown_warp"] = str(error)

    # 7. warp_regions: three region lists warped consistently, keys preserved
    boxes = [{{"kind": "field", "text": "a", "quad": q.tolist()}} for q in quads[:5]]
    words = [{{"kind": "word", "text": "b", "quad": q.tolist()}} for q in quads[5:8]]
    cells = [{{"kind": "cell", "quad": q.tolist()}} for q in quads[8:10]]
    new_img, new_boxes, new_words, new_cells = G.warp_regions(
        "page_curl", img.copy(), {{}}, random.Random(9), boxes, words, cells)
    out["regions_lengths"] = [len(new_boxes), len(new_words), len(new_cells)]
    out["regions_keys_kept"] = (
        set(new_boxes[0]) == {{"kind", "text", "quad"}}
        and set(new_cells[0]) == {{"kind", "quad"}})
    # A corner drawn once, shared across all three lists: the same quad index
    # relative to its own list must land in the same place whichever list it
    # came from, which we check indirectly by re-deriving one warp on the
    # concatenation and comparing to warp_regions' own split.
    all_quads = np.concatenate([quads[:5], quads[5:8], quads[8:10]])
    direct = G.apply_warp("page_curl", img.copy(), all_quads.copy(), {{}}, random.Random(9))[1]
    rebuilt = np.array([b["quad"] for b in new_boxes]
                        + [b["quad"] for b in new_words]
                        + [b["quad"] for b in new_cells], dtype=np.float32)
    out["regions_match_direct"] = bool(np.allclose(rebuilt, direct, atol=0.15))

    # 8. empty quads do not crash (a caller with no labels)
    for name in G.names():
        oi, oq = G.apply_warp(name, img.copy(), np.zeros((0, 4, 2), np.float32),
                               {{}}, random.Random(4))
        out.setdefault("empty_ok", {{}})[name] = oq.shape == (0, 4, 2)

    print(json.dumps(out))
""")


@pytest.fixture(scope="module")
def probe() -> dict:
    interpreter = venv_python(VENVS["html"])
    if not interpreter.exists():
        pytest.skip("html environment not built")
    script = PROBE.format(repo=str(REPO_ROOT))
    result = subprocess.run([str(interpreter), "-c", script],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-3000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_every_warp_keeps_the_page_finite(probe):
    for name, finite in probe["finite"].items():
        assert finite, f"{name} produced a non-finite quad corner"


def test_page_curl_pads_rather_than_crops(probe):
    """`CurlWarp`'s own contract, carried over: render large, never lose a
    corner off the edge -- a curl grows the canvas, it does not crop into it.
    """
    assert probe["page_curl_grew"]


def test_fold_crease_and_corner_bulge_do_not_need_to_pad(probe):
    """Both pinch content INWARD (towards a crease or a corner), so unlike
    `page_curl` they never push a point past the original frame."""
    assert probe["fold_crease_same_shape"]
    assert probe["corner_bulge_same_shape"]


def test_zero_depth_is_the_identity_map(probe):
    """A named parameter that means "none of this" has to actually mean it --
    a page with `depth: 0.0` in its recipe must come back with unmoved boxes,
    not a small residual bend nobody asked for."""
    assert probe["fold_crease_identity_diff"] == pytest.approx(0.0, abs=1e-4)
    assert probe["corner_bulge_identity_diff"] == pytest.approx(0.0, abs=1e-4)


def test_the_warp_is_reproducible_from_a_seed(probe):
    """`recipe.seed` has to determine the page bit-for-bit, same as every
    other stage in this pipeline -- a warp that drew from unseeded global
    state would make two runs of the same seed diverge only here."""
    assert probe["reproducible"]
    assert probe["seed_matters"]


def test_an_unknown_warp_name_fails_loudly(probe):
    assert "not_a_warp" in probe["unknown_warp"]
    assert probe["unknown_warp"] != "accepted"


def test_warp_regions_keeps_list_lengths_and_dict_keys(probe):
    assert probe["regions_lengths"] == [5, 3, 2]
    assert probe["regions_keys_kept"]


def test_warp_regions_applies_one_shared_warp_not_one_per_list(probe):
    """`boxes`, `words` and `cells` describe the same page and must agree on
    where a corner went -- warping each list on its own rng draw would let a
    box and the word inside it disagree about the page's own shape."""
    assert probe["regions_match_direct"]


def test_empty_quads_do_not_crash_a_caller_with_no_labels(probe):
    for name, ok in probe["empty_ok"].items():
        assert ok, f"{name} broke on an empty quad array"
