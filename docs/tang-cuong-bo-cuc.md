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

Và **hai chế độ an toàn, không phải một** — đây là chỗ bản đầu của tài liệu này
quá hẹp. Tờ A gộp ở tiêu đề (đi theo cây → *hợp lệ theo cấu tạo*, khỏi kiểm);
tờ B gộp hai cột trong **đúng một hàng**, không theo cây nào (→ *đề xuất rồi
kiểm*, với một vị từ một dòng: **ô gộp không được phủ cột nào có giá trị ở hàng
đó**). Cả hai tờ đều có thật, nên bộ tăng cường phải sinh được cả hai. Chi tiết
ở §3.2.

Và **hai trục, không phải một**: cột (§3–§4) và **component** (§4b). Trang đã
là một dãy khối — `sections: [letterhead, doctitle, parties, table, …]` — nên
biến thể ở mức khối nhân với biến thể ở mức cột. Một file bố cục khai đủ quan
hệ cho ra **hàng nghìn** trang hợp lệ.

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

### 3.2 Hai chế độ an toàn, không phải một

> **Sửa lại so với bản đầu.** Bản đầu chỉ có *hợp lệ theo cấu tạo* và vì thế
> **từ chối** một ca có thật: tờ A gộp ở tiêu đề (cây cột), tờ B gộp hai cột
> trong **đúng một hàng**, không theo cây nào cả. Tờ B tồn tại — người thiết kế
> mẫu gộp hai ô để chỗ cho một nhãn dài, hoặc một dòng ghi chú chạy ngang hai
> cột trong khi hai cột kia vẫn có số. Một bộ tăng cường không sinh được tờ B
> là một bộ tăng cường thiếu.

Nên có **hai chế độ**, và chúng khác nhau ở chỗ *bao giờ thì biết là an toàn*:

| chế độ | ai bảo đảm | kiểm lúc nào | ca |
| --- | --- | --- | --- |
| **Hợp lệ theo cấu tạo** | cây cột | không cần kiểm | **A** — tiêu đề nhóm, cột trụ, dải phân nhóm |
| **Đề xuất rồi kiểm** | một vị từ rẻ | mỗi hàng, mỗi lần | **B** — gộp cục bộ trong một hàng |

Vị từ cho chế độ thứ hai chỉ có một câu, và **nó đã nằm sẵn trong repo** (§1.2):

> Một ô gộp trên một hàng là hợp lệ **khi và chỉ khi** nó không phủ lên cột nào
> có giá trị không rỗng ở hàng đó.

Rẻ (`values.get(key)` cho mỗi cột bị phủ), tất định, và **đủ**: nó chính là
định nghĩa của "gộp mà không nuốt mất dữ liệu". Nên tờ B không cần một cây; nó
cần một *phạm vi* được khai và một vị từ được chạy.

Và một nhận xét làm mọi thứ nhẹ hơn: **ca B đã diễn tả được trong ngữ pháp hiện
tại.** `{from: name, span: [qty, amount]}` trong `item.rows` **chính là** một
colspan cục bộ theo hàng — nó đã chạy trên `eatery_indexed` từ đầu. Cái thiếu
không phải là ngôn ngữ, mà là (a) nó chưa vào nhãn, và (b) nó chưa được coi là
một *nước đi* có thể bốc.

### 3.2b · Chín nước đi

Bộ tăng cường **không có** phép biến đổi nào ngoài chín phép này. Danh sách
đóng là điều làm cho "hợp lệ" trở thành một câu kiểm chứng được chứ không phải
một lời hứa.

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
| **`row_local_merge`** | gộp một dải cột trên **một hàng** — ca B | dải nằm trong `row_merges.scope` đã khai, **và** vị từ §3.2 đúng cho hàng đó |

Tám nước đầu là *hợp lệ theo cấu tạo*: không cần kiểm. Nước thứ chín là *đề
xuất rồi kiểm*: được đề xuất tự do trong phạm vi đã khai, rồi vị từ nhận hoặc
loại — **cho từng hàng một**, vì cùng một dải có thể hợp lệ ở hàng này và nuốt
mất một số ở hàng kia.

