# Redesign plan — `vlm-ocr-synthetic` (v2, HTML-first)

> Status: **approved direction**, design updated per review (12 fixes). Ready for P0.
> Pipeline execution order: P0 → P8 as §7. Plan document is the source of truth for the planner agent.

---

## 0. Mục tiêu

Biến repo thành một **general-purpose synthetic OCR/VLM document engine**: một rule/spec chung, một renderer HTML duy nhất, các asset factory độc lập (pattern, artifact, handwriting), và annotation hierarchy bậc thang là capability hạng nhất.

```
Spec → Sampler → Content Provider → Builder → Document Model → HTML/CSS → Chromium
     → Artifact/Asset composite → Environment → Augmentation → Image + Hierarchical BBoxes + GT + Recipe
```

Thay vì:
- 3 renderer chia sẻ character-grid (cũ), chỉ **một** renderer HTML.
- Document type là logic nằm trong code renderer (cũ), trở thành **data/configuration**.
- Corpus là nguồn content duy nhất (cũ), trở thành một trong các **content providers** (corpus / LLM).

## 1. Các quyết định đã chốt

| # | Quyết định | Hệ quả |
|---|---|---|
| 1 | **HTML-first** — Chromium là primary renderer duy nhất | Bỏ renderer glyph + character-grid hoàn toàn; thermal cũng chuyển CSS flow |
| 2 | **Strip genalog** — WeasyPrint chỉ là secondary PDF renderer | `render/weasy/` wrapper mỏng, dùng chung markup với HTML |
| 3 | **WriteViT** dùng làm **handwriting asset provider**, không chạy trong dataset loop | pre-gen library PNG, render chỉ composite; CPU-only pipeline |
| 4 | **Bỏ character-grid** | `geometry.py` xóa; chỉ còn `make_content`; structure đo từ cells |
| 5 | **Annotation hierarchy là first-class capability** | DOM tree là source of truth cho bbox hierarchy (page→…→character) |
| 6 | **Environment tách khỏi augmentation** | Environment = capture condition; Augmentation = image degradation |
| 7 | **Artifact tách khỏi ornament** | Artifact = semantic document marks; Ornament = decorative elements |
| 8 | **LLM là Content Provider, không phải Renderer** | LLM → structured JSON → validator → builder → HTML; không bao giờ trả HTML trực tiếp |
| 9 | Giữ tên repo `vlm-ocr-synthetic` | không đổi branding |
| 10 | **Recipe.json** mỗi sample | ghi đầy đủ cách sample được sinh, phục vụ experiment/debug |

## 2. Attribute dependency graph (thay cho "8 attributes")

Không còn gọi "8 attributes". Có **11 thuộc tính** trong một **dependency graph** (DAG) — không phải mọi cạnh đều là dependency cứng:

```
document ──► layout ──► content
              │            │
              ▼            ▼
        typography ◄──────┘
        ├─ visual
        ├─ color
        └─ ornament
              │
              ▼
         handwriting ──► artifact ──► pattern ──► environment ──► augmentation
```

| Layer | Thuộc tính | Decides |
|---|---|---|
| 1 | `document` | loại giấy tờ + params |
| 2 | `layout` | họ bố cục → layout files |
| 3 | `content` | câu/giá trị/ngữ liệu (provider-agnostic) |
| 4 | `visual` / `color` / `ornament` (typography) | font, mực, giấy, hoa văn trang trí |
| 5 | `handwriting` | trường nào viết tay, writer, mật độ |
| 6 | `artifact` | stamp/seal/signature/barcode/QR/checkbox |
| 7 | `pattern` | nền, watermark, giấy, guilloche |
| 8 | `environment` | cách document được capture |
| 9 | `augmentation` | degradation của ảnh |

Mọi ràng buộc `requires`/`excludes`/`tags` vẫn đi qua dependency graph (mở rộng từ `spec.py` → `sampler.py`).

## 3. Cây phân cấp mới (đã chốt)

