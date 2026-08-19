"""The stopwatch, and what it is allowed to claim.

A profiler is a measuring instrument, so the tests here are about the two ways
a measuring instrument lies: by disturbing what it measures (the generator must
not get slower, or draw a different pixel, because this module exists), and by
reporting a breakdown that does not add up (nested stages counted twice, or a
remainder quietly dropped).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import profile_pipeline as P  # noqa: E402

import profiling  # noqa: E402


@pytest.fixture(autouse=True)
def _off():
    """Leave it off however the test ended -- an escaped `enable()` would make
    every later test in the process pay for the stopwatch."""
    yield
    profiling.disable()


def _spin(seconds: float = 0.002) -> None:
    import time

    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


# ------------------------------------------------------ off means off


def test_off_it_allocates_nothing_and_returns_one_shared_object():
    """The instrumentation sits in the hot path of every renderer, so `off`
    has to be cheaper than the thing being measured by a wide margin. Sharing
    one object is how: no allocation, no generator frame, no bookkeeping."""
    profiling.disable()
    assert profiling.stage("a") is profiling.stage("b")
    with profiling.stage("a"):
        pass
    assert profiling.report()["stages"] == {}


def test_off_records_nothing_even_for_a_stage_that_ran():
    profiling.disable()
    with profiling.stage("render"):
        _spin()
    assert profiling.report()["stages"] == {}


# ------------------------------------------------------ the arithmetic


def test_a_nested_stage_is_not_counted_twice():
    """Exclusive minus its children, so the column can be summed.

    Without this the total exceeds the wall clock as soon as anything nests,
    and every percentage in the table is wrong in the same direction.
    """
    profiling.enable(calibrate=False)
    with profiling.stage("outer"):
        _spin(0.004)
        with profiling.stage("inner"):
            _spin(0.006)
    stages = profiling.report()["stages"]
    assert set(stages) == {"outer", "outer/inner"}
    outer, inner = stages["outer"], stages["outer/inner"]
    assert outer["inclusive"] >= inner["inclusive"]
    # Two microseconds, because the report rounds each of the three numbers to
    # one on its own and the errors do not cancel. Anything tighter would be
    # testing the rounding rather than the arithmetic.
    assert outer["exclusive"] == pytest.approx(
        outer["inclusive"] - inner["inclusive"], abs=2e-6)
    # The pair of them add up to the parent, which is the property the table
    # depends on.
    assert (outer["exclusive"] + inner["exclusive"]) == pytest.approx(
        outer["inclusive"], abs=2e-6)


def test_the_child_carries_the_parent_in_its_name():
    profiling.enable(calibrate=False)
    with profiling.stage("degradation"):
        with profiling.stage("gradient_domain"):
            pass
    assert "degradation/gradient_domain" in profiling.report()["stages"]


def test_sibling_stages_accumulate_rather_than_replace():
    profiling.enable(calibrate=False)
    for _ in range(3):
        with profiling.stage("render"):
            _spin(0.001)
    entry = profiling.report()["stages"]["render"]
    assert entry["calls"] == 3
    assert entry["inclusive"] > 0


def test_the_unmeasured_remainder_is_a_number_and_not_a_silence():
    """A breakdown covering 70% of the time is not a breakdown of the run.

    Reporting the gap is what lets a reader tell the two apart, so it is part
    of the report rather than something to work out from the columns.
    """
    profiling.enable(calibrate=False)
    _spin(0.010)                      # outside any stage, on purpose
    with profiling.stage("counted"):
        _spin(0.002)
    out = profiling.report()
    assert out["unattributed"] > 0.005
    assert out["unattributed_share"] > 0.5
    assert out["unattributed"] == pytest.approx(
        out["wall"] - out["stages"]["counted"]["exclusive"], abs=1e-5)


def test_report_accepts_the_real_span_from_outside():
    """A driver timing a subprocess knows seconds the child's clock never saw --
    interpreter start-up, imports. Passing them in is what makes the stages
    sum to the real time rather than to the part after `enable()`."""
    profiling.enable(calibrate=False)
    with profiling.stage("work"):
        _spin(0.002)
    out = profiling.report(wall=10.0)
    assert out["wall"] == 10.0
    assert out["unattributed"] > 9.9


# ------------------------------------------------------ measuring itself


def test_the_instrument_reports_its_own_cost():
    profiling.enable()                # calibrates
    for _ in range(50):
        with profiling.stage("x"):
            pass
    overhead = profiling.report()["overhead"]
    assert overhead["calls"] == 50
    assert overhead["per_call"] > 0, "calibration produced a free stopwatch"
    assert overhead["per_call"] < 1e-4, "a stage costing 100us would drown the signal"
    assert overhead["total"] == pytest.approx(
        overhead["calls"] * overhead["per_call"], abs=1e-9)


def test_calibration_does_not_leave_itself_in_the_totals():
    """Calibration runs thousands of stages. If they survived into the report
    they would be the largest stage in every profile."""
    profiling.enable()
    assert profiling.report()["stages"] == {}
    assert profiling.report()["overhead"]["calls"] == 0


# ------------------------------------------------------ merging


def test_merging_adds_the_walls_and_the_stages():
    left = {"wall": 2.0, "stages": {"render": {"calls": 1, "inclusive": 1.0,
                                               "exclusive": 1.0}},
            "overhead": {"calls": 10, "per_call": 1e-7}}
    right = {"wall": 3.0, "stages": {"render": {"calls": 2, "inclusive": 2.0,
                                                "exclusive": 2.0},
                                     "export": {"calls": 1, "inclusive": 0.5,
                                                "exclusive": 0.5}},
             "overhead": {"calls": 5, "per_call": 3e-7}}
    out = profiling.merge([left, right])
    assert out["wall"] == 5.0
    assert out["stages"]["render"] == {"calls": 3, "inclusive": 3.0, "exclusive": 3.0}
    assert out["stages"]["export"]["calls"] == 1
    assert out["unattributed"] == pytest.approx(5.0 - 3.5)
    assert out["overhead"]["calls"] == 15
    # Weighted by calls, not averaged: two processes that made very different
    # numbers of calls do not get an equal say in the per-call cost.
    assert out["overhead"]["per_call"] == pytest.approx((10 * 1e-7 + 5 * 3e-7) / 15)


def test_tops_keeps_only_the_stages_that_partition_the_run():
    one = {"stages": {"degradation": {}, "degradation/holes": {}, "render": {}}}
    assert set(profiling.tops(one)) == {"degradation", "render"}


# ------------------------------------------------------ the cost model


def _report(images: int, **stages) -> dict:
    return {"images": images,
            "stages": {name: {"calls": images, "inclusive": value, "exclusive": value}
                       for name, value in stages.items()}}


def test_the_cost_model_separates_what_is_fixed_from_what_is_per_image():
    """Eight workers pay start-up eight times and the per-image cost once
    between them. A model that merged the two would predict a parallel run as
    though splitting it were free."""
    pass_a = {"html": _report(4, interpreter=2.0, startup=1.0, render=8.0, export=0.4)}
    model = P.cost_model(pass_a, {}, {})
    assert model["fixed_per_process"]["html"] == 3.0
    assert model["per_image"]["html"] == {"export": 0.1, "render": 2.0}

    one = P.predict(model, {"html": 10}, processes=1)
    assert one["seconds"] == pytest.approx(2.1 * 10 + 3.0)
    eight = P.predict(model, {"html": 10}, processes=8)
    assert eight["seconds"] == pytest.approx(2.1 * 10 + 3.0 * 8)


def test_the_cost_model_uses_inclusive_time_for_a_stage_with_children():
    """`degradation` does almost nothing itself -- all of it is in the models
    it calls. Taken exclusively it would read as free, and the largest stage of
    two renderers would vanish from the table."""
    pass_a = {"html": {"images": 2, "stages": {
        "degradation": {"calls": 2, "inclusive": 4.0, "exclusive": 0.002},
        "degradation/holes": {"calls": 2, "inclusive": 4.0, "exclusive": 3.998},
    }}}
    model = P.cost_model(pass_a, {}, {})
    assert model["per_image"]["html"]["degradation"] == 2.0
    assert "degradation/holes" not in model["per_image"]["html"]


def test_the_per_model_costs_pool_every_run_that_drew_them():
    pass_a = {"html": {"images": 1, "stages": {
        "degradation/holes": {"calls": 1, "inclusive": 1.0, "exclusive": 1.0}}}}
    pass_b = {"html": {"heavy": {"images": 2, "stages": {
        "degradation/holes": {"calls": 3, "inclusive": 3.0, "exclusive": 3.0},
        "degradation": {"calls": 2, "inclusive": 3.0, "exclusive": 0.0}}}}}
    model = P.cost_model(pass_a, pass_b, {})
    assert model["per_degradation_model"]["holes"]["calls"] == 4
    assert model["per_degradation_model"]["holes"]["per_call"] == 1.0
    # And the chain's own per-image cost, which is what a plan is made of.
    assert model["per_augmentation"]["heavy"]["html"] == 1.5


def test_predicting_a_backend_the_model_never_measured_says_so():
    model = P.cost_model({"html": _report(1, render=1.0)}, {}, {})
    with pytest.raises(KeyError, match="synthdog"):
        P.predict(model, {"synthdog": 5})


def test_validation_is_folded_in_from_where_it_actually_runs():
    """It happens in the worker, not in a renderer, so a backend's own profile
    cannot see it. It still has to appear in the per-image costs, or every
    prediction is short by it."""
    model = P.cost_model({"html": _report(4, render=8.0)}, {},
                         {"html": {"calls": 4, "inclusive": 0.8, "exclusive": 0.8}})
    assert model["per_image"]["html"]["validation"] == 0.2


def test_the_table_names_every_stage_even_the_ones_that_did_not_run():
    """A stage missing from the table reads as a stage nobody thought of. A
    zero reads as a stage that cost nothing, which is the true statement."""
    lines = P.table({"html": {"images": 1, "wall": 2.0, "unattributed": 0.0,
                              "stages": {"render": {"calls": 1, "inclusive": 1.0,
                                                    "exclusive": 1.0}}}}, {})
    text = "\n".join(lines)
    for stage in P.STAGES:
        assert f"| {stage} |" in text, stage
    assert "unattributed" in text


def test_the_cost_model_records_the_conditions_it_was_taken_under():
    """Law 8, applied to seconds. Ageing is between 14% and 55% of an image
    depending on the renderer, so which chains were drawn moves the per-image
    cost on its own -- and two numbers taken over different mixes compared
    silently is how an optimisation gets credited with a change in the draw."""
    pass_a = {"html": {"images": 4, "stages": {
        "degradation": {"calls": 4, "inclusive": 2.0, "exclusive": 0.0},
        "degradation/holes": {"calls": 4, "inclusive": 1.0, "exclusive": 1.0},
        "degradation/blur": {"calls": 1, "inclusive": 1.0, "exclusive": 1.0}}}}
    conds = P.cost_model(pass_a, {}, {}, seed=4242)["conditions"]
    assert conds["seed"] == 4242
    assert conds["images"] == {"html": 4}
    assert conds["degradation_calls"]["html"] == {"blur": 1, "holes": 4}
    assert conds["machine"]["cpus"]
    assert "not pinned" in conds["augmentation"]


def test_pricing_the_plan_shows_what_the_process_churn_costs():
    """The finding this profile exists to make findable.

    A renderer process is started per run, and a run is one layout, so a
    twenty-image shard over fourteen layouts starts fourteen of them. Whether
    that is a rounding error or a quarter of the run is arithmetic the table
    has to do, because nobody does it by eye.
    """
    model = {"per_image": {"html": {"render": 1.0}},
             "fixed_per_process": {"html": 0.75}}
    churned = P.plan_cost(model, {"html": (14, 20)})
    once = P.plan_cost(model, {"html": (1, 20)})
    assert "| 14 | 20 | 1.43 |" in churned[2]
    assert "34%" in churned[2], churned          # 10.5 fixed of 30.5 total
    assert "4%" in once[2], once                 # 0.75 of 20.75
