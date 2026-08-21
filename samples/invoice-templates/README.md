# invoice-templates — năm tờ mẫu, dựng tay

Năm file HTML+CSS **độc lập**, mỗi file dựng theo một ảnh chụp hoá đơn thật.
Mở thẳng bằng trình duyệt, không cần dựng môi trường; hoặc xem file `.jpg` bên
cạnh, chính là bản WeasyPrint in ra.

| file | tờ giấy | khổ | bố cục nó là tham chiếu |
| --- | --- | --- | --- |
| [`invoice_vat_summary.html`](invoice_vat_summary.html) | hoá đơn GTGT, bản thể hiện của hoá đơn điện tử | A4 | `invoice_vat_summary` |
| [`invoice_export.html`](invoice_export.html) | hoá đơn xuất khẩu song ngữ | A4 | `invoice_export` |
| [`invoice_hotel_stay.html`](invoice_hotel_stay.html) | hoá đơn khu nghỉ dưỡng | A4 | `invoice_hotel_stay` |
| [`invoice_hotel_compact.html`](invoice_hotel_compact.html) | hoá đơn khách sạn nhỏ | A5 | `invoice_hotel_compact` |
| [`invoice_brand.html`](invoice_brand.html) | hoá đơn tiệm bánh | A5 | `invoice_brand` |

Tên file là **id của bố cục** trong
[`rulebase/rules/layout.yaml`](../../rulebase/rules/layout.yaml), nên không cần
bảng tra: tờ nào là tham chiếu cho bố cục nào thì tên nói thẳng.

```bash
make templates       # in lại: out/*.pdf và *.jpg
```

## Engine dựng theo năm tờ này

Từ khi `generators/html/sheets/` ra đời, năm tờ ở đây không chỉ là tranh minh
hoạ nữa: chúng là **hình mẫu** mà engine tham số hoá. `sheets/statutory.py` dựng
theo hai tờ đầu, `sheets/lodging.py` theo hai tờ khách sạn, `sheets/modern.py`
theo tờ tiệm bánh. Sửa một tờ ở đây không tự động đổi engine — nhưng nếu tờ mẫu
và trang engine sinh ra đã khác nhau thì một trong hai đang sai, và tờ mẫu là
bên nói đúng.

```bash
generators/html/render.py -o out -c 1 --template --layout invoice_vat_summary
```

## Đây KHÔNG phải bố cục của rule-base

Chỗ dễ nhầm nhất, nên nói trước. Bố cục thật của repo là
[`rulebase/layouts/*.yaml`](../../rulebase/layouts): lưới ký tự, ba renderer
cùng đọc, sinh ra kèm nhãn dữ liệu. Năm file ở đây là **bản vẽ tham chiếu** —
HTML thường, CSS thường, không đụng gì tới `rulebase`.

Chúng có mặt để trả lời một câu mà file YAML không trả lời được: *tờ giấy thật
trông như thế nào?* Dòng `source:` trong mỗi file bố cục ghi tên tấm ảnh nó
được đo từ đó; những tấm ảnh ấy không phát hành lại được, còn năm tờ này thì
được.

## Hoạ tiết

`invoice_hotel_compact.html` là tờ duy nhất có màu nhận diện và hoạ tiết, và nó
lấy hoạ tiết từ [`textures/ornament/`](../../textures/ornament) — cùng bộ file
mà thuộc tính `ornament` dùng, chứ không phải một bản sao riêng. Sinh lại bằng
`make ornaments`.

## Tên doanh nghiệp

Tên trên tờ GTGT và tờ xuất khẩu là **tên tự đặt**, không phải hai thương hiệu
trong ảnh gốc: đây là mẫu để sinh dữ liệu tổng hợp, không nên mang tên công ty
thật. Ba tờ còn lại giữ nguyên dữ liệu giả vốn có của bản gốc — bản thân chúng
đã là mẫu trống ("Đường ABC, Thành phố DEF", "demowebsite.site").
