"""Tab 2: con dấu vẽ bằng PIL (`tools/make_ornaments.py`), với màu sắc, hình
dạng, nội dung ở giữa và một lớp "mòn/kiểu đóng" chỉnh được ngay trên UI.

Từng là một cột PIL cạnh một cột thử nghiệm bằng synthtiger, để so hai cách
vẽ con dấu -- xem lịch sử git nếu cần lại bản đó. synthtiger không vẽ được
chữ cong theo đúng một vòng tròn (`CurveLayout` chỉ uốn theo parabola), nên
`make_ornaments.py`'s `_arc_text` (dựng bằng toạ độ cực, không qua synthtiger)
vẫn là -- và luôn là -- thứ thật sự tạo ra con dấu; cột kia chỉ minh hoạ vì
sao. Tab này giữ lại đúng nửa thật, và mở rộng nó thay vì diễn lại phép so
sánh mỗi lần bấm nút.
"""

from __future__ import annotations

import sys
from pathlib import Path

import gradio as gr

REPO_ROOT = Path(__file__).resolve().parents[2]
for _extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from make_ornaments import (  # noqa: E402
    _ring_only,
    double_strike,
    edge_seal,
    rectangular_seal,
    round_seal,
)

# Khoảng `coverage` truyền vào `_ink()` -- thấp hơn nghĩa là mực mòn/nhạt hơn.
# Xem `round_seal`'s docstring cho ý nghĩa của tham số `wear`.
WEAR = {
    "sắc nét": (0.90, 0.97),
    "bình thường": (0.78, 0.93),
    "mòn / nhạt": (0.55, 0.72),
}

# Hậu xử lý áp lên ảnh con dấu ĐÃ vẽ xong -- "lớp" theo đúng nghĩa augment:
# mỗi lựa chọn là một bước riêng, không phải một tham số của chính `round_seal`
# / `rectangular_seal`. `None` nghĩa là không thêm bước nào.
STRIKE = {
    "một lần (bình thường)": None,
    "đóng hai lần (double strike)": "double",
    "mờ vành, rỗng ruột (mặt dấu vồng)": "faint",
    "giáp lai (chỉ giữ một nửa mép)": "edge",
}

CENTRE = {
    "ngôi sao": "star",
    "chữ (dòng giữa)": "text",
    "cả hai (sao trên, chữ dưới)": "both",
    "để trống": "none",
}


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    value = (value or "#C41E26").lstrip("#")
    if len(value) != 6:
        value = "C41E26"
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def _apply_strike(image, strike_label: str, seed: int):
    kind = STRIKE.get(strike_label)
    if kind == "double":
        return double_strike(image, seed=seed)
    if kind == "faint":
        return _ring_only(image)
    if kind == "edge":
        return edge_seal(image)
    return image


def generate(shape: str, colour_hex: str, centre_label: str, top: str, bottom: str,
            middle_text: str, wear_label: str, strike_label: str, seed: float):
    colour = _hex_to_rgb(colour_hex)
    middle = [line for line in (middle_text or "").splitlines() if line.strip()]
    seed = int(seed)
    lo, hi = WEAR.get(wear_label, WEAR["bình thường"])

    if shape == "square":
        lines = middle or [top or "CONG TY TNHH VI DU"]
        image = rectangular_seal(lines, seed=seed, colour=colour, wear=(lo, hi))
    else:
        image = round_seal(top or "CONG TY TNHH VI DU", bottom, middle, seed=seed,
                           colour=colour, centre_kind=CENTRE.get(centre_label, "star"),
                           wear=(lo, hi))

    return _apply_strike(image, strike_label, seed)


def _toggle_centre(shape: str):
    """Nội dung giữa chỉ có ý nghĩa với dấu tròn -- `rectangular_seal` không
    có khái niệm sao/chữ riêng, `lines` của nó LÀ toàn bộ nội dung dấu."""
    return gr.update(visible=(shape == "round"))


def build_tab() -> None:
    with gr.Tab("Con dấu"):
        gr.Markdown(
            "Vẽ con dấu bằng PIL (`tools/make_ornaments.py`) -- cùng mã nguồn "
            "sinh ra mọi con dấu trong `textures/ornament/`. Đổi màu, hình dạng, "
            "nội dung giữa và độ mòn/kiểu đóng, xem ngay kết quả."
        )
        with gr.Row():
            shape = gr.Radio(["round", "square"], value="round", label="Hình dạng")
            colour = gr.ColorPicker(value="#C41E26", label="Màu mực")
        with gr.Row():
            top = gr.Textbox(label="Dòng trên (round) / dùng khi Dòng giữa trống (square)",
                             value="CONG TY TNHH VI DU")
            bottom = gr.Textbox(label="Dòng dưới (chỉ round)", value="MST 0123456789")
        with gr.Row():
            centre = gr.Radio(list(CENTRE), value="ngôi sao",
                              label="Nội dung giữa (chỉ dấu tròn)")
            middle = gr.Textbox(
                label="Dòng giữa -- mỗi dòng một ô (round: dùng khi Nội dung giữa "
                     "là 'chữ' hoặc 'cả hai'; square: TOÀN BỘ nội dung con dấu)",
                lines=2, value="DA THU TIEN")
        with gr.Row():
            wear = gr.Radio(list(WEAR), value="bình thường", label="Mòn mực")
            strike = gr.Dropdown(list(STRIKE), value="một lần (bình thường)",
                                 label="Kiểu đóng")
        seed = gr.Number(label="Seed", value=0, precision=0)
        go = gr.Button("Vẽ", variant="primary")
        out = gr.Image(label="Con dấu", type="pil")

        shape.change(_toggle_centre, inputs=[shape], outputs=[centre])
        go.click(generate, inputs=[shape, colour, centre, top, bottom, middle, wear, strike, seed],
                 outputs=[out])
