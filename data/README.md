# data — bộ dữ liệu đã sinh

| bộ | ảnh | mô tả |
| --- | ---: | --- |
| [`dataset60/`](dataset60) | 60 | 20 ảnh mỗi renderer, trải đều 5 bố cục, kèm nhãn và kết quả OCR |

Sinh lại:

```bash
make dataset                 # DATASET=data/dataset60 N=20
make proof                   # đọc lại bằng Tesseract và chấm điểm
```

Bộ này **được commit vào git**. Điểm chính của repo là mở ra xem được ngay mà
không cần dựng ba môi trường trước — nên ảnh, nhãn và báo cáo OCR đều nằm trong
repo. Còn mọi thứ renderer tự ghi ra `outputs/` thì không.

## Cấu trúc

```
dataset60/
├── dataset.json            số ảnh mỗi renderer, phân bổ theo bố cục
├── synthdog/
│   ├── synthdog_000.jpg …  20 ảnh
│   └── metadata.jsonl      một dòng một ảnh
├── html/       …
├── genalog/    …
└── proof/
    ├── README.md           bảng điểm OCR
    ├── ocr_report.json     điểm từng ảnh + các trường đọc sai nhiều nhất
    └── proof_*.jpg         ảnh gốc kèm khung từng từ Tesseract đọc được
```

## Một dòng `metadata.jsonl`

```json
{
  "file_name": "synthdog_000.jpg",
  "framework": "synthdog",
  "layout": "quan_nhau_stt",
  "ground_truth": "{\"gt_parse\": {…}}",
  "text_sequence": "QUÁN NHẬU SEN VÀNG 251 235 Phan Xích Long …",
  "recipe": {"seed": 2026, "attributes": {…}, "tags": […]},
  "boxes": [{"kind": "menu.nm", "text": "…", "quad": [[x,y],…]}]
}
```

| trường | |
| --- | --- |
| `ground_truth` | nhãn lồng nhau kiểu CORD, dạng chuỗi JSON (Donut đọc trực tiếp) |
| `text_sequence` | nhãn đọc-trơn, dùng cho pre-training và cho việc chấm OCR |
| `recipe` | **đầy đủ** 6 thuộc tính đã bốc, kèm seed — dựng lại ảnh y hệt được |
| `boxes` | toạ độ polygon từng ô, vẫn đúng sau khi tờ giấy đã bị làm cong. Chỉ renderer glyph có |

`recipe.seed` là thứ làm cho bộ dữ liệu tái lập được: `rulebase.make(seed=n)` cho
lại đúng nội dung đó, và mỗi renderer vẽ lại đúng ảnh đó.
