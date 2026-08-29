"""Tab 1's non-Gradio half: drive `pipeline.run.execute()`, watch it happen.

`execute()` prints one line per finished SHARD, not per image (see its own
docstring) -- fine for a real run, useless for a "watch it happen" UI. Rather
than teach it a callback, this runs it with `shard.size = 1` on a background
thread and polls the shard directories it already writes, the same way
`tools/monitor.py` does for a long job. That keeps `pipeline/run.py` -- whose
`manifest.json` shape is checked byte-for-byte by `make baseline-verify` --
completely unmodified, at the cost of one renderer subprocess per image
instead of one per batch. Fine for the 5-50 image previews this tool is for;
wrong for a real dataset, which is what `make dataset` is for instead.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from monitor import _elapsed  # noqa: E402 -- same formatting, not restated

from pipeline import preflight, record, synthesis  # noqa: E402
from pipeline.config import Config  # noqa: E402
from pipeline.run import execute  # noqa: E402
from pipeline.worker import is_done  # noqa: E402

RUNS_ROOT = REPO_ROOT / "data" / "visualize_runs"
# Matches `pipeline.run.SHARDS_DIR`. Restated rather than imported: it is a
# module-level string, not a function, and importing one constant across a
# package boundary for this is more coupling than the constant is worth.
SHARDS_DIR = ".shards"


@dataclass
class RunState:
    """What the polling loop and the ETA maths both need, updated in place."""

    out: Path
    total: int
    started: float = field(default_factory=time.time)
    done: set[str] = field(default_factory=set)   # shard directory names seen
    finished: bool = False
    returncode: int | None = None
    error: str | None = None


# ------------------------------------------------------------------- config


def new_out_dir() -> Path:
    """A fresh, never-reused run directory.

    Reusing one would hit `render_shard`'s own resume logic -- a shard with a
    `DONE` file is left alone -- and a rerun of the same seed would then look
    like it finished instantly, which is confusing here even though it is
    exactly the right behaviour for a real job being resumed.
    """
    RUNS_ROOT.mkdir(parents=True, exist_ok=True)
    return RUNS_ROOT / uuid.uuid4().hex[:8]


def build_config(*, out: Path, n: int, layouts: list[str], force: list[str],
                  seed: int = 2026) -> Config:
    """The same shape `tools/generate_dataset.py` builds, with two differences:
    `shard.size` is pinned to 1 -- the mechanism this whole module exists for,
    not something a user picks -- and `backends` is always just `["html"]`,
    the one backend this repository still draws with."""
    return Config.from_dict({
        "run": {
            "out": str(out.resolve()),
            "per_backend": n,
            "seed": seed,
            "workers": 1,          # execute(workers=...) overrides this
            "clean": False,
            "layouts": list(layouts or []),
            "force": list(force),
            "pairing": "paired",
            "template": "",
        },
        "backends": ["html"],
        "shard": {"size": 1},
    })


def preflight_problems() -> list[str]:
    return preflight.check()


# --------------------------------------------------------------------- run


def start(config: Config, workers: int) -> RunState:
    """Launch `execute()` on a daemon thread and return the state to poll.

    A thread, not a process: `execute()` itself only orchestrates (it hands
    the actual rendering to a `ProcessPoolExecutor`, spawn-started, which is
    what actually touches Playwright) -- so nothing about running it from a
    non-main thread crosses the "sync API is not thread-safe" line
    `pipeline/run.py`'s own module docstring warns about; that boundary is the
    process pool, still there, still spawned the same way.
    """
    state = RunState(out=config.out, total=config.per_backend)

    def _run() -> None:
        try:
            state.returncode = execute(config, workers=workers, skip_preflight=True)
        except BaseException as error:  # noqa: BLE001 -- surfaced to the UI, not lost
            state.error = f"{type(error).__name__}: {error}"
            state.returncode = 1
        finally:
            state.finished = True

    threading.Thread(target=_run, daemon=True).start()
    return state


def poll_new(state: RunState) -> list[dict]:
    """Shards that finished since the last call, each resolved to one image.

    Reads directly from `.shards/shard-NNNN/`, the same directories
    `tools/monitor.py` polls -- nothing here writes anything, so it is safe to
    call against a run another thread is actively writing to.
    """
    shards_root = state.out / SHARDS_DIR
    if not shards_root.exists():
        return []
    found = []
    for directory in sorted(shards_root.glob("shard-*")):
        name = directory.name
        if name in state.done or not is_done(directory):
            continue
        state.done.add(name)
        found.append(_read_one(directory))
    return found


def _read_one(directory: Path) -> dict:
    """One shard's single image (shard.size=1), with its recipe and layout."""
    items = record.read(directory)   # exactly one record, given shard.size=1
    item = items[0]
    name = record.file_name(item)
    drew = synthesis.read_if_there(directory)
    return {
        "path": directory / name,
        "name": name,
        "record": item,
        "recipe": drew.recipe(name) if name in drew else {},
        "layout": drew.layout(name) if name in drew else "?",
        "job_id": (drew.entry(name) or {}).get("job_id", ""),
    }


