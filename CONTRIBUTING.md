# Contributing

This repository holds two independent generators. There is no shared package
and no shared virtualenv: pick the one you are working on.

| working on | environment | notes |
| --- | --- | --- |
| `generators/synthdog/` | `make setup` | Python 3.8 – 3.11 only |
| `generators/html-table/` | `pip install -r generators/html-table/requirements.txt` | vendored; prefer upstreaming fixes |

Each generator is run **from its own directory** — the paths in their configs
are relative to it. That is also why resources live under the generator that
needs them rather than in one shared folder.

```bash
make check                    # every tracked .py parses, no dependencies needed
make lint                     # ruff, on this repo's own scripts
```

## The version cap is real

`generators/synthdog/requirements.txt` pins `pillow<10`, `numpy<2` and `opencv-python<5`,
and each pin exists because removing it breaks something specific — the file
says which. Python 3.13+ cannot satisfy them at all;
[`docs/python-versions.md`](docs/python-versions.md) has the measurements. If you are on a
newer interpreter, create the 3.12 environment rather than relaxing a pin.

Also worth knowing while debugging templates: **synthtiger swallows exceptions
and retries forever**, so a broken template hangs silently. Always pass `-v`.

## Style

`ruff` for linting, configured in `pyproject.toml`. It checks correctness and
imports, not formatting: most of the Python here is adapted from upstream and
reformatting it would only make future merges harder. Vendored code
(`generators/html-table/`) is excluded entirely.

`target-version` is `py38` because that is what `synthdog/` supports —
so ruff will not suggest `zip(strict=)` or other 3.10+ syntax that would break
it.

## Generated output

Everything a generator writes goes under its own directory (`generators/synthdog/outputs/`)
and is git-ignored. Do not commit generated images.