```
vlm-ocr-synthetic/
│
├── spec/                          # WHAT a document is
│   ├── attributes/                # 11 thuộc tính, đặt theo dependency graph
│   │   ├── _order.yaml            # causal order
│   │   ├── document.yaml
│   │   ├── layout.yaml
│   │   ├── content.yaml
│   │   ├── visual.yaml
│   │   ├── color.yaml
│   │   ├── ornament.yaml
│   │   ├── handwriting.yaml
│   │   ├── artifact.yaml          # NEW: stamp/seal/signature/barcode/QR/checkbox
│   │   ├── pattern.yaml           # NEW: nền/watermark/giấy/guilloche
│   │   ├── environment.yaml       # NEW: camera/lighting/scene/paper-warp
│   │   └── augmentation.yaml
│   │
│   ├── distribution/              # NEW: C1–C4 trở thành distribution metaphor
│   │   └── risk_profile.yaml      #     (layout.nested_table, handwriting.mixed, …)
│   │
│   ├── families/                  # 1 thư mục = 1 họ tài liệu (manifest.yaml)
│   │   ├── retail_receipt/
│   │   ├── statutory_invoice/
│   │   ├── utility_invoice/
│   │   ├── lodging_invoice/
│   │   ├── modern_invoice/
│   │   ├── administrative/
│   │   ├── loan/                  # MỚI
│   │   ├── payment_voucher/       # MỚI
│   │   ├── certificate/           # MỚI
│   │   └── filled_form/           # MỚI
│   │
│   ├── annotation/                # NEW — first-class capability
│   │   ├── hierarchy.yaml         #     page→section→block→paragraph→sentence→line→word→character
│   │   ├── labels.yaml            #     semantic labels (title, section_header, …)
│   │   └── schema.yaml            #     CORD/PubTabNet-compatible schema
│   │
│   ├── content/                   # NEW — content providers, không nhét vào corpus
│   │   ├── providers/
│   │   │   ├── corpus.py
│   │   │   └── llm.py             #     LLM → JSON schema → validator → DocumentModel
│   │   ├── constraints/           #     ràng buộc content (regex, tỷ lệ, định dạng tiền…)
│   │   ├── validators/            #     validate trước khi vào builder
│   │   └── schemas/               #     JSON schema cho từng loại content intent
│   │
│   ├── sampler.py                 # (was spec.py) weighted sampling + constraint graph
│   ├── builder.py                 # (was content.py build) recipe → DocumentModel
│   └── text.py
│
├── render/
│   ├── html/                      # PRIMARY — Chromium/Playwright
│   │   ├── render.py              # CLI + worklist
│   │   ├── engine.py              # (was page.py) browser lifecycle, bbox extraction
│   │   ├── sheets/                # CSS flow + table (đường duy nhất)
│   │   │   ├── base.py            # block chung: items, totals, parties, signatures
│   │   │   ├── families.py        # family id → template registry (KHÔNG hard-code)
│   │   │   ├── statutory.py  lodging.py  modern.py  medical.py  statement.py  till.py
│   │   │   ├── loan.py  voucher.py  certificate.py  form.py       # MỚI
│   │   │   └── components/        # NEW: HTML component composition
│   │   └── assets.py              # composite patterns/ + artifacts/ + handwriting/
│   └── weasy/                     # SECONDARY — WeasyPrint thuần (strip genalog)
│       └── render.py              # reuse sheets.build() + PyMuPDF rasterise
│
├── patterns/                      # asset factory (synthdog reborn + WriteViT)
│   ├── generate.py                # CLI: make patterns / make handwriting
│   ├── backgrounds/               # nền trang, watermark, guilloche
│   ├── paper/                     # texture giấy (was textures/paper)
│   ├── ornaments/                 # hoa văn trang trí (was textures/ornament)
│   ├── artifacts/                 # NEW — semantic marks
│   │   ├── stamps/
│   │   ├── seals/
│   │   ├── signatures/
│   │   └── barcodes/
│   ├── handwriting/               # NEW — WriteViT asset provider
│   │   ├── writevit/              # vendored WriteViT (MIT) + vn_ckpt.pth
│   │   ├── providers/             # future: thay/nhiều provider
│   │   ├── library/               # pre-gen output, pipeline chỉ đọc
│   │   │   ├── paragraph/  field/  name/  date/  signature/
│   │   └── selector.py            # QUAN TRỌNG: chọn asset theo handwriting.yaml
│   └── synthdog/                  # engine synthtiger (chỉ sinh asset, hết render)
│
├── augment/                       # post-render image degradation (was degradation/)
│   ├── __init__.py                # registry
│   ├── models/                    # 14 model hiện có
│   └── pipeline.py
│
├── environment/                   # NEW — capture condition, tách khỏi augmentation
│   ├── __init__.py
│   ├── camera.py                  # perspective, rotation, scale
│   ├── lighting.py                # direction, intensity, unevenness
│   ├── scene.py                   # background, shadow, surface
│   └── paper.py                   # warp, fold, curl
│
├── pipeline/                      # orchestration — giữ nguyên
├── data/                          # datasets — giữ nguyên cấu trúc
├── tools/                         # tiện ích
├── tests/
├── docs/
├── fonts/
└── references/
```

