# docs — bộ tài liệu thiết kế tự động hoá

> **Trạng thái: đây là *thiết kế*, chưa phải *hiện thực*.**
> Bảy commit vừa rồi đổi **4 file, tất cả đều là `.md`** — không một dòng code
> nào trong `rulebase/`, `generators/`, `degradation/` hay `pipeline/` bị đụng
> tới. Bộ sinh chạy hôm nay đúng như nó chạy hôm qua.

```
$ git diff --stat f67e7d5..HEAD
 README.md                    |    9 +-
 docs/duong-ong.md            |  591 +++
 docs/tang-cuong-bo-cuc.md    |  957 +++
 docs/tu-dong-hoa-bang-llm.md | 1400 +++
 4 files changed, 2954 insertions(+), 3 deletions(-)

$ git diff --name-only f67e7d5..HEAD | grep -v '\.md$'
 (không có gì)
```

---

## 1. Ba tài liệu, đọc theo thứ tự này

| # | tài liệu | trả lời câu gì | dài |
| --- | --- | --- | ---: |
| 1 | [`tu-dong-hoa-bang-llm.md`](tu-dong-hoa-bang-llm.md) | **Ai ra quyết định?** Hiện trạng, khảo sát ngoài, trục mực thứ tám, lộ trình, kinh tế | 1400 |
| 2 | [`tang-cuong-bo-cuc.md`](tang-cuong-bo-cuc.md) | **Một bố cục nhân lên thành bao nhiêu?** Cây cột, chín nước đi, `compose:`, biến thể có tên | 957 |
| 3 | [`duong-ong.md`](duong-ong.md) | **Một tờ giấy đi qua hệ thống ra sao, và ai sở hữu toạ độ?** | 591 |
| 4 | [`ke-hoach.md`](ke-hoach.md) | **Làm gì, theo thứ tự nào?** Mười việc, mỗi việc mô tả đủ để nhận và làm | 619 |
| 5 | [`brief-plan-run.md`](brief-plan-run.md) | **Brief cho agent làm P1** — việc đầu tiên, viết đủ để bắt tay vào code | 501 |

Không có thời gian đọc hết: đọc **§0 của (1)**, **§0 của (2)**, và **§9 của (3)**
— khoảng bốn trang, đủ để phản biện.

---

## 2. Mười quyết định đã chốt

Xếp theo mức chịu lực. Đổi cái ở trên thì mọi thứ dưới nó phải xem lại.

| # | quyết định | ở đâu | vì sao |
| --- | --- | --- | --- |
| 1 | **LLM đứng ở author-time, không ở render-time.** Đầu ra là YAML được commit | (1) §3, Phụ lục C | giữ nguyên tất định `seed → trang` và nhãn-dựng-từ-object-đã-vẽ. Cũng là kiến trúc **rẻ nhất**: chi phí `k × số bố cục`, không `k × N` |
| 2 | **Schema bố cục là việc đầu tiên** | (1) §12 M0 | `rules/*.yaml` từ chối khoá lạ, `layouts/*.yaml` thì không — đã chứng minh bằng thí nghiệm. Vừa là cổng, vừa là hợp đồng đưa cho LLM |
| 3 | **Nguồn mực là thuộc tính của Ô, không của trang** — trục thứ tám `ink` | (1) §8 | không trục nào hiện có diễn tả được "nhãn in sẵn, giá trị viết tay" |
| 4 | **`ink/` sinh hộp; `degradation/` thì không** | (1) §15 bất biến 6 | thứ viết chữ lên trang phải khai vào nhãn. Đặt vào chuỗi làm cũ là cách chắc chắn có chữ mà nhãn không biết |
| 5 | **Gộp ô là nước đi trên cây cột, không phải mặt nạ ngẫu nhiên** | (2) §3 | ràng buộc ngữ nghĩa nằm trong cây; ngoài cây thì cần vị từ |
| 6 | **Vị từ: ô gộp không được phủ cột có giá trị ở hàng đó** | (2) §1.2, §3.2 | đã nằm sẵn trong `_group_row`, cho một ca. Tổng quát hoá là xong |
| 7 | **Nội dung hợp lý bảo đảm ở chỗ *khai báo*, không ở chỗ *sinh*** — `compose:` | (2) §3.3 | không khai cách nối hai giá trị thì không có nước đi. Phán quyết đắt tiền chạy `O(cây × chính sách)`, không `O(ảnh)` |
| 8 | **Biến thể là file có tên, được duyệt — không phải xác suất** | (2) §3.2c | xác suất làm lỗi *im lặng*; toạ độ tường minh làm lỗi *có địa chỉ, lúc soạn* |
| 9 | **Hộp do engine đã dàn chữ sinh ra, không bao giờ do LLM** | (3) §1 | LLM không chạy engine layout; ba backend có ba cơ chế khác hẳn nhau |
| 10 | **Hộp sinh một lần, sau đó chỉ *biến đổi*, không bao giờ *đo lại*** | (3) §4 | đo lại là biến hộp của engine thành hộp của một bộ dò |

