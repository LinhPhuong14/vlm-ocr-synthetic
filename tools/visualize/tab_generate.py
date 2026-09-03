"""Tab 1: sinh ảnh, xem trực tiếp từng ảnh vừa xong trong một gallery, có
thanh tiến độ và xem/tương tác box của ảnh đang chọn.

The Gradio widgets and event wiring only -- see `live_run.py` for how images
land here one at a time instead of at the end of a batch, and the plan file
this tool was built from for why (`shard.size = 1` + disk polling, not a
callback into `pipeline.run.execute()`).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import gradio as gr

REPO_ROOT = Path(__file__).resolve().parents[2]
for _extra in (REPO_ROOT, REPO_ROOT / "tools", Path(__file__).resolve().parent):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

import live_run  # noqa: E402

from rulebase import available_layouts, load_rules  # noqa: E402

RANDOM = "— ngẫu nhiên —"
POLL_SECONDS = 0.7
EMPTY_ANNOTATED = (None, [])


def _augmentation_choices() -> list[str]:
    try:
        return [RANDOM] + [option.id for option in load_rules()["augmentation"]]
    except Exception:  # noqa: BLE001 -- a bad rules dir must not crash the tab
        return [RANDOM]


def _layout_choices() -> list[str]:
    try:
        return list(available_layouts())
    except Exception:  # noqa: BLE001
        return []


def _caption(result: dict) -> str:
    attrs = (result.get("recipe") or {}).get("attributes") or {}
    augmentation = (attrs.get("augmentation") or {}).get("id", "?")
    return f"{result['layout']} · {augmentation}"


def generate(n: float, layouts: list[str], augmentation: str, workers: float,
            progress: gr.Progress = gr.Progress()):
    """The Generate button's handler -- a generator, so Gradio streams each
    `yield` to the gallery/status/state outputs instead of waiting for
    return. `progress` is a Gradio-recognised default: calling it each step
    draws the built-in progress bar, no extra component needed."""
    n = int(n)
    workers = max(1, int(workers))
    force = [] if augmentation == RANDOM else [f"augmentation={augmentation}"]

    problems = live_run.preflight_problems()
    if problems:
        yield [], "**preflight:**\n" + "\n".join(f"- {p}" for p in problems), []
        return

    out = live_run.new_out_dir()
    config = live_run.build_config(out=out, n=n, layouts=list(layouts or []),
                                   force=force)
    progress(0, desc="đang khởi động...")
    yield [], live_run.eta_pre_run(n, workers), []

    state = live_run.start(config, workers)
    gallery: list[tuple[str, str]] = []
    metadata: list[dict] = []

    while True:
        for result in live_run.poll_new(state):
            gallery.append((str(result["path"]), _caption(result)))
            metadata.append(result)
        progress(len(state.done) / max(state.total, 1),
                desc=f"{len(state.done)}/{state.total} ảnh")
        yield gallery, live_run.eta_live(state), metadata
        if state.finished:
            break
        time.sleep(POLL_SECONDS)

    # One last look: a shard can finish in the gap between the last poll
    # above and the thread actually reporting `finished`.
    for result in live_run.poll_new(state):
        gallery.append((str(result["path"]), _caption(result)))
        metadata.append(result)
    progress(1, desc="xong")
    yield gallery, live_run.summary(state), metadata


def show_detail(metadata: list[dict], evt: gr.SelectData):
    """A gallery thumbnail was clicked: the ảnh's own detail markdown, plus
    its boxes drawn on `gr.AnnotatedImage` and kept in a state for the
    box-click handler below to index into."""
    if not metadata or evt.index is None or evt.index >= len(metadata):
        return "_(chưa chọn ảnh)_", EMPTY_ANNOTATED, None
    result = metadata[evt.index]
    return (live_run.detail_markdown(result), live_run.annotations_for(result), result)


def show_box(current: dict | None, evt: gr.SelectData) -> str:
    """A box on the annotated image was clicked: that box's own kind/text."""
    if not current or evt.index is None:
        return "_(bấm vào một hộp để xem nội dung)_"
    return live_run.box_detail(current, evt.index)


def build_tab() -> None:
    with gr.Tab("🖼️ Sinh ảnh"):
        gr.Markdown(
            "Sinh vài ảnh và xem từng ảnh xuất hiện ngay khi xong -- không "
            "chờ hết cả mẻ. Dùng `shard.size=1` (mỗi ảnh một tiến trình "
            "renderer riêng) nên **chậm hơn** `make dataset` thật; hợp cho "
            "xem thử 5-50 ảnh, không hợp cho sinh dataset."
        )
        with gr.Row(equal_height=False):
            with gr.Column(scale=1, min_width=320):
                with gr.Group():
                    n = gr.Slider(1, 50, value=5, step=1, label="Số lượng ảnh")
                    workers = gr.Slider(1, 8, value=2, step=1, label="Worker song song")
                    augmentation = gr.Dropdown(
                        choices=_augmentation_choices(), value=RANDOM,
                        label="Augmentation (ép buộc, hoặc để ngẫu nhiên)")
                with gr.Accordion("Bố cục (bỏ trống = mọi bố cục)", open=False):
                    layouts = gr.CheckboxGroup(choices=_layout_choices(), show_label=False)
                go = gr.Button("Sinh ảnh", variant="primary", size="lg")
                status = gr.Markdown("")

            with gr.Column(scale=2):
                gallery = gr.Gallery(label="Ảnh đã sinh", columns=4, object_fit="contain",
                                     height=420)
                with gr.Row(equal_height=False):
                    annotated = gr.AnnotatedImage(
                        label="Ảnh + hộp (bấm một ảnh ở trên, rồi bấm một hộp)",
                        show_legend=True, scale=2)
                    detail = gr.Markdown("_(bấm vào một ảnh để xem chi tiết)_", scale=1)

        meta_state = gr.State([])       # every generated image's metadata, this run
        current_result = gr.State(None)  # the one selected in the gallery, if any

        go.click(generate, inputs=[n, layouts, augmentation, workers],
                 outputs=[gallery, status, meta_state])
        gallery.select(show_detail, inputs=[meta_state],
                       outputs=[detail, annotated, current_result])
        annotated.select(show_box, inputs=[current_result], outputs=[detail])