# --------------------------------------------------------------------- eta


def eta_pre_run(n: int, workers: int) -> str:
    """Before a single image has rendered: the committed cost model's guess.

    `processes=n`, not `processes=workers`: with `shard.size=1` every image is
    its own renderer subprocess, so the fixed per-process startup cost
    `predict()` charges is paid `n` times over, not `workers` times -- the
    direct consequence of the throughput/feedback trade this tool makes.
    """
    model_path = REPO_ROOT / "data" / "profile" / "cost_model.json"
    if not model_path.exists():
        return "ước tính: chưa có data/profile/cost_model.json (chạy `make profile`)"
    try:
        from profile_pipeline import predict  # noqa: PLC0415 -- tools/ is on sys.path

        model = json.loads(model_path.read_text(encoding="utf-8"))
        predicted = predict(model, {"html": n}, processes=n)
        wall = predicted["seconds"] / max(min(workers, n), 1)
        return (f"ước tính ~{_elapsed(wall)} cho {n} ảnh "
                f"({min(workers, n)} worker song song, mỗi ảnh một renderer riêng)")
    except Exception as error:  # noqa: BLE001 -- an estimate that fails to load
        return f"ước tính: không tính được ({error})"       # is not a reason to stop


def eta_live(state: RunState) -> str:
    """Once real data exists, the measured rate beats the model's guess.

    Same formula as `tools/monitor.py::render()`: rate over every image
    written so far, not only images inside a fully-assembled dataset.
    """
    done = len(state.done)
    elapsed = time.time() - state.started
    if not done or elapsed <= 0:
        return "đang chờ ảnh đầu tiên..."
    rate = done / elapsed
    remaining = state.total - done
    if remaining <= 0:
        return f"{done}/{state.total} -- xong trong {_elapsed(elapsed)}"
    return (f"{done}/{state.total} -- {rate:.2f} ảnh/s, "
            f"còn khoảng {_elapsed(remaining / rate)}")


def summary(state: RunState) -> str:
    if state.error:
        return f"**Lỗi:** {state.error}"
    lines = [f"Xong -- {len(state.done)}/{state.total} ảnh, "
             f"{_elapsed(time.time() - state.started)}."]
    manifest_path = state.out / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for entry in manifest.get("failed") or []:
            lines.append(f"- [FAILED] shard {entry['shard']}: "
                         f"{str(entry['error']).splitlines()[0]}")
        for warning in (manifest.get("warnings") or [])[:5]:
            lines.append(f"- [warn] {warning}")
    return "\n".join(lines)


# ------------------------------------------------------------------ detail


def annotations_for(result: dict) -> tuple[str, list[tuple[tuple[int, int, int, int], str]]]:
    """One image's boxes, shaped for `gr.AnnotatedImage`'s `(image,
    [((x1, y1, x2, y2), label), ...])` value -- `record.boxes()` already
    carries `bbox`/`kind` per block, this just picks them apart."""
    boxes = record.boxes(result["record"])
    marks = []
    for box in boxes:
        bbox = box.get("bbox") or {}
        marks.append((
            (int(bbox.get("x1", 0)), int(bbox.get("y1", 0)),
             int(bbox.get("x2", 0)), int(bbox.get("y2", 0))),
            str(box.get("kind", "?")),
        ))
    return str(result["path"]), marks


def box_detail(result: dict, index: int) -> str:
    """One box's kind/text/coordinates, for the click-a-box detail panel."""
    boxes = record.boxes(result["record"])
    if index < 0 or index >= len(boxes):
        return "_(hộp không hợp lệ)_"
    box = boxes[index]
    bbox = box.get("bbox") or {}
    lines = [
        f"**hộp #{index}** -- `{box.get('kind', '?')}`",
        f"toạ độ: ({bbox.get('x1', '?')}, {bbox.get('y1', '?')}) -- "
        f"({bbox.get('x2', '?')}, {bbox.get('y2', '?')})",
        "",
        box.get("text") or "_(không có text)_",
    ]
    return "\n".join(lines)


def detail_markdown(result: dict) -> str:
    """Everything known about one generated image, for the click-for-detail panel."""
    item = result["record"]
    recipe = result.get("recipe") or {}
    attributes = recipe.get("attributes") or {}
    width, height = record.page_size(item)
    boxes = record.boxes(item)

    lines = [
        f"### {result['name']}",
        f"layout `{result['layout']}` · seed `{recipe.get('seed', '?')}` · "
        f"{width}x{height}px · {len(boxes)} hộp",
        "",
        "| thuộc tính | id |",
        "| --- | --- |",
    ]
    for name in sorted(attributes):
        lines.append(f"| {name} | `{attributes[name].get('id', '?')}` |")

    extracted = record.extracted(item)
    lines += ["", "```json",
             json.dumps(extracted, ensure_ascii=False, indent=2)[:3000],
             "```"]
    return "\n".join(lines)