---

## 3. Bốn quyết định **đã sửa** trong lúc soạn

Ghi lại để lần sau không ai đề xuất lại cái đã bị loại, và để thấy cái nào đã
được phản biện.

### 3.1 Gộp ô: một chế độ → **hai chế độ**
**Bản đầu:** chỉ *hợp lệ theo cấu tạo* (đi theo cây cột).
**Vấn đề:** từ chối một ca có thật — tờ gộp hai cột trong **đúng một hàng**,
không theo cây nào.
**Bây giờ:** hai chế độ — cây cột (khỏi kiểm) và **chỉ đích danh rồi kiểm** (vị
từ không-nuốt-giá-trị). Kèm phát hiện: ca đó **đã diễn tả được** trong ngữ pháp
— `{from: name, span: [qty, amount]}` chính là colspan cục bộ, chạy từ đầu.

### 3.2 Khai gộp: **phạm vi + xác suất** → **toạ độ tường minh có neo**
**Bản trước:** `{scope: [name, unit], on: item, prob: 0.35}`.
**Vấn đề — và đây là lỗi của chính tôi:** khi vị từ từ chối, hàng đó **im lặng
không gộp**, nên một khai báo sai trông y hệt một hàng không đủ điều kiện. Đúng
loại lỗi im lặng repo này liên tục trả giá.
**Bây giờ:** `merges: [{row: "item[*]", from: name, to: unit, when: "not unit"}]`
— lỗi **có địa chỉ, bắt lúc soạn**. Hàng địa chỉ bằng **neo tượng trưng** vì số
hàng phụ thuộc nội dung.

### 3.3 `n_rows`: **"không khai được"** → **"một nguồn sự thật, hai kiến trúc"**
**Bản trước:** viết như thể chiều phụ thuộc là bắt buộc.
**Vấn đề:** nói hẹp. Phản đối thật sự là **hai nguồn sự thật cho cùng một con
số**, không phải chiều phụ thuộc.
**Bây giờ:** content-first (repo hôm nay) và layout-first (SynthTabNet) **đều
hợp lệ** — điều kiện là chọn một và ghi ra là đã chọn. Kèm cái giá của
layout-first: số mặt hàng thôi là thuộc tính của giao dịch. → **Câu hỏi treo
số 1**.

### 3.4 Hộp = "ô trừ lề X%": bác bỏ **bằng số đo**, và chỉ ra chỗ nó bắt buộc
**Đề xuất:** suy hộp chữ từ ô + lề tương đối.
**Đo trên data đã commit:** mực chiếm **16% diện tích ô** ở trung vị, **37% bề
rộng**; 71% hộp chiếm dưới nửa bề rộng ô; ô gộp trung vị **0,25**, nhỏ nhất
**0,10**. → hộp suy ra **lớn gấp ~6 lần** thứ nó mô tả.
**Nguy hiểm:** qua được **2/3** phép kiểm của `check_boxes.py`.
**Nhưng bắt buộc phải có ở một chỗ:** chữ viết tay **không có `<span>` nào để
đo**, nên `ink/` phải được khai *"vẽ vào đâu bên trong ô"*. → quy tắc:
**khai báo thì tương đối với ô, nhãn thì đo từ thứ đã đáp xuống.**

---

## 4. Số đo đã lấy — nền bằng chứng

Tất cả chạy lại được, phần lớn không cần dựng venv renderer nào.

