<!-- Sinh tự động bởi agent/guideline.py ngày 2026-09-03 từ /home/user/vlm-ocr-synthetic/data/5k_llm. Đừng sửa tay: chạy lại `tools/critic_review.py --guideline` sau mỗi lần đổi rules. -->

# Máy này sinh ra cái gì

Ảnh chứng từ Việt Nam có nhãn: hoá đơn GTGT, phiếu tính tiền quán ăn, hoá đơn điện nước, giấy khai sinh, giấy chứng nhận bảo hiểm, báo, tạp chí, sổ tay. Mỗi ảnh đi kèm một record JSON ghi từng ô chữ: `kind` (trường gì), `text` (chữ gì), `quad` (nằm ở đâu). Bộ dữ liệu này dùng để huấn luyện OCR và trích xuất trường, nên **cái nhãn phải đúng với cái ảnh** — đó là ràng buộc trên tất cả.

## Một trang được quyết bằng gì

| thuộc tính | số giá trị | nghĩa |
|---|---:|---|
| `document` | 41 | loại giấy tờ — quyết định nội dung, và quyết định luôn được phép dựng lại hay không |
| `layout` | 52 | phôi: khung HTML gốc của trang, thuộc một trong 10 họ giấy |
| `variant` | 49 | bộ áo: CSS chồng lên phôi. `none` là mặc phôi trần |
| `content` | 12 | ngôn ngữ, dấu tiếng Việt, hoa/thường, đơn vị tiền |
| `visual` | 7 | loại máy in và loại giấy |
| `color` | 5 | hệ màu mực |
| `ornament` | 21 | dấu, QR, mã vạch, hoa văn nền, chữ ký |
| `augmentation` | 23 | tờ giấy đã đi qua những gì: photocopy, chụp lệch, ố, gấp |

Rút theo đúng thứ tự trên. Giá trị rút trước gắn tag lên trang, và tag quyết định giá trị nào còn hợp lệ ở bước sau — nên `document` và `layout` là hai quyết định lớn nhất, phần còn lại chảy theo.

## Ba hạng giấy tờ

### `locked` — 8 loại

Phôi do cơ quan nhà nước ban hành, có mẫu số và ký hiệu quy định. Dáng tờ giấy là một phần của tính hợp lệ, nên chỉ đóng dấu chứ không dựng lại.

`form_activity`, `form_dense`, `form_symmetric`, `hospital_bill`, `insurance_auto_certificate`, `insurance_health_id_card`, `insurance_moto_certificate`, `vat_invoice_form`

### `livery` — 11 loại

Bố cục do ngành hoặc bên phát hành quy định — số cột, thứ tự khối, nhãn song ngữ đều cố định — nhưng mực, nền và nét kẻ thì mỗi đợt in một khác. Đổi màu thì được, đổi hình thì không.

`authorisation_letter`, `export_invoice`, `form_roster`, `insurance_cargo_policy`, `insurance_fire_certificate`, `insurance_health_certificate`, `insurance_life_schedule`, `insurance_travel_certificate`, `tax_invoice_en`, `utility_power`, `utility_water`

### `free` — 22 loại

Chứng từ thương mại và giấy tính tiền: mỗi quán, mỗi siêu thị, mỗi khách sạn tự thiết kế. Đa dạng dáng ở đây là đúng với đời thật, không phải là bịa.

`bakery_order`, `convenience_store`, `form_brief`, `form_checklist`, `form_checklist_table`, `form_sectioned`, `hotel_stay`, `insurance_application_form`, `insurance_property_contract`, `invoice_detailed`, `invoice_plain`, `magazine_contents`, `magazine_qa_interview`, `newspaper_classifieds`, `newspaper_front_broadsheet`, `pub_eatery`, `resort_stay`, `restaurant_vat`, `retail_vat_invoice`, `street_eatery`, `supermarket`, `supermarket_vat`

## Bộ áo (`variant`) được dựng ra sao

Hai nguồn. **Trục** — 8 trục độc lập (`stock`, `rule`, `band`, `zebra`, `type`, `density`, `mark`, `structure`), tổ hợp lại cho 648 bộ áo hạng livery và 622,080 bộ áo hạng free. Rẻ và rộng, nhưng mỗi bộ vẫn là *cùng một trang sơn khác màu*.

**Kiến trúc** — 22 bản vẽ tay trong `agent/redesign.py`, mỗi bản là một cách dựng trang khác hẳn: cột nhận diện dọc bên trái, sổ cái không đường viền, băng-rôn tối chữ đảo màu, bảng thang bậc lệch phải. Đây mới là thứ làm bố cục khác đi thật.

Khác bao nhiêu thì có đo, không nói miệng: `agent/distance.py` vẽ cùng một trang hai lần — một lần `variant=none`, một lần mặc bộ áo — rồi đếm tỉ lệ ô chữ đã dời chỗ **sau khi trừ đi độ dịch chung của cả trang**. Trừ độ dịch chung là điểm mấu chốt: nới lề đẩy cả trang xuống 15 mm thì đó vẫn là trang cũ nằm thấp hơn, không phải bố cục mới.

8 trong số đó được đánh dấu `graphic`: chúng đủ tính thiết kế để một giấy tờ hạng `locked` cũng mặc được mà vẫn ra dáng ấn phẩm chính thức — `cot_nhan_dien_trai`, `bang_thanh_the`, `dan_bao_chi`, `bang_ron_toi`, `cuon_bang_ron_toi`, `the_hai_mang`, `the_nen_chat`, `the_chia_hai_cot`.

## Cái gì bộ áo không được đụng vào

`generators/html/sheets/variant.py::forbidden` chặn hai thứ, và chặn vì cùng một lý do: nhãn được đo từ DOM sau khi CSS chạy, nên CSS nào **đổi chữ** sẽ làm nhãn nói dối.

- `text-transform` — chữ hiện lên là HOA còn nhãn ghi thường.
- `content:` có chữ trong đó — thêm chữ không ai gán nhãn.

`content:''` rỗng thì được: đó là cách bật một pseudo-element trang trí, và nó không thêm chữ nào.

## Chữ viết tay

`hand_both` là giá trị chính: WriteViT viết được chữ nào thì viết, phần nó không viết được (chữ số, chữ hoa, dấu câu) mới rơi về font. `hand_font` bị tắt bằng `enabled: false` — dùng font ngay từ đầu thì trang ghi nhãn 'viết tay' mà pixel là chữ in, tức là nhãn sai.

## Dấu và QR

`generators/html/ornament.py` đóng dấu **trước** khi làm cũ tờ giấy, vì ngoài đời cũng vậy. Chỗ đóng do `clearest()` tìm: nó dò ba vòng — quanh mỏ neo, dải ngang cùng độ cao, rồi cả tờ — và lấy **vòng đầu tiên có chỗ trống hẳn**. Không có ngưỡng 'chồng bao nhiêu thì chấp nhận': ngưỡng ấy từng là 15% và gần như không bao giờ kích hoạt, nên QR vẫn đè lên tiêu đề.

Ngoại lệ là `page_full` và `page_center` — mỏ neo của con dấu chìm BẢN SAO, vốn *phải* vắt ngang chữ. Chúng khai trong `OVERPRINT_ANCHORS` và bộ phản biện bỏ qua.

## Hai cách một giá trị bị tắt

- `weight: 0` — tắt vì lỡ tay, chưa ai quyết.
- `enabled: false` — tắt có chủ ý, và `degradation.SWITCHED_OFF` khai tên nó ra. `ink_degradation` (hiệu ứng đốm trên giấy nhiệt) nằm ở đây; `tools/rules_report.py --check` bắt cả hai chiều, nên khai mà không tắt hay tắt mà không khai đều gãy.

Bộ chọn đọc **cả hai**. Một bộ chọn chỉ nhìn `weight` sẽ vẽ `torn_edges` và `punched`, tức là đục lỗ qua những trang mà nhãn khẳng định là còn nguyên chữ.

## Lượt chạy gần nhất nói gì

`/home/user/vlm-ocr-synthetic/data/5k_llm` — 250 trang, 3 trang có lỗi nặng (1.2%).

- `cham_box` (nhẹ) ×17 — con dấu chạm vào một trường có nhãn — đúng như dấu thật, chữ vẫn đọc được qua nét dấu
- `lap_noi_dung` (nhẹ) ×17 — một chuỗi lặp lại nhiều lần trong cùng một loại trường
- `chu_nhat_mau` (nhẹ) ×11 — chữ quá nhạt so với nền ngay trong ô của nó
- `chu_nho` (nhẹ) ×3 — dòng chữ thấp dưới ngưỡng pixel, OCR không đọc nổi
- `khong_muc` (nặng) ×2 — chỗ có nhãn nhưng trên giấy không có mực
- `che_box` (nặng) ×1 — con dấu/QR đóng lên một trường có nhãn và xoá mất chữ
