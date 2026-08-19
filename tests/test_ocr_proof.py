"""The scoring, not the OCR: no image is read here.

W2e. A pooled recall is a comparison point, so Law 8 applies to it -- it has to
carry the conditions it was taken under. The condition that turned out to matter
is the **layout mix**: ageing costs `invoice_brand` 0.026 of its recall and
`market_barcode` 0.552, twenty-one times as much, so a pooled number moves when
the mix moves and says nothing about anything else having changed.

The report shipped in `data/` is the fixture. Re-aggregating its own per-image
scores under a different mix is exactly the situation these functions exist to
survive, and it needs no engine.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import ocr_proof as P  # noqa: E402

AGED = REPO_ROOT / "data" / "dataset60" / "proof" / "ocr_report.json"
CLEAN = REPO_ROOT / "data" / "dataset60_clean" / "proof" / "ocr_report.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def scored():
    if not AGED.exists():
        pytest.skip("no committed OCR report")
    return load(AGED)["images"]


def summarise(per_image, report=None):
    return {
        "pooled": round(P.mean([r["token_recall"] for r in per_image]), 4),
        "by_layout": P.bucket(per_image, lambda r: r.get("layout", "")),
        "conditions": P.conditions(per_image, report or {}),
    }


# ------------------------------------------------- the acceptance criterion


def test_a_different_layout_mix_moves_the_pooled_score_and_not_the_strata(scored):
    """Two datasets differing ONLY in layout mix, same everything else.

    Built by resampling one real run, so the images -- and therefore the ageing,
    the printers, the renderers -- are identical between the two. All that
    differs is how many of each layout are in the pool.

    The pooled number must move, because that is the defect being guarded
    against. The per-layout numbers must not, because they hold the layout fixed
    and that is what makes them the quantity worth quoting.
    """
    heavy = [r for r in scored]
    # Half the invoices dropped: the same images, a different mix.
    light = [r for r in scored
             if not r["layout"].startswith("invoice_") or hash(r["file_name"]) % 2]
    assert len(light) < len(heavy)

    a, b = summarise(heavy), summarise(light)
    assert a["pooled"] != b["pooled"], "the pooled score ignored a change of mix"

    shared = set(a["by_layout"]) & set(b["by_layout"])
    assert len(shared) >= 5
    for layout in shared:
        if a["by_layout"][layout]["images"] != b["by_layout"][layout]["images"]:
            continue          # this layout was resampled; only untouched ones apply
        assert a["by_layout"][layout]["token_recall"] == \
            b["by_layout"][layout]["token_recall"], layout


# ------------------------------------------------------ recorded conditions


def test_the_report_records_the_layout_set_it_scored(scored):
    conds = P.conditions(scored, {"engine": "x", "lang": "vie", "psm": 4})
    assert conds["layouts"] == sorted({r["layout"] for r in scored})
    assert sum(conds["images_per_layout"].values()) == len(scored)
    assert conds["psm"] == 4


def test_two_reports_over_different_layout_sets_refuse_to_be_pooled():
    left = {"conditions": {"layouts": ["a", "b"], "engine": "t", "lang": "vie", "psm": 4}}
    right = {"conditions": {"layouts": ["a", "b", "c"], "engine": "t", "lang": "vie", "psm": 4}}
    refusal = P.comparable(left, right)
    assert refusal and "layout sets differ" in refusal[0] and "+c" in refusal[0]


def test_the_same_conditions_compare_freely():
    same = {"conditions": {"layouts": ["a"], "engine": "t", "lang": "vie", "psm": 4}}
    assert P.comparable(same, dict(same)) == []


def test_a_different_engine_or_mode_also_refuses():
    base = {"conditions": {"layouts": ["a"], "engine": "t5", "lang": "vie", "psm": 4}}
    for field, value in (("engine", "t4"), ("lang", "eng"), ("psm", 6)):
        other = {"conditions": dict(base["conditions"], **{field: value})}
        assert any(field in line for line in P.comparable(base, other)), field


def test_a_report_from_before_conditions_were_recorded_says_so():
    assert "predates" in P.comparable({}, {"conditions": {}})[0]


# -------------------------------------------------- the comparison it emits


def test_the_comparison_gives_the_per_layout_drop_even_when_pooling_is_refused():
    """The refusal must not take the useful half of the answer with it."""
    before = {"conditions": {"layouts": ["a", "b"], "engine": "t", "lang": "v", "psm": 4},
              "by_layout": {"a": {"token_recall": 0.9, "images": 2},
                            "b": {"token_recall": 0.8, "images": 2}},
              "frameworks": {"html": {"token_recall": 0.85}}}
    after = {"conditions": {"layouts": ["a", "b", "c"], "engine": "t", "lang": "v", "psm": 4},
             "by_layout": {"a": {"token_recall": 0.5, "images": 2},
                           "b": {"token_recall": 0.79, "images": 2},
                           "c": {"token_recall": 0.1, "images": 2}},
             "frameworks": {"html": {"token_recall": 0.46}}}

    out = P.compare_reports(before, after, "x.json")
    assert out["refused"], "different layout sets were pooled anyway"
    assert "pooled" not in out
    drops = {row["layout"]: row["drop"] for row in out["by_layout"]}
    assert drops == {"a": 0.4, "b": 0.01}
    assert out["layouts_only_here"] == ["c"]
    # Ordered by how much was lost, so the worst-hit layout is the first row.
    assert out["by_layout"][-1]["layout"] == "a"


def test_the_comparison_pools_when_the_conditions_match():
    before = {"conditions": {"layouts": ["a"], "engine": "t", "lang": "v", "psm": 4},
              "by_layout": {"a": {"token_recall": 0.9, "images": 2}},
              "frameworks": {"html": {"token_recall": 0.9}}}
    after = {"conditions": {"layouts": ["a"], "engine": "t", "lang": "v", "psm": 4},
             "by_layout": {"a": {"token_recall": 0.6, "images": 2}},
             "frameworks": {"html": {"token_recall": 0.6}}}
    out = P.compare_reports(before, after, "x.json")
    assert out["refused"] == []
    assert out["pooled"] == {"html": -0.3}


def test_the_comparison_reaches_the_readme_and_not_only_the_json():
    """A finding kept in JSON is a finding nobody reads.

    The per-layout drop is the whole point of the comparison, so it has to be
    in the prose a reader of `proof/README.md` actually meets -- including the
    refusal, when the pooled halves were not allowed to be put side by side.
    """
    report = {"against": {
        "source": "clean/ocr_report.json",
        "by_layout": [{"layout": "steady", "before": 0.95, "after": 0.92, "drop": 0.03},
                      {"layout": "fragile", "before": 0.90, "after": 0.35, "drop": 0.55}],
        "refused": ["the layout sets differ (+extra)"],
        "layouts_only_here": ["extra"], "layouts_only_there": []}}
    text = "\n".join(P._against_note(report))
    assert "clean/ocr_report.json" in text
    assert "| fragile | 0.900 | 0.350 | 0.550 |" in text
    assert "18 times as much" in text, text        # 0.55 / 0.03
    assert "not** compared" in text and "layout sets differ" in text
    assert "`extra` is in this dataset only" in text


def test_a_report_with_nothing_to_compare_against_adds_no_section():
    assert P._against_note({}) == []


# ------------------------------------------- what the shipped reports say


@pytest.mark.skipif(not (AGED.exists() and CLEAN.exists()), reason="no reports")
def test_the_two_shipped_reports_are_over_the_same_layouts_so_they_may_be_compared():
    aged, clean = load(AGED)["summary"], load(CLEAN)["summary"]
    assert P.comparable(clean, aged) == []


@pytest.mark.skipif(not (AGED.exists() and CLEAN.exists()), reason="no reports")
def test_ageing_costs_layouts_wildly_different_amounts():
    """The finding W2e exists because of, kept as a fact rather than a memory.

    If this ever stops being true the stratification is no longer load-bearing
    and the reasoning in the READMEs should be revisited -- which is worth
    finding out from a test rather than from a conclusion drawn years later.
    """
    aged, clean = load(AGED)["summary"], load(CLEAN)["summary"]
    drops = {name: clean["by_layout"][name]["token_recall"] - entry["token_recall"]
             for name, entry in aged["by_layout"].items()
             if name in clean["by_layout"]}
    assert len(drops) >= 10
    assert min(drops.values()) >= 0, drops
    assert max(drops.values()) > 8 * max(min(drops.values()), 0.01), drops
