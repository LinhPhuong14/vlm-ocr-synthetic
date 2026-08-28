"""Drift: the two hard criteria are opposed, so both are tested against each other.

One says a small `paired` run must stay silent -- sixty images are twenty draws
and `crumpled` at 5.3% is expected about once, so its absence means nothing. The
other says a run that really has drifted must speak. A threshold that passes only
one of them is not a threshold, it is a preference, so the same numbers are made
to do both here.

Vectors are built from `rulebase.make()` and real committed images rather than by
rendering, so this stays in the dependency-free `tests` CI job.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import rulebase
from pipeline import drift, invariants, record, synthesis

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_IMAGES = REPO_ROOT / "data" / "dataset60" / "html"


def make_records(seeds, layout=None, force=None):
    """The index and the provenance beside it, as a renderer writes both."""
    items, notes = [], []
    for index, seed in enumerate(seeds):
        pinned = dict(force or {})
        if layout:
            pinned["layout"] = layout
        recipe, receipt, grid = rulebase.make(seed=seed, force=pinned or None)
        name = f"html_{index:03d}.jpg"
        item = record.build(
            filename=name, width=1000, height=1400,
            parser="html", layout=grid.layout_id, seed=seed,
            boxes=[{"kind": c.role, "text": c.text,
                    "quad": [[0, 0], [1, 0], [1, 1], [0, 1]]}
                   for c in grid.cells if c.text.strip() and c.role != "sep"],
            extracted=receipt.ground_truth())
        items.append(item)
        notes.append((name, {"job_id": item["job_id"], "layout": grid.layout_id,
                             "recipe": recipe.to_dict(),
                             "text_sequence": receipt.text_sequence()}))
    return items, notes


def build_shard(directory: Path, made, *, index=0, backend="html",
                notes=None, sources=None) -> dict:
    """A shard directory complete enough for `shard_vector` to read."""
    records, provenance = made
    directory.mkdir(parents=True, exist_ok=True)
    images = sorted(SOURCE_IMAGES.glob("*.jpg"))
    for position, item in enumerate(records):
        if sources:
            provenance[position][1].setdefault("extra", {})["content_source"] = \
                sources[position % len(sources)]
        shutil.copy2(images[position % len(images)],
                     directory / record.file_name(item))
    record.write(records, directory)
    synthesis.write(synthesis.beside(directory), backend, provenance)
    (directory / invariants.INVARIANTS_NAME).write_text(
        json.dumps({"images": len(records), "notes": notes or {},
                    "unprinted": {}, "occurrences": {}, "label_values": {}}),
        encoding="utf-8")
    return {"index": index, "backend": backend, "count": len(records),
            "runs": [{"layout": entry["layout"], "seed": entry["recipe"]["seed"],
                      "count": 1, "first_index": position}
                     for position, (_name, entry) in enumerate(provenance)]}


def plan_for(shard, **extra):
    return {"pairing": "paired", "backends": ["html"], "clean": False,
            "force": [], "shards": [shard], **extra}


# --------------------------------------------------------------- the vector


def test_the_vector_is_a_function_of_the_shard_alone(tmp_path):
    """Law 5. Two reads of one shard must agree byte for byte."""
    shard = build_shard(tmp_path / "s", make_records(range(12)))
    first = json.dumps(drift.shard_vector(tmp_path / "s", shard), sort_keys=True)
    second = json.dumps(drift.shard_vector(tmp_path / "s", shard), sort_keys=True)
    assert first == second


def test_the_vector_carries_no_clock_and_no_path(tmp_path):
    shard = build_shard(tmp_path / "s", make_records(range(8)))
    text = json.dumps(drift.shard_vector(tmp_path / "s", shard), ensure_ascii=False)
    assert str(tmp_path) not in text
    for forbidden in ("seconds", "elapsed", "started", "pid", "timestamp"):
        assert forbidden not in text.lower(), forbidden


def test_the_vector_measures_what_it_says_it_does(tmp_path):
    records = make_records(range(10))
    shard = build_shard(tmp_path / "s", records, notes={"total_label_collapsed": 2})
    vector = drift.shard_vector(tmp_path / "s", shard)
    assert vector["images"] == 10 and vector["draws"] == 10
    assert vector["collapsed_totals"] == 2
    assert vector["collapsed_total_share"] == 0.2
    assert vector["image_pixels_mean"] > 0
    assert vector["text_length_mean"] > 0
    assert set(vector["attributes"]) == set(invariants.attribute_names())
    assert vector["content_sources"] == {"corpus": 10}


def test_a_shard_with_no_metadata_says_so_rather_than_reporting_zero(tmp_path):
    """Law 3: nothing to read is not the same as nothing to report."""
    (tmp_path / "empty").mkdir()
    vector = drift.shard_vector(tmp_path / "empty", {"index": 3, "backend": "html"})
    assert vector["unchecked"] and vector["unchecked"][0].startswith(drift.UNCHECKED)


def test_diacritics_are_detected_and_their_absence_is_too():
    assert drift.has_diacritics("PHIẾU TÍNH TIỀN")
    assert drift.has_diacritics("Số 201A đường Láng Hạ")
    assert not drift.has_diacritics("PHIEU TINH TIEN 286,000")


# ---------------------------------------------------------- the expectation


def test_the_expectation_is_conditioned_on_the_pins_the_run_used(tmp_path):
    """The trap this whole comparison would otherwise fall into.

    The driver pins the layout so all five are drawn equally often. Sampling the
    rules without that pin gives the layout mix the *weights* describe, which is
    nothing like it, and every run would report drift on the layout axis for
    ever. The expectation has to carry the run's own pins.
    """
    records = make_records([3, 4, 5], layout="market_vat")
    shard = build_shard(tmp_path / "s", records)
    shares, problems = drift.expected_shares(shard, plan_for(shard), draws=60)
    assert problems == []
    assert shares["layout"] == {"market_vat": pytest.approx(1.0)}


def test_a_clean_run_expects_every_chain_attribute_pinned(tmp_path):
    """Not just `augmentation`: `toner`, `drum` and `rollers` carry chains too.

    An expectation that left them free would report drift on a clean run for
    the three attributes the run had in fact pinned to nothing.
    """
    shard = build_shard(tmp_path / "s", make_records(range(4)))
    shares, _problems = drift.expected_shares(
        shard, plan_for(shard, clean=True), draws=40)
    for attribute, value in invariants.CLEAN_FORCES.items():
        if attribute in shares:
            assert shares[attribute] == {value: pytest.approx(1.0)}


def test_an_explicit_force_reaches_the_expectation(tmp_path):
    shard = build_shard(tmp_path / "s", make_records(range(4)))
    shares, _problems = drift.expected_shares(
        shard, plan_for(shard, force=["augmentation=heavy"]), draws=40)
    assert shares["augmentation"] == {"heavy": pytest.approx(1.0)}


def test_total_variation_reads_as_the_share_that_would_have_to_move():
    assert drift.total_variation({"a": 5, "b": 5}, {"a": 0.5, "b": 0.5}) == 0
    assert drift.total_variation({"a": 10}, {"b": 1.0}) == pytest.approx(1.0)
    # A value drawn 20% of the time disappearing moves the distance by 0.2 --
    # which is exactly why class B cannot be left to this measure.
    assert drift.total_variation(
        {"a": 8}, {"a": 0.8, "b": 0.2}) == pytest.approx(0.2)


# ----------------------------------------------- the two opposed criteria


def vector_for(counts, *, draws=None, backend="html"):
    """A vector with a chosen augmentation mix and nothing else of interest."""
    return {"backend": backend, "images": draws or sum(counts.values()),
            "draws": draws or sum(counts.values()),
            "attributes": {"augmentation": counts},
            "content_sources": {"corpus": draws or sum(counts.values())},
            "unchecked": []}


# The shipped augmentation weights, near enough: what matters is that `crumpled`
# is rare and `real_paper` is common.
SHARES = {"augmentation": {
    "real_paper": 0.30, "medium": 0.20, "photocopy": 0.15, "stains": 0.12,
    "ghost_text": 0.10, "torn_edges": 0.08, "crumpled": 0.05,
}}


def test_a_small_paired_run_missing_its_rare_values_stays_silent():
    """Criterion 4. Twenty draws expect one `crumpled`; none is not news.

    A warning here would fire on `make dataset` every single time, and a
    dashboard that cries wolf on correct output is switched off within a week.
    """
    observed = {"real_paper": 6, "medium": 4, "photocopy": 3, "stains": 3,
                "ghost_text": 2, "torn_edges": 2}
    warnings, stops, notes = drift.compare(vector_for(observed), SHARES)
    assert warnings == [] and stops == []
    # And it says why nothing fired, rather than looking clean by accident.
    assert notes and "too few" in notes[0]


def test_a_large_run_missing_the_same_value_says_so():
    """Criterion 3. At 200 draws `crumpled` expects ten, and zero is news."""
    observed = {"real_paper": 62, "medium": 41, "photocopy": 30, "stains": 25,
                "ghost_text": 21, "torn_edges": 21}
    warnings, _stops, _notes = drift.compare(vector_for(observed, draws=200), SHARES)
    missing = [w for w in warnings if "crumpled" in w]
    assert missing, warnings
    assert "expected about 10" in missing[0] and "warns from 5" in missing[0]


def test_the_never_drawn_threshold_is_printed_with_the_warning():
    """Criterion 8 in miniature: a reader must not have to guess the rule."""
    warnings, _stops, _notes = drift.compare(
        vector_for({"real_paper": 200}, draws=200), SHARES)
    assert all("warns from" in w for w in warnings if "never appeared" in w)


def test_a_mix_that_really_moved_is_caught():
    """Criterion 5, at the level the measure works on.

    Half the draws from a run whose weights favour `stains`, half from one that
    does not: a mix no single set of weights produces.
    """
    spliced = {"real_paper": 30, "medium": 20, "photocopy": 15, "stains": 100,
               "ghost_text": 10, "torn_edges": 8, "crumpled": 5}
    warnings, _stops, _notes = drift.compare(vector_for(spliced), SHARES)
    moved = [w for w in warnings if "mix is" in w]
    assert moved, warnings
    assert "stains" in moved[0]


def test_the_threshold_grows_when_the_sample_is_small_and_shrinks_when_it_is_not():
    """The single number that lets criteria 4 and 5 both pass.

    A flat tolerance cannot: at 40 draws over eleven values a *correct*
    generator lands 0.13-0.19 from its own weights, which is already past 0.15,
    so a flat 0.15 warns on runs that have not drifted -- measured, on the first
    real run this was tried on, which warned at 0.17 with nothing wrong.
    """
    small = drift.sampling_noise(SHARES["augmentation"], 20)
    large = drift.sampling_noise(SHARES["augmentation"], 2000)
    assert small > drift.DEFAULT_TOLERANCE, small
    assert large < 0.03, large
    # It falls as 1/sqrt(n): a hundred times the draws, a tenth the scatter.
    assert small / large == pytest.approx(10.0, rel=0.05)


def test_a_mix_no_weighting_produces_is_caught_at_the_smallest_judged_size():
    """Drift big enough to see through the noise is seen through the noise.

    Forty draws of two values, when seven were expected, is not a plausible
    sample of anything -- and unlike the case above, it does speak.
    """
    lumpy = {"real_paper": 20, "medium": 20}
    warnings, _stops, _notes = drift.compare(vector_for(lumpy), SHARES)
    assert [w for w in warnings if "mix is" in w], "a two-value mix passed as ordinary"


def test_a_plausible_sample_and_an_implausible_one_are_told_apart():
    """The pair that matters, side by side and at the same size."""
    plausible = {"real_paper": 12, "medium": 8, "photocopy": 6, "stains": 5,
                 "ghost_text": 4, "torn_edges": 3, "crumpled": 2}
    implausible = {"stains": 36, "real_paper": 4}
    quiet, _s, _n = drift.compare(vector_for(plausible), SHARES)
    loud, _s, _n = drift.compare(vector_for(implausible), SHARES)
    assert not [w for w in quiet if "mix is" in w], quiet
    assert [w for w in loud if "mix is" in w]


def test_a_shard_below_the_judged_size_says_so_and_judges_nothing():
    """MIN_DRAWS is measured, not chosen -- see the table beside it.

    Twelve shards of ten draws produced two warnings on a run where nothing was
    wrong, which is what set this floor.
    """
    warnings, _stops, notes = drift.compare(
        vector_for({"real_paper": 5, "medium": 5}), SHARES)
    assert not [w for w in warnings if "mix is" in w]
    assert notes and "too few to say anything" in notes[0]
    assert drift.MIN_DRAWS == 30


def test_the_warning_says_what_the_threshold_was_made_of():
    """Criterion 8. A number a reader cannot decompose gets widened."""
    warnings, _stops, _notes = drift.compare(
        vector_for({"stains": 180, "real_paper": 20}, draws=200), SHARES)
    moved = [w for w in warnings if "mix is" in w]
    assert moved
    assert "tolerance plus" in moved[0] and "scatters by" in moved[0]


# ------------------------------------------------------- content source


def test_a_run_falling_back_for_its_content_stops_rather_than_warns():
    """Criterion 7. A fallback is not a flavour of page, it is a fault."""
    vector = vector_for({"real_paper": 100}, draws=100)
    vector["content_sources"] = {"corpus": 90, "fallback": 10}
    warnings, stops, _notes = drift.compare(vector, SHARES)
    assert stops and "fell back" in stops[0]
    assert not [w for w in warnings if "fell back" in w]


def test_one_stray_fallback_is_under_the_limit():
    vector = vector_for({"real_paper": 100}, draws=100)
    vector["content_sources"] = {"corpus": 98, "fallback": 2}
    _warnings, stops, _notes = drift.compare(vector, SHARES)
    assert stops == []


def test_an_unknown_content_source_stops_the_shard():
    vector = vector_for({"real_paper": 100}, draws=100)
    vector["content_sources"] = {"corpus": 90, "scraped": 10}
    _warnings, stops, _notes = drift.compare(vector, SHARES)
    assert stops and "unknown content source" in stops[0]


# -------------------------------------------------- draws, not images


def test_paired_backends_count_once_and_independent_ones_add_up():
    """Criterion 1.2 of the brief, and the reason class B is not deaf.

    Sixty `paired` images are twenty draws. Counting them as sixty would triple
    every expectation and make `crumpled` look missing on every small run.
    """
    vectors = [vector_for({"real_paper": 20}, backend=name)
               for name in ("synthdog", "html", "genalog")]
    assert drift.run_draws(vectors, "paired") == 20
    assert drift.run_draws(vectors, "independent") == 60


def test_the_run_summary_counts_one_backend_when_paired():
    """Criterion 6: cross-backend content is an invariant, not a drift axis.

    Since W1b the backends draw the same receipts by construction, so adding
    their distributions together would multiply one sample by three and call it
    evidence.
    """
    vectors = [vector_for({"real_paper": 20}, backend=name)
               for name in ("synthdog", "html", "genalog")]
    summary = drift.summarise(vectors, "paired")
    assert summary["draws"] == 20
    assert summary["attributes"]["augmentation"] == {"real_paper": 20}
    assert summary["counted_backend"] == "genalog"   # sorted, so it is stable
    assert summary["images"] == 60                   # files on disk, still 60

    independent = drift.summarise(vectors, "independent")
    assert independent["draws"] == 60
    assert independent["attributes"]["augmentation"] == {"real_paper": 60}


def test_drift_never_compares_two_backends_with_each_other():
    """Criterion 6, read off the code rather than off the prose.

    `compare` takes one vector, so there is no cross-backend axis to be had; and
    the invariant that the backends agree is guarded once, in `invariants.py`. A
    second copy here would be a softer instrument answering a question that
    already has a hard answer -- and, under `paired`, one that returns zero for
    ever whatever the state of the world.
    """
    import ast
    import inspect

    assert list(inspect.signature(drift.compare).parameters)[:2] == ["vector", "shares"]

    tree = ast.parse(inspect.getsource(drift))
    named = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    named |= {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "paired_content" not in named, "drift.py re-checks a settled invariant"


# ------------------------------------------------------------- tolerance


def test_the_tolerance_comes_from_the_config_and_falls_back_safely():
    assert drift.tolerance_of({"drift_tolerance": 0.2}) == 0.2
    assert drift.tolerance_of({}) == drift.DEFAULT_TOLERANCE
    assert drift.tolerance_of(None) == drift.DEFAULT_TOLERANCE
    assert drift.tolerance_of({"drift_tolerance": "nonsense"}) == drift.DEFAULT_TOLERANCE
    assert drift.tolerance_of({"drift_tolerance": -1}) == drift.DEFAULT_TOLERANCE


def test_the_shipped_tolerance_is_the_one_the_documentation_explains():
    """`pipeline.yaml` and the module must not drift apart from each other."""
    import yaml

    config = yaml.safe_load((REPO_ROOT / "pipeline.yaml").read_text(encoding="utf-8"))
    assert config["quality"]["drift_tolerance"] == drift.DEFAULT_TOLERANCE


def test_an_overridden_run_is_compared_against_its_own_weights(tmp_path):
    """The same mistake as ignoring the pins, one level up.

    A run with `overrides:` renders against a materialised copy of the rules. If
    the expectation came from the shipped weights, every overridden run would
    report drift -- and the fix people reach for is widening the tolerance.
    """
    from pipeline.config import apply_overrides
    from rulebase.spec import load_rules

    shard = build_shard(tmp_path / "s", make_records(range(4)))
    plan = plan_for(shard)

    shipped, _ = drift.expected_shares(shard, plan, draws=200)
    silenced = apply_overrides(load_rules(), {"augmentation.ghost_text.weight": 0})
    overridden, _ = drift.expected_shares(shard, plan, rules=silenced, draws=200)

    assert shipped["augmentation"].get("ghost_text", 0) > 0
    assert "ghost_text" not in overridden["augmentation"], (
        "the expectation ignored the run's own overrides")


# The augmentation mix an actual, undrifted 40-image run produced, and the
# shares the plan expected of it. Kept as data rather than described in prose
# because it is the case that decided the design: total variation 0.167, past a
# flat 0.15 tolerance, with nothing whatsoever wrong.
REAL_RUN_COUNTS = {"crumpled": 3, "ghost_text": 4, "light": 4, "medium": 5,
                   "photocopy": 4, "pristine": 2, "real_paper": 8, "stains": 6,
                   "torn_edges": 4}
REAL_RUN_SHARES = {"augmentation": {
    "crumpled": 0.051, "ghost_text": 0.0965, "heavy": 0.023, "light": 0.156,
    "medium": 0.1475, "photocopy": 0.110, "pristine": 0.076, "punched": 0.029,
    "real_paper": 0.144, "stains": 0.0905, "torn_edges": 0.0765}}


def test_the_run_that_motivated_the_noise_term_stays_silent():
    """The decisive case, kept as the numbers it actually produced.

    A flat 0.15 ceiling warns here -- the distance is 0.167 -- on a run where
    nothing at all had gone wrong. With the scatter a 40-draw sample carries
    (0.19) it is comfortably inside. This is the test that fails if anyone
    removes the sampling term and leaves the tolerance looking tidy.
    """
    distance = drift.total_variation(REAL_RUN_COUNTS, REAL_RUN_SHARES["augmentation"])
    noise = drift.sampling_noise(REAL_RUN_SHARES["augmentation"], 40)
    assert distance > drift.DEFAULT_TOLERANCE, distance
    assert distance < drift.DEFAULT_TOLERANCE + noise

    warnings, _stops, _notes = drift.compare(
        vector_for(REAL_RUN_COUNTS, draws=40), REAL_RUN_SHARES)
    assert not [w for w in warnings if "mix is" in w], warnings


def test_the_same_sized_run_with_real_drift_still_speaks():
    """And the noise term must not have bought silence at the price of deafness.

    Half of the run above spliced with half of one forced to `stains`, which is
    the construction the brief asks for. Measured on real shards: 0.47.
    """
    spliced = dict(REAL_RUN_COUNTS)
    spliced["stains"] = 22
    spliced["real_paper"] = 6
    spliced["medium"] = 4
    spliced["photocopy"] = 1
    spliced["light"] = 1
    spliced["torn_edges"] = 2
    spliced["ghost_text"] = 2
    spliced["crumpled"] = 1
    spliced["pristine"] = 1
    warnings, _stops, _notes = drift.compare(
        vector_for(spliced, draws=40), REAL_RUN_SHARES)
    moved = [w for w in warnings if "mix is" in w]
    assert moved, warnings
    assert "stains" in moved[0]


def test_every_float_in_a_vector_has_a_pinned_precision(tmp_path):
    """Law 5 across machines, not just across two calls in one process.

    Two runs of one plan have to agree byte for byte, and an unrounded mean
    carries whatever the last bit of a platform's floating point did. Rounding
    is what makes the comparison portable, so it is asserted rather than
    assumed -- a same-process test would pass without it.
    """
    shard = build_shard(tmp_path / "s", make_records(range(7)))
    vector = drift.shard_vector(tmp_path / "s", shard)

    def walk(value):
        if isinstance(value, float):
            yield value
        elif isinstance(value, dict):
            for item in value.values():
                yield from walk(item)
        elif isinstance(value, list):
            for item in value:
                yield from walk(item)

    floats = list(walk(vector))
    assert floats, "no float in the vector; this test would pass vacuously"
    for number in floats:
        assert number == round(number, 6), f"{number!r} carries unpinned precision"


# ---------------------------------------------- an agent pins every attribute


def test_the_expectation_carries_a_runs_own_pins():
    """`forced_for` merged the job's `--force` and the run's layout and stopped.

    An agent-planned run pins all eight attributes on the run itself, so the
    expectation was the mix the *weights* predict while the shard held the mix
    the *plan* asked for -- and every such shard warned by 0.29 for doing what
    it was told. The images were fine; only the judgement of them was wrong.
    """
    from pipeline.drift import forced_for

    plan = {"force": [], "clean": False}
    shard = {"runs": [{"layout": "market_vat", "count": 3,
                       "force": {"document": "supermarket_vat",
                                 "ornament": "shelf_barcode"}}]}
    pinned = forced_for(shard, plan)[0]
    assert pinned == {"document": "supermarket_vat", "ornament": "shelf_barcode",
                      "layout": "market_vat", "_count": 3}


def test_a_runs_pin_beats_the_jobs_pin():
    """The narrower statement wins, as `worklist.Job.pins` already documents."""
    from pipeline.drift import forced_for

    plan = {"force": ["augmentation=pristine"], "clean": False}
    shard = {"runs": [{"layout": "market_vat", "count": 1,
                       "force": {"augmentation": "photocopy"}}]}
    assert forced_for(shard, plan)[0]["augmentation"] == "photocopy"


def test_a_run_with_no_pins_expects_what_it_always_expected():
    from pipeline.drift import forced_for

    plan = {"force": ["augmentation=pristine"], "clean": False}
    shard = {"runs": [{"layout": "market_vat", "count": 2}]}
    assert forced_for(shard, plan)[0] == {
        "augmentation": "pristine", "layout": "market_vat", "_count": 2}
