"""Config and plan: pure data, so this belongs in the dependency-free CI job.

Nothing here starts a renderer. Worker and run behaviour needs the three
virtualenvs and is checked by hand, which keeps the `tests` job down to pytest
and pyyaml.
"""

from __future__ import annotations

import json

import pytest

from pipeline.config import (
    Config,
    ConfigError,
    apply_overrides,
    resolve_per_backend,
    resolve_workers,
)
from pipeline.plan import (
    LAYOUT_STRIDE,
    Run,
    adjacent_repeats,
    backend_runs,
    build_plan,
    deal,
    disjoint_seeds,
    shard_runs,
    split_by_layout,
    uncovered,
)

LAYOUTS = ["eatery_ascii", "eatery_indexed", "market_barcode",
           "market_compact", "market_vat"]


def make_config(**changes) -> Config:
    raw = {
        "run": {"out": "data/x", "per_backend": 20, "seed": 2026, "workers": 4},
        "backends": ["html", "second", "third"],
        "shard": {"size": 7},
    }
    for key, value in changes.items():
        if key in ("out", "per_backend", "seed", "workers", "clean", "force",
                   "pairing", "layouts"):
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
    rules = apply_overrides(_rules(), {"augmentation.heavy.weight": 0.5})
    option = next(o for o in rules["augmentation"] if o.id == "heavy")
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
        apply_overrides(_rules(), {"augmentation.heavy": 1})


def test_an_override_of_an_unsupported_field_is_rejected():
    with pytest.raises(ConfigError, match="only weight"):
        apply_overrides(_rules(), {"augmentation.heavy.wieght": 1})


def test_no_overrides_leaves_the_rules_untouched():
    rules = _rules()
    assert apply_overrides(rules, {}) is rules


# ------------------------------------------------------------------- plan


def test_the_layout_split_matches_the_sequential_driver():
    assert split_by_layout(20, LAYOUTS) == [(name, 4) for name in LAYOUTS]
    assert [q for _, q in split_by_layout(3, LAYOUTS)] == [1, 1, 1, 0, 0]
    assert sum(q for _, q in split_by_layout(37, LAYOUTS)) == 37


def test_a_run_too_small_for_its_layouts_names_the_ones_it_would_drop():
    """The split hands the remainder to the FRONT of the list, so a count below
    the layout count does not spread thin -- it drops the tail entirely."""
    assert uncovered(3, LAYOUTS) == LAYOUTS[3:]
    assert uncovered(5, LAYOUTS) == []
    assert uncovered(20, LAYOUTS) == []


def test_a_plan_that_would_miss_a_layout_is_refused():
    """A dataset silently missing the tail of its own layout list is worse than
    a run that will not start: `dataset.json` still names every layout, because
    that field records what the run was pointed at, not what came out."""
    with pytest.raises(ValueError, match="cannot cover"):
        build_plan(make_config(per_backend=3), LAYOUTS)
    # ... and the error says which ones and what to do about it.
    try:
        build_plan(make_config(per_backend=3), LAYOUTS)
    except ValueError as error:
        assert "market_compact" in str(error)
        assert "at least 5" in str(error)


def test_a_plan_records_where_its_layout_list_came_from():
    """The list alone cannot say. An `all` run and a `named` run over the same
    five layouts produce identical `layouts:` and are not comparable: the day
    someone adds a layout, only one of them changes."""
    assert build_plan(make_config(), LAYOUTS)["layout_source"] == "all"
    assert build_plan(make_config(layouts=LAYOUTS), LAYOUTS)["layout_source"] == "named"
    forced = make_config(force=["layout=market_vat"])
    assert build_plan(forced, LAYOUTS)["layout_source"] == "forced"


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


# ------------------------------------------------------- the deal (W4)


def layouts_in_order(plan, backend="html"):
    """Every image of one backend, in output order, as its layout name."""
    pages = [(run["first_index"] + offset, run["layout"])
             for shard in plan["shards"] if shard["backend"] == backend
             for run in shard["runs"]
             for offset in range(run["count"])]
    return [layout for _index, layout in sorted(pages)]


