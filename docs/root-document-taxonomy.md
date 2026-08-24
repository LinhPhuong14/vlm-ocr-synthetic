# Root document taxonomy — đề xuất mở rộng phạm vi tài liệu

Kho này hiện chỉ sinh **chứng từ Việt Nam**: hoá đơn/biên lai (`till_receipt`,
`statutory_invoice`, `commercial_invoice`, `service_invoice` — xem
[`rules/document.yaml`](../rulebase/rules/document.yaml)) và hai chứng từ hành
chính không phải hoá đơn (`hospital_bill`, `authorisation_letter`). Tài liệu
này ghi lại một đề xuất mở **8 root document** — mỗi root 10 biến thể layout —
để định hình bước mở rộng tiếp theo, cùng với đâu là chỗ kho này **đã có chân**
và đâu là **hoàn toàn trống**.

📊 **Bản xem trực quan (80 ảnh thật, một ảnh mỗi layout, có nguồn kèm theo):**
**[Root Document Taxonomy — gallery](https://claude.ai/code/artifact/aabd76bb-fa3b-4fdd-84ab-c86eeba01244)**

Cơ sở tham chiếu chung của đề xuất: **RVL-CDIP** (16 nhóm document: form,
handwritten, scientific report/publication, news article, invoice,
questionnaire, resume, memo…), **M6Doc** (scientific article, textbook, test
paper, magazine, newspaper, note, book), **OmniDocBench** (10 loại tài liệu, 5
kiểu layout, 28 loại block-level + 4 loại span-level).

---

## 1 · Bảng tổng quan 8 root

| # | Root | Ưu tiên | Đặc trưng OCR chính | Kho này hiện có gì |
| :-: | :--- | :--- | :--- | :--- |
| 1 | Invoice / Billing | 🔴 Rất cao | key-value + table + totals | **Có** — 4 họ document, là trọng tâm hiện tại |
| 2 | Receipt | 🔴 Rất cao | narrow layout + line items | **Có** — họ `till_receipt`, 5 layout |
| 3 | Forms / Applications | 🔴 Rất cao | fields + checkbox + K-V | **Một phần** — chỉ 2 chứng từ (`hospital_bill`, `authorisation_letter`), chưa có checkbox/chữ ký/đơn chính phủ |
| 4 | Identity Documents | 🔴 Rất cao | photo + K-V + MRZ + security | **Chưa có** |
| 5 | Academic / Scientific | 🔴 Rất cao | multi-column + equations + figures | **Chưa có** |
| 6 | Reports / Business Documents | 🟠 Cao | headings + paragraphs + tables/charts | **Chưa có** |
| 7 | Newspaper / Magazine / Editorial | 🟠 Cao | complex multi-column + images | **Chưa có** |
| 8 | Handwritten / Historical Documents | 🟠 Cao | degradation + handwriting + irregular layout | **Một phần** — có engine chữ viết tay ([`handwriting-html.md`](handwriting-html.md)) nhưng chỉ để điền vào biểu mẫu in sẵn, không phải root riêng |

Root 1–2 đã là lõi của kho; root 3 và 8 có hạ tầng liên quan (biểu mẫu, chữ
viết tay) nhưng chưa đủ rộng để tính là phủ root đó; root 4–7 là bốn mảng
trống hoàn toàn.

---

## 2 · Phương pháp lấy ảnh minh hoạ

Cột "keyword" trong đề xuất gốc được viết để dùng trực tiếp làm câu truy vấn
tìm ảnh — nên với mỗi trong 80 layout, một agent tìm một ảnh **thật** (không
tự vẽ) khớp với keyword đó, ưu tiên đúng dataset học thuật được trích dẫn cho
root ấy, tiếp theo là Hugging Face `datasets-server`, Wikimedia Commons, hoặc
trang mẫu/template mở. Kết quả: **80/80 layout đều tìm được ảnh**, nguồn theo
từng root:

| Root | Nguồn ảnh đã dùng |
| :--- | :--- |
| Invoice | FATURA2-invoices qua Hugging Face (6/10) · mẫu Invoice Ninja, Uniform Software, Invoicer.ai (3/10) · PDF mẫu chính thức Canada Post cho layout nhiều trang (1/10) |
| Receipt | CORD-v2 qua Hugging Face (6/10) · SROIE qua Hugging Face (3/10) · Wikimedia Commons (1/10) |
| Form | FUNSD, qua mirror `nielsr/funsd-layoutlmv3` trên Hugging Face (9/10) · Wikimedia Commons — mẫu DS-160 của Bộ Ngoại giao Mỹ (1/10) |
| Identity Document | **100% Wikimedia Commons, toàn bộ là mẫu "SPECIMEN/SAMPLE/MUSTER/FACSIMILE" chính thức do cơ quan nhà nước công bố** — không dùng giấy tờ thật của bất kỳ ai (xem lưu ý bên dưới) |
| Academic/Scientific | PDF thật render trực tiếp từ arXiv, JMLR, CVPR (thecvf.com), ACL Anthology, trang tác giả, Internet Archive (CACM) — 10/10 |
| Report/Business | DocLayNet v1.2 qua Hugging Face (8/10) · Wikimedia Commons (2/10) |
| Newspaper/Magazine | **100% Wikimedia Commons** — báo/tạp chí lịch sử public domain |
| Handwritten/Historical | **100% Wikimedia Commons** (một phần qua NARA) |

**Về quyền riêng tư (root Identity Document):** mọi ảnh đều là mẫu trưng bày
chính thức (tên giả định kiểu "Mustermann Erika", "Suzy Q. Sample", watermark
"SPECIMEN" phủ chéo…), không phải giấy tờ của một cá nhân có thật. MIDV-500 —
dataset học thuật được trích dẫn cho root này — được xây đúng theo tinh thần
đó (500 clip quay giấy tờ **mẫu**, không phải giấy tờ thật), nhưng kho ảnh của
nó không có sẵn ảnh đơn lẻ tải trực tiếp được nên các ảnh dùng ở đây lấy từ
Commons thay thế, cùng tinh thần "specimen" như MIDV-500 nêu.

Ảnh trong gallery dùng để **hình dung layout**, không khẳng định đây là mẫu
chính thức duy nhất của layout đó — mỗi ảnh trong trang đều kèm nguồn, bấm vào
ảnh để xem phóng to và link gốc.

---

## 3 · Chi tiết 80 layout theo root

Tên layout và từ khoá giữ nguyên như đề xuất gốc (phần lớn tiếng Anh, vì đó là
câu truy vấn). Ảnh tương ứng từng dòng xem trong gallery ở đầu tài liệu.

### 3.1 · Invoice / Billing — *key-value + table + totals*
Dataset trích dẫn: **FATURA** (10.000 hoá đơn tổng hợp, 50 layout khác nhau) · **MIDD** (4 layout) · **DocILE**

| ID | Layout | Keyword |
| :--- | :--- | :--- |
| INV-01 | Header + full-width table | invoice header full width line item table |
| INV-02 | Logo trái + metadata phải | invoice logo left metadata right |
| INV-03 | Logo giữa + company info | centered invoice header |
| INV-04 | 2-column billing/shipping | invoice billing shipping two column |
| INV-05 | Sidebar + main table | invoice sidebar layout |
| INV-06 | Header + key-value blocks + table | invoice key value layout line items |
| INV-07 | Dense table invoice | dense invoice table layout |
| INV-08 | Minimalist invoice | minimal invoice layout |
| INV-09 | Multi-page invoice | multi page invoice layout |
| INV-10 | Invoice + payment/remittance section | invoice remittance payment section |

### 3.2 · Receipt — *narrow layout + line items*
Dataset trích dẫn: **SROIE** · **CORD** (1.000 biên lai thật) · **WildReceipt**

| ID | Layout | Keyword |
| :--- | :--- | :--- |
| REC-01 | Classic thermal receipt | thermal receipt OCR |
| REC-02 | Centered store header | centered receipt layout |
| REC-03 | Left-aligned receipt | left aligned receipt |
| REC-04 | Logo + store info | receipt logo store information |
| REC-05 | Wide supermarket receipt | supermarket receipt layout |
| REC-06 | Restaurant receipt | restaurant receipt layout |
| REC-07 | Receipt with QR/barcode | receipt QR code barcode layout |
| REC-08 | Receipt with tax section | receipt tax subtotal total layout |
| REC-09 | Long receipt / many items | long receipt many line items |
| REC-10 | Irregular photographed receipt | photographed receipt perspective OCR |

### 3.3 · Form / Application — *fields + checkbox + K-V*
Dataset trích dẫn: **FUNSD** (199 scanned forms, nhãn semantic entities + relations) · **XFUND** (mở rộng 7 ngôn ngữ) · **RVL-CDIP** (lớp questionnaire/form)

| ID | Layout | Keyword |
| :--- | :--- | :--- |
| FORM-01 | Simple questionnaire | questionnaire form layout |
| FORM-02 | Grid form | grid form layout |
| FORM-03 | Label-value form | key value form layout |
| FORM-04 | Two-column form | two column application form |
| FORM-05 | Multi-section form | multi section form layout |
| FORM-06 | Checkbox-heavy | checkbox form layout |
| FORM-07 | Form + signature | form signature field layout |
| FORM-08 | Table-based form | table form layout |
| FORM-09 | Government application | government application form layout |
| FORM-10 | Dense registration form | registration form dense layout |

### 3.4 · Identity Document — *photo + K-V + MRZ + security*
Dataset trích dẫn: **MIDV-500** (500 video clip, 50 loại giấy tờ tuỳ thân **mẫu**)

| ID | Layout | Keyword |
| :--- | :--- | :--- |
| ID-01 | Portrait left + fields right | ID card portrait left fields right |
| ID-02 | Portrait right + fields left | ID card portrait right fields left |
| ID-03 | Portrait top + fields bottom | ID card portrait top layout |
| ID-04 | Full-width government ID | government ID card layout |
| ID-05 | Passport bio page | passport biodata page layout |
| ID-06 | Passport with MRZ | passport MRZ layout |
| ID-07 | Driver license | driver license document layout |
| ID-08 | Residence permit | residence permit card layout |
| ID-09 | ID + QR/barcode | identity card QR barcode layout |
| ID-10 | Dense security-background ID | security background identity document |

### 3.5 · Academic / Scientific Document — *multi-column + equations + figures*
Dataset trích dẫn: **DocLayNet** · **OmniDocBench** (28 loại block-level, 4 loại span-level)

| ID | Layout | Keyword |
| :--- | :--- | :--- |
| SCI-01 | Single-column paper | single column scientific paper |
| SCI-02 | Two-column paper | two column academic paper |
| SCI-03 | Three-column paper | three column scientific paper |
| SCI-04 | Abstract + two columns | academic paper abstract two column |
| SCI-05 | Text + figure side-by-side | scientific paper figure text layout |
| SCI-06 | Text + large table | scientific paper large table layout |
| SCI-07 | Equation-heavy | equation heavy academic paper |
| SCI-08 | Figure-heavy | figure heavy scientific paper |
| SCI-09 | Appendix-heavy | academic paper appendix layout |
| SCI-10 | Review / survey paper | scientific review paper layout |

### 3.6 · Report / Business Document — *headings + paragraphs + tables/charts*
Dataset trích dẫn: **DocLayNet** (financial reports, laws/regulations, government tenders, manuals, patents)

| ID | Layout | Keyword |
| :--- | :--- | :--- |
| REP-01 | Executive summary | business report executive summary layout |
| REP-02 | Text-heavy report | text heavy business report |
| REP-03 | Report + tables | business report tables layout |
| REP-04 | Report + charts | business report charts layout |
| REP-05 | Dashboard-like report | business report dashboard layout |
| REP-06 | Two-column report | two column business report |
| REP-07 | Sectioned annual report | annual report section layout |
| REP-08 | Financial statement | financial statement document layout |
| REP-09 | Technical specification | technical specification document layout |
| REP-10 | Contract-like document | contract document layout |

### 3.7 · Newspaper / Magazine — *complex multi-column + images*
Dataset trích dẫn: **M6Doc** (riêng newspaper và magazine subsets) · **OmniDocBench**

| ID | Layout | Keyword |
| :--- | :--- | :--- |
| NEWS-01 | Classic 3-column newspaper | three column newspaper layout |
| NEWS-02 | 5-column newspaper | five column newspaper layout |
| NEWS-03 | Hero image + articles | newspaper hero image layout |
| NEWS-04 | Image-heavy magazine | image heavy magazine layout |
| NEWS-05 | Text-heavy magazine | text heavy magazine layout |
| NEWS-06 | Sidebar article | magazine sidebar layout |
| NEWS-07 | Full-page feature | magazine full page feature layout |
| NEWS-08 | Modular grid | modular newspaper grid layout |
| NEWS-09 | Advertisement + editorial | newspaper advertisement editorial layout |
| NEWS-10 | Irregular editorial | irregular newspaper layout |

### 3.8 · Handwritten / Historical Document — *degradation + handwriting + irregular layout*
Dataset trích dẫn: **Arabic Documents OCR Dataset** (12 lớp tài liệu) · **M6Doc** (note/book subsets)

| ID | Layout | Keyword |
| :--- | :--- | :--- |
| HIS-01 | Handwritten paragraph | handwritten document paragraph |
| HIS-02 | Handwritten form | handwritten form document |
| HIS-03 | Mixed printed + handwritten | printed handwritten mixed document |
| HIS-04 | Historical letter | historical handwritten letter |
| HIS-05 | Historical newspaper | historical newspaper scan |
| HIS-06 | Old book page | historical book page scan |
| HIS-07 | Notebook page | handwritten notebook page |
| HIS-08 | Marginal annotations | annotated historical document margins |
| HIS-09 | Dense archival record | historical archival record document |
| HIS-10 | Table + handwriting | historical handwritten table document |

---

## 4 · Nếu triển khai

Đây là **đề xuất**, chưa có root nào trong mục 4–7 (và phần còn thiếu của
mục 3, 8) được dựng thành luật/layout thật. Muốn đưa một layout ở trên vào kho,
đường đi giống hệt [`README.md` § 6 — Thêm một loại chứng từ mới](../README.md#-6-thêm-một-loại-chứng-từ-mới):
một giá trị mới trong `rules/document.yaml`, một file bố cục trong
`rulebase/layouts/`, khai dưới một node cha (họ) trong `rules/layout.yaml`, và
— nếu là một họ giấy hoàn toàn mới, như Identity Document hay Academic Paper —
một template CSS mới trong `generators/html/sheets/`.

Root 4–7 đổi khác nhiều so với các họ hiện có ở một điểm: tất cả `document`
hiện tại đều là **tiếng Việt**, còn bốn root này (Identity, Academic, Report,
Newspaper) chủ yếu gắn với tài liệu **tiếng Anh** hoặc đa ngôn ngữ — nên việc
mở rộng còn kéo theo `rulebase/corpus/` cho ngôn ngữ/văn phong tương ứng, chứ
không chỉ thêm layout.