## 4. Annotation Engine — DOM tree là source of truth

HTML không chỉ để render ảnh. **DOM tree là nguồn chân lý cho annotation hierarchy.**

`spec/annotation/hierarchy.yaml`:

```yaml
hierarchy:
  page:      {children: [header, section, body, table, footer]}
  section:   {children: [title, paragraph, table, image]}
  paragraph: {children: [sentence]}
  sentence:  {children: [word]}
  word:      {children: [character]}
```

Chromium trả về bbox theo từng cấp:

```
DOM → getBoundingClientRect() → page bbox / section bbox / block bbox / paragraph bbox
     / sentence bbox / line bbox / word bbox / character bbox / table bbox / row bbox / cell bbox
```

Annotation **không phụ thuộc document family**: cùng một chuỗi "Thông tin người mua" có thể đồng thời là `TITLE`, `TEXT`, `SECTION_HEADER`, `WORD`, `CHARACTER` tùy task. Output schema tương thích CORD/PubTabNet.

## 5. Environment ≠ Augmentation

| | Environment | Augmentation |
|---|---|---|
| Mô phỏng | cách document được **capture** | **degradation** của image |
| Ví dụ | camera (perspective/rotation/scale), lighting (direction/intensity/unevenness), scene (background/shadow/surface), paper (warp/fold/curl) | blur, noise, compression, low_resolution, contrast, saturation, scratch, texture, stain |

Causal layer khác nhau, là 2 attribute riêng (`environment.yaml` / `augmentation.yaml`), chạy theo thứ tự: render → artifact composite → environment → augmentation.

## 6. Artifact ≠ Ornament

| | Artifact | Ornament |
|---|---|---|
| Bản chất | semantic document marks | decorative elements |
| Ví dụ | stamp, seal, signature, barcode, QR, checkbox, handwritten mark | background, watermark, guilloche, hoa văn |

Stamp có thể **overlap text, overlap signature, cross section boundary** — rất quan trọng với OCR/VLM, nên là attribute riêng `artifact.yaml` + asset riêng trong `patterns/artifacts/`.

## 7. Handwriting — WriteViT là asset provider

**Không coi WriteViT là handwriting engine hoàn chỉnh.** Nó là một **Handwriting Asset Provider** trong số nhiều provider tương lai. Pipeline cần nhiều loại asset: paragraph, field, name, date, signature, initial, check mark.

```
[asset time] patterns/handwriting/generate.py (GPU, `make handwriting`)
    text + writer refs ──► WriteViT ──► library/<writer>/<type>/<hash>.png (line-level, alpha)

[dataset time] render/html/sheets/form.py + assets.py + selector.py (CPU)
    handwriting.yaml ──► selector chọn asset ──► composite vào form
    ground_truth ghi đúng text; boxes đo từ vị trí composite
```

`selector.py` là điểm quan trọng nhất — quyết định lấy asset nào:

```yaml
handwriting:
  field: borrower_name
  style: cursive
  writer: writer_017
  length: short
```

Rủi ro còn lại: WriteViT sinh theo dòng, chữ ký ngắn có thể kém ổn định → giảm trọng số trường chữ ký ở phase P5.

## 8. LLM là Content Provider

```
Document family → Content intent → LLM / Corpus → Structured content → Validator → Builder → HTML
```

LLM **không bao giờ trả HTML trực tiếp**. Chỉ sinh JSON theo schema:

```json
{
  "document_type": "loan_agreement",
  "borrower_name": "...",
  "loan_amount": "...",
  "terms": [...],
  "notes": [...]
}
```

Layout hoàn toàn do engine quyết định. `spec/content/validators/` kiểm tra trước khi vào builder → tránh LLM phá layout.

## 9. Recipe.json — mỗi sample ghi đầy đủ nguồn gốc

```json
{
  "seed": 183729,
  "family": "filled_form",
  "layout": "insurance_form_03",
  "content":    {"provider": "llm", "language": "vi"},
  "handwriting": {"enabled": true, "writer": "writer_017"},
  "artifacts":   {"stamp": true, "signature": true},
  "environment": {"camera": "phone_02", "perspective": 0.12, "lighting": "uneven"},
  "augmentation": {"resolution": 0.35, "blur": 0.15, "texture": 0.20}
}
```

