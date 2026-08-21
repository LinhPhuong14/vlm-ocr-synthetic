# form-templates — hai biểu mẫu hành chính, dựng tay

Hai file HTML+CSS **độc lập**, mỗi file dựng theo một tệp PDF quét thật. Mở
thẳng bằng trình duyệt, không cần dựng môi trường; hoặc xem file `.jpg` bên
cạnh, chính là bản WeasyPrint in ra.

| file | tờ giấy | khổ | số trang | bố cục nó là tham chiếu |
| --- | --- | --- | --- | --- |
| [`authorisation_letter.html`](authorisation_letter.html) | giấy uỷ quyền nhận tiền, biểu mẫu in sẵn của công ty bảo hiểm nhân thọ | A4 | 1 | `authorisation_letter` |
| [`medical_statement.html`](medical_statement.html) | bảng kê chi phí điều trị nội trú, Mẫu số 01/KBCB | A4 | 3 | `medical_statement` |

Tên file là **id của bố cục** trong
[`rulebase/rules/layout.yaml`](../../rulebase/rules/layout.yaml), giống lệ của
`invoice-templates/`, nên không cần bảng tra.

```bash
make templates       # in lại cả đây lẫn invoice-templates/
```

Hai tờ này khác năm tờ trong [`invoice-templates/`](../invoice-templates) ở một
điểm: chúng **không phải hoá đơn**. Không có bảng hàng tính từ số lượng × đơn
giá, không có dòng thuế. Cái chúng có là *trường điền*, *ô đóng khung*, *ô
tích*, *dải tiêu đề mục*, và — trên tờ bảng kê — một cái bảng 13 cột có tiêu đề
hai tầng mà năm tờ kia không có chỗ nào giống.

Phân tích đo đạc hai bản quét gốc nằm ở
[`docs/phan-tich-2-mau-moi.html`](../../docs/phan-tich-2-mau-moi.html); hai bản
dựng thử đầu tiên nằm ở [`docs/mau/`](../../docs/mau). Hai tờ ở đây là bản
hoàn chỉnh của chúng.

## Đây KHÔNG phải bố cục của rule-base

Giống hệt ghi chú trong `invoice-templates/`: bố cục thật của repo là
[`rulebase/layouts/*.yaml`](../../rulebase/layouts), sinh ra kèm nhãn dữ liệu.
Hai file ở đây là **bản vẽ tham chiếu** — HTML thường, CSS thường, không đụng
tới `rulebase`, không đi qua `generators/html/sheets/`, nên **chưa sinh ra
nhãn**. Chúng trả lời đúng một câu: *tờ giấy thật trông như thế nào?*

## Engine đã dựng theo hai tờ này

Hai bố cục ấy nay đã có thật trong bộ sinh: `sheets/statement.py` dựng tờ uỷ
quyền, `sheets/medical.py` dựng tờ bảng kê, ngữ liệu y tế nằm ở
`rulebase/corpus/vi/catalogue_medical_*.txt`, và bộ ảnh sinh ra kèm nhãn nằm ở
[`data/forms16/`](../../data/forms16).

Nên quan hệ ở đây đúng như quan hệ giữa `invoice-templates/` và
`sheets/statutory.py`: **hai tờ này là hình mẫu, engine là bản tham số hoá**.
Sửa một tờ ở đây không tự động đổi engine — nhưng nếu tờ mẫu và trang engine
sinh ra đã khác nhau thì một trong hai đang sai, và tờ mẫu là bên nói đúng.

```bash
generators/html/render.py -o out -c 1 --template --layout medical_statement
```

## Số trên tờ bảng kê tự cộng đúng

Khoảng năm mươi con số trong bảng không gõ tay mà tính ra, theo đúng mấy ràng
buộc đọc ngược từ bản quét:

```
thành tiền BV   = số lượng × đơn giá BV          (dòng người bệnh tự trả)
thành tiền BH   = số lượng × đơn giá BH          (dòng tính theo thẻ)
quỹ BHYT        = thành tiền BH × mức hưởng      (95% trên tờ này)
cùng chi trả    = thành tiền BH − quỹ BHYT
tự chi trả      = (thành tiền BV − khác) + cùng chi trả
tổng chi phí    = thành tiền BH + thành tiền BV
người bệnh trả  = tự chi trả + khác
```

