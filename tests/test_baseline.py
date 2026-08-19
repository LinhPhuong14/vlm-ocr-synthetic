"""The golden baseline's own conditions.

W2c, and Law 8 behind it: a comparison has to record what it was taken under.
The file used to pin only the output, so when the rule-base grew from five
layouts to fourteen it went red and could not say whether the plan had moved or
the renderer had regressed -- and the cheapest way to make it green was to
recapture, which is the same as deleting the check.

No image is rendered here. Everything below is a function of two dicts.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import baseline as B  # noqa: E402

INPUTS = {
    "layouts": ["eatery_ascii", "eatery_indexed"],
    "seed": 2026,
    "per_backend": 2,
    "pairing": "paired",
    "clean": False,
    "rules": {"rulebase/rules": "aaa", "rulebase/layouts": "bbb",
              "rulebase/corpus": "ccc"},
}


def plan(images=None, **input_changes):
    return {
        "inputs": {**INPUTS, **input_changes},
        "images": images if images is not None else {"html/html_000.jpg": "h0"},
        "metadata": {"html": ["m0"]},
        "counts": {"by_backend": {"html": 1}, "by_layout": {"eatery_ascii": 1}},
        "dataset_json": "d",
    }


def compare(want_plan, have_plan):
    return B.compare({"plans": {"n": want_plan}}, {"plans": {"n": have_plan}})


# ------------------------------------------------- the two kinds of red


def test_identical_runs_are_silent():
    assert compare(plan(), plan()) == ([], [])


def test_the_same_plan_with_different_pixels_is_a_regression():
    """The one thing this file exists to catch."""
    moved, regressed = compare(plan(), plan(images={"html/html_000.jpg": "CHANGED"}))
    assert moved == []
    assert regressed and "differs" in regressed[0]


def test_a_changed_layout_list_is_the_plan_moving_not_a_regression():
    moved, regressed = compare(
        plan(), plan(layouts=["eatery_ascii", "eatery_indexed", "market_vat"],
                     images={"html/html_000.jpg": "CHANGED"}))
    assert regressed == [], "a plan drawn under other conditions is not evidence"
    assert moved and "layouts 2 -> 3" in moved[0] and "+market_vat" in moved[0]


def test_a_changed_rule_base_is_the_plan_moving():
    """A weight edited in `rules/` changes the pixels, legitimately."""
    changed = dict(INPUTS["rules"], **{"rulebase/rules": "zzz"})
    moved, regressed = compare(plan(), plan(rules=changed,
                                            images={"html/html_000.jpg": "X"}))
    assert regressed == []
    assert moved and "rulebase/rules/ changed" in moved[0]


def test_each_fingerprinted_input_is_named_separately():
    """One hash for all of them could not say which input moved."""
    for directory in (*B.FINGERPRINTED, B.LAYOUT_ROOT):
        changed = dict(INPUTS["rules"], **{directory: "zzz"})
        moved, _ = compare(plan(), plan(rules=changed))
        assert moved and f"{directory}/ changed" in moved[0], directory


NAMED = ["eatery_ascii", "market_vat"]

PROBE_OPTION = """
      - id: zz_acceptance_probe
        weight: 1
        requires: [has_vat_lines]
        tags: [vat_rows]
"""


def add_a_layout():
    """A whole new layout, the way one is really added: a file AND a rule."""
    spec = B.REPO_ROOT / B.LAYOUT_ROOT / "zz_acceptance_probe.yaml"
    rules = B.REPO_ROOT / B.RULES_ROOT / "layout.yaml"
    original = rules.read_text(encoding="utf-8")
    anchor = """      - id: market_vat
        weight: 2
        requires: [has_vat_lines]
        tags: [vat_rows]