Khi model OCR fail trên `sample_91823`, biết chính xác cách sample được sinh — phục vụ experiment/debug.

## 10. C1–C4 → distribution metaphor

C1–C4 **không phải domain model** và **không biến mất**: chúng là distribution/risk profile.

```yaml
distribution:
  layout:       {nested_table: 0.20, multi_level: 0.15}
  visual:       {low_resolution: 0.25, blur: 0.15}
  handwriting:  {mixed: 0.30}
  environment:  {camera_capture: 0.40}
```

## 11. Family manifest & template registry (không hard-code)

Family manifest → template identifier → **generic template registry** → HTML component composition. Nghiêm cấm `if family == "loan": ...`.

```yaml
# spec/families/loan/manifest.yaml
id: loan
label: "Tờ vay, khế ước vay"
page: a4
sections: [header, parties, loan, terms, signatures]
template: loan
requires: [borrower, lender]
```

## 12. Ánh xạ cũ → mới

| Cũ | Mới | Thay đổi |
|---|---|---|
| `rulebase/rules/` | `spec/attributes/` | + artifact, environment, pattern, handwriting |
| `rulebase/layouts/` | `spec/families/<họ>/` (dần dần) | gom theo họ |
| `rulebase/corpus/` | `spec/content/providers/corpus.py` + `spec/corpus/` | content provider hóa |
| `rulebase/content.py` | `spec/builder.py` | mở rộng model |
| `rulebase/spec.py` | `spec/sampler.py` | + dependency graph |
| `rulebase/layout.py` | **xóa** | bỏ grid |
| `generators/html/` | `render/html/` | promoted primary |
| `generators/genalog/` | `render/weasy/` | strip → WeasyPrint thuần |
| `generators/synthdog/` | `patterns/synthdog/` | chỉ sinh asset |
| `textures/paper\|ornament` | `patterns/paper\|ornaments` | gộp |
| `degradation/` | `augment/` | giữ |
| — | `environment/` | MỚI |
| — | `spec/annotation/` | MỚI |
| — | `spec/content/providers/llm.py` | MỚI |
| — | `spec/attributes/artifact.yaml` | MỚI |
| — | `spec/distribution/` | MỚI |
| `pipeline/`, `tools/`, `data/`, `tests/` | như cũ | chỉ sửa import/path |

## 13. Work packages (đã đổi thứ tự)

| Phase | Nội dung | Tiêu chí xong |
|---|---|---|
| **P0** | Branch `redesign/html-first` + `git mv` + sửa import + test + golden baseline. **KHÔNG đổi behavior** — chỉ move/rename/import | `before.png ≈ after.png` |
| **P1** | Spec + Distribution: `families/` + manifest, `sampler.py` dependency graph, `distribution/risk_profile.yaml`, `builder.py` hỗ trợ khối văn bản dài | `make check-families`, distribution báo đúng 11 attribute |
| **P2** | HTML-first: bỏ grid, hợp nhất CSS flow duy nhất, `make_content` là đường duy nhất, thermal qua `till.py`, cập nhật record/invariants/tests | golden baseline cho họ hiện có |
| **P3** | Pattern/Artifact: strip genalog → `render/weasy/`; synthdog → `patterns/`; thêm `artifact.yaml` + `pattern.yaml`; HTML composite nền/watermark/stamp | `make patterns`, artifact composite không đổi bbox text |
| **P4** | Annotation: `spec/annotation/` + đo bbox theo hierarchy từ DOM | annotation hierarchy test cho từng họ |
| **P5** | Handwriting: WriteViT → `patterns/handwriting/` + họ `filled_form/` + `form.py` sheet + selector | `make handwriting`, filled_form dataset |
| **P6** | Environment: `environment.yaml` + `environment/` camera/lighting/scene/paper | capture-condition test |
| **P7** | New families (chữ máy): `loan/`, `payment_voucher/`, `certificate/` | dataset + proof mỗi họ |
| **P8** | Benchmark: pipeline/dataset/docs/CI + `make proof` + Recipe.json đầy đủ | báo cáo OCR theo distribution profile |

## 14. Kết luận

Với kiến trúc trên, engine đi từ **clean invoice → structured form → handwritten form → stamp/signature → camera-captured document → degraded OCR hard case** mà không cần tạo generator riêng cho từng loại document — dấu hiệu đạt mục tiêu "general-purpose synthetic OCR engine".