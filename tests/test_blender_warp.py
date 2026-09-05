"""`degradation.blender` -- deformed-page meshes, and the Blender render built from one.

Two tiers, same reason `tests/test_ink_degradation.py` has them: this needs numpy (and
`degradation.blender.meshes` alone needs only that), so it shells out to the html
renderer's virtualenv rather than using `pytest.importorskip` -- see that file's own
docstring for why that shortcut is a trap. `degradation.blender.render` needs a real
`blender` executable on top, which this suite does not assume exists; that half is marked
`slow` AND skips outright when `blender` is not found, rather than failing a clone that
never ran `make setup-blender`.
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

MESH_PROBE = textwrap.dedent("""
    import json, random, sys
    sys.path.insert(0, {repo!r})
    from pathlib import Path
    from degradation.blender import meshes

    out = {{"vert_counts": {{}}, "face_counts": {{}}, "finite": {{}}, "reproducible": {{}},
           "seed_matters": {{}}}}
    grid = (12, 16)  # small, so this stays fast -- shape is what is under test, not detail

    for name in meshes.names():
        extra = {{"axis": "x"}} if name == "fold_crease" else {{}}
        path_a = Path("/tmp/_mesh_probe_a.obj")
        path_b = Path("/tmp/_mesh_probe_b.obj")
        meshes.generate(name, 0.21, 0.297, random.Random(3), path_a,
                         {{**extra, "grid": grid}})
        text_a = path_a.read_text()
        verts = [l for l in text_a.splitlines() if l.startswith("v ")]
        faces = [l for l in text_a.splitlines() if l.startswith("f ")]
        out["vert_counts"][name] = len(verts)
        out["face_counts"][name] = len(faces)
        out["finite"][name] = all(
            all(abs(float(x)) < 1e6 for x in line.split()[1:]) for line in verts)

        meshes.generate(name, 0.21, 0.297, random.Random(3), path_b, {{**extra, "grid": grid}})
        out["reproducible"][name] = text_a == path_b.read_text()

        path_c = Path("/tmp/_mesh_probe_c.obj")
        meshes.generate(name, 0.21, 0.297, random.Random(4), path_c, {{**extra, "grid": grid}})
        out["seed_matters"][name] = text_a != path_c.read_text()

    # axis="y" for fold_crease: same grid, transposed roles -- must not crash or mis-shape.
    path_y = Path("/tmp/_mesh_probe_y.obj")
    meshes.generate("fold_crease", 0.21, 0.297, random.Random(3), path_y,
                     {{"axis": "y", "grid": grid}})
    out["fold_crease_y_verts"] = len([
        l for l in path_y.read_text().splitlines() if l.startswith("v ")])

    try:
        meshes.generate("not_a_scenario", 0.21, 0.297, random.Random(0),
                         Path("/tmp/_mesh_probe_bad.obj"))
        out["unknown_scenario"] = "accepted"
    except KeyError as error:
        out["unknown_scenario"] = str(error)

    print(json.dumps(out))
""")


@pytest.fixture(scope="module")
def mesh_probe() -> dict:
    interpreter = venv_python(VENVS["html"])
    if not interpreter.exists():
        pytest.skip("html environment not built")
    script = MESH_PROBE.format(repo=str(REPO_ROOT))
    result = subprocess.run([str(interpreter), "-c", script],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-3000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_every_mesh_has_exactly_grid_rows_times_columns_vertices(mesh_probe):
    """A grid `(nx, ny)` must write exactly `nx * ny` vertices -- `fold_crease` once wrote
    400 per row regardless of `grid` (a mismatched `steps` default in `_developable_bend`),
    padding the file with unused vertices no face ever referenced."""
    expected = 12 * 16
    for name, count in mesh_probe["vert_counts"].items():
        assert count == expected, f"{name}: expected {expected} vertices, got {count}"


def test_every_mesh_is_finite(mesh_probe):
    for name, ok in mesh_probe["finite"].items():
        assert ok, f"{name} wrote a non-finite or absurd vertex coordinate"


def test_mesh_generation_is_reproducible_from_a_seed(mesh_probe):
    for name, ok in mesh_probe["reproducible"].items():
        assert ok, f"{name}: same seed produced a different mesh"
    for name, ok in mesh_probe["seed_matters"].items():
        assert ok, f"{name}: different seeds produced the identical mesh"


def test_fold_crease_axis_y_does_not_crash_or_mis_shape(mesh_probe):
    assert mesh_probe["fold_crease_y_verts"] == 12 * 16


def test_an_unknown_scenario_fails_loudly(mesh_probe):
    assert "not_a_scenario" in mesh_probe["unknown_scenario"]
    assert mesh_probe["unknown_scenario"] != "accepted"


RENDER_PROBE = textwrap.dedent("""
    import json, random, sys
    sys.path.insert(0, {repo!r})
    import numpy as np
    from degradation.blender import warp_regions

    img = np.full((400, 300, 3), 245, np.uint8)

    def grid(w, h, nx=3, ny=4):
        xs = np.linspace(30, w - 30, nx)
        ys = np.linspace(30, h - 30, ny)
        return [[[x - 15, y - 8], [x + 15, y - 8], [x + 15, y + 8], [x - 15, y + 8]]
                for y in ys for x in xs]

    boxes = [{{"kind": "field", "quad": q}} for q in grid(300, 400)]

    new_img, new_boxes = warp_regions("page_curl", img, {{"angle": 30.0}},
                                       random.Random(11), boxes)

    h, w = new_img.shape[:2]
    xs = [x for b in new_boxes for x, y in b["quad"]]
    ys = [y for b in new_boxes for x, y in b["quad"]]
    print(json.dumps({{
        "image_shape": list(new_img.shape),
        "box_count": len(new_boxes),
        "input_box_count": len(boxes),
        "within_frame": bool(min(xs) >= -1 and max(xs) <= w + 1
                              and min(ys) >= -1 and max(ys) <= h + 1),
        "all_finite": bool(all(np.isfinite(v) for v in xs + ys)),
    }}))
""")


@pytest.fixture(scope="module")
def render_probe() -> dict:
    interpreter = venv_python(VENVS["html"])
    if not interpreter.exists():
        pytest.skip("html environment not built")

    # A plain `shutil.which` here, not `degradation.blender.render.find_blender` -- that
    # module imports cv2/numpy/scipy at load time, and this suite's own interpreter is
    # bare pytest + PyYAML on purpose (see this file's docstring). `find_blender` checks a
    # couple of fixed install paths beyond PATH too; `which` alone is close enough for a
    # test that only needs to know whether to skip.
    import shutil
    if not shutil.which("blender"):
        pytest.skip("blender not found -- run `make setup-blender`")

    script = RENDER_PROBE.format(repo=str(REPO_ROOT))
    result = subprocess.run([str(interpreter), "-c", script], cwd=REPO_ROOT,
                            capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stderr[-5000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_a_real_render_keeps_every_box_and_puts_them_in_frame(render_probe):
    """The one test that actually shells out to Blender -- everything else in this file is
    the mesh-generation half, which does not need it. `render_probe` skips this whole test
    when `blender` is not on PATH, rather than failing a clone that never opted in."""
    assert render_probe["box_count"] == render_probe["input_box_count"]
    assert render_probe["all_finite"]
    assert render_probe["within_frame"]
    assert len(render_probe["image_shape"]) == 3
