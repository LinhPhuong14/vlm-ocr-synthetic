# Redesign plan — `vlm-ocr-synthetic` (v3, HTML-first)

> Status: **approved direction**, design updated per v3 review (7 technical locks). Ready for P0.
> Pipeline execution order: P0 → P8 as §13. Plan document is the source of truth for the planner agent.
> Must-have before planner execute: generic component registry (§11), annotation tree from DocumentModel (§4), environment transform contract (§5), conditional distribution (§10).

---

## 0. Mục tiêu

Biến repo thành một **general-purpose synthetic OCR/VLM document engine**: một rule/spec chung, một renderer HTML duy nhất, các asset factory độc lập (pattern, artifact, handwriting), và annotation hierarchy bậc thang là capability hạng nhất.

```
Spec → Distribution → Sampler → Content Provider → Builder → DocumentModel
     → Generic HTML Components → HTML/CSS → Chromium
     → Pattern/Artifact composite → Environment → Augmentation
     → Image + Hierarchical Annotation + GT + Recipe
```

Thay vì:
- 3 renderer chia sẻ character-grid (cũ), chỉ **một** renderer HTML.
- Document type là logic nằm trong code renderer (cũ), trở thành **data/configuration**.
- Corpus là nguồn content duy nhất (cũ), trở thành một trong các **content providers** (corpus / LLM).
- 1 document family = 1 Python template (cũ), trở thành **Family → Layout Spec → Generic Components → HTML** (§11).

## 1. Các quyết định đã chốt

