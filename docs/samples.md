# Sample documents


Two documents ship with the package; `python -m vlm_ocr_synthetic list` names
them, and `experiments/build_gallery.py` regenerates the previews below.

### `receipt_vn` — Vietnamese restaurant bill

80mm thermal paper, centred shop block, cash total, thank-you footer, and the
column layout Vietnamese invoices actually use:

| STT | Tên hàng | SL | Đơn giá | Thành tiền |
| --- | -------- | -- | ------- | ---------- |
| 1 | Bún Sinh | 1 | 42,000 | 42,000 |
| 4 | Cơm Bát Bửu | 4 | 43,000 | 172,000 |

Only the item name is free text. `STT` numbers the lines, `Thành tiền` is
`SL x Đơn giá`, and the cash total is the sum — so a generated bill always adds
up, whatever order you feed it. The register line and the cash total are real
two- and three-column tables rather than padded strings, so they land the same
way in both backends (see [the corpus rule](#corpus-rule-content-is-words-layout-is-structure)):

```python
from vlm_ocr_synthetic.samples.receipt_vn import OrderLine, build_receipt_document

document = build_receipt_document(
    order=(OrderLine("Phở Bò", 3, 30_000), OrderLine("Trà Đá", 2, 2_000)),
    table_number=12,
)
```

The text carries full diacritics on purpose: it is the cheapest end-to-end check
that font shaping is not dropping Vietnamese marks, in **both** the Pillow
backend (via raqm) and the browser.

| `synthdog` | `html` | `html`, structure only |
| --- | --- | --- |
| ![receipt rendered by synthdog](../data/samples/receipt_vn-synthdog.jpg) | ![receipt rendered by html](../data/samples/receipt_vn-html.jpg) | ![receipt structure without paper](../data/samples/receipt_vn-html-structure.jpg) |
| `configs/renderers/synthdog_receipt_vn.yaml` | `configs/renderers/html_receipt_vn.yaml` | `--no-paper` |

Receipts needed things the general presets did not have, all added as config or
document structure rather than as special cases in the renderers: `extra_css` on
the html backend (centre the header, drop table borders) and
`center_block_types` / `underline_headers` on synthdog. The column widths and
alignment are **not** in either preset — they are in the document.

### `invoice` — A4 page with a bordered table

| `synthdog` | `html` (flow) | `html` (scanned preset) |
| --- | --- | --- |
| ![invoice by synthdog](../data/samples/invoice-synthdog.jpg) | ![invoice by html](../data/samples/invoice-html-flow.jpg) | ![invoice, degraded](../data/samples/invoice-html-scanned.jpg) |
