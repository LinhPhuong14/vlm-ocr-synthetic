# Contributing

## Getting set up

```bash
make setup     # venv, dependencies, chromium, then `doctor`
make test      # everything
make test-fast # everything that does not render, sub-second
make lint      # ruff check + format --check
make format    # fix what can be fixed
```

`make setup` ends with `python -m vlm_ocr_synthetic doctor`, which prints the
interpreter, the dependency floors, and whether each backend is usable. Start
there when something does not work.

## Where things live

The tests mirror the package, so a change and its test are a directory apart:

| you are changing | source | tests |
| --- | --- | --- |
| the document model | `vlm_ocr_synthetic/schemas/` | `tests/schemas/` |
| shared text, the plain-text rule | `vlm_ocr_synthetic/corpus/` | `tests/corpus/` |
| a sample document | `vlm_ocr_synthetic/samples/` | `tests/samples/` |
| a backend, or the paper layer | `vlm_ocr_synthetic/renderers/` | `tests/renderers/` |
| layouts, styles, degradations | `vlm_ocr_synthetic/variations/` | `tests/variations/` |
| dataset generation | `vlm_ocr_synthetic/dataset/` | `tests/dataset/` |
| the benchmark | `vlm_ocr_synthetic/evaluation/` | `tests/evaluation/` |
| the CLI | `vlm_ocr_synthetic/cli/` | `tests/test_cli.py` |

Adding a layout, style or degradation is usually a few lines in
`variations/` — see [docs/datasets.md](docs/datasets.md#adding-your-own-attributes-and-resources).

## Rules that are enforced, not just documented

These have tests behind them; breaking one fails the suite rather than
producing subtly wrong data:

- **Every backend satisfies the same contract** — image size, a bbox for every
  block and cell, non-overlapping cells in a row, deterministic output
  (`tests/renderers/test_contract.py`). A new backend inherits the suite.
- **Content never encodes layout** — no padding spaces, no tabs
  (`tests/corpus/`). Alignment belongs on the table.
- **The paper stage changes pixels, never annotations** (`tests/renderers/test_paper.py`).
- **The synthdog backend never imports pygame, synthtiger or imgaug**
  (`tests/test_compat.py`), which is what keeps it installable on 3.14.
- **A mistyped config key or variant weight raises** rather than silently
  doing nothing.

## Tests

Mark anything that renders with `@pytest.mark.slow` so `make test-fast` stays
fast. A test that needs a backend should skip with a reason when it is missing,
never pass silently:

```python
from helpers import requires_renderer


@requires_renderer("html")
@pytest.mark.slow
def test_something(): ...
```

## Style

`ruff` for both linting and formatting; the configuration is in
`pyproject.toml` and CI checks it. Line length is 90.

Comments should explain *why*, and are worth writing when the reason is not
obvious from the code — a measured constant, a workaround for a real
incompatibility, an invariant someone might otherwise break.

## CI

`.github/workflows/ci.yml` runs lint, `doctor`, and the full suite on Python
3.10, 3.12 and 3.14 — the ends of the supported range matter, because the
dependency floors in `compat.py` differ between them.

## Generated files

Everything generated lands in `data/` and is git-ignored, except the JPEG
previews in `data/samples/` and the benchmark report. Regenerate them with
`make gallery` and `make benchmark` if a change alters how pages look.