| # | Quyết định | Hệ quả |
|---|---|---|
| 1 | **HTML-first** — Chromium là primary renderer duy nhất | Bỏ renderer glyph + character-grid hoàn toàn; thermal cũng chuyển CSS flow |
| 2 | **Strip genalog** — WeasyPrint chỉ là secondary PDF renderer | `render/weasy/` wrapper mỏng, dùng chung markup với HTML |
| 3 | **WriteViT** dùng làm **handwriting asset provider**, không chạy trong dataset loop | pre-gen library PNG, render chỉ composite; CPU-only pipeline |
| 4 | **Bỏ character-grid** | `geometry.py` xóa; chỉ còn `make_content`; structure đo từ cells |
| 5 | **Annotation hierarchy là first-class capability** | Annotation tree được **tạo từ DocumentModel**, không suy luận từ HTML sau render (§4) |
| 6 | **Environment tách khỏi augmentation** | Environment = capture condition; Augmentation = image degradation. Environment có transform contract riêng (§5) |
| 7 | **Artifact tách khỏi ornament** | Artifact = semantic document marks (có bbox riêng, §6); Ornament = decorative elements |
| 8 | **LLM là Content Provider, không phải Renderer** | LLM → structured JSON → validator → builder → HTML; không bao giờ trả HTML trực tiếp. Mọi provider dùng chung interface (§9) |
| 9 | Giữ tên repo `vlm-ocr-synthetic` | không đổi branding |
| 10 | **Recipe.json** mỗi sample, ghi đầy đủ dependency chain | phục vụ experiment/debug: query theo factor gây fail (§12) |
| 11 | **Generic component registry**, không phải `family → Python template` | §11 — must-have |
| 12 | **Conditional distribution** | §10 — must-have |
| 13 | **Environment transform contract** (bbox/polygon) | §5 — must-have |
| 14 | **Annotation tree từ DocumentModel** | §4 — must-have |

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
│   ├── distribution/              # NEW: C1–C4 → distribution metaphor
│   │   ├── risk_profile.yaml      #     layout.nested_table, handwriting.mixed, …
│   │   └── conditional.yaml       #     NEW: conditional distribution (§10)
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
│   ├── components/                # NEW — generic component registry (§11)
│   │   ├── __init__.py            #     registry: name → component
│   │   ├── document_header.py     #     KHÔNG phải "loan.py"
│   │   ├── two_party_table.py
│   │   ├── amount_block.py
│   │   ├── numbered_paragraphs.py
│   │   ├── signature_grid.py
│   │   ├── items_table.py  totals_block.py  field_line.py  …
│   │   └── README.md
│   │
│   ├── annotation/                # NEW — first-class capability
│   │   ├── tree.py                #     Annotation tree từ DocumentModel (§4)
│   │   ├── hierarchy.yaml         #     page→section→block→paragraph→sentence→line→word→character
│   │   ├── labels.yaml            #     semantic labels (title, section_header, …)
│   │   ├── schema.yaml            #     CORD/PubTabNet-compatible schema
│   │   └── transform.py           #     NEW: transform contract cho bbox/polygon (§5)
│   │
│   ├── content/                   # NEW — content providers
│   │   ├── base.py                #     NEW: interface chung ContentProvider (§9)
│   │   ├── providers/
│   │   │   ├── corpus.py
│   │   │   └── llm.py             #     LLM → JSON schema → validator → StructuredContent
│   │   ├── constraints/           #     ràng buộc content (regex, tỷ lệ, định dạng tiền…)
│   │   ├── validators/            #     validate trước khi vào builder
│   │   └── schemas/               #     JSON schema cho từng loại content intent
│   │
│   ├── sampler.py                 # (was spec.py) weighted sampling + constraint graph + conditional
│   ├── builder.py                 # (was content.py build) StructuredContent → DocumentModel
│   └── text.py
│
├── render/
│   ├── html/                      # PRIMARY — Chromium/Playwright
│   │   ├── render.py              # CLI + worklist
│   │   ├── engine.py              # (was page.py) browser lifecycle, bbox extraction
│   │   ├── sheets/                # layout driver: family spec → component composition
│   │   │   ├── base.py            # component composition engine (§11)
│   │   │   ├── compose.py         #     manifest + layout spec → assembled HTML
│   │   │   └── grids/             #     chỉ còn các layout kiểu đặc biệt (thermal till)
│   │   └── assets.py              # composite patterns/ + artifacts/ + handwriting/
│   └── weasy/                     # SECONDARY — WeasyPrint thuần (strip genalog)
│       └── render.py              # reuse sheets.compose() + PyMuPDF rasterise
│
├── patterns/                      # asset factory (synthdog reborn + WriteViT)
│   ├── generate.py                # CLI: make patterns / make handwriting
│   ├── backgrounds/               # nền trang, watermark, guilloche
│   ├── paper/                     # texture giấy (was textures/paper)
│   ├── ornaments/                 # hoa văn trang trí (was textures/ornament)
│   ├── artifacts/                 # NEW — semantic marks (có bbox, §6)
│   │   ├── stamps/  seals/  signatures/  barcodes/
│   ├── handwriting/               # NEW — WriteViT asset provider
│   │   ├── writevit/              # vendored WriteViT (MIT) + vn_ckpt.pth
│   │   ├── providers/             # future: nhiều provider
│   │   ├── library/               # pre-gen output: paragraph/field/name/date/signature
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
│   ├── base.py                    #     NEW: transform contract (§5)
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

## 4. Annotation tree từ DocumentModel (must-have)

**Không suy luận sentence/word/character từ HTML sau render.** `getBoundingClientRect()` biết `<p>`, nhưng không tự biết đâu là sentence, word, character.

Pipeline đúng:

```
DocumentModel
      ↓
Annotation Tree      ← tạo ở đây, ngay khi content được quyết định
      ↓
HTML DOM             ← annotation-aware HTML, data-annotation mang theo
      ↓
Chromium bbox        ← chỉ đo bbox, không đoán annotation
```

`spec/annotation/tree.py` dựng cây annotation song song với DocumentModel, mỗi node mang `{kind, text, role}` theo `hierarchy.yaml`. HTML render ra **annotation-aware markup**:

```html
<p data-annotation="paragraph">
  <span data-annotation="sentence">
    <span data-annotation="word">Người</span>
    <span data-annotation="word">mua</span>
    …
  </span>
</p>
```

