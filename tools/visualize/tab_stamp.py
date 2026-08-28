"""Tab 2: con dấu bằng synthtiger (thử nghiệm), cạnh `tools/make_ornaments.py`'s
PIL bản có sẵn.

See `generators/synthdog/tools/stamp_experiment.py`'s own docstring for why
this repo draws seals with PIL today and what the synthtiger attempt can and
cannot do (`CurveLayout`'s parabola vs. a true circle, no ellipse primitive).
This tab is a side-by-side, not a replacement -- the PIL column always
renders (in-process, no venv needed); the synthtiger column needs
`generators/synthdog/.venv`, checked fresh on every click so it starts
working the moment that venv is fixed, with no app restart needed.
"""

from __future__ import annotations

import platform
import subprocess
import sys
import tempfile
from pathlib import Path

import gradio as gr

REPO_ROOT = Path(__file__).resolve().parents[2]
for _extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

from make_ornaments import rectangular_seal, round_seal  # noqa: E402
from paths import VENVS, venv_python  # noqa: E402

SCRIPT = REPO_ROOT / "generators" / "synthdog" / "tools" / "stamp_experiment.py"


def _synthdog_ready() -> tuple[bool, str]:
    """Fresh on every call -- not cached, so fixing the venv works without
    restarting the app (the whole point of checking this per click)."""
    if venv_python(VENVS["synthdog"]).exists():
        return True, ""
    return False, (
        f"cần Python 3.8-3.11 cho synthdog (máy này đang chạy "
        f"{platform.python_version()}). Cài rồi dựng lại venv -- trên Ubuntu "
        f"24.04+ (noble) python3.11 không còn trong repo mặc định, cần thêm "
        f"deadsnakes trước:\n"
        f"  sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update\n"
        f"  sudo apt install python3.11 python3.11-venv\n"
        f"  python3.11 tasks.py setup-synthdog"
    )


def _pil_stamp(shape: str, top: str, bottom: str, middle: list[str], seed: int):
    """`tools/make_ornaments.py`'s existing PIL functions -- in-process, no
    venv, always available."""
    if shape == "square":
        lines = middle or [top or "CONG TY TNHH VI DU"]
        return rectangular_seal(lines, seed=seed)
    return round_seal(top or "CONG TY TNHH VI DU", bottom, middle, seed=seed)


def _synthtiger_stamp(shape: str, top: str, bottom: str, middle: list[str], seed: int):
    ready, message = _synthdog_ready()
    if not ready:
        return None, f"⚠️ chưa sẵn sàng -- {message}"

    with tempfile.TemporaryDirectory() as scratch:
        out = Path(scratch) / "stamp.png"
        command = [str(venv_python(VENVS["synthdog"])), str(SCRIPT),
                  "--shape", shape, "--top", top or "", "--bottom", bottom or "",
                  "--seed", str(seed), "--out", str(out)]
        for line in middle:
            command += ["--middle", line]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return None, "lỗi: quá 60s, dừng lại"
        if result.returncode != 0:
            # Same "last 15 lines" shape `pipeline/worker.py` uses for a
            # failed renderer subprocess -- enough to see what broke.
            tail = "\n".join((result.stderr.strip() + "\n" + result.stdout.strip())
                             .strip().splitlines()[-15:])
            return None, f"lỗi (exit {result.returncode}):\n```\n{tail}\n```"

        from PIL import Image
        return Image.open(out).convert("RGBA").copy(), "OK"


def generate(shape: str, top: str, bottom: str, middle_text: str, seed: float):
    middle = [line for line in (middle_text or "").splitlines() if line.strip()]
    seed = int(seed)
    pil_image = _pil_stamp(shape, top, bottom, middle, seed)
    synth_image, note = _synthtiger_stamp(shape, top, bottom, middle, seed)
    return pil_image, synth_image, note


def build_tab() -> None:
    with gr.Tab("Con dấu (synthtiger)"):
        ready, message = _synthdog_ready()
        gr.Markdown(
            "Thử vẽ con dấu bằng synthtiger, cạnh bản PIL sẵn có trong "
            "`tools/make_ornaments.py`. Dấu **vuông** không cần gì synthtiger "
            "thiếu; dấu **tròn** dùng `CurveLayout` uốn theo **parabola**, "
            "không phải một hình tròn thật -- xem lệch rõ nhất ở hai đầu cung."
        )
        if not ready:
            gr.Markdown(f"⚠️ **synthdog chưa sẵn sàng** -- {message}")

        shape = gr.Radio(["square", "round"], value="square", label="Hình dạng")
        with gr.Row():
            top = gr.Textbox(label="Dòng trên (round) / dùng khi Dòng giữa trống (square)",
                             value="CONG TY TNHH VI DU")
            bottom = gr.Textbox(label="Dòng dưới (chỉ round)", value="MST 0123456789")
        middle = gr.Textbox(
            label="Dòng giữa -- mỗi dòng một ô (round: chữ giữa vành; "
                 "square: TOÀN BỘ nội dung con dấu, mỗi dòng một hàng)",
            lines=2, value="DA THU TIEN")
        seed = gr.Number(label="Seed", value=0, precision=0)
        go = gr.Button("Vẽ thử", variant="primary")
        note = gr.Markdown("")
        with gr.Row():
            with gr.Column():
                gr.Markdown("### PIL — đã có (`make_ornaments.py`)")
                pil_out = gr.Image(label="PIL", type="pil")
            with gr.Column():
                gr.Markdown("### synthtiger — thử nghiệm")
                synth_out = gr.Image(label="synthtiger", type="pil")

        go.click(generate, inputs=[shape, top, bottom, middle, seed],
                 outputs=[pil_out, synth_out, note])
