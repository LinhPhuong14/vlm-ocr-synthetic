# Contributing

This repository holds three independent generators. There is no shared package
and no shared virtualenv: pick the one you are working on.

| working on | environment | notes |
| --- | --- | --- |
| `synthdog/` | `make setup` (or its README) | Python 3.8 – 3.12 only |
| `html-table/` | `pip install -r html-table/requirements.txt` | vendored; prefer upstreaming fixes |
| `genalog/` | upstream repo | a submodule, do not edit in place |

```bash
git submodule update --init   # genalog has no content until you do this
make check                    # every tracked .py parses, no dependencies needed
make lint                     # ruff, on this repo's own scripts
```

## The version cap is real

`synthdog/requirements.txt` pins `pillow<10`, `numpy<2` and `opencv-python<5`,
and each pin exists because removing it breaks something specific — the file
says which. Python 3.13+ cannot satisfy them at all;
[`docs/python-314.md`](docs/python-314.md) has the measurements. If you are on a
newer interpreter, create the 3.12 environment rather than relaxing a pin.

Also worth knowing while debugging templates: **synthtiger swallows exceptions
and retries forever**, so a broken template hangs silently. Always pass `-v`.

## Style

`ruff` for linting, configured in `pyproject.toml`. It checks correctness and
imports, not formatting: most of the Python here is adapted from upstream and
reformatting it would only make future merges harder. Vendored code
(`html-table/`, `genalog/`) is excluded entirely.

`target-version` is `py38` because that is what `synthdog/` supports —
so ruff will not suggest `zip(strict=)` or other 3.10+ syntax that would break
it.

## Generated output

Everything a generator writes goes under its own directory (`synthdog/outputs/`)
and is git-ignored. Do not commit generated images.
