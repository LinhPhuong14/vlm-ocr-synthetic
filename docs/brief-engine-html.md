# Brief: sửa engine HTML để dựng bảng có ô gộp

> **Việc này đã làm xong.** Bản mô tả bên dưới giữ nguyên như lúc viết, vì nó
> là bản ghi những gì ĐO ĐƯỢC trước khi sửa. Kết quả và số liệu sau khi sửa nằm
> ở [§8](#8-đã-làm-gì-và-đo-lại-ra-sao) cuối trang; `a4.py` không còn nữa, chỗ
> của nó là [`generators/html/sheets/`](../generators/html/sheets).

Tài liệu này viết cho một agent nhận việc sửa `generators/html/`. Nó ghi lại
**những gì đã đo được**, không phải những gì phỏng đoán — kể cả chỗ triệu
chứng báo lại mà tôi tái hiện không ra.

---

## 1. Hiện có ba đường dựng trang, không phải một

Nhầm ba đường này với nhau là cách nhanh nhất để sửa sai chỗ.

| đường | vào bằng | dựng gì | mô hình bố cục |
| --- | --- | --- | --- |
| **lưới ký tự** | `render.py` (mặc định) | mọi bố cục trong `rulebase/layouts/` | `Grid` — mỗi ô là một `<span>` định vị tuyệt đối, đơn vị `ch` |
| **template CSS** | `render.py --template brand` | *một* tờ hoá đơn GTGT chung | `a4.py` — HTML thường, `<table>` thật, có `colspan`/`rowspan` |
| **sinh bảng** | `tables.py` | bảng ngẫu nhiên kiểu PubTabNet | ma trận `colspan`/`rowspan`, nhãn token PP-Structure |

Hai đường sau **đã có mô hình ô gộp đầy đủ và chạy đúng**. Tôi đã render và
xem tận mắt: `tables.py` gộp cột đầu bảng, gộp dòng cột đầu, ô bị nuốt đánh dấu
`-1`; `a4.py` có `_cell(..., colspan, rowspan)` và `structure_tokens()` xuất ra
đúng chuỗi token. Không có gì hỏng ở đó.

---

## 2. Lỗi cấu trúc đã chứng minh được

### `a4.build()` không hề đọc bố cục

```python
def build(recipe, receipt, theme: str = "brand") -> str:
    parse = receipt.ground_truth()
    ...
    rng = random.Random(recipe.seed ^ 0x5A4D)
```

Nó đọc `receipt.ground_truth()` và `recipe.seed`. **`recipe.layout.id` không
xuất hiện ở đâu trong hàm.** Hệ quả: `--template brand` vẽ cùng một tờ hoá đơn
GTGT cho cả 14 bố cục. Ép một tờ lưu trú qua đường này thì ra một tờ GTGT.

Đo được: ba bố cục khác hẳn nhau — `invoice_vat_summary`, `invoice_hotel_stay`,
`invoice_brand` — cho ra ảnh **cùng kích thước 1230×1740**, tức là cùng một
trang.

```bash
cd generators/html
for L in invoice_vat_summary invoice_hotel_stay invoice_brand; do
  python3 render.py -o /tmp/t/$L -c 1 --seed 31 --template brand \
      --force layout=$L --force augmentation=pristine
done
```

### Đường lưới ký tự không có mô hình ô gộp

`rulebase/layout.py` **mô phỏng** ô gộp chứ không mô hình hoá nó:

* `_paint_bars()` vẽ `|` xuống từng dòng và **bỏ qua** vị trí đã có ô chiếm chỗ.
  Một dòng tổng chạy ngang năm cột chỉ là "một ô rộng tình cờ không có gạch dọc
  cắt qua" — không đâu ghi rằng nó *gộp* cột 1 tới 5.
* `_resolve()` được gọi **riêng cho từng bảng**. Trang hoá đơn GTGT có hai
  bảng — bảng hàng và bảng "Tổng hợp" — nên hai bộ biên cột tính độc lập và
  không có gì buộc chúng thẳng hàng.
* Không có `colspan`/`rowspan` nào đi vào nhãn dữ liệu. Ảnh có ô gộp, nhãn thì
  không biết.

Đây đúng là chỗ "engine không hiểu logic merge dù code đã có sẵn": mô hình có
sẵn nằm ở `tables.py` và `a4.py`, còn đường lưới — đường mà 14 bố cục thật sự
chạy qua — thì không dùng nó.

---

## 3. Chỗ tôi KHÔNG tái hiện được: chữ đè lên chữ

Đã đo, không tìm ra. Ghi lại để agent khỏi mất công đi lại đường cũ.

Quét 18 lần render, 6 bố cục, đường lưới, tắt hẳn lớp làm cũ:

```
invoice_brand         chồng>30%: 0   cặp chạm nhau: 2
invoice_export        chồng>30%: 0   cặp chạm nhau: 2
invoice_vat_form      chồng>30%: 0   cặp chạm nhau: 3
invoice_vat_summary   chồng>30%: 0   cặp chạm nhau: 3
```

Thêm 12 lần render qua `--template`: **không một cặp box chữ nào giao nhau.**

Engine đã tự chặn sẵn nguyên nhân dễ ngờ nhất — chữ phóng to tràn ô:

```python
scale = min(cell.scale, width / max(len(cell.text), 1))   # render.py
```

Cỡ chữ bị kẹp theo bề rộng ô, nên một dòng tổng đặt 1.6em trong ô 20 ký tự sẽ
tự thu lại chứ không tràn.

**Giả thuyết còn lại, theo thứ tự đáng thử:**

1. **Lớp làm cũ, không phải engine.** Bản render đầu tiên tôi xem có lớp
   `augmentation` và *trông như* chữ dính vào nhau; bản `--force
   augmentation=pristine` cùng seed thì sạch. `ink_degradation` và
   `phantom_character` dán mực ra rìa chữ, và giữa hai dòng sát nhau thì mắt
   đọc ra "đè". Kiểm bằng cách render cùng seed hai lần, có và không có làm cũ.
2. **Bố cục hoặc seed ngoài phạm vi tôi quét.** Script đo nằm ở §6, chạy rộng
   ra là biết.
3. **Khổ giấy hẹp.** `width: [66, 78]` của `invoice_brand` là hẹp nhất; ô nào
   `fit()` cắt cụt thì không tràn, nhưng ô có `span` thì có thể.

Trước khi sửa, **hãy tái hiện và chụp lại**. Một bản vá cho triệu chứng không
tái hiện được là một bản vá không kiểm chứng được.

---

## 4. Hướng nên đi: lấy hình mẫu từ `samples/invoice-templates/`

Trong repo đã có **năm tờ HTML dựng tay**, mỗi tờ ứng với một bố cục, đặt tên
đúng bằng id bố cục:

```
samples/invoice-templates/invoice_vat_summary.html
samples/invoice-templates/invoice_export.html
samples/invoice-templates/invoice_hotel_stay.html
samples/invoice-templates/invoice_hotel_compact.html
samples/invoice-templates/invoice_brand.html
```

Chúng dựng bằng CSS thường: `<table>` thật, `colspan` thật, dòng chảy tự nhiên,
đơn vị `mm`, `@page`, **không một chỗ nào định vị tuyệt đối**. Chúng in ra đúng
một trang qua WeasyPrint (`make templates` từ chối tờ nào ra hai trang) và mở
được thẳng bằng trình duyệt.

Đó là hình dạng markup mà engine nên sinh ra. Việc cần làm là **tham số hoá
chúng từ `Receipt`**, một template cho mỗi họ bố cục, thay vì một
`a4.py` cứng duy nhất. Cụ thể:

* `a4.build(recipe, receipt)` chọn template **theo `recipe.layout.id`**, không
  phải theo `theme`.
* Ô gộp dùng `colspan`/`rowspan` của HTML — trình duyệt tự lo biên cột, nên hai
  bảng trên cùng trang thẳng hàng mà không ai phải tính.
* `structure_tokens()` xuất nhãn cấu trúc từ chính markup ấy, như `tables.py`
  đang làm.

---

## 5. Ràng buộc không được phá

Mỗi dòng dưới đây đều có một cơ chế trong repo canh nó. Phá là đỏ, không phải
là "hơi khác đi".

* **Hợp đồng box.** Mọi đoạn chữ có nhãn phải là `<span data-kind="...">`.
  `CELL_RECTS_JS` moi quad ra từ đó và không biết gì về template.
* **Nhãn phải bằng đúng chữ trên trang.** `a4.py` in từ
  `receipt.ground_truth()` chứ không từ các trường của `Receipt` — cố ý, để hai
  bên không trôi ra khỏi nhau.
* **`pipeline/invariants.py` báo LỖI** với mọi giá trị trong nhãn mà không box
  nào in ra, trừ các cặp (bố cục, trường) đã ghi trong `SUPPRESSED`.
* **Bất biến hình học của đường lưới** — `tests/test_layout.py`: không ô nào
  chồng ô nào, không ô nào tràn giấy, chữ vừa số cột nó chiếm.
* **Tất định.** Cùng seed phải ra cùng pixel. Không `Date.now()`, không RNG
  toàn cục.
* **Ba renderer phải so sánh được.** WeasyPrint lấy box từ lớp text của PDF chứ
  không từ DOM; template nào cũng phải chạy được ở đó — năm tờ trong
  `samples/invoice-templates/` đã chứng minh là được.
* **`make preflight`** có `sheet_overflow()`: bố cục nào tràn khổ giấy nó khai
  báo là bị bắt.

---

## 6. Script đo chồng lấn

Dùng chính box mà renderer xuất ra, nên nó đo cái engine thật sự vẽ chứ không
đo cảm nhận:

```python
import json, sys
from collections import defaultdict
from pathlib import Path

def rect(q):
    xs = [p[0] for p in q]; ys = [p[1] for p in q]
    return min(xs), min(ys), max(xs), max(ys)

def area(r):
    return max(r[2] - r[0], 0) * max(r[3] - r[1], 0)

def inter(a, b):
    return area((max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])))

bad = defaultdict(int)
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    item = json.loads(line)
    layout = item["recipe"]["attributes"]["layout"]["id"]
    boxes = [b for b in (item.get("boxes") or [])
             if b.get("kind") not in ("sep", "colnum") and (b.get("text") or "").strip()]
    rs = [(rect(b["quad"]), b) for b in boxes]
    for i in range(len(rs)):
        for j in range(i + 1, len(rs)):
            ra, ba = rs[i]; rb, bb = rs[j]
            if inter(ra, rb) / max(min(area(ra), area(rb)), 1) > 0.30:
                bad[layout] += 1
                print(f"{layout}: {ba['text'][:30]!r} ⟂ {bb['text'][:30]!r}")
print(dict(bad) or "không có chồng lấn")
```

```bash
cd generators/html
python3 render.py -o /tmp/sweep -c 20 --seed 1 --force augmentation=pristine
python3 overlap.py /tmp/sweep
```

---

## 7. Xong việc là khi nào

1. `--template` chọn template **theo `recipe.layout.id`**; ép một bố cục lưu
   trú qua đường template thì ra tờ lưu trú, không ra tờ GTGT.
2. Ô gộp là `colspan`/`rowspan` thật, và hai bảng trên cùng một trang có biên
   cột thẳng hàng — kiểm bằng chính box của renderer, không kiểm bằng mắt.
3. `structure_tokens()` xuất đúng chuỗi token cho trang có ô gộp.
4. Script §6 chạy trên ≥100 ảnh, mọi bố cục, báo **0** cặp chồng >30%. Nếu
   trước khi sửa nó đã báo 0 thì phải tìm ra và ghi lại tổ hợp làm nó khác 0,
   nếu không thì không có gì để sửa.
5. `make preflight`, `pytest tests`, `make lint` xanh; `pipeline/invariants.py`
   không có lỗi mới.
6. Cùng seed vẫn ra cùng pixel.

---

## 8. Đã làm gì, và đo lại ra sao

### Đường template: một `a4.py` → một họ template cho mỗi họ bố cục

`generators/html/a4.py` bị xoá. Thay vào là gói
[`generators/html/sheets/`](../generators/html/sheets):

| module | dựng | tờ mẫu tham chiếu |
| --- | --- | --- |
| `statutory.py` | tờ mẫu in sẵn: khối mẫu số, bảng kẻ ô, hai ô chữ ký | `invoice_vat_summary`, `invoice_export` |
| `lodging.py` | tờ lưu trú: khối đặt phòng, một dòng một đêm | `invoice_hotel_stay`, `invoice_hotel_compact` |
| `modern.py` | tờ tự thiết kế: không khung, tổng tiền nép lề phải | `invoice_brand` |
| `till.py` | giấy cuộn in nhiệt — để `--template` phủ được cả 14 bố cục | — |

`sheets.build(recipe, receipt)` chọn theo `recipe.layout.id`. Bố cục nào không
có trong `sheets.FAMILIES` là **lỗi có kèm danh sách**, không phải im lặng rơi
về tờ GTGT — vẽ tờ lưu trú thành tờ thuế đúng là khiếm khuyết mà gói này sinh
ra để sửa. Cái gì khác nhau GIỮA các thành viên một họ thì đọc từ chính file
bố cục: `sections:`, `columns:`, `item.rows:` — kể cả `span: [qty, amount]`,
tức một ô `colspan` thật.

### Đường genalog: WeasyPrint in đúng markup ấy *(đã xoá)*

> Mục này mô tả một backend không còn tồn tại. Giữ lại vì phần CSS nói ở cuối
> mục vẫn đang có trong `sheets/`, và ai đọc nó cần biết vì sao nó được viết
> như thế. Xem [`renderers.md`](renderers.md).

`generators/genalog/render.py --template` nhận cùng một chuỗi markup, đưa qua
`Document` của genalog (`templates/sheet.html.jinja` chỉ có `{{ content }}`).
Box lấy từ **lớp ký tự** của PDF chứ không phải lớp span: đo được rằng một
`<span>` của WeasyPrint có thể ôm hai `<td>` cạnh nhau — `"3 BÁNH CANH CUA"` là
ô số lượng dính ô tên hàng — nên cách nối span cũ chỉ tìm lại được 58% số
trường trên tờ giấy cuộn. Đi theo từng ký tự thì tìm lại được **100%**.

Ba chỗ phải sửa ở CSS để giữ được thứ tự ấy, và cả ba đều cùng một nguyên nhân:
**WeasyPrint vẽ hộp có `position` SAU hộp trong luồng**, nên một khối chữ được
định vị là một khối chữ rơi xuống cuối luồng ký tự. Đầu trang tờ lưu trú đổi
sang hai ô bảng; con dấu khách sạn thành `background`; dấu tick trong ô chữ ký
số thành `float`. Dấu chìm giữ `position:absolute` nhưng đẩy xuống `z-index:-1`
thay vì định vị mọi anh em của nó.

### Hộp của một dòng chữ xuống dòng

Cả hai backend cắt box **theo dòng**. Hình chữ nhật bao quanh một đoạn chữ đã
xuống dòng không phải là box quanh chữ: nó bao cả hai dòng *và khoảng giấy
trắng giữa hai đầu so le*, và trên một khối chạy hết bề ngang thì nó nuốt luôn
chữ đứng đầu dòng thứ nhất. Đo được: nhãn "Số tiền bằng chữ:" nằm gọn 100%
trong box của phần tiền viết bằng chữ. Chromium cắt bằng `Range`, WeasyPrint
cắt theo toạ độ dòng của ký tự.

### `make_content`: không phủ lưới ký tự lên nội dung trước

`build_grid` cắt giá trị không vừa cột ký tự rồi **ghi ngược** vào `Receipt` để
nhãn khớp trang đã vẽ. Tờ CSS không có cột ký tự, nên tờ dựng sau một lần
`build_grid` in ra "Hàng hoá không chịu thuế GTG" trên một dòng còn thừa chỗ.
`rulebase.make_content()` trả về `(recipe, receipt, rng)` và không dựng lưới;
hai backend CSS đi lối này.

### Số đo sau khi sửa

| phép đo | kết quả |
| --- | --- |
| `--template` chọn theo bố cục | 3 bố cục → 3 trang khác nhau, khác cả khổ giấy (§7.1) |
| script chồng lấn §6, 120 trang Chromium, đủ 14 bố cục | **0** cặp chồng >30% |
| script chồng lấn §6, 100 trang WeasyPrint | **0** cặp chồng >30% |
| `pipeline/invariants.py` trên 220 trang của cả hai backend | **0** lỗi, 15 718 box |
| tìm lại box từ PDF, 14 bố cục × 3 seed | **100%** số đoạn có nhãn |
| mọi dòng bảng cộng `colspan` bằng bề rộng bảng | `tests/test_sheets.py`, 14 bố cục × 3 seed |
| cùng seed → cùng pixel | 4 trang, ảnh và metadata giống nhau từng byte |
| `pytest tests`, `make lint`, `make preflight` | xanh |

Về §3 — chỗ "chữ đè lên chữ" mà bản brief này không tái hiện được: quét lại
trên đường template mới thì tìm ra **một** trường hợp thật, và nó không nằm ở
engine dựng trang mà ở phép ĐO box (đoạn chữ xuống dòng, ở trên). Giả thuyết
số 1 trong brief — lớp làm cũ chứ không phải engine — vẫn chưa bị bác bỏ, và
`--force augmentation=pristine` vẫn là cách kiểm nhanh nhất.
