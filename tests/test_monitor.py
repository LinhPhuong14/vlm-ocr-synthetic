"""Monitor: mostly one question -- does it understand the resume contract?

A shard with no `DONE` has not lost anything. The worker deletes a fragment and
renders the shard again, on purpose, so that a half-written shard can never pass
for a complete one; between two looks the image count can therefore fall. W1 saw
7 then 5. A monitor that calls that "2 images lost" is wrong about the system and
will be switched off within a week, and a monitor nobody runs is worth nothing.

Run directories here are built by hand rather than rendered, so this stays in the
dependency-free `tests` CI job.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import monitor  # noqa: E402


def build_run(root: Path, shards, *, pairing="paired", finished=False,
              seconds=None) -> Path:
    """A run directory in whatever state the test needs.

    `shards` is a list of (backend, planned, images, done).
    """
    root.mkdir(parents=True, exist_ok=True)
    plan = {
        "pairing": pairing,
        "backends": sorted({backend for backend, *_ in shards}),
        "per_backend": sum(planned for backend, planned, *_ in shards
                           if backend == shards[0][0]),
        "shards": [],
    }
    for index, (backend, planned, images, done) in enumerate(shards):
        plan["shards"].append({
            "index": index, "backend": backend, "count": planned,
            "runs": [{"layout": "eatery_ascii", "seed": 1000 + index,
                      "count": planned, "first_index": 0}],
        })
        if images is None:                      # never started
            continue
        directory = root / monitor.SHARDS_DIR / f"shard-{index:04d}"
        directory.mkdir(parents=True, exist_ok=True)
        for position in range(images):
            (directory / f"{backend}_{position:03d}.jpg").write_bytes(b"x")
        (directory / "drift.json").write_text(json.dumps({
            "backend": backend, "images": images, "draws": images,
            "attributes": {"augmentation": {"real_paper": images}},
            "content_sources": {"corpus": images},
            "collapsed_totals": 0, "unchecked": [],
        }), encoding="utf-8")
        if done:
            (directory / monitor.DONE).write_text("{}", encoding="utf-8")

    (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
    if finished:
        (root / "manifest.json").write_text("{}", encoding="utf-8")
    if seconds is not None:
        (root / "timings.json").write_text(
            json.dumps({"seconds_total": seconds}), encoding="utf-8")
    return root


# ------------------------------------------------------- the resume contract


def test_a_shard_that_restarted_is_reported_as_a_redo_not_a_loss(tmp_path):
    """Law 6, and the whole reason this tool needs to know the contract.

    The count fell from 12 to 0 because a worker threw a fragment away and
    started again. Saying "12 images lost" would be false, and saying it on
    every resume is how a dashboard gets ignored.
    """
    before = monitor.scan(build_run(tmp_path / "a", [("html", 20, 12, False)]))
    after = monitor.scan(build_run(tmp_path / "b", [("html", 20, 0, False)]))
    after["out"] = before["out"]

    text = monitor.render(after, before)
    assert "restarted" in text
    assert "were a fragment and were deleted, not lost" in text
    for word in ("lost 12", "missing", "LOST"):
        assert word not in text, word


def test_a_shard_that_lost_its_done_is_reported_as_being_redone(tmp_path):
    before = monitor.scan(build_run(tmp_path / "a", [("html", 20, 20, True)]))
    after = monitor.scan(build_run(tmp_path / "b", [("html", 20, 3, False)]))
    after["out"] = before["out"]
    assert "being redone" in monitor.render(after, before)


def test_an_unfinished_shard_is_progress_not_a_result(tmp_path):
    """A count without a DONE behind it is never presented as an outcome."""
    state = monitor.scan(build_run(tmp_path / "r", [("html", 20, 7, False)]))
    assert state["shards"][0]["state"] == "working"
    text = monitor.render(state)
    assert "7/20" in text and "done" not in text.split("\n")[2]


def test_a_first_look_at_a_fragment_does_not_claim_a_restart(tmp_path):
    """With no previous look there is nothing to compare, and it says nothing."""
    state = monitor.scan(build_run(tmp_path / "r", [("html", 20, 7, False)]))
    assert "restarted" not in monitor.render(state)


def test_the_three_states_are_told_apart(tmp_path):
    state = monitor.scan(build_run(tmp_path / "r", [
        ("html", 10, 10, True), ("html", 10, 4, False), ("html", 10, None, False)]))
    assert [s["state"] for s in state["shards"]] == ["done", "working", "waiting"]


# ---------------------------------------------------------------- reading


def test_it_reads_a_run_that_is_still_going(tmp_path):
    """Criterion 1: no manifest.json, because that is written at the end."""
    root = build_run(tmp_path / "r", [("html", 20, 20, True), ("html", 20, 5, False)])
    assert not (root / "manifest.json").exists()
    state = monitor.scan(root)
    assert not state["finished"]
    text = monitor.render(state)
    # 20 finished plus the 5 already written by the shard in flight.
    assert "[running]" in text and "25 of 40" in text


def test_it_reads_a_run_that_has_finished(tmp_path):
    root = build_run(tmp_path / "r", [("html", 20, 20, True)],
                     finished=True, seconds=42.5)
    text = monitor.render(monitor.scan(root))
    assert "[finished]" in text
    # The duration comes from the file that is allowed to hold one, not from a
    # file mtime -- which would report the age of the run, not its length.
    assert "42s" in text and "from timings.json" in text


def test_a_directory_that_is_not_a_run_says_so(tmp_path):
    (tmp_path / "nothing").mkdir()
    with pytest.raises(SystemExit, match="plan.json"):
        monitor.scan(tmp_path / "nothing")


def test_looking_at_a_run_changes_nothing_on_disk(tmp_path):
    """Criterion 6, and what makes it safe to point at a live job."""
    root = build_run(tmp_path / "r", [("html", 20, 20, True), ("html", 20, 5, False)])
    before = {p: p.stat().st_mtime_ns for p in sorted(root.rglob("*"))}
    monitor.render(monitor.scan(root))
    after = {p: p.stat().st_mtime_ns for p in sorted(root.rglob("*"))}
    assert before == after, "the monitor wrote something"


# ------------------------------------------------------------- the numbers


def test_paired_runs_count_each_receipt_once(tmp_path):
    """The same rule as `drift.run_draws`: 60 paired images are 20 receipts."""
    root = build_run(tmp_path / "r", [
        ("synthdog", 20, 20, True), ("html", 20, 20, True), ("genalog", 20, 20, True)])
    assert sum(monitor.observed_mix(root).values()) == 20

    independent = build_run(tmp_path / "i", [
        ("synthdog", 20, 20, True), ("html", 20, 20, True), ("genalog", 20, 20, True)],
        pairing="independent")
    assert sum(monitor.observed_mix(independent).values()) == 60


def test_the_live_mix_follows_whichever_backend_is_furthest_ahead(tmp_path):
    """Otherwise a mid-run view is held back by the slowest renderer.

    Still one backend -- they drew the same receipts -- but the one with the
    most to say.
    """
    root = build_run(tmp_path / "r", [
        ("synthdog", 10, 10, True), ("synthdog", 10, 10, True),
        ("html", 10, 10, True), ("html", 10, 2, False)])
    assert sum(monitor.observed_mix(root).values()) == 20


def test_an_unfinished_shard_is_left_out_of_the_mix(tmp_path):
    """A shard still being written is a partial sample of nothing in particular."""
    root = build_run(tmp_path / "r", [("html", 10, 10, True), ("html", 10, 9, False)])
    assert sum(monitor.observed_mix(root).values()) == 10


def test_the_rate_counts_every_image_written_not_only_finished_shards(tmp_path):
    """Measured: finished-shards-only said 1m39s for a run with 45s left.

    Nine shards and four workers means most of the work in progress is invisible
    to a rate built on `DONE` files alone.
    """
    root = build_run(tmp_path / "r", [
        ("html", 20, 20, True), ("html", 20, 15, False), ("html", 20, None, False)])
    state = monitor.scan(root)
    state["started"] = 0.0
    text = monitor.render(state, now=35.0)
    # 35 images in 35 seconds, so 1.00/s and 25 left -- not 20 in 35 seconds.
    assert "1.00 images/s" in text, text
    assert "35 of 60" in text


def test_elapsed_falls_back_to_the_clock_while_the_run_is_going(tmp_path):
    root = build_run(tmp_path / "r", [("html", 20, 5, False)])
    state = monitor.scan(root)
    state["started"] = 100.0
    assert "elapsed  60s" in monitor.render(state, now=160.0)


# ---------------------------------------------------------------- static


def test_static_mode_draws_what_make_distribution_draws():
    """Criterion 3, pinned so the two cannot become two different answers."""
    from rules_report import sample_distribution

    assert monitor.STATIC_DRAWS == 2000 and monitor.STATIC_SEED == 0
    counters, _families, failures = sample_distribution(
        monitor.STATIC_DRAWS, monitor.STATIC_SEED)
    assert failures == 0
    assert sum(counters["augmentation"].values()) == monitor.STATIC_DRAWS
