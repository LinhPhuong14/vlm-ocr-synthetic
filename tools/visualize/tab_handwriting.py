"""Tab 3: xem chữ WriteViT sinh ra, từng từ, trên một đoạn text tự nhập.

`hw.hybrid_line` đã là "chữ từ model, chỗ nào model không viết được thì rơi
về font" -- không phải chữ giả, và không phải một bản so sánh: đây LÀ chữ
thật `generators/html/handwriting.py` dùng trong pipeline (`HybridHand`).
Tab này từng đặt nó cạnh `BothHands` (chọn model/font theo TRƯỜNG, chính sách
production) để so hai cách chọn; giờ model (`../WriteViT`) đã sẵn có nên việc
cần xem là chữ model sinh ra trông thế nào, không phải so hai chính sách --
`BothHands` bỏ hẳn khỏi tab này.

`Hand` (nửa WriteViT) mở lười, một lần, giữ sống cả app -- cùng lý do
docstring `Hand` của `generators/html/handwriting.py` nêu: 11s tải nguội trả
một lần, không phải mỗi lần bấm. Nếu `../WriteViT` chưa cài, tab không tự tắt:
nó rơi về chỉ-font, kèm banner nói rõ vì sao -- không im lặng giả chữ.
"""

from __future__ import annotations

import sys
import threading
import zlib
from pathlib import Path

import gradio as gr

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

import handwriting as hw  # noqa: E402

RANDOM = "— ngẫu nhiên —"
COLOR = {"model": (37, 99, 235), "font": (217, 119, 6), "skipped": (156, 163, 175)}
MARK = {"model": "🔵 model", "font": "🟠 font", "skipped": "⬜ bỏ qua"}


class _NullHand:
    """Stands in for `Hand` when WriteViT is not installed.

    Writes nothing (`tiles()` is always empty), so `hybrid_line` falls
    through to `FontHand` for every word -- the correct behaviour when the
    model half simply is not there, achieved by reusing the real per-word
    routing rather than a second code path.
    """

    source = "model"
    device = "(WriteViT chưa cài)"

    def tiles(self, words, writer, seed):  # noqa: ARG002 -- matches Hand.tiles
        return {}


_lock = threading.Lock()
_state: dict = {"hand": None, "error": None, "tried": False}


def _get_hand():
    """The shared `Hand`, opened on the first call and kept for the app's life."""
    with _lock:
        if not _state["tried"]:
            _state["tried"] = True
            candidate = hw.Hand()
            try:
                candidate.open()
                _state["hand"] = candidate
            except RuntimeError as error:
                _state["error"] = str(error)
        return _state["hand"], _state["error"]


def _seed_for(text: str) -> int:
    """A seed tied to the text, so typing the same thing twice compares the
    same writer/pen -- stable across app restarts, unlike Python's hash()."""
    return zlib.crc32(text.encode("utf-8")) % 10_000


def _draw_overlay(image, report: list[dict]):
    from PIL import ImageDraw

    rgb = image.convert("RGB")
    draw = ImageDraw.Draw(rgb)
    for entry in report:
        if entry["engine"] == "skipped" or "left" not in entry:
            continue
        x, y, w, h = entry["left"], entry["top"], entry["width"], entry["height"]
        draw.rectangle([x, y, x + w, y + h],
                       outline=COLOR.get(entry["engine"], (0, 0, 0)), width=2)
    return rgb


def _legend(report: list[dict]) -> str:
    lines = ["| từ | nguồn |", "| --- | --- |"]
    for entry in report:
        mark = MARK.get(entry["engine"], entry["engine"])
        reason = f" ({entry['reason']})" if entry.get("reason") else ""
        lines.append(f"| {entry['word']} | {mark}{reason} |")
    return "\n".join(lines)


def _writer_choices() -> list[str]:
    return [RANDOM] + [str(i) for i in range(106)]


def generate(text: str, writer_choice: str):
    text = (text or "").strip()
    if not text:
        return "", None, "_(nhập text)_"

    font = hw.FontHand()
    font.open()
    page = hw.Page(seed=_seed_for(text))
    if writer_choice != RANDOM:
        page.writer = int(writer_choice)

    hand, error = _get_hand()
    banner = ("" if hand is not None else
             f"⚠️ **WriteViT chưa cài** ({error}) -- ảnh dưới đây chỉ dùng "
             f"font, không phải chữ model thật. Chạy "
             f"`python tools/writevit/setup.py` (~294 MB) để có chữ model.")
    effective_hand = hand if hand is not None else _NullHand()

    try:
        image, report = hw.hybrid_line(text, effective_hand, font, page)
        overlay = _draw_overlay(image, report)
        legend = f"writer `{page.writer:03d}`\n\n" + _legend(report)
    except ValueError as error:
        overlay, legend = None, f"_(không viết được: {error})_"

    return banner, overlay, legend


def build_tab() -> None:
    with gr.Tab("✍️ Viết tay (WriteViT)"):
        gr.Markdown(
            "Chữ do **WriteViT** sinh, từng từ -- từ nào model không viết "
            "được (số, ký tự ngoài bảng chữ cái đã huấn luyện, ...) rơi về "
            "font, đúng cơ chế `hybrid_line` trong pipeline thật."
        )
        with gr.Row(equal_height=False):
            text = gr.Textbox(
                label="Text", lines=2, scale=3,
                value="Nguyễn Văn A nộp 3.920.000 đồng cho HOÁ ĐƠN số 17")
            writer = gr.Dropdown(_writer_choices(), value=RANDOM, scale=1,
                                 label="Writer (ngẫu nhiên = theo seed của text)")
        go = gr.Button("Sinh chữ", variant="primary", size="lg")
        banner = gr.Markdown("")
        image = gr.Image(label="Kết quả", type="pil")
        legend = gr.Markdown("")

        go.click(generate, inputs=[text, writer], outputs=[banner, image, legend])
