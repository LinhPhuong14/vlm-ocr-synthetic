# generators/genalog — the print path

WeasyPrint lays a Jinja2 template out as a PDF and PyMuPDF rasterises it. That
is a genuinely different way to put ink on a page from Chromium's screenshot or
synthdog's glyph compositing, which is the reason this backend exists.

| file | whose | what it does |
| --- | --- | --- |
| `render.py` | ours | the backend: rule-base grid → template variables → PDF → JPEG + `metadata.jsonl` |
| `templates/receipt.html.jinja` | ours | a receipt layout measured in characters; genalog's own templates are for prose |
| `requirements.txt` | ours | what the venv needs, and why each pin is there |
| `genalog/` | vendored | [microsoft/genalog](https://github.com/microsoft/genalog), MIT — see `LICENSE` |

## Why genalog is vendored rather than installed

`genalog` is deliberately **not** in `requirements.txt`. Its source sits in this
directory and `render.py` runs from here, so `generators/genalog/` is
`sys.path[0]` and the vendored tree wins over any installed copy. Installing the
package as well would leave two of them with one silently shadowing the other.

Vendoring also side-steps genalog's pins — numpy 1.18.1, WeasyPrint 51,
scikit-image 0.16.2, none of which has a wheel for Python 3.9+ — because nothing
on the path this repository calls touches those APIs.

## What was kept of it

`render.py` imports exactly one module:

```python
from genalog.generation.document import Document, DocumentGenerator
```

so `genalog/generation/` is what is vendored, plus the empty `genalog/__init__.py`
that makes it a package. The upstream subpackages were removed as unused here:

| removed | what it was | why it is not needed |
| --- | --- | --- |
| `genalog/ocr/` | Azure Read API clients | this repository reads images with Tesseract, in `tools/ocr_proof.py` |
| `genalog/text/` | CoNLL/NER alignment | labels come from the rule-base, already aligned |
| `genalog/degradation/` | genalog's ageing models | superseded by [`src/degradation/`](../../src/degradation), which ports DocCreator's |
| `genalog/pipeline.py` | upstream's own runner | superseded by [`src/pipeline/`](../../src/pipeline) |
| `docs/`, `example/`, `tests/`, `devops/`, packaging meta | upstream project scaffolding | genalog is never built or released from here |

`genalog/generation/templates/` is kept even though `render.py` passes its own
`template_path` and never loads them: they are the fallback
`DocumentGenerator()` uses when given no path, and removing them would leave
`document.py` referring to templates that are not there.

To re-vendor a newer genalog, copy its `genalog/generation/` over this one and
re-read `render.py`'s notes on `render_png()` — WeasyPrint removed the call that
upstream's `Document.render_png()` still makes, which is why this backend
rasterises the PDF itself.