Vẫn không có `random_merge` trên toàn bảng, và không có `split_cell`. Khác biệt
giữa `row_local_merge` và "gộp ngẫu nhiên" là **phạm vi được khai** cộng **vị từ
được chạy** — không phải là chỗ gộp có đẹp hay không.

### 3.2c · `row_merges:` — khai phạm vi cho ca B

```yaml
table:
  row_merges:
    # Trên hàng mặt hàng, tên có thể chạy sang cột ĐVT khi mặt hàng không có
    # đơn vị (dịch vụ, phí) -- đúng như tờ mẫu in ra.
    - {scope: [name, unit], on: item, prob: 0.35}
    # Trên hàng ghi chú, ghi chú chạy ngang ba cột số.
    - {scope: [qty, amount], on: note, prob: 1.0}
    # Trên hàng tổng, nhãn chạy tới cột đầu tiên có số -- luật §1.2, khai
    # tường minh cho người đọc thấy.
    - {scope: [stt, amount], on: total, prob: 1.0}
```

Ba trường, và mỗi trường chặn một kiểu sai:

* **`scope`** — dải cột **liền nhau** được phép gộp. Không khai thì không gộp.
  Đây là chỗ "ngẫu nhiên" bị chặn: ngẫu nhiên *trong* một dải người viết bố cục
  đã nhìn qua, chứ không ngẫu nhiên trên cả bảng.
* **`on`** — loại hàng (`item` · `note` · `total` · `group` · `blank`). Cùng
  một dải hợp lệ trên hàng ghi chú và vô nghĩa trên hàng mặt hàng.
* **`prob`** — bao nhiêu phần hàng đủ điều kiện thì thật sự gộp. Đây là chỗ
  "tuỳ chỗ" trong câu hỏi: **cùng một bảng, hàng này gộp, hàng kia không** —
  vốn là hình dạng thật của một tờ mẫu, chứ không phải một quy luật đều.

Vị từ vẫn chạy sau cùng và vẫn có quyền phủ quyết: `prob: 1.0` mà hàng đó có số
ở cột bị phủ thì **không gộp**, và không báo lỗi — hàng ấy đơn giản là không đủ
điều kiện. Đó là điểm khác then chốt so với "gộp rồi sửa": không có gì để sửa,
vì nước đi không xảy ra.

### 3.2d · Chế độ thứ ba: hồ sơ gộp đo từ giấy thật

Hai chế độ trên đều dựa vào khai báo của người viết bố cục. Có một chế độ thứ
ba **chính xác hơn cả hai** khi có dữ liệu: **đo phân phối gộp từ chính các tờ
giấy thật** rồi lấy mẫu theo nó.

