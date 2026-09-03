"""Visualize tool -- a local Gradio app over three of this repo's capabilities.

    python tools/visualize/app.py [--host 127.0.0.1] [--port 7860]

Three tabs, independent of each other:

* **Sinh ảnh** -- drive `pipeline.run.execute()`, watching images land in a
  gallery one at a time instead of waiting for a whole run to finish.
* **Con dấu** -- `tools/make_ornaments.py`'s PIL stamp generator, with colour,
  shape, centre content (star / text / both / none) and a wear/strike-style
  layer all adjustable from the UI. Used to compare against an experimental
  synthtiger renderer, side by side; that comparison is retired (synthtiger
  cannot draw text on a true circular arc -- see git history and
  `docs/co-che-sinh-con-dau.md` for why), and this tab now only drives the
  PIL half that actually ships in `textures/ornament/`.
* **Viết tay (WriteViT)** -- `HybridHand`'s per-word mix (model where it
  can write, font where it can't) on typed-in text -- see
  `tab_handwriting.py` for why this dropped the old BothHands comparison.

Run from `generators/html/.venv` (`make visualize` / `python tasks.py
visualize` do this for you): that venv already has everything the html
renderer needs, which is also everything this tool needs in-process. Tab 3's
WriteViT half is the one exception, crossing a venv boundary on its own via
`tools/writevit/serve.py`, the same way the rest of the pipeline does.

Not this tool's job to install that: the tab says plainly when it is missing
and how to build it (`python tasks.py setup-writevit`).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import gradio as gr  # noqa: E402
import tab_generate  # noqa: E402
import tab_handwriting  # noqa: E402
import tab_stamp  # noqa: E402

TITLE = "vlm-ocr-synthetic -- Visualize"

CSS = """
.gr-group, .gradio-group { border-radius: 12px !important; }
.gradio-accordion { border-radius: 10px !important; }
#title-row { margin-bottom: 0.25em; }
"""


def build() -> gr.Blocks:
    with gr.Blocks(title=TITLE) as demo:
        gr.Markdown(f"# {TITLE}", elem_id="title-row")
        gr.Markdown(
            "Xem nhanh 3 khả năng của repo -- sinh ảnh, con dấu, viết tay -- "
            "không cần chờ cả dataset."
        )
        tab_generate.build_tab()
        tab_stamp.build_tab()
        tab_handwriting.build_tab()
    return demo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    # Gradio 6 moved `theme`/`css` off the `Blocks` constructor and onto
    # `launch()` -- passing them to `Blocks()` still works but warns.
    build().launch(server_name=args.host, server_port=args.port,
                   theme=gr.themes.Soft(), css=CSS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
