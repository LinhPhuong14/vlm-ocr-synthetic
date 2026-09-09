"""`degradation.simulated_warp` -- the one engine that can destroy text, and whether
it TELLS you which labels it destroyed.

The other two warp engines cannot lose a glyph, and that is structural rather than
lucky: `paper_warp` bounds the Jacobian, and `blender/meshes.py` builds developable
surfaces behind a camera check that refuses any view not seeing the whole sheet.
This one projects a page onto a mesh a cloth simulator folded onto itself, so a
label really can end up BEHIND the page -- and a record that still claims that
string is the poisoned data `tools/legibility.py` exists to keep out.

**The mesh in this file is built here, not simulated.** A folded flap laid back
over the middle of a sheet is enough to test every claim the module makes, it runs
on a clone with no simulator installed, and it keeps the suite free of the licence
question that governs the ARCSim meshes the engine was measured against (see
`degradation/blender/vendor/NOTICE.md`).

Runs in the html renderer's virtualenv for the reason `tests/test_ink_degradation.py`
gives, and is marked `slow` with it.
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
    import json, random, sys, tempfile
    sys.path.insert(0, {repo!r})
    from pathlib import Path
    import cv2, numpy as np
    from degradation.simulated_warp import NAME, apply_warp, frames, read_mesh, warp_regions
    from degradation.warp import engine_for, names as warp_names

    W, H = 480, 640
    SHEET = (0.20, 0.30)

    def mesh(path):
        # A sheet whose top third is folded back OVER its middle third. Material
        # space stays a plain 0.20x0.30 rectangle -- that is the point of `ms`:
        # the flat page is always a rectangle however the sheet is bent.
        rows, cols = 13, 5
        verts, flat = [], []
        for r in range(rows):
            v = SHEET[1] * r / (rows - 1)
            for c in range(cols):
                u = SHEET[0] * c / (cols - 1)
                if v <= 0.20:
                    y, z = v, 0.0
                else:                       # the flap, laid back down over v ~ 0.10-0.20
                    y, z = 0.40 - v, 0.01
                verts.append((u, y, z)); flat.append((u, v))
        lines = []
        for u, v in flat:
            lines.append(f"ms {{u}} {{v}} 0")
        for x, y, z in verts:
            lines.append(f"v {{x}} {{y}} {{z}}")
        for r in range(rows - 1):
            for c in range(cols - 1):
                a = r * cols + c + 1; b = a + 1; d = a + cols; e = d + 1
                lines.append(f"f {{a}} {{b}} {{e}}")
                lines.append(f"f {{a}} {{e}} {{d}}")
        Path(path).write_text("\\n".join(lines))

    def page():
        img = np.full((H, W, 3), 240, np.uint8)
        for i in range(12):
            cv2.putText(img, f"line {{i:02d}} ABC", (30, 60 + i * 45),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (20, 20, 20), 2, cv2.LINE_AA)
        return img

    def box(y, text):
        return {{"kind": "menu.nm", "text": text,
                "quad": [[40, y - 18], [300, y - 18], [300, y + 6], [40, y + 6]]}}

    out = {{}}
    tmp = Path(tempfile.mkdtemp())
    mesh(tmp / "frame_000.obj")
    out["frames_found"] = len(frames(tmp))
    verts, flat, faces = read_mesh(tmp / "frame_000.obj")
    out["mesh"] = [len(verts), len(flat), len(faces)]

    # v ~ 0.10-0.20 of the sheet is under the flap; v is measured from the BOTTOM,
    # so that is the LOWER-middle band of the page in pixels.
    hidden_box = box(int(H * (1 - 0.15 / 0.30)), "under the flap")
    visible_box = box(int(H * (1 - 0.27 / 0.30)), "in the clear")
    regions = [visible_box, hidden_box]

    img, marked = warp_regions(NAME, page(), {{"meshes": str(tmp), "frame": 0.0,
                                              "elev": 0.0, "azim": 0.0}},
                               random.Random(1), regions)
    out["legible"] = [r["legible"] for r in marked]
    out["occluded_corners"] = [r["occluded_corners"] for r in marked]
    out["keeps_text"] = [r["text"] for r in marked]
    out["moved"] = bool(any(r["quad"] != o["quad"] for r, o in zip(marked, regions)))
    out["image_changed"] = bool(cv2.absdiff(img, page()).sum() > 0)
    out["shape_kept"] = list(img.shape) == [H, W, 3]

    # No mesh directory -> a no-op on both, same contract as `texture.paper_overlay`
    quads = np.asarray([b["quad"] for b in regions], dtype=np.float32).reshape(-1, 4, 2)
    same, same_quads, hidden = apply_warp(NAME, page(), quads, {{}}, random.Random(1))
    out["noop"] = bool(np.array_equal(same, page()) and np.array_equal(same_quads, quads)
                       and not hidden.any())

    # A mesh without `ms` lines is refused rather than guessed at
    bad = tmp / "bad.obj"
    bad.write_text("v 0 0 0\\nv 1 0 0\\nv 0 1 0\\nf 1 2 3\\n")
    try:
        read_mesh(bad)
        out["no_ms"] = "accepted"
    except ValueError as error:
        out["no_ms"] = str(error)

    try:
        apply_warp("not_an_engine", page(), quads, {{}}, random.Random(0))
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
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_reads_a_simulated_frame(probe):
    assert probe["frames_found"] == 1
    verts, flat, faces = probe["mesh"]
    assert verts == flat == 65 and faces == 96


def test_a_mesh_without_material_space_is_refused(probe):
    """Guessing the UV is the one thing this engine must not do: `vendor/uv_unwrap.py`
    already guesses (angle-based), and on a crumpled sheet that guess is garbage."""
    assert probe["no_ms"] != "accepted"
    assert "material-space" in probe["no_ms"]


def test_the_page_is_projected_onto_the_mesh(probe):
    assert probe["image_changed"] and probe["shape_kept"] and probe["moved"]


def test_a_label_under_a_fold_is_marked_illegible(probe):
    """The whole reason this engine exists. The label keeps its text -- the record
    still knows what was printed -- but `legible: false` says a model that reads it
    off this image would be inventing it."""
    visible, hidden = probe["legible"]
    assert visible is True, "a box in the clear was called illegible"
    assert hidden is False, "a box behind the folded flap was called legible"
    assert probe["occluded_corners"][1] >= 2 > probe["occluded_corners"][0]
    assert probe["keeps_text"] == ["in the clear", "under the flap"]


def test_no_meshes_is_a_no_op(probe):
    assert probe["noop"]


def test_unknown_engine_name_raises(probe):
    assert probe["unknown_name"] != "accepted"


def test_dispatcher_routes_by_name(probe):
    assert probe["dispatch"] == "simulated_warp"
    assert {"simulated_paper", "paper_photo", "page_curl"} <= set(probe["warp_names"])