"""
    assert anchor in original
    spec.write_text("id: zz_acceptance_probe\nname: probe\nwidth: [40, 44]\n",
                    encoding="utf-8")
    rules.write_text(original.replace(anchor, anchor + PROBE_OPTION), encoding="utf-8")
    return spec, rules, original


def test_adding_a_layout_no_plan_draws_changes_no_input():
    """Criterion 1 of W2c, at the level it is decided.

    A hash of the whole rules directory would fire here, and the baseline would
    be red every time someone adds content -- the erosion this change exists to
    stop. It is safe to ignore because the pixels genuinely do not move: a run
    pinned to `eatery_ascii` resolves the same recipe before and after, which
    the test below measures rather than assumes.
    """
    before = B.rules_fingerprint(NAMED)
    spec, rules, original = add_a_layout()
    try:
        assert B.rules_fingerprint(NAMED) == before
    finally:
        spec.unlink()
        rules.write_text(original, encoding="utf-8")


def test_adding_a_layout_does_not_move_a_pinned_recipe():
    """Why criterion 1 is honest rather than convenient.

    If a new layout option shifted the draw of a run pinned to another layout,
    ignoring it in the fingerprint would be hiding a real change. It does not.
    """
    from rulebase.spec import load_rules, sample_recipe

    def drawn():
        rules = load_rules()
        return [sample_recipe(seed=seed, rules=rules,
                              force={"layout": "eatery_ascii"}).to_dict()
                for seed in (2026, 2027, 3026, 4026)]

    before = drawn()
    spec, rules_file, original = add_a_layout()
    try:
        assert drawn() == before
    finally:
        spec.unlink()
        rules_file.write_text(original, encoding="utf-8")


def test_a_weight_the_plan_draws_is_an_input():
    """Criterion 4: the fingerprint has to catch a rules edit."""
    before = B.rules_fingerprint(NAMED)
    path = B.REPO_ROOT / B.RULES_ROOT / "visual.yaml"
    original = path.read_text(encoding="utf-8")
    anchor = "  - id: thermal_dark\n    weight: 3"
    assert anchor in original
    path.write_text(original.replace(anchor, "  - id: thermal_dark\n    weight: 4"),
                    encoding="utf-8")
    try:
        assert B.rules_fingerprint(NAMED)[B.RULES_ROOT] != before[B.RULES_ROOT]
    finally:
        path.write_text(original, encoding="utf-8")


def test_a_layout_the_plan_draws_is_an_input():
    before = B.rules_fingerprint(NAMED)
    path = B.REPO_ROOT / B.LAYOUT_ROOT / "eatery_ascii.yaml"
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "\n# touched\n", encoding="utf-8")
    try:
        assert B.rules_fingerprint(NAMED)[B.LAYOUT_ROOT] != before[B.LAYOUT_ROOT]
    finally:
        path.write_text(original, encoding="utf-8")


def test_the_corpus_is_an_input():
    before = B.rules_fingerprint(NAMED)
    path = B.REPO_ROOT / "rulebase" / "corpus" / "vi" / "streets.txt"
    original = path.read_text(encoding="utf-8")
    path.write_text(original + "Đường Thử Nghiệm\n", encoding="utf-8")
    try:
        assert B.rules_fingerprint(NAMED)[B.CORPUS_ROOT] != before[B.CORPUS_ROOT]
    finally:
        path.write_text(original, encoding="utf-8")


def test_the_fingerprint_is_stable_when_nothing_changed():
    """Contents, not mtimes: a fresh clone must not look like a change."""
    assert B.rules_fingerprint(NAMED) == B.rules_fingerprint(NAMED)


def test_the_layouts_hash_does_not_depend_on_the_order_they_are_named():
    assert (B.rules_fingerprint(["market_vat", "eatery_ascii"])
            == B.rules_fingerprint(["eatery_ascii", "market_vat"]))


def test_seed_count_and_pairing_are_pinned_too():
    for key, value in (("seed", 4242), ("per_backend", 9), ("pairing", "independent")):
        moved, regressed = compare(plan(), plan(**{key: value}))
        assert moved and key in moved[0], key
        assert regressed == []


def test_a_baseline_taken_before_inputs_were_pinned_says_so():
    old = plan()
    del old["inputs"]
    moved, regressed = compare(old, plan())
    assert regressed == []
    assert moved and "predates input pinning" in moved[0]


# --------------------------------------------------------- the plans


def test_every_plan_names_its_layouts_explicitly():
    """The root cause. A plan that takes the directory is not fixed.

    `split_by_layout` walks the list in order, so an unnamed set draws
    different layouts the day someone adds one -- which is precisely how this
    baseline went red without being able to explain itself.
    """
    from rulebase import available_layouts

    known = set(available_layouts())
    for name, spec in B.PLANS.items():
        assert spec["layouts"], f"{name} names no layouts"
        assert len(set(spec["layouts"])) == len(spec["layouts"]), f"{name} repeats one"
        assert set(spec["layouts"]) <= known, f"{name}: {set(spec['layouts']) - known}"
        assert "--layouts" in B.arguments(spec)


def test_a_plan_asks_the_driver_for_exactly_what_it_declares():
    argv = B.arguments({"per_backend": 4, "seed": 7, "layouts": ["a", "b"]})
    assert argv == ["-n", "4", "--seed", "7", "--layouts", "a", "b"]


def test_the_widest_plan_covers_every_layout_that_ships():
    """Not required to stay true -- a new layout must not turn the file red --
    but true today, and a test is how anyone finds out it stopped being."""
    from rulebase import available_layouts

    assert sorted(B.PLANS["n14"]["layouts"]) == sorted(available_layouts())
