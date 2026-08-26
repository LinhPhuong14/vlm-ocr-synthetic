# insurance-templates — mười tờ mẫu, dựng tay

Mười file HTML+CSS **độc lập**, mỗi file dựng cho một loại giấy tờ bảo hiểm
phổ biến ở Việt Nam — từ giấy chứng nhận trách nhiệm dân sự bắt buộc đến hợp
đồng nhân thọ, thẻ BHYT, đơn yêu cầu bảo hiểm. Mở thẳng bằng trình duyệt,
không cần dựng môi trường; hoặc xem file `.jpg` bên cạnh.

| file | tờ giấy | khổ | số trang | LO gốc |
| --- | --- | --- | --- | --- |
| [`insurance_moto_certificate.html`](insurance_moto_certificate.html) | GCN bảo hiểm bắt buộc TNDS — mô tô, xe máy | 148×105mm (≈A6 ngang) | 1 | LO-01 |
| [`insurance_auto_certificate.html`](insurance_auto_certificate.html) | GCN bảo hiểm bắt buộc TNDS — ô tô, dạng bảng 9 dòng | A5 ngang | 1 | LO-02 |
| [`insurance_life_policy_schedule.html`](insurance_life_policy_schedule.html) | Trang hợp đồng bảo hiểm nhân thọ (Policy Schedule) | A4 dọc | 1 | LO-03 |
| [`insurance_application_form.html`](insurance_application_form.html) | Đơn yêu cầu bảo hiểm, ô vuông ghi từng ký tự (comb box) | A4 dọc | 1 | LO-04 |
| [`insurance_health_id_card.html`](insurance_health_id_card.html) | Thẻ bảo hiểm y tế, khổ thẻ ID-1, hai mặt | A4 ngang (hai mặt thẻ cạnh nhau) | 1 | LO-05 |
| [`insurance_health_certificate.html`](insurance_health_certificate.html) | GCN bảo hiểm sức khoẻ, cột trái + thẻ hội viên | A4 dọc | 1 | LO-06 |
| [`insurance_cargo_policy.html`](insurance_cargo_policy.html) | Đơn bảo hiểm hàng hoá vận chuyển, song ngữ Việt/Anh | A4 dọc | 1 | LO-07 |
| [`insurance_fire_certificate.html`](insurance_fire_certificate.html) | GCN bảo hiểm cháy, nổ bắt buộc, bố cục toàn bảng | A4 dọc | 1 | LO-08 |
| [`insurance_travel_certificate.html`](insurance_travel_certificate.html) | GCN bảo hiểm du lịch quốc tế, dạng vé song ngữ | A4 ngang | 1 | LO-09 |
| [`insurance_property_contract.html`](insurance_property_contract.html) | Hợp đồng bảo hiểm tài sản, văn bản hành chính | A4 dọc | 2 (`-p1.jpg`, `-p2.jpg`) | LO-10 |

Tên file **không** phải id của một bố cục có sẵn trong
[`rulebase/rules/layout.yaml`](../../rulebase/rules/layout.yaml) — khác lệ của
`invoice-templates/` và `form-templates/` ở đúng điểm này, xem mục ngay dưới.
Tên được chọn theo đúng quy ước đặt tên của hai thư mục kia (`insurance_` +
hình dạng tờ giấy) để khi có bố cục thật thì dùng lại làm id luôn, không phải
đổi tên.

```bash
make templates       # in lại cả ba: đây, invoice-templates/, form-templates/
```

## Đây KHÔNG phải bố cục của rule-base — và CHƯA có engine

Giống hệt ghi chú trong `invoice-templates/README.md` và
`form-templates/README.md`: mười file ở đây là **bản vẽ tham chiếu**, HTML
thường CSS thường, không đụng gì tới `rulebase`, không đi qua
`generators/html/sheets/`, nên chưa sinh ra nhãn dữ liệu.

Khác hai thư mục kia ở một điểm: `invoice-templates/` và `form-templates/`
mỗi thư mục đều đã có một họ engine dựng theo chúng (`sheets/statutory.py`,
`sheets/lodging.py`, `sheets/modern.py`, `sheets/statement.py`,
`sheets/medical.py`). Mười tờ bảo hiểm ở đây thì **chưa** — đây là bước đọc
và lưu tham chiếu, làm trước bước viết layout/engine thật, đúng thứ tự đã làm
với root 1 (hoá đơn) và root 3 (biểu mẫu): trước khi có `invoice_header_table`
hay `form_questionnaire` cũng có một tờ tham chiếu nằm ở đây trước.

## Hiệu ứng nền chuyển sang augmentation (LO-02, LO-05)

Bản gốc của hai tờ này có hiệu ứng nền dựng bằng CSS thuần: LO-02 (giờ là
`insurance_auto_certificate.html`) có một lưới chéo mô phỏng giấy bảo an cộng
một lớp chữ mờ "BẢN MẪU" giữa trang; LO-05 (`insurance_health_id_card.html`)
có một nền dạng guilloche (chấm toả tròn + gạch chéo + dải màu) phủ mặt thẻ.

Cả hai bị bỏ khỏi bản lưu ở đây. Lý do: đó là hiệu ứng nền — không phải nội
dung tờ giấy, không có field nào đọc ra từ nó — và hiệu ứng dạng "giấy có kết
cấu/hoạ tiết" đã là việc của chuỗi augmentation dùng chung
([`rulebase/rules/augmentation.yaml`](../../rulebase/rules/augmentation.yaml):
`paper_texture`, `gradient_domain`, `real_paper`, ...), áp lên **mọi** layout
khi sinh dữ liệu chứ không phải CSS riêng của một layout. Giữ lại trong bản
tham chiếu sẽ khiến sau này ai đó chép luôn hiệu ứng ấy vào engine như thể nó
là một phần bố cục, trong khi bố cục thật của hai tờ này chỉ là nền trắng
phẳng — `.sheet`/`.card` gốc đã tự có `background:#fff` nên bỏ lớp phủ đi là
đủ, không cần thay gì khác. Xem chú thích ngay tại chỗ bỏ trong từng file.

## Hoạ tiết còn giữ nguyên

Ngoài hai chỗ trên, mọi hoạ tiết trang trí khác của cả mười tờ — con dấu tròn
đỏ xoay nghiêng, mã QR/mã vạch giả, dải màu đầu trang, đường răng cưa kiểu vé
— đều là **nội dung tờ giấy claim có** (một con dấu ai đó đóng lên, một logo
công ty in sẵn), khác hẳn "giấy có kết cấu bảo an" ở trên, nên giữ nguyên
trong CSS của từng layout, không chuyển sang augmentation.

## Tên doanh nghiệp và dữ liệu

Toàn bộ tên doanh nghiệp bảo hiểm ("Minh Hoạ", "Minh Hoa Insurance
Corporation"), tên người ("Nguyễn Văn A", "Trần Thị B"), địa chỉ ("Đường
Mẫu", "Khu công nghiệp Mẫu") và số hiệu (số GCN, số hợp đồng, số thẻ) trên cả
mười tờ đều là **dữ liệu tự đặt** ngay từ bản gốc do người dùng cung cấp —
tên miền dùng `.example`/`example.vn`, đúng lệ của
`invoice-templates/README.md` và `form-templates/README.md`. Không tờ nào
mang tên một doanh nghiệp bảo hiểm hay một cá nhân có thật.
