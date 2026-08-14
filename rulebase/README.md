# rulebase — luật sinh dùng chung cho cả ba renderer

Mọi thứ về **nội dung** một trang giấy tổng hợp nằm ở đây. Mọi thứ về **cách vẽ
nó ra pixel** nằm ở `generators/`. Ba renderer đều bắt đầu bằng đúng ba dòng:

```python
recipe  = rulebase.sample_recipe(seed=7)          # bốc một điểm trong không gian luật
receipt = rulebase.build_receipt(recipe)          # điền nội dung vào các trường
grid    = rulebase.build_grid(receipt, recipe.layout.id)   # xếp thành lưới ô
```

hoặc gọn hơn: `recipe, receipt, grid = rulebase.make(seed=7)`.

Cùng một seed thì ra cùng một chữ ở cùng một cột, dù vẽ bằng glyph, bằng
Chromium hay bằng WeasyPrint. Đó là điều kiện để so sánh ba renderer với nhau
có ý nghĩa — nếu mỗi renderer tự sinh nội dung thì cái được so là hai bộ dữ
liệu khác nhau, không phải hai cách vẽ.

```
rulebase/
├── rules/          6 THUỘC TÍNH, mỗi file một thuộc tính  ← chỗ chỉnh phân phối
├── layouts/        5 BỐ CỤC đo từ ảnh hoá đơn thật        ← chỗ thêm bố cục mới
├── corpus/vi/      ngữ liệu tiếng Việt CÓ DẤU             ← chỗ thêm mặt hàng
├── spec.py         bốc mẫu theo trọng số + ràng buộc
├── content.py      điền nội dung + sinh nhãn
├── layout.py       nội dung + bố cục -> lưới ô
└── text.py         bỏ dấu, định dạng tiền, ngắt dòng
```

---

## 1. Sáu thuộc tính

Bốc theo đúng thứ tự này. Mỗi thuộc tính nhìn thấy `tags` mà các thuộc tính
trước đã gắn vào, nên thuộc tính sau tự loại mình ra nếu không hợp.

| # | thuộc tính | quyết định | file |
| --- | --- | --- | --- |
| 1 | `document` | loại document: quán nhậu, siêu thị, hoá đơn GTGT… | [rules/document.yaml](rules/document.yaml) |
| 2 | `layout` | bố cục: cột nào, mỗi mặt hàng mấy dòng | [rules/layout.yaml](rules/layout.yaml) |
| 3 | `content` | nội dung: có dấu / không dấu, IN HOA, kiểu tiền, có VAT | [rules/content.yaml](rules/content.yaml) |
| 4 | `visual` | hình thức: font, cỡ chữ, độ đậm mực, tờ giấy, độ cong | [rules/visual.yaml](rules/visual.yaml) |
| 5 | `color` | màu: mực, ám giấy, màu nhấn cho tên cửa hàng | [rules/color.yaml](rules/color.yaml) |
| 6 | `augmentation` | làm cũ: chuỗi degradation chạy sau khi render | [rules/augmentation.yaml](rules/augmentation.yaml) |

Thứ tự này không tuỳ tiện — nó theo đúng thứ tự thực tế: cửa hàng chọn in cái
gì từ rất lâu trước khi tờ giấy quyết định nó sẽ bị nhàu ra sao. Vì thế
`document` là lựa chọn rộng nhất còn `augmentation` hẹp nhất.

### Cấu trúc một giá trị

```yaml
- id: sieu_thi_lon        # bắt buộc, duy nhất trong file
  weight: 3               # tần suất tương đối; 0 = không bao giờ bốc trúng
  tags: [doc_sieuthi, has_barcode]   # thẻ để các thuộc tính sau nhìn thấy
  requires: [doc_sieuthi]            # chỉ bốc được nếu recipe ĐÃ có các thẻ này
  excludes: [ascii_only]             # không bốc được nếu recipe ĐÃ có thẻ nào ở đây
  params:                            # đi thẳng vào code, không qua xử lý nào
    profile: sieuthi
    num_items: [3, 12]
```

`requires` / `excludes` là thứ chặn những tổ hợp vô lý. Không có nó, sampler sẽ
sinh ra hoá đơn quán nhậu có cột mã vạch trống, hoặc máy in nhiệt năm 2011 in
được chữ "Phở" có dấu.

---

## 2. Chỉnh phân phối

Sửa `weight`, không sửa code.

```yaml
# muốn 70% là hoá đơn siêu thị:
- id: quan_nhau            # weight: 3 -> 1
- id: sieu_thi_lon         # weight: 3 -> 5
```

Trọng số là **tương đối trong danh sách ứng viên còn lại sau khi lọc**, không
phải xác suất tuyệt đối. Nếu `sieu_thi_vat` bị `requires: [has_vat_lines]` loại
ra thì trọng số của nó không tính vào mẫu số.

Xem phân phối thật sự ra sao trước khi chạy dài:

```bash
make distribution            # 2000 lần bốc, đếm theo từng thuộc tính
```

Kiểm tra luật có chỗ nào vô nghĩa không (thẻ gõ sai, giá trị không bao giờ bốc
trúng — sai loại này im lặng, sinh ảnh vẫn chạy, chỉ là giá trị đó không bao
giờ xuất hiện):

```bash
make check-rules
```

---

## 3. Thêm một bố cục mới

1. Tạo `layouts/<tên>.yaml`. Chép một file gần giống nhất rồi sửa; ghi rõ
   `source:` là đo từ ảnh nào.
2. Khai báo nó trong `rules/layout.yaml`, kèm `requires` phù hợp.
3. Xem thử bằng chữ, không cần render ảnh:

