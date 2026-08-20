# Tự động hoá sinh dữ liệu — thiết kế hệ thống

> Bản viết lại sau khi khảo sát cả kho mã lẫn tình hình bên ngoài (8/2026).
> Bản trước chỉ trả lời câu hỏi hẹp "làm sao để LLM tạo được bố cục". Bản này
> hỏi câu rộng hơn: **hệ thống này cuối cùng phải sinh ra được những gì**, và
> kiến trúc nào chịu được điều đó — form điền tay, chữ ký, dấu đóng, bản
> photocopy nhiều trang, và những trường hợp chưa ai nêu tên.

---

## Mục lục

**[Phần 0 · Tóm tắt điều hành](#phần-0--tóm-tắt-điều-hành)**

**Phần I · Hiện trạng** — [§1 Repo là gì](#1-repo-là-gì-đo-lại-chứ-không-đọc-readme) · [§2 Bảy trục và chỗ chúng hết vốn](#2-bảy-trục-và-chỗ-chúng-hết-vốn) · [§3 Ai đang ra quyết định](#3-ai-đang-ra-quyết-định)

**Phần II · Khảo sát ngoài** — [§4 Sinh tài liệu tổng hợp](#4-sinh-tài-liệu-tổng-hợp-tình-hình-82026) · [§5 Chữ viết tay](#5-chữ-viết-tay-cập-nhật-khảo-sát-của-chính-repo) · [§6 Ba rủi ro đã có bằng chứng](#6-ba-rủi-ro-đã-có-bằng-chứng)

**Phần III · Thiết kế** — [§7 Chẩn đoán](#7-chẩn-đoán-repo-mô-hình-hoá-một-trang-một-nguồn-mực) · [§8 Trục thứ tám: lớp mực](#8-trục-thứ-tám-lớp-mực-ink) · [§9 Kiến trúc sáu tầng](#9-kiến-trúc-sáu-tầng) · [§10 Sáu tác nhân](#10-sáu-tác-nhân-mỗi-tác-nhân-một-hợp-đồng) · [§11 Vòng lặp đóng](#11-vòng-lặp-đóng-đo--chọn--sinh--đo-lại)

**Phần IV · Lộ trình** — [§12 Năm đợt](#12-năm-đợt) · [§13 Ưu tiên](#13-bảng-ưu-tiên) · [§14 Cái sẽ không xây](#14-cái-tôi-sẽ-không-xây)

**Phần V · Ràng buộc** — [§15 Chín bất biến](#15-chín-bất-biến) · [§16 Rủi ro](#16-rủi-ro) · [§17 Quản trị](#17-quản-trị--phần-không-ai-thích-đọc)

[Phụ lục A · Số đo](#phụ-lục-a--số-đo) · [Phụ lục B · Nguồn](#phụ-lục-b--nguồn)

---

# Phần 0 · Tóm tắt điều hành

**Kết luận 1 — kiến trúc của repo này đang đứng đúng phía của lịch sử.**
Hướng đang thắng trong tài liệu tổng hợp năm 2025–2026 là *LLM viết mã/luật,
công cụ dựng hình vẽ ảnh, mã ấy đồng thời là nhãn* — CoSyn (Allen AI, 400K ảnh,
2,7M dòng chỉ dẫn, vượt GPT-4V trên 7 benchmark), DocGenie (CVPRW 2025, MLLM
sinh HTML có ví dụ mồi), DocDjinn (VLM + khuếch tán chữ tay, phát hành 140k
mẫu, đạt **87 % hiệu năng của bộ dữ liệu thật đầy đủ chỉ với 100 mẫu thật**).
Cả ba đều phải tự dựng phần *hạ tầng kiểm chứng* — bất biến, trôi phân phối,
vân tay tất định, cổng tiền kiểm. Repo này **đã có sẵn phần đó** và đang thiếu
đúng phần trên: người ra quyết định. Đó là một vị thế tốt, không phải một sự
tụt hậu.

**Kết luận 2 — nút thắt kỹ thuật không phải LLM, mà là mô hình dữ liệu.**
Repo hiện mô hình hoá **một trang, một nguồn mực**: mọi ký tự trên tờ giấy đều
do cùng một máy in đặt xuống. Không một trong bảy trục nào diễn tả được câu
"nhãn in sẵn, giá trị viết tay" — mà đó chính là ca người dùng nêu, và cũng là
`handwriting_fill`, thứ [`hoa-tiet-de-xuat.md`](hoa-tiet-de-xuat.md) gọi là
**khoảng trống lớn nhất** của bộ dữ liệu. Đề xuất trung tâm của tài liệu này là
**trục thứ tám: `ink`** — nguồn mực khai ở mức *ô*, không ở mức *trang* (§8).
Một thay đổi, mở ra: form điền tay, chữ ký, dấu tích kế toán, gạch xoá, bút dạ
quang, con dấu đóng đè, và ô bị bôi đen.

**Kết luận 3 — thứ chặn đường LLM vẫn là thiếu schema, y như bản trước.**
`rules/*.yaml` từ chối khoá lạ; `layouts/*.yaml` thì không. Đã chứng minh lại:
thêm `headr:` và `algin:` vào một bản sao layout thì `build_grid` vẫn dựng ra
21 dòng 40 ô, không một tiếng động. Với LLM, đây là chế độ hỏng số một. Schema
phải là việc đầu tiên, và nó **vừa là cổng vừa là hợp đồng** — cùng một file
phục vụ cả hai.

**Kết luận 4 — có ba cái bẫy đã được đo ở nơi khác, đừng đo lại bằng tiền
mình.** (a) *Model collapse*: giữ ≥ 5 % dữ liệu thật thì tránh được sụp dài
hạn, 100 % tổng hợp thì phân kỳ tuyến tính theo số vòng; và **tích luỹ** an
toàn hơn **thay thế**. (b) *FID không đo được ích lợi*: một bộ dữ liệu đẹp hơn
theo FID vẫn có thể dạy kém hơn — phải đo bằng hiệu năng downstream. (c) *Ép
định dạng làm giảm chất lượng suy luận*: đừng bắt LLM vừa nghĩ vừa xuất ra
YAML hợp lệ trong một lượt.

**Kiến trúc đề xuất, một hình:**

```
  NGƯỜI ─ mục tiêu, chứng từ thật, quyền phủ quyết
     │
     ▼
  ┌──────────────────────── AUTHOR-TIME (có LLM, có người duyệt) ───────────┐
  │  A1 soạn bố cục   A2 soạn corpus   A3 soạn hoạ tiết   A4 lập kế hoạch   │
  │            ↓ đề xuất          ↓                ↓              ↓         │
  │      proposals/  ──▶  A5 phản biện  ──▶  chuỗi cổng  ──▶  người duyệt   │
  └────────────────────────────────┬────────────────────────────────────────┘
                                   │  commit YAML
                                   ▼
  ┌──────────────────── RENDER-TIME (không LLM, tất định) ──────────────────┐
  │  rulebase ─▶ Grid(+ink) ─▶ 3 renderer ─▶ ink/ ─▶ degradation/ ─▶ ảnh    │
  │                                          (mới)                          │
  └────────────────────────────────┬────────────────────────────────────────┘
                                   ▼
              đo: proof · drift · invariants · downstream ──┐
                                   ▲                        │
                                   └────────────────────────┘
                                     vòng lặp đóng (§11)
```

**Thứ tự làm, ngắn gọn:** schema (M0) → lớp mực + form điền tay (M1) → tác nhân
soạn bố cục (M2) → vòng lặp đóng (M3) → mở rộng (M4). Mỗi đợt dừng được, và
sau M2 là đã đạt yêu cầu "LLM lập luận, lựa chọn, tạo bố cục".

---

# Phần I · Hiện trạng

## 1. Repo là gì (đo lại, chứ không đọc README)

Một rule-base, ba renderer. Nội dung quyết một lần trong `rulebase/`, biến
thành pixel theo ba đường; cả ba nhận cùng `(recipe, receipt, grid)` và ghi
cùng một `metadata.jsonl`.

```
rules/*.yaml (7 thuộc tính) ──▶ sample_recipe ──▶ Recipe
corpus/vi/ en/              ──▶ build_receipt ──▶ Receipt (+ nhãn)
layouts/*.yaml (16 bố cục)  ──▶ build_grid    ──▶ Grid (cells + marks)
                                                   │
                     ┌─────────────────────────────┼───────────────────────┐
                     ▼                             ▼                       ▼
             synthdog (glyph)               html (Chromium)        genalog (WeasyPrint)
                     └─────────── degradation/ ────┴───────────────────────┘
                                          ▼
                              jpg + metadata.jsonl + boxes
```

Đo trong môi trường này (Python 3.11.15, **chưa dựng venv renderer nào**):

| lệnh | kết quả |
| --- | --- |
| `python -m pytest` | **599 passed, 4 skipped, 1 xfailed**, 78 s |
| `python tasks.py check` | 84 file Python biên dịch |
| `python tasks.py check-rules` | sạch, trừ `degradation not importable` (thiếu numpy/opencv ở đây) |
| `python tasks.py check-corpus` | vi 12 nhóm, en 5 nhóm, hợp lệ |
| `python tasks.py distribution` | 2000/2000 lần bốc, 16 bố cục trong 6 họ |

Cái đã tự động — nhiều hơn cảm giác ban đầu, và liệt kê ra để kế hoạch không đi
xây lại:

| đã có | ở đâu | bảo đảm gì |
| --- | --- | --- |
| Khai báo một lần chạy | `pipeline.yaml` + `config.py` | **khoá lạ thì dừng** |
| Chia shard tất định, resume nguyên khối | `plan.py`, `worker.py` | `DONE` ghi cuối, nguyên tử; shard dở thì xoá làm lại |
| Ghi đè trọng số theo run | `config.apply_overrides` | chỉ `weight/tags/requires/excludes`, và phải trỏ vào thứ **có thật** |
| Preflight | `preflight.py` | giá trị luật chết, thiếu asset, **phủ glyph tiếng Việt**, tràn khổ giấy |
| Bất biến từng ảnh | `invariants.py` | số học tiền, quad trong khung, không ô glyph rỗng, **mọi giá trị nhãn đều được in** |
| Trôi phân phối | `drift.py` | đã trừ nhiễu lấy mẫu của chính cỡ shard |
| Vân tay vàng | `tools/baseline.py` | sha256 từng ảnh; chụp lại **bắt buộc** có `REASON` |
| Chứng minh OCR | `tools/ocr_proof.py` | chấm không phụ thuộc thứ tự đọc, tách theo bố cục / mức làm cũ / trường |
| Mô hình chi phí | `tools/profile_pipeline.py` | dự đoán được thời gian trước khi chạy |

> **Lệch tài liệu (đã sửa trong đợt này):** README từng ghi `417 passed` và
> `64 python files`. Đã cập nhật và đánh dấu † vì đo ở môi trường không có venv
> renderer — một bảng trộn điều kiện đo mà không nói ra thì kém giá trị hơn
> bảng nói ra.

## 2. Bảy trục và chỗ chúng hết vốn

| trục | giá trị | trục này diễn tả được gì | **không** diễn tả được gì |
| --- | ---: | --- | --- |
| `document` | 17 | loại chứng từ, corpus, các trường | một tờ có **hai** loại nội dung |
| `layout` | 16 (6 họ) | cột, section, khổ giấy, kiểu kẻ | ô gộp *trong nhãn*; nhiều trang |
| `content` | 12 | bỏ dấu, viết hoa, định dạng tiền, VAT | ai viết phần nào |
| `visual` | 7 | font, cỡ, lề, giấy, độ cong | **một trang có hai loại mực** |
| `color` | 5 | mực, nền, màu nhấn | màu bút khác màu mực in |
| `ornament` | 21 (4 họ) | dấu, hoa văn, mã vạch — "mực không phải chữ" | *(chưa renderer nào ghép lên trang)* |
| `augmentation` | 15 | làm cũ, chụp lại, photocopy | hư hại làm **đổi nhãn** (gạch xoá, bôi đen) |

Tích Descartes: **35.985.600** tổ hợp trước khi nhân corpus, số mặt hàng và
seed. Nghĩa là **repo không nghèo vì thiếu tổ hợp**. Nó nghèo ở những chỗ mà
*không tổ hợp nào diễn tả được* — cột phải của bảng trên.

Ba khoảng trống lớn nhất, xếp theo mức chặn:

1. **Không có mực viết tay.** `ff9a9f0` gỡ cả họ nét tay với lý do ghi rõ:
   *"một mặt chữ in bị làm lệch không phải là chữ viết tay"*. Đúng — và từ đó
   khoảng trống chưa được lấp. Mọi tờ mẫu sinh ra đều trống trơn hoặc in máy
   toàn bộ, trong khi **tờ mẫu tồn tại là để được điền tay**.
2. **`ornament` được bốc, được ghi vào `metadata.jsonl`, và chưa renderer nào
   vẽ nó lên trang.** `rulebase/README.md` §4b nói thẳng điều này. Nghĩa là hôm
   nay nhãn khai một con dấu mà ảnh không có — đúng loại lệch nhãn↔ảnh mà
   `invariants.py` sinh ra để bắt, chỉ là nó chưa bắt trục này.
3. **Một ảnh = một trang.** `metadata.jsonl` không có `doc_id` hay `page`. Một
   tập hoá đơn nhiều trang, một bảng kê ba tờ, một hợp đồng — không diễn tả
   được.

## 3. Ai đang ra quyết định

| # | việc | hôm nay | đầu ra |
| --- | --- | --- | --- |
| 1 | Đo tờ giấy thật → `layouts/<id>.yaml` | người, bằng mắt | YAML |
| 2 | Chọn họ, đặt `requires` | người | khối trong `rules/layout.yaml` |
| 3 | Đặt trọng số, cân mix | người, sau `make distribution` | số trong `rules/*.yaml` |
| 4 | Ngữ nghĩa trường mới | người | **Python** (`content.py`) |
| 5 | Gắn bố cục vào họ CSS | người | **Python** (`sheets.FAMILIES`) |
| 6 | Đọc `ocr_report.json` → quyết sửa gì | người | *không có đầu ra máy đọc được* |

Việc 1–3 là YAML thuần. Việc 6 là suy luận trên số đo. Việc 4–5 là Python.
Ranh giới đó quyết định thứ tự giao việc cho máy (§12).

---

# Phần II · Khảo sát ngoài

Repo này đã có thói quen tốt: [`khao-sat-sinh-chu-viet-tay.md`](khao-sat-sinh-chu-viet-tay.md)
xếp hạng tám kho mã theo đúng hai câu hỏi mà bộ dữ liệu cần, chứ không theo số
sao. Phần này làm việc tương tự cho **cả bài toán**, và cập nhật khảo sát chữ
viết tay theo những gì xuất hiện từ đó tới nay.

## 4. Sinh tài liệu tổng hợp: tình hình 8/2026

Bốn công trình đáng đọc, và điều đáng giá là **cả bốn đều hội tụ về cùng một
kiến trúc** — cái mà bản trước của tài liệu này gọi là *author-time*.

### 4.1 CoSyn — LLM viết **mã**, mã chính là nhãn

Allen AI. LLM chỉ-văn-bản sinh ra **mã dựng hình** (Python, HTML, LaTeX); công
cụ dựng hình chạy mã ra ảnh; **chính mã đó** là nhãn văn bản để sinh dữ liệu
chỉ dẫn. 400K ảnh, 2,7M dòng chỉ dẫn, và mô hình học từ đó **vượt GPT-4V và
Gemini 1.5 Flash** trên bảy benchmark.

Đây là bằng chứng mạnh nhất cho luận điểm trung tâm: *đừng để mô hình sinh
pixel, hãy để nó sinh thứ dựng ra pixel* — vì thứ đó đồng thời là nhãn chính
xác. Repo này đã làm đúng như vậy từ đầu; khác biệt là ở chỗ CoSyn để LLM viết
**mã tự do** còn repo này có **một ngữ pháp hẹp** (`layouts/*.yaml`). Ngữ pháp
hẹp đổi tính tổng quát lấy tính kiểm chứng được — và với một bộ dữ liệu có
nhãn toạ độ thì đó là đổi đúng chiều.

### 4.2 DocGenie — ví dụ mồi, sinh HTML, và một thước đo đáng mượn

CVPRW 2025. MLLM tiền tuyến sinh tài liệu **dựa trên ví dụ mồi** (seed-guided),
đầu ra là HTML, để bám theo quy ước nội dung và bố cục của từng lĩnh vực.

Phần đáng mượn ngay là thước đo: **Layout-FID** — FID nhưng thay InceptionV3
bằng **LayoutLMv3**, nên nó bắt được đặc trưng *văn bản và cấu trúc* chứ không
chỉ đặc trưng thị giác. Repo này hiện không có bất kỳ thước đo nào trả lời câu
"bộ ảnh sinh ra có *giống phân phối tài liệu thật* không" — chỉ có "OCR đọc
được không" và "mix có khớp luật không". Hai câu đó khác nhau.

### 4.3 DocDjinn — đúng ca người dùng nêu

VLM + **khuếch tán chữ viết tay**, tách rời ngữ nghĩa khỏi thị giác
(*semantic-visual decoupling*), chọn mồi theo cụm rồi lấy mẫu có tham số để bố
cục sinh ra bám phân phối của tập nguồn. Phát hành **hơn 140k mẫu**. Con số
đáng nhớ: **chỉ với 100 mẫu thật, đạt trung bình 87 % hiệu năng của bộ dữ liệu
thật đầy đủ** trên 11 benchmark (KIE, QA, phân loại, phân tích bố cục).

Đây chính xác là "background HTML có chữ + nội dung viết tay" mà câu hỏi nêu,
đã có người làm và đo. Hai điều rút ra:

* **Ca này khả thi và có giá trị đo được** — không phải một ý tưởng đẹp chưa ai
  thử.
* **Cách họ giữ nhãn khác cách repo này giữ nhãn.** DocDjinn để VLM *sinh chú
  thích*; repo này dựng nhãn từ chính object đã vẽ. Cách của repo **mạnh hơn**
  và không nên đổi — nhưng nó đặt một ràng buộc mà DocDjinn không có: chữ viết
  tay ở đây phải đi đường `from_receipt`, tức nội dung lấy từ `Receipt` đã sinh
  ra tờ giấy. Đó không phải chi tiết triển khai, đó là điều kiện tiên quyết.

### 4.4 LayoutPrompter — ba thành phần, không cần huấn luyện

NeurIPS 2023, và vẫn là khung tham chiếu. Ba thành phần:

1. **tuần tự hoá vào–ra** — ràng buộc và bố cục đều thành chuỗi LLM đọc được
   (họ dùng HTML);
2. **chọn ví dụ động** — lấy k ví dụ *gần nhất với yêu cầu hiện tại*, không
   phải k ví dụ cố định;
3. **xếp hạng bố cục** — sinh nhiều phương án rồi chấm, giữ phương án tốt nhất.

Cả ba ánh xạ thẳng vào thiết kế tác nhân A1 ở §10, và thành phần (3) là thứ
bản trước của tài liệu này bỏ sót.

### 4.5 DataEnvGym — tác nhân sinh dữ liệu theo điểm yếu của học trò

ICLR 2025 Spotlight. Khung "môi trường giáo viên" cho **tác nhân sinh dữ liệu**:
chính sách sinh dữ liệu lập kế hoạch → cỗ máy sinh biến kế hoạch thành dữ liệu
→ học trò báo lại lỗi và kỹ năng còn yếu → lặp. Kết luận: tác nhân **cải thiện
được** học trò qua nhiều vòng, trên bốn lĩnh vực.

Một kết quả liên quan, và nó tiết kiệm tiền: *sinh dữ liệu có-học-trò-trong-vòng
hiệu quả hơn sinh một lần tĩnh*, và **tiêu chí chọn kiểu active-learning đơn
giản lại thắng các cách tinh vi hơn**. Nghĩa là §11 nên bắt đầu bằng một quy
tắc chọn tầm thường (lấy mẫu tỉ lệ nghịch với điểm OCR theo bố cục), không phải
bằng một mô-đun khám phá kỹ năng.

### 4.6 Vị thế của repo này

| | CoSyn | DocGenie | DocDjinn | **repo này** |
| --- | --- | --- | --- | --- |
| ai quyết cấu trúc trang | LLM (mã tự do) | MLLM (HTML, có mồi) | VLM + lấy mẫu theo cụm | **người** (YAML) |
| nhãn từ đâu | chính mã sinh ra | mô hình chú thích | VLM chú thích | **object đã vẽ** |
| hộp từng trường | có (mã) | — | có | **có, từ engine vẽ** |
| nhiều engine vẽ | có (3 loại mã) | HTML | — | **có (3)** |
| làm cũ có mô hình vật lý | — | — | có | **có (DocCreator, 10 mô hình)** |
| tiền kiểm / bất biến / trôi | — | — | — | **có** |
| chữ viết tay | — | — | **có** | **không** |
| nhiều trang | — | — | — | không |
| tiếng Việt | — | — | — | **có, là trọng tâm** |

Đọc bảng này theo cột cuối: repo mạnh ở **hạ tầng kiểm chứng** và **tiếng
Việt**, yếu ở **người ra quyết định** và **chữ viết tay**. Đó là hai việc phải
làm, và chúng độc lập nhau nên làm song song được.

## 5. Chữ viết tay: cập nhật khảo sát của chính repo

[`khao-sat-sinh-chu-viet-tay.md`](khao-sat-sinh-chu-viet-tay.md) xếp hạng tám
kho và chọn WriteViT; [`writevit.md`](writevit.md) dựng nó lên rồi **đo xem nó
không viết được gì**. Kết quả đo đó vẫn là dữ kiện quan trọng nhất trong toàn
bộ chủ đề này, nên nhắc lại:

> WriteViT viết đúng chữ có dấu, kể cả dấu chồng (`ệ`, `ộ`, `ễ`). Nhưng
> **chữ số hỏng hoàn toàn** — `1500000` ra một nét ngoằn ngoèo, `15 03 2025` ra
> `1S 0h ảvcls`. Nguyên nhân tìm được trong mã huấn luyện: từ điển bị chia đôi
> và nửa chứa chữ số **không bao giờ được lấy mẫu** — 0/10.131 token mà bộ sinh
> từng thấy có chứa một chữ số. Bảng chữ cũng **không có** `,` `.` `/` `-`, nên
> `15/03/2025` và `1.500.000` không sinh được kể cả sau khi sửa chuyện chữ số.

Đây là **chặn cứng** với hoá đơn Việt Nam, vì phần lớn ô cần điền là số: số
tiền, ngày, mã số thuế, số hoá đơn.

### 5.1 Từ lúc khảo sát tới nay có gì mới

| | năm | điểm mạnh với bài toán này | điểm yếu |
| --- | --- | --- | --- |
| **DiffusionPen** (ECCV 2024) | 2024 | khuếch tán tiềm ẩn few-shot, mã hoá phong cách tường minh | IAM/CVL — bảng chữ Latin không dấu |
| **One-DM** (ECCV 2024) | 2024 | **một ảnh mẫu** là đủ để bắt phong cách | như trên |
| **VATr++** | 2024 | tổng quát hoá tốt hơn cho **ký tự hiếm** — đúng bài của dấu tiếng Việt | trên tiếng Việt VATr tụt hạng mạnh (FID 23,9 so với WriteViT 6,2) |
| **Emuru** | 2025 | sinh ảnh tiềm ẩn tự hồi quy; **độ dài linh hoạt** → sinh được cả *dòng*, không chỉ *từ* | chưa có chứng cứ tiếng Việt |
| **Eruku** | 2026 | như trên, zero-shot sang phong cách chưa gặp tốt hơn | như trên |
| **HandwritingAgent** | 2026 | **LLM suy luận hình học rồi sinh chuỗi nét → SVG**; độc lập độ phân giải, sửa được, đọc hiểu được | phụ thuộc năng lực LLM nền; chưa nêu tiếng Việt |

Hai điều mới đáng đổi quyết định:

**(a) `Emuru`/`Eruku` gỡ đúng cái chặn "mức từ".** WriteViT sinh theo *từ* và
khoảng cách giữa các từ do người gọi đặt — một dòng ghép từ các từ rời sẽ lộ,
vì chữ tay thật không đều khoảng cách. Sinh theo *dòng* gỡ được chuyện đó.

**(b) `HandwritingAgent` là câu trả lời trực tiếp cho "LLM reasoning".** Nó
không phải mô hình sinh ảnh; nó là **một mô hình suy luận vẽ ra chuỗi nét trên
lưới rời rạc rồi xuất SVG**. Đầu ra là *vector* — đúng dạng mà khảo sát của
chính repo kết luận là tổng quát nhất: vẽ lại ở mọi dpi, mọi bề rộng ngòi, mọi
màu mực, xoay theo dòng kẻ của ô. Rủi ro: chưa ai chứng minh nó đặt đúng dấu
tiếng Việt, và chất lượng phụ thuộc LLM nền.

### 5.2 Chữ số là bài **dễ hơn** chữ — và đó là lối ra

Một nhận xét không có trong khảo sát cũ, nhưng gỡ được nút thắt lớn nhất:

> **Dấu thanh là bài riêng của tiếng Việt. Chữ số thì không.**
> `0123456789` viết tay của người Việt và người Anh là **cùng một hình**. Nên
> chỗ WriteViT chặn cứng có thể lấp bằng **một nguồn mực thứ hai** chuyên chữ
> số, huấn luyện trên dữ liệu tiếng Anh/quốc tế, mà không mất gì về tính bản
> địa.

Từ đó ra một kiến trúc lai, và nó rẻ hơn hẳn việc huấn luyện lại:

| nội dung ô | nguồn mực | vì sao |
| --- | --- | --- |
| tên người, địa chỉ, tên hàng | WriteViT `vn_ckpt` | đã đo: dấu đặt đúng |
| số tiền, ngày, MST, số hoá đơn | mô hình nét chữ số (IAM-OnDB / VNOnDB) | ngôn ngữ trung tính |
| dấu `,` `.` `/` `-` | nét dựng thủ công, hoặc từ mô hình nét | 4 hình, không đáng dùng mạng |
| chữ ký | tập chữ ký có giấy phép, tách nền | chữ ký là nếp đã luyện, không phải đường cong ngẫu nhiên — `ff9a9f0` đã đúng chỗ này |
| dấu tích ✓ | nét dựng thủ công | một nét, dễ nhất trong họ |

Và **VNOnDB có sẵn chữ số viết tay** — `writevit.md` đếm được 2.579/92.048 nhãn
có chứa chữ số (2,80 %), 1.388 nhãn viết hoa toàn phần. Dữ liệu không thiếu;
chỉ bộ lọc từ điển của WriteViT gạt chúng ra.

### 5.3 Cảnh báo phải đọc trước khi đầu tư

*Quo Vadis Handwritten Text Generation for Handwritten Text Recognition?* (2025)
hỏi thẳng: chữ viết tay tổng hợp có thật sự làm mô hình nhận dạng tốt lên
không. Kết luận **không đồng nhất** — lợi ích phụ thuộc chất lượng sinh, đặc
điểm tập dữ liệu, và cách trộn. Khuyến nghị của họ: *kiểm chứng mẫu tổng hợp
trên chính bài toán của mình trước khi cam kết nguồn lực; dùng như nguồn bổ
sung, không phải nguồn chính.*

Áp vào đây: **đợt M1 phải kết thúc bằng một phép đo downstream, không phải bằng
một bức ảnh đẹp.** Cụ thể ở §12.

## 6. Ba rủi ro đã có bằng chứng

### 6.1 Model collapse — và vì sao `provenance` không phải hình thức

Nghiên cứu 2024–2026 hội tụ ở mấy con số dùng được:

* **Giữ ít nhất ~5 % dữ liệu thật thì tránh được sụp dài hạn**; 100 % tổng hợp
  thì phân kỳ tuyến tính theo số vòng.
* **Tích luỹ** dữ liệu qua các vòng an toàn hơn **thay thế** — sụp tránh được
  hoàn toàn nếu dữ liệu được cộng dồn thay vì bị ghi đè.
* Chỉ trộn tỉ lệ là **chưa đủ**; phải *chọn lọc* dữ liệu tổng hợp theo chỗ
  phân phối thật còn trống.

Bản riêng của rủi ro này trong repo tinh vi hơn "trộn tỉ lệ". Nếu bố cục do LLM
soạn từ những tờ giấy **LLM tưởng tượng ra**, thì phân phối bố cục trôi khỏi
thực tế mà **không có neo nào kéo lại** — và không cổng nào hiện có phát hiện
được, vì mọi cổng đều kiểm tính nhất quán nội tại chứ không kiểm tính giống
thật. Đó là lý do mỗi bố cục phải truy được về một **file chứng cứ**, và tỉ lệ
`llm_proposed` phải đếm được và có trần. Không phải để đẹp hồ sơ.

### 6.2 FID đo cái đẹp, không đo cái dạy được

Kết quả lặp lại nhiều nơi: FID và các biến thể *tập trung vào độ trung thực thị
giác và không phản ánh ích lợi downstream*, và lệch khỏi cảm nhận người khi có
nhiễu loạn. Đồng thời có kết quả tích cực: mô hình học **chủ yếu bằng dữ liệu
tổng hợp** đạt trong khoảng **4 %** so với mô hình học bằng dữ liệu thật ở
nhận dạng bố cục (DocBank, PubLayNet), NER (FUNSD), phân loại (RVL-CDIP).

Kết luận cho repo: Layout-FID (§4.2) đáng thêm vì nó rẻ và bắt được cái mà
`drift.py` không bắt — nhưng **không được để nó thành mục tiêu tối ưu**.
Thước đo cuối cùng phải là *huấn luyện một mô hình nhỏ và đo trên tập thật*.

### 6.3 Ép định dạng làm giảm chất lượng suy luận

*Let Me Speak Freely?* đo được rằng ràng buộc định dạng đầu ra làm **giảm** chất
lượng suy luận của LLM. Trong khi đó giải mã có ràng buộc đã rất trưởng thành —
XGrammar là backend mặc định của vLLM/SGLang/TensorRT-LLM từ 3/2026, dưới 40 µs
mỗi token.

Kết luận thiết kế, cụ thể: **tách hai lượt**. Lượt một cho LLM *suy luận tự do*
về tờ giấy (nó có mấy khối, cột nào, chỗ nào để trống cho người điền) — văn
xuôi. Lượt hai *chuyển bản suy luận đó thành YAML* dưới ràng buộc schema. Ép
schema ngay từ lượt một là trả bằng chất lượng bố cục để mua lấy sự tiện.

---

# Phần III · Thiết kế

## 7. Chẩn đoán: repo mô hình hoá "một trang, một nguồn mực"

Đọc `rulebase/layout.py`, mọi thứ đặt lên trang đều đi qua đúng hai kiểu:

```python
@dataclass
class Cell:   # chữ
    text: str; role: str; row: int; col0: int; col1: int
    align: str; scale: float; bold: bool

@dataclass
class Mark:   # không phải chữ: rule | fill | frame
    kind: str; row0: int; col0: int; row1: int; col1: int
    weight: float; tone: float
```

Không có trường nào nói **mực này từ đâu ra**. Renderer suy ra từ
`recipe.visual` — một font, một cỡ, một độ đậm cho cả trang. Đó là mô hình đúng
cho một tờ hoá đơn in ra từ một máy in, và **sai** cho gần như mọi thứ còn lại
mà một bộ dữ liệu tài liệu Việt Nam cần:

| tờ giấy thật | có mấy nguồn mực |
| --- | --- |
| hoá đơn GTGT in sẵn, điền tay | **2** — máy in (nhãn) + bút bi (giá trị) |
| ...cộng dấu tròn đóng lên chữ ký | **3** |
| biên lai có dấu tích kế toán bằng bút đỏ | 2 |
| hợp đồng có dòng bị gạch xoá và chữ "huỷ" viết bên lề | 2, và **nhãn phải đổi** |
| bản photocopy đã bị bôi đen một ô | 2, và **nhãn phải giấu đi một trường** |
| giấy uỷ quyền có chữ ký và điểm chỉ | 3 |

Cột phải là thứ trục nào cũng không nói được. Và đây không phải suy đoán về
tương lai: đó chính là danh sách trong
[`hoa-tiet-de-xuat.md` §B](hoa-tiet-de-xuat.md) — `handwriting_fill`,
`signature_scrawl`, `tick_accounting`, `strikethrough_line`, `pen_underline`,
`highlighter_swipe` — sáu mục **đã dựng một lần rồi gỡ đi**, vì cách tiếp cận
sai chứ không vì tham số sai.

Cách tiếp cận sai đó có tên: chúng được xếp vào `ornament`, tức là **overlay
dán lên trang đã vẽ xong**. Một chữ ký dán lên thì được. Một **giá trị điền
tay** thì không: nó là *nội dung*, nó phải có hộp, phải vào nhãn, phải khớp với
`Receipt`. Dán một overlay không cho ta thứ nào trong ba thứ đó.

**Chẩn đoán:** nguồn mực phải là thuộc tính của **ô**, không phải của **trang**,
và không phải của lớp overlay.

## 8. Trục thứ tám: lớp mực (`ink`)

### 8.1 Ý tưởng, một câu

Mỗi `Cell` mang thêm một trường `ink`. `press` (mặc định) nghĩa là renderer vẽ
như hôm nay; các giá trị khác nghĩa là **renderer chỉ ghi hộp và để ô trống**,
rồi một tầng dùng chung vẽ mực vào đúng hộp đó — cùng chỗ, cùng lối, cùng lý
lẽ như `degradation/`.

```python
@dataclass
class Cell:
    text: str; role: str; row: int; col0: int; col1: int
    align: str = "left"; scale: float = 1.0; bold: bool = False
    ink: str = "press"          # press | hand | stamp | redact
```

### 8.2 Bốn nguồn mực, và vì sao đúng bốn

| `ink` | ai đặt mực | hộp | nhãn | trộn ảnh |
| --- | --- | --- | --- | --- |
| `press` | máy in / máy in nhiệt | có | giá trị thật | thay thế |
| `hand` | người cầm bút | có | giá trị thật **+ `ink: hand`** | nhân (mực trong) |
| `stamp` | con dấu, dấu ngày | có | giá trị thật **+ `ink: stamp`** | nhân |
| `redact` | bút xoá, băng dán, ô bị bôi đen | **có hộp, không có chữ** | trường **bị giấu** | phủ đè |

`redact` không phải cho vui. Nó là ca duy nhất mà **nhãn phải nói ít hơn nội
dung** — và hôm nay `invariants.py` sẽ báo lỗi ca đó, đúng như thiết kế, vì nó
coi mọi trường không in ra là lỗi. Có `redact` thì "bị giấu có chủ ý" khác được
với "quên in", và đó là một khả năng downstream thật (đọc tài liệu đã che
thông tin).

Ba giá trị đầu đủ để diễn tả cả sáu mục đã bị gỡ ở §7, cộng con dấu mà
`ornament` đang bốc nhưng chưa vẽ.

### 8.3 Ai quyết ô nào viết tay

Một file luật mới, `rules/ink.yaml` — trục **thứ tám được thêm vào**, nhưng
**bốc thứ tư**. Vị trí trong `_order.yaml`: **sau `content`, trước `visual`**,
vì nó cần biết chữ là gì (`content` đã quyết bỏ dấu hay chưa) và phải đặt thẻ
*trước* khi `visual`, `color`, `ornament`, `augmentation` bốc, để bốn trục sau
nhìn thấy nó. Nhắc lại lý lẽ của `rulebase/README.md`: thứ tự là **nhân quả**,
không phải thứ tự thêm vào — người ta điền tờ mẫu trước khi tờ giấy quyết định
sẽ nhàu thế nào.

Thêm một trục là **một file YAML và một dòng trong `_order.yaml`**, không sửa
Python — `attribute_order()` đọc manifest và `validate()` kiểm ba kiểu sai. Đó
là thiết kế đã có sẵn, và đây là lần đầu nó được dùng đúng mục đích.

```yaml
# rules/ink.yaml — trục thứ 8, bốc thứ 4/8
options:
  - id: all_printed
    weight: 10
    params: {hand_roles: []}

  # `blank_form` là thẻ MỚI, đặt trên node `statutory_invoice` trong
  # rules/layout.yaml — chưa có hôm nay. Vai (`role`) thì đã có: layout.py
  # gắn `invoice.field`, `meta.value`, `sign.name`, `invoice.words` … cho mọi ô.
  - id: hand_filled_parties
    weight: 3
    requires: [blank_form]
    tags: [has_handwriting, pen_ink]
    params:
      hand_roles: ["invoice.field", "meta.value"]
      pen: {colour: [ink_blue, ink_black], nib: [0.30, 0.45]}

  - id: hand_filled_full
    weight: 1
    requires: [blank_form]
    tags: [has_handwriting, pen_ink, hand_amounts]
    params:
      hand_roles: ["invoice.field", "meta.value", "invoice.words", "total.grand"]
      pen: {colour: [ink_blue], nib: [0.35, 0.50]}

  - id: signed_and_sealed
    weight: 2
    requires: [has_signature_block]
    tags: [has_handwriting, has_seal]
    params:
      hand_roles: ["sign.name"]
      stamp_roles: [signature_seller]      # neo của rules/ornament.yaml
```

Ba điều thiết kế ở đây, và mỗi điều đều là để **không lặp lại một sai lầm cũ**:

* **`requires: [blank_form]`** — chỉ tờ mẫu in sẵn mới được điền tay. Một biên
  lai nhiệt điền tay là chuyện không có thật. Thẻ đặt trong `rules/layout.yaml`
  ở mức **node họ**, nên cả họ `statutory_invoice` nhận một lần và bố cục thêm
  vào sau không quên được — đúng cơ chế §1b của `rulebase/README.md`.
* **`hand_roles` nói theo `role`, không theo toạ độ.** `Cell.role` đã tồn tại
  và đã là một vốn từ có dấu chấm phân cấp — `store.name`, `meta.value`,
  `invoice.field`, `invoice.words`, `sign.name`, `colhdr`, `footer` — do
  `builder.put(text, role, ...)` gắn ở mọi emitter. Nói theo toạ độ thì mỗi
  bố cục phải khai lại; nói theo vai thì một luật phủ cả mười sáu bố cục —
  cùng lý lẽ với `anchor: signature_seller` của `ornament`. Việc phải làm ở
  M0 là **đóng băng vốn từ đó thành hằng số** (`ROLES` trong `schema.py`), vì
  hôm nay nó chỉ là những chuỗi rải trong `layout.py`.
* **`pen` là màu riêng, không lấy từ `color`.** Mực bút không phải mực in. Trục
  `color` quyết mực máy in; bút xanh trên bản in đen là ca **thường gặp nhất**,
  và nó là tín hiệu mạnh để mô hình phân biệt hai lớp.

### 8.4 Mực vẽ ở đâu: tầng `ink/`, anh em với `degradation/`

```
Grid(+ink) ──▶ renderer vẽ press, chừa hộp cho phần còn lại ──▶ ink/ ──▶ degradation/ ──▶ ảnh
                     (3 sửa nhỏ)                              (1 tầng dùng chung)
```

Đây là **cùng một quyết định kiến trúc** mà `degradation/` đã đúng: một hiện
thực, ba renderer gọi, thay vì ba hiện thực trùng tên. Lý lẽ trong
`degradation/pipeline.py` áp nguyên văn — *"giữ chuyện này trong một hàm là
khác biệt giữa so sánh ba renderer và so sánh ba hiện thực làm cũ tình cờ
trùng tên"*.

Nhưng có **một khác biệt phải nói to**, vì nó quyết định chỗ đứng của tầng này:

> `degradation/` **không được** đổi kích thước ảnh và **không** sinh hộp — nó
> làm hỏng giấy, không viết thêm chữ. `ink/` thì **viết chữ**: nó phải sinh hộp,
> phải khai vào nhãn, và phải chịu `invariants.py` kiểm.
>
> Vì thế `ink/` **không phải** một degradation và **không được** đặt vào
> `rules/augmentation.yaml`. Đặt nhầm chỗ là cách chắc chắn nhất để có một tờ
> giấy có chữ mà nhãn không biết — đúng khiếm khuyết mà cả `invariants.py` lẫn
> `pipeline/drift.py` sinh ra để chặn.

API, cố ý giống `apply_recipe`:

```python
# ink/pipeline.py
def apply_ink(image, grid, receipt, recipe, seed=None) -> tuple[np.ndarray, list[dict]]:
    """Vẽ mọi ô không phải `press`, trả về ảnh và các hộp mới.

    Hộp đến từ chính renderer: một ô `ink != press` được renderer đặt chỗ và
    ghi quad như mọi ô khác, chỉ không vẽ glyph. Nên toạ độ ở đây không phải
    đo lại — đó là điều kiện để hộp chữ tay chính xác ngang hộp chữ in.
    """
```

Ba sửa nhỏ ở renderer, mỗi cái vài dòng:

| renderer | sửa gì |
| --- | --- |
| `synthdog` | ô `ink != press` → `TextLayer` trong suốt (giữ nguyên bố trí và quad), không đổ mực |
| `html` | `<span data-kind=... data-ink="hand">` với `color: transparent` — `getBoundingClientRect()` vẫn trả đúng hộp |
| `genalog` | như trên; PyMuPDF vẫn đọc được chuỗi ký tự nên hộp vẫn ra |

Chi tiết đáng giá của cách này: **hộp do engine bố trí văn bản tính ra**, nên
chữ viết tay chiếm đúng chỗ mà chữ in sẽ chiếm, và tự động vừa ô, tự động
xuống dòng theo cùng luật. Không cần một hệ toạ độ thứ hai — cùng lý lẽ đã dùng
cho `Mark` (`rulebase/README.md`: *"trên cùng lưới (row, column) mà các ô dùng,
nên không renderer nào cần hệ toạ độ thứ hai"*).

### 8.5 Nguồn chữ viết tay: một giao diện, nhiều bản dựng

```python
# ink/sources/__init__.py
class HandSource(Protocol):
    def can_write(self, text: str) -> list[str]:
        """Các ký tự nguồn này KHÔNG viết được. Rỗng nghĩa là viết được hết."""
    def write(self, text: str, *, writer: int, height_px: int,
              colour, rng) -> np.ndarray:      # BGRA
        ...
```

`can_write` đứng trước `write` chứ không phải ngược lại, và đó là bài học rút
thẳng từ `writevit.md`: WriteViT **không báo lỗi** khi gặp chữ số, nó vẽ ra một
nét ngoằn ngoèo trông như chữ. Một nguồn mực im lặng vẽ sai còn tệ hơn một
nguồn từ chối — vì nhãn vẫn khai đúng số tiền.

`make preflight` gọi `can_write` trên **mọi chuỗi mà `hand_roles` có thể tạo
ra**, y hệt cách nó đang kiểm phủ glyph của font. Cùng một kiểm tra, cùng một
lý do, chỉ khác nguồn mực.

Các bản dựng, theo thứ tự nên làm:

| bản dựng | dùng cho | trạng thái |
| --- | --- | --- |
| `writevit` | từ tiếng Việt có dấu | **đã dựng** (`tools/writevit/`), đã đo giới hạn |
| `digits_strokes` | chữ số và `,. /-` | phải làm — mô hình nét, ngôn ngữ trung tính (§5.2) |
| `signature_bank` | chữ ký | tập chữ ký có giấy phép, tách nền |
| `marks` | ✓, gạch chân, gạch xoá | nét dựng thủ công; rẻ nhất, làm trước để thông đường ống |
| `emuru` / `eruku` | cả dòng, thay `writevit` | khảo sát sau; **cần đo trên dấu tiếng Việt trước** |
| `svg_agent` | LLM sinh nét → SVG | thử nghiệm; hấp dẫn vì ra vector, chưa có chứng cứ tiếng Việt |

**Bắt đầu bằng `marks`, không phải bằng `writevit`.** Một dấu ✓ là một nét,
không đòi hình dạng chữ, và nó đủ để chứng minh cả đường ống — `Cell.ink` →
renderer chừa hộp → `ink/` vẽ → hộp vào `metadata.jsonl` → `invariants` kiểm →
`ocr_proof` tách nhóm. Chứng minh đường ống bằng thứ dễ nhất rồi mới thay ruột,
là đúng thứ tự.

### 8.6 Nhãn đổi những gì

Ít, và có chủ đích.

```jsonc
{
  "boxes": [
    {"kind": "party_value", "text": "Nguyễn Thị Bích Ngọc",
     "quad": [[..]], "ink": "hand"},          // ← trường mới
    {"kind": "total", "text": "1.500.000", "quad": [[..]], "ink": "press"}
  ],
  "ground_truth": { /* KHÔNG ĐỔI — giá trị vẫn là giá trị */ },
  "recipe": {"attributes": {"ink": {"id": "hand_filled_parties", "params": {...}}}}
}
```

`ground_truth` không đổi là có chủ ý: người mua tên gì thì tên đó, viết tay hay
in ra không đổi câu trả lời. Nhưng `ink` trên từng hộp là **tín hiệu huấn luyện
mới và thật** — "trường nào trên tờ mẫu này do người điền" là một bài downstream
có thật, và không bộ dữ liệu tiếng Việt nào hiện có nhãn đó.

Kiểm tra mới trong `invariants.py`, hai cái:

1. **Ô `hand` phải có mực thật trong hộp.** `ink_coverage` của hộp phải trên
   ngưỡng. Không thì nhãn khai một giá trị mà không ai viết — chính xác cùng
   loại lỗi mà `check_boxes.py` đang bắt cho chữ in.
2. **Ô `redact` phải *không* đọc được**, và trường tương ứng phải vắng mặt
   trong `ground_truth`. Đây là bất biến duy nhất chạy **ngược** chiều những
   cái đang có, nên phải viết riêng chứ không sửa cái cũ.

Và một nhóm mới trong `ocr_report.json`: `by_ink`. Điểm OCR trên ô viết tay
**sẽ tệ** — đó là kết quả đúng, không phải hồi quy. Trộn chung vào điểm tổng
thì một tờ điền tay kéo tụt cả bố cục và không ai đọc ra vì sao.

### 8.7 Trục này còn mở ra gì

Cùng một cơ chế, không thêm khái niệm nào:

| ca | cách diễn tả |
| --- | --- |
| chữ ký hai bên | `ink: hand` trên `role: signature_name`, nguồn `signature_bank` |
| dấu tròn đóng đè chữ ký | `ink: stamp`, trộn nhân — và **đây là chỗ `ornament` cuối cùng được vẽ lên trang** |
| dấu tích kế toán | `ink: hand`, nguồn `marks`, trên `role: item_row` |
| gạch xoá một dòng + chữ "huỷ" | `ink: hand` + cờ `struck: true` trên hộp; `ground_truth` đánh dấu dòng đó vô hiệu |
| bút dạ quang | `ink: hand`, trộn nhân, `role` phủ cả dải |
| ô bị bôi đen | `ink: redact` |
| điểm chỉ | `ink: stamp`, nguồn ảnh vân tay |
| bản carbon (liên 2) | *không* thuộc trục này — thuộc `visual` (một loại giấy) + một chuỗi làm cũ |

Dòng cuối đáng chú ý: nó cho thấy trục mới **không nuốt** những gì trục cũ đã
làm được. Ranh giới giữ nguyên như `hoa-tiet-de-xuat.md` đã đặt — *cố ý có mặt*
thì thuộc `ink`/`ornament`, *hư hại* thì thuộc `augmentation`.

### 8.8 Cái trục này **không** giải, và phải làm riêng

| khoảng trống | vì sao trục mực không giải | phải làm gì |
| --- | --- | --- |
| **một ảnh = một trang** | trang là đơn vị của `Grid`, không phải của mực | thêm `doc_id` + `page` vào `record.py`; `plan.py` cấp seed theo *tài liệu* chứ không theo *ảnh* |
| **ô gộp không vào nhãn** (đường lưới) | `_paint_bars` mô phỏng ô gộp chứ không mô hình hoá; xem [`brief-engine-html.md` §2](brief-engine-html.md) | `Cell` mang `colspan`/`rowspan`; nhãn nhận token cấu trúc như `tables.py` đã có |
| **không có TEDS** | thước đo, không phải nội dung | port TEDS, chấm `data/tables60` |
| **chỉ glyph backend cho quad xoay** | thuộc engine | hoặc thêm một engine cong, hoặc chấp nhận và ghi rõ |

## 9. Kiến trúc sáu tầng

Đặt tên cho từng tầng, vì cái không có tên thì không ai bảo vệ được ranh giới
của nó.

```
┌─ T5 · QUẢN TRỊ ───────────────────────────────────────────────────────┐
│  giấy phép · nhãn "tổng hợp" · truy xuất nguồn · trần llm_proposed    │  §17
├─ T4 · ĐIỀU PHỐI ──────────────────────────────────────────────────────┤
│  mục tiêu → kế hoạch chạy → đo → sửa kế hoạch      (A4, A5, vòng lặp) │  §11
├─ T3 · SOẠN THẢO ──────────────────────────────────────────────────────┤
│  bố cục · corpus · hoạ tiết · luật        (A1, A2, A3 — CÓ LLM)       │  §10
├─ T2 · HỢP ĐỒNG ───────────────────────────────────────────────────────┤
│  schema bố cục · schema luật · schema mực · vốn từ `role` và `from`   │  §12 M0
├─ T1 · NGUỒN MỰC ──────────────────────────────────────────────────────┤
│  press (3 engine) · hand (n nguồn) · stamp · redact                   │  §8
├─ T0 · NỀN TẤT ĐỊNH ───────────────────────────────────────────────────┤
│  rulebase · pipeline · degradation · bất biến · trôi · vân tay vàng   │  đã có
└───────────────────────────────────────────────────────────────────────┘
```

Quy tắc một chiều: **T3 và T4 được đọc mọi tầng dưới, nhưng chỉ được ghi ra
T2** — tức là ra YAML hợp schema. Không tác nhân nào được sửa T0 và T1. Đó là
toàn bộ chính sách an toàn, viết trong một câu.

Hệ quả kiểm tra được, và nên có một test khẳng định nó:

```python
def test_no_agent_code_reaches_the_deterministic_core():
    """Không file nào trong rulebase/, generators/, degradation/, ink/,
    pipeline/ được import tầng tác nhân hay một client mạng."""
```

Một test như thế đáng giá hơn một đoạn văn trong CONTRIBUTING, vì nó không phai.

## 10. Sáu tác nhân, mỗi tác nhân một hợp đồng

| | tác nhân | vào | ra | cổng |
| --- | --- | --- | --- | --- |
| **A1** | Soạn bố cục | chứng từ thật (ảnh/PDF/mô tả) + schema + k ví dụ gần nhất | `proposals/<id>/layout.yaml` + khối `rules/layout.yaml` | schema → test_layout → preflight → preview → 3 ảnh thật |
| **A2** | Soạn corpus | profile + n dòng mẫu + bảng chữ | dòng TSV, `source: llm` | check-corpus → **phủ glyph** → trần tỉ lệ |
| **A3** | Soạn hoạ tiết | mô tả hoạ tiết + danh mục chưa làm | vá `make_ornaments.py` + khối `ornament.yaml` | preflight hai chiều → mắt người |
| **A4** | Lập kế hoạch chạy | mục tiêu + `ocr_report.json` + `drift.json` + distribution | `pipeline.yaml` **kèm lý do** | `config.py` (đã có) |
| **A5** | Phản biện | đề xuất của A1–A4 | phán quyết + lý do | *là cổng của người, không phải cổng của máy* |
| **A6** | Truy xuất nguồn | mọi đề xuất | `provenance.json` | schema bắt buộc |

### A1 — soạn bố cục, ba lượt chứ không một

Nhập thẳng ba thành phần của LayoutPrompter, cộng bài học §6.3:

```
lượt 1  SUY LUẬN TỰ DO       "tờ này có mấy khối? cột nào? chỗ nào để trống
        (không ràng buộc)     cho người điền? nó giống bố cục nào đang có?"
                                        │
lượt 2  CHUYỂN THÀNH YAML    dưới ràng buộc schema (XGrammar/Outlines)
        (có ràng buộc)        k phương án, không phải một
                                        │
lượt 3  XẾP HẠNG             chấm k phương án: (a) số lỗi schema, (b) một VLM
                              so preview với ảnh gốc, (c) khoảng cách tới các
                              bố cục đã có — thưởng cái khác, phạt cái trùng
                                        │
                              đề xuất tốt nhất  ──▶  A5  ──▶  cổng  ──▶  người
```

Chọn ví dụ mồi **động**: k bố cục gần nhất, đo bằng những thứ đã có trong file
— cùng họ, có/không `sheet`, `rules: marks` hay `ascii`, số cột, có
`letterhead`/`table`/`signatures` không. Không cần embedding cho mười sáu file.

Cấu trúc thư mục đề xuất — **tác nhân không bao giờ ghi vào `rulebase/`**:

```
proposals/<id>/
├── reasoning.md         lượt 1, để người đọc hiểu tác nhân *nghĩ* gì
├── candidates/01..05.yaml
├── ranking.json         điểm từng phương án và vì sao
├── layout.yaml          phương án thắng
├── rules-layout.yaml    khối để chèn, dưới họ nào
├── provenance.json      nguồn, phương pháp, model, hash prompt, ngày
├── preview.txt          make preview-grid
├── rounds/NN.errors     mọi vòng tự sửa (§10, A5)
└── verdict.md           A5 phản biện
```

### A5 — phản biện, và vì sao nó không phải "LLM tự chấm"

A5 **không** được hỏi "bố cục này có tốt không". Nó được giao việc **bác bỏ**:

> *"Nêu một chứng từ Việt Nam có thật mà bố cục này mô tả sai. Nêu một trường
> mà nhãn sẽ khai nhưng trang không in. Nêu một cột mà bề rộng cộng lại không
> vừa khổ giấy hẹp nhất. Mặc định là BÁC BỎ nếu không chắc."*

Đây là khác biệt giữa một lượt tự khen và một lượt tìm lỗi. Với những chỗ có
thể kiểm bằng máy (bề rộng cột, trường không in) thì A5 chỉ là lớp lọc rẻ chạy
trước cổng thật; với những chỗ **không** kiểm bằng máy được — *"tờ giấy này có
tồn tại không"* — nó là thứ duy nhất đứng giữa LLM và repo, ngoài người duyệt.

### A4 — lập kế hoạch: rẻ nhất, an toàn nhất, làm sớm nhất

Đầu ra là `pipeline.yaml`. Bán kính sát thương **đã bị chặn bởi cổng đang chạy
hôm nay**: `config.py` từ chối khoá lạ, `apply_overrides` bắt mọi override trỏ
vào thứ có thật và chỉ cho sửa `weight/tags/requires/excludes`. Không phải xây
gì thêm để bảo vệ.

Ví dụ với số thật từ `data/dataset60/proof/README.md`:

> *"Cần 5000 ảnh nghiêng về chỗ model đang yếu."*
> `by_layout`: `market_barcode` 0,234 · `invoice_export` 0,296 ·
> `invoice_brand` 0,924 — chênh **4×**.
> Bước bắt buộc trước khi đổi trọng số: đọc `by_layout_augmentation` để tách
> *"bố cục khó"* khỏi *"bố cục này rơi trúng mix làm cũ nặng"*. Hai chẩn đoán
> ấy dẫn tới hai kế hoạch ngược nhau.

Và mỗi override phải kèm **một dòng lý do** trong comment. `pipeline.yaml` là
file được chú thích dày nhất repo vì mỗi con số là một quyết định; một file do
máy sinh mà không nói được vì sao thì làm hỏng nếp đó.

## 11. Vòng lặp đóng: đo → chọn → sinh → đo lại

Đây là chỗ chữ "reasoning" có giá trị kinh tế, chứ không chỉ giá trị trình diễn.

```
   ┌──────────────────────────────────────────────────────────────┐
   │                                                              │
   ▼                                                              │
 sinh N ảnh ──▶ huấn luyện mô hình HỌC TRÒ nhỏ ──▶ đo trên TẬP THẬT
   ▲                                                     │
   │                                                     ▼
   │                                          điểm yếu theo (bố cục × mực
   │                                          × mức làm cũ × trường)
   │                                                     │
   └──── A4 sửa pipeline.yaml / A1 soạn bố cục thiếu ◀────┘
```

Bốn quy tắc, mỗi cái đến từ một kết quả ở §4–§6:

1. **Học trò phải thật.** Không dùng `ocr_proof` (Tesseract) làm tín hiệu vòng
   lặp. Tesseract là **mốc dưới cố định**, dùng để kiểm nhãn khớp ảnh — đúng
   như `docs/huong-dan-va-giai-thich.md` §9 nói. Tối ưu theo nó là tối ưu theo
   một engine chưa fine-tune, không phải theo bài toán.
2. **Tiêu chí chọn phải tầm thường ở vòng đầu.** Lấy mẫu tỉ lệ nghịch với điểm
   theo bố cục. Kết quả 2025 nói tiêu chí kiểu active-learning **đơn giản**
   thắng cách tinh vi; xây mô-đun khám phá kỹ năng trước là tiêu tiền vào chỗ
   chưa biết có cần không.
3. **Tích luỹ, không thay thế.** Mỗi vòng **cộng thêm** vào tập, không ghi đè.
   Đây là điều khác biệt giữa "tránh được sụp" và "sụp chậm hơn".
4. **Neo bằng dữ liệu thật.** Tập đánh giá phải là ảnh thật, và tỉ lệ ảnh thật
   trong tập huấn luyện không được về 0. Ngưỡng ~5 % là con số đã có trong tài
   liệu; với repo này, "thật" gồm cả các ảnh tham chiếu trong `docs/mau/` và
   `samples/invoice-templates/`.

Nếu chưa có mô hình học trò và tập thật, vòng lặp vẫn chạy được ở **chế độ
giảm**: thay "hiệu năng học trò" bằng "độ phủ" — bố cục nào chưa có ảnh nào,
`role` nào chưa bao giờ ở `ink: hand`, tổ hợp `(layout × ink × augmentation)`
nào chưa xuất hiện. `tools/monitor.py` đã đọc được không gian luật, nên đây là
một báo cáo chứ không phải một hệ thống.

---

# Phần IV · Lộ trình

Năm đợt. Mỗi đợt **tự nó dùng được** và dừng được — không đợt nào là khoản đầu
tư chỉ hoàn vốn ở đợt sau.

## 12. Năm đợt

### M0 · Hợp đồng — `rulebase/schema.py`

**Vì sao trước tiên.** Nó vừa là cổng vừa là hợp đồng đưa cho LLM. Một schema
viết một lần phục vụ cả hai; một prompt mô tả bằng văn xuôi chỉ phục vụ cái sau
và sẽ lệch khỏi code trong vòng một tháng.

**Bằng chứng nó đang thiếu.** Chép thư mục bố cục ra chỗ khác, thêm vào
`eatery_ascii.yaml` hai lỗi rất giống lỗi LLM sẽ mắc — `headr:` thay `header:`,
và `algin:` thay `align:` trong một cột:

```
built anyway: 21 rows, 40 cells — unknown keys silently ignored
```

Không ngoại lệ, không cảnh báo. Trang vẫn dựng, chỉ **thiếu đúng cái mà khoá đó
lẽ ra làm**. Đối chiếu: `rules/*.yaml` raise ngay, kèm câu *"params belong under
'params:'"*. Hai file YAML cạnh nhau, hai chuẩn khác nhau.

**Làm gì.**

```python
# rulebase/schema.py
#
# Ngữ pháp file bố cục ở dạng máy đọc được. rulebase/README.md §3 mô tả cùng
# thứ này bằng văn xuôi cho người; đây là bản cho máy, và là bản build_grid
# THI HÀNH -- hai bản không được phép lệch nhau, và có một test giữ chuyện đó.

FROM_SOURCES = ("stt", "name", "qty", "unit_price", "amount", "barcode", ...)
ROLES        = (...)          # vốn từ `role`, cũng là vốn từ `hand_roles` dùng

LAYOUT_SCHEMA = {
    "id":       {"type": "str", "required": True},
    "source":   {"type": "str", "required": True},
    "provenance": {"type": "block", "required": True, "keys": {
        "method":   {"type": "enum", "values": ("measured", "llm_transcribed",
                                                "llm_proposed"), "required": True},
        "evidence": {"type": "str"},
        "reviewed_by": {"type": "str"},
    }},
    "width":    {"type": "int_pair", "min": 20, "max": 200, "required": True},
    "sheet":    {"type": "enum", "values": tuple(SHEETS)},
    "rules":    {"type": "enum", "values": ("ascii", "marks")},
    "sections": {"type": "enum_list", "values": tuple(SECTIONS)},
    "columns":  {"type": "column_list"},
    ...
}

def validate_layout(spec, layout_id="") -> list[str]: ...
def schema_json() -> dict:  """Cùng schema, dạng JSON — thứ đưa cho LLM."""
```

**Bắt được gì mà hôm nay không bắt được:** khoá lạ ở mọi cấp (kể cả trong
`columns:`, `item.rows:`, `totals:`) · `from:` trỏ vào nguồn không có → hôm nay
in ra rỗng · `col:` trỏ vào `key` chưa khai · tổng bề rộng cột cộng gutter vượt
`width` nhỏ nhất · không có đúng một cột `width: 0` · `shade:`/`border:` khai
mà thiếu `rules: marks` → âm thầm bị bỏ · section khai mà thiếu khối cấu hình.

**Gắn vào đâu.** `build_grid` gọi và raise; `rules_report.check()` gọi và liệt
kê tất cả; task mới `make check-layouts` và `make layout-schema`; CI job `rules`
chạy thêm cả hai.

**Xong khi:** thí nghiệm trên báo đúng hai lỗi; 16 file hiện có qua sạch; một
test khẳng định **mọi khoá xuất hiện trong 16 file đều có trong schema** (đây
là thứ giữ schema và `rulebase/README.md` không lệch nhau).

**Công:** 2–3 ngày (nhiều hơn ước lượng cũ vì thêm `provenance` và vốn từ
`role`). **Không cần LLM.** Đáng làm kể cả nếu dừng ở đây.

---

### M1 · Lớp mực — form điền tay chạy được đầu-cuối

Đợt lớn nhất, và là đợt trả lời thẳng câu hỏi đã đặt.

| bước | việc | xong khi |
| --- | --- | --- |
| M1.1 | `Cell.ink`, `rules/ink.yaml`, một dòng trong `_order.yaml` | `make distribution` in ra trục thứ tám; `check-rules` sạch |
| M1.2 | Ba renderer chừa hộp cho ô không phải `press` | ba renderer cho ra hộp giống nhau cho cùng một ô, ảnh còn trống |
| M1.3 | `ink/` + nguồn `marks` (✓, gạch chân) | một dấu tích lên đúng ô, có hộp trong `metadata.jsonl` |
| M1.4 | `invariants`: ô `hand` phải có mực; `by_ink` trong `ocr_proof` | một ô `hand` rỗng thì **đỏ** |
| M1.5 | Nguồn `writevit` + `can_write` | `make preflight` chặn trước khi chạy nếu bố cục cần chữ số |
| M1.6 | Nguồn `digits_strokes` | `15/03/2025` và `1.500.000` viết được |
| M1.7 | `ink: stamp` — **`ornament` cuối cùng được vẽ lên trang** | con dấu trong `metadata.jsonl` có mặt trong pixel |
| M1.8 | **Đo downstream** | xem dưới |

**M1.8 là điều kiện nghiệm thu, không phải phần thưởng.** *Quo Vadis* (§5.3)
nói chữ tay tổng hợp **không chắc** làm mô hình nhận dạng tốt lên. Nên đợt này
kết thúc bằng một phép đo, không bằng một bức ảnh:

> Lấy một tập nhỏ ảnh **thật** của form Việt Nam điền tay (đủ để đánh giá, không
> cần để huấn luyện). Huấn luyện một mô hình nhận dạng nhỏ ở ba chế độ: chỉ dữ
> liệu in sẵn có; in + tổng hợp điền tay; và nếu có, in + một ít thật. So trên
> tập thật. **Nếu cột thứ hai không hơn cột thứ nhất, đợt này chưa xong** — và
> điều cần ghi lại là *vì sao*, không phải là thêm ảnh.

**Công:** 3–4 tuần, và M1.5–M1.6 là chỗ rủi ro tiến độ (huấn luyện, giấy phép
dữ liệu). M1.1–M1.4 độc lập với chuyện đó và cho ra kết quả nhìn thấy được
trong tuần đầu.

**Rủi ro riêng của đợt này:** `make baseline-verify` sẽ đỏ khi `ink` vào
`_order.yaml`, vì thêm một trục làm đổi mọi lần bốc. Đó là **đúng thiết kế** —
và phải chụp lại có `REASON` nói rõ, chứ không phải lặng lẽ.

---

### M2 · Tác nhân soạn bố cục

Sau M0 (schema là hợp đồng) và song song được với M1.

| bước | việc |
| --- | --- |
| M2.1 | `tools/propose_layout.py` — ba lượt của §10 (suy luận tự do → YAML có ràng buộc → xếp hạng) |
| M2.2 | Thư mục `proposals/` + `make accept-layout ID=<id>` chạy hết chuỗi cổng |
| M2.3 | Vòng tự sửa: LLM đọc lỗi validator và sửa YAML của chính nó, tối đa 5 vòng; **dừng nếu một lỗi lặp hai vòng liền** |
| M2.4 | A5 phản biện — nhiệm vụ là **bác bỏ**, mặc định bác nếu không chắc |
| M2.5 | Bỏ hard-code `sheets.FAMILIES`: bố cục tự khai `family:`, schema kiểm |

Chuỗi cổng trước khi `accept`, dừng ở lỗi đầu:

```bash
make check-layouts LAYOUT=<id>      # M0
make check-rules                    # khai báo trong họ có hợp lệ không
make preview-grid LAYOUT=<id>       # người nhìn một lần
make preflight                      # phủ glyph chuỗi mới, tràn giấy, can_write
python -m pytest tests/test_layout.py tests/test_content.py -q
python tools/generate_dataset.py -n 3 --layouts <id> -o data/tmp-<id>
make check-boxes                    # hộp còn mô tả đúng pixel
```

`accept-layout` **không bao giờ** chạy `baseline-write` — thêm bố cục làm đổi
kế hoạch, nên chụp lại phải có chủ ý và có lý do.

**Nền móng đã có sẵn, và đây là chỗ đợt này rẻ hơn tưởng:** `tests/test_layout.py`
đọc `available_layouts()` chứ không liệt kê tên, nên một file mới **tự động**
được 5 seed × ~15 kiểm tra hình học; `preflight.printable_text` đã đi bộ *toàn
bộ* file bố cục nên chuỗi mới được kiểm phủ glyph ngay ngày thêm vào.

**Công:** 1–1,5 tuần sau M0.

---

### M3 · Vòng lặp đóng

| bước | việc |
| --- | --- |
| M3.1 | `tools/plan_run.py` — A4, đọc `ocr_report.json` + `drift.json` + distribution, ra `pipeline.yaml` **kèm lý do** |
| M3.2 | Báo cáo độ phủ: tổ hợp `(layout × ink × augmentation)` nào chưa có ảnh nào |
| M3.3 | Học trò: một mô hình nhỏ + tập đánh giá **thật** |
| M3.4 | Layout-FID (LayoutLMv3) như thước phụ — **không** phải mục tiêu tối ưu |
| M3.5 | Sổ tích luỹ: mỗi vòng cộng thêm, không ghi đè; tỉ lệ thật không về 0 |

M3.1 và M3.2 làm được **ngay hôm nay**, không chờ M0/M1. Nếu chỉ có ngân sách
cho một việc trong cả tài liệu này, M3.1 là việc có tỉ lệ giá trị/công cao nhất.

**Công:** M3.1–M3.2 2 ngày · M3.3 tuỳ việc có tập thật không · M3.4 3 ngày.

---

### M4 · Mở rộng — sau khi bốn đợt trên đứng vững

Xếp theo giá trị, không theo độ khó:

| việc | vì sao |
| --- | --- |
| **Nhiều trang** (`doc_id` + `page`) | mở ra KIE nhiều trang, DocVQA; hôm nay không diễn tả được |
| **Ô gộp vào nhãn** cho đường lưới | [`brief-engine-html.md` §2](brief-engine-html.md) đã đo và ghi rõ; ảnh có ô gộp mà nhãn không biết |
| **TEDS** cho `data/tables60` | thước đo đúng cho cấu trúc bảng; README đã tự nhận thiếu |
| A2 soạn corpus, `source: llm` | móc **đã chừa sẵn**: `drift.SOURCES = ("corpus", "llm", "fallback")` |
| Engine thứ tư (**Typst**) | 200–500 ms/tài liệu, ra PDF/SVG/PNG, tạo hình chữ khác cả ba engine hiện có — rẻ hơn WeasyPrint và thêm một cách vẽ |
| Loại chứng từ mới (chạm `content.py`) | LLM đề xuất bản vá, **người duyệt**; chỗ duy nhất có thể phá bất biến nhãn↔pixel |
| A3 soạn hoạ tiết | 23 mẫu đã khảo sát chưa dựng, mỗi mẫu đã ghi sẵn lý do |

## 13. Bảng ưu tiên

| # | việc | công | giá trị | phụ thuộc |
| --- | --- | --- | --- | --- |
| 1 | **M3.1** A4 lập kế hoạch chạy | 2 ngày | ★★★ dùng ngay, rủi ro ~0, cổng đã có | — |
| 2 | **M0** schema bố cục | 2–3 ngày | ★★★ chặn lỗi im lặng; hợp đồng cho LLM | — |
| 3 | **M1.1–M1.4** trục mực + `marks` + bất biến | 1 tuần | ★★★ thông cả đường ống bằng ca dễ nhất | M0 |
| 4 | **M2** tác nhân soạn bố cục (3 lượt + phản biện) | 1–1,5 tuần | ★★★ đúng mục tiêu đề bài | M0 |
| 5 | **M1.5–M1.7** WriteViT + chữ số + dấu đóng | 2–3 tuần | ★★★ lấp khoảng trống lớn nhất | M1.1–M1.4 |
| 6 | **M1.8** đo downstream | 1 tuần | ★★★ *điều kiện nghiệm thu*, không phải phần thưởng | M1.5–M1.7 |
| 7 | **M2.5** bỏ `sheets.FAMILIES` | 1 ngày | ★★ xoá điểm chạm Python cuối | M0 |
| 8 | **M4** nhiều trang | 1 tuần | ★★ mở lớp bài toán mới | M0 |
| 9 | **M3.3–M3.4** học trò + Layout-FID | tuỳ | ★★ đóng vòng lặp thật | M3.1 |
| 10 | **M4** ô gộp vào nhãn, TEDS, Typst, corpus LLM | mỗi cái ~1 tuần | ★–★★ | — |

Sau mục #4 là đã đạt yêu cầu đề bài (*LLM lập luận, lựa chọn, tạo bố cục*).
Sau mục #6 là đã có form điền tay **và biết nó có ích hay không**.

## 14. Cái tôi sẽ **không** xây

Phần này quan trọng ngang phần trên. "Over-engineer" đúng nghĩa là nghĩ rộng
rồi **cắt**, không phải xây hết mọi thứ nghĩ ra.

| không xây | vì sao |
| --- | --- |
| **LLM trong đường render** | phá tất định `seed → trang`, làm `baseline-verify` vô nghĩa, và nhãn tụt xuống chỉ tốt bằng mô hình |
| **Mô hình khuếch tán sinh cả trang** | không cho biết nó vẽ chữ gì ở đâu; nhãn phải OCR lại. `huong-dan-va-giai-thich.md` §9 đã trả lời, và câu trả lời vẫn đúng |
| **Một DSL bố cục mới** | ngữ pháp YAML hiện tại đã diễn tả được 16 tờ giấy thật; đổi ngôn ngữ là viết lại `layout.py` để đổi lấy sự thanh lịch |
| **Mô-đun "khám phá kỹ năng"** ở vòng đầu | tiêu chí active-learning đơn giản thắng cách tinh vi (§4.5); xây trước là tiêu tiền vào chỗ chưa biết có cần |
| **Tự động duyệt đề xuất bố cục** | A5 lọc rẻ; **người chốt**. Bố cục là thứ duy nhất phải nhìn bằng mắt, vì "tờ giấy này có tồn tại không" không kiểm được bằng máy |
| **Mặt chữ viết tay jitter làm phương án dự phòng** | `ff9a9f0` đã đi đường đó và đã sai. Thiếu nguồn mực thì **dừng**, không hạ chuẩn |
| **Huấn luyện lại WriteViT ngay** | thử `digits_strokes` trước: rẻ hơn nhiều, và chữ số là bài ngôn ngữ trung tính (§5.2) |
| **Bám FID làm mục tiêu** | đo cái đẹp, không đo cái dạy được (§6.2) |

---

# Phần V · Ràng buộc

## 15. Chín bất biến

Bốn cái đầu đã có trong bản trước và giữ nguyên; năm cái sau là mới, đến từ
phần khảo sát.

1. **Nhãn dựng từ chính object dùng để vẽ.** Không tác nhân nào chạm
   `ground_truth()`.
2. **`seed` → trang.** Không lời gọi mạng nào trong đường render.
3. **Mọi cổng còn nguyên.** Năng lực mới **thêm** cổng, không bớt. Đề xuất làm
   đỏ một cổng thì cổng đúng, cho tới khi có ai chứng minh ngược lại bằng số và
   ghi lý do vào file — như `baseline-write` đang bắt buộc.
4. **Mỗi bố cục nói nó từ đâu ra.** `provenance.method` bắt buộc; tỉ lệ ba loại
   đếm được và `llm_proposed` có trần.
5. **Mực là thuộc tính của ô, không của trang.** Một trục mới chứ không phải
   một cờ trong `visual`.
6. **`ink/` sinh hộp; `degradation/` thì không.** Thứ viết chữ lên trang phải
   khai vào nhãn. Đặt nguồn mực vào chuỗi làm cũ là cách chắc chắn nhất để có
   chữ mà nhãn không biết.
7. **Một nguồn mực từ chối thì tốt hơn một nguồn mực đoán bừa.** `can_write`
   chạy trước `write`, và preflight gọi nó trên mọi chuỗi có thể sinh ra.
8. **Tích luỹ, không thay thế; tỉ lệ dữ liệu thật không về 0.** (§6.1)
9. **Thước đo cuối cùng là hiệu năng downstream trên dữ liệu thật**, không phải
   FID, không phải Tesseract, không phải số ảnh. (§6.2, §5.3)

## 16. Rủi ro

| rủi ro | dấu hiệu | cách chặn |
| --- | --- | --- |
| LLM đẻ khoá nghe hợp lý mà không tồn tại | trang thiếu một khối, không ai báo | **M0** — lý do nó đứng đầu |
| LLM bịa bố cục không tờ giấy nào giống | dataset đa dạng giả, phân phối trôi khỏi thực tế | `provenance.method`, trần `llm_proposed`, A5 phản biện |
| **Nguồn chữ tay vẽ sai mà không báo** | `1500000` ra nét ngoằn ngoèo, nhãn vẫn khai đúng số | `can_write` **trước** `write`; preflight gọi trên mọi chuỗi có thể sinh |
| **Mực tay không đáp xuống hộp** | nhãn khai giá trị mà pixel trống | bất biến mới: ô `hand` phải có mực trong hộp |
| Điểm OCR tụt sau M1, tưởng là hồi quy | ai đó "sửa" bằng cách bỏ chữ tay | nhóm `by_ink` tách riêng **trước** khi bật chữ tay |
| Model collapse qua nhiều vòng | đa dạng co lại, ảnh na ná nhau | ≥5 % thật, tích luỹ không thay thế, chọn theo chỗ trống |
| Trọng số LLM đặt làm lệch mix | drift cảnh báo, hoặc tệ hơn: không, vì mix mới là "chủ ý" | `apply_overrides` đã bắt trỏ đúng thứ có thật; thêm: mỗi override kèm một dòng lý do |
| Chuỗi corpus mới thiếu glyph | in ra ô vuông, nhãn vẫn khai là chữ | `make preflight` bắt buộc sau mỗi lần thêm corpus |
| Vòng tự sửa quẩn | 5 vòng vẫn đỏ, tốn token | dừng khi một lỗi lặp hai vòng liền |
| Ép schema làm bố cục nhạt đi | mọi đề xuất na ná ví dụ mồi | tách hai lượt (§6.3); xếp hạng có thưởng cho cái khác biệt |
| Người duyệt đóng dấu cho có | bố cục xấu lọt vào repo | `preview.txt` + `reasoning.md` trong mỗi đề xuất |
| Schema và `rulebase/README.md` lệch nhau | tài liệu nói một đằng, máy thi hành một nẻo | test khẳng định mọi khoá trong 16 file đều có trong schema |
| **Giấy phép dữ liệu học của mô hình chữ tay** | ảnh phát hành ra vi phạm điều khoản VNOnDB/IAM | đọc điều khoản **dữ liệu**, không phải giấy phép **mã** (§17) |

## 17. Quản trị — phần không ai thích đọc

Repo này sinh ra **hoá đơn GTGT Việt Nam trông rất thật**: có `Mẫu số`,
`Ký hiệu`, `Số`, mã số thuế, chữ ký, và — sau M1 — con dấu tròn đóng lên chữ
ký. README tự ghi *"No licence is chosen yet"*. Ba việc phải làm trước khi phát
hành, và mốc thời gian không phải do tôi đặt ra:

**(a) Đánh dấu là tổng hợp, ở mức tệp.** EU AI Act Điều 50 bắt đầu thi hành
**8/2026**; California SB 942 có hiệu lực từ **1/1/2026**. Chuẩn công nghiệp đã
hội tụ về hai lớp: **C2PA content credentials** (manifest ký số — bản 2.3,
12/2025, đã mở rộng sang cả đầu ra LLM) và watermark chìm. Với repo này, mức
tối thiểu hợp lý: `dataset.json` có cờ `synthetic: true` và nguồn sinh; mức nên
làm: manifest C2PA gắn vào từng ảnh.

**(b) Không để một tổ chức có thật xuất hiện.** Corpus hiện có tên thương hiệu
thật (`VinCommerce`, `VM Royal City` trong ví dụ nhãn của `rulebase/README.md`).
Một tờ hoá đơn tổng hợp mang tên công ty có thật, mã số thuế đúng định dạng và
con dấu tròn là thứ **không nên tồn tại ngoài repo**. Đề xuất: một bất biến mới
kiểm rằng tên tổ chức và mã số thuế nằm trong dải dành riêng, và một mục
`SPECIMEN` — cơ chế đã có sẵn, `invoice_vat_form.yaml` nhắc tới tờ đóng chìm
chữ **"HOÁ ĐƠN MẪU"**.

**(c) Điều khoản của dữ liệu học, không phải của mã.**
[`writevit.md`](writevit.md) và [`khao-sat-sinh-chu-viet-tay.md`](khao-sat-sinh-chu-viet-tay.md)
đều đã cảnh báo: tám kho đều MIT, nhưng trọng số học từ **IAM-OnDB và VNOnDB**,
và điều khoản phát hành lại của *dữ liệu* mới là thứ quyết định ảnh sinh ra có
được công bố hay không. Việc này phải xong **trước** M1.5, không phải sau.

Đây không phải phần phụ. Nó là điều kiện để tất cả những gì ở trên có chỗ dùng.

---

## Phụ lục A · Số đo

Môi trường: Linux, Python 3.11.15, **chưa dựng venv renderer nào** (nên các
kiểm tra cần numpy/opencv/Chromium/WeasyPrint không chạy ở đây).

```
$ python -m pytest
599 passed, 4 skipped, 1 xfailed in 77.87s

$ python tasks.py check
all 84 python files compile

$ python tasks.py check-rules
LUẬT CÓ VẤN ĐỀ:
  - degradation not importable (needs numpy and opencv); chains unchecked
        # thiếu thư viện ở môi trường này, không phải lỗi luật

$ python tasks.py check-corpus
corpus en/ hợp lệ: invoice=18, streets=16, wards=14, payments=7, people=15
corpus vi/ hợp lệ: bakery=22, eatery=115, export=20, hotel=20, invoice=28,
                   market=88, utility_power=8, utility_water=7, streets=40,
                   wards=34, payments=13, people=25

$ python tasks.py distribution
2000 lần bốc thành công / 2000 — 16 bố cục trong 6 họ
```

Không gian luật, đếm từ `load_rules()`:

```
document 17 · layout 16 (6 họ) · content 12 · visual 7 · color 5 ·
ornament 21 (4 họ) · augmentation 15   →   trần trên 35.985.600 tổ hợp
```

**Thí nghiệm schema** (§12 M0) — thêm `headr:` và `columns[0].algin:` vào một
bản sao của `eatery_ascii.yaml` rồi gọi `build_grid` với `root=` trỏ vào bản
sao:

```
built anyway: 21 rows, 40 cells — unknown keys silently ignored
```

Số OCR trích từ `data/dataset60/proof/README.md` (tesseract 5.3.4, `vie`,
psm 4), dùng ở §10 A4: `invoice_brand` 0,924 → `invoice_export` 0,296 →
`market_barcode` 0,234.

Số về WriteViT trích từ [`writevit.md`](writevit.md): 0/10.131 token bộ sinh
từng thấy có chứa chữ số; `VN.pickle` có 2.579/92.048 nhãn chứa chữ số.

---

## Phụ lục B · Nguồn

**Sinh tài liệu tổng hợp**
- CoSyn — *Scaling Text-Rich Image Understanding via Code-Guided Synthetic Multimodal Data Generation*, arXiv [2502.14846](https://arxiv.org/abs/2502.14846)
- DocGenie — *A Framework for High-Fidelity Synthetic Document Generation via Seed-Guided Multimodal LLM and Document-Aware Evaluation*, CVPRW 2025, [OpenReview](https://openreview.net/forum?id=cT5v6GjdsH)
- DocDjinn — *Controllable Synthetic Document Generation with VLMs and Handwriting Diffusion*, arXiv [2602.21824](https://arxiv.org/abs/2602.21824)
- Nayana OCR — *A Scalable Framework for Document Synthetic Data Generation*, [ACL 2025 LM4UC](https://aclanthology.org/2025.lm4uc-1.11.pdf)

**Sinh bố cục bằng LLM**
- LayoutPrompter — *Awaken the Design Ability of Large Language Models*, NeurIPS 2023, arXiv [2311.06495](https://arxiv.org/abs/2311.06495)
- *Smaller But Better: Unifying Layout Generation with Smaller Large Language Models*, arXiv [2502.14005](https://arxiv.org/html/2502.14005v1)

**Tác nhân sinh dữ liệu, vòng lặp đóng**
- DataEnvGym — *Data Generation Agents in Teacher Environments with Student Feedback*, ICLR 2025 Spotlight, arXiv [2410.06215](https://arxiv.org/abs/2410.06215)
- *Towards Active Synthetic Data Generation for Finetuning Language Models*, arXiv [2512.00884](https://arxiv.org/pdf/2512.00884)

**Chữ viết tay**
- WriteViT, arXiv [2505.13235](https://arxiv.org/html/2505.13235) — đã dựng và đo, xem [`writevit.md`](writevit.md)
- DiffusionPen (ECCV 2024), [mã nguồn](https://github.com/koninik/DiffusionPen) · One-DM (ECCV 2024), arXiv [2409.04004](https://arxiv.org/abs/2409.04004) · VATr++ (2024)
- HandwritingAgent — *Language-Driven Handwriting Synthesis in Scalable Vector Space*, arXiv [2606.18788](https://arxiv.org/html/2606.18788), [mã nguồn](https://github.com/Jaykef/HandwritingAgent)
- *Quo Vadis Handwritten Text Generation for Handwritten Text Recognition?*, arXiv [2508.09936](https://arxiv.org/pdf/2508.09936)
- Danh mục cập nhật: [awesome-handwritten-text-generation](https://github.com/koninik/awesome-handwritten-text-generation)

**Rủi ro dữ liệu tổng hợp**
- *Strong Model Collapse*, ICLR 2025
- *How to Synthesize Text Data without Model Collapse?*, arXiv [2412.14689](https://arxiv.org/pdf/2412.14689)
- *Escaping Model Collapse via Synthetic Data Verification*, arXiv [2510.16657](https://arxiv.org/pdf/2510.16657)
- SADGE — *Structure and Appearance Domain Gap Estimation of Synthetic and Real Data*, arXiv [2605.22467](https://arxiv.org/pdf/2605.22467)

**Đầu ra có cấu trúc**
- *Let Me Speak Freely? A Study on the Impact of Format Restrictions on Performance of LLMs*, arXiv [2408.02442](https://arxiv.org/pdf/2408.02442)
- JSONSchemaBench, arXiv [2501.10868](https://arxiv.org/abs/2501.10868)

**Bối cảnh tiếng Việt**
- *A Survey on Vietnamese Document Analysis and Recognition: Challenges and Future Directions*, arXiv [2506.05061](https://arxiv.org/html/2506.05061)
- HANDS-VNOnDB · Vintern-1B, arXiv [2408.12480](https://arxiv.org/pdf/2408.12480) · MC-OCR 2021

**Quản trị**
- [C2PA Specification 2.2 Implementation Guidance](https://spec.c2pa.org/specifications/specifications/2.2/guidance/_attachments/Guidance.pdf) (bản 2.3, 12/2025 mở rộng sang đầu ra LLM)
- EU AI Act Điều 50 (thi hành 8/2026) · California SB 942 (hiệu lực 1/1/2026)

---

## Liên quan trong kho này

| | |
| --- | --- |
| [`README.md` §Adding a document kind](../README.md#adding-a-document-kind) | quy trình thủ công hôm nay |
| [`rulebase/README.md` §3](../rulebase/README.md) | ngữ pháp file bố cục — bản văn xuôi mà M0 biến thành dữ liệu |
| [`docs/hoa-tiet-de-xuat.md` §B](hoa-tiet-de-xuat.md) | sáu mục nét tay đã dựng rồi gỡ, và lý do — nguồn gốc §7 |
| [`docs/khao-sat-sinh-chu-viet-tay.md`](khao-sat-sinh-chu-viet-tay.md) | tám kho sinh chữ tay, xếp theo hai trục — §5 cập nhật nó |
| [`docs/writevit.md`](writevit.md) | WriteViT đã dựng, và **đo được nó không viết được gì** |
| [`docs/brief-engine-html.md` §2](brief-engine-html.md) | ô gộp: ảnh có, nhãn không — nguồn gốc §8.8 |
| [`docs/huong-dan-va-giai-thich.md` §9](huong-dan-va-giai-thich.md) | vì sao không dùng LLM sinh thẳng ảnh — câu trả lời vẫn đúng |
| [`pipeline.yaml`](../pipeline.yaml) | đầu ra của A4 |
| [`pipeline/drift.py`](../pipeline/drift.py) | `SOURCES` đã chừa sẵn chỗ cho `llm` |