Chromium chỉ gán bbox vào các node đã có sẵn — annotation là nguồn được dựng trước, DOM là nơi đo. Cùng một chuỗi "Thông tin người mua" có thể đồng thời là `TITLE`, `TEXT`, `SECTION_HEADER`, `WORD`, `CHARACTER` tùy task — vì annotation tree có sẵn từ DocumentModel.

## 5. Environment transform contract (must-have)

DOM bbox được đo **trước** Environment. Camera perspective / paper warp / rotation / crop / scale sẽ làm bbox cũ sai. Mỗi environment operation phải khai báo:

```text
transform(image)
transform_bbox(bbox)
transform_polygon(polygon)
```

Pipeline:

```
DOM bbox
   ↓
Environment transform
   ↓
Transformed bbox
   ↓
Augmentation (không đổi geometry — giữ nguyên invariant hiện có)
   ↓
final annotation
```

`spec/annotation/transform.py` là nơi định nghĩa contract; `environment/base.py` implement. Thiết kế từ đầu theo polygon để sau này segmentation không phải viết lại.

## 6. Artifact là annotation object (không chỉ là PNG decoration)

Mỗi artifact composite lên trang phải có bbox riêng và đi vào annotation:

```json
{
  "type": "stamp",
  "bbox": [...],
  "z_index": 20,
  "overlap": ["text", "signature"],
  "semantic": "official_stamp"
}
```

Cover các case đã nêu: stamp đè text, stamp đè handwriting, signature overlap, barcode, checkbox, image trong table, seal crossing section boundary. Bbox artifact đi qua cùng transform contract (§5).

## 7. Handwriting — WriteViT là asset provider

**Không coi WriteViT là handwriting engine hoàn chỉnh.** Nó là một **Handwriting Asset Provider** trong số nhiều provider tương lai. Pipeline cần nhiều loại asset: paragraph, field, name, date, signature, initial, check mark.

```
[asset time] patterns/handwriting/generate.py (GPU, `make handwriting`)
    text + writer refs ──► WriteViT ──► library/<writer>/<type>/<hash>.png (line-level, alpha)

[dataset time] render/html/sheets/ + assets.py + selector.py (CPU)
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

Rủi ro còn lại: WriteViT sinh theo dòng, chữ ký ngắn có thể kém ổn định → giảm trọng số trường chữ ký ở phase P6.

## 8. LLM là Content Provider — interface chung

Mọi content provider dùng chung interface, để thêm provider mới không sửa builder:

```python
class ContentProvider:
    def generate(self, intent, constraints, seed) -> StructuredContent:
        ...
```

Hai implementation: `CorpusProvider`, `LLMProvider` — đều trả `StructuredContent`. Sau này thêm `TemplateProvider`, `DatabaseProvider`, `HumanProvider`, `SyntheticProvider` không đụng builder.

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

```
Corpus ──┐
         ├── StructuredContent → Validator → Builder
LLM ─────┘
```

## 9. Family → Layout Spec → Generic Components (must-have)

**Nghiêm cấm `family_id → Python family renderer`.** 1 family ≠ 1 template. Thay vào đó 3 tầng:

```
Family
  ↓
Layout Spec
  ↓
Generic Components
  ↓
HTML
```

Manifest khai báo **component composition**, không phải tên template riêng:

```yaml
# spec/families/loan/manifest.yaml
id: loan
label: "Tờ vay, khế ước vay"
page: a4
layout:
  sections:
    - header
    - parties
    - amount
    - terms
    - signatures
components:
  header: document_header
  parties: two_party_table
  amount: amount_block
  terms: numbered_paragraphs
  signatures: signature_grid