def test_no_two_adjacent_images_carry_the_same_layout():
    """The property the deal exists for, over a run that is not a round number.

    23 images over 5 layouts is quotas [5,5,5,4,4]: four full rounds and a
    short one, so the last round is where a naive deal would leave the front
    of the list beside itself.
    """
    plan = build_plan(make_config(per_backend=23, size=5), LAYOUTS)
    for backend in plan["backends"]:
        order = layouts_in_order(plan, backend)
        assert len(order) == 23
        assert adjacent_repeats(order) == [], f"{backend}: {order}"


def test_the_deal_holds_across_shard_boundaries():
    """A shard is a cut in the sequence, not a reason for two pages to pair up.

    The images either side of a boundary sit next to each other in the
    assembled dataset, however they were rendered, so the check is on the
    assembled order and the shard size is deliberately not a multiple of the
    layout count.
    """
    plan = build_plan(make_config(per_backend=20, size=3), LAYOUTS)
    assert len([s for s in plan["shards"] if s["backend"] == "html"]) > 1
    assert adjacent_repeats(layouts_in_order(plan)) == []


def test_dealing_does_not_move_a_single_page():
    """Order changed; content did not. The k-th page of a layout keeps its seed.

    This is what makes the deal a re-ordering rather than a new dataset: every
    (layout, seed) pair the block plan produced is still here, exactly once.
    """
    runs = backend_runs(0, 23, 2026, LAYOUTS)
    dealt = sorted((run.layout, run.seed) for run in runs)

    blocked = []
    offset = 0
    for layout, quota in split_by_layout(23, LAYOUTS):
        if not quota:
            continue
        blocked += [(layout, 2026 + offset * LAYOUT_STRIDE + k) for k in range(quota)]
        offset += 1
    assert dealt == sorted(blocked)


def test_every_layout_appears_before_any_layout_appears_twice():
    """Round-robin, not merely shuffled: the first pass covers everything.

    A run cut short after N images should hold N distinct layouts, which is
    what makes a partial or failed run still worth looking at.
    """
    order = [layout for layout, _which in deal(23, LAYOUTS)]
    assert order[:len(LAYOUTS)] == LAYOUTS
    assert len(set(order[:len(LAYOUTS)])) == len(LAYOUTS)


def test_a_run_pinned_to_one_layout_is_still_allowed():
    """One layout has no other layout to alternate with. Not a failure."""
    plan = build_plan(make_config(per_backend=4, force=["layout=market_vat"]), LAYOUTS)
    assert layouts_in_order(plan) == ["market_vat"] * 4


def test_per_backend_auto_draws_one_of_every_layout():
    plan = build_plan(make_config(per_backend="auto"), LAYOUTS)

    assert plan["per_backend"] == len(LAYOUTS)
    assert sorted(layouts_in_order(plan)) == sorted(LAYOUTS)


def test_per_backend_auto_records_the_number_it_resolved_to():
    """`plan.json` must say what was built, not the word that asked for it."""
    assert resolve_per_backend("auto") == 0
    assert resolve_per_backend(12) == 12
    with pytest.raises(ConfigError, match="a number or 'auto'"):
        resolve_per_backend("every")


def test_shards_cover_every_image_exactly_once():
    plan = build_plan(make_config(per_backend=23, size=5), LAYOUTS)
    for backend in plan["backends"]:
        indices = [run["first_index"] + offset
                   for shard in plan["shards"] if shard["backend"] == backend
                   for run in shard["runs"]
                   for offset in range(run["count"])]
        assert sorted(indices) == list(range(23)), backend


def seeds_of(plan, backend=None):
    return [run["seed"] + offset
            for shard in plan["shards"]
            if backend is None or shard["backend"] == backend
            for run in shard["runs"]
            for offset in range(run["count"])]


def test_seed_ranges_are_disjoint_at_scale():
    """Within one backend, no two images may share a seed.

    Constructed rather than sampled: 2000 per backend over five layouts is 400
    seeds per layout, well inside the 1000-seed block, and this is the size the
    brief asks to be proved. Across backends the answer depends on the pairing
    mode, which the two tests below cover.
    """
    plan = build_plan(make_config(per_backend=2000, size=250), LAYOUTS)
    for backend in plan["backends"]:
        seeds = seeds_of(plan, backend)
        assert len(seeds) == len(set(seeds)), f"{backend}: two images share a seed"


# --------------------------------------------------------------- pairing (W1b)


def test_paired_is_the_default_and_gives_every_backend_the_same_seeds():
    """The claim `README.md` opens with, asserted where it is decided.

    Before W1b the seed carried `backend_index * 100_000`, so the three
    renderers shared not one seed and the published side-by-side numbers were
    comparing three different corpora.
    """
    plan = build_plan(make_config(per_backend=20, size=7), LAYOUTS)
    assert plan["pairing"] == "paired"
    sets = [set(seeds_of(plan, backend)) for backend in plan["backends"]]
    assert len(sets[0]) == 20
    for other in sets[1:]:
        assert other == sets[0], "paired backends do not share their seeds"


def test_independent_keeps_the_blocks_apart():
    plan = build_plan(make_config(per_backend=20, size=7, pairing="independent"),
                      LAYOUTS)
    assert plan["pairing"] == "independent"
    sets = [set(seeds_of(plan, backend)) for backend in plan["backends"]]
    assert set.intersection(*sets) == set(), "independent backends share a seed"
    assert len(set.union(*sets)) == 60


def test_an_unknown_pairing_is_rejected():
    with pytest.raises(ConfigError, match="run.pairing"):
        make_config(pairing="sometimes")


def test_the_guard_does_not_cry_wolf_in_either_mode():
    """`disjoint_seeds` must stay useful under both modes.

    Under `paired` the backends cover the same seeds deliberately, so a guard
    that compared them would fire on every correct run and be switched off.
    """
    for pairing in ("paired", "independent"):
        runs = {backend: backend_runs(index, 2000, 2026, LAYOUTS, pairing)
                for index, backend in enumerate(["html", "second", "third"])}
        assert disjoint_seeds(runs, pairing) == [], pairing


def test_an_overlap_inside_one_backend_is_still_caught_when_paired():
    per_backend = (LAYOUT_STRIDE + 2) * len(LAYOUTS)
    runs = {backend: backend_runs(index, per_backend, 0, LAYOUTS, "paired")
            for index, backend in enumerate(["html", "second"])}
    problems = disjoint_seeds(runs, "paired")
    assert problems and "overlap" in problems[0]


def test_the_paired_invariant_sees_a_plan_whose_backends_diverge():
    """Law 2: the condition is built, not waited for.

    A plan that says `paired` while its backends sit on different seeds is what
    the whole of W1b is about, so it is constructed here rather than trusted not
    to happen.
    """
    from pipeline.invariants import paired_content

    good = build_plan(make_config(per_backend=10, size=10), LAYOUTS)
    assert paired_content(good) == []

    broken = json.loads(json.dumps(good))
    for shard in broken["shards"]:
        if shard["backend"] != broken["backends"][0]:
            for run in shard["runs"]:
                run["seed"] += 100_000
    problems = paired_content(broken)
    assert problems and "do not draw the same pages" in problems[0], problems


def test_the_paired_invariant_says_nothing_about_an_independent_plan():
    from pipeline.invariants import paired_content

    plan = build_plan(make_config(per_backend=10, size=10, pairing="independent"),
                      LAYOUTS)
    assert paired_content(plan) == []


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


def test_the_paired_invariant_catches_a_plan_naming_a_layout_the_rules_lost():
    """The half the structural check cannot do.

    Comparing three identical (seed, layout) pairs through a deterministic
    sampler proves nothing on its own. What this half is for is a plan that is
    perfectly well-formed and still cannot be rendered -- a layout renamed in
    `rulebase/rules/layout.yaml` since the plan was written, which otherwise
    surfaces as a dead worker an hour in.
    """
    from pipeline.invariants import paired_content

    plan = build_plan(make_config(per_backend=10, size=10), LAYOUTS)
    for shard in plan["shards"]:
        for run in shard["runs"]:
            run["layout"] = "a_layout_nobody_ships"
    problems = paired_content(plan)
    assert problems, "a plan pinned to a layout that does not exist passed"
    assert "will not produce" in problems[0], problems


def test_the_paired_invariant_catches_a_sampler_that_moved_the_seed(monkeypatch):
    """A pin that walks to another seed makes the plan unreproducible.

    This is the W1b defect seen from the scheduling side: the plan says seed
    2026 and the sampler hands back 2031, so `recipe.seed` no longer indexes
    the plan and nothing downstream can line the two up.
    """
    import rulebase
    from pipeline.invariants import paired_content

    real = rulebase.make

    def walked(seed=None, force=None, **kwargs):
        return real(seed=(seed or 0) + 5, force=force, **kwargs)

    monkeypatch.setattr(rulebase, "make", walked)
    plan = build_plan(make_config(per_backend=10, size=10), LAYOUTS)
    problems = paired_content(plan)
    assert problems and "the sampler returned" in problems[0], problems


# ------------------------------------------------------- a pinned layout


def test_forcing_a_layout_narrows_the_plan_instead_of_riding_beside_it():
    """`--force layout=X` decides which layouts the plan renders.

    Left alone, the plan still spread the run across every layout and handed
    each renderer `--layout Y --force layout=X`. The renderer drew X -- force
    wins -- and the worker then stamped the plan's Y onto the item. The image
    was one layout and the label said another, which the invariants met as a
    failure on a correct run, because they read the layout to know what that
    layout is allowed to leave unprinted.
    """
    plan = build_plan(make_config(per_backend=6, force=["layout=market_vat"]), LAYOUTS)
    assert plan["layouts"] == ["market_vat"]
    drawn = {run["layout"] for shard in plan["shards"] for run in shard["runs"]}
    assert drawn == {"market_vat"}
    assert sum(run["count"] for shard in plan["shards"] for run in shard["runs"]) == 18


def test_forcing_something_other_than_a_layout_leaves_the_plan_alone():
    plan = build_plan(make_config(force=["augmentation=pristine"]), LAYOUTS)
    assert plan["layouts"] == LAYOUTS


def test_forcing_a_layout_nobody_ships_is_refused_before_anything_is_drawn():
    with pytest.raises(ValueError, match="no such layout"):
        build_plan(make_config(force=["layout=not_a_layout"]), LAYOUTS)


def test_a_pinned_plan_still_gives_every_backend_the_same_receipts():
    """The point of `paired`, and the pin must not quietly break it."""
    from pipeline.invariants import paired_content

    plan = build_plan(make_config(per_backend=4, size=4, force=["layout=eatery_ascii"]),
                      LAYOUTS)
    assert paired_content(plan) == []


# --------------------------------------------- a split run keeps what it carries


def test_splitting_a_run_across_shards_keeps_its_pins():
    """`shard_runs` rebuilt each piece field by field and dropped `force`.

    Invisible while `force` was always empty; fatal once an agent puts all eight
    attributes there, because the pages still render and still validate -- they
    are simply not the pages the plan describes.
    """
    pins = {"document": "supermarket", "variant": "f_x", "augmentation": "pristine"}
    shards = shard_runs([Run(layout="market_vat", seed=10, count=5, first_index=0,
                             force=pins)], "html", size=2, start_index=0)
    pieces = [run for shard in shards for run in shard.runs]
    assert sum(run.count for run in pieces) == 5
    assert [run.seed for run in pieces] == [10, 12, 14]
    assert all(run.force == pins for run in pieces)


def test_a_run_with_no_pins_is_unchanged_by_the_split():
    shards = shard_runs([Run(layout="market_vat", seed=1, count=3, first_index=0)],
                        "html", size=2, start_index=0)
    assert all(run.force == {} for shard in shards for run in shard.runs)
