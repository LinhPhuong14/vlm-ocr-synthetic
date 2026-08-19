# Hướng dẫn chạy và giải thích code

Tài liệu này dành cho người đọc code lần đầu và cho buổi trình bày. Nó đi từ
"chạy được" tới "hiểu tại sao viết như thế".

Quy ước: mỗi mục đều chỉ rõ **hàm nào, trong file nào**, làm gì, và **tại sao
không viết theo cách hiển nhiên hơn** — phần cuối mới là phần đáng đọc, vì gần
như mọi chỗ "viết lạ" trong repo này đều là hậu quả của một lỗi đã gặp thật.

- [1. Chạy thử](#1-chạy-thử)
- [2. Đường đi của một tấm ảnh](#2-đường-đi-của-một-tấm-ảnh)
- [3. Phần dùng chung: `rulebase/`](#3-phần-dùng-chung-rulebase)
- [4. Framework 1 — synthdog (glyph)](#4-framework-1--synthdog-glyph)
- [5. Framework 2 — html (Chromium)](#5-framework-2--html-chromium)
- [6. Framework 3 — genalog (WeasyPrint)](#6-framework-3--genalog-weasyprint)
- [7. Phần dùng chung: `degradation/`](#7-phần-dùng-chung-degradation)
- [8. Kiểm thử](#8-kiểm-thử)
- [9. Q&A](#9-qa)

---

## 1. Chạy thử

### 1.1 Dựng môi trường

```bash
make setup          # dựng cả ba: setup-synthdog, setup-html, setup-genalog
```

Không có `make` (Windows chẳng hạn) thì gọi thẳng task runner — **mọi task định
nghĩa ở `tasks.py`**, `Makefile` chỉ forward, nên hai bên không thể lệch nhau:

```powershell
py -3.11 tasks.py setup
py tasks.py            # liệt kê task
```

Chi tiết Windows: [`windows.md`](windows.md).

Ba môi trường **không gộp được**. synthtiger ghim `pillow<10` (nó gọi
`ImageFont.getsize()`, API bị xoá ở Pillow 10) còn WeasyPrint đời mới cần
Pillow mới. Đây là mâu thuẫn thật, không phải sự cẩn thận thừa — xem
[`docs/python-versions.md`](python-versions.md).

Dựng riêng từng cái nếu chỉ cần một:

```bash
make setup-synthdog    # cần Python 3.8–3.11, Makefile chặn 3.12+
make setup-html        # playwright; KHÔNG chạy `playwright install`
make setup-genalog     # genalog vendor sẵn trong repo, xem §6
```

### 1.2 Xem trước, không cần render

Nhanh nhất để biết luật đang sinh ra cái gì:

```bash
make preview-grid              # mỗi bố cục một hoá đơn, in ra dạng chữ
make preview-grid LAYOUT=eatery_indexed
make distribution              # 2000 lần bốc, đếm theo từng thuộc tính
```

`make preview-grid` gọi `tools/preview_grid.py`, hàm `to_text(grid)` vẽ lưới ô
lên một canvas ký tự. Không đụng tới ảnh nên chạy được bằng **bất kỳ** Python
nào có PyYAML — kể cả khi chưa dựng môi trường nào.

### 1.3 Sinh dữ liệu

```bash
make dataset                     # 60 ảnh có làm cũ  -> data/dataset60/
make dataset-clean               # 60 ảnh sạch       -> data/dataset60_clean/
make dataset N=5 DATASET=/tmp/thu # 15 ảnh, thử nhanh
```

Chạy một renderer thôi:

```bash
generators/html/.venv/bin/python generators/html/render.py \
    -o /tmp/thu -c 5 --seed 100 --layout market_barcode
```

Ghim thuộc tính bất kỳ (lặp lại được):

```bash
--force augmentation=torn_edges --force visual=laser_sharp
```

### 1.4 Chấm điểm

```bash
make proof DATASET=data/dataset60
make proof DATASET=data/dataset60_clean
```

Đọc lại bằng Tesseract 5 (`vie`), chấm với nhãn, ghi
`<DATASET>/proof/{README.md, ocr_report.json, proof_*.jpg}`.

Số hiện tại — `token_recall`, đo lại sau W1b:

| bộ | synthdog | html | genalog |
| --- | ---: | ---: | ---: |
| có làm cũ | 0.454 | **0.611** | 0.578 |
| sạch | 0.851 | 0.881 | **0.882** |

Bảng cũ ở đây ghi 0.41 / 0.68 / 0.76 và kết luận genalog dễ đọc nhất. Sai hai
lần. Một: con số 0.76 chưa bao giờ có trong `ocr_report.json` — số thật lúc đó
là 0.638, và html 0.671 đã cao hơn rồi. Hai: ba renderer khi ấy vẽ **ba bộ hoá
đơn khác nhau** (xem `pipeline/plan.py`, `pairing`), nên ba cột đó không so
được với nhau dù số có đúng. Bảng trên là bộ đã sinh lại với `pairing: paired`,
cùng 20 hoá đơn cho cả ba renderer, `money_total` bằng nhau (101) ở cả ba cột —
đó mới là điều kiện để đọc bảng theo hàng ngang.

**Đọc bảng theo hàng dọc thì phải kèm điều kiện.** Từ W2e, mỗi
`ocr_report.json` ghi luôn *tập bố cục* nó chấm, vì làm cũ tốn của mỗi bố cục
một khoản rất khác nhau: `invoice_brand` mất 0.026 recall, `market_barcode`
mất 0.552 — gấp hai mươi mốt lần. Đổi tập bố cục là đổi số gộp, không cần đổi
gì khác. Hai bảng chỉ so được khi cùng tập; `tools/ocr_proof.py --against
<report>` tự kiểm tra điều đó, từ chối phần gộp khi khác nhau, và vẫn đưa phần
**theo từng bố cục** — phần giữ bố cục cố định, nên cái còn lại đúng là thứ đã
thay đổi.

Cột ngang trên vẫn đọc được vì cả hai bộ dùng đúng một tập 14 bố cục và đúng
20 hoá đơn.

### 1.5 Kiểm tra trước khi commit

```bash
make check           # mọi file .py parse được, không cần thư viện
make lint            # ruff
make check-rules     # giá trị không bao giờ bốc trúng, thẻ gõ sai, file thiếu
make check-corpus    # corpus thiếu file, sai số cột
```

`make check-rules` là cái hay bị quên. Gõ sai một thẻ **không báo lỗi**: giá
trị mang thẻ đó đơn giản là không bao giờ được bốc, sinh ảnh vẫn chạy, và một
tháng sau mới phát hiện bố cục đó chưa từng xuất hiện trong dataset.

---

## 2. Đường đi của một tấm ảnh

```
  rulebase.sample_recipe(seed)      bốc 6 thuộc tính  ->  Recipe
            │
  rulebase.build_receipt(recipe)    điền nội dung     ->  Receipt (thuần dữ liệu)
            │
  rulebase.build_grid(receipt, …)   xếp lên lưới ký tự -> Grid (ô + hàng + cột)
            │
     ┌──────┴───────┬───────────────┐
  synthdog         html          genalog          ← ba cách vẽ CÙNG một Grid
     │              │                │
     └──────┬───────┴───────────────┘
  degradation.pipeline.apply_recipe  làm cũ         ->  ảnh cuối
```

Ba dòng đầu gói trong một hàm: `rulebase.make(seed, force)` trong
`rulebase/__init__.py`.

**Tại sao tách `Receipt` (dữ liệu) khỏi `Grid` (vị trí)?** Vì nhãn phải dựng từ
`Receipt`, còn ảnh dựng từ `Grid`. Nếu gộp làm một thì mỗi renderer sẽ tự quyết
định "dòng này in gì", và ba renderer sẽ trôi khỏi nhau — lúc đó so sánh ba
renderer thực chất là so sánh ba bộ dữ liệu khác nhau, vô nghĩa.

---

## 3. Phần dùng chung: `rulebase/`

### 3.1 `spec.py` — bốc mẫu

| hàm | làm gì |
| --- | --- |
| `load_rules(root)` | đọc `rules/<thuộc tính>.yaml` cho cả 6 thuộc tính |
| `Option.from_dict(raw, attribute)` | dựng một giá trị; **từ chối khoá lạ** |
| `Option.allowed(tags)` | `requires ⊆ tags` và `excludes ∩ tags = ∅` |
| `_weighted_choice(options, rng)` | bốc theo trọng số |
| `sample_recipe(seed, rules, force)` | vòng lặp chính, bốc 6 thuộc tính theo thứ tự |
| `parse_force(items, layout)` | `["augmentation=x"]` → `{"augmentation": "x"}` |
| `validate(rules)` | tìm giá trị không bao giờ bốc được |

**Vòng lặp chính** trong `sample_recipe`:

```python
for attribute in ATTRIBUTES:            # document, layout, content, visual, color, augmentation
    candidates = [o for o in rules[attribute] if o.allowed(tags)]
    chosen = _weighted_choice(candidates, rng)
    tags |= chosen.tags
```

**Tại sao bốc tuần tự có trạng thái, mà không bốc độc lập 6 chiều rồi lọc?**
Bốc độc lập thì phần lớn tổ hợp là vô nghĩa (máy in nhiệt 2011 in chữ có dấu;
hoá đơn quán nhậu có cột mã vạch) và tỉ lệ bị loại sẽ rất cao — muốn giữ phân
phối đúng thì phải rejection sampling, chậm và khó suy luận. Bốc tuần tự đảm
bảo **mọi recipe sinh ra đều hợp lệ ngay từ đầu**.

**Tại sao thứ tự đúng là `document → … → augmentation`?** Vì đó là thứ tự nhân
quả thật: cửa hàng chọn in cái gì từ rất lâu trước khi tờ giấy quyết định nó sẽ
bị nhàu ra sao. Nhờ vậy `augmentation` — thuộc tính hẹp nhất — nhìn thấy **mọi**
thẻ phía trên, và viết được ràng buộc như `crumpled` chỉ áp cho `thermal`.

**Tại sao `Option.from_dict` từ chối khoá lạ?** Vì tham số của model nằm dưới
`params:`. Gõ nhầm `level: 5` ở cấp ngoài thay vì trong `params:` sẽ **im lặng
bị bỏ qua** nếu không kiểm tra — model vẫn chạy với giá trị mặc định, ảnh vẫn
ra, và không có gì báo sai.

**`make(seed, force, attempts)` trong `__init__.py`** có vòng thử lại: ghim một
thuộc tính có thể xung đột với thứ đã bốc trước đó (bố cục siêu thị trên một
seed đã bốc ra quán nhậu), nên seed được tăng dần tới khi ghim vừa. Recipe trả
về báo đúng cái seed đã dùng, không phải seed bạn truyền vào — nếu không thì
`recipe.seed` không dựng lại được ảnh.

### 3.2 `content.py` — điền nội dung

| hàm | làm gì |
| --- | --- |
| `build(recipe, rng)` | hàm chính; trả `Receipt` |
| `_build_store(profile, rng, case)` | tên/địa chỉ/điện thoại, khác nhau giữa quán và siêu thị |
| `_build_items(profile, rng, case, params)` | danh sách mặt hàng, giá, khuyến mãi, hàng cân |
| `_build_meta(profile, rng, case, params)` | số phiếu, ngày giờ, quầy, NVBH |
| `Item.display_qty()` / `display_unit_price()` | cột SL và đơn giá cho hàng cân |
| `Receipt.ground_truth()` | nhãn CORD lồng nhau |
| `Receipt.text_sequence()` | nhãn đọc-trơn |

**`Item.display_qty()` — chi tiết dễ bỏ sót.** Hàng cân (0,406 KG) in ra **SL =
1**, còn đơn giá cột hiển thị là *thành tiền của lần cân đó*; khối lượng thật và
giá theo kilo nằm ở dòng tên hàng. Đó là cách máy tính tiền in thật (xem ảnh mẫu
VinCommerce). Trước khi có hàm này, cột SL rộng 4 ký tự nhận chuỗi `0,406` và bị
cắt thành `0.40`.

Nhãn dùng đúng `display_*`, còn khối lượng thật đi kèm ở trường riêng
(`weight`, `unitprice_per_unit`). **Nguyên tắc: nhãn mô tả cái được in, không
phải cái được bốc.**

**`Receipt.grand_index`** — chỉ số dòng "tiền phải trả" trong `totals`. Không
phải dòng cuối: sau nó còn "tiền khách đưa" và "tiền thối lại". Trước khi có
trường này, `_emit_totals` in **dòng tiền thối** ở cỡ 1.6em đậm.

### 3.3 `layout.py` — xếp lên lưới

| hàm | làm gì |
| --- | --- |
| `build_grid(receipt, layout_id, rng)` | hàm chính |
| `_resolve_columns(spec, ncols)` | quy width tương đối thành `[col0, col1)` thật |
| `_span(entry, columns, builder)` | vị trí một ô: span, cột có tên, hay cả bề ngang |
| `_emit_header/_meta/_column_header/_items/_totals/_footer` | sinh từng khối |
| `_case(receipt, text)` | đưa chuỗi trong YAML qua chính tả của hoá đơn |
| `_item_values(item, receipt)` | mọi nguồn dữ liệu dùng được trong `from:` |

**`_resolve_columns` chừa "gutter".** Mỗi cột trừ cột cuối nhường lại một ký tự.
Không có nó thì số canh phải chạm sát cột kế tiếp: `112,000BUN BO HUE`.

**`_emit_items` giữ con trỏ dòng ở dòng đầu.** Tên hàng dài ngắt xuống 3 dòng
nhưng giá/SL/thành tiền vẫn phải nằm ở **dòng đầu tiên**, nên hàm ghi lại
`base`, đặt `builder.row = base + offset` cho từng dòng của tên, rồi mới
`builder.row = base + extra` ở cuối. Viết tuần tự "put xong rồi newline" sẽ đẩy
giá xuống dòng cuối của tên hàng — hoá đơn WinMart nhìn là biết sai ngay.

**`_case` áp cho cả chuỗi trong YAML.** Tiêu đề cột (`Số lượng`, `Giá`) nằm
trong file bố cục chứ không nằm trong corpus, nên không có gì bỏ dấu chúng. Kết
quả trước khi sửa: hoá đơn máy in nhiệt 2011 in `Số lượng` phía trên các món tên
`BUN RIEU CUA`.

**Cắt chuỗi thì ghi ngược vào nhãn.** `_emit_header` và `_emit_items` khi phải
`fit()` một chuỗi dài đều gán lại vào `receipt.store.<field>` / `item.name`.
Nhãn dựng sau, từ chính các object đó, nên không thể khai một chuỗi mà ảnh không
in. Đo trên 400 seed: trước khi sửa là 0.8% chuỗi nhãn không có trong ảnh, sau
khi sửa là 0.

### 3.4 `style.py` — màu và lề

| hàm | làm gì |
| --- | --- |
| `fade(colour, gray)` | kéo màu mực về phía trắng |
| `inks(recipe, rng)` | mực, mực nhấn, ám giấy |
| `padding(recipe, grid, rng)` | lề trên / dưới / trái phải |

**`fade` kéo về trắng chứ không nhân.** Nhân sẽ làm mực xanh hoá xám khi nhạt;
kéo về trắng thì mực nhạt vẫn còn màu, đúng như hộp mực sắp hết.

**Tại sao hai hàm này nằm ở `rulebase` chứ không ở từng renderer?** Vì đã từng
nằm ở từng renderer và **trôi mất**: `ink_gray` được renderer glyph áp dụng còn
hai renderer HTML bỏ qua, nên so sánh ba renderer âm thầm biến thành so sánh
"có áp thuộc tính" với "không áp". Lề cũng vậy — ba con số khác nhau ở ba nơi.

**`padding` có sàn cứng:** `max(padding_top, tallest + 0.5)`. Tên cửa hàng in to
(1.15–1.65em, và cỡ đó cũng bốc ngẫu nhiên theo bố cục) tràn lên trên khỏi hộp
dòng. Một con số cố định không bao giờ bảo đảm được điều này vì nó không biết
recipe bốc ra cỡ bao nhiêu.

### 3.5 `text.py` và `corpus.py`

`wrap(text, width)` ngắt dòng bằng `re.split(r"(\s+)")` **giữ nguyên dấu cách**.
`textwrap.fill` gộp các dấu cách liên tiếp, nên renderer glyph và renderer HTML
sẽ bắt đầu dòng ở cột khác nhau.

`ascii_fold` là **một chiều**: corpus luôn lưu có dấu, bỏ dấu lúc render. Từ
"Hẹn gặp lại" ra "Hen gap lai" được, ngược lại thì không.

`corpus._columns` **bỏ qua** dòng sai số cột thay vì raise. Corpus sửa bằng tay,
một dòng hỏng chỉ nên tốn dòng đó.

`corpus.items(profile)` nhận `"eatery"` hoặc `"market"` và ghép thẳng vào tên
file (`items_eatery.txt`). Nghĩa là **`profile` trong `rules/document.yaml` là
tên file, không phải một enum riêng** — thêm một profile mới chỉ cần thêm ba
file corpus cùng hậu tố, không phải sửa `corpus.py`. Đổi lại, gõ sai `profile`
sẽ nổ ở `FileNotFoundError` chứ không ở chỗ validate; `make check-corpus` chạy
đúng để bắt chuyện đó trước.

**Tại sao `profile` là `eatery`/`market` chứ không phải `quan`/`sieuthi`?**
Ranh giới đặt tên trong repo này chạy theo *thứ có đi vào ảnh hay không*: `id`,
`tags`, `profile`, tên texture — code so sánh, nên tiếng Anh; `titles`,
`total_labels`, `title:` của cột, toàn bộ `corpus/vi/` — in lên tờ giấy, nên
tiếng Việt. Dịch nốt vế sau là đổi bộ dữ liệu chứ không phải đổi tên biến.

---

## 4. Framework 1 — synthdog (glyph)

**Bản chất:** vẽ từng ô chữ bằng `synthtiger.layers.TextLayer`, rồi làm cong tờ
giấy, thả lên nền và "chụp lại". Kết quả trông như **ảnh chụp** hoá đơn nằm
trên bàn.

### 4.1 Các file

| file | vai trò |
| --- | --- |
| `elements/receipt.py` | đổi `Grid` thành danh sách `TextLayer` |
| `template_receipt.py` | điều phối 4 bước dựng ảnh, lưu nhãn |
| `render.py` | chạy template trực tiếp, chọn seed, ghim bố cục, `--clean` |
| `elements/warp.py` | `CurlWarp` — cong giấy, **có map lại toạ độ** |
| `config_vi_receipt.yaml` | chỉ còn tham số riêng của renderer này |

### 4.2 `elements/receipt.py` → `Receipt.generate(seed, force)`

Các bước, theo thứ tự trong hàm:

1. `rulebase.make(seed, force)` — lấy recipe/receipt/grid.
2. `self._fonts(visual["font_dir"])` — danh sách font.
3. `rulebase.inks(recipe, rng)` — màu mực.
4. Đo `char_w` và `line_h` bằng một `TextLayer` mẫu `"0"*10`.
5. `rulebase.padding(recipe, grid, rng)` — lề.
6. Với mỗi ô: dựng `TextLayer`, scale, kẹp trong cột, canh lề, đặt `top`.

**`_fonts(group)` ưu tiên `resources/font/<group>` rồi mới tới `fonts/` ở gốc
repo.** Lý do: `fonts/` là bộ dùng chung, phát hành lại được, commit trong repo;
`resources/font/` là chỗ để font riêng của bạn mà `.gitignore` giữ ngoài repo.
Có thì dùng cái riêng.

**Tại sao đo `char_w` bằng `"0"*10 / 10` mà không đo một ký tự?** Sai số làm
tròn của một ký tự nhân lên 48 lần bằng cả một cột. Đo 10 ký tự rồi chia thì sai
số chia mười.

**Tại sao `line_h` đo bằng chữ số vẫn đúng cho chữ có dấu?**
`TextLayer.height` là **chiều cao dòng của font**, không đổi theo nội dung. Tôi
đã thử "sửa" chỗ này bằng probe `"ẦỄjgQ"` và ảnh ra **y hệt byte-for-byte** —
nên đã revert và ghi chú lại. Đây là một giả thuyết sai, không phải một bug.

**Tại sao một `TextLayer` cho cả chuỗi, không phải một layer mỗi ký tự?**
`elements/textbox.py` của SynthDoG gốc tạo một layer **mỗi ký tự** — đo được
~2.7 ms/ký tự. Một hoá đơn ~40 dòng dày chữ thì cách đó không dùng được.

**Kẹp cỡ chữ trong cột:**

```python
if layer.width > span:
    layer.size = layer.size * (span / layer.width)
```

Dòng tổng tiền in 1.6em có thể rộng hơn cột của nó. Không kẹp thì số tiền chạy
ra ngoài mép giấy. Hai renderer kia làm y hệt (§5.2, §6.2) — nếu chỉ một
renderer kẹp thì cùng recipe lại ra hai kết quả khác nhau.

### 4.3 `template_receipt.py` → `SynthVNReceipt.generate(force)`

Bốn bước, **cố ý theo đúng thứ tự vật lý**:

```
1. vẽ chữ lên tờ giấy trắng      -> doc_group.output()
2. chạy chuỗi làm cũ của recipe   -> apply_recipe(rgb[..., ::-1], …)[..., ::-1]
3. làm cong tờ giấy               -> self.curl.apply(doc_image, quads, meta)
4. đặt lên nền và chụp            -> layers.Group([doc, bg]).merge(); self.effect.apply
```

**Tại sao làm cũ ở bước 2 chứ không phải bước 1?** Nếu texture giấy được dán
trước khi vẽ chữ thì nó bị kéo giãn theo layer chữ; nếu dán sau bước 4 thì nó
phủ luôn lên **nền**, tức là bàn cũng có vân giấy. Bước 2 là chỗ duy nhất mà
"tờ giấy đã có chữ, chưa bị cong, chưa ghép nền".

**`[..., ::-1]` hai lần** là đổi RGB↔BGR: synthtiger làm việc bằng RGB,
`degradation` viết trên OpenCV nên dùng BGR.

**Hệ số cong lấy từ recipe:**

```python
curl_meta = self.curl.sample()
strength = float(recipe.get("visual", "curl", 1.0))
for key in ("shift", "squeeze", "wave"):
    curl_meta[key] *= strength
```

Giấy nhiệt mỏng cong nhiều (`curl: 0.9`), hoá đơn laser trên A5 gần như phẳng
(`0.25`). Trước khi nối vào recipe, tờ nào cũng cong như nhau.

**`wave` là tham số nguy hiểm nhất** và config ghi rõ điều đó. `c_of(x)` trong
`elements/warp.py` lệch **dọc theo cột**, nên nó là thứ duy nhất phá vỡ việc các
ô cùng một dòng nằm cùng một hàng. Quá 0.004 thì cột tiền tụt xuống dòng dưới so
với cột tên hàng và OCR đọc thành hai dòng khác nhau — đã gặp thật, ảnh trông
như nhãn bị lệch.

**Tại sao viết `CurlWarp` riêng mà không dùng `components.ElasticDistortion`?**
ElasticDistortion **chỉ warp pixel, không cập nhật toạ độ**. Méo mạnh là box
lệch khỏi chữ. `CurlWarp` định nghĩa biến dạng bằng công thức giải tích, tách
làm 2 lượt, mỗi lượt khả nghịch trên một trục:

```
lượt 1 (theo hàng y):  x' = a(y)·(x − cx) + cx + b(y)
lượt 2 (theo cột x'):  y' = y + c(x')
```

nên vừa dựng được ánh xạ ngược cho `cv2.remap` (ảnh), vừa map xuôi được 4 góc
của từng ô (nhãn).

**`self._counter`.** synthtiger gọi `generate()` không truyền chỉ số, nên seed
tự đếm trong template; `seed_base` cho phép chạy lần hai mà không trùng ảnh.

### 4.4 `render.py` → `make_clean(config)`

Tắt **mọi thứ renderer này làm sau bước dựng cấu trúc**: `curl.prob = 0`, mọi
`prob` trong `doc_effect`/`effect` về 0, `quality` lên 93–97, và:

```python
config["canvas_fill"]   = [1.0, 1.0]
config["canvas_aspect"] = [4.0, 4.0]
```

`canvas_w = max(dw / fill, canvas_h / aspect)`, nên aspect lớn hơn tỉ lệ
cao/rộng của hoá đơn (~2) làm số hạng thứ hai thua, và khung ảnh ra đúng bằng
tờ giấy — không lộ nền.

**Tại sao `--clean` cần tồn tại riêng, không chỉ dùng
`--force augmentation=pristine`?** Vì ghim thuộc tính chỉ làm rỗng chuỗi
degradation. Renderer này còn nguồn biến dạng thứ hai mà hai renderer HTML
không có. Không tắt nó thì "không augmented" chỉ đúng với 2/3 renderer.

---

## 5. Framework 2 — html (Chromium)

**Bản chất:** mỗi ô là một `<span>` định vị tuyệt đối trên lưới ký tự, chụp màn
hình bằng Chromium. Kết quả trông như **bản quét phẳng**.

### 5.1 Các file

| file | vai trò |
| --- | --- |
| `render.py` | toàn bộ renderer, ~260 dòng |
| `requirements.txt` | playwright, numpy, opencv-headless, pillow, PyYAML |

### 5.2 `build_html(grid, recipe, receipt)`

Sinh HTML. Ba quyết định đáng nói.

**(a) Định vị bằng `ch`, không bằng `px`.**

```python
style = (f"left:{left:.3f}ch;top:{pad_top + cell.row * line_px:.2f}px;"
         f"width:{width}ch;text-align:{cell.align};…")
```

`1ch` = bề rộng ký tự của font mono. Một cột trong trình duyệt rộng đúng một ký
tự, y như trên lưới. Đó là thứ làm hai renderer **so sánh được ở mức pixel**,
chứ không chỉ "cả hai đều ra hoá đơn".

**(b) Phóng to ở thẻ trong, không ở thẻ ngoài.**

```html
<span style="left:…ch;width:…ch;text-align:right"><i style="font-size:1.5em">794,000</i></span>
```

`ch` tính theo font-size **của chính element đó**. Phóng to thẻ ngoài sẽ phóng
to luôn lưới: dòng tổng tiền 1.5em bị canh phải vào một hộp rộng dư 1.5 cột và
**chạy ra ngoài mép giấy**. Thẻ ngoài giữ cỡ chữ của sheet nên vẫn nằm trên
lưới; chỉ thẻ trong to lên.

**(c) Lề trên cộng thẳng vào `top`, không dùng `padding`.**

```
height:{grid.nrows * line_px + pad_top + pad_bottom:.2f}px;
```

**`padding` của CSS không đẩy được con `position:absolute`** — chúng bám vào
*padding box* của cha, nên đặt `padding-top` bao nhiêu cũng vô hiệu. Đây là lỗi
đã gặp: lần sửa đầu tiên đặt `padding` đúng mà tên quán vẫn sát mép trên.

**`_font_faces()` nhúng font từ `fonts/` bằng `@font-face`.** Không để CSS stack
rơi xuống font nào máy có sẵn: một font thiếu dấu tiếng Việt sẽ vẽ ô vuông trong
khi nhãn vẫn khai là đã in chữ có dấu — **lỗi này không tự báo ra**.

### 5.3 `HtmlReceiptRenderer`

`__enter__` / `__exit__` giữ **một** trình duyệt sống suốt cả lần chạy. Mở
browser tốn ~300 ms; với 20 ảnh là 6 giây lãng phí.

`find_chromium()` dò `/opt/pw-browsers` trước. Trong container Claude Code đã có
sẵn bản build; **không chạy `playwright install`** — nó tải lại vài trăm MB.

`render(seed, force)`: chụp `#sheet` → `cv2.imdecode` → **thu nhỏ** về
`short_size` (960–1400) → `apply_recipe`.

**Tại sao render to rồi thu nhỏ, không render đúng cỡ?** Thu nhỏ giữ chữ nét
(hiệu ứng antialias tốt), phóng to thì không. Và nó đưa ảnh về đúng dải kích
thước của renderer glyph, nên hai bên so được ở mức pixel.

### 5.4 Cố ý khác gì

Trình duyệt mang theo text shaping, font fallback, giả lập chữ đậm. Ảnh ra là
**bản quét phẳng**: không nền, không phối cảnh, không ánh đèn. Đó là một phân
phối khác hẳn renderer glyph — và là lý do giữ cả ba.

---

## 6. Framework 3 — genalog (WeasyPrint)

**Bản chất:** dựng document bằng Jinja2 + WeasyPrint qua chính API của
[genalog](https://github.com/microsoft/genalog), in ra PDF rồi raster. Kết quả
trông như **bản in / photocopy**.

### 6.1 Các file

| file | vai trò |
| --- | --- |
| `render.py` | renderer |
| `templates/receipt.html.jinja` | template hoá đơn (của mình) |
| `requirements.txt` | weasyprint, pymupdf, jinja2, … |

### 6.2 Cái gì của genalog, cái gì của mình

Template prose của genalog (`text_block`, `columns`, `letter`) **không có khái
niệm cột đo bằng ký tự**, mà cuộn giấy in nhiệt thì đúng là thế. Nên template
là của mình; còn lại là của genalog: `DocumentGenerator` nạp template từ thư mục
của mình, `Document` biên dịch, WeasyPrint vẽ.

`cells_for_template(grid, recipe, line_px, pad_ch)` làm phẳng `Grid` thành list
dict cho Jinja2 lặp. `styles_for(...)` dựng biến style, trong đó có cùng phép
kẹp cỡ chữ như hai renderer kia:

```python
"scale": f"{min(cell.scale, width / max(len(cell.text), 1)):.3f}",
```

### 6.3 Hai chỗ phải lách

**(a) Dựng `Document` thẳng từ template env, không qua `create_generator()`.**

```python
template = self.generator.template_env.get_template(TEMPLATE)
document = Document(cells, template, **styles_for(...))
```

`create_generator()` yield ra `Document` **đã biên dịch sẵn với style prose mặc
định của genalog** — template này không hiểu chúng, nên nó nổ ngay lần render
đầu, trước khi `update_style()` kịp truyền style thật (`'tint_alpha' is
undefined`).

**(b) `render_png()` không dùng được.** Nó gọi `write_png()` của WeasyPrint,
API bị xoá ở WeasyPrint 53. `_rasterise(pdf)` lấy `render_pdf()` rồi raster
bằng PyMuPDF, ghép dọc nếu WeasyPrint tách trang.

**Ghim phiên bản của genalog:** `numpy==1.18.1`, `WeasyPrint==51`,
`scikit-image==0.16.2`, `Jinja2==2.11.1` — **không cái nào có wheel cho Python
3.9+**. Source của genalog **vendor thẳng vào `generators/genalog/`** nên các
ghim đó không áp dụng; dependency lấy từ `requirements.txt` ở phiên bản có
thật. Đường code mình gọi (`DocumentGenerator`, `Document`, `render_pdf`) chỉ
cần Jinja2 và WeasyPrint, cả hai đều ổn định ở phần template này dùng.

Một hệ quả phải biết: `render.py` nằm cùng thư mục với cây vendor, nên
`generators/genalog/` là `sys.path[0]` mỗi khi nó chạy và `import genalog`
**luôn lấy cây vendor**, kể cả khi pip có cài một bản khác. Vì thế
`setup-genalog` cố tình không cài genalog từ PyPI — hai bản mà một bản che bản
kia là đúng loại bẫy im lặng.

**Tại sao vẫn giữ genalog mà không tự viết WeasyPrint?** Vì nó là một **đường
render khác thật**: print engine có page box, phân trang thật, text shaper
riêng. Model chỉ nhìn ảnh chụp màn hình trình duyệt thì chưa từng gặp nó.

Chỗ này trước đây viết "genalog là renderer dễ đọc nhất ở bộ có làm cũ (0.76)".
Bỏ. Trên cùng một bộ hoá đơn (`pairing: paired`, W1b) genalog được **0.659**,
thấp hơn html **0.729**. Lý do giữ genalog không phải vì nó dễ đọc nhất — mà vì
nó là đường render thứ ba, và đó là lý do đủ.

---

## 7. Phần dùng chung: `degradation/`

Port các model của [DocCreator](https://github.com/DocCreator/DocCreator).
Chi tiết ở [`degradation/README.md`](../degradation/README.md); ở đây chỉ nói
phần kiến trúc.

`pipeline.apply_recipe(image, recipe, seed)` — **cả ba renderer đều gọi hàm
này**, ở cùng một điểm: sau khi vẽ xong tờ giấy, trước khi ghép nền. Không có
nó thì "so sánh ba renderer" biến thành "so sánh ba cách làm cũ khác nhau tình
cờ trùng tên".

Nó điền tờ giấy từ `visual.paper` của recipe, nên cùng recipe thì cùng tờ giấy
dưới cả glyph lẫn HTML. Chuỗi lấy từ `rules/augmentation.yaml`.

Thứ tự trong chuỗi **không hoán vị được**: mực mòn rồi mới nhoè = "chữ cũ bị
scan dở"; nhoè rồi mới mòn = "vết lem". `paper_texture` luôn đứng đầu — mọi thứ
sau nó là hư hại lên một tờ giấy đã tồn tại.

Ba model đáng nói nhất: `ink_degradation` (mô hình nhiễu cục bộ của Kieu),
`gradient_domain` (ghép vết bẩn bằng Poisson blending, Seuret và cs. ICDAR
2015), `holes` (rách/xé, phần mất lấp bằng **đen** — mặc định của DocCreator).

---

## 8. Kiểm thử

Từ W0, repo có bộ test `pytest` (`pytest -q`, chạy trong CI, chỉ cần pytest và
pyyaml) phủ **tầng dữ liệu**: luật, bố cục, nội dung, kế hoạch, bất biến từng
ảnh. Phần *ảnh* thì không: assert trên pixel vừa giòn vừa không phát hiện được
thứ sai thật sự (chữ đè lên nhau, nhãn không khớp ảnh). Chỗ đó dùng năm công cụ.

| công cụ | bắt được gì |
| --- | --- |
| `pytest -q` | luật, bố cục, số học nội dung, kế hoạch shard, bất biến từng ảnh |
| `make check-rules` | thẻ gõ sai, giá trị không bao giờ bốc trúng, bố cục/giấy/degradation không tồn tại |
| `make check-corpus` | corpus thiếu file, sai số cột |
| `make preview-grid` | bố cục sai — nhìn bằng chữ, nhanh hơn nhìn JPEG rất nhiều |
| `make proof` | nhãn có khớp ảnh không, ảnh có đọc được không |
| `make baseline-verify` | pixel có đổi không, và **vì lý do gì** — "kế hoạch đã đổi" khác hẳn "cùng kế hoạch, khác pixel" |

**`make proof` trên bộ sạch là bài test nhãn rẻ nhất.** Nhãn sai thì bộ sạch
cũng không thể đạt 0.8. Bộ sạch gần như đồng đều giữa ba renderer
(0.851 / 0.881 / 0.882) — chênh lệch ở bộ làm cũ (0.454 / 0.611 / 0.578)
**là do làm cũ**.

Suy luận đó chỉ đứng được từ W1b trở đi. Trước W1b ba renderer vẽ ba bộ hoá đơn
khác nhau, nên "bộ sạch đồng đều ⇒ chênh lệch là do làm cũ" là so ba corpus
khác nhau rồi quy kết cho một biến. Giờ cả ba vẽ **cùng 20 hoá đơn**
(`pairing: paired`), `money_total` bằng nhau 101/101/101, và câu trên là một
phép so sánh có cặp thật.

Nhưng nó chỉ đọc được **theo hàng ngang**. So một con số gộp với một con số
gộp cũ thì phải cùng tập bố cục: làm cũ tốn `invoice_brand` 0.026 recall và
`market_barcode` 0.552, gấp hai mươi mốt lần, nên đổi tập bố cục là đổi số gộp.
Đó là lý do `ocr_report.json` ghi luôn điều kiện của chính nó từ W2e, và
`--against` từ chối phần gộp khi hai bộ khác tập.

Chấm điểm trong `tools/ocr_proof.py` **không phụ thuộc thứ tự đọc**: Tesseract
đọc hoá đơn hai cột theo thứ tự do layout analysis của nó quyết, nên so chuỗi
với nhãn sẽ đo *thứ tự đọc* chứ không phải *khả năng nhận dạng*. Thay vào đó:
`token recall` (bao nhiêu token in ra được đọc lại), `field hit` (mỗi trường đạt
≥70% token thì tính là đọc được), `money exact` (số tiền phải đúng từng ký tự).

`locate_page(grey)` cắt về tờ giấy trước khi OCR. Renderer glyph ghép hoá đơn
lên nền tối, mà Tesseract nhị phân hoá toàn cục: có nền tối trong khung thì
ngưỡng rơi vào giữa nền và giấy, chữ xám trên giấy trắng bị đẩy về phía giấy và
biến mất. Cắt trước là việc **mọi pipeline OCR thật đều làm**.

### 8.1 Đo xem thời gian đi đâu — `make profile`

`profiling.py` là một cái đồng hồ bấm giây **tắt mặc định**: tắt thì
`profiling.stage()` trả về một object dùng chung không làm gì, nên code sinh
ảnh không chậm đi và không đổi một pixel nào vì có profiler. Bật thì
`tools/profile_pipeline.py` đo từng giai đoạn — sampling · nội dung · layout ·
render · geometry · degradation · annotation · validation · export — riêng
từng renderer, riêng từng model làm cũ.

Ba nguyên tắc, và cả ba đều là lý do bảng số đọc được:

* **Không dựng sẵn danh sách nghi phạm.** Đo hết, kể cả tầng đọc YAML mà không
  ai nghĩ là đắt (`sampling` là 2,4–8,5% một ảnh, gần như toàn bộ nằm ở
  `load_rules`).
* **Phần chưa đo được ghi thành số.** Thời gian khởi động interpreter mà tiến
  trình con không tự thấy được đo từ ngoài và đặt tên `interpreter`, nên cột số
  cộng lại bằng đồng hồ thật chứ không bằng "gần hết".
* **Đo cả chính cái đồng hồ.** `enable()` hiệu chuẩn vài nghìn stage rỗng; báo
  cáo ghi giá mỗi lần gọi và tổng chi phí đó chiếm bao nhiêu phần trăm.

Kết quả nằm ở [`data/profile/README.md`](../data/profile/README.md), cùng một
**mô hình chi phí máy đọc được** (`cost_model.json`) để lần chạy sau *dự đoán*
trước rồi đối chiếu với đồng hồ — lệch bao nhiêu chính là phát hiện.

Ba thứ đọc code không ra:

* Giai đoạn đắt nhất của renderer glyph **không phải vẽ chữ**: cong giấy, khung
  ảnh, nền và hiệu ứng chụp chiếm 55% một ảnh synthdog.
* `gradient_domain` — thứ bị đồn là nút thắt suốt bốn wave — chỉ là **4% tổng
  thời gian làm cũ**, khoảng 1% một lần chạy. Tối ưu nó là công vô ích.
* Đòn bẩy lớn nhất không nằm trong renderer nào cả mà ở **hình dạng kế hoạch**:
  worker khởi động một tiến trình renderer cho mỗi *run*, mà một run là một bố
  cục, nên 20 ảnh trên 14 bố cục khởi động 14 tiến trình và trả chi phí khởi
  động 14 lần — 23% đến 44% một lần chạy tuỳ backend.

Mọi số throughput trước đây đã lạc hậu và **được đo lại từ đầu**, không so với
số cũ: số cũ lấy trước bản sửa `sample_recipe` và trên một tập bố cục khác, nên
so hai cái đó là gán cho một tối ưu cái mà thật ra là đổi phép bốc.

---

## 9. Q&A

**H: Sao không dùng LLM/diffusion sinh hoá đơn cho nhanh?**
Vì cần **nhãn chính xác tới từng ký tự và từng toạ độ**. Model sinh ảnh không
cho bạn biết nó đã vẽ chữ gì ở đâu; muốn có nhãn thì phải OCR lại ảnh nó sinh,
và lúc đó nhãn chỉ tốt bằng OCR. Ở đây nhãn dựng từ chính object dùng để vẽ nên
đúng theo cấu trúc. Đổi lại, đa dạng bị giới hạn bởi luật mình viết — đó là lý
do rule-base là thứ được đầu tư nhất trong repo.

**H: 5 bố cục thì ít quá, model sẽ overfit chứ?**
Bố cục chỉ là một trong sáu trục. Không gian là tích của cả sáu, cộng thêm
corpus (115 món quán + 88 mặt hàng siêu thị), số mặt hàng, seed. Nhưng đúng là
5 bố cục ít — và **đó là thiết kế**: mỗi bố cục đo từ một ảnh hoá đơn thật, chứ
không bịa. Thêm bố cục = thêm một file YAML, xem `rulebase/README.md` §3. Mình
thà có 5 cái đúng còn hơn 50 cái tưởng tượng.

**H: Rule-base có phải là hard-code trá hình không?**
Ranh giới ở chỗ: cái gì thay đổi thường xuyên thì ở YAML, cái gì là *cơ chế* thì
ở Python. Tỉ lệ hoá đơn siêu thị, số mặt hàng, cường độ làm cũ, tên món — YAML.
"Ngắt dòng thế nào", "canh cột ra sao" — Python. Phép thử: đổi tỉ lệ dataset
mà **không mở file .py nào**? Được. Đó là mục tiêu.

**H: `weight` là xác suất à?**
Không. Là trọng số **tương đối trong tập ứng viên còn lại sau khi lọc**. Tăng
weight của một giá trị `requires` thẻ hiếm thì gần như không đổi gì. Vì thế mới
có `make distribution` — cách duy nhất biết phân phối thật là bốc thử.

**H: Sao renderer glyph điểm OCR thấp thế (0.41)? Có phải nó tệ hơn?**
Không, nó **khó hơn**. Nó cho ra ảnh *chụp* tờ giấy trên bàn: nền tối, phối
cảnh, bóng đèn, motion blur. Hai cái kia cho bản quét phẳng và bản in. Bằng
chứng: tắt camera pipeline (`--clean`) thì nó nhảy lên **0.85**, ngang hai cái
kia. Nếu bỏ nó đi thì dataset mất hẳn trường hợp khó nhất, cũng là trường hợp
giống ảnh người dùng chụp bằng điện thoại nhất.

**H: Sao chấm bằng Tesseract mà không phải model tốt hơn?**
Tesseract là **mốc dưới**, không phải trần: engine đa dụng, chưa fine-tune trên
hoá đơn nhiệt tiếng Việt. Nó đủ để trả lời hai câu hỏi đang cần — "nhãn có khớp
ảnh không" và "ảnh có khó dần theo mức làm cũ không". Đổi engine chỉ cần sửa
`run_tesseract` trong `tools/ocr_proof.py`.

**H: Điểm thấp trên ảnh làm cũ nặng có phải là nhãn sai?**
Không. Kiểm bằng bộ sạch: cùng nhãn đó, cùng nội dung đó, tắt làm cũ thì lên
0.85. Muốn soi trường nào sai có hệ thống thì xem `worst_fields` trong
`ocr_report.json` — sai trên **mọi** ảnh mới là nhãn hỏng.

**H: Sao ba môi trường ảo? Không gộp được à?**
Không. synthtiger ghim `pillow<10` vì gọi `ImageFont.getsize()` (xoá ở Pillow
10), WeasyPrint đời mới cần Pillow mới. Mâu thuẫn thật. `tools/generate_dataset.py`
chạy ba renderer bằng **subprocess** qua đúng venv của từng cái, chứ không import
cả ba vào một process không thể tồn tại.

**H: Có scale lên 100k ảnh được không?**
Được, nhưng chưa tối ưu cho quy mô đó. Renderer glyph có sẵn đường
`make receipts` chạy synthtiger CLI đa worker. Renderer HTML giữ một browser
sống nên chi phí biên thấp. Nút cổ chai là `gradient_domain`
(`cv2.seamlessClone` khá chậm) — chính DocCreator cũng ghi "This implementation
is rather slow". Ở 100k ảnh nên hạ weight của `stains`, hoặc dựng sẵn kho vết
bẩn thay vì sinh từng cái.

**H: Reproducibility tới đâu?**
`recipe.seed` dựng lại được **cả nội dung lẫn ảnh**, với điều kiện code và
corpus không đổi. Đó cũng là lý do mỗi lần đổi model (ví dụ đổi `holes` sang lấp
màu đen) thì dataset đã commit được sinh lại — nếu không, recipe trong repo mô tả
một ảnh mà code hiện tại không tạo ra nữa.

**H: Nhãn có format gì? Dùng train được luôn không?**
`ground_truth` là chuỗi JSON `{"gt_parse": {...}}` lồng nhau kiểu CORD —
`DonutDataset` đọc trực tiếp. Thêm `text_sequence` cho pre-training đọc trơn, và
`boxes` (polygon 4 điểm mỗi ô, **vẫn đúng sau khi giấy cong**) cho detection.
Renderer glyph có `boxes`; hai renderer HTML thì chưa.

**H: Sao không vendor luôn ảnh texture của DocCreator cho giống?**
Vì chúng là data LGPL. Nên pattern được sinh từ seed — bù lại repo clone về là
render được ngay, không phải tải gì. Có scan thật thì trỏ `stains_dir` /
`patterns` vào là nó dùng cái thật.

**H: Chỗ nào trong repo là rủi ro nhất?**
Ba chỗ, xếp theo mức độ:
1. **Font.** Font thiếu dấu tiếng Việt vẽ ra ô vuông mà nhãn vẫn khai đúng chữ —
   **lỗi im lặng**. DejaVu Sans Mono, lựa chọn mono hiển nhiên nhất, thiếu 46 ký
   tự. Vì thế mới có `tools/check_fonts.py` và vì thế `fonts/` mới được commit.
2. **Ngưỡng làm cũ.** Đặt quá tay thì ảnh vô dụng mà không có gì báo. `make proof`
   là cái phanh: bảng "theo mức làm cũ" phải giảm đơn điệu.
3. **Nhãn lệch ảnh.** Đã dính hai lần (cắt chuỗi không ghi ngược, tiêu đề cột
   không bỏ dấu). Cả hai đều bị bắt bằng cách **nhìn ảnh**, không phải bằng test.

**H: Thêm một loại document mới (ví dụ hoá đơn điện) mất bao lâu?**
Một buổi. Thêm giá trị vào `rules/document.yaml`, một file bố cục trong
`layouts/`, corpus tương ứng, khai bố cục ở `rules/layout.yaml` kèm
`requires`. Không phải sửa Python nếu bố cục dùng được ngữ pháp có sẵn
(cột, span, `note_row`, `discount_row`). `make preview-grid LAYOUT=<id>` để soi.

**H: Sao không dùng Albumentations/imgaug cho phần augmentation?**
Chúng làm rất tốt biến đổi **tổng quát** (xoay, méo, nhiễu, đổi màu) — và
`config_vi_receipt.yaml` vẫn dùng chúng qua synthtiger cho phần "chụp lại".
Nhưng chúng không có model **đặc thù tài liệu**: mực mòn theo từng ký tự, chữ
thấm từ mặt sau, vết rách lộ mặt bàn, bóng gáy sách. Đó là chỗ DocCreator hơn
hẳn, vì các model đó được thiết kế đối chiếu với bản thảo hư hại thật.
