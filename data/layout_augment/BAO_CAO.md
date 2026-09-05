# Thư viện dựng lại bố cục

52 phôi, 306 bản dựng lại, mỗi bản kèm ảnh proof có tag từng box.

| | |
|---|---:|
| số phôi | 52 |
| bản dựng lại | 306 |
| đo được | 306 |
| trung bình khác phôi | 76.4% |
| đạt ngưỡng ≥70% | 212/306 (69%) |

## Đọc con số ấy thế nào

Vẽ cùng một trang hai lần — một lần phôi trần, một lần mặc bản dựng lại — rồi đếm tỉ lệ ô chữ có nhãn đã đổi chỗ, **sau khi trừ đi độ dịch chung của cả trang**. Trừ độ dịch chung là điểm mấu chốt: nới lề đẩy cả trang xuống 15mm thì vẫn là trang cũ nằm thấp hơn, không phải bố cục mới. Chi tiết trong `agent/distance.py`.

## Chính sách trong thư mục này khác lúc chạy thật

Lúc chạy thật, `agent/policy.yaml` **cấm** dựng lại bố cục của giấy tờ do pháp luật quy định, và điều đó không đổi. Ở đây thì cho phép — 2 bản, và chỉ lấy từ những thiết kế đánh dấu `graphic` — vì câu hỏi của thư mục này là *nếu dựng lại thì trông thế nào*, mà muốn trả lời thì phải vẽ ra.

| phôi | chứng từ | hạng | số bản | khác phôi (thấp – cao) |
|---|---|---|---:|---|
| `eatery_indexed` | `pub_eatery` | free · cuộn | 7 | 66% – 100% |
| `eatery_indexed_b` | `pub_eatery` | free · cuộn | 7 | 66% – 100% |
| `eatery_ascii` | `pub_eatery` | free · cuộn | 7 | 56% – 100% |
| `market_barcode` | `supermarket` | free · cuộn | 7 | 71% – 100% |
| `market_compact` | `convenience_store` | free · cuộn | 7 | 50% – 100% |
| `notebook_ledger` | `convenience_store` | free · cuộn | 7 | 31% – 100% |
| `market_vat` | `supermarket_vat` | free · cuộn | 7 | 70% – 100% |
| `invoice_vat_form` | `vat_invoice_form` | locked | 2 | 95% – 100% |
| `invoice_vat_summary` | `retail_vat_invoice` | free | 3 | 31% – 92% |
| `invoice_export` | `export_invoice` | livery | 7 | 47% – 97% |
| `invoice_water` | `utility_water` | livery | 7 | 51% – 100% |
| `invoice_power` | `utility_power` | livery | 7 | 61% – 95% |
| `invoice_hotel_stay` | `hotel_stay` | free | 7 | 43% – 98% |
| `invoice_hotel_compact` | `hotel_stay` | free | 6 | 85% – 100% |
| `invoice_tax_en` | `tax_invoice_en` | livery | 7 | 58% – 100% |
| `invoice_brand` | `bakery_order` | free | 7 | 58% – 100% |
| `invoice_header_table` | `invoice_detailed` | free | 6 | 60% – 96% |
| `invoice_logo_split` | `invoice_detailed` | free | 7 | 44% – 100% |
| `invoice_logo_center` | `invoice_plain` | free | 7 | 17% – 95% |
| `invoice_two_column` | `invoice_detailed` | free | 7 | 43% – 100% |
| `invoice_sidebar` | `invoice_detailed` | free | 7 | 71% – 97% |
| `invoice_keyvalue` | `invoice_detailed` | free | 7 | 44% – 100% |
| `invoice_dense_table` | `invoice_plain` | free | 7 | 31% – 95% |
| `invoice_minimalist` | `invoice_plain` | free | 7 | 17% – 92% |
| `invoice_multipage` | `invoice_plain` | free | 7 | 17% – 95% |
| `invoice_remittance` | `invoice_detailed` | free | 7 | 44% – 100% |
| `medical_statement` | `hospital_bill` | locked | 2 | 99% – 99% |
| `authorisation_letter` | `authorisation_letter` | livery | 7 | 18% – 68% |
| `form_questionnaire` | `form_brief` | free | 7 | 67% – 100% |
| `form_timesheet_grid` | `form_roster` | livery | 7 | 22% – 100% |
| `form_project_kv` | `form_brief` | free | 7 | 67% – 100% |
| `form_two_column` | `form_symmetric` | locked | 2 | 59% – 83% |
| `form_multi_section` | `form_sectioned` | free | 7 | 62% – 100% |
| `form_checkbox_heavy` | `form_checklist` | free | 7 | 70% – 100% |
| `form_activity_signature` | `form_activity` | locked | 2 | 75% – 92% |
| `form_table_based` | `form_checklist_table` | free | 4 | 74% – 100% |
| `form_government_app` | `form_dense` | locked | 2 | 59% – 66% |
| `form_dense_registration` | `form_dense` | locked | 2 | 59% – 71% |
| `newspaper_front_broadsheet` | `newspaper_front_broadsheet` | free | 7 | 69% – 100% |
| `newspaper_classifieds` | `newspaper_classifieds` | free | 7 | 6% – 96% |
| `magazine_contents` | `magazine_contents` | free | 7 | 6% – 93% |
| `magazine_qa_interview` | `magazine_qa_interview` | free | 7 | 97% – 100% |
| `insurance_moto_certificate` | `insurance_moto_certificate` | locked · thẻ ngang | 1 | 54% – 54% |
| `insurance_auto_certificate` | `insurance_auto_certificate` | locked · thẻ ngang | 2 | 95% – 100% |
| `insurance_life_schedule` | `insurance_life_schedule` | livery | 7 | 70% – 100% |
| `insurance_application_form` | `insurance_application_form` | free | 7 | 44% – 52% |
| `insurance_health_id_card` | `insurance_health_id_card` | locked · thẻ ngang | 2 | 37% – 62% |
| `insurance_health_certificate` | `insurance_health_certificate` | livery | 7 | 34% – 100% |
| `insurance_cargo_policy` | `insurance_cargo_policy` | livery | 7 | 6% – 78% |
| `insurance_fire_certificate` | `insurance_fire_certificate` | livery | 7 | 58% – 100% |
| `insurance_travel_certificate` | `insurance_travel_certificate` | livery · thẻ ngang | 4 | 57% – 95% |
| `insurance_property_contract` | `insurance_property_contract` | free | 7 | 49% – 100% |

