"""Visualize tool -- a local Gradio app over three of this repo's capabilities.

    python tools/visualize/app.py [--host 127.0.0.1] [--port 7860]

Three tabs, independent of each other:

* **Sinh ảnh** -- drive `pipeline.run.execute()`, watching images land in a
  gallery one at a time instead of waiting for a whole run to finish.
* **Con dấu (synthtiger)** -- an experimental stamp generator built on
  synthtiger, shown beside `tools/make_ornaments.py`'s existing PIL one.
* **Viết tay (hybrid)** -- `BothHands` (production, per-field) next to
  `HybridHand` (new, per-word) on the same input text.

Run from `generators/html/.venv` (`make visualize` / `python tasks.py
visualize` do this for you): that venv already has everything the html
renderer needs, which is also everything this tool needs in-process. The two
exceptions cross a venv boundary on their own, the same way the rest of the
pipeline does -- `tools/writevit/serve.py` for the WriteViT half of Tab 3, and
`generators/synthdog/.venv` as a subprocess for Tab 2's actual rendering.

Not this tool's job to install any of that; each tab says plainly when its
half of the machinery is missing and how to build it.
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


def build() -> gr.Blocks:
    with gr.Blocks(title=TITLE) as demo:
        gr.Markdown(f"# {TITLE}")
        tab_generate.build_tab()
        tab_stamp.build_tab()
        tab_handwriting.build_tab()
    return demo


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=7860)
    args = parser.parse_args()

    build().launch(server_name=args.host, server_port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
