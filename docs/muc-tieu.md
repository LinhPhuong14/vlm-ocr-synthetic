# Mục tiêu dự án — vì sao mười việc này tồn tại

> Tầng trên cùng của bộ tài liệu. [`ke-hoach.md`](ke-hoach.md) nói **làm gì**,
> [`brief-plan-run.md`](brief-plan-run.md) nói **làm thế nào**; bản này nói
> **vì sao**, và **thế nào là xong** ở mức dự án chứ không phải mức việc.
>
> Đây cũng là tài liệu đổi ít nhất. Nếu một đề xuất mâu thuẫn với §2 hoặc §8,
> đề xuất sai — cho tới khi có ai sửa được bản này bằng lập luận.

---

## 0. Một câu

> Biến một **cỗ máy sinh dữ liệu tốt nhưng phải có người điều khiển** thành một
> **hệ thống tự quyết định sinh gì**, mà không đánh mất thứ làm nó đáng tin:
> nhãn dựng từ chính object đã vẽ, và một seed dựng lại đúng một trang.

---

## 1. Bài toán

### 1.1 Repo hôm nay: máy tốt, không có người ra quyết định

Đo được, không phải cảm nhận:

| | |
| --- | --- |
| bố cục · họ · thuộc tính | 16 · 6 · 7 |
| không gian luật | 35.985.600 tổ hợp *(trước khi nhân corpus và seed)* |
| bộ kiểm | 599 test · preflight · bất biến từng ảnh · trôi phân phối · vân tay vàng |
| chứng minh OCR | chấm không phụ thuộc thứ tự đọc, tách theo bố cục / mức làm cũ / trường |

Hạ tầng kiểm chứng ấy là thứ ba công trình cùng lĩnh vực (CoSyn, DocGenie,
DocDjinn) **đều phải tự dựng**. Repo này đã có. Cái nó thiếu nằm ở tầng trên:

> **Mọi quyết định về *sinh cái gì* đều do một người đọc số rồi sửa YAML.**
> Đo tờ giấy thật bằng mắt · chọn họ bố cục · cân trọng số · đọc
> `ocr_report.json` rồi đoán lần sau sửa gì.

### 1.2 Ba thứ hệ thống **không nói được**, dù có bao nhiêu tổ hợp

Đây mới là giới hạn thật. Không tổ hợp nào của 35.985.600 tổ hợp diễn tả được:

| không nói được | hệ quả |
| --- | --- |
| **"nhãn in sẵn, giá trị viết tay"** | mọi tờ mẫu sinh ra đều trống trơn hoặc in máy toàn bộ — trong khi **tờ mẫu tồn tại là để được điền tay**. `hoa-tiet-de-xuat.md` gọi đây là *khoảng trống lớn nhất* |
| **"ô này gộp bảy cột"** trong nhãn | ảnh có ô gộp, nhãn không biết. Đo được: `cells` chỉ có ở **1 trong 3** đường vẽ |
| **"trang 2 của cùng tài liệu"** | một ảnh = một trang; `metadata.jsonl` không có `doc_id`/`page` |

Ba khoảng trống này không phải thiếu dữ liệu — là **thiếu từ vựng**. Sinh thêm
một triệu ảnh cũng không lấp được cái nào.

### 1.3 Và một giới hạn kinh tế

Cách rõ ràng nhất để "cho LLM làm" — gọi model cho **mỗi tài liệu** — có chi
phí `k × N`. Đo bằng giá thật cho 50.000 ảnh: sinh cả trang ~**$4.450**, chọn
component ~**$450**. Cách repo đang đi — viết luật một lần — là ~**$3**, và
**không tăng theo N**. Ở 5 triệu ảnh: vẫn ba đô la, so với bốn mươi lăm nghìn.

Nên mục tiêu không phải "dùng LLM nhiều hơn". Là **đặt LLM đúng chỗ nó không
nhân lên theo sản lượng**.

---

## 2. Kết quả mong muốn — bốn năng lực

Dự án xong khi hệ thống có đủ bốn. Không phải bốn tính năng — bốn **năng lực**,
mỗi cái trả lời một câu hỏi hệ thống hôm nay trả lời được nửa vời hoặc không.

### A · QUYẾT — *"sinh cái gì tiếp theo?"*

**Hôm nay:** một người đọc `ocr_report.json`, so `by_layout` với
`by_layout_augmentation`, rồi đoán nên nâng trọng số nào.
**Mong muốn:** một mục tiêu bằng lời + số đo đã có → một kế hoạch chạy **kèm lý
do cho từng con số**, và về sau là một vòng lặp đóng lấy điểm yếu của mô hình
học trò làm đầu vào.

> Ranh giới: hệ thống **đề xuất**, người **chốt**. Cái đổi là *ai làm số học*,
> không phải *ai chịu trách nhiệm*.

### B · DIỄN TẢ — *"nói được thứ tờ giấy thật có"*

**Hôm nay:** mực là thuộc tính của **trang**; ô gộp là thứ được *mô phỏng* chứ
không được *mô hình hoá*; component không khai gì về mình.
**Mong muốn:** mực là thuộc tính của **ô** (`press`/`hand`/`stamp`/`redact`);
`colspan`/`rowspan` vào **nhãn** trên **cả ba** renderer; component có hợp đồng.

> Đây là năng lực **chịu lực nhất**. Ba năng lực kia đều xây trên nó: không
> diễn tả được thì không soạn được, không kiểm được, và không có gì để quyết.

### C · SOẠN — *"tạo ra cái mới mà không phải đo bằng mắt"*

**Hôm nay:** thêm một bố cục = một người mở ảnh, đếm cột, gõ YAML. 15/16 bố cục
chưa khai quan hệ cột nào.
**Mong muốn:** LLM soạn **cây cột** và **bố cục mới** từ chứng từ thật; một bộ
tăng cường tất định nhân mỗi bố cục thành hàng trăm biến thể **chứng minh được
là hợp lệ**.

> Ranh giới: LLM soạn **thứ lặp lại được** (cây, chính sách, biến thể có tên),
> không soạn **từng ảnh**. Đó là chỗ giữ chi phí phẳng ở §1.3.

### D · KIỂM CHỨNG — *"biết nó có tác dụng, không phải tin là có"*

**Hôm nay:** mọi cổng kiểm **tính nhất quán nội tại** — nhãn khớp ảnh, mix khớp
luật, pixel khớp vân tay. Không cổng nào kiểm **tính giống thật** hay **tính
dạy được**.
**Mong muốn:** mỗi năng lực mới kết thúc bằng một **phép đo downstream trên dữ
liệu thật**, và mỗi thứ do máy soạn ra **truy được về một chứng cứ**.

> Đây là năng lực dễ bỏ qua nhất, vì ba cái kia cho ra thứ nhìn thấy được còn
> cái này cho ra một con số có thể nói *"chưa được"*. Nó vẫn phải có.

---

## 3. Bản đồ: việc nào phục vụ năng lực nào

Đọc cột cuối — đó là câu trả lời cho *"làm xong việc này thì làm được gì mà hôm
nay không làm được?"*

| việc | năng lực | hôm nay | sau khi xong |
| --- | :---: | --- | --- |
| **P1** `plan_run.py` | **A** | người đọc số rồi cân trọng số bằng tay | một câu mục tiêu → `pipeline.yaml` có lý do cho từng con số |
| **P2** `schema.py` | **C·D** | 112 khoá bố cục, **không khoá nào được kiểm**; khoá lạ đi qua im lặng | ngữ pháp thành **dữ liệu** — vừa là cổng, vừa là hợp đồng đưa cho LLM |
| **P3** hợp đồng component | **B·C** | 15 emitter nhận toàn bộ `spec`, khai báo **không gì cả** | `sections:` kiểm được mạch lạc; thêm component không sửa `build_grid`; LLM có thực đơn máy đọc |
| **P4** ô gộp vào nhãn | **B** | `cells` ở **1/3** đường vẽ; ảnh có ô gộp, nhãn không biết | cấu trúc bảng thôi là **đặc quyền của renderer có DOM** |
| **P5** tác nhân soạn bố cục | **C** | 15/16 bố cục chưa khai quan hệ cột; bố cục mới = đo bằng mắt | LLM khai cây từ ảnh thật, đề xuất bố cục mới, người duyệt |
| **P6** bộ tăng cường | **C** | một bố cục = một cấu trúc | một bố cục = hàng trăm cấu trúc **chứng minh được là hợp lệ** |
| **P7** trục mực + `marks` | **B** | không có mực nào ngoài mực in | đường ống mực thông đầu-cuối, chứng minh bằng ca dễ nhất |
| **P8** bỏ `FAMILIES` | **C** | bố cục mới đi đường CSS **bắt buộc** sửa Python | thêm bố cục = thuần YAML, trên **cả hai** đường vẽ |
| **P9** chữ viết tay thật | **B** | `handwriting_fill` — khoảng trống lớn nhất, chưa lấp | tờ mẫu điền tay: nhãn in sẵn + giá trị viết tay + dấu đóng |
| **P10** đo downstream | **D** | không cổng nào hỏi *"có dạy được không?"* | một bảng ba cột, và quyền nói **"chưa được"** |

Ba việc của **đợt 5** — nhiều trang, TEDS, corpus LLM — phục vụ cùng bốn năng
lực ấy ở mức rộng hơn, và cố ý xếp sau vì chúng không chặn gì.

---

## 4. "Xong" của dự án — năm phát biểu kiểm được

Không phải cảm giác. Mỗi câu dưới đây đúng hoặc sai, và kiểm được bằng lệnh.

| # | phát biểu | kiểm bằng |
| --- | --- | --- |
| 1 | **Một tờ mẫu Việt Nam điền tay sinh ra được**, nhãn khai đúng trường nào in sẵn và trường nào viết tay | `by_ink` trong `ocr_report.json`; bất biến "ô `hand` phải có mực trong hộp" |
| 2 | **Cả ba renderer phát được nhãn cấu trúc**, và hai đường vẽ độc lập **đồng ý** về cùng một bảng | `medical_statement` qua đường lưới và qua đường CSS cho cùng chuỗi `structure` token |
| 3 | **Thêm một bố cục không sửa một dòng Python nào**, và bố cục ấy truy được về một chứng cứ | `make accept-layout` xanh; `provenance.method` bắt buộc trong schema |
| 4 | **Chi phí LLM không tăng theo số ảnh** — nhân đôi bộ dữ liệu không nhân đôi tiền | token LLM cho một lần chạy 100k ảnh ≈ token cho 10k ảnh |
| 5 | **Dữ liệu sinh ra dạy được**, đo trên tài liệu thật chứ không trên chính nó | mô hình học trò: (in + tổng hợp) > (chỉ in) trên tập thật |

Ba câu đầu là **năng lực**. Câu 4 là **kinh tế**. Câu 5 là **lý do tồn tại** —
và là câu duy nhất có thể trả lời "không" sau khi bốn câu kia đã "có".

---

## 5. Năm dấu hiệu theo dõi

Không phải KPI để tối ưu — **dấu hiệu** để nhìn. Cái gì thành mục tiêu tối ưu
thì thành cái bị lách.

| dấu hiệu | hôm nay | hướng đúng |
| --- | --- | --- |
| **Độ phủ từ vựng** — bao nhiêu tổ hợp `(bố cục × mực × cấu trúc)` thật sự có ảnh | mực: 1 giá trị · cấu trúc: 1/bố cục | tăng, nhưng **đo bằng tổ hợp có ảnh**, không bằng số ảnh |
| **Nhãn đầy đủ** — bao nhiêu renderer phát được `cells` + `structure` | **1/3** | 3/3 |
| **Truy xuất nguồn** — tỉ lệ bố cục về được một chứng cứ có thật | 16/16 `measured` | giữ cao; `llm_proposed` có trần |
| **Đường chi phí** — token LLM cho mỗi 1000 ảnh, theo cỡ bộ dữ liệu | chưa đo | **phẳng**. Dốc lên nghĩa là LLM đã trôi vào đường render |
| **Hiệu năng downstream** trên tài liệu **thật** | chưa đo | tăng — và đây là dấu hiệu duy nhất được coi là kết luận |

Dấu hiệu thứ tư đáng nói: nó **phát hiện được một sai lầm kiến trúc bằng một
con số**. Nếu chi phí mỗi 1000 ảnh bắt đầu tăng theo cỡ bộ dữ liệu, nghĩa là có
ai đó đã đặt một lời gọi model vào chỗ chạy mỗi ảnh — và điều đó cũng đã phá
tất định, resume và mô hình chi phí, chỉ là chưa ai nhận ra.

---

## 6. Cái dự án này **không** nhắm tới

Viết ra để không phải cãi lại mỗi quý.

| không nhắm tới | vì sao |
| --- | --- |
| **Thay thế dữ liệu thật** | nhắm bổ sung, và neo vào dữ liệu thật. Tỉ lệ thật trong tập huấn luyện **không được về 0** |
| **Mô hình sinh ảnh tài liệu** | không cho biết nó vẽ chữ gì ở đâu; nhãn tụt xuống chỉ tốt bằng OCR chạy lại |
| **Tổng quát hoá ra ngoài tiếng Việt** | kiến trúc thì tổng quát, **đầu tư thì không**. Corpus, quy ước giấy tờ, phủ glyph, mô hình chữ tay — đều là bài tiếng Việt |
| **Huấn luyện / phục vụ mô hình** | repo sinh dữ liệu. Mô hình học trò ở P10 là **dụng cụ đo**, không phải sản phẩm |
| **Một DSL bố cục mới** | ngữ pháp YAML hiện tại đã diễn tả 16 tờ giấy thật; đổi ngôn ngữ là viết lại `layout.py` để mua sự thanh lịch |
| **Tự động hoá phần duyệt** | bố cục là thứ duy nhất phải nhìn bằng mắt: *"tờ giấy này có tồn tại không"* không kiểm được bằng máy |
| **Số ảnh làm mục tiêu** | một triệu ảnh của mười sáu tờ giấy vẫn là mười sáu tờ giấy |

---

## 7. Bốn cách dự án thất bại **dù mười việc đều xong**

Phần này là premortem, và là phần đáng đọc lại sau sáu tháng.

### 7.1 Bộ dữ liệu lớn lên, downstream không nhúc nhích

**Dấu hiệu:** đủ năng lực, ảnh đẹp, `by_layout` tăng — nhưng mô hình thật không
khá hơn trên tài liệu thật.
**Vì sao có thể xảy ra:** *Quo Vadis HTG* (2025) đo được rằng chữ tay tổng hợp
**không đồng nhất** làm mô hình nhận dạng tốt lên. Không có lý do gì để tin
những trục khác miễn nhiễm.
**Chặn bằng:** P10 là **điều kiện nghiệm thu**, không phải phần thưởng. Nếu số
không nhích, thứ phải ghi lại là **vì sao** — không phải là thêm ảnh.

### 7.2 Phân phối trôi khỏi giấy thật, và không cổng nào thấy

**Dấu hiệu:** hàng nghìn biến thể, tất cả hợp lệ, tất cả qua bất biến — và
không tờ nào trong đó giống một tờ giấy có thật.
**Vì sao có thể xảy ra:** **mọi cổng hiện có kiểm tính nhất quán nội tại**, không
cổng nào kiểm tính giống thật. Một bố cục máy nghĩ ra, được máy kiểm, sinh ra
ảnh máy chấp nhận — vòng khép kín không có thực tế trong đó.
**Chặn bằng:** `as_printed` nặng ký nhất · trần biến thể ≤ 40%/run ·
`provenance.method` bắt buộc và đếm được · Layout-FID như **thước phụ** (không
bao giờ là mục tiêu tối ưu).

### 7.3 Chi phí lặng lẽ chuyển từ `k` sang `k × N`

**Dấu hiệu:** một chỗ nào đó gọi model mỗi ảnh vì "chỉ chỗ này thôi, tiện hơn".
**Vì sao nguy hiểm:** cùng lúc mất **bốn** thứ, và không cái nào báo động ngay
— tất định (`baseline-verify` mất nghĩa), resume (shard làm lại ra khác), mô
hình chi phí (`profile_pipeline.py` mô hình CPU chứ không mô hình mạng), và
chạy offline.
**Chặn bằng:** dấu hiệu chi phí §5 · một test khẳng định **không module nào**
dưới `rulebase/`, `generators/`, `degradation/`, `pipeline/` import được client
mạng. Test đó sống lâu hơn bất kỳ đoạn văn nào trong CONTRIBUTING.

### 7.4 Truy xuất nguồn mục ruỗng