## Những bản vẽ ra rồi bỏ

46 bản. Một thiết kế bị bỏ khi bộ phản biện bắt lỗi nặng trên trang nó vẽ ra, hoặc khi đo được dưới 5% — tức là CSS của nó không với tới họ giấy ấy. Thiết kế kế tiếp trong danh sách được lấy thay, tối đa 3 lần.

| phôi | thiết kế | lý do |
|---|---|---|
| `invoice_vat_summary` | `cot_nhan_dien_trai` | 6 lỗi nặng (tran_le) |
| `invoice_vat_summary` | `bang_dan_dau` | 1 lỗi nặng (tran_le) |
| `invoice_vat_summary` | `dan_bao_chi` | 1 lỗi nặng (tran_le) |
| `invoice_vat_summary` | `so_cai_khong_vien` | 1 lỗi nặng (tran_le) |
| `invoice_vat_summary` | `bang_ron_toi` | 1 lỗi nặng (tran_le) |
| `invoice_vat_summary` | `cot_giua_hep` | 7 lỗi nặng (tran_le) |
| `invoice_vat_summary` | `bac_thang_phai` | 2 lỗi nặng (tran_le) |
| `invoice_export` | `cot_nhan_dien_trai` | 2 lỗi nặng (tran_le) |
| `invoice_export` | `bang_ron_toi` | 1 lỗi nặng (khong_muc) |
| `invoice_export` | `cot_giua_hep` | 3 lỗi nặng (tran_le) |
| `invoice_hotel_compact` | `dan_bao_chi` | 1 lỗi nặng (khong_muc) |
| `invoice_hotel_compact` | `so_cai_khong_vien` | 1 lỗi nặng (khong_muc) |
| `invoice_hotel_compact` | `bang_ron_toi` | 1 lỗi nặng (khong_muc) |
| `invoice_hotel_compact` | `cot_giua_hep` | 5 lỗi nặng (tran_le) |
| `invoice_header_table` | `bang_dan_dau` | 11 lỗi nặng (tran_le) |
| `invoice_header_table` | `so_cai_khong_vien` | 11 lỗi nặng (tran_le) |
| `invoice_header_table` | `cot_giua_hep` | 17 lỗi nặng (tran_le) |
| `invoice_header_table` | `bac_thang_phai` | 22 lỗi nặng (tran_le) |
| `invoice_two_column` | `hai_cot_so_le` | 3 lỗi nặng (tran_le) |
| `invoice_two_column` | `cot_giua_hep` | 7 lỗi nặng (tran_le) |
| `invoice_sidebar` | `hai_cot_so_le` | 1 lỗi nặng (chong_lan) |
| `invoice_sidebar` | `bang_ron_toi` | 1 lỗi nặng (khong_muc) |
| `form_activity_signature` | `bang_thanh_the` | 6 lỗi nặng (tran_le) |
| `form_table_based` | `bang_thanh_the` | 12 lỗi nặng (tran_le) |
| `form_table_based` | `hai_cot_so_le` | 18 lỗi nặng (tran_le) |
| `form_table_based` | `so_cai_khong_vien` | 6 lỗi nặng (tran_le) |
| `form_table_based` | `cot_giua_hep` | 6 lỗi nặng (tran_le) |
| `form_table_based` | `bac_thang_phai` | 6 lỗi nặng (tran_le) |
| `form_table_based` | `phieu_dong_dau_lon` | 6 lỗi nặng (tran_le) |
| `newspaper_classifieds` | `bang_ron_toi` | 2 lỗi nặng (khong_muc) |
| `magazine_qa_interview` | `hai_cot_so_le` | 5 lỗi nặng (tran_le) |
| `magazine_qa_interview` | `bang_ron_toi` | 1 lỗi nặng (khong_muc) |
| `magazine_qa_interview` | `cot_giua_hep` | 8 lỗi nặng (tran_le) |
| `insurance_moto_certificate` | `the_hai_mang` | 3 lỗi nặng (tran_le) |
| `insurance_moto_certificate` | `the_nen_chat` | không đổi gì (0.0%) |
| `insurance_moto_certificate` | `the_chia_hai_cot` | không đổi gì (0.0%) |
| `insurance_moto_certificate` | `the_lech_phai` | 1 lỗi nặng (tran_le) |
| `insurance_auto_certificate` | `the_nen_chat` | không đổi gì (0.0%) |
| `insurance_life_schedule` | `bang_thanh_the` | 1 lỗi nặng (khong_muc) |
| `insurance_life_schedule` | `hai_cot_so_le` | 1 lỗi nặng (tran_le) |