```

Renderer chỉ biết `document_header`, `two_party_table`, `amount_block`, `numbered_paragraphs`, `signature_grid` — **không cần biết "loan" là gì**. `spec/components/` là registry; `render/html/sheets/compose.py` là bộ lắp ráp. Khi có 20 invoice + 30 forms + 15 certificates + 50 administrative docs, renderer không phình to — chỉ thêm component mới khi thật sự mới.

## 10. Distribution & Conditional distribution (must-have)

C1–C4 không phải domain model, không biến mất — thành distribution/risk profile:

```yaml
distribution:
  layout:       {nested_table: 0.20, multi_level: 0.15}
  visual:       {low_resolution: 0.25, blur: 0.15}
  handwriting:  {mixed: 0.30}
  environment:  {camera_capture: 0.40}
```

**Không sample độc lập** các factor liên quan (nested_table × low_resolution khó hơn bình thường). Thêm conditional distribution:

```yaml
# spec/distribution/conditional.yaml
conditional:
  - when:
      layout: nested_table
    then:
      resolution:
        low: 0.45
  - when:
      handwriting: complex
    then:
      resolution:
        low: 0.40
      blur:
        medium: 0.30
```

Đây là nơi kiến thức về distribution + oversampling + conditional degradation được đưa trực tiếp vào engine — `sampler.py` đọc cả `risk_profile.yaml` lẫn `conditional.yaml`.

## 11. Ánh xạ cũ → mới

| Cũ | Mới | Thay đổi |
|---|---|---|
| `rulebase/rules/` | `spec/attributes/` | + artifact, environment, pattern, handwriting |
| `rulebase/layouts/` | `spec/families/<họ>/` (dần dần) | gom theo họ |
| `rulebase/corpus/` | `spec/content/providers/corpus.py` + `spec/corpus/` | content provider hóa |
| `rulebase/content.py` | `spec/builder.py` | mở rộng model |
| `rulebase/spec.py` | `spec/sampler.py` | + dependency graph + conditional |
| `rulebase/layout.py` | **xóa** | bỏ grid |
| `generators/html/` | `render/html/` | promoted primary |
| `generators/genalog/` | `render/weasy/` | strip → WeasyPrint thuần |
| `generators/synthdog/` | `patterns/synthdog/` | chỉ sinh asset |
| `textures/paper\|ornament` | `patterns/paper\|ornaments` | gộp |
| `degradation/` | `augment/` | giữ |
| — | `environment/` | MỚI |
| — | `spec/annotation/` (tree, transform) | MỚI |
| — | `spec/components/` (registry) | MỚI |
| — | `spec/content/base.py` + `providers/llm.py` | MỚI |
| — | `spec/distribution/conditional.yaml` | MỚI |
| — | `spec/attributes/artifact.yaml` | MỚI |
| `pipeline/`, `tools/`, `data/`, `tests/` | như cũ | chỉ sửa import/path |

## 12. Recipe.json — ghi đầy đủ dependency chain

```json
{
  "seed": 183729,
  "family": "filled_form",
  "distribution": {
    "profile": "real_world",
    "risk": {"nested_table": 0.20, "low_resolution": 0.35}
  },
  "content":    {"provider": "llm", "language": "vi", "content_seed": 1234},
  "layout":     {"family": "form", "variant": "insurance_03"},
  "visual":     {},
  "handwriting": {"enabled": true, "writer": "writer_017"},
  "artifact":   {"stamp": true, "signature": true},
  "pattern":    {},
  "environment": {"camera": "phone_02", "perspective": 0.12, "lighting": "uneven"},
  "augmentation": {"resolution": 0.35, "blur": 0.15, "texture": 0.20}
}
```

Khi OCR fail trên `sample_91823`, query được theo `failures → distribution → layout → content → visual → handwriting → artifact → environment → augmentation` để tìm **factor gây fail** — nền tảng cho synthetic-data experimentation.

## 13. Work packages (đã đổi thứ tự — Environment trước Annotation)

| Phase | Nội dung | Tiêu chí xong |
|---|---|---|
| **P0** | Branch `redesign/html-first` + `git mv` + sửa import + test + golden baseline. **KHÔNG đổi behavior** — chỉ move/rename/import | `before.png ≈ after.png` |
| **P1** | Spec + Distribution: `families/` + manifest, `sampler.py` dependency graph, `distribution/risk_profile.yaml` + `conditional.yaml`, `builder.py` hỗ trợ khối văn bản dài | `make check-families`, distribution báo đúng 11 attribute + conditional |
| **P2** | HTML-first: bỏ grid, hợp nhất CSS flow duy nhất, `make_content` là đường duy nhất, thermal qua CSS flow, cập nhật record/invariants/tests | golden baseline cho họ hiện có |
| **P3** | Pattern/Artifact: strip genalog → `render/weasy/`; synthdog → `patterns/`; thêm `artifact.yaml` + `pattern.yaml`; HTML composite nền/watermark/stamp | `make patterns`, artifact composite có bbox riêng, không đổi bbox text |
| **P4** | **Environment** (trước annotation finalization): `environment.yaml` + `environment/` camera/lighting/scene/paper + **transform contract** (`transform_bbox`/`transform_polygon`) + `annotation/transform.py` | bbox sau perspective/warp khớp ảnh cuối |
| **P5** | Annotation: `spec/annotation/tree.py` + hierarchy + annotation-aware HTML; đo bbox theo cây từ DocumentModel | annotation hierarchy test cho từng họ |
| **P6** | Handwriting: WriteViT → `patterns/handwriting/` + họ `filled_form/` + selector | `make handwriting`, filled_form dataset |
| **P7** | New families (chữ máy): `loan/`, `payment_voucher/`, `certificate/` — qua **component registry**, không thêm template riêng | dataset + proof mỗi họ, không có `if family ==` |
| **P8** | Benchmark: pipeline/dataset/docs/CI + `make proof` + Recipe.json đầy đủ dependency chain | báo cáo OCR theo distribution profile + conditional |

## 14. Kiến trúc cuối (đã khóa)

```
                    ┌─────────────────┐
                    │ Distribution    │
                    │ risk_profile +  │
                    │ conditional     │
                    └────────┬────────┘
                             ↓
                    ┌─────────────────┐
                    │    Sampler      │
                    └────────┬────────┘
                             ↓
        ┌────────────────────┴────────────────────┐
        ↓                                         ↓
 ┌──────────────┐                         ┌──────────────┐
 │ Corpus       │                         │ LLM          │
 │ Provider     │                         │ Provider     │
 └──────┬───────┘                         └──────┬───────┘
        └────────────────┬──────────────────────┘
                         ↓
                ┌──────────────────┐
                │ Content Validator│
                └────────┬─────────┘
                         ↓
                ┌──────────────────┐
                │ Document Builder │
                └────────┬─────────┘
                         ↓
        ┌────────────────┴────────────────┐
        ↓                                 ↓
 ┌──────────────┐                ┌──────────────────┐
 │Annotation    │                │ Generic HTML     │
 │Tree          │                │ Components       │
 └──────┬───────┘                └────────┬─────────┘
        │                                ↓
        └───────────────┬────────── HTML / Chromium
                        ↓
              ┌──────────┴──────────┐
              ↓                     ↓
        Pattern/Artifact      Handwriting
              └──────────┬──────────┘
                         ↓
                  Environment
                  (transform contract)
                         ↓
                  Augmentation
                         ↓
       ┌─────────────────┼─────────────────┐
       ↓                 ↓                 ↓
     Image          Annotation          Recipe
                         ↓
              page → section → block
                    → paragraph
                    → sentence
                    → line
                    → word
                    → character
```

## 15. Kết luận

Với kiến trúc trên, engine đi từ **clean invoice → structured form → handwritten form → stamp/signature → camera-captured document → degraded OCR hard case** mà không cần tạo generator riêng cho từng loại document. Mọi capability mới đi qua `spec → distribution → provider → component → asset → transform → annotation` — không có family/generator ad-hoc.