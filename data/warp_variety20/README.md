# warp_variety20 — 20 trang, 5 kiểu biến dạng bề mặt khác nhau

Bổ sung cho [`page_curl20/`](../page_curl20) (bộ đó chỉ dùng `page_curl`): tập
này trộn đều **5 kịch bản warp** trong `degradation/blender/meshes.py`, 4 ảnh
mỗi kịch bản, cố ý CHỈ chọn biến dạng bề mặt thuần — không dùng nhóm
"thả rơi xuống vật cản" của SyntheticDoc (`fall_on_roller`, `fall_on_roof`
chưa port; `lifted_corner`/`fall_on_ball` vẫn giữ lại vì gần với "góc giấy
cong lên" hơn là "va vào vật gì đó").

| kịch bản | tương ứng scenario SyntheticDoc | dáng |
| --- | --- | --- |
| `page_curl` | `curve_by_pull` | cuộn đều một phía |
| `folded` (`fold_crease`) | `fold_by_pull` | một nếp gấp cứng |
| `lifted_corner` (`corner_bulge`) | `fall_on_ball` | một góc phồng lên |
| `crease_bundle` | — (mới, lấy cảm hứng `fall_on_many`) | 2-4 nếp gấp cắt chéo nhau |
| `crumple` | — (mới, xấp xỉ phẳng của `fall_on_many`) | nhàu rải rác nhiều vết nhỏ |

## Kết quả batch

**20/20 thành công, 0 lỗi.** Ảnh #0 khôi phục từ một lần chạy trước bị lỗi
thư mục output chưa kịp tạo (crash ở đúng bước copy file, không phải ở
render) — ảnh vẫn hợp lệ, chỉ không đo được thời gian riêng. 19 ảnh còn lại
chạy tiếp từ chỗ dừng, mỗi ảnh vẫn là một tiến trình `render.py -c 1` riêng.

| | |
| --- | ---: |
| Số ảnh | 20 |
| Thành công | 20 |
| Lỗi | 0 |
| Tổng thời gian (19 ảnh đo được) | 3349.4s (≈ 55 phút 49 giây) |
| Trung bình / ảnh | 176.3s |
| Nhanh nhất | 97.6s |
| Chậm nhất | 197.2s |

Nhanh hơn `page_curl20/` một chút (176s vs 217s trung bình) dù cùng cơ chế —
chênh lệch nằm trong biên độ tự nhiên giữa các lần chạy (khởi động Chromium +
Blender mỗi ảnh), không phải do kịch bản nào nhanh hơn hẳn kịch bản khác.

## Một lỗi thật bắt được khi chuẩn bị bộ này

`crease_bundle` từng làm một góc nhãn nhảy tới toạ độ (-1868, 7181) trên ảnh
1024×1440 — bản đồ UV nghịch đảo ngoại suy sai tại một góc bị nếp gấp che
khuất hoàn toàn. Đã sửa ở hai chỗ trong `degradation/blender/`:

1. `sample_renderer.py` từng `raise` lại sau khi ghi lỗi vào metadata, nên
   `main()` không bao giờ in JSON ra stdout khi có lỗi — vòng lặp thử lại của
   `render.py` không đọc được lý do lỗi và bỏ cuộc ngay từ lần đầu, bất kể
   cấu hình bao nhiêu lần thử.
2. `apply_warp()` giờ kiểm tra mọi toạ độ hộp nhãn sau khi warp có nằm trong
   biên hợp lý không, thay vì tin thẳng kết quả nội suy.

Xem commit sửa lỗi trong lịch sử `degradation/blender/` để biết chi tiết.

## Từng ảnh

| # | kịch bản | seed | layout | trạng thái | thời gian (s) |
| --: | --- | --: | --- | --- | --: |
| 0 | page_curl | 42000 | — | success | — (không đo, ảnh khôi phục từ lần chạy bị lỗi thư mục) |
| 1 | page_curl | 42001 | newspaper_front_broadsheet | success | 175.1 |
| 2 | page_curl | 42002 | insurance_life_schedule | success | 186.4 |
| 3 | page_curl | 42003 | newspaper_classifieds | success | 183.8 |
| 4 | folded | 42004 | eatery_ascii | success | 180.8 |
| 5 | folded | 42005 | invoice_brand | success | 197.2 |
| 6 | folded | 42006 | eatery_indexed_b | success | 168.9 |
| 7 | folded | 42007 | form_multi_section | success | 173.7 |
| 8 | lifted_corner | 42008 | insurance_travel_certificate | success | 188.7 |
| 9 | lifted_corner | 42009 | invoice_vat_summary | success | 184.1 |
| 10 | lifted_corner | 42010 | invoice_power | success | 176.9 |
| 11 | lifted_corner | 42011 | invoice_power | success | 186.1 |
| 12 | crease_bundle | 42012 | authorisation_letter | success | 97.6 |
| 13 | crease_bundle | 42013 | insurance_cargo_policy | success | 161.9 |
| 14 | crease_bundle | 42014 | form_two_column | success | 158.9 |
| 15 | crease_bundle | 42015 | insurance_life_schedule | success | 191.8 |
| 16 | crumple | 42016 | invoice_hotel_stay | success | 180.2 |
| 17 | crumple | 42017 | insurance_fire_certificate | success | 190.8 |
| 18 | crumple | 42018 | insurance_health_certificate | success | 182.7 |
| 19 | crumple | 42019 | eatery_indexed | success | 183.8 |


## Kiểm tra đã chạy

- `pipeline.record.validate()` — 20/20 record đúng schema, không lỗi.
- Mọi góc `quad` của mọi `block` nằm trong khung `[0, width] × [0, height]` —
  20/20 pass (bao gồm cả trường hợp lỗi ở trên, đã bị chặn từ trước khi tới
  record nhờ bản vá thứ hai).