**Dấu hiệu:** `provenance.method` có mặt ở mọi file, và một nửa ghi
`llm_proposed` với `evidence` trỏ vào chỗ không ai mở lại bao giờ.
**Vì sao nguy hiểm:** đây là phiên bản của **model collapse** trong repo này —
nếu bố cục do LLM soạn từ những tờ giấy LLM tưởng tượng, phân phối trôi khỏi
thực tế **mà không có neo nào kéo lại**.
**Chặn bằng:** tỉ lệ ba `method` phải **in ra được** (`make distribution`), có
trần, và bị nhìn — chứ không chỉ được lưu.

---

## 8. Ràng buộc không được đổi

Chín bất biến, bản rút gọn. Bản đầy đủ:
[`tu-dong-hoa-bang-llm.md` §15](tu-dong-hoa-bang-llm.md#15-chín-bất-biến).

1. **Nhãn dựng từ chính object đã vẽ.** Không tác nhân nào chạm `ground_truth()`.
2. **`seed` → trang.** Không lời gọi mạng nào trong đường render.
3. **Mọi cổng còn nguyên.** Năng lực mới **thêm** cổng, không bớt.
4. **Mỗi bố cục nói nó từ đâu ra.**
5. **Mực là thuộc tính của ô**, không của trang.
6. **`ink/` sinh hộp; `degradation/` thì không.**
7. **Nguồn mực từ chối tốt hơn nguồn mực đoán bừa.** `can_write` trước `write`.
8. **Tích luỹ, không thay thế; tỉ lệ dữ liệu thật không về 0.**
9. **Thước đo cuối cùng là hiệu năng downstream trên dữ liệu thật** — không phải
   FID, không phải Tesseract, không phải số ảnh.

Cộng một cái chỉ thuộc về tài liệu này:

10. **Hệ thống đề xuất, người chốt.** Cái dự án này tự động hoá là **số học và
    việc gõ**, không phải **trách nhiệm**.

---

## 9. Một đoạn để dán vào đề cương

> Kho này sinh ảnh tài liệu tiếng Việt tổng hợp kèm nhãn có cấu trúc và hộp
> từng trường, cho việc huấn luyện và đánh giá mô hình VLM/OCR. Bộ sinh đã tất
> định và đã được kiểm chứng dày; cái nó thiếu là **người ra quyết định** — mọi
> lựa chọn về *sinh cái gì* vẫn do một người đọc số rồi sửa YAML — và **từ vựng**
> để nói ba thứ mà tài liệu thật có: giá trị điền tay trên tờ mẫu in sẵn, ô gộp
> trong nhãn, và tài liệu nhiều trang.
>
> Dự án thêm bốn năng lực: **quyết** (mục tiêu bằng lời → kế hoạch chạy có lý
> do), **diễn tả** (mực theo ô, cấu trúc bảng vào nhãn trên cả ba renderer),
> **soạn** (LLM soạn bố cục và biến thể từ chứng từ thật, có cổng và có người
> duyệt), và **kiểm chứng** (mỗi năng lực kết thúc bằng một phép đo downstream
> trên dữ liệu thật).
>
> Ràng buộc trung tâm quyết định toàn bộ kiến trúc: **LLM chạy lúc soạn luật,
> không lúc vẽ ảnh.** Nhờ đó nhãn vẫn dựng từ chính object đã vẽ, một seed vẫn
> dựng lại đúng một trang, và chi phí LLM tính theo **số loại tài liệu** chứ
> không theo **số ảnh** — khác biệt giữa ba đô la và bốn mươi lăm nghìn ở quy
> mô năm triệu ảnh.

---

## Liên quan

| | |
| --- | --- |
| [`README.md`](README.md) | trạng thái, mười quyết định đã chốt, bốn quyết định đã sửa |
| [`ke-hoach.md`](ke-hoach.md) | **làm gì** — mười việc, mô tả từng việc |
| [`brief-plan-run.md`](brief-plan-run.md) | **làm thế nào** — brief cho agent làm P1 |
| [`tu-dong-hoa-bang-llm.md`](tu-dong-hoa-bang-llm.md) | thiết kế đầy đủ, khảo sát ngoài, kinh tế |
| [`tang-cuong-bo-cuc.md`](tang-cuong-bo-cuc.md) · [`duong-ong.md`](duong-ong.md) | hai tài liệu chuyên đề |
