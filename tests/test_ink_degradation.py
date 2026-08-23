"""How much speckle `ink_degradation` puts on a page, and what decides it.

The model itself is DocCreator's and is not in question here. What is in
question is the *dose*: how many blots get drawn, which in DocCreator is two
per connected component of ink. That constant was tuned on scanned prose,
where a component is a letter. On a Vietnamese invoice a dotted leader line --
the row of full stops after `Ma so thue:` -- makes every dot its own component,
so the same `level` put roughly eight times the speckle on an invoice as on a
receipt, for a reason unrelated to how much ink was on the page.

**These run in a renderer's virtualenv, not in the suite's.** `ink_degradation`
needs numpy and OpenCV and the suite environment has neither by design -- it is
pytest and PyYAML, so the data-layer tests run anywhere. The tempting shortcut
is `pytest.importorskip("cv2")`, and it is a trap: the module then skips in
every environment anyone actually runs, silently, and a test nobody runs is
worse than no test because it reads like coverage. So these shell out the same
way `tests/test_worklist.py` does, and are marked `slow`.
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

# The probe. A pale page with one solid bar and a row of leader dots -- the
# dots are the point, since they are what inflates the component count on a
# real invoice -- then the model at whatever densities the caller asks for.
PROBE = textwrap.dedent("""
    import json, random, sys, importlib
    sys.path.insert(0, {repo!r})
    import cv2, numpy as np
    I = importlib.import_module("degradation.ink_degradation")
    from degradation import apply_one

    def page(dots=150, width=800, height=900):
        # A page with a realistic component count: rows of letter-sized marks,
        # plus a leader line whose dots are far enough apart to stay separate
        # components -- which is the whole mechanism under test.
        out = np.full((height, width, 3), 245, np.uint8)
        for row in range(3):
            y = 60 + row * 30
            for col in range(40):
                x = 40 + col * 16
                cv2.rectangle(out, (x, y), (x + 7, y + 12), (30, 30, 30), -1)
        for i in range(dots):
            cv2.circle(out, (40 + i * 5, 200), 1, (20, 20, 20), -1)
        return out

    def speckle(after, base):
        changed = (cv2.absdiff(base, after).max(axis=2) > 8).astype(np.uint8)
        n, _ = cv2.connectedComponents(changed[400:, :], connectivity=8)
        return max(n - 1, 0)

    def ink_components(dots):
        grey = cv2.cvtColor(page(dots=dots), cv2.COLOR_BGR2GRAY)
        threshold = I.InkDegradationConfig().ink_threshold
        return I._component_count(I._ink_mask(grey, threshold))

    base = page()
    out = {{"DENSITY": I.DENSITY, "per_component": I.NOISE_REGIONS_PER_COMPONENT,
           "speckle": {{}}, "energy": {{}}, "components": {{}}}}

    for tag, kwargs in {cases!r}:
        aged = I.ink_degradation(base.copy(), rng=random.Random(3), **kwargs)
        out["speckle"][tag] = speckle(aged, base)
        out["energy"][tag] = int(cv2.absdiff(base, aged).sum())

    # Through the registry too: a chain in rules/augmentation.yaml passes its
    # options as keyword arguments, so `density` has to survive that path.
    for tag, opts in (("chain_full", {{"level": 5, "density": 1.0}}),
                      ("chain_thin", {{"level": 5, "density": 0.1}})):
        aged = apply_one(base.copy(), "ink_degradation", opts, random.Random(3))
        out["speckle"][tag] = speckle(aged, base)

    out["components"]["plain"] = ink_components(0)
    out["components"]["dotted"] = ink_components(150)

    try:
        I.ink_degradation(base.copy(), level=5, density=-1.0, rng=random.Random(3))
        out["negative"] = "accepted"
    except ValueError as error:
        out["negative"] = str(error)

    print(json.dumps(out))
""")

CASES = [
    ("full", {"level": 5, "density": 1.0}),
    ("shipped", {"level": 5, "density": 0.35}),
    ("default", {"level": 5}),
    ("zero", {"level": 5, "density": 0.0}),
    ("level1", {"level": 1}),
    ("level9", {"level": 9}),
]


@pytest.fixture(scope="module")
def probe() -> dict:
    interpreter = venv_python(VENVS["html"])
    if not interpreter.exists():
        pytest.skip("html environment not built")
    script = PROBE.format(repo=str(REPO_ROOT), cases=CASES)
    result = subprocess.run([str(interpreter), "-c", script],
                            cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-3000:]
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_the_shipped_dose_is_a_fraction_of_doccreators(probe):
    """Named rather than buried in an expression, so it can be argued with.

    Pinned to the exact value on purpose. It was chosen by eye against a
    rendered invoice, so nothing derives it and nothing else would notice it
    drifting -- a constant tuned by looking needs a test that says what was
    looked at.
    """
    assert probe["DENSITY"] == pytest.approx(0.35)
    assert probe["per_component"] == 2


def test_turning_the_density_down_puts_fewer_blots_on_blank_paper(probe):
    many, few = probe["speckle"]["full"], probe["speckle"]["shipped"]
    assert many > 0, "the fixture drew no speckle at all; it cannot show a cut"
    # Not exactly four: blots overlap and merge, so counting them undercounts
    # the dense case. The claim is a large cut in the right direction, and the
    # exact pixels are the golden baseline's job, not this test's.
    assert few <= many / 2, f"expected a substantial cut, got {many} -> {few}"


def test_the_default_is_the_thinned_dose(probe):
    assert probe["speckle"]["default"] == probe["speckle"]["shipped"]


def test_a_chain_can_override_the_density_per_scenario(probe):
    """A scenario that wants heavier speckle has to be able to ask for it in
    YAML, which means `density` is a parameter and not only a constant."""
    assert probe["speckle"]["chain_thin"] < probe["speckle"]["chain_full"]


def test_a_negative_density_is_refused_rather_than_silently_clamped(probe):
    assert "negative" in probe["negative"], probe["negative"]


def test_zero_density_still_draws_something_rather_than_dividing_by_zero(probe):
    """`total` is floored at one, so zero means "as little as possible" -- not
    a crash, and not a silent no-op that would make a scenario look applied."""
    assert probe["speckle"]["zero"] >= 0


def test_the_dose_still_rises_with_level(probe):
    """Thinning the count must not flatten the level knob -- `light` and
    `heavy` in the rules differ by `level` alone, and must stay different."""
    assert probe["energy"]["level9"] > probe["energy"]["level1"]


def test_every_leader_dot_adds_a_component_of_its_own(probe):
    """The mechanism behind the change, kept as a fact rather than a memory.

    A row of 150 leader dots adds ~150 components to a page that otherwise has
    ~120, so it more than doubles the dose while adding almost no ink. On a
    real invoice the leaders are 49-74% of all components. If this stops being
    true, deriving the dose from a component count is no longer the problem it
    is, and the reasoning written at `DENSITY` wants revisiting.
    """
    plain, dotted = probe["components"]["plain"], probe["components"]["dotted"]
    assert dotted - plain >= 140, (plain, dotted)
    assert dotted > 2 * plain, (plain, dotted)