| số đo | giá trị | dùng cho |
| --- | --- | --- |
| `pytest` | 599 passed, 4 skipped, 1 xfailed, 78 s | hiện trạng (README từng ghi 417) |
| `tasks.py check` | 84 file biên dịch | hiện trạng (README từng ghi 64) |
| không gian luật | 17×16×12×7×5×21×15 = **35.985.600** | repo không nghèo vì thiếu tổ hợp |
| **schema bố cục** | thêm `headr:`/`algin:` → **vẫn dựng 21 dòng, 40 ô, im lặng** | lý do M0 đứng đầu |
| cột & nhóm | 87 cột / 16 bố cục · **1/16** khai `header_groups` | cây cột đã tồn tại một nửa |
| OCR theo bố cục | `invoice_brand` 0,924 → `market_barcode` 0,234 (**4×**) | đầu vào của A4 |
| WriteViT | **0/10.131** token bộ sinh từng thấy có chứa chữ số | chặn cứng của `handwriting_fill` |
| loại hộp | `invoices54/html`: 105 `boxes`, **102 `cells`**, 240 token · genalog: **0 `cells`** | `cells` chỉ có trên 1/3 đường vẽ |
| **độ lấp đầy ô** | trung vị **0,16** diện tích · **0,37** bề rộng · 71% dưới nửa | bác bỏ "ô trừ lề" |
| chi phí LLM (50k ảnh) | sinh cả trang ~$4.450 · chọn component ~$450 · **viết luật ~$3** | ranh giới author-time |

---

## 5. Kế hoạch hợp nhất

Gộp `M0–M4` của tài liệu (1) và `T0–T3` của tài liệu (2) thành một danh sách
theo đúng thứ tự phụ thuộc.

> **Mô tả đầy đủ từng việc** — mục tiêu, file nào đụng vào, các bước, xong khi
> nào, cổng nào phải xanh, bẫy nào đã biết trước — ở **[`ke-hoach.md`](ke-hoach.md)**.
> Bảng dưới đây chỉ là mục lục.

### Đợt 0 · làm được **ngay hôm nay**, không phụ thuộc gì

| | việc | công | giá trị |
| --- | --- | ---: | --- |
| **P1** | `tools/plan_run.py` — LLM đọc `ocr_report.json` + `drift.json` rồi viết `pipeline.yaml` **kèm lý do** | 2 ngày | ★★★ rủi ro ~0: `config.py` đã từ chối khoá lạ và override trỏ vào thứ không có |

### Đợt 1 · hợp đồng — nền cho mọi thứ sau

| | việc | công | phụ thuộc |
| --- | --- | ---: | --- |
| **P2** | `rulebase/schema.py`: ngữ pháp bố cục thành dữ liệu — gồm cây cột, `merges`, `compose`, `provenance`, đóng băng vốn từ `role` | 3–4 ngày | — |
| **P3** | Hợp đồng component: `requires`/`provides`/`after`/`optional`/`accepts` | 3–4 ngày | song song P2 |

### Đợt 2 · **bước then chốt** — nhãn phải hiểu ô gộp

| | việc | công | phụ thuộc |
| --- | --- | ---: | --- |
| **P4** | `Cell.colspan/rowspan/roles`; đường lưới đọc `header_groups`; `structure_tokens()` dùng chung; **`cells` phát được trên cả ba backend** | 1,5–2 tuần | P2, P3 |

> Đây là bước đáng làm **kể cả nếu không bao giờ sinh biến thể** — nó vá đúng
> khiếm khuyết `brief-engine-html.md` đã đo: *ảnh có ô gộp, nhãn thì không biết*.
> Phép thử nghiệm thu mạnh nhất trong cả kế hoạch: **đường lưới và đường CSS
> phải cho ra cùng chuỗi token cho `medical_statement`.**

### Đợt 3 · ba năng lực mới, song song được

| | việc | công | phụ thuộc |
| --- | --- | ---: | --- |
| **P5** | Tác nhân soạn bố cục (3 lượt + A5 phản biện + vòng tự sửa) **và** khai cây cột cho 15 bố cục còn lại | 1,5–2 tuần | P2 |
| **P6** | Bộ tăng cường + `rules/structure.yaml` biến thể có tên + `make structures` / `make preview-structures` | 1–1,5 tuần | P4 |
| **P7** | Trục mực `ink` + nguồn `marks` (✓, gạch chân) + bất biến "ô hand phải có mực" + nhóm `by_ink` | 1 tuần | P2 |
| **P8** | Bỏ hard-code `sheets.FAMILIES` → bố cục tự khai `family:` | 1 ngày | P2 |

