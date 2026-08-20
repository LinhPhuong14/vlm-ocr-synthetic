# Tăng cường bố cục: gộp ô nhiều chỗ mà nội dung vẫn hợp lý

> Tài liệu đồng hành của [`tu-dong-hoa-bang-llm.md`](tu-dong-hoa-bang-llm.md).
> Bản kia trả lời "ai soạn ra bố cục"; bản này trả lời câu tiếp theo: **một bố
> cục đã soạn thì nhân lên thành bao nhiêu, bằng cách nào, và làm sao biết cái
> nhân ra vẫn là một tờ giấy có nghĩa.**

---

## 0. Câu trả lời ngắn

**Đừng sinh nhiều file bố cục. Hãy sinh ít file *giàu cấu trúc*, rồi nhân lên
bằng những nước đi hợp lệ.**

Ba mệnh đề, mỗi mệnh đề chống lại một sai lầm dễ mắc:

1. **Gộp ô không phải là một mặt nạ ngẫu nhiên trên lưới m×n.** Nó là một
   **nước đi trên cây cột ngữ nghĩa**. Bốn cột `Quỹ BHYT / Cùng chi trả / Khác
   / Tự chi trả` gộp được dưới một tiêu đề vì chúng là **bốn nguồn của cùng một
   số tiền**; `Đơn giá` với `Thuế suất` thì không, dù hai ô đứng cạnh nhau và
   mặt nạ nào cũng cho phép. Đi từ cây thì mọi phép gộp **hợp lệ theo cấu tạo**,
   không cần ai kiểm.
2. **Nội dung hợp lý được bảo đảm ở chỗ khai báo, không ở chỗ sinh.** Một cặp
   cột chỉ gộp được nếu file bố cục nói *gộp rồi thì chữ trong ô là gì*
   (`compose: "{qty} {unit}"`). Không khai thì nước đi đó không tồn tại. Phán
   quyết đắt tiền xảy ra **một lần cho mỗi cây**, không phải một lần cho mỗi
   ảnh.
3. **Biến thể là thứ được *bốc*, không phải thứ được *lưu*.** Một trục mới
   trong `rules/`, không phải 3000 file trong `layouts/`. Như thế nó có trọng
   số, có `requires`, tự động vào `metadata.jsonl`, tự động được `drift.py` đo,
   và tái lập được từ seed — y hệt mọi trục khác.

Và một cảnh báo đi kèm, vì nó dễ bị bỏ qua: **biến thể phải là cái đuôi của
phân phối, không phải cái thân.** `as_printed` — bố cục đúng như đo từ tờ giấy
thật — phải nặng ký nhất. Một bộ dữ liệu mà đa số trang là biến thể máy nghĩ ra
thì đã trôi khỏi thực tế, và không cổng nào hiện có phát hiện được.

---

## 1. Vì sao gộp ngẫu nhiên là sai (ở bài này)

Repo **đã có** một bộ sinh gộp ngẫu nhiên và nó đúng:
[`generators/html/tables.py`](../generators/html/tables.py) dựng bảng kiểu
PubTabNet, `colspan`/`rowspan` rải ngẫu nhiên, ô bị nuốt đánh dấu `-1`, nhãn là
chuỗi token PP-Structure. Nội dung là chữ vô nghĩa **cố ý** — README nói thẳng:
*"It teaches structure, not reading."* Với bài nhận dạng cấu trúc bảng thì ngẫu
nhiên là đúng: mô hình phải gặp cả những cấu trúc không tờ giấy nào có.

Bài đang bàn thì khác. Ở đây bảng nằm trong một **chứng từ có nhãn KIE**: nhãn
nói "Thành tiền chưa thuế của dòng 3 là 39.124.000". Nếu phép gộp ngẫu nhiên
đặt `Đơn giá` và `Thuế suất` chung một ô thì:

* ô ấy chứa cái gì? Hai giá trị không cộng được, không nối được;
* nhãn khai hai trường mà trang chỉ in một ô → `invariants.py` **đỏ**, đúng như
  thiết kế;
* và kể cả nếu qua được, mô hình học được một quy ước **không tồn tại**.

Hai bộ sinh này bổ sung nhau và **không nên nhập làm một**. Bảng ngẫu nhiên dạy
cấu trúc; chứng từ có biến thể hợp lệ dạy cấu trúc **và** ngữ nghĩa cùng lúc.

### 1.1 Sáu lý do gộp trong tài liệu thật

Bảng này là toàn bộ nội dung ngữ nghĩa của vấn đề. Mỗi dòng: nó là gì, và
**tiền đề** nào phải đúng thì nó mới có nghĩa.

