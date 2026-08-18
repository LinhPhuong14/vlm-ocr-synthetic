"""Config and plan: pure data, so this belongs in the dependency-free CI job.

Nothing here starts a renderer. Worker and run behaviour needs the three
virtualenvs and is checked by hand, which keeps the `tests` job down to pytest
and pyyaml.
"""

from __future__ import annotations

import json

import pytest

from pipeline.config import Config, ConfigError, apply_overrides, resolve_workers
from pipeline.plan import (
    LAYOUT_STRIDE,
    backend_runs,
    build_plan,
    disjoint_seeds,
    shard_runs,
    split_by_layout,
)

LAYOUTS = ["eatery_ascii", "eatery_indexed", "market_barcode",
           "market_compact", "market_vat"]


def make_config(**changes) -> Config:
    raw = {
        "run": {"out": "data/x", "per_backend": 20, "seed": 2026, "workers": 4},
        "backends": ["synthdog", "html", "genalog"],
        "shard": {"size": 7},
    }
    for key, value in changes.items():
        if key in ("out", "per_backend", "seed", "workers", "clean", "force"):
            raw["run"][key] = value
        elif key == "size":
            raw["shard"]["size"] = value
        else:
            raw[key] = value
    return Config.from_dict(raw)


# ----------------------------------------------------------------- config


def test_unknown_top_level_key_is_rejected():
    with pytest.raises(ConfigError, match="unknown keys"):
        Config.from_dict({"run": {"out": "x", "per_backend": 1}, "backends": ["html"],
                          "nonsense": 1})


def test_unknown_run_key_is_rejected():
    # The motivating typo: `ouput` silently ignored, the run writes to the
    # default, and the config no longer describes what happened.
    with pytest.raises(ConfigError, match="unknown keys"):
        Config.from_dict({"run": {"ouput": "x", "per_backend": 1}, "backends": ["html"]})


def test_missing_out_is_rejected():
    with pytest.raises(ConfigError, match="run.out"):
        Config.from_dict({"run": {"per_backend": 1}, "backends": ["html"]})


def test_no_backends_is_rejected():
    with pytest.raises(ConfigError, match="backends"):
        Config.from_dict({"run": {"out": "x", "per_backend": 1}, "backends": []})


@pytest.mark.parametrize("value", [0, -3])
def test_nonsense_counts_are_rejected(value):
    with pytest.raises(ConfigError):
        make_config(per_backend=value)


def test_out_is_absolute():
    # A relative output path handed to the glyph backend lands inside
    # generators/synthdog/, because that backend runs from its own directory and
    # creates whatever it is given.
    assert make_config(out="data/rel").out.is_absolute()


def test_workers_auto_resolves_to_a_number():
    assert resolve_workers("auto") >= 1
    assert resolve_workers(4) == 4
    with pytest.raises(ConfigError):
        resolve_workers("many")
    with pytest.raises(ConfigError):
        resolve_workers(0)


def test_quality_is_carried_but_not_required():
    config = make_config(quality={"drift_tolerance": 0.2, "sample_for_ocr": 10})
    assert config.quality["drift_tolerance"] == 0.2
    assert make_config().quality == {}


def test_unknown_quality_key_is_rejected():
    with pytest.raises(ConfigError, match="unknown keys"):
        make_config(quality={"tolerance": 0.2})


# -------------------------------------------------------------- overrides


def _rules():
    from rulebase.spec import load_rules

    return load_rules()


def test_an_override_changes_the_weight():
    rules = apply_overrides(_rules(), {"augmentation.torn_edges.weight": 0.5})
    option = next(o for o in rules["augmentation"] if o.id == "torn_edges")
    assert option.weight == 0.5


def test_an_override_naming_nothing_is_rejected():
    # Same lesson as `_order.yaml` refusing a forgotten file: a config that
    # claims to re-weight something and silently does not is worse than one that
    # stops.
    with pytest.raises(ConfigError, match="does not "):
        apply_overrides(_rules(), {"visual.khong_ton_tai.weight": 2})


def test_an_override_naming_a_missing_attribute_is_rejected():
    with pytest.raises(ConfigError, match="attribute"):
        apply_overrides(_rules(), {"nosuch.value.weight": 2})


def test_an_override_of_the_wrong_shape_is_rejected():
    with pytest.raises(ConfigError, match="attribute.value_id.field"):
        apply_overrides(_rules(), {"augmentation.torn_edges": 1})


