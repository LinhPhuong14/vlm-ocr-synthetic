# page_curl20 — 20 trang qua warp Blender thật, `page_curl` bật mặc định

Tập đầu tiên dựng sau khi `rulebase/rules/augmentation.yaml`'s `page_curl` chuyển
từ `enabled: false` sang `enabled: true` — xem `degradation/blender/`. Mục đích
là nhìn qua ảnh thật trước khi bật, không phải một benchmark cố định: 15 bố cục
khác nhau trong 20 trang (một vài lặp lại tự nhiên vì rule-base bốc ngẫu
nhiên, không ép tên).

## Kết quả batch

**20/20 thành công, 0 lỗi.** Dựng lại cùng 20 seed sau hai đổi: crop ảnh về
đúng khung trang (thay vì giữ nguyên canvas 1024×1440 cố định) và giảm
Cycles 96→48 sample / mô phỏng vật lý 250→100 khung hình — xem
`degradation/blender/vendor/config.py` và mục "Trang quá nhỏ, render quá
chậm" bên dưới. Mỗi ảnh vẫn render bằng một tiến trình `render.py -c 1`
riêng, để một lần Blender lỗi không kéo mất cả mẻ — xem `batch_report.json`
cho log thô.

| | |
| --- | ---: |
| Số ảnh | 20 |
| Thành công | 20 |
| Lỗi | 0 |
| Tổng thời gian | 1939.0s (≈ 32 phút 19 giây) |
| Trung bình / ảnh | 96.9s |
| Nhanh nhất | 89.6s |
| Chậm nhất | 103.9s |

Chậm hơn nhiều so với một trang không warp (vài giây): mỗi ảnh ở đây khởi
động lại Chromium (renderer HTML) **và** một tiến trình Blender riêng
(camera dò góc thấy trọn trang, tối đa 6 lần thử với mesh dựng lại mỗi lần
nếu góc đầu bị từ chối, cộng dựng cảnh + render Cycles 48 sample). Chạy
trong một tiến trình `render.py -c N` dài hơi sẽ nhanh hơn (Chromium khởi
động một lần), Blender thì không — mỗi trang vẫn là một lần gọi
`blender --background` mới.

## Trang quá nhỏ, render quá chậm — hai điều đã sửa

Bản dựng đầu (bảng cũ: trung bình 216.9s/ảnh) luôn render vào canvas cố định
1024×1440, đủ rộng cho camera ở xa nhất mà vẫn thấy trọn trang — nên phần lớn
ảnh là một trang nhỏ giữa nền lớn. Bản dựng lại này crop về đúng khung trang
sau render (`_page_bounding_box` trong `degradation/blender/render.py`, biên
4%), và giảm sample/khung hình mô phỏng để bù lại phần thời gian crop thêm.
Diện tích ảnh giờ chỉ còn ≈24% so với canvas cố định cũ, ở cùng kích thước
trang thật.

## Từng ảnh

| # | seed | layout | trạng thái | thời gian (s) | kích thước |
| --: | --: | --- | --- | --: | --: |
| 0 | 31000 | authorisation_letter | success | 93.5 | 492×715 |
| 1 | 31001 | insurance_fire_certificate | success | 97.7 | 543×675 |
| 2 | 31002 | form_project_kv | success | 102.9 | 522×728 |
| 3 | 31003 | invoice_hotel_stay | success | 97.0 | 478×749 |
| 4 | 31004 | eatery_indexed | success | 93.9 | 503×802 |
| 5 | 31005 | medical_statement | success | 91.8 | 432×764 |
| 6 | 31006 | newspaper_classifieds | success | 102.0 | 552×740 |
| 7 | 31007 | market_barcode | success | 98.1 | 431×810 |
| 8 | 31008 | insurance_auto_certificate | success | 102.4 | 674×556 |
| 9 | 31009 | insurance_health_certificate | success | 103.9 | 516×687 |
| 10 | 31010 | invoice_tax_en | success | 95.9 | 552×720 |
| 11 | 31011 | newspaper_classifieds | success | 101.2 | 468×719 |
| 12 | 31012 | eatery_indexed | success | 92.5 | 388×774 |
| 13 | 31013 | insurance_travel_certificate | success | 99.5 | 654×577 |
| 14 | 31014 | magazine_qa_interview | success | 95.2 | 467×742 |
| 15 | 31015 | market_compact | success | 96.6 | 398×810 |
| 16 | 31016 | form_timesheet_grid | success | 90.7 | 462×737 |
| 17 | 31017 | eatery_indexed | success | 89.6 | 405×795 |
| 18 | 31018 | form_checkbox_heavy | success | 95.3 | 511×713 |
| 19 | 31019 | eatery_indexed | success | 99.3 | 409×759 |


## Kiểm tra đã chạy

- `pipeline.record.validate()` — 20/20 record đúng schema, không lỗi.
- Mọi góc `quad` của mọi `block` nằm trong khung `[0, width] × [0, height]` —
  20/20 pass.

Chưa chạy `tools/check_boxes.py` (dựng lại từ seed để so khớp pixel — tốn kém
hơn, và bộ này không phải golden baseline nên không bắt buộc).
