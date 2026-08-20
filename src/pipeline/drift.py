"""Has this run stopped producing what it said it would?

A shard is checked against itself by `src/pipeline/invariants.py`: every image, every
label, absolutely. This asks a question no single image can answer -- whether the
*mix* is still the mix the rules describe. A generator that quietly stops drawing
one paper texture, or starts drawing twice as many supermarket receipts as it
should, produces sixty thousand individually valid images and a dataset that no
longer matches its own description.

    from pipeline import drift
    vector = drift.shard_vector(shard_directory, shard)     # in the worker
    problems, stops = drift.compare(vector, expectation)    # in the run

Three decisions worth arguing about
-----------------------------------

**Drift is measured across shards within one backend, never between backends.**
Since W1b the backends are `paired`: all three draw the same receipts, and
`src/pipeline/invariants.paired_content` refuses to start a run where they would not.
Comparing their content distributions would therefore return zero every time, for
ever, whatever the state of the world -- and a number that cannot change is a
number nobody reads. Cross-backend agreement is an invariant and is guarded as
one; it is not re-checked here with a softer instrument.

**The expectation is conditioned on the plan's own pins.** The driver forces the
layout so every layout is drawn equally often, and `--clean` forces the
augmentation. Sampling the rule-base without those pins gives the layout mix the
*weights* describe, which is not the mix the *run* asked for, and every run would
report drift on the layout axis. So the expectation is drawn with the same
`force` the shard was rendered with, and mixed in the proportions the shard's own
runs specify. What is left over after that is real drift.

**Expected counts are counted in draws, not in images.** Under `paired`, sixty
images are twenty receipts drawn three ways. Scaling an expectation by the image
count would make every small run declare that `heavy` (2.45% of the space) and
`crumpled` (5.3%) had gone missing, when twenty draws are simply too few to
expect either. A shard belongs to one backend, so within a shard the two numbers
agree; the distinction bites when the run is rolled up, and `run_draws` is where
it is handled.

Two kinds of warning, kept apart
--------------------------------

**A -- the mix moved.** Total variation distance between the observed counts and
the expected shares, per attribute. TVD is chosen because it reads as a sentence:
*0.15 means at most 15% of the draws would have to be moved from one value to
another to turn the observed mix into the expected one.* A tolerance that cannot
be said out loud gets widened whenever it is inconvenient.

It is compared against `drift_tolerance` **plus** what a sample that size
scatters by on its own -- see `sampling_noise`. Without that term the sentence is
still true and the check is still useless: forty draws over eleven values land
about 0.19 from their own weights by chance, so a flat 0.15 warns on runs that
have not drifted. Measured, on the first real run this was tried on, which
warned at 0.17 with nothing wrong. With the term, one tolerance serves a forty-
draw shard and a four-thousand-draw one, and it means *drift beyond sampling*.

**B -- a value stopped appearing at all.** A distance cannot catch this. Drop a
value drawn 5% of the time and TVD moves by 0.05, well inside any usable
tolerance, while the dataset has silently lost a whole kind of page. So absence
is its own first-class warning, and it fires only when the expectation was big
enough for absence to mean something -- `MIN_EXPECTED` draws -- with the
threshold printed alongside so nobody has to guess why it did or did not speak.

Everything in a vector is a deterministic function of the shard: no clock, no
PID, no path. Timings stay in `timings.json`, which nothing compares.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from pipeline import invariants, record
from pipeline.invariants import UNCHECKED

# What `quality.drift_tolerance` means, in one sentence: the share of draws that
# would have to move from one value to another to turn what was drawn into what
# was expected. 0.15 is loose enough to survive the sampling noise of a few
# hundred draws and tight enough that a doubled weight shows up.
DEFAULT_TOLERANCE = 0.15

# A "never drawn" warning needs an expectation worth being surprised by. Below
# this, absence is ordinary: at 5.3% -- `crumpled` -- twenty draws expect one,
# and one-in-three such shards would legitimately contain none.
MIN_EXPECTED = 5

# Below this many draws the mix is not judged at all. `sampling_noise` uses the
# *mean* deviation of a correct sample, and a mean is not a ceiling: half of all
# correct shards land above it, so at small n a meaningful fraction clear
# tolerance + mean as well. Measured, 4000 simulated correct shards per cell,
# as the share that would have warned:
#
#     draws     augmentation (11 values)   visual (5 values)
#        10              5.0%                    6.2%
#        20              1.2%                    1.7%
#        30              0.5%                    0.7%
#        40              0.2%                    0.2%
#       100              0.0%                    0.0%
#
# Ten was the first guess and a real run showed why it was wrong: twelve shards
# of ten draws produced two warnings with nothing wrong. Thirty is where the
# per-attribute rate drops under a percent. Shards of 100-250, which is what
# `pipeline.yaml` recommends, are far past it.
MIN_DRAWS = 30

# Where the text came from. W2 always writes `corpus`; W6 introduces the others
# and will declare its own expected mix. `fallback` means the intended source
# failed and something else filled in, which is why it has a limit rather than a
# share: it is not a flavour of content, it is a fault that produced content.
SOURCES = ("corpus", "llm", "fallback")
PRIMARY_SOURCE = "corpus"
FALLBACK_LIMIT = 0.05

# Images per shard that get decoded for ink coverage. Every other axis comes
# from the metadata; this one needs pixels, and at roughly 15 ms an image a full
# decode of a 250-image shard would cost more than the check is worth. The first
# N by name, so it is the same N on every machine.
INK_SAMPLE = 20

# Draws per layout used to build an expectation. Large enough that the
# expectation's own sampling error is well under the tolerance it is compared
# against: at 400 draws a 20% share has a standard error near 2%.
EXPECT_DRAWS = 400

# Fixed, and deliberately far from any seed a run would use. The expectation
# must not accidentally sample the same recipes the run rendered, or it would be
# comparing a thing with itself.
EXPECT_SEED = 20_260_101

VECTOR = "drift.json"


# --------------------------------------------------------------- ingredients


def has_diacritics(text: str) -> bool:
    """Does this page carry Vietnamese tone marks at all?

    The corpus is Vietnamese, but `content` may fold a page to ASCII -- an old
    thermal printer that cannot render tone marks. The share of folded pages is
    a real property of the dataset and a real thing to lose by accident: a
    model trained on a set that quietly went all-ASCII cannot read the language
    it was built for.
    """
    return any("̀" <= character <= "ͯ"
               or "Ạ" <= character <= "ỹ"
               or character in "ăâđêôơưĂÂĐÊÔƠƯáàảãạÁÀẢÃẠéèẻẽẹÉÈẺẼẸíìỉĩịÍÌỈĨỊ"
                              "óòỏõọÓÒỎÕỌúùủũụÚÙỦŨỤýỳỷỹỵÝỲỶỸỴ"
               for character in text)


def ink_coverage(path: Path) -> float | None:
    """Share of pixels clearly darker than the paper. None if it cannot be read.

    Measured against the image's own median rather than a fixed grey level: the
    glyph backend photographs its receipt on a dark table, so an absolute
    threshold would count the background as ink and report a page four times as
    full as it is.
    """
    try:
        import cv2
    except ImportError:
        return None
    image = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return None
    paper = float(image.reshape(-1).mean()) if image.size else 0.0
    # `median` would be the natural choice and is what tools/check_boxes.py uses
    # inside a box; over a whole photograph the dark surround drags it down, so
    # the mean, which the surround also moves but less, is the steadier of two
    # imperfect references. Either way the number is only ever compared with
    # itself across shards.
    darker = int((image < paper - 25).sum())
    return round(darker / image.size, 6) if image.size else None


def _round(value: float) -> float:
    """Floats in a vector are compared byte for byte, so pin the precision."""
    return round(float(value), 6)


# ------------------------------------------------------------- the vector


def shard_vector(directory: Path, shard: dict, *,
                 ink_sample: int = INK_SAMPLE) -> dict[str, Any]:
    """What one shard drew, as numbers. A deterministic function of the shard.

    Reads `metadata.jsonl` and `invariants.json`, and decodes at most
    `ink_sample` images. Nothing here is allowed to vary between two runs of the
    same plan -- that is what makes the vector comparable, and it is the same
    rule that keeps durations out of `manifest.json`.
    """
    directory = Path(directory)
    unchecked: list[str] = []

    metadata = directory / "metadata.jsonl"
    if not metadata.exists():
        return {
            "backend": shard.get("backend", "?"),
            "images": 0,
            "unchecked": [f"{UNCHECKED} shard {shard.get('index')} has no metadata, "
                          f"so no quality vector was computed"],
        }
    records = record.read(metadata)

    attributes: dict[str, Counter] = {}
    layouts: Counter = Counter()
    sources: Counter = Counter()
    lengths: list[int] = []
    diacritics = 0
    pixels: list[int] = []

    for item in records:
        for name, value in ((item.get("recipe") or {}).get("attributes") or {}).items():
            attributes.setdefault(name, Counter())[str(value.get("id"))] += 1
        layouts[str(item.get("layout", "?"))] += 1
        # Absent means `corpus`: W2 has no other source, and defaulting keeps
        # the axis readable now rather than empty until W6 fills it in.
        sources[str(item.get("content_source", PRIMARY_SOURCE))] += 1
        text = str(item.get("text_sequence", ""))
        lengths.append(len(text))
        diacritics += 1 if has_diacritics(text) else 0
        size = invariants.jpeg_size(directory / str(item.get("file_name", "")))
        if size:
            pixels.append(size[0] * size[1])

    if len(pixels) < len(records):
        unchecked.append(
            f"{UNCHECKED} {len(records) - len(pixels)} of {len(records)} images in "
            f"shard {shard.get('index')} would not give up their size")

    coverages = [c for c in (ink_coverage(directory / str(item.get("file_name", "")))
                             for item in records[:max(ink_sample, 0)]) if c is not None]
    sampled = min(max(ink_sample, 0), len(records))
    if sampled and not coverages:
        unchecked.append(
            f"{UNCHECKED} no ink coverage for shard {shard.get('index')}: the "
            f"imaging library is not importable here")

    measured = json.loads((directory / invariants.INVARIANTS_NAME).read_text(
        encoding="utf-8")) if (directory / invariants.INVARIANTS_NAME).exists() else {}
    if not measured:
        unchecked.append(
            f"{UNCHECKED} shard {shard.get('index')} has no invariants.json, so its "
            f"label defects are not in the vector")

    collapsed = int((measured.get("notes") or {}).get("total_label_collapsed", 0))

    return {
        "backend": shard.get("backend", "?"),
        "images": len(records),
        # Within a shard these are the same number -- a shard is one backend, so
        # one image is one draw. They differ once shards are rolled up under
        # `paired`, and naming both here is what stops that being forgotten.
        "draws": len(records),
        "layouts": dict(sorted(layouts.items())),
        "attributes": {name: dict(sorted(counter.items()))
                       for name, counter in sorted(attributes.items())},
        "text_length_mean": _round(sum(lengths) / len(lengths)) if lengths else 0.0,
        "diacritic_share": _round(diacritics / len(records)) if records else 0.0,
        "image_pixels_mean": _round(sum(pixels) / len(pixels)) if pixels else 0.0,
        "ink_coverage_mean": _round(sum(coverages) / len(coverages)) if coverages else None,
        "ink_coverage_images": len(coverages),
        "content_sources": dict(sorted(sources.items())),
        # First class, above the distribution axes, because it is not a shift in
        # the mix -- it is a label that describes an amount the page prints and
        # the label does not carry. See the W4 debt in the wave notes.
        "collapsed_totals": collapsed,
        "collapsed_total_share": _round(collapsed / len(records)) if records else 0.0,
        "unprinted": measured.get("unprinted") or {},
        "occurrences": measured.get("occurrences") or {},
        "label_values": measured.get("label_values") or {},
        "unchecked": sorted(set(unchecked)),
    }


def write_vector(vector: dict, directory: Path) -> Path:
    path = Path(directory) / VECTOR
    path.write_text(json.dumps(vector, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                    encoding="utf-8")
    return path


# -------------------------------------------------------- the expectation


def forced_for(shard: dict, plan: dict) -> list[dict[str, str]]:
    """The `force` each of a shard's runs was rendered with, and its weight.

    A run pins the layout; `--clean` pins the augmentation; `--force` pins
    whatever the caller asked for. The expectation has to carry the same pins or
    it is an expectation for a different job.
    """
    pinned: dict[str, str] = {}
    for item in plan.get("force") or []:
        name, _, value = str(item).partition("=")
        if value:
            pinned[name] = value
    if plan.get("clean") and "augmentation" not in pinned:
        pinned["augmentation"] = invariants.CLEAN_AUGMENTATION
    return [{**pinned, "layout": run["layout"], "_count": run["count"]}
            for run in shard.get("runs", [])]


def expected_shares(shard: dict, plan: dict, *, rules=None,
                    draws: int = EXPECT_DRAWS) -> tuple[dict[str, dict[str, float]], list[str]]:
    """What this shard's mix should look like, as shares per attribute.

    Drawn from the rules rather than read off another shard: shard 1 is a sample
    too, and comparing samples with samples turns ordinary sampling noise into
    an alarm. Each of the shard's runs contributes its own pinned draw, weighted
    by how many images that run produces, so a shard covering three layouts is
    compared against the mix those three layouts actually make.

    `rules` must be the rules the run **rendered with**. A run with `overrides:`
    renders against a materialised copy, and expecting the shipped weights
    instead would report drift on every such run -- which is the same mistake as
    ignoring the plan's pins, one level up.
    """
    import sys

    root = str(Path(__file__).resolve().parents[2] / "tools")
    if root not in sys.path:
        sys.path.insert(0, root)
    try:
        from rules_report import sample_distribution
    except ImportError as error:
        return {}, [f"{UNCHECKED} no expected distribution ({error})"]

    if rules is None:
        # Once, here. `sample_recipe(rules=None)` re-reads every YAML file on
        # every single draw, so leaving it to default costs one full parse of
        # the rule-base per draw -- thousands per shard, and it showed up as a
        # test suite that went from 9 seconds to 57.
        from rulebase.spec import load_rules

        rules = load_rules()

    problems: list[str] = []
    totals: dict[str, Counter] = {}
    weight_total = 0
    for index, pinned in enumerate(forced_for(shard, plan)):
        weight = int(pinned.pop("_count", 0))
        if weight <= 0:
            continue
        weight_total += weight
        # A different block of sampling seeds per run, so two runs pinned to the
        # same layout do not contribute the same draws twice.
        counters, _families, failures = sample_distribution(
            draws, EXPECT_SEED + index * 1_000_000, rules=rules, force=pinned)
        if failures:
            problems.append(
                f"{failures} of {draws} expectation draws failed for {pinned}; the "
                f"rules may forbid the combination the plan asks for")
        for name, counter in counters.items():
            bucket = totals.setdefault(name, Counter())
            drawn = sum(counter.values())
            if not drawn:
                continue
            for value, count in counter.items():
                # Scaled to this run's weight, so the mix is the plan's mix.
                bucket[value] += count * weight / drawn

    if not weight_total:
        return {}, problems
    shares: dict[str, dict[str, float]] = {}
    for name, bucket in totals.items():
        total = sum(bucket.values())
        if total:
            shares[name] = {value: amount / total
                            for value, amount in sorted(bucket.items())}
    return shares, problems


def sampling_noise(shares: dict[str, float], draws: int) -> float:
    """How far a *correct* generator's mix lands from its own weights, typically.

    This is the number that decides whether the tolerance means anything. Drawing
    n times from the expected distribution does not reproduce it: each value's
    observed share wobbles, and total variation adds every wobble up, so an
    attribute with eleven values over forty draws sits about 0.13 away from its
    own weights by chance alone. Comparing that against a flat 0.15 tolerance
    reports drift on runs that have not drifted -- measured, on the first real
    run this was tried on, which warned at 0.17 with nothing wrong.

    For each value, the observed share is Binomial(n, p)/n, whose mean absolute
    deviation is about sqrt(2p(1-p)/(pi n)); total variation is half their sum.
    Closed form rather than simulated, so the threshold stays a deterministic
    function of the plan and costs nothing.

    The effect is that `drift_tolerance` means *drift beyond what a sample this
    size scatters by anyway*, which is the only reading under which one number
    can serve a 40-draw shard and a 4000-draw one.
    """
    if draws < 1:
        return 1.0
    return 0.5 * sum(math.sqrt(2 * p * (1 - p) / (math.pi * draws))
                     for p in shares.values() if 0 < p < 1)


def total_variation(observed: dict[str, int], shares: dict[str, float]) -> float:
    """Half the L1 distance between two distributions over the same values.

    Reads as: the share of draws that would have to move from one value to
    another to turn the first into the second. Values missing from either side
    count as zero there, which is the point -- a value that stopped appearing
    contributes its whole share.
    """
    drawn = sum(observed.values())
    if not drawn:
        return 0.0
    seen = {value: count / drawn for value, count in observed.items()}
    return 0.5 * sum(abs(seen.get(value, 0.0) - shares.get(value, 0.0))
                     for value in set(seen) | set(shares))


# --------------------------------------------------------------- the verdict


def compare(vector: dict, shares: dict[str, dict[str, float]], *,
            tolerance: float = DEFAULT_TOLERANCE,
            min_expected: int = MIN_EXPECTED,
            min_draws: int = MIN_DRAWS) -> tuple[list[str], list[str], list[str]]:
    """(warnings, stops, notes).

    A warning goes in the manifest and makes the run return non-zero. A stop
    fails the shard. A **note** is neither: it records something about how the
    comparison was made, so that "nothing to report" and "this could not be
    judged" are distinguishable in the manifest without a correct small run
    exiting as a failure.

    The two warning classes are kept apart on purpose. A distance says the mix
    moved and by how much; absence says a kind of page is gone, which no
    distance is sensitive enough to say. Rolling them together would mean
    choosing a tolerance that is either deaf to the first or hysterical about
    the second.
    """
    warnings: list[str] = []
    stops: list[str] = []
    notes: list[str] = []
    draws = int(vector.get("draws", 0))
    backend = vector.get("backend", "?")

    # --- the axis that stops a run rather than warning about it. Content that
    # came from a fallback is not a different flavour of page: it is the record
    # of the intended source having failed, and a run that keeps going produces
    # tens of thousands of pages nobody asked for.
    sources = vector.get("content_sources") or {}
    counted = sum(sources.values())
    if counted:
        fallback = sources.get("fallback", 0) / counted
        if fallback > FALLBACK_LIMIT:
            stops.append(
                f"{backend}: {sources.get('fallback', 0)} of {counted} pages fell back "
                f"to a substitute content source ({fallback:.0%}, limit "
                f"{FALLBACK_LIMIT:.0%}); the run is not producing what it declares")
        unknown = sorted(set(sources) - set(SOURCES))
        if unknown:
            stops.append(
                f"{backend}: unknown content source {unknown}; have {list(SOURCES)}")

    warnings += list(vector.get("unchecked") or [])
    if not shares or not draws:
        return warnings, stops, notes

    underpowered: list[tuple[str, float]] = []
    judge_mix = draws >= min_draws
    if not judge_mix:
        notes.append(
            f"{backend}: {draws} draws is too few to say anything about the mix; "
            f"only the never-drawn check ran")

    for name in sorted(shares):
        observed = {str(k): int(v)
                    for k, v in (vector.get("attributes") or {}).get(name, {}).items()}
        if not observed:
            continue
        expected = shares[name]

        # --- class A: the mix moved, by more than a sample this size wobbles
        distance = total_variation(observed, expected)
        noise = sampling_noise(expected, draws)
        if judge_mix and distance > tolerance + noise:
            moved = sorted(
                ((value, observed.get(value, 0) / draws - expected.get(value, 0.0))
                 for value in set(observed) | set(expected)),
                key=lambda pair: -abs(pair[1]))[:3]
            detail = ", ".join(f"{value} {gap:+.0%}" for value, gap in moved)
            warnings.append(
                f"{backend}: the {name} mix is {distance:.2f} from what the plan "
                f"expects, over the {tolerance:.2f} tolerance plus the {noise:.2f} "
                f"a {draws}-draw sample scatters by (largest gaps: {detail})")
        elif judge_mix and noise > tolerance:
            # Collected rather than emitted one by one: five attributes across
            # three shards is fifteen lines saying the same thing about a
            # sixty-image run, and a note nobody finishes reading is a note
            # nobody reads.
            underpowered.append((name, noise))

        # --- class B: a value stopped appearing
        for value, share in sorted(expected.items()):
            count = share * draws
            if observed.get(value, 0) == 0 and count >= min_expected:
                warnings.append(
                    f"{backend}: {name}={value} never appeared, and {draws} draws at "
                    f"{share:.1%} expected about {count:.0f} (warns from "
                    f"{min_expected}); a whole kind of page is missing")

    if underpowered:
        # The honest answer to "why did nothing fire". At this size the check
        # cannot see drift as small as the tolerance describes, and saying so is
        # the difference between a clean run and an unmeasured one.
        worst = max(noise for _name, noise in underpowered)
        names = ", ".join(sorted(name for name, _noise in underpowered))
        notes.append(
            f"{backend}: {draws} draws are too few to resolve the {tolerance:.2f} "
            f"tolerance on {names}; scatter alone reaches {worst:.2f}, so only "
            f"drift past {tolerance + worst:.2f} would have been seen")
    return warnings, stops, notes


# ----------------------------------------------------------------- the run


def run_draws(vectors: list[dict], pairing: str) -> int:
    """How many distinct receipts a set of shard vectors represents.

    Under `paired` every backend drew the same ones, so the run's sample is one
    backend's worth however many backends ran. Counting images instead is the
    mistake that would make every small paired run declare its rare values
    missing -- 60 images look like 60 draws and are 20.
    """
    if not vectors:
        return 0
    by_backend: dict[str, int] = {}
    for vector in vectors:
        by_backend[vector.get("backend", "?")] = (
            by_backend.get(vector.get("backend", "?"), 0) + int(vector.get("draws", 0)))
    if pairing == "paired":
        return max(by_backend.values())
    return sum(by_backend.values())


def summarise(vectors: list[dict], pairing: str) -> dict[str, Any]:
    """The run's quality vector: counts only, comparable between two runs."""
    attributes: dict[str, Counter] = {}
    sources: Counter = Counter()
    images = collapsed = 0
    lengths: list[float] = []
    coverages: list[float] = []
    unchecked: set[str] = set()

    # Under `paired` the backends are replicas of one another, so one of them is
    # the sample and the rest would only multiply it. Sorted, so which one is
    # picked does not depend on the order the shards happened to finish in.
    backends = sorted({v.get("backend", "?") for v in vectors})
    counted = [backends[0]] if pairing == "paired" and backends else backends

    for vector in vectors:
        images += int(vector.get("images", 0))
        collapsed += int(vector.get("collapsed_totals", 0))
        unchecked.update(vector.get("unchecked") or [])
        if vector.get("ink_coverage_mean") is not None:
            coverages.append(float(vector["ink_coverage_mean"]))
        if vector.get("backend") not in counted:
            continue
        for name, counter in (vector.get("attributes") or {}).items():
            bucket = attributes.setdefault(name, Counter())
            for value, count in counter.items():
                bucket[value] += int(count)
        for value, count in (vector.get("content_sources") or {}).items():
            sources[value] += int(count)
        if vector.get("images"):
            lengths.append(float(vector.get("text_length_mean", 0.0))
                           * int(vector["images"]))

    drawn = run_draws(vectors, pairing)
    return {
        "pairing": pairing,
        "images": images,
        "draws": drawn,
        "counted_backend": counted[0] if counted and pairing == "paired" else None,
        "attributes": {name: dict(sorted(counter.items()))
                       for name, counter in sorted(attributes.items())},
        "content_sources": dict(sorted(sources.items())),
        "collapsed_totals": collapsed,
        "collapsed_total_share": _round(collapsed / images) if images else 0.0,
        "text_length_mean": _round(sum(lengths) / drawn) if drawn and lengths else 0.0,
        "ink_coverage_mean": _round(sum(coverages) / len(coverages)) if coverages else None,
        "unchecked": sorted(unchecked),
    }


def tolerance_of(config_quality: dict | None) -> float:
    """`quality.drift_tolerance` from pipeline.yaml, or the default."""
    value = (config_quality or {}).get("drift_tolerance", DEFAULT_TOLERANCE)
    try:
        tolerance = float(value)
    except (TypeError, ValueError):
        return DEFAULT_TOLERANCE
    return tolerance if math.isfinite(tolerance) and tolerance > 0 else DEFAULT_TOLERANCE


__all__ = [
    "DEFAULT_TOLERANCE",
    "EXPECT_DRAWS",
    "FALLBACK_LIMIT",
    "MIN_DRAWS",
    "MIN_EXPECTED",
    "SOURCES",
    "VECTOR",
    "compare",
    "expected_shares",
    "forced_for",
    "has_diacritics",
    "ink_coverage",
    "run_draws",
    "shard_vector",
    "summarise",
    "tolerance_of",
    "total_variation",
    "write_vector",
]
