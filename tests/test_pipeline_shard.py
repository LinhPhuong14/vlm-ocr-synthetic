"""A whole shard assembled, with a renderer that draws nothing.

`tests/test_pipeline_worker.py` covers the resume contract and the command
line, and says the rest "needs all three virtualenvs, so it is verified by
hand". That was true while a shard's own work was three lines of dict
assignment. It is not the part that breaks: what breaks is the seam between a
renderer's `metadata.jsonl` and the dataset's -- the rename, the layout the
plan asked for against the layout the recipe drew, and the shape check on the
way out. All three are `pipeline/record.py` calls now, and none of them needs a
pixel.

So the renderer here is a script that copies a committed JPEG and writes a
record built exactly the way the real three build theirs. It is not a second
implementation of one: it renders nothing, and if it ever needed to, this test
would be measuring the wrong thing. What it is is the shard's own contract,
run end to end, in the dependency-free CI job.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from pipeline import record, worker

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "data" / "dataset60" / "html" / "html_000.jpg"

# Two layouts, the second drawn twice: the arrangement where an off-by-one in
# the walk over runs mislabels every page after it.
RUNS = [
    {"layout": "eatery_ascii", "seed": 2026, "count": 1, "first_index": 0},
    {"layout": "market_vat", "seed": 3026, "count": 2, "first_index": 1},
]

FAKE_RENDERER = '''
import argparse, json, os, shutil, sys
from pathlib import Path

sys.path.insert(0, __REPO_ROOT__)

import rulebase
import worklist
from pipeline import invariants, record

parser = argparse.ArgumentParser()
parser.add_argument("-o", "--out", type=Path, required=True)
parser.add_argument("--jobs", type=Path)
parser.add_argument("--force", action="append", default=[])
parser.add_argument("--template", default="")
parser.add_argument("--clean", action="store_true")
parser.add_argument("--seed", type=int, default=0)
parser.add_argument("-c", "--count", type=int, default=1)
parser.add_argument("--layout", default=None)
args = parser.parse_args()

SOURCE = Path(__SOURCE__)
width, height = invariants.jpeg_size(SOURCE)
args.out.mkdir(parents=True, exist_ok=True)

# The one thing this renderer can do wrong on purpose: hand its pages back in
# an order the job list did not ask for.
pages = list(worklist.pages(worklist.load(args)))
if os.environ.get("SHARD_TEST_REVERSE"):
    pages = [(index, job, seed) for index, (_i, job, seed)
             in enumerate(reversed(pages))]

with open(args.out / "metadata.jsonl", "w", encoding="utf-8") as handle:
    for index, job, seed in pages:
        recipe, receipt, grid = rulebase.make(seed=seed, force={"layout": job.layout})
        name = f"html_{index:03d}.jpg"
        shutil.copy2(SOURCE, args.out / name)
        item = record.build(
            filename=name, width=width, height=height, parser="html",
            boxes=[{"kind": cell.role, "text": cell.text,
                    "quad": [[0, 0], [10, 0], [10, 10], [0, 10]]}
                   for cell in grid.cells if cell.text.strip() and cell.role != "sep"],
            extracted=receipt.ground_truth(),
            text_sequence=receipt.text_sequence(), recipe=recipe.to_dict())
        json.dump(item, handle, ensure_ascii=False)
        handle.write("\\n")
'''


@pytest.fixture
def shard(tmp_path, monkeypatch):
    """A worker pointed at the script above instead of a renderer venv.

    The script is written into the temporary directory, not into the tree: a
    run killed halfway through must not leave a file behind that looks like a
    renderer. Both paths it needs are baked into its text for the same reason.
    """
    script = tmp_path / "fake_renderer.py"
    script.write_text(FAKE_RENDERER
                      .replace("__SOURCE__", repr(str(SOURCE)))
                      .replace("__REPO_ROOT__", repr(str(REPO_ROOT))),
                      encoding="utf-8")
    monkeypatch.setitem(worker.BACKENDS, "html", (script, REPO_ROOT))
    monkeypatch.setattr(worker, "venv_python", lambda venv: Path(sys.executable))
    yield {"index": 0, "backend": "html", "count": 3, "runs": RUNS}


def rendered(shard, tmp_path, **plan):
    out = tmp_path / "run"
    result = worker.render_shard(shard, out, {"clean": False, "force": [], **plan})
    directory = worker.shard_dir(out, shard["index"])
    return result, directory, record.read(directory / "metadata.jsonl")


def test_a_shard_comes_out_in_the_shape_record_defines(shard, tmp_path):
    result, directory, items = rendered(shard, tmp_path)

    assert result["images"] == 3
    assert worker.is_done(directory)
    assert len(items) == 3
    for item in items:
        assert record.validate(item) == [], record.file_name(item)
        assert item["schema_version"] == record.SCHEMA_VERSION
        assert item["task"] == record.TASK_CONVERT


def test_the_dataset_name_reaches_every_field_that_follows_it(shard, tmp_path):
    """The rename is three fields, not one, and the third is derived."""
    _result, directory, items = rendered(shard, tmp_path)

    names = [record.file_name(item) for item in items]
    assert names == ["html_000.jpg", "html_001.jpg", "html_002.jpg"]
    for item, name in zip(items, names):
        assert (directory / name).exists()
        assert item["source_files"] == [name]
        assert item["job_id"] == record.job_id(
            "html", record.layout(item), record.recipe(item)["seed"], name)
    assert len({item["job_id"] for item in items}) == 3


def test_the_plans_layout_is_attached_to_every_page(shard, tmp_path):
    _result, _directory, items = rendered(shard, tmp_path)
    assert [record.layout(item) for item in items] == [
        "eatery_ascii", "market_vat", "market_vat"]
    assert {record.framework(item) for item in items} == {"html"}
    assert {item["settings"]["convert_mode"] for item in items} == {"html"}


def test_a_renderer_that_returns_its_pages_in_another_order_is_caught(
        shard, tmp_path, monkeypatch):
    """The walk over runs is by position, so a reordering mislabels silently.

    The plan is untouched and the renderer hands its pages back reversed --
    exactly the shape of an off-by-one, and the arrangement in which every page
    after it gets another layout's name while the file count still adds up. It
    must not reach DONE.
    """
    monkeypatch.setenv("SHARD_TEST_REVERSE", "1")
    with pytest.raises(worker.ShardError, match="different order from the job list"):
        rendered(shard, tmp_path)
    assert not worker.is_done(worker.shard_dir(tmp_path / "run", shard["index"]))


def test_a_shard_that_is_already_done_is_left_alone(shard, tmp_path):
    _result, directory, items = rendered(shard, tmp_path)
    stamp = (directory / "metadata.jsonl").stat().st_mtime_ns

    again = worker.render_shard(shard, tmp_path / "run", {"clean": False, "force": []})
    assert again["skipped"] and again["images"] == 0
    assert (directory / "metadata.jsonl").stat().st_mtime_ns == stamp