| kiểu gộp | ví dụ thật trong repo | tiền đề ngữ nghĩa |
| --- | --- | --- |
| **Tiêu đề nhóm** (`colspan` trên hàng tiêu đề) | `medical_statement`: "Nguồn thanh toán (đồng)" phủ `fund → self_pay` | các cột con là **các mặt của cùng một khái niệm** |
| **Cột trụ** (`rowspan` cột đầu) | `stt`/`name` phủ các dòng phụ của cùng một mặt hàng | các dòng thuộc **cùng một thực thể** |
| **Dòng tổng** (`colspan` trái) | "Cộng tiền hàng" chạy từ cột 1 tới cột trước ô số | các cột bị phủ **không có giá trị riêng ở dòng đó** |
| **Dải phân nhóm** (`colspan` cả hàng) | `medical_statement`: "I. Khám bệnh"; `group_span: 6` | dòng phân nhóm, không mang số của riêng nó |
| **Dòng ghi chú của mặt hàng** | `{from: name, span: [qty, amount]}` — **đã có trong ngữ pháp** | ghi chú thuộc mặt hàng ngay trên nó |
| **Cặp cột hợp nhất** | `Số lượng` + `ĐVT` → "SL/ĐVT" | có **một cách viết chung** cho hai giá trị |

Năm dòng đầu repo **đã làm được ít nhất ở một đường vẽ**. Dòng cuối là thứ chưa
có, và cũng là thứ duy nhất bắt buộc phải khai thêm thông tin (§3.3).

### 1.2 Một luật đã nằm sẵn trong code, chỉ chưa được gọi là luật

`generators/html/sheets/base.py::_group_row` quyết định dải phân nhóm rộng bao
nhiêu như sau:

```python
# No declaration: run the name up to the first column that has a number
# on this row, which is where the sums begin.
width = next((index for index, key in enumerate(keys) if values.get(key)), 1)
```

Đó chính là **tiền đề của dòng "Dòng tổng"** ở bảng trên, viết bằng Python, ở
một chỗ, cho một trường hợp. Tổng quát hoá nó thành một bất biến áp cho mọi
phép gộp là một trong những việc rẻ nhất và giá trị nhất ở đây:

> **Trên một hàng có giá trị, một ô chỉ được phủ những cột không có giá trị ở
> hàng đó.** Gộp mà nuốt mất một giá trị là một lỗi, không phải một kiểu trình
> bày.

---

## 2. Hiện trạng: ba đường vẽ, ba mức hỗ trợ gộp

Đo trực tiếp, không đọc tài liệu:

| đường | mô hình ô gộp | nhãn có biết không |
| --- | --- | --- |
| `tables.py` | **đầy đủ** — ma trận `colspan`/`rowspan`, ô bị nuốt `-1` | **có** — token PP-Structure |
| `sheets/` (CSS) | **đầy đủ** — `<table>` thật, `colspan`/`rowspan` thật, `structure_tokens()` | **có** |
| **lưới ký tự** (14 bố cục thật sự chạy qua) | **mô phỏng, không mô hình hoá** | **không** |

`docs/brief-engine-html.md` §2 đã đo và ghi lại chỗ thứ ba:

> `_paint_bars()` vẽ `|` xuống từng dòng và **bỏ qua** vị trí đã có ô chiếm chỗ.
> Một dòng tổng chạy ngang năm cột chỉ là "một ô rộng tình cờ không có gạch dọc
> cắt qua" — không đâu ghi rằng nó *gộp* cột 1 tới 5. […] Ảnh có ô gộp, nhãn
> thì không biết.

### 2.1 Phát hiện: cây cột đã tồn tại một nửa

`sheets/base.py::_header_rows` đọc một khai báo **đã có trong ngữ pháp file bố
cục**:

```yaml
# rulebase/layouts/medical_statement.yaml
table:
  header_groups:
    - {title: "Nguồn thanh toán (đồng)", from: fund, to: self_pay}
  group_span: 6
```

và dựng ra hai tầng tiêu đề với `colspan` cho nhóm, `rowspan="2"` cho các cột
ngoài nhóm. Docstring của chính hàm đó nói ra vấn đề:

> *"There is no arithmetic here and that is the point: the same statement drawn
> on a character grid would be a wide cell that happens to have no rule under
> half of it."*

Và tác giả bố cục đã viết sẵn **tiền đề ngữ nghĩa** vào comment:

> *"Bốn cột cuối là bốn NGUỒN của cùng một số tiền, nên tờ mẫu gộp chúng dưới
> một tiêu đề chung."*

Nghĩa là ý tưởng "cây cột" không phải phát minh của tài liệu này. Nó đã ở đó,
được dùng đúng một lần, chỉ một đường vẽ đọc, và không vào nhãn.

**Đo được:**

```
tổng cột trên 16 bố cục:      87
bố cục có bảng đóng khung:     6/16
bố cục khai header_groups:     1/16   ← medical_statement
```

