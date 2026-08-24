"""A job list, and the one thing it is not allowed to change.

Handing a renderer several layouts in one process is a change to where process
boundaries fall and to nothing else. So the tests here are of two kinds: that
the list parses strictly (a job with a typo in it must stop, not render on a
default), and that a page drawn as part of a list is byte-for-byte the page it
was when drawn alone.

The second kind is the one that matters, and it is also the one that caught a
real defect: the glyph renderer's pages were never a function of their seed.
They were a function of the seed *and the position of the page in its process*,
because `config_vi_receipt.yaml` uses imgaug augmenters and imgaug does one-time
initialisation on its first augmentation in a process. Nothing noticed for four
waves, because the worker started a fresh process per layout and every page was
page one. See `_warm_imgaug` in `generators/synthdog/template_receipt.py`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

from paths import VENVS, venv_python  # noqa: E402

import worklist as W  # noqa: E402
from pipeline import record  # noqa: E402

# What the renderer comparison draws: two layouts, one of them twice, so the
# test covers both "first page of a job" and "later page of a job".
PLAN = [{"layout": "market_vat", "seed": 5000, "count": 2},
        {"layout": "eatery_ascii", "seed": 6000, "count": 1}]

SCRIPTS = {
    "synthdog": (REPO_ROOT / "generators" / "synthdog" / "render.py",
                 REPO_ROOT / "generators" / "synthdog"),
    "html": (REPO_ROOT / "generators" / "html" / "render.py", REPO_ROOT),
    "genalog": (REPO_ROOT / "generators" / "genalog" / "render.py", REPO_ROOT),
}


# ------------------------------------------------------------- the list itself


def test_a_single_layout_invocation_still_works_unchanged():
    """The old way in has to keep working: scripts and tests use it."""

    class Args:
        jobs = None
        layout = "market_vat"
        seed = 7
        count = 3

    assert W.load(Args()) == [W.Job(layout="market_vat", seed=7, count=3)]


def test_no_layout_means_the_sampler_picks():
    class Args:
        jobs = None
        layout = None
        seed = 0
        count = 1

    assert W.load(Args())[0].layout is None


def test_a_job_list_wins_over_the_single_flags(tmp_path):
    """Documented to win rather than silently losing. A flag that quietly
    yields to another flag is the harder bug of the two."""
    path = W.write(tmp_path / "jobs.json", [W.Job("eatery_ascii", 11, 2)])

    class Args:
        jobs = path
        layout = "market_vat"
        seed = 999
        count = 99

    assert W.load(Args()) == [W.Job("eatery_ascii", 11, 2)]


def test_pages_number_across_the_list_and_seed_within_a_job():
    """Two different counters, and confusing them is how a batch collides its
    own filenames or re-draws one seed twice."""
    jobs = [W.Job("a", 100, 2), W.Job("b", 200, 3)]
    assert list(W.pages(jobs)) == [
        (0, jobs[0], 100), (1, jobs[0], 101),
        (2, jobs[1], 200), (3, jobs[1], 201), (4, jobs[1], 202),
    ]
    assert W.total(jobs) == 5


def test_a_typo_in_a_job_stops_rather_than_rendering_on_a_default():
    with pytest.raises(W.JobError, match="unknown keys"):
        W.parse([{"layouts": "market_vat", "seed": 1, "count": 1}])


def test_a_job_missing_its_seed_stops():
    with pytest.raises(W.JobError, match="seed"):
        W.parse([{"layout": "market_vat", "count": 1}])


def test_an_empty_list_is_refused_rather_than_drawing_nothing():
    with pytest.raises(W.JobError, match="draws nothing"):
        W.parse([])


def test_a_count_of_zero_is_refused():
    with pytest.raises(W.JobError, match="at least 1"):
        W.parse([{"layout": "a", "seed": 1, "count": 0}])


def test_force_is_a_mapping_and_a_list_is_refused():
    with pytest.raises(W.JobError, match="mapping"):
        W.parse([{"seed": 1, "count": 1, "force": ["augmentation=pristine"]}])


def test_a_jobs_force_is_merged_after_the_command_lines_so_it_wins():
    job = W.parse([{"seed": 1, "count": 1,
                    "force": {"augmentation": "pristine"}}])[0]
    assert job.pins(["augmentation=heavy", "visual=laser_sharp"]) == [
        "augmentation=heavy", "visual=laser_sharp", "augmentation=pristine"]


def test_a_written_list_reads_back_as_what_was_written(tmp_path):
    jobs = [W.Job("a", 1, 2, (("augmentation", "pristine"),)), W.Job(None, 3, 1)]
    assert W.read(W.write(tmp_path / "j.json", jobs)) == jobs


def test_jobs_are_hashable_so_they_can_key_a_cache():
    """The renderers key their parsed `--force` by job; a job that could not be
    a dict key would mean re-reading the rules once per page."""
    assert len({W.Job("a", 1, 1), W.Job("a", 1, 1), W.Job("b", 1, 1)}) == 2


# ------------------------------------------------ the same pages, drawn two ways


def _render(backend: str, out: Path, args: list[str]) -> list[tuple]:
    script, cwd = SCRIPTS[backend]
    interpreter = venv_python(VENVS[backend])
    result = subprocess.run(
        [str(interpreter), str(script), "-o", str(out.resolve()), *args],
        cwd=cwd, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-2000:]
    pages = []
    for item in record.read(out / "metadata.jsonl"):
        pages.append((
            hashlib.sha256((out / record.file_name(item)).read_bytes()).hexdigest(),
            record.ground_truth(item),
            json.dumps(record.boxes(item), sort_keys=True),
        ))
    return pages


@pytest.mark.slow
@pytest.mark.parametrize("backend", sorted(SCRIPTS))
def test_a_page_is_the_same_drawn_alone_or_in_a_list(backend, tmp_path):
    """The claim the whole change rests on, checked as bytes rather than argued.

    Splitting the same work across processes the old way and drawing it in one
    process the new way must produce identical images, identical labels and
    identical quads. If it does not, the process boundary is carrying state,
    which is the failure this test exists to make loud -- it was silent for
    four waves in the glyph backend.
    """
    if not venv_python(VENVS[backend]).exists():
        pytest.skip(f"{backend} environment not built")

    split: list[tuple] = []
    for job in PLAN:
        here = tmp_path / "split" / job["layout"]
        split += _render(backend, here, ["-c", str(job["count"]),
                                         "--seed", str(job["seed"]),
                                         "--layout", job["layout"]])

    jobs = tmp_path / "jobs.json"
    jobs.write_text(json.dumps(PLAN), encoding="utf-8")
    joined = _render(backend, tmp_path / "joined", ["--jobs", str(jobs)])

    assert len(joined) == len(split) == sum(job["count"] for job in PLAN)
    for index, (alone, together) in enumerate(zip(split, joined)):
        assert alone[0] == together[0], f"page {index}: the image differs"
        assert alone[1] == together[1], f"page {index}: the label differs"
        assert alone[2] == together[2], f"page {index}: the boxes differ"


@pytest.mark.slow
def test_a_glyph_page_does_not_depend_on_its_position_in_the_process(tmp_path):
    """The defect that batching exposed, kept as a test of its own.

    The same seed drawn as the first page of a process and as the second page
    of a process must give the same image. Before `_warm_imgaug` it did not,
    and the difference was invisible: same label, same words, different pixels
    and different quads.
    """
    if not venv_python(VENVS["synthdog"]).exists():
        pytest.skip("synthdog environment not built")

    alone = _render("synthdog", tmp_path / "alone",
                    ["-c", "1", "--seed", "5000", "--layout", "market_vat"])
    pair = _render("synthdog", tmp_path / "pair",
                   ["-c", "2", "--seed", "4999", "--layout", "market_vat"])
    assert alone[0][0] == pair[1][0], (
        "seed 5000 drew a different image as page 2 of a process than as page 1")
