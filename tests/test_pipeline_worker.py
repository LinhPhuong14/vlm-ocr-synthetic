"""The parts of the worker that need no renderer.

Rendering a shard needs all three virtualenvs, so it is verified by hand and
stays out of the dependency-free CI job. What *can* be tested here is the
resume contract -- which is the part that decides whether a killed run
recovers correctly or silently produces duplicates.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pipeline import record
from pipeline.worker import DONE, is_done, mark_done, shard_dir


def test_shard_directories_are_zero_padded_and_ordered(tmp_path):
    names = [shard_dir(tmp_path, i).name for i in (0, 3, 42, 1000)]
    assert names == ["shard-0000", "shard-0003", "shard-0042", "shard-1000"]
    # Padding is not cosmetic: unpadded names sort shard-10 before shard-2, and
    # a listing that reads out of order is a listing nobody trusts.
    assert sorted(names) == names


def test_a_directory_without_the_marker_is_not_done(tmp_path):
    directory = tmp_path / "shard-0000"
    directory.mkdir()
    (directory / "metadata.jsonl").write_text('{"a": 1}\n', encoding="utf-8")
    (directory / "html_000.jpg").write_bytes(b"not really a jpeg")
    # A fragment: files present, no marker. Resume must treat this as unfinished
    # however much of it is there.
    assert not is_done(directory)


def test_the_marker_is_the_last_thing_written(tmp_path):
    directory = tmp_path / "shard-0000"
    directory.mkdir()
    mark_done(directory, {"shard": 0, "images": 3})
    assert is_done(directory)
    payload = json.loads((directory / DONE).read_text(encoding="utf-8"))
    assert payload["images"] == 3
    # No temporary left behind: the rename is what makes the marker atomic, so
    # a leftover .tmp would mean it was written in place after all.
    assert not list(directory.glob(".*tmp"))


def test_marking_done_twice_is_harmless(tmp_path):
    directory = tmp_path / "shard-0000"
    directory.mkdir()
    mark_done(directory, {"images": 1})
    mark_done(directory, {"images": 2})
    assert json.loads((directory / DONE).read_text(encoding="utf-8"))["images"] == 2


# ------------------------------------------------- carrying a document type


@pytest.fixture
def command(monkeypatch):
    """`renderer_command` with the interpreter check satisfied.

    The check exists to fail early when a virtualenv was never built; here it
    is the only thing standing between this test and the argument list, which
    is what is actually under test.
    """
    import sys

    from pipeline import worker

    monkeypatch.setattr(worker, "venv_python", lambda _venv: Path(sys.executable))

    def build(run: dict) -> list[str]:
        return worker.renderer_command("html", Path("/tmp/staging"), run,
                                       clean=False, force=[])

    return build


def test_a_layout_only_run_sends_no_doc_flag(command):
    """The old command line, character for character.

    A plan that does not stratify by document type must produce exactly the
    invocation it always did -- that is what keeps the golden baseline a check
    on this change rather than a casualty of it.
    """
    assert "--doc" not in command({"count": 3, "seed": 2026, "layout": "market_vat"})


def test_a_stratified_run_pins_the_type_it_was_planned_for(command):
    built = command({"count": 3, "seed": 2026, "layout": "market_vat",
                     "doc_type": "business.receipt.retail"})
    assert built[built.index("--doc") + 1] == "business.receipt.retail"


def test_the_type_of_a_record_is_read_from_its_label():
    """Not from the plan: the label is what a consumer of the dataset sees."""
    item = {"ground_truth": json.dumps(
        {"gt_parse": {"doc_type": "business.receipt.retail", "title": "X"}})}
    assert record.doc_type(item) == "business.receipt.retail"


@pytest.mark.parametrize("item", [
    {},
    {"ground_truth": "not json"},
    {"ground_truth": json.dumps({"gt_parse": {"title": "X"}})},
])
def test_a_record_with_no_usable_type_reports_none_rather_than_raising(item):
    """Assembling a dataset must not die on one odd line."""
    assert record.doc_type(item) == ""
