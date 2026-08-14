# samples — ví dụ đã chọn sẵn

Xem được ngay, không cần dựng môi trường.

| thư mục | nội dung |
| --- | --- |
| [`degradation/`](degradation) | mỗi model làm cũ áp riêng lẻ lên **cùng một trang giấy**, kèm ảnh ghép |

Sinh lại: `make showcase`.

Bộ dữ liệu đầy đủ 60 ảnh — ba renderer, năm bố cục, kèm nhãn và điểm OCR — nằm ở
[`data/dataset60/`](../data/dataset60), không phải ở đây.

## degradation/

`showcase-before.jpg` là trang gốc; mỗi `showcase-<tên>.jpg` là trang đó sau khi
áp **một** model. `showcase-contact.jpg` ghép tất cả lại để so sánh nhanh, và
`showcase.json` ghi tham số đã dùng.

Áp từng model riêng chính là điểm của bộ này: dán texture giấy, ghép vết bẩn
bằng Poisson blending, và dán mực thừa vào rìa chữ trông hoàn toàn khác nhau —
chạy cả chuỗi thì không phân biệt được cái nào gây ra cái gì.

Tham số ở đây chọn để **nhìn thấy rõ**, không phải để giống thật. Tham số dùng
thật nằm trong [`rulebase/rules/augmentation.yaml`](../rulebase/rules/augmentation.yaml).