Nên dòng cộng của từng nhóm, dòng `Cộng:` và khối quyết toán cuối tờ khớp
nhau, và số đọc ra chữ (`Bảy triệu tám trăm tám mươi bảy nghìn một trăm tám
mươi đồng`) khớp với số viết bằng chữ số. Đây đúng loại bất biến mà
[`pipeline/invariants.py`](../../pipeline/invariants.py) canh trên dữ liệu
sinh ra — sửa một con số trong bảng mà không sửa mấy dòng cộng thì tờ mẫu sai,
và nó sai một cách kiểm được.

## Ngắt trang là đặt tay

Bản gốc chạy bảng từ trang 1 sang trang 3 và **không lặp lại tiêu đề bảng**.
WeasyPrint thì mặc định lặp `<thead>`, nên tờ này không để bảng tự ngắt: nó
chia sẵn thành ba `<div class="sheet">`, mỗi trang một `<table>` riêng, dùng
chung một `<colgroup>` để ba đoạn thẳng cột với nhau, và chỉ trang 1 có
`<thead>`.

Cái giá phải trả: **thêm hay bớt một dòng hàng là phải chia lại**. `render.py`
canh đúng chỗ đó — nó bắt số trang phải bằng `EXPECTED_PAGES`, nên một dòng dài
ra đẩy khối quyết toán sang trang thứ tư sẽ báo lỗi chứ không lặng lẽ trôi.

## Con dấu lấy từ `textures/ornament/`

Cả hai tờ đóng dấu bằng chính bộ ảnh mà thuộc tính `ornament` dùng, không phải
bản sao riêng: dấu tên, dấu tròn công ty, dấu vuông `SAO Y BẢN CHÍNH`. Trang 2
xoay dấu 90°, trang 3 xoay 12°, và dấu tròn bệnh viện tràn qua mép phải trang
cuối — cả ba đều là chuyện bản gốc làm. Sinh lại bộ dấu bằng `make ornaments`.

Mã vạch Code 39 dưới chân tờ uỷ quyền (`*POS0142*`) là mã **thật**, vẽ bằng
`<rect>` nội tuyến theo bảng mã 9 vạch, tỷ lệ rộng/hẹp 3:1 — quét được. Mã QR
góc phải tờ bảng kê do `segno` sinh, cùng thư viện mà `qr_svg()` dùng.

## Dữ liệu trên tờ là bịa

Quan trọng, nên nói rõ. Hai bản quét gốc là giấy tờ thật, mang tên người thật,
số CMND, mã thẻ BHYT, chẩn đoán và ngày điều trị thật. **Không giá trị nào
trong hai tờ này lấy từ đó.** Tên công ty bảo hiểm, tên bệnh viện, tên người
bệnh, mọi con số định danh đều tự đặt, theo đúng lệ của
`invoice-templates/README.md` — đây là mẫu để sinh dữ liệu tổng hợp, không
mang dữ liệu thật. Tên miền dùng `.example`, dành riêng cho việc này.

Cái giữ nguyên theo bản gốc là **phần in sẵn**: chữ trên biểu mẫu, thứ tự
trường, cách đánh số `(1)`…`(20)`, tên cột. Mẫu số 01/KBCB là biểu mẫu chuẩn
của Bộ Y tế / BHXH, nên phần in sẵn của nó vốn là văn bản công.

## Chỗ tờ uỷ quyền còn thiếu: nét viết tay

Trên giấy thật, **toàn bộ** giá trị của tờ uỷ quyền là chữ viết tay — họ tên,
số CMND, ngày, địa chỉ, số tiền bằng chữ, bốn chữ ký, tên dưới chữ ký. Phần in
sẵn là hằng số; mọi thứ biến thiên đều viết tay.

Tờ ở đây điền các giá trị ấy bằng chữ *đánh máy nghiêng trên nét kẻ*, để thấy
trường nằm đâu và dài bao nhiêu. Đó là một sự thoả hiệp có ý thức, không phải
một tờ giấy có thật: bộ nét tay cũ đã bị gỡ (commit `ff9a9f0`) vì chất lượng
không đạt, và sinh tờ này hàng loạt với giá trị đánh máy sẽ dạy mô hình đọc
một loại tài liệu không tồn tại. Muốn làm tờ uỷ quyền cho ra hồn thì phải có
nguồn chữ viết tay tiếng Việt tử tế trước — phông viết tay có dấu, hoặc một bộ
mẫu chữ ký quét thật.

Tờ bảng kê không vướng chuyện đó: nó in máy toàn bộ, chỉ có chữ ký là tay.