Một trên mười sáu. Đó không phải vì mười lăm tờ còn lại không có nhóm cột —
`invoice_vat_form` có `Thuế suất GTGT` và `Thành tiền có thuế GTGT` đứng cạnh
nhau và tờ mẫu thật gộp chúng dưới "Thuế GTGT" — mà vì **khai ra thì chỉ đường
CSS được lợi**, nên không ai buồn khai.

Đó là lý do việc này phải làm **theo thứ tự**: cho lưới ký tự và nhãn hiểu ô
gộp trước, rồi mới sinh biến thể. Ngược lại là nhân bản một khiếm khuyết.

---

## 3. Nguyên tắc: cây cột, và nước đi hợp lệ

### 3.1 Cây cột — mở rộng `header_groups` chứ không thay nó

Giữ nguyên cú pháp phẳng đang chạy (16 file không phải sửa), và cho phép khai
thêm quan hệ ở `table:`:

```yaml
columns:
  - {key: stt,             title: "STT",                   width: 6}
  - {key: name,            title: "Tên hàng hoá, dịch vụ", width: 0}
  - {key: unit,            title: "Đơn vị tính",           width: 11, optional: true}
  - {key: qty,             title: "Số lượng",              width: 10}
  - {key: unit_price,      title: "Đơn giá",               width: 14}
  - {key: amount,          title: "Thành tiền chưa thuế",  width: 14}
  - {key: vat_rate,        title: "Thuế suất",             width: 10}
  - {key: amount_with_vat, title: "Thành tiền có thuế",    width: 15}

table:
  header_groups:
    - {title: "Thuế GTGT", from: vat_rate, to: amount_with_vat,
       optional: true}                       # ← có thể hiện hoặc không
  merges:                                    # ← MỚI: cặp cột hợp nhất được
    - {from: qty, to: unit, title: "SL/ĐVT",
       compose: "{qty} {unit}"}
  stub:                                      # ← MỚI: cột nào làm trụ rowspan
    columns: [stt, name]
```

Ba khai báo mới, và **cả ba đều tuỳ chọn**: một file không khai gì thì hành vi
y như hôm nay. Đây là điều kiện để 16 bố cục đã đo không bị động vào — cùng lý
lẽ mà `rules: marks` đã dùng khi được thêm vào.

### 3.2 Tám nước đi

Bộ tăng cường **không có** phép biến đổi nào ngoài tám phép này. Danh sách đóng
là điều làm cho "hợp lệ theo cấu tạo" trở thành một câu nói được kiểm chứng chứ
không phải một lời hứa.

| nước đi | làm gì | chỉ hợp lệ khi |
| --- | --- | --- |
| `expand_group` | dựng tầng tiêu đề nhóm; cột ngoài nhóm `rowspan=2` | nhóm khai `optional: true` |
| `collapse_group` | bỏ tầng nhóm, mọi cột một tầng | nhóm khai `optional: true` |
| `merge_pair` | hợp nhất một cặp cột đã khai | cặp có trong `merges:` **và** có `compose:` |
| `drop_column` | bỏ hẳn một cột | cột khai `optional: true` **và** nhãn nén được trường đó (§6, T2-c) |
| `stub_rowspan` | cột trụ phủ các dòng phụ thay vì lặp lại | cột có trong `stub.columns` **và** mặt hàng có dòng phụ |
| `stack_rows` | đổi giữa các mẫu dòng mặt hàng đã khai | `item.rows` có nhiều hơn một mẫu |
| `total_span` | dòng tổng phủ tới cột đầu tiên có số | luôn hợp lệ — chính là luật §1.2 |
| `blank_rows` | số dòng trống có kẻ ô | bố cục khai `blank_rows` là một khoảng |

Không có `random_merge`. Không có `split_cell`. Không có nước đi nào tạo ra một
quan hệ mà file bố cục chưa nói tới.

### 3.3 `compose:` — chỗ bảo đảm "nội dung hợp lý"

Đây là câu trả lời trực tiếp cho vế thứ hai của câu hỏi.

Một phép gộp cột là một **phép biến đổi trên giá trị**, không chỉ trên hình.
Gộp `Số lượng` với `Đơn vị tính` thì ô mới phải chứa `"2 cái"`, không phải
`"2"` cũng không phải `"2cái"` cũng không phải hai giá trị dính nhau. Nên phép
gộp **phải khai cách hợp nhất**:

```yaml
merges:
  - {from: qty, to: unit, title: "SL/ĐVT", compose: "{qty} {unit}"}
  - {from: unit_price, to: amount, title: "Đơn giá × SL",
     compose: "{unit_price} × {qty}"}        # ví dụ, nếu tờ nào in thế
```

`compose:` là template trên đúng vốn từ `from:` mà `item_values()` đã cung cấp
(`stt`, `name`, `qty`, `unit_price`, `amount`, `vat_rate`, …). Nên nó không mở
ra không gian mới — nó chỉ nói cách viết lại hai giá trị đã có thành một chuỗi.

Bốn hệ quả, và đây là chỗ nguyên tắc trả công:

* **Không khai `compose` thì không có nước đi.** Bộ tăng cường không được phép
  đoán cách nối hai giá trị. Đây là toàn bộ cơ chế "bảo đảm hợp lý", và nó
  chuyển gánh nặng về **thời điểm soạn**, nơi có người và có phản biện.
* **Nhãn không mất gì.** `ground_truth()` vẫn khai `qty` và `unit` riêng — giá
  trị không đổi vì cách in đổi. Chỉ `boxes` gộp lại, và hộp mới mang **cả hai**
  `role`. Đây là tín hiệu huấn luyện thật: "ô này chứa hai trường".
* **Bất biến hiện có vẫn chạy.** Số học tiền không đụng tới; kiểm "mọi giá trị
  nhãn đều được in" vẫn đúng vì `"2 cái"` chứa cả `"2"` lẫn `"cái"`.
* **Kiểm được bằng máy.** Một test khẳng định: với mọi `compose:` trong mọi bố
  cục, chuỗi sinh ra chứa tất cả các giá trị nguồn không rỗng. Cái nào không thì
  `compose` ấy làm mất dữ liệu và phải sửa.

---

## 4. Chọn nước đi: một trục mới, không phải 3000 file

### 4.1 Vì sao không lưu thành file

Một biến thể **không phải** một bố cục mới. Nó là cùng tờ giấy, in ra hơi
khác. Lưu thành file thì:

* `layouts/` từ 16 lên hàng nghìn, và `provenance:` mất nghĩa — 3000 file cùng
  trỏ về một bức ảnh;
* `rules/layout.yaml` phải khai 3000 giá trị, mỗi giá trị một trọng số;
* `tests/test_layout.py` chạy 5 seed × 3000 bố cục;
* và không ai đọc được thư mục ấy nữa.

Bốc thì ngược lại: biến thể vào `metadata.jsonl` như mọi thuộc tính khác, lọc
được, `drift.py` đo được, seed tái lập được.

### 4.2 `rules/structure.yaml`

Trục thứ chín, **bốc ngay sau `layout`** — vì nó là một phát biểu *về* bố cục
vừa bốc, và phải đặt thẻ trước khi `content` quyết định cách viết.

```yaml
# rules/structure.yaml — bốc thứ 3/9, ngay sau `layout`
options:
  # Đúng như tờ giấy được đo. PHẢI nặng ký nhất — xem §4.4.
  - id: as_printed
    weight: 12
    tags: [structure_measured]
    params: {moves: []}

  - id: grouped_headers
    weight: 3
    requires: [has_optional_group]
    tags: [structure_varied, two_band_header]
    params:
      moves: [expand_group]
      group_prob: 1.0

  - id: compact
    weight: 2
    requires: [has_optional_column]
    tags: [structure_varied]
    params:
      moves: [collapse_group, drop_column]
      drop_prob: 0.5           # mỗi cột optional bị bỏ với xác suất này
      max_drops: 2

  - id: stubbed
    weight: 2
    requires: [has_stub_column, multi_row_item]
    tags: [structure_varied, has_rowspan]
    params: {moves: [stub_rowspan]}

  - id: dense
    weight: 1
    requires: [has_merge_pair]
    tags: [structure_varied, has_merged_columns]
    params:
      moves: [merge_pair, collapse_group, stub_rowspan]
      merge_prob: 0.7
```

Ba thẻ `has_optional_group` / `has_optional_column` / `has_stub_column` do
**giá trị `layout` đặt** trong `rules/layout.yaml`, và đó là chỗ cơ chế cũ trả
công lần nữa: viết ở mức **node họ** thì cả họ nhận một lần, và bố cục thêm vào
sau không quên được.

