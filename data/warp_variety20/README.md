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

**20/20 thành công, 0 lỗi.** Dựng lại cùng 20 seed sau khi crop ảnh về đúng
khung trang và giảm sample Cycles/khung hình mô phỏng — cùng đổi đã áp cho
`page_curl20/`, xem README ở đó cho chi tiết cơ chế crop. Mỗi ảnh vẫn là một
tiến trình `render.py -c 1` riêng (bản dựng đầu từng crash ở bước copy file
của ảnh #0 vì thư mục output chưa kịp tạo; lần này chạy trọn từ đầu, không
còn ảnh nào thiếu thời gian đo).

| | |
| --- | ---: |
| Số ảnh | 20 |
| Thành công | 20 |
| Lỗi | 0 |
| Tổng thời gian | 2007.7s (≈ 33 phút 28 giây) |
| Trung bình / ảnh | 100.4s |
| Nhanh nhất | 67.7s |
| Chậm nhất | 109.2s |

Cùng tốc độ với `page_curl20/` (100.4s vs 96.9s trung bình) — chênh lệch nằm
trong biên độ tự nhiên giữa các lần chạy, không phải do kịch bản nào nhanh
hơn hẳn kịch bản khác. Ngoại lệ là seed 42012 (`crease_bundle`, 67.7s): nếp
gấp che gần hết trang nên vùng crop cuối cùng rất nhỏ (155×213) — vẫn đọc
được, chỉ ít pixel để render hơn.

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

| # | kịch bản | seed | layout | trạng thái | thời gian (s) | kích thước |
| --: | --- | --: | --- | --- | --: | --: |
| 0 | page_curl | 42000 | invoice_hotel_compact | success | 93.7 | 422×763 |
| 1 | page_curl | 42001 | newspaper_front_broadsheet | success | 101.3 | 532×759 |
| 2 | page_curl | 42002 | insurance_life_schedule | success | 100.8 | 518×692 |
| 3 | page_curl | 42003 | newspaper_classifieds | success | 100.1 | 481×728 |
| 4 | folded | 42004 | eatery_ascii | success | 97.2 | 427×786 |
| 5 | folded | 42005 | invoice_brand | success | 108.0 | 465×751 |
| 6 | folded | 42006 | eatery_indexed_b | success | 97.4 | 381×786 |
| 7 | folded | 42007 | form_multi_section | success | 104.2 | 499×713 |
| 8 | lifted_corner | 42008 | insurance_travel_certificate | success | 107.6 | 733×485 |
| 9 | lifted_corner | 42009 | invoice_vat_summary | success | 103.4 | 488×703 |
| 10 | lifted_corner | 42010 | invoice_power | success | 100.9 | 513×738 |
| 11 | lifted_corner | 42011 | invoice_power | success | 99.2 | 507×723 |
| 12 | crease_bundle | 42012 | authorisation_letter | success | 67.7 | 155×213 |
| 13 | crease_bundle | 42013 | insurance_cargo_policy | success | 97.6 | 341×475 |
| 14 | crease_bundle | 42014 | form_two_column | success | 99.5 | 343×488 |
| 15 | crease_bundle | 42015 | insurance_life_schedule | success | 106.6 | 577×745 |
| 16 | crumple | 42016 | invoice_hotel_stay | success | 104.7 | 572×765 |
| 17 | crumple | 42017 | insurance_fire_certificate | success | 109.2 | 505×730 |
| 18 | crumple | 42018 | insurance_health_certificate | success | 108.4 | 585×713 |
| 19 | crumple | 42019 | eatery_indexed | success | 100.2 | 440×738 |


## Kiểm tra đã chạy

- `pipeline.record.validate()` — 20/20 record đúng schema, không lỗi.
- Mọi góc `quad` của mọi `block` nằm trong khung `[0, width] × [0, height]` —
  20/20 pass (bao gồm cả trường hợp lỗi ở trên, đã bị chặn từ trước khi tới
  record nhờ bản vá thứ hai).
