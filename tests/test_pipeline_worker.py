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

from pipeline.worker import DONE, is_done, mark_done, shard_dir

REPO_ROOT = Path(__file__).resolve().parents[1]


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


# --------------------------------------------------------- the command built

def test_renderer_command_carries_the_pins_and_the_page_model(tmp_path, monkeypatch):
    """What a backend is actually told to do, without running one.

    The flags are the whole contract between the plan and the renderers, and
    they are invisible in a passing run: a `--template` that never reaches the
    command line produces a complete, valid dataset drawn from the wrong page
    model.
    """
    from pipeline import worker

    interpreter = tmp_path / "bin" / "python"
    interpreter.parent.mkdir(parents=True)
    interpreter.touch()
    monkeypatch.setattr(worker, "venv_python", lambda venv: interpreter)

    command = worker.renderer_command(
        "html", tmp_path / "out", tmp_path / "jobs.json",
        clean=True, force=["visual=laser_invoice"], template="auto")
    assert "--template" in command
    assert command[command.index("--template") + 1] == "auto"
    assert "--force" in command
    assert f"augmentation={worker.CLEAN_AUGMENTATION}" in command
    assert "--clean" not in command, (
        "`--clean` switched off the glyph backend's own geometry; no drawable "
        "backend has any, so a clean run is augmentation=pristine and nothing else")

    grid = worker.renderer_command(
        "html", tmp_path / "out", tmp_path / "jobs.json", clean=False, force=[])
    assert "--template" not in grid, "no template means the character grid"


def test_a_name_that_is_not_a_backend_cannot_be_dispatched(tmp_path):
    """The registry turns a name into a process, so it is the backstop.

    A retired backend is refused earlier by `Config`, with the reason; a typo
    has no earlier check at all, because the seed arithmetic is N-backend and
    `Config` deliberately does not police names it merely does not recognise.
    Both stop here.
    """
    from pipeline import worker
    from pipeline.worker import ShardError

    for name in ("synthdog", "genalog", "crayon"):
        with pytest.raises(ShardError, match="not a backend"):
            worker.renderer_command(
                name, tmp_path / "out", tmp_path / "jobs.json",
                clean=False, force=[])


def test_a_retired_backend_is_refused_by_name_with_the_reason():
    """Refused at the config, not silently mixed at the renderer.

    This used to be narrower -- a *sheet* run could not include the glyph
    backend, because it draws a character grid and would have produced a third
    of the images from a different page model. `synthdog` and `genalog` are now
    off for dataset generation altogether, so the refusal is unconditional and
    carries the reason rather than leaving a reader to find it.
    """
    from pipeline.config import Config, ConfigError

    for retired in ("synthdog", "genalog"):
        with pytest.raises(ConfigError, match=retired):
            Config.from_dict({
                "run": {"out": "/tmp/x", "per_backend": 2},
                "backends": [retired, "html"],
            })


def test_the_shipped_config_names_only_drawable_backends():
    from pipeline.config import ACTIVE_BACKENDS, Config

    config = Config.load(REPO_ROOT / "pipeline.yaml")
    assert set(config.backends) <= set(ACTIVE_BACKENDS)
