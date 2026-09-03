# Báo cáo phản biện

Bộ dữ liệu: `/home/user/vlm-ocr-synthetic/data/5k_llm` — 250 trang

| | trang | tỉ lệ |
|---|---:|---:|
| sạch | 208 | 83.2% |
| lỗi nhẹ | 39 | 15.6% |
| lỗi nặng | 3 | 1.2% |

## Lỗi theo loại

| mã | mức | soi ở | số lần | nghĩa |
|---|---|---|---:|---|
| `cham_box` | nhẹ | record | 17 | con dấu chạm vào một trường có nhãn — đúng như dấu thật, chữ vẫn đọc được qua nét dấu |
| `lap_noi_dung` | nhẹ | record | 17 | một chuỗi lặp lại nhiều lần trong cùng một loại trường |
| `chu_nhat_mau` | nhẹ | ảnh giấy | 11 | chữ quá nhạt so với nền ngay trong ô của nó |
| `chu_nho` | nhẹ | record | 3 | dòng chữ thấp dưới ngưỡng pixel, OCR không đọc nổi |
| `khong_muc` | nặng | ảnh giấy | 2 | chỗ có nhãn nhưng trên giấy không có mực |
| `che_box` | nặng | record | 1 | con dấu/QR đóng lên một trường có nhãn và xoá mất chữ |

## Giá trị nào hay hỏng

`lift` là tỉ lệ hỏng của giá trị đó chia cho tỉ lệ hỏng chung của cả lượt. `lift = 1` nghĩa là vô can; ở đây liệt kê những giá trị từ 2.0 trở lên.

| thuộc tính | giá trị | vẽ | hỏng | tỉ lệ | lift | mã lỗi |
|---|---|---:|---:|---:|---:|---|
| color | `mono_black` | 80 | 3 | 4% | 3.1 | khong_muc×2, che_box×1 |
| handwriting | `hand_both` | 71 | 2 | 3% | 2.4 | khong_muc×2 |

## Cặp không nên đi cùng nhau

Không có cặp nào hỏng đủ đều để cấm.

## Ví dụ

Mỗi mã lỗi một trang, để mở ra xem tận mắt.

- `khong_muc` — `html_005.jpg`: 2 trường có nhãn nhưng không có mực: invoice.field
- `chu_nhat_mau` — `html_005.jpg`: 1 trường chữ nhạt, nhạt nhất invoice.field chênh 41/255 giữa chỗ đậm nhất và chỗ nhạt nhất trong ô
- `cham_box` — `html_006.jpg`: seal_round_company_faint đóng ở signature_seller trùm 11% lên sign.title, mất 0% chữ
- `chu_nho` — `html_007.jpg`: 31 trường thấp dưới 10px, thấp nhất teaser.kicker 9.0px
- `lap_noi_dung` — `html_015.jpg`: menu.name: 'Tiền phòng Studio' lặp 3 lần
- `che_box` — `html_143.jpg`: barcode_ean13_sample đóng ở footer_band trùm 46% lên footer, mất 15% chữ

## Phản hồi vào pipeline

Những hệ số này được ghi vào `feedback.json`; `tools/agent_dataset.py --feedback` đọc lại và nhân vào trọng số khi chọn, nên lượt sau tự tránh.

- `color=mono_black` × 0.16 ████████████████████████····
- `handwriting=hand_both` × 0.213 ██████████████████████······