## Bộ phản biện soi lại thư viện này

`agent/critic.py` chạy trên chính những trang vừa vẽ. Thư viện là chỗ một thiết kế được nhìn thấy lần đầu, nên cũng phải là chỗ lỗi của nó bị bắt — chứ không phải một thư mục chỉ khoe cái đẹp rồi để thiết kế hỏng đi thẳng vào lượt 5000 trang.

| mã | mức | số lần | nghĩa |
|---|---|---:|---|
| `lap_noi_dung` | nhẹ | 32 | một chuỗi lặp lại nhiều lần trong cùng một loại trường |
| `chu_nho` | nhẹ | 26 | dòng chữ thấp dưới ngưỡng pixel, OCR không đọc nổi |
| `chu_nhat_mau` | nhẹ | 25 | chữ quá nhạt so với nền ngay trong ô của nó |

## Bản dựng lại nào được dùng ở đâu

| thiết kế | kiểu | dùng cho | số lần |
|---|---|---|---:|
| `cot_nhan_dien_trai` | graphic | khổ rộng | 38 |
| `bang_thanh_the` | graphic | khổ rộng | 38 |
| `hai_cot_so_le` | thường | khổ rộng | 30 |
| `bang_dan_dau` | thường | khổ rộng | 33 |
| `dan_bao_chi` | graphic | khổ rộng | 34 |
| `so_cai_khong_vien` | thường | khổ rộng | 31 |
| `bang_ron_toi` | graphic | khổ rộng | 27 |
| `cot_giua_hep` | thường | khổ rộng | 5 |
| `bac_thang_phai` | thường | khổ rộng | 6 |
| `phieu_dong_dau_lon` | thường | khổ rộng | 6 |
| `cuon_hai_dong_moi_mon` | thường | cuộn giấy nhiệt | 7 |
| `cuon_dau_lech_trai` | thường | cuộn giấy nhiệt | 7 |
| `cuon_khung_kep` | thường | cuộn giấy nhiệt | 7 |
| `cuon_thua_dong` | thường | cuộn giấy nhiệt | 7 |
| `cuon_bang_ron_toi` | graphic | cuộn giấy nhiệt | 7 |
| `cuon_treo_dong` | thường | cuộn giấy nhiệt | 7 |
| `cuon_nen_chat` | thường | cuộn giấy nhiệt | 7 |
| `the_hai_mang` | graphic | thẻ ngang | 3 |
| `the_chia_hai_cot` | graphic | thẻ ngang | 2 |
| `the_lech_phai` | thường | thẻ ngang | 2 |
| `the_dai_ngang` | thường | thẻ ngang | 2 |
