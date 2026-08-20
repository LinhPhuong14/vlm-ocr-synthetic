# Tự động hoá sinh dữ liệu: đưa LLM vào vòng **viết luật**, không vào vòng **vẽ ảnh**

Báo cáo phân tích hiện trạng và kế hoạch điều chỉnh, cho mục tiêu: *một LLM có
thể lập luận, lựa chọn và tạo bố cục — rồi pipeline tự chạy ra dataset có nhãn.*

Đọc từ code chứ không từ README; mọi con số trong báo cáo này đều đo lại trong
môi trường hiện tại và ghi ở [phụ lục](#phụ-lục-các-lệnh-đã-chạy-và-số-đo).

---

## 0. Câu trả lời ngắn

Repo này **đã** là một pipeline tự động hoàn chỉnh. Cái nó chưa có không phải
là máy chạy, mà là **người ra quyết định**: hôm nay con người đo một tờ giấy
thật, viết ra YAML, chọn họ bố cục, đặt trọng số, rồi đọc `ocr_report.json` để
biết lần sau nên sửa gì. Đó chính xác là ba việc câu hỏi đang hỏi —
*reasoning, lựa chọn, tạo layout*.

Kết luận có ba phần:

1. **LLM phải đứng ở author-time, không đứng ở render-time.** Đầu ra của LLM là
   **file YAML được commit**, không phải pixel và tuyệt đối không phải nhãn.
   Đây không phải sự thận trọng thừa: giá trị lớn nhất của repo là *nhãn được
   dựng từ chính object dùng để vẽ*, và tính tất định `seed → trang`. Một LLM
   gọi trong lúc render phá cả hai. Một LLM gọi lúc soạn luật thì không phá gì
   — sau khi YAML được duyệt và commit, pipeline tất định đúng như hôm nay.
2. **Thứ chặn đường không phải là LLM, mà là thiếu một schema cho file bố cục.**
   `rules/*.yaml` từ chối khoá lạ; `layouts/*.yaml` thì **không** — tôi đã thử
   và nó im lặng đi qua (§4.1). Với người copy file cũ thì sống được. Với LLM
   sinh ra khoá nghe rất hợp lý thì đó là chế độ hỏng thường gặp nhất, và nó
   **im lặng** — đúng loại lỗi mà `pipeline.yaml` mở đầu bằng lời than.
3. **Phần lớn cổng kiểm tra cần thiết đã có sẵn.** `tests/test_layout.py` đọc
   thư mục bố cục nên một file mới **tự động** được 5 seed × ~15 kiểm tra hình
   học; `preflight` đã kiểm phủ glyph và tràn giấy; `invariants` đã kiểm nhãn
   với hộp. Kế hoạch dưới đây gần như chỉ là **bắc cầu**, không phải xây mới.

---

## 1. Repo đang là gì

### 1.1 Kiến trúc

Một rule-base, ba renderer. Nội dung trang được quyết một lần trong
`rulebase/`; biến thành pixel theo ba đường khác nhau. Cả ba nhận cùng
`(recipe, receipt, grid)` và ghi cùng một `metadata.jsonl`.

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

Không gian luật hiện tại, đếm trực tiếp từ `load_rules()`:

| thuộc tính | số giá trị | số họ (`groups:`) |
| --- | ---: | ---: |
| document | 17 | — |
| layout | 16 | 6 |
| content | 12 | — |
| visual | 7 | — |
| color | 5 | — |
| ornament | 21 | 4 |
| augmentation | 15 | — |

Tích Descartes: **35.985.600** tổ hợp, chưa nhân corpus, số mặt hàng và seed.
Con số này là *trần trên* — `requires`/`excludes` cắt đi rất nhiều — nhưng nó
nói một điều quan trọng cho kế hoạch: **repo không thiếu đa dạng vì thiếu tổ
hợp, mà vì thiếu bố cục có thật.** Thêm một bố cục đúng đáng giá hơn nhiều so
với nới một trọng số.

### 1.2 Cái gì **đã** tự động

Nhiều hơn cảm giác ban đầu. Liệt kê ra để kế hoạch không đi xây lại:

| đã có | ở đâu | nó bảo đảm gì |
| --- | --- | --- |
| Khai báo một lần chạy | `pipeline.yaml` + `pipeline/config.py` | **khoá lạ thì dừng**, không chạy im lặng trên mặc định |
| Chia shard tất định | `pipeline/plan.py` | shard là *khoảng ảnh*, không phải bố cục — một trình duyệt cho cả shard |
| Chạy song song + resume | `pipeline/run.py`, `worker.py` | `DONE` ghi cuối và nguyên tử; shard dở thì **xoá làm lại**, không nối thêm |
| Ghi đè trọng số cho một lần chạy | `config.apply_overrides` | chỉ sửa được `weight/tags/requires/excludes`, và phải trỏ vào thứ **có thật** |
| Preflight | `pipeline/preflight.py` | giá trị luật không bao giờ bốc được, thiếu ảnh nền/hoa tiết, **phủ glyph tiếng Việt**, bố cục tràn khỏi khổ giấy |
| Bất biến từng ảnh | `pipeline/invariants.py` | số học tiền, quad nằm trong khung, không có ô glyph rỗng, **mọi giá trị nhãn đều thật sự được in** |
| Trôi phân phối | `pipeline/drift.py` | mix còn khớp luật không, đã trừ nhiễu lấy mẫu của chính cỡ shard đó |
| Vân tay vàng | `tools/baseline.py` | sha256 từng ảnh; chụp lại **bắt buộc** có `REASON` |
| Chứng minh OCR | `tools/ocr_proof.py` | chấm không phụ thuộc thứ tự đọc, tách theo bố cục / mức làm cũ / trường |
| Mô hình chi phí | `tools/profile_pipeline.py` | dự đoán được thời gian một lần chạy trước khi chạy |

### 1.3 Đo tại chỗ

| lệnh | kết quả (Python 3.11.15, chưa dựng venv renderer) |
| --- | --- |
| `python -m pytest` | **599 passed, 4 skipped, 1 xfailed**, 78 s |
| `python tasks.py check` | 84 file Python đều biên dịch |
| `python tasks.py check-rules` | sạch, trừ `degradation not importable` — thiếu numpy/opencv ở môi trường này, không phải lỗi luật |
| `python tasks.py distribution` | 2000/2000 lần bốc thành công, 16 bố cục trong 6 họ |

> **Lệch tài liệu nhỏ:** `README.md` §Quality gates ghi *"417 passed, 1 xfailed"*.
> Thực tế đã là 599. Nên cập nhật cùng lúc với bất kỳ thay đổi nào ở dưới —
> một con số cũ trong bảng "đã kiểm chứng" làm hỏng chính chức năng của bảng đó.

---

## 2. Chỗ nào con người vẫn phải làm

Đây là danh sách việc mà mục tiêu đang muốn giao cho LLM. Rút ra từ
[checklist "Adding a document kind"](../README.md#adding-a-document-kind) và từ
việc đọc code, chứ không từ mô tả:

| # | việc | hôm nay ai làm | đầu ra là gì |
| --- | --- | --- | --- |
| 1 | Đo một tờ giấy thật → viết `layouts/<id>.yaml` | người, bằng mắt | YAML |
| 2 | Chọn bố cục thuộc họ nào, thêm `requires` gì | người | một khối trong `rules/layout.yaml` |
| 3 | Đặt trọng số, cân mix | người, sau khi đọc `make distribution` | số trong `rules/*.yaml` |
| 4 | Viết ngữ nghĩa trường mới | người | **Python** trong `rulebase/content.py` |
| 5 | Gắn bố cục vào một họ CSS | người | **Python** — `sheets.FAMILIES` |
| 6 | Đọc `ocr_report.json` / `drift.json` rồi quyết sửa gì | người | không có đầu ra máy đọc được |

Việc 1–3 là YAML thuần → **LLM làm được, an toàn**.
Việc 6 là suy luận trên số đo → **LLM làm được, rẻ nhất, làm trước**.
Việc 4–5 là Python → làm sau cùng, và có người duyệt.

---

## 3. Ranh giới an toàn: author-time, không phải render-time

`docs/huong-dan-va-giai-thich.md` §9 đã trả lời câu "sao không dùng LLM sinh
hoá đơn cho nhanh": vì cần **nhãn chính xác tới từng ký tự và từng toạ độ**, mà
model sinh ảnh không nói nó vẽ chữ gì ở đâu. Câu trả lời đó vẫn đúng nguyên vẹn
và kế hoạch này **không** mâu thuẫn với nó — vì nó đặt LLM ở một chỗ khác hẳn:

```
   ✗ SAI: render-time                        ✓ ĐÚNG: author-time
   ─────────────────────                     ─────────────────────
   seed ──▶ LLM ──▶ ảnh + nhãn               người/LLM ──▶ layouts/*.yaml
             ↑                                                │
        nhãn chỉ tốt bằng OCR                             cổng kiểm tra
        seed không tái lập được                               │
        mọi cổng kiểm tra vô nghĩa                        commit vào repo
                                                              │
                                             seed ──▶ pipeline tất định ──▶ ảnh + nhãn
                                                     (y hệt hôm nay)
```

Hệ quả cụ thể của ranh giới này, viết ra để sau không ai vô tình vượt:

* **Không có lời gọi mạng nào trong `rulebase/`, `generators/`, `degradation/`,
  `pipeline/`.** Toàn bộ phần LLM sống trong `tools/`, và chỉ chạy khi người
  gõ lệnh — không bao giờ chạy trong `render.py` hay `worker.py`.
* **LLM không bao giờ sinh nhãn.** Nhãn vẫn do `receipt.ground_truth()` dựng từ
  cùng object mà renderer vẽ. LLM chỉ mô tả *cấu trúc trang*.
* **LLM không ghi thẳng vào `rulebase/`.** Nó ghi vào `proposals/`, và một lệnh
  `accept` chạy hết chuỗi cổng mới chép sang.
* **Tính tất định không đổi.** Sau khi YAML được commit, `make baseline-verify`
  vẫn là câu hỏi có nghĩa.

---

## 4. Khoảng trống chặn đường, đã đo

### 4.1 File bố cục không có schema — chứng minh

`rules/*.yaml` chặt: `Option.from_dict` và `Group.from_dict` **raise** khi gặp
khoá lạ, kèm câu "params belong under 'params:'". `layouts/*.yaml` thì không —
`load_layout` chỉ là `yaml.safe_load`, và mỗi emitter tự `spec.get(...)`.

Thử: chép thư mục bố cục ra chỗ khác, thêm vào `eatery_ascii.yaml` hai lỗi
chính tả rất giống lỗi một LLM sẽ mắc — `headr:` thay cho `header:`, và
`algin:` thay cho `align:` trong một cột:

```
built anyway: 21 rows, 40 cells — unknown keys silently ignored
```

Không có ngoại lệ, không có cảnh báo. Trang vẫn dựng, chỉ là **thiếu đúng cái
mà khoá đó lẽ ra làm**. Với `headr:` thì mất cả khối header mà không ai biết;
với `algin:` thì cột canh sai lề và trông vẫn "hợp lý".

`build_grid` có kiểm hai thứ — `sections:` lạ và `sheet:` lạ đều raise (xem
`tests/test_layout.py::test_an_unknown_sheet_is_refused_when_the_layout_is_built`).
Nhưng đó là hai khoá trong khoảng bốn mươi.

**Đây là việc phải làm trước tiên, và đáng làm ngay cả khi không bao giờ dùng
LLM** — cùng lỗi đó người cũng mắc, chỉ hiếm hơn.

### 4.2 `sheets.FAMILIES` là dict hard-code

```python
FAMILIES = {"invoice_vat_form": statutory, ..., "market_vat": till}
```

Một bố cục mới đi đường CSS **bắt buộc** phải sửa Python. Chỗ này viết đúng —
thiếu thì raise kèm danh sách chứ không âm thầm vẽ hoá đơn thuế cho tờ folio
khách sạn — nhưng nó là điểm chạm Python cuối cùng trên con đường lẽ ra thuần
YAML, và README tự nhận *"Nothing in `generators/` changes"* khi thêm bố cục.
Với đường lưới ký tự thì đúng; với đường CSS thì chưa.

### 4.3 Không có vòng phản hồi đóng

`ocr_report.json` có `by_layout`, `by_layout_augmentation`, `worst_fields`.
`drift.json` có vector mix. `distribution` có mix thật. Ba nguồn đo tốt — và
**không có gì đọc chúng để đề xuất thay đổi**. Vòng lặp hiện tại đóng qua mắt
người.

Số hiện có đã đủ để một tác nhân suy luận. Từ `data/dataset60/proof/README.md`:

| bố cục | token recall |
| --- | ---: |
| invoice_brand | 0.924 |
| … | … |
| invoice_export | 0.296 |
| market_barcode | 0.234 |

Chênh **4×** giữa bố cục dễ nhất và khó nhất. Đó là một câu hỏi rất cụ thể mà
một LLM có thể trả lời được: *market_barcode khó vì hàng cột chật, vì mã vạch,
hay vì mix làm cũ của nó nặng hơn?* — và `by_layout_augmentation` có sẵn dữ
liệu để tách ba khả năng đó.

### 4.4 `content.py` rẽ nhánh theo profile

`_build_store`, `_build_items`, `_build_meta` đều có `if profile == "market"`;
`_build_utility_items`, `_build_medical_items`, `_build_stay_items` là các
nhánh riêng. Nghĩa là:

* một **bố cục mới của loại chứng từ đã có** → YAML thuần, LLM làm được;
* một **loại chứng từ mới có trường chưa từng có** → phải sửa Python.

Kế hoạch phải nói rõ ranh giới này, nếu không LLM sẽ đề xuất một bố cục dùng
`from: <nguồn chưa tồn tại>` và nó sẽ **im lặng in ra chuỗi rỗng**.

### 4.5 `source:` — lời hứa mạnh nhất của repo

Mỗi `layouts/*.yaml` có `source:` ghi bức ảnh nó được đo từ đó. `docs/huong-dan`
§9 nói thẳng: *"Mình thà có 5 cái đúng còn hơn 50 cái tưởng tượng."*

Một LLM **bịa** bố cục thì mâu thuẫn trực tiếp với câu đó. Một LLM **phiên**
một tờ giấy có thật thành YAML thì không — đó vẫn là "đo từ giấy thật", chỉ là
người đo nhanh hơn. Ranh giới này phải nằm trong dữ liệu, không nằm trong lời
hứa: xem `provenance:` ở Giai đoạn 2.

---

## 5. Kế hoạch

Bảy giai đoạn. Mỗi giai đoạn tự nó dùng được, có cổng riêng, và không giai đoạn
nào bắt buộc phải có giai đoạn sau mới có giá trị.

Ba động từ trong mục tiêu ánh xạ vào kế hoạch như sau:

| mục tiêu | giai đoạn |
| --- | --- |
| **tạo layout** | 0 → 1 → 2 |
| **reasoning** (tự sửa theo lỗi máy trả về) | 3 |
| **lựa chọn** (chọn bố cục / trọng số / mức làm cũ theo mục tiêu) | 4 |
| mở trần đa dạng | 5 |
| loại chứng từ mới | 6 |

---

### Giai đoạn 0 — `rulebase/schema.py`: ngữ pháp bố cục thành **dữ liệu**

**Tại sao trước tiên.** Nó vừa là bộ kiểm tra (§4.1), vừa là **hợp đồng** để
đưa cho LLM. Một schema viết ra một lần phục vụ cả hai; một prompt mô tả bằng
văn xuôi thì chỉ phục vụ cái sau, và sẽ lệch khỏi code trong vòng một tháng.

**Làm gì.**

```python
# rulebase/schema.py
#
# Ngữ pháp của một file bố cục, ở dạng máy đọc được. rulebase/README.md §3 mô
# tả cùng thứ này bằng văn xuôi cho người đọc; đây là bản cho máy, và là bản
# `build_grid` thật sự thi hành -- hai bản không được phép lệch nhau.

FROM_SOURCES = ("stt", "name", "qty", "unit_price", "amount", "barcode", ...)

LAYOUT_SCHEMA = {
    "id":       {"type": "str", "required": True},
    "name":     {"type": "str"},
    "source":   {"type": "str", "required": True},
    "width":    {"type": "int_pair", "min": 20, "max": 200, "required": True},
    "gutter":   {"type": "int", "min": 0, "max": 8},
    "sheet":    {"type": "enum", "values": tuple(SHEETS)},
    "rules":    {"type": "enum", "values": ("ascii", "marks")},
    "sections": {"type": "enum_list", "values": tuple(SECTIONS)},
    "columns":  {"type": "column_list"},
    "item":     {"type": "block", "keys": {...}},
    ...
}

def validate_layout(spec: dict, layout_id: str = "") -> list[str]:
    """Mọi vấn đề của một file bố cục, không dừng ở cái đầu tiên."""

def schema_json() -> dict:
    """Cùng schema, dạng JSON -- đây là thứ đưa cho LLM."""
```

**Bắt được gì mà hôm nay không bắt được:**

* khoá lạ ở mọi cấp (§4.1) — kể cả trong `columns:`, `item.rows:`, `totals:`;
* `from:` trỏ vào nguồn không có trong `FROM_SOURCES` → hôm nay in ra rỗng;
* `col:` trỏ vào `key` cột chưa khai báo;
* tổng `width:` của các cột cộng gutter vượt `width:` nhỏ nhất của trang;
* không có đúng một cột `width: 0` (cột "lấy phần còn lại");
* `shade:` / `border:` khai mà không có `rules: marks` → âm thầm bị bỏ qua;
* section khai mà thiếu khối cấu hình nó cần.

**Gắn vào đâu.** `build_grid` gọi và raise (một file hỏng thì dừng trước khi có
ảnh); `tools/rules_report.check()` gọi và **liệt kê tất cả** (để `make preflight`
và CI báo một lượt). Thêm task `make check-layouts` và `make layout-schema`
(in JSON ra stdout).

**Xong khi:** thí nghiệm §4.1 chạy lại và báo đúng hai lỗi; 16 file bố cục hiện
có đều qua sạch; CI job `rules` chạy thêm `check-layouts`.

**Ước lượng:** 1–2 ngày. **Không cần LLM.** Đây là phần đáng làm nhất trong cả
kế hoạch dù có làm tiếp hay không.

---

### Giai đoạn 1 — `make check-layouts`: các kiểm tra ngữ nghĩa còn lại

Schema bắt lỗi *cú pháp*. Còn lại là những thứ chỉ biết khi dựng thử — và
**phần lớn đã có sẵn**, chỉ cần gom lại thành một lệnh:

| kiểm tra | đã có ở đâu |
| --- | --- |
| bố cục dựng được, ô không chồng, không tràn cột, chữ vừa cột | `tests/test_layout.py`, đã tham số hoá theo `available_layouts()` |
| không tràn khổ giấy | `preflight.sheet_overflow` |
| phủ glyph trên chuỗi mới của bố cục | `preflight.printable_text` — đã đi bộ **toàn bộ** file bố cục |
| nhãn không mô tả thứ không in | `tests/test_content.py::test_label_never_describes_unprinted_text` |
| khai trong luật ⇔ có file | `rules_report.check` |

Điều đáng nói: **một file bố cục mới tự động được 5 seed × ~15 kiểm tra hình
học**, vì `tests/test_layout.py` đọc thư mục chứ không liệt kê tên. Nền móng
cho vòng lặp LLM đã nằm sẵn ở đó.

Việc thật sự phải viết mới ở giai đoạn này chỉ là cái vỏ: một lệnh chạy hết
chuỗi trên **một** bố cục và trả về báo cáo máy đọc được (JSON) chứ không chỉ
là exit code — vì đó là thứ giai đoạn 3 sẽ đọc.

**Ước lượng:** 0,5–1 ngày.

---

### Giai đoạn 2 — `tools/propose_layout.py`: LLM soạn bố cục

**Vào:** một chứng từ **có thật** — ảnh, PDF, hoặc bản mô tả cấu trúc — cộng
`schema_json()`, cộng 2–3 bố cục gần nhất làm ví dụ.

**Ra:** một **thư mục đề xuất**, không phải một commit:

```
proposals/<id>/
├── layout.yaml            # bản nháp cho rulebase/layouts/<id>.yaml
├── rules-layout.yaml      # khối để chèn vào rules/layout.yaml, dưới họ nào
├── provenance.json        # nguồn, phương pháp, model, prompt hash, ngày
├── preview.txt            # đầu ra make preview-grid, để người liếc mắt
└── rounds/                # giai đoạn 3 ghi vào đây
```

`provenance.json` là chỗ giải quyết §4.5 — và nó phải vào **cả file bố cục**,
không chỉ vào thư mục đề xuất:

```yaml
source: "ảnh hoá đơn tiền nước Sawaco tháng 3/2024, người dùng cung cấp"
provenance:
  method: llm_transcribed      # measured | llm_transcribed | llm_proposed
  evidence: "docs/mau/sawaco-2024-03.jpg"
  reviewed_by: "<tên người duyệt>"
```

Ba giá trị `method` khác nhau thật sự, và schema phải bắt buộc có:

* `measured` — người đo từ ảnh. 16 bố cục hôm nay.
* `llm_transcribed` — LLM phiên từ một chứng từ có thật, người duyệt. **Đây là
  chế độ được khuyến nghị.**
* `llm_proposed` — không có chứng từ gốc. Cho phép, nhưng phải đếm được: một
  câu lệnh `make distribution` nên in ra tỉ lệ ba loại này, để không ai sáng ra
  phát hiện nửa dataset là giấy tưởng tượng.

**Cổng trước khi `accept`** — chạy đúng thứ tự này, dừng ở lỗi đầu tiên:

```bash
make check-layouts LAYOUT=<id>     # giai đoạn 0 + 1
make check-rules                   # khai báo trong họ có hợp lệ không
make preview-grid LAYOUT=<id>      # người nhìn một lần
make preflight                     # phủ glyph trên chuỗi mới, tràn giấy
python -m pytest tests/test_layout.py tests/test_content.py -q
python tools/generate_dataset.py -n 3 --layouts <id> -o data/tmp<id>
make check-boxes                   # hộp còn mô tả đúng pixel
```

`make accept-layout ID=<id>` chỉ chép file khi cả chuỗi xanh, và **không bao
giờ** chạy `make baseline-write` — thêm bố cục làm đổi kế hoạch, nên baseline
phải chụp lại có chủ ý và có `REASON`.

**Ước lượng:** 3–4 ngày. **Điểm rủi ro:** LLM sẽ muốn phát minh section mới.
Schema phải nói rõ danh sách 15 section là đóng, và lỗi phải liệt kê chúng ra.

---

### Giai đoạn 3 — vòng tự sửa: chỗ "reasoning" thật sự có giá

LLM đọc đầu ra validator và sửa chính YAML của nó, tối đa N vòng.

Vòng lặp này hội tụ vì **lỗi do máy sinh ra và rất cụ thể** — `"columns[3]: có
khoá lạ 'algin'; ý bạn là 'align'?"` là thứ một model sửa đúng ngay lần đầu.
Nó khác hẳn "ảnh trông chưa giống", vốn không hội tụ.

Ràng buộc:

* chặn ở 5 vòng, ghi **mọi** vòng vào `proposals/<id>/rounds/NN.{yaml,errors}`
  — một đề xuất qua ở vòng 5 khác hẳn một đề xuất qua ngay, và người duyệt cần
  thấy điều đó;
* nếu cùng một lỗi lặp lại hai vòng liền → dừng và báo người. Model đang loanh
  quanh chứ không đang sửa;
* seed cố định + prompt lưu lại, để một đề xuất tái lập được.

**Ước lượng:** 1–2 ngày sau giai đoạn 2.

---

### Giai đoạn 4 — `tools/plan_run.py`: LLM **lựa chọn**

Rẻ nhất và an toàn nhất trong cả kế hoạch — nên có thể làm **song song** với
giai đoạn 0, không phải chờ.

**Vào:** một mục tiêu bằng lời + `ocr_report.json` + `drift.json` +
`distribution`.
**Ra:** một `pipeline.yaml`.

Vì sao an toàn: `pipeline/config.py` **đã** từ chối khoá lạ, và
`apply_overrides` **đã** bắt mọi override phải trỏ vào thứ có thật, chỉ cho
sửa `weight/tags/requires/excludes`. Nghĩa là bán kính sát thương của một
`pipeline.yaml` do LLM viết đã bị chặn bởi một cổng đang chạy hôm nay. Không
cần xây gì để bảo vệ.

Ví dụ cụ thể, dùng số thật ở §4.3:

> *"Cần 5000 ảnh nghiêng về những chỗ model đang yếu."*
> → đọc `by_layout`: `market_barcode` 0.234, `invoice_export` 0.296, so với
> `invoice_brand` 0.924. Đọc `by_layout_augmentation` để tách "bố cục khó" khỏi
> "bố cục này rơi vào mix làm cũ nặng". Ra `overrides:` nâng trọng số hai bố
> cục đó, kèm **một câu giải thích vì sao** ghi trong comment của file.

Câu giải thích không phải trang trí: `pipeline.yaml` hiện tại là file được chú
thích dày nhất repo, vì mỗi con số trong đó là một quyết định. Một file do máy
sinh không nói được vì sao thì làm hỏng nếp đó.

**Ước lượng:** 2 ngày. **Giá trị/công sức cao nhất trong cả bảng.**

---

### Giai đoạn 5 — corpus có `source: llm`

Cái móc **đã có sẵn**, chưa dùng:

```python
# pipeline/drift.py
SOURCES = ("corpus", "llm", "fallback")
PRIMARY_SOURCE = "corpus"
FALLBACK_LIMIT = 0.05
```

Chú thích ngay trên nó viết *"W2 always writes `corpus`; W6 introduces the
others"*. Nghĩa là chỗ này đã được thiết kế trước cho đúng việc đang bàn.

Việc phải làm: một cột nguồn cho từng chuỗi (hoặc một file kèm), để `drift.py`
đếm được mix; cộng chính sách cho `fallback`. Giá trị: phá trần corpus (115 món
quán, 88 mặt hàng siêu thị) mà **không** đụng đến cấu trúc trang — rủi ro thấp
hơn hẳn sinh bố cục.

Bắt buộc: `make preflight` phải chạy lại sau mỗi lần thêm corpus. Phủ glyph là
kiểm tra rủi ro số một của repo, và một LLM viết tên hàng tiếng Việt rất dễ
đẻ ra ký tự chưa font nào trong `fonts/` vẽ được — lúc đó ảnh in ra ô vuông
trong khi nhãn vẫn khai là chữ.

**Ước lượng:** 2–3 ngày.

---

### Giai đoạn 6 — loại chứng từ mới (chạm Python)

Chỉ sau 0–5. LLM đề xuất bản vá `rulebase/content.py` dưới dạng patch, người
duyệt. Đây là chỗ duy nhất một sửa đổi có thể phá bất biến *nhãn ↔ pixel*, nên
nó ở cuối và không tự động hoá phần duyệt.

**Kèm theo, nên làm sớm hơn nếu tiện:** bỏ hard-code `sheets.FAMILIES` (§4.2)
bằng cách cho file bố cục tự khai `family: statutory`, schema kiểm giá trị đó
nằm trong danh sách module có thật. Dict Python trở thành **sổ đăng ký module**
chứ không còn là bảng tra bố cục. Sau đó một bố cục mới đi đường CSS cũng
thuần YAML, và câu README *"Nothing in `generators/` changes"* thành đúng cho
cả hai đường vẽ.

**Ước lượng:** 1 ngày cho phần `FAMILIES`; loại chứng từ mới thì tuỳ chứng từ.

---

## 6. Thứ tự ưu tiên

| # | giai đoạn | công | giá trị | phụ thuộc |
| --- | --- | --- | --- | --- |
| 1 | **0 — schema bố cục** | 1–2 ngày | ★★★ chặn lỗi im lặng; là hợp đồng cho LLM | — |
| 2 | **4 — LLM lập kế hoạch chạy** | 2 ngày | ★★★ dùng ngay, rủi ro ~0 | (song song được) |
| 3 | **1 — `check-layouts`** | 0,5–1 ngày | ★★ gom cổng sẵn có | 0 |
| 4 | **2 — LLM soạn bố cục** | 3–4 ngày | ★★★ đúng mục tiêu chính | 0, 1 |
| 5 | **3 — vòng tự sửa** | 1–2 ngày | ★★ tăng tỉ lệ qua cổng | 2 |
| 6 | **6b — bỏ `FAMILIES`** | 1 ngày | ★★ xoá điểm chạm Python cuối | 0 |
| 7 | **5 — corpus LLM** | 2–3 ngày | ★★ phá trần đa dạng | 0 |
| 8 | **6 — loại chứng từ mới** | tuỳ | ★ cần người duyệt | tất cả |

Sau mục #4 là đã đạt mục tiêu đề bài: LLM lập luận, lựa chọn, và tạo được bố
cục — với mọi cổng hiện có còn nguyên hiệu lực.

---

## 7. Cái gì **không** được đổi

Bốn điều. Mỗi cái là lý do repo này đáng tin hơn một bộ sinh ảnh:

1. **Nhãn dựng từ chính object dùng để vẽ.** Không có LLM nào chạm vào
   `ground_truth()`.
2. **`seed` → trang.** Một lời gọi mạng trong đường render phá tính tất định,
   và cùng lúc làm `make baseline-verify` mất nghĩa.
3. **Mọi cổng còn nguyên.** Năng lực mới **thêm** cổng, không bớt. Nếu một đề
   xuất của LLM làm đỏ một cổng, cổng đúng và đề xuất sai — cho tới khi có ai
   chứng minh ngược lại, bằng số, và ghi lý do vào file như `baseline-write`
   đang bắt buộc.
4. **Mỗi bố cục phải nói nó từ đâu ra.** `provenance.method` bắt buộc, và tỉ lệ
   ba loại phải đếm được.

---

## 8. Rủi ro

| rủi ro | dấu hiệu | cách chặn |
| --- | --- | --- |
| LLM đẻ khoá nghe hợp lý mà không tồn tại | trang thiếu một khối, không ai báo | **Giai đoạn 0** — lý do nó đứng đầu |
| LLM bịa bố cục không tờ giấy nào giống | dataset đa dạng giả, model học sai phân phối | `provenance.method`, và đếm tỉ lệ `llm_proposed` |
| Trọng số do LLM đặt làm lệch mix | drift cảnh báo, hoặc tệ hơn: không cảnh báo vì mix mới là "chủ ý" | `apply_overrides` đã bắt trỏ đúng thứ có thật; thêm: mọi override phải kèm một dòng lý do |
| Chuỗi corpus mới thiếu glyph | in ra ô vuông, nhãn vẫn khai là chữ | `make preflight` bắt buộc sau mỗi lần thêm corpus |
| Vòng tự sửa quẩn | 5 vòng vẫn đỏ, tốn token | dừng khi một lỗi lặp hai vòng liền |
| Người duyệt đóng dấu cho có | bố cục xấu lọt vào repo | `preview.txt` trong mỗi đề xuất; bố cục là thứ duy nhất phải nhìn bằng mắt |
| Schema và `rulebase/README.md` lệch nhau | tài liệu nói một đằng, máy thi hành một nẻo | một test khẳng định mọi khoá trong 16 file bố cục hiện có đều có trong schema |

---

## Phụ lục: các lệnh đã chạy và số đo

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

$ python tasks.py distribution
2000 lần bốc thành công / 2000 — 16 bố cục trong 6 họ
```

Đếm không gian luật:

```
document 17 · layout 16 (6 họ) · content 12 · visual 7 · color 5 ·
ornament 21 (4 họ) · augmentation 15   →   trần trên 35.985.600 tổ hợp
```

Thí nghiệm §4.1 — thêm `headr:` và `columns[0].algin:` vào một bản sao của
`eatery_ascii.yaml` rồi gọi `build_grid` với `root=` trỏ vào bản sao:

```
built anyway: 21 rows, 40 cells — unknown keys silently ignored
```

Số OCR trích từ `data/dataset60/proof/README.md` (tesseract 5.3.4, `vie`,
psm 4): `invoice_brand` 0.924 → `market_barcode` 0.234.

---

## Liên quan

* [`README.md` §Adding a document kind](../README.md#adding-a-document-kind) — quy trình thủ công hôm nay
* [`rulebase/README.md` §3](../rulebase/README.md) — ngữ pháp file bố cục, bản văn xuôi mà Giai đoạn 0 biến thành dữ liệu
* [`docs/huong-dan-va-giai-thich.md` §9](huong-dan-va-giai-thich.md) — vì sao không dùng LLM sinh thẳng ảnh
* [`pipeline.yaml`](../pipeline.yaml) — đầu ra của Giai đoạn 4
* [`pipeline/drift.py`](../pipeline/drift.py) — `SOURCES` đã chừa sẵn chỗ cho `llm`
