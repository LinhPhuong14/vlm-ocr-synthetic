# page_curl20 — 20 trang qua warp Blender thật, `page_curl` bật mặc định

Tập đầu tiên dựng sau khi `rulebase/rules/augmentation.yaml`'s `page_curl` chuyển
từ `enabled: false` sang `enabled: true` — xem `degradation/blender/`. Mục đích
là nhìn qua ảnh thật trước khi bật, không phải một benchmark cố định: 15 bố cục
khác nhau trong 20 trang (một vài lặp lại tự nhiên vì rule-base bốc ngẫu
nhiên, không ép tên).

## Kết quả batch

**20/20 thành công, 0 lỗi.** Mỗi ảnh render bằng một tiến trình `render.py -c 1`
riêng (không phải `-c 20` một lượt), để một lần Blender lỗi không kéo mất cả
mẻ — xem `batch_report.json` cho log thô.

| | |
| --- | ---: |
| Số ảnh | 20 |
| Thành công | 20 |
| Lỗi | 0 |
| Tổng thời gian | 4337.2s (≈ 72 phút 17 giây) |
| Trung bình / ảnh | 216.9s |
| Nhanh nhất | 185.9s |
| Chậm nhất | 245.5s |

Chậm hơn nhiều so với một trang không warp (vài giây): mỗi ảnh ở đây khởi
động lại Chromium (renderer HTML) **và** một tiến trình Blender riêng
(camera dò góc thấy trọn trang, tối đa 4 lần thử nếu góc đầu bị từ chối,
cộng dựng cảnh + render Cycles 96 sample). Chạy trong một tiến trình
`render.py -c N` dài hơi sẽ nhanh hơn (Chromium khởi động một lần), Blender
thì không — mỗi trang vẫn là một lần gọi `blender --background` mới.

## Từng ảnh

| # | seed | layout | trạng thái | thời gian (s) |
| --: | --: | --- | --- | --: |
| 0 | 31000 | authorisation_letter | success | 245.5 |
| 1 | 31001 | insurance_fire_certificate | success | 213.6 |
| 2 | 31002 | form_project_kv | success | 240.3 |
| 3 | 31003 | invoice_hotel_stay | success | 212.7 |
| 4 | 31004 | eatery_indexed | success | 219.8 |
| 5 | 31005 | medical_statement | success | 194.6 |
| 6 | 31006 | newspaper_classifieds | success | 244.7 |
| 7 | 31007 | market_barcode | success | 217.3 |
| 8 | 31008 | insurance_auto_certificate | success | 236.0 |
| 9 | 31009 | insurance_health_certificate | success | 225.3 |
| 10 | 31010 | invoice_tax_en | success | 225.7 |
| 11 | 31011 | newspaper_classifieds | success | 222.8 |
| 12 | 31012 | eatery_indexed | success | 185.9 |
| 13 | 31013 | insurance_travel_certificate | success | 228.0 |
| 14 | 31014 | magazine_qa_interview | success | 207.2 |
| 15 | 31015 | market_compact | success | 191.9 |
| 16 | 31016 | form_timesheet_grid | success | 190.6 |
| 17 | 31017 | eatery_indexed | success | 204.1 |
| 18 | 31018 | form_checkbox_heavy | success | 217.1 |
| 19 | 31019 | eatery_indexed | success | 214.1 |


## Kiểm tra đã chạy

- `pipeline.record.validate()` — 20/20 record đúng schema, không lỗi.
- Mọi góc `quad` của mọi `block` nằm trong khung `[0, width] × [0, height]` —
  20/20 pass.

Chưa chạy `tools/check_boxes.py` (dựng lại từ seed để so khớp pixel — tốn kém
hơn, và bộ này không phải golden baseline nên không bắt buộc).