Tham số ở đây mượn thẳng vốn từ của
[SynthTabNet](https://github.com/IBM/SynthTabNet) — số tầng tiêu đề, **loại
span** (chỉ tiêu đề / chỉ hàng / chỉ cột / cả hai), kích thước span lớn nhất,
tỉ lệ diện tích bảng bị span phủ. Khác biệt: ở đây mỗi tham số bị chặn bởi
những gì file bố cục **cho phép**, chứ không rải tự do lên lưới.

### 4.3 Đếm thật, không nhân bừa

Các nước đi **không độc lập**: bỏ cột `unit` và hợp nhất `qty`+`unit` loại trừ
nhau. Nên số biến thể không phải một tích, và cách trung thực để nói con số là
**liệt kê**, rồi in ra.

Ví dụ có thật — `invoice_vat_form` (8 cột), với ba khai báo đề xuất ở §3.1:

| trục biến thiên | số trạng thái |
| --- | ---: |
| cột `unit`: giữ / bỏ / hợp nhất vào `qty` | 3 *(không phải 4 — "vừa bỏ vừa gộp" không tồn tại)* |
| nhóm `Thuế GTGT`: hiện / ẩn | 2 |
| cột trụ `stt`: rowspan / lặp lại | 2 |
| `blank_rows` khai khoảng `[3, 6]` | 4 |
| | **48 cấu trúc hợp lệ** |

Nhân với bề rộng trang mà bố cục này đã bốc sẵn (`width: [104, 118]` → 15 giá
trị): **720 lưới khác nhau từ một file**. Rồi nhân tiếp với bảy trục hiện có
(35.985.600 tổ hợp) và với corpus.

Con số ấy phải **in ra được**, không phải ước lượng trong đầu:

```bash
make structures                 # mỗi bố cục: bao nhiêu cấu trúc hợp lệ, và là những gì
make structures LAYOUT=invoice_vat_form --enumerate
```

Đây là bản song sinh của `make distribution` cho trục mới, và nó là cách duy
nhất để biết một khai báo mới thật sự mở ra bao nhiêu — hay mở ra 1 vì `requires`
chặn hết, đúng cái bẫy mà `rulebase/README.md` §2 đã cảnh báo cho trọng số.

### 4.4 Biến thể là cái đuôi, không phải cái thân

`as_printed` trọng số 12, tất cả biến thể cộng lại là 8. Cố ý, và có lý do đo
được ở tài liệu kia:

> Nếu bố cục do máy nghĩ ra chiếm đa số, phân phối bố cục trôi khỏi thực tế mà
> **không cổng nào hiện có phát hiện** — mọi cổng đều kiểm tính nhất quán nội
> tại chứ không kiểm tính giống thật. Đây là bản riêng của *model collapse*
> trong repo này.

Nên: `structure` phải vào `manifest.json`, và tỉ lệ `structure_measured` phải
là một con số người ta nhìn thấy. Đề xuất trần: **biến thể không quá 40 %** một
lần chạy, và `drift.py` cảnh báo khi vượt — cùng cơ chế `FALLBACK_LIMIT = 0.05`
đã dùng cho nguồn nội dung.

---

## 5. Nhãn phải học được ô gộp

Nhân biến thể mà nhãn vẫn mù thì chỉ là nhân bản một khiếm khuyết đã biết. Nên
việc này **đi trước**, không đi sau.

### 5.1 Hai hệ toạ độ, một dẫn xuất

```python
@dataclass
class Cell:
    text: str; role: str
    row: int; col0: int; col1: int      # KÝ TỰ — để vẽ
    align: str = "left"; scale: float = 1.0; bold: bool = False
    ink: str = "press"                  # (từ tài liệu kia)
    colspan: int = 1                    # CỘT BẢNG — để dựng nhãn cấu trúc
    rowspan: int = 1
    roles: tuple[str, ...] = ()         # >1 khi ô là kết quả của `merge_pair`
```

`col0/col1` là ký tự vì renderer vẽ bằng ký tự; `colspan/rowspan` là cột bảng
vì nhãn cấu trúc nói bằng cột bảng. Hai hệ, và cái thứ hai **dẫn xuất** từ cây
cột chứ không đo lại từ pixel — đúng khuôn mẫu `Mark` đã dùng
(`rulebase/README.md`: *"trên cùng lưới (row, column) mà các ô dùng, nên không
renderer nào cần hệ toạ độ thứ hai"*).

`roles` số nhiều là chi tiết nhỏ nhưng cần: sau `merge_pair`, ô "2 cái" thuộc
về **cả** `menu.qty` lẫn `menu.unit`. Một `role` duy nhất sẽ buộc phải chọn một
và nói dối về cái kia.

### 5.2 Dùng lại chuỗi token đã có, không phát minh cái thứ ba

`sheets/base.py::structure_tokens()` đã sinh đúng định dạng PP-Structure mà
`tables.py` viết, và docstring của nó nói vì sao:

> *"Same format `tables.py` writes, so anything that already reads those reads
> this."*

Nên đường lưới ký tự **cũng** phải sinh định dạng ấy, không phải một lược đồ
thứ ba. Ba đường vẽ, một vốn từ cấu trúc. Cái giá của việc không làm thế là ba
bộ đọc dữ liệu ở phía người dùng.

### 5.3 Phép thử: dựng lại rồi so

`tests/test_tables.py` đã có đúng cái oracle cần cho việc này:

| test đã có | nó khẳng định |
| --- | --- |
| `test_the_token_list_promises_exactly_the_cells_the_page_has` | số ô nhãn hứa = số ô trang có |
| `test_a_covered_cell_is_written_neither_as_markup_nor_as_a_token` | ô bị nuốt không xuất hiện ở đâu cả |
| `test_the_rebuilt_html_carries_every_cell_text` | **ghép chữ trở lại giữa các token thì dựng lại đúng bảng** |
| `test_merged_cells_are_the_normal_case_not_the_rare_one` | gộp là ca thường, không phải ca hiếm |

Cái thứ ba là oracle mạnh nhất và nên áp cho cả đường chứng từ: **nhãn cấu trúc
cộng nhãn nội dung phải dựng lại được trang**. Nếu dựng lại không ra thì một
trong hai nửa sai, và bài kiểm nói ngay nửa nào.

---

## 6. Ba tầng bảo đảm "hợp lý"

Xếp theo giá: rẻ nhất và chắc nhất ở trên.

### T1 · Hợp lệ theo cấu tạo — miễn phí

Nước đi thao tác trên cây. Phép gộp cắt ngang biên giới nhóm **không phải một
nước đi**, nên không cần ai kiểm. Đây là chỗ diệt ~95 % chuyện vô nghĩa, và nó
không tốn một chu kỳ CPU nào lúc chạy.

### T2 · Bất biến kiểm được — rẻ, chạy mỗi ảnh

Bảy điều, và **bốn điều đã có sẵn**:

| # | bất biến | trạng thái |
| --- | --- | --- |
| a | Số học tiền vẫn đúng sau biến thể | **đã có** (`invariants.py`) |
| b | Mọi giá trị nhãn đều thật sự được in | **đã có** |
| c | Bỏ một cột thì nhãn cũng nén trường đó | **đã có ngưỡng** — `test_content.py::test_the_suppressed_field_defect_has_not_grown` |
| d | Quad nằm trong khung | **đã có** |
| e | Trên hàng có giá trị, ô gộp chỉ phủ cột không có giá trị (§1.2) | **mới** |
| f | Chuỗi token dựng lại được trang (§5.3) | **mới** — nhưng dùng lại `rebuild_html` đã có |
| g | Ô `merge_pair` chứa mọi giá trị nguồn không rỗng | **mới** — một test trên `compose:` |

Điểm đáng nói ở (c): **`drop_column` là nước đi nguy hiểm nhất**, vì nó là nước
duy nhất làm nhãn phải nói ít đi. Nó không được phép chỉ "ngừng vẽ" — trường
tương ứng phải đi qua đường nén của `ground_truth()`, nếu không `invariants.py`
sẽ đỏ, và đỏ **đúng**. Nếu một cột không nén được thì nó không được khai
`optional: true`, hết.

### T3 · Phán quyết một lần cho mỗi **chính sách**, không phải mỗi ảnh

Câu *"tờ giấy này có tồn tại không"* không kiểm bằng máy được. Nhưng nó **không
cần hỏi mỗi ảnh** — nó là câu hỏi về **cây và về chính sách**, hai thứ thay đổi
hiếm.

```
soạn cây cột  ──▶  A5 phản biện  ──▶  người duyệt   ← hiếm, đắt, có căn cứ
       │
       ▼
in ra N biến thể bằng preview-grid, xem một lượt     ← một lần cho mỗi chính sách
       │
       ▼
sinh 50.000 ảnh                                      ← thường xuyên, rẻ, kiểm bằng máy
```

Kinh tế của cách này là toàn bộ lý do nó đáng làm: chi phí phán quyết là
**O(số cây × số chính sách)** chứ không phải **O(số ảnh)**.

Việc phải làm cho T3: `make preview-structures LAYOUT=<id>` in **mọi** cấu trúc
hợp lệ của một bố cục dưới dạng văn bản, cạnh nhau. 48 biến thể của
`invoice_vat_form` là hai màn hình — đủ để một người liếc qua và nói "cái thứ
ba trông không phải hoá đơn".

---

## 7. Chỗ LLM đứng

Ngắn: **LLM soạn cây, không soạn biến thể.**

| | ai làm | tần suất | kiểm bằng |
| --- | --- | --- | --- |
| cây cột (`header_groups`, `merges`, `compose`, `stub`, `optional`) | **LLM + người duyệt** | mỗi bố cục một lần | schema, phản biện, mắt |
| chính sách biến thể (`rules/structure.yaml`) | **LLM đề xuất, người chốt** | vài lần cho cả repo | `make preview-structures` |
| chọn nước đi cho một ảnh | **Python tất định**, từ seed | mỗi ảnh | 7 bất biến |

Đây là câu trả lời cho "sinh nhiều layout data": không phải LLM viết 200 file —
mà là **LLM viết 20 file *giàu quan hệ*, bộ tăng cường nhân lên thành hàng
nghìn cấu trúc chứng minh được là hợp lệ**. Vế đắt tiền hiếm và có căn cứ; vế
rẻ tiền nhiều và kiểm được.

Có một lợi ích phụ đáng kể: **khai cây cột dễ hơn soạn bố cục mới**. Nó là câu
hỏi hẹp — *"cột nào là mặt của cùng một khái niệm? cột nào tờ này có mà tờ kia
bỏ? hai cột nào có cách viết chung?"* — hỏi trên một file đã tồn tại, đã được
đo từ giấy thật. Nên đây là **việc đầu tiên nên giao cho LLM**, trước cả soạn
bố cục mới: rủi ro thấp hơn, phần thưởng cao hơn, và 15/16 bố cục hiện có đang
chờ được khai.

---

## 8. Bằng chứng bên ngoài

Hai kết quả đo được, và cả hai đều nói cùng một điều.

**Đừng sinh ngẫu nhiên — hãy dẫn xuất từ bảng thật, rồi biến thiên có chặn.**
[*Synthesizing Realistic Data for Table Recognition*](https://arxiv.org/abs/2404.11100)
lấy cấu trúc và nội dung từ **bảng có thật**, phân loại theo nội dung thành 14
nhóm, chọn hồ sơ kiểu dáng theo nhóm, rồi chỉ chỉnh ngẫu nhiên **tối đa 10 %**.
Kết quả: mô hình học trên dữ liệu tiếng Trung sinh ra đạt TEDS 0,9091 trên
benchmark thật; và bổ sung FinTabNet bằng bảng phức tạp sinh ra nâng TEDS từ
**0,9758 lên 0,9847 — lợi ích tập trung đúng ở những bảng có nhiều ô gộp**.

Đó vừa là xác nhận rằng **việc này đáng làm** (ô gộp là chỗ mô hình yếu, và
tăng cường ô gộp là chỗ trả công), vừa là xác nhận cho *cách* làm: neo vào tờ
giấy thật, biến thiên trong biên đã khai. Đúng những gì §3 và §4.4 đề ra.

**Tham số hoá cấu trúc là cách kiểm soát đúng.**
[SynthTabNet](https://github.com/IBM/SynthTabNet) (Nassar và cs. 2022, cùng bài với [TableFormer](https://arxiv.org/abs/2203.01017)) — 600k bảng, 4 tập con — điều
khiển bằng: số hàng/cột, số tầng tiêu đề, **loại span** (chỉ tiêu đề / chỉ hàng
/ chỉ cột / cả hai), kích thước span lớn nhất, **tỉ lệ diện tích bị span phủ**.
Vốn từ đó nên mượn nguyên cho `rules/structure.yaml`; khác biệt duy nhất, và là
khác biệt quan trọng, là ở đây mỗi tham số bị **chặn bởi cây cột** thay vì rải
tự do — vì SynthTabNet dạy cấu trúc, còn repo này dạy cấu trúc *và* ngữ nghĩa
cùng lúc.

---

## 9. Lộ trình

Bốn bước. Chúng cài vào chuỗi M0–M4 của [tài liệu chính](tu-dong-hoa-bang-llm.md#12-năm-đợt)
như sau, và **T1 phải xong trước khi nghĩ tới T3**.

### T0 · Cây cột vào schema *(cài vào M0)*
Thêm `optional`, `merges`, `compose`, `stub` vào `LAYOUT_SCHEMA`; kiểm
`from`/`to` trỏ vào `key` có thật, nhóm không chồng nhau, `compose` chỉ dùng
vốn từ `from:` đã có, mọi `merges` đều có `compose`.
**Xong khi:** `medical_statement` (bố cục duy nhất đang khai `header_groups`)
qua sạch, và một khai báo sai bị bắt.
**Công:** +1 ngày trên M0.

### T1 · Ô gộp vào lưới ký tự **và vào nhãn** *(nâng từ M4 lên ngay sau M0)*
`Cell.colspan/rowspan/roles`; đường lưới đọc `header_groups` như đường CSS đã
đọc; `structure_tokens()` dùng chung; bất biến (e) và (f).
**Xong khi:** `medical_statement` qua đường lưới cho ra cùng chuỗi token như
qua đường CSS. Đây là phép thử mạnh nhất trong cả lộ trình — hai đường vẽ độc
lập phải đồng ý về cùng một cấu trúc.
**Công:** 1–1,5 tuần. **Đây là bước then chốt**, và nó có giá trị *kể cả khi
không bao giờ sinh biến thể*: nó vá đúng khiếm khuyết `brief-engine-html.md` đã
đo và ghi lại.

### T2 · Bộ tăng cường + `rules/structure.yaml` *(sau T1)*
Tám nước đi, giải xung đột, `make structures` và `make preview-structures`,
trần biến thể trong `drift.py`.
**Xong khi:** `make structures` in ra 48 cho `invoice_vat_form`, và cả 48 dựng
được, qua bất biến, `preview-grid` đọc được.
**Công:** 1 tuần.

### T3 · LLM khai cây cho 15 bố cục còn lại *(cài vào M2)*
Việc hẹp, có căn cứ, dễ phản biện: *"cột nào cùng nhóm? cột nào bỏ được? cặp
nào gộp được và viết chung thế nào?"* — hỏi trên file đã có, kèm ảnh gốc mà
`source:` trỏ tới.
**Xong khi:** mỗi khai báo mới có một dòng lý do như comment của
`medical_statement` đã có, và `make preview-structures` được người xem một lượt.
**Công:** 2–3 ngày sau khi A1 (§10 tài liệu chính) chạy được.

## 10. Cái sẽ **không** làm

| không làm | vì sao |
| --- | --- |
| Gộp ngẫu nhiên trên lưới m×n cho đường chứng từ | `tables.py` đã làm đúng cho bài của nó; ở đây nó tạo ra tờ giấy không tồn tại và làm đỏ bất biến đúng |
| Để bộ tăng cường tự đoán cách nối hai giá trị | không có `compose:` thì không có nước đi. Đoán là chỗ "nội dung hợp lý" sẽ mất |
| Lưu biến thể thành file trong `layouts/` | phá `provenance:`, phá thư mục, phá bộ test |
| Nhập `tables.py` vào đường chứng từ | hai bài khác nhau, hai loại nhãn, hai loại nội dung |
| Sinh biến thể trước khi nhãn hiểu ô gộp (T1) | nhân bản một khiếm khuyết đã được đo và ghi lại |
| Cho biến thể chiếm đa số | phân phối trôi khỏi thực tế, và không cổng nào bắt được (§4.4) |

---

## Phụ lục · Số đo

```
$ python - <<'PY'   # đếm trên rulebase/layouts/*.yaml
tổng cột trên 16 bố cục:      87
bố cục có bảng đóng khung:     6/16
bố cục khai header_groups:     1/16   (medical_statement)
```

| bố cục | cột | section | header_groups | mẫu dòng hàng | kiểu kẻ |
| --- | ---: | ---: | ---: | ---: | --- |
| medical_statement | 13 | 9 | **1** | 1 | marks |
| invoice_vat_form | 8 | 8 | 0 | 1 | marks |
| invoice_vat_summary | 8 | 9 | 0 | 1 | marks |
| invoice_hotel_stay | 7 | 7 | 0 | 2 | marks |
| invoice_export · invoice_hotel_compact · invoice_water | 6 | 7–9 | 0 | 1–3 | marks |
| invoice_brand · invoice_tax_en | 5 | 7 | 0 | 1 | marks |
| eatery_indexed · market_* · invoice_power | 4 | 6–8 | 0 | 1–2 | ascii/marks |
| eatery_ascii | 3 | 6 | 0 | 1 | ascii |
| authorisation_letter | 0 | 6 | 0 | 0 | marks |

Ước lượng biến thể ở §4.3 dựa trên ba khai báo *đề xuất* cho
`invoice_vat_form`, không phải trên file hiện tại — file hiện tại chưa khai
`optional`, `merges` hay `stub` nào.

## Nguồn

- [*Synthesizing Realistic Data for Table Recognition*](https://arxiv.org/abs/2404.11100) — dẫn xuất từ bảng thật, biến thiên ≤10 %; FinTabNet TEDS 0,9758 → 0,9847, lợi ích tập trung ở bảng nhiều ô gộp
- SynthTabNet — Nassar và cs. 2022, giới thiệu trong [TableFormer](https://arxiv.org/abs/2203.01017), dữ liệu ở [IBM/SynthTabNet](https://github.com/IBM/SynthTabNet): 600k bảng, 4 tập con (Finance · PubTabNet · Marketing · Sparse); tham số hoá cấu trúc — tầng tiêu đề, loại span, kích thước span, tỉ lệ diện tích bị phủ
- [UniTable](https://arxiv.org/abs/2403.04822) — khung hợp nhất cho nhận dạng cấu trúc bảng, để đối chiếu vốn từ nhãn
- [TIES_DataGeneration](https://github.com/hassan-mahmood/TIES_DataGeneration) — mô hình bảng mà `generators/html/tables.py` dẫn xuất từ đó, qua PaddleOCR

## Liên quan trong kho này

| | |
| --- | --- |
| [`tu-dong-hoa-bang-llm.md`](tu-dong-hoa-bang-llm.md) | tài liệu chính: ai soạn bố cục, trục mực, lộ trình M0–M4 |
| [`brief-engine-html.md` §2](brief-engine-html.md) | đo và ghi lại: ảnh có ô gộp, nhãn không biết |
| [`rulebase/README.md` §3](../rulebase/README.md) | ngữ pháp file bố cục — `span:`, `columns:`, `item.rows:` |
| [`generators/html/sheets/base.py`](../generators/html/sheets/base.py) | `_header_rows` (nhóm tiêu đề thật) · `structure_tokens` · `_group_row` |
| [`generators/html/tables.py`](../generators/html/tables.py) | bộ sinh bảng ngẫu nhiên — bài khác, nhãn khác, giữ nguyên |
| [`tests/test_tables.py`](../tests/test_tables.py) | bốn oracle dùng lại được cho nhãn cấu trúc |
| [`rulebase/layouts/medical_statement.yaml`](../rulebase/layouts/medical_statement.yaml) | bố cục duy nhất đã khai `header_groups`, kèm lý do ngữ nghĩa |
