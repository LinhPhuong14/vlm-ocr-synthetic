"""A small LLM-agent test run, restricted to documents with a real item table.

    python tools/agent_dataset_tables.py -o data/tables_llm_test -n 30

This is `tools/agent_dataset.py` with two defaults changed and one flag
forced on: `--layouts-with-table`, so the plan only ever draws a layout whose
file lays out a real item table (see `agent_dataset.table_layout_ids` -- read
off `rulebase/layouts/*.yaml` at run time, not a list kept here); and a
test-sized `--out`/`--count` instead of the 5000-image production default,
since the point of this script is checking that the table techniques
(`table.header_style`, `table.header_groups`, `cellstyle: hatch_zero` /
`heatmap`) come out of the LLM-driven planner and renderer intact, not
producing a shippable dataset. Every other flag `agent_dataset.py` takes --
`--workers`, `--content-llm`, `--clean`, `--feedback`, and the rest -- still
works; pass it through same as always.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _extra in (REPO_ROOT, REPO_ROOT / "tools"):
    if str(_extra) not in sys.path:
        sys.path.insert(0, str(_extra))

import agent_dataset  # noqa: E402

DEFAULT_OUT = REPO_ROOT / "data" / "tables_llm_test"
DEFAULT_COUNT = "30"


def main() -> int:
    argv = list(sys.argv[1:])
    if not any(flag in argv for flag in ("-o", "--out")):
        argv = ["-o", str(DEFAULT_OUT), *argv]
    if not any(flag in argv for flag in ("-n", "--count")):
        argv = ["-n", DEFAULT_COUNT, *argv]
    if "--layouts-with-table" not in argv:
        argv = [*argv, "--layouts-with-table"]
    sys.argv = [sys.argv[0], *argv]
    return agent_dataset.main()


if __name__ == "__main__":
    os.environ.setdefault("PYTHONWARNINGS", "ignore")
    raise SystemExit(main())
