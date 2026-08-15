# generators/genalog — rendered through Microsoft genalog

[genalog](https://github.com/microsoft/genalog) builds a document by handing a
Jinja2 template to WeasyPrint. That is a genuinely different path from a
browser — a print engine with a page box, real pagination and its own text
shaper — so a model trained on browser screenshots alone has not seen it.

```bash
make setup-genalog
generators/genalog/.venv/bin/python generators/genalog/render.py -o outputs -c 10
```

| flag | |
| --- | --- |
| `-c`, `--count` | how many pages |
| `--seed` | first seed; image *n* uses `seed + n` |
| `--layout` | pin one bố cục |
| `--dpi` | rasterisation density of the PDF (default 150) |

## What is genalog's and what is ours

genalog's own templates are for prose — `text_block`, `columns`, `letter` —
and none of them has a notion of columns measured in characters, which is what
a till roll is. So the template is ours
([`templates/receipt.html.jinja`](templates/receipt.html.jinja)); everything
else is genalog's: `DocumentGenerator` loads it from our template directory,
`Document` compiles it, WeasyPrint paints it.

The `Document` is built straight from genalog's template environment rather
than through `create_generator()`. That helper yields a `Document` already
compiled against genalog's *default prose styles*, which mean nothing to this
template — it fails on the first render, before `update_style()` gets a chance
to supply the real ones.

## Two things genalog being pinned to 2020 forces

* **`Document.render_png()` is unusable.** It calls WeasyPrint's `write_png()`,
  removed in WeasyPrint 53. `render.py` takes `render_pdf()` and rasterises
  with PyMuPDF instead.
* **The pins have no wheels.** genalog requires `numpy==1.18.1`,
  `WeasyPrint==51`, `scikit-image==0.16.2` and `Jinja2==2.11.1`; none has a
  wheel for Python 3.9 or newer. Its source is vendored here rather than
  installed, so the pins never apply, and the
  dependencies come from [`requirements.txt`](requirements.txt) at versions
  that exist. Nothing on the path this repository calls touches the pinned
  APIs — `DocumentGenerator`, `Document` and `render_pdf` only need Jinja2 and
  WeasyPrint, both of which are API-stable for what the template uses.

If you want genalog's own degradations as well, they are in
`genalog.degradation`; this repository uses the DocCreator port in
[`degradation/`](../../degradation/README.md) instead, so that all three
renderers age their pages identically.