def test_an_override_of_an_unsupported_field_is_rejected():
    with pytest.raises(ConfigError, match="only weight"):
        apply_overrides(_rules(), {"augmentation.torn_edges.wieght": 1})


def test_no_overrides_leaves_the_rules_untouched():
    rules = _rules()
    assert apply_overrides(rules, {}) is rules


# ------------------------------------------------------------------- plan


def test_the_layout_split_matches_the_sequential_driver():
    assert split_by_layout(20, LAYOUTS) == [(name, 4) for name in LAYOUTS]
    assert [q for _, q in split_by_layout(3, LAYOUTS)] == [1, 1, 1, 0, 0]
    assert sum(q for _, q in split_by_layout(37, LAYOUTS)) == 37


def test_the_same_config_gives_the_same_plan_bytes():
    dumps = {json.dumps(build_plan(make_config(), LAYOUTS), sort_keys=True)
             for _ in range(5)}
    assert len(dumps) == 1


def test_a_shard_may_span_layouts():
    """The structural decision of W1, asserted rather than assumed.

    Cutting by layout also works, and it locks a later wave out of sharing one
    browser per shard. Nothing else in the code says a shard is a range, so this
    is where that is written down.
    """
    plan = build_plan(make_config(per_backend=20, size=7), LAYOUTS)
    spanning = [shard for shard in plan["shards"]
                if len({run["layout"] for run in shard["runs"]}) >= 2]
    assert spanning, "no shard covers more than one layout; the cut is by layout"


def test_shards_cover_every_image_exactly_once():
    plan = build_plan(make_config(per_backend=23, size=5), LAYOUTS)
    for backend in plan["backends"]:
        indices = [run["first_index"] + offset
                   for shard in plan["shards"] if shard["backend"] == backend
                   for run in shard["runs"]
                   for offset in range(run["count"])]
        assert sorted(indices) == list(range(23)), backend


def test_seed_ranges_are_disjoint_at_scale():
    # Constructed rather than sampled: 2000 per backend over five layouts is
    # 400 seeds per layout, well inside the 1000-seed block, and this is the
    # size the brief asks to be proved.
    config = make_config(per_backend=2000, size=250)
    plan = build_plan(config, LAYOUTS)
    seeds = [run["seed"] + offset
             for shard in plan["shards"]
             for run in shard["runs"]
             for offset in range(run["count"])]
    assert len(seeds) == len(set(seeds)), "two images would share a seed"


def test_an_overlapping_plan_is_refused_rather_than_emitted():
    """More images per layout than the stride allows must stop the run.

    The stride is inherited from the sequential driver and the count is not, so
    the two can be put into conflict by config alone -- and the symptom would be
    two identical images under different names, which no count or checksum of
    the run itself would reveal.
    """
    config = make_config(per_backend=LAYOUT_STRIDE * len(LAYOUTS) + 10)
    with pytest.raises(ValueError, match="duplicate"):
        build_plan(config, LAYOUTS)


def test_disjoint_seeds_reports_a_real_overlap():
    # Needs MORE than LAYOUT_STRIDE images in a single layout, not merely a big
    # total: 3000 over five layouts is 600 each and fits comfortably. Getting
    # this wrong once is why the check exists rather than the reasoning.
    per_backend = (LAYOUT_STRIDE + 2) * len(LAYOUTS)
    runs = {"html": backend_runs(0, per_backend, 0, LAYOUTS)}
    problems = disjoint_seeds(runs)
    assert problems and "overlap" in problems[0]


def test_the_plan_holds_no_absolute_paths():
    plan = build_plan(make_config(), LAYOUTS)
    text = json.dumps(plan)
    assert '"/' not in text, "an absolute path would tie the plan to one machine"


def test_shard_size_is_respected():
    shards = shard_runs(backend_runs(0, 20, 2026, LAYOUTS), "html", 7, 0)
    assert [shard.count for shard in shards] == [7, 7, 6]


def test_a_single_shard_holds_everything_when_it_is_large_enough():
    shards = shard_runs(backend_runs(0, 20, 2026, LAYOUTS), "html", 1000, 0)
    assert len(shards) == 1 and shards[0].count == 20


def test_shard_indices_are_unique_across_backends():
    plan = build_plan(make_config(per_backend=20, size=7), LAYOUTS)
    indices = [shard["index"] for shard in plan["shards"]]
    assert len(indices) == len(set(indices))
