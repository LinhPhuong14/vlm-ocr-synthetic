# invoices54 — chín bố cục hoá đơn thương mại, dựng bằng engine CSS

54 ảnh: **9 bố cục × 3 ảnh × 2 renderer**. Đây là bộ đầu tiên đi qua
[`generators/html/sheets/`](../../generators/html/sheets) thay vì lưới ký tự —
trang được dựng bằng `<table>` thật, `colspan` thật, đơn vị `mm`, `@page`, theo
đúng hình mẫu của năm tờ vẽ tay trong
[`samples/invoice-templates/`](../../samples/invoice-templates).

| | |
| --- | --- |
| bố cục | 9 hoá đơn thương mại (khổ A4/A5), **không có** 5 bố cục giấy cuộn |
| renderer | `html` (Chromium) và `genalog` (WeasyPrint) — hai engine duy nhất in được tờ CSS |
| ghép cặp | `paired`: `html_007.jpg` và `genalog_007.jpg` là **cùng một hoá đơn**, in hai cách |
| làm cũ | có, rút từ luật như thường lệ — 13 chuỗi khác nhau xuất hiện trong 27 ảnh |
| nhãn | `blocks` như mọi bộ khác, **cộng thêm** `structure` trong `synthesis.json` — chuỗi token PPStructure của bảng |

`dataset.json` ghi `"template": "auto"`. Đó là chỗ đọc để biết bộ này dựng bằng
mô hình trang nào; bộ nào không có khoá ấy là lưới ký tự.

## Sinh lại

```bash
python tools/generate_dataset.py -o data/invoices54 -n 27 \
    --frameworks html genalog --template --workers 2 \
    --layouts invoice_vat_form invoice_vat_summary invoice_export \
              invoice_water invoice_power invoice_hotel_stay \
              invoice_hotel_compact invoice_tax_en invoice_brand
```

Danh sách bố cục viết thẳng ra chứ không để trống, vì hạn ngạch đi theo thứ tự
của danh sách: một lệnh không nêu tên sẽ vẽ bộ khác đi vào ngày ai đó thêm một
bố cục. `--frameworks` cũng vậy — renderer glyph ghép từng chữ lên canvas, không
vẽ được đường kẻ bảng, nên một lần chạy có `--template` mà kèm `synthdog` bị
**từ chối** ở `pipeline/config.py` chứ không lặng lẽ trộn hai mô hình trang.

## Đã kiểm những gì

| phép đo | kết quả |
| --- | --- |
| `pipeline/invariants.py` | **0** lỗi / 54 ảnh, 4 400 box |
| `generators/html/overlap.py` | **0** cặp box chữ chồng nhau >30%, cả hai renderer |
| `make check-boxes DATASET=data/invoices54` | mọi đoạn chữ có nhãn đều có box, box nào cũng nằm trên nét mực |
| nhãn của cặp ảnh cùng chỉ số | giống nhau 27/27 — `paired` đúng là paired |

## Có một chỗ NÊN biết trước khi dùng

`invoice_hotel_compact` là tờ duy nhất có **băng màu và chữ in ngược** (chữ
trắng trên nền xanh cổ vịt). Các mô hình làm cũ trong
[`degradation/`](../../degradation) được dựng từ DocCreator, và DocCreator đo
trên bản chép tay: **mực sẫm trên giấy sáng**. Trên một dải màu đặc, `stains`
(`gradient_domain`) và `ink_degradation` để lại đốm sáng lệch màu chứ không ra
vết bẩn — xem `genalog_019.jpg`. Ảnh vẫn đúng nhãn và box vẫn đúng chỗ; chỉ là
vệt bẩn trông không giống vệt bẩn.

Đây là hành vi sẵn có của `degradation/`, không phải của engine mới; nó chỉ mới
*nhìn thấy được* vì đây là những trang đầu tiên có mảng màu lớn. Cần bộ sạch để
so thì:

```bash
python tools/generate_dataset.py -o data/invoices54_clean -n 27 \
    --frameworks html genalog --template --clean --layouts ...
```

Cùng lý do ấy, `tools/check_boxes.py` đã phải sửa: phép thử "có mực dưới box
không" trước đây chỉ tìm chỗ **tối hơn** nền, nên nó báo 15/61 box của tờ khách
sạn nằm trên giấy trắng — trong khi từng box một đều nằm gọn trên một chữ. Giờ
nó nhận tương phản theo cả hai chiều.

## Cấu trúc

```
invoices54/
├── dataset.json        số ảnh mỗi renderer, chia theo bố cục, và `template`
├── html/
│   ├── html_000.jpg …  27 ảnh
│   └── metadata.jsonl  một dòng một ảnh
└── genalog/            27 ảnh, cùng 27 hoá đơn ấy
```

`plan.json`, `manifest.json` và `timings.json` là trạng thái làm việc của lần
chạy, `.gitignore` bỏ chúng như với mọi bộ khác — seed của từng ảnh nằm trong
`seed` trong `synthesis.json` của chính trang ấy, nên dựng lại một ảnh không cần
tới chúng.

Một dòng `metadata.jsonl` như mọi bộ khác:

```json
{"schema_version": 8,
 "task": "convert",
 "parser": "html",
 "filename": "html_004.jpg",
 "blocks": [{"label": "Table", "kind": "menu.name", "text": "...",
             "bbox": {"x1": 0, "y1": 0, "x2": 0, "y2": 0}, "quad": [[x,y], ...]}],
 "extracted": {...}}
```

...còn `synthesis.json` bên cạnh có thêm `cells` và `structure` so với các bộ cũ:

```json
"html_004.jpg": {
  "job_id": "...", "seed": 4026, "layout": "invoice_vat_form",
  "attributes": {...}, "tags": [...], "text_sequence": "...",
  "cells": [{"kind": "menu.name", "row": 4, "col": 1, "colspan": 1, "rowspan": 1, "quad": [...]}],
  "structure": ["<tr>", "<td", " colspan=\"7\"", ">", "</td>", "<td>", "</td>", "</tr>"]}
```

`blocks` là chữ, `cells` + `structure` là bảng. Hai nửa ấy tả cùng một trang:
ghép chữ của các ô vào giữa chuỗi token thì dựng lại được bảng. `cells` chỉ có ở
renderer `html` — Chromium đo được ô từ DOM đã dàn xong, còn WeasyPrint chỉ có
lớp ký tự của PDF, nên bên ấy `structure` đọc thẳng từ markup đã in.