> P7 cố ý bắt đầu bằng **dấu tích**, không bằng WriteViT: một nét, không đòi
> hình dạng chữ, đủ để chứng minh cả đường ống trước khi thay ruột.

### Đợt 4 · chữ viết tay thật

| | việc | công | phụ thuộc |
| --- | --- | ---: | --- |
| **P9** | Nguồn `writevit` + `can_write` + **nguồn chữ số riêng** (ngôn ngữ trung tính) + `ink: stamp` — *lần đầu `ornament` được vẽ lên trang* | 2–3 tuần | P7 |
| **P10** | **Đo downstream** — điều kiện nghiệm thu, không phải phần thưởng | 1 tuần | P9 |

> P10 không xong thì đợt 4 chưa xong. *Quo Vadis HTG* (2025) nói chữ tay tổng
> hợp **không chắc** làm mô hình nhận dạng tốt lên. Nếu số không nhích, thứ phải
> ghi lại là **vì sao**, không phải là thêm ảnh.

### Đợt 5 · mở rộng

Nhiều trang (`doc_id` + `page`) · TEDS cho `data/tables60` · engine thứ tư
(Typst) · corpus `source: llm` (móc đã chừa sẵn trong `drift.SOURCES`) ·
Layout-FID · mô hình học trò + vòng lặp đóng đầy đủ.

---

## 6. Việc đầu tiên nên làm

**P1 và P2 song song.** P1 vì nó cho giá trị trong hai ngày với rủi ro gần
bằng không; P2 vì mọi thứ còn lại chờ nó.

Nếu chỉ có ngân sách cho **một** việc: **P2**. Nó bắt lỗi im lặng mà con người
cũng mắc, và nó là hợp đồng để bất kỳ tác nhân nào làm việc được về sau.

---

## 7. Năm câu hỏi cần **người** chốt

Không câu nào máy trả lời thay được, và mỗi câu chặn ít nhất một đợt.

| # | câu hỏi | chặn | ghi chú |
| --- | --- | --- | --- |
| 1 | **Content-first hay layout-first?** Ai sở hữu số dòng — `document.num_items` hay biến thể? | P4, P6 | §3.3 ở trên. Cả hai hợp lệ; layout-first đổi số mặt hàng từ thuộc tính giao dịch thành thuộc tính tờ mẫu |
| 2 | Có **tập ảnh thật form Việt Nam điền tay** để đánh giá không? | P10 | không có thì đợt 4 không nghiệm thu được, chỉ nhìn ảnh đoán |
| 3 | **Giấy phép** của repo, và điều khoản phát hành lại của **VNOnDB/IAM** | P9 (phát hành) | phải xong **trước** P9, không phải sau |
| 4 | Có **mô hình học trò + tập đánh giá thật** không? | vòng lặp đóng (đợt 5) | chưa có thì chạy chế độ giảm: đo **độ phủ** thay cho hiệu năng |
| 5 | Trần cho `llm_proposed` và cho biến thể cấu trúc là bao nhiêu? | P5, P6 | đề xuất: biến thể ≤ 40% một lần chạy; `llm_proposed` càng thấp càng tốt |

---

## 8. Tài liệu khác trong thư mục này

| | |
| --- | --- |
| [`khao-sat-sinh-chu-viet-tay.md`](khao-sat-sinh-chu-viet-tay.md) | tám kho sinh chữ tay, xếp theo hai trục |
| [`writevit.md`](writevit.md) | WriteViT đã dựng, và **đo được nó không viết được gì** |
| [`hoa-tiet-de-xuat.md`](hoa-tiet-de-xuat.md) | 23 hoạ tiết khảo sát chưa dựng, mỗi cái một lý do |
| [`brief-engine-html.md`](brief-engine-html.md) | ba đường dựng trang, và ô gộp mà nhãn không biết |
| [`huong-dan-va-giai-thich.md`](huong-dan-va-giai-thich.md) | ba renderer, từng hàm một, kèm Q&A |
| [`python-versions.md`](python-versions.md) · [`windows.md`](windows.md) | vì sao ghim 3.11 · dựng trên Windows |