Đây là cách [*Synthesizing Realistic Data for Table
Recognition*](https://arxiv.org/abs/2404.11100) đi (§8), và số của họ nói nó
đáng: TEDS 0,9758 → 0,9847, lợi ích tập trung đúng ở bảng nhiều ô gộp. Điều
kiện: một tập tờ giấy thật **đã chú thích cấu trúc**. Repo chưa có, và đó là
lý do nó là chế độ thứ ba chứ không phải thứ nhất — nhưng nếu có thì `prob`
trong `row_merges:` không phải đoán nữa mà là **đo được**.

Ba chế độ xếp theo độ tin và theo giá:

| | bảo đảm bằng | cần gì | dùng khi |
| --- | --- | --- | --- |
| 1 · cấu tạo | cây cột | một khai báo | quan hệ có thật và ổn định |
| 2 · đề xuất+kiểm | vị từ không-nuốt-giá-trị | một phạm vi | gộp cục bộ, "tuỳ chỗ" |
| 3 · hồ sơ đo | phân phối thật | tờ giấy thật đã chú thích | khi có dữ liệu — thay `prob` đoán bằng `prob` đo |

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

## 4b. Trục thứ hai: biến thể ở mức **component**

Cột không phải trục duy nhất. Trang cũng là một dãy khối, và repo **đã** mô
hình hoá nó như vậy — chỉ chưa khai thác.

### 4b.1 Repo đã là kiến trúc component rồi

```yaml
sections: [letterhead, doctitle, parties, table, totals, words, signatures, footer]
```

Đó **chính là** "chọn component rồi sắp xếp". `rulebase/layout.py` giữ một sổ
đăng ký 15 component:

```python
SECTIONS = {"header": _emit_header, "strip": _emit_strip, "vat_summary": …,
            "meta": …, "columns": …, "items": …, "totals": …, "footer": …,
            "letterhead": …, "doctitle": …, "parties": …, "table": …,
            "words": …, "notes": …, "signatures": …}
```

và bố cục dùng 6–9 trong số đó. Nên ý tưởng "engine theo component" không phải
một kiến trúc thay thế — **nó là kiến trúc đang chạy**. Câu hỏi thật là câu
tiếp theo: *ai chọn, và bao lâu một lần* (trả lời bằng số ở
[`tu-dong-hoa-bang-llm.md` Phụ lục C](tu-dong-hoa-bang-llm.md#phụ-lục-c--kinh-tế-đặt-llm-ở-đâu-thì-rẻ)).

### 4b.2 Chỗ nó chưa đủ: component không có hợp đồng

```python
SECTIONS[name](builder, spec, receipt, columns, rng)
```

Mọi component nhận **toàn bộ** `spec`. Không có phạm vi, không khai mình cần
gì, không khai mình vẽ ra `role` nào, không khai phải đứng sau ai. Bốn hệ quả,
và cả bốn đều chặn đúng việc đang bàn:

| hệ quả | vì sao đau |
| --- | --- |
| thêm component phải sửa `layout.py` | trái với "thêm một trục là một file YAML" mà repo đã đạt được ở các trục khác |
| không kiểm được một `sections:` có mạch lạc không | `vat_summary` mà không có `table` là vô nghĩa; hôm nay không ai báo |
| không **xáo trộn / bỏ bớt** component một cách an toàn | tức là không có nước đi nào ở mức component |
| LLM không có thực đơn máy đọc được | nó phải suy ra 15 component từ văn xuôi trong README |

### 4b.3 Hợp đồng component

```python
@dataclass(frozen=True)
class Component:
    id: str
    emit: Callable                      # như hôm nay
    requires: frozenset[str] = frozenset()   # trường trên Receipt nó cần
    provides: frozenset[str] = frozenset()   # role nó vẽ ra
    after: frozenset[str] = frozenset()      # ràng buộc thứ tự
    optional: bool = False                   # có bỏ được không
    accepts: dict = field(default_factory=dict)   # schema RIÊNG của khối này
```

`accepts` là chỗ trả công lớn nhất và nó nối thẳng vào **M0** của tài liệu
chính: schema bố cục hôm nay là một khối phẳng bốn mươi khoá; chia theo
component thì mỗi khối tự khai khoá của mình, và câu lỗi đổi từ *"khoá lạ
`algin`"* thành *"`table.algin` không có — `table` nhận: frame, row_rules,
blank_rows, shade, border, header_groups…"*. Với một LLM đang sửa YAML của
chính nó, khác biệt đó là khác biệt giữa hội tụ ở vòng 1 và vòng 4.

`after` là chỗ diệt cả một lớp vô nghĩa mà không cần ai nghĩ: `doctitle` sau
`letterhead`, `vat_summary` sau `table`, `signatures` sau `totals`. Khai xong
thì **mọi thứ tự còn lại đều hợp lệ**, và bộ tăng cường được xáo trộn tự do
trong khoảng đó.

### 4b.4 Bốn nước đi ở mức component

| nước đi | ví dụ | hợp lệ khi |
| --- | --- | --- |
| `drop_component` | bỏ `notes`, bỏ `vat_summary` | `optional: true` **và** không component nào còn lại `requires` cái nó `provides` |
| `swap_component` | `meta` ↔ `strip` (hai cách in cùng khối khoá) | hai component `provides` cùng tập role |
| `reorder` | `words` trước hoặc sau `signatures` | không vi phạm `after` |
| `repeat_component` | `notes` xuất hiện hai lần, trên và dưới bảng | component khai `repeatable: true` |

Cùng vị từ của §3.2 áp ở mức khác: **một component chỉ bỏ được nếu không ai
đang dựa vào nó**, y như một ô chỉ gộp được nếu nó không nuốt giá trị nào. Một
luật, hai mức.

### 4b.5 Hai trục nhân với nhau

`invoice_vat_form` khai 8 section, trong đó (đề xuất) `notes` và `vat_summary`
là tuỳ chọn, `words`/`signatures` đổi được thứ tự:

```
2 (notes)  ×  2 (vat_summary)  ×  2 (thứ tự words/signatures)  =  8 biến thể component
                          ×
                48 cấu trúc cột (§4.3)
                          ×
                15 giá trị width
                          =
              5.760 trang khác nhau  —  từ MỘT file bố cục
```

Rồi mới nhân với bảy trục hiện có. Đây là lý do vì sao câu trả lời cho "phải
sinh nhiều layout data" **không phải** là sinh nhiều file: một file khai đủ
quan hệ đã cho hàng nghìn trang **chứng minh được là hợp lệ**, còn một file thứ
hai chỉ cho thêm một tờ giấy.

> **Cùng cảnh báo của §4.4 áp ở đây, mạnh hơn.** 5.760 biến thể của một tờ giấy
> **không** làm cho bộ dữ liệu đa dạng gấp 5.760 lần — chúng tương quan rất
> cao. Đa dạng thật vẫn đến từ **tờ giấy thứ mười bảy được đo từ ảnh thật**.
> Biến thể chống *overfit vào một cách trình bày*; nó không thay được việc đi
> đo thêm giấy. Ai đọc bảng nhân ở trên mà kết luận "khỏi cần thêm bố cục" thì
> đã đọc ngược.

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

### T1b · Hợp đồng component *(song song với T1)*
`Component` với `requires`/`provides`/`after`/`optional`/`accepts`; `SECTIONS`
thành sổ đăng ký có kiểu; `sections:` được kiểm mạch lạc; schema bố cục chia
theo khối (§4b.3) — **cùng lúc làm câu lỗi của M0 tốt hơn hẳn cho LLM**.
**Xong khi:** một `sections: [vat_summary]` không có `table` bị từ chối kèm lý
do, và thêm một component không phải sửa `build_grid`.
**Công:** 3–4 ngày.

### T2 · Bộ tăng cường + `rules/structure.yaml` *(sau T1, T1b)*
Chín nước đi ở mức cột (§3.2b) cộng bốn ở mức component (§4b.4), giải xung đột,
`make structures` và `make preview-structures`, trần biến thể trong `drift.py`.
Vị từ không-nuốt-giá-trị chạy cho `row_local_merge` **theo từng hàng**.
**Xong khi:** `make structures` in ra 48 cấu trúc cột × 8 biến thể component
cho `invoice_vat_form`, và mẫu ngẫu nhiên 100 trang trong số đó dựng được, qua
bất biến, `preview-grid` đọc được.
**Công:** 1–1,5 tuần.

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
| Gộp ngẫu nhiên trên **cả bảng**, không phạm vi, không vị từ | `tables.py` đã làm đúng cho bài của nó; ở đây nó tạo ra tờ giấy không tồn tại và làm đỏ bất biến đúng. Gộp cục bộ *có* phạm vi khai và *có* vị từ (§3.2c) thì khác — cái đó phải làm |
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
| [`duong-ong.md`](duong-ong.md) | đường ống vẽ đầy đủ — nước đi mức 3 và 4, vòng đời cái hộp, ai sở hữu toạ độ |
| [`brief-engine-html.md` §2](brief-engine-html.md) | đo và ghi lại: ảnh có ô gộp, nhãn không biết |
| [`rulebase/README.md` §3](../rulebase/README.md) | ngữ pháp file bố cục — `span:`, `columns:`, `item.rows:` |
| [`generators/html/sheets/base.py`](../generators/html/sheets/base.py) | `_header_rows` (nhóm tiêu đề thật) · `structure_tokens` · `_group_row` |
| [`generators/html/tables.py`](../generators/html/tables.py) | bộ sinh bảng ngẫu nhiên — bài khác, nhãn khác, giữ nguyên |
| [`tests/test_tables.py`](../tests/test_tables.py) | bốn oracle dùng lại được cho nhãn cấu trúc |
| [`rulebase/layouts/medical_statement.yaml`](../rulebase/layouts/medical_statement.yaml) | bố cục duy nhất đã khai `header_groups`, kèm lý do ngữ nghĩa |
