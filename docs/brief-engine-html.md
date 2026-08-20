# Brief: sửa engine HTML để dựng bảng có ô gộp

Tài liệu này viết cho một agent nhận việc sửa `generators/html/`. Nó ghi lại
**những gì đã đo được**, không phải những gì phỏng đoán — kể cả chỗ triệu
chứng báo lại mà tôi tái hiện không ra.

---

## 1. Hiện có ba đường dựng trang, không phải một

Nhầm ba đường này với nhau là cách nhanh nhất để sửa sai chỗ.

| đường | vào bằng | dựng gì | mô hình bố cục |
| --- | --- | --- | --- |
| **lưới ký tự** | `render.py` (mặc định) | mọi bố cục trong `src/rulebase/layouts/` | `Grid` — mỗi ô là một `<span>` định vị tuyệt đối, đơn vị `ch` |
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

`src/rulebase/layout.py` **mô phỏng** ô gộp chứ không mô hình hoá nó:

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
* **`src/pipeline/invariants.py` báo LỖI** với mọi giá trị trong nhãn mà không box
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
python3 overlap.py /tmp/sweep/metadata.jsonl
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
5. `make preflight`, `pytest tests`, `make lint` xanh; `src/pipeline/invariants.py`
   không có lỗi mới.
6. Cùng seed vẫn ra cùng pixel.
