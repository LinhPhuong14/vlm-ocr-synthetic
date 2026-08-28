"""Tab 3: `BothHands` (production, per field) beside `HybridHand` (new, per
word) on the same input text.

The WriteViT half (`Hand`) is opened lazily, once, and kept alive for the
whole app -- the same reason `generators/html/handwriting.py`'s own `Hand`
docstring gives: an 11 s cold load should be paid once, not per click. If
`../WriteViT` is not installed, this tab does not disable itself: it falls
back to font-only on both panels, with a banner saying so, because the font
half of both comparisons needs nothing WriteViT-related at all.
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

COLOR = {"model": (37, 99, 235), "font": (217, 119, 6), "skipped": (156, 163, 175)}
MARK = {"model": "🔵 model", "font": "🟠 font", "skipped": "⬜ bỏ qua"}


class _NullHand:
    """Stands in for `Hand` when WriteViT is not installed.

    Writes nothing (`tiles()` is always empty), so `hybrid_line` and the
    `BothHands` preview both fall through to `FontHand` for every word --
    the correct behaviour when the model half simply is not there, achieved
    by reusing the real per-word routing rather than a second code path.
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


def compare(text: str):
    text = (text or "").strip()
    if not text:
        placeholder = "_(nhập text)_"
        return "", None, placeholder, None, placeholder

    font = hw.FontHand()
    font.open()
    page = hw.Page(seed=_seed_for(text))
    hand, error = _get_hand()
    banner = ("" if hand is not None else
             f"⚠️ **WriteViT chưa cài** ({error}) -- cả hai bên dưới đều chỉ "
             f"dùng font. Chạy `python tools/writevit/setup.py` (~294 MB) để "
             f"có so sánh thật.")
    effective_hand = hand if hand is not None else _NullHand()

    # -- BothHands: what the production per-FIELD policy would pick --
    if hand is not None and hw.writable(text):
        both_image = hand.line(text, page.writer, page.seed)
        both_note = "**BothHands chọn: model** — viết được toàn bộ trường."
    else:
        # BothHands would set live CSS text here; there is no browser in this
        # tool, so the same font/PIL path `font_tile` uses stands in as a
        # preview of the shape, not the production pixels.
        words = hw.words_of(text)
        tiles = [(word, hw.font_tile(word, font.face_for(page))) for word in words
                if font.writable(word, page)]
        both_image = hw.compose(tiles) if tiles else None
        reason = "chưa cài WriteViT" if hand is None else hw.refusal(text)
        both_note = (f"**BothHands chọn: font** — toàn bộ trường, vì model từ "
                     f"chối (`{reason}`).\n\n_Đây là ảnh xem trước dựng bằng "
                     f"PIL — trang thật do Chromium/WeasyPrint vẽ chữ sống, "
                     f"không phải ảnh này._")

    # -- HybridHand: the new per-WORD split, always the real composited image --
    try:
        hybrid_image, report = hw.hybrid_line(text, effective_hand, font, page)
        overlay = _draw_overlay(hybrid_image, report)
        legend = _legend(report)
    except ValueError as error:
        overlay, legend = None, f"_(không viết được: {error})_"

    return banner, both_image, both_note, overlay, legend


def build_tab() -> None:
    with gr.Tab("Viết tay (hybrid)"):
        gr.Markdown(
            "So sánh `BothHands` (đã có trong `generators/html/handwriting.py`, "
            "chọn model/font theo **từng trường**) với `HybridHand` (mới, trộn "
            "model+font **trong cùng một trường**) trên cùng một đoạn text."
        )
        text = gr.Textbox(
            label="Text", lines=2,
            value="Nguyễn Văn A nộp 3.920.000 đồng cho HOÁ ĐƠN số 17")
        go = gr.Button("So sánh", variant="primary")
        banner = gr.Markdown("")
        with gr.Row():
            with gr.Column():
                gr.Markdown("### BothHands — theo trường (đã có)")
                both_image = gr.Image(label="Preview", type="pil")
                both_note = gr.Markdown("")
            with gr.Column():
                gr.Markdown("### HybridHand — theo từ (mới)")
                hybrid_image = gr.Image(label="Kết quả thật", type="pil")
                legend = gr.Markdown("")

        go.click(compare, inputs=[text],
                 outputs=[banner, both_image, both_note, hybrid_image, legend])