```bash
make preview-grid LAYOUT=<tên>
```

### Ngữ pháp của một file bố cục

```yaml
width: [40, 48]        # bề rộng giấy tính bằng KÝ TỰ (giấy nhiệt 80mm ≈ 42-48)
gutter: 1              # số ký tự chừa giữa hai cột (0 = sát nhau)
rule_char: "-"         # ký tự vẽ đường kẻ ngang

header:                # tên cửa hàng, địa chỉ, tiêu đề
  name_scale: [1.15, 1.45]
  title: true
  branch: false        # bỏ hẳn một dòng: WinMart không in chi nhánh

meta:
  style: pairs         # pairs | two_column | pipes
  rule_after: false

columns:               # width 0 = "lấy phần còn thừa" (chỉ dùng cho cột name)
  - {key: stt,        title: "Stt",      width: 4,  align: right}
  - {key: qty,        title: "Số lượng", width: 11, align: right}

item:
  wrap_name: true      # false = cắt bớt tên dài, như máy in đời cũ
  rows:                # mỗi phần tử là MỘT DÒNG in ra
    - - {col: stt, from: stt}
      - {from: name, span: [qty, amount]}   # trải từ cột qty tới hết cột amount
    - - {col: qty, from: qty}
      - {col: unit_price, from: unit_price}
  note_row: {indent: 2}                 # dòng tên hàng thụt vào (kiểu siêu thị)
  discount_row: {label: "KM"}
  original_price_row: {label: "Giá gốc:"}

totals:
  emphasise_grand: true
  grand_scale: [1.20, 1.55]
  grand_two_lines: true    # nhãn một dòng, số tiền dòng sau
```

Nguồn dữ liệu dùng được trong `from:`: `stt`, `name`, `qty`, `unit_price`,
`amount`, `barcode`, `barcode_name`, `vat`, `unit`, `note`.

Dòng nào mà mọi trường đều rỗng thì bị bỏ qua — nhờ vậy một template dùng chung
được cho cả hàng cân (có dòng khối lượng) lẫn hàng đóng gói (không có).

---

## 4. Thêm mặt hàng / cửa hàng

`corpus/vi/` là file text thuần, phân cách bằng **TAB**. Luôn viết tiếng Việt
**CÓ DẤU** — thuộc tính `content` mới là chỗ quyết định có bỏ dấu lúc render hay
không, và bỏ dấu là một chiều: từ "Hẹn gặp lại" ra "Hen gap lai" thì được, ngược
lại thì không.

| file | cột |
| --- | --- |
| `items_quan.txt`, `items_sieuthi.txt` | tên ⇥ giá tối thiểu ⇥ giá tối đa |
| `shops_quan.txt` | tên |
| `shops_sieuthi.txt` | thương hiệu ⇥ chi nhánh |
| `streets.txt`, `footers_*.txt` | một dòng một giá trị |
| `wards.txt` | phường ⇥ quận ⇥ tỉnh/thành |
| `payments.txt` | nhãn ⇥ nhóm (`tienmat`/`the`/`vi`/`qr`) |

Dòng sai số cột bị bỏ qua chứ không làm hỏng cả lần chạy — sửa corpus bằng tay
thì một dòng hỏng chỉ nên tốn dòng đó. Kiểm tra bằng `make check-corpus`.

---

## 5. Thêm một hiệu ứng làm cũ

Viết model mới trong `degradation/`, đăng ký vào `DEGRADATIONS`, rồi dùng tên đó
trong `rules/augmentation.yaml`:

```yaml
- id: kịch_bản_mới
  weight: 2
  requires: [in_nhiet]
  params:
    chain:
      - [paper_texture, {alpha: 0.4, grain: 0.6}]
      - [tên_hiệu_ứng_mới, {tham_số: 1.0}]
```

Thứ tự trong `chain` **không hoán vị được**: mực mòn rồi mới nhoè thì đọc ra là
"chữ cũ bị scan dở", nhoè rồi mới mòn thì ra "vết lem". `paper_texture` luôn
đứng đầu — mọi thứ sau nó là hư hại lên một tờ giấy đã tồn tại.

Xem danh sách hiệu ứng có sẵn: `make list-degradations`.

---

## 6. Nhãn

`receipt.ground_truth()` trả về nhãn lồng nhau kiểu CORD, dựng từ **chính các
object mà renderer dùng để vẽ**, nên nhãn không thể mô tả thứ ảnh không có.

```json
{
  "doc_type": "receipt_sieuthi",
  "title": "HOÁ ĐƠN BÁN HÀNG",
  "store": {"name": "VinCommerce", "branch": "VM Royal City", "address": "..."},
  "menu": [
    {"nm": "Nho đỏ không hạt Mỹ", "cnt": "1", "price": "149.625",
     "unitprice": "149.625", "barcode": "2607609009502",
     "weight": "0,950 KG", "unitprice_per_unit": "157.500",
     "discountprice": "-64.125"}
  ],
  "total": {"TỔNG TIỀN PHẢI T.TOÁN": "353.300", "TIỀN TRẢ LẠI": "0"},
  "footer": ["CẢM ƠN QUÝ KHÁCH VÀ HẸN GẶP LẠI"]
}
```

Hàng cân đo (`weight`) in ra SL là **1** và đơn giá là **thành tiền của lần cân
đó**, còn giá theo kilo nằm ở dòng tên hàng — đúng như máy tính tiền in. Nhãn
ghi theo cái được in, và mang kèm khối lượng thật ở trường riêng.

Renderer glyph còn kèm `boxes`: toạ độ polygon từng ô, vẫn đúng sau khi tờ giấy
đã bị làm cong.
