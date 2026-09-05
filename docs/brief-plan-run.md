# Brief: `tools/plan_run.py` — LLM viết `pipeline.yaml` từ số đo

> Tài liệu này viết cho **một agent nhận việc P1**. Nó ghi đủ để bắt tay vào làm
> mà không phải hỏi lại: schema đầu vào đã đo, hình dạng đầu ra, lời gọi API
> chính xác, cái gì bị cấm, và checklist nghiệm thu.
>
> Cùng khuôn với [`brief-engine-html.md`](brief-engine-html.md).
> Bối cảnh: [`ke-hoach.md` §P1](ke-hoach.md#p1--toolsplan_runpy--llm-viết-pipelineyaml).

---

## 1. Việc là gì, một câu

Đọc `ocr_report.json` + `drift.json` + phân phối luật, cộng một **mục tiêu bằng
lời**, rồi sinh ra một `pipeline.yaml` **hợp lệ, kèm lý do cho từng con số** —
đặt vào `proposals/`, để người chép sang.

**Ranh giới, và nó là lý do việc này rẻ và an toàn:**

| | |
| --- | --- |
| **Được sửa** | `tools/plan_run.py` (mới) · `tests/test_plan_run.py` (mới) · `tasks.py` (một task) · `Makefile` (một dòng) · `.gitignore` (một dòng cho `proposals/`) |
| **KHÔNG được sửa** | bất cứ gì trong `pipeline/`, `rulebase/`, `generators/`, `degradation/` |
| **KHÔNG được ghi ra** | `pipeline.yaml` ở gốc kho — **không bao giờ**, kể cả có cờ |

Việc này là file **đầu tiên trong kho gọi ra mạng**. README hiện viết *"Nothing
calls a network service."* Câu đó nói về **đường render**, và vẫn phải đúng sau
khi xong việc này — xem §10.

---

## 2. Vì sao việc này an toàn: cổng đã có sẵn

Không phải xây gì để bảo vệ. `pipeline/config.py` **đã** làm hai việc:

* **Khoá lạ thì raise.** `_reject_unknown` với `TOP_KEYS`, `RUN_KEYS`,
  `SHARD_KEYS`, `QUALITY_KEYS`.
* **Mọi override phải phân giải được.** `apply_overrides` bắt đường dẫn đúng
  dạng `attribute.value_id.field`, bắt attribute có thật, bắt value_id có thật,
  và **chỉ cho sửa `weight` / `tags` / `requires` / `excludes`**.

**Xác thực bằng cách gọi chính hàm đó, không viết lại luật của nó.** Viết lại
là tạo ra bản sao thứ hai sẽ lệch.

```python
from pipeline.config import Config, ConfigError, apply_overrides
from rulebase.spec import load_rules

# đúng: để chính cỗ máy nói có hợp lệ không
apply_overrides(load_rules(), proposed["overrides"])   # raise ConfigError nếu sai
Config.load(written_path)                              # raise ConfigError nếu sai
```

---

## 3. Đầu vào — schema thật, đã đo

### 3.1 `ocr_report.json`

Có sẵn ở `data/dataset60/proof/ocr_report.json` và `data/dataset60_clean/proof/`.

```
top-level:  {"summary": {...}, "images": [...]}     ← LUÔN đọc ["summary"]

summary:
  by_layout               dict, 14 mục   {"eatery_ascii": {"images": 6, "token_recall": 0.5924}}
  by_layout_augmentation  dict, 20 mục   {"eatery_ascii/medium": {"images": 3, "token_recall": 0.5747}}
  by_augmentation         dict,  8 mục
  by_visual               dict
  frameworks              dict,  3 mục   {"synthdog": {"images": 20, "token_recall": 0.4537,
                                          "token_recall_folded":…, "field_hit_rate":…,
                                          "field_hit_rate_folded":…}}
  conditions              dict,  6 mục   {"layouts": [...], ...}
  distinct_labels · pairing · engine · lang · psm · against
```

`images[]` — 60 mục, mỗi mục có `layout` · `framework` · `augmentation` ·
`visual` · `token_recall` · `field_hit_rate` · `money_exact` · `money_total` ·
`fields` · `worst_fields`.

**Đừng nhét cả `images[]` vào prompt** — 60 ảnh là hàng nghìn token và phần lớn
vô ích. Gộp lại:

```python
from collections import Counter
worst = Counter(w["role"] for i in report["images"] for w in i.get("worst_fields", []))
worst.most_common(15)
# đã chạy trên data/dataset60: [('store.phone', 39), ('menu[0].price', 32),
#                               ('menu[1].price', 21), ('store.name', 17), ...]
```

`store.phone` đứng đầu với 39/60 ảnh là một tín hiệu thật và cụ thể — đúng loại
thứ đáng đưa vào brief.

### 3.2 `drift.json`

`pipeline/drift.py` ghi ra tại `<run>/drift.json` (hằng `VECTOR`). **Chưa có
file nào commit trong kho** — nên công cụ phải chạy được **khi thiếu nó**, và
nói rõ là thiếu, chứ không im lặng bỏ qua một nửa bằng chứng.

Hình dạng (từ `shard_vector`): `backend` · `images` · `draws` · `layouts`
(Counter) · `attributes` (dict tên thuộc tính → Counter giá trị) · và các trục
đo khác.

### 3.3 Phân phối luật

Gọi hàm, đừng parse stdout:

```python
from rules_report import sample_distribution      # tools/ đã ở sys.path
per_attribute, per_group, ok = sample_distribution(draws=2000, seed=7)
```

### 3.4 Trọng số hiện hành

```python
from rulebase.spec import load_rules
rules = load_rules()      # {attribute: [Option, ...]}, Option.weight / .id / .tags
```

---

## 4. Đầu ra

```
proposals/run-<YYYYMMDD-HHMMSS>/
├── pipeline.yaml     bản đề xuất — CHƯA phải file thật
├── reasoning.md      lượt 1, nguyên văn: tác nhân NGHĨ gì
└── inputs.json       đã đọc những file nào, hash của mỗi cái
```

`inputs.json` không phải trang trí: một đề xuất tái lập được là một đề xuất cãi
lại được. Ghi đường dẫn + sha256 của từng file đầu vào, tên model, và hash của
prompt.

Thêm một dòng vào `.gitignore`: `proposals/`. Đây là bản nháp, không phải kho.

---

## 5. Kiến trúc: hai lượt, và **YAML do Python sinh**

```
số đo  ─▶  LƯỢT 1  suy luận tự do, KHÔNG ràng buộc định dạng   ─▶  reasoning.md
                        │
                        ▼
           LƯỢT 2  ràng buộc JSON schema  ─▶  dict Python
                        │
                        ▼
           yaml.safe_dump  ─▶  pipeline.yaml   ← PYTHON viết YAML, không phải model
```

**Ba quyết định, mỗi cái một lý do:**

1. **Lượt 1 không ép định dạng.** Ràng buộc định dạng làm **giảm** chất lượng
   suy luận. Lượt một là chỗ cần chất lượng: *"bố cục nào yếu — yếu vì bố cục,
   hay vì nó rơi trúng mix làm cũ nặng?"* Hai chẩn đoán đó dẫn tới hai kế hoạch
   ngược nhau.
2. **Lượt 2 xin JSON, không xin YAML.** JSON ràng buộc được bằng
   `output_config.format`; YAML thì không. Một chuỗi YAML do model viết có thể
   sai tinh vi (thụt lề, `:` trong chuỗi không quote, `on`/`no` thành boolean).
   Nhận JSON đã được máy chủ ép đúng schema, rồi **Python `yaml.safe_dump`** —
   YAML không thể hỏng.
3. **Lý do là một trường trong schema**, không phải comment model tự viết.
   `overrides: [{path, value, reason}]` — rồi Python biến `reason` thành comment
   khi ghi. Bắt buộc bằng schema thì không quên được.

### Schema của lượt 2

```python
from pydantic import BaseModel, Field

class Override(BaseModel):
    path: str    = Field(description="attribute.value_id.field — vd augmentation.heavy.weight")
    value: float
    reason: str  = Field(description="một câu: vì sao con số này, dẫn ra số đo nào")

class Proposal(BaseModel):
    per_backend: int
    backends: list[str]
    layouts: list[str]          # rỗng = mọi bố cục; xem bẫy §11
    shard_size: int
    drift_tolerance: float
    overrides: list[Override]
    summary: str                # 2-3 câu, vào đầu pipeline.yaml làm comment
```

**Chú ý những gì KHÔNG có trong schema:** `seed`, `pairing`, `out`. Model không
được đụng vào ba khoá đó — §11.

---

## 6. Lời gọi API, chính xác

SDK Python chính thức (`pip install anthropic`), model `claude-opus-5`.

```python
def _client():
    """Import muộn: CI chỉ cài pytest và pyyaml, và tests không được chạm mạng."""
    try:
        import anthropic
    except ImportError:
        raise SystemExit(
            "tools/plan_run.py cần gói `anthropic`: pip install anthropic\n"
            "Đây là công cụ soạn kế hoạch, không phải một phần của đường render —\n"
            "không renderer nào import nó."
        )
    return anthropic.Anthropic()      # tự phân giải ANTHROPIC_API_KEY / hồ sơ ant auth
```

**Lượt 1 — suy luận tự do:**

```python
first = client.messages.create(
    model="claude-opus-5",
    max_tokens=16000,
    system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
    output_config={"effort": "high"},
    messages=[{"role": "user", "content": brief}],   # brief = §7
)
reasoning = "".join(b.text for b in first.content if b.type == "text")
```

`thinking` **không cần khai**: trên Opus 5 thinking bật sẵn ở chế độ adaptive.
Đừng truyền `budget_tokens` — Opus 5 trả 400.

**Lượt 2 — ràng buộc schema:**

```python
second = client.messages.parse(
    model="claude-opus-5",
    max_tokens=16000,
    system=[{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
    messages=[
        {"role": "user", "content": brief},
        {"role": "assistant", "content": reasoning},
        {"role": "user", "content": "Giờ xuất ra kế hoạch theo đúng lược đồ."},
    ],
    output_format=Proposal,        # lớp Pydantic — helper của SDK
)
proposal: Proposal = second.parsed_output
```

`messages.parse(output_format=...)` là helper Pydantic; `messages.create(
output_config={"format": {...}})` là dạng schema thô. **Đừng trộn hai cái.**

**Cache.** `SYSTEM` cộng khối luật là phần ổn định và được đặt trước; mục tiêu
và số đo đi sau. Cache chỉ trả công khi có nhiều lượt (lượt 2, và các vòng sửa
nếu thêm sau) — tiền tố phải trên ~1024 token mới cache được. Kiểm bằng
`response.usage.cache_read_input_tokens`; bằng 0 ở lượt 2 nghĩa là có thứ gì đó
đang làm hỏng tiền tố (thường là timestamp hoặc `json.dumps` không `sort_keys`).

**Bắt lỗi theo chuỗi, từ hẹp tới rộng** — một `except APIStatusError` gộp hết
sẽ xoá mất phân biệt giữa lỗi thử lại được và lỗi không:

```python
except anthropic.NotFoundError:      ...   # model sai
except anthropic.RateLimitError:     ...   # SDK đã tự thử lại 2 lần
except anthropic.APIStatusError as e: ...  # e.status_code >= 500 thì thử lại
except anthropic.APIConnectionError: ...   # mạng
```

`stop_reason == "refusal"` phải kiểm **trước khi** đọc `content`.

---

## 7. `brief` — cái đưa cho model

Một hàm **thuần**, không mạng, để test được:

```python
def build_brief(goal: str, report: dict, drift: dict | None,
                distribution: dict, rules: dict) -> str:
```

Phải chứa, theo thứ tự:

1. **Mục tiêu** người dùng, nguyên văn.
2. **Điểm theo bố cục**, xếp từ tệ tới tốt, kèm số ảnh.
   Ví dụ thật: `market_barcode 0,234 (3 ảnh)` … `invoice_brand 0,924 (6 ảnh)` —
   chênh **4×**.
3. **Điểm theo (bố cục × mức làm cũ)** — đây là bảng **bắt buộc**, vì nó là thứ
   duy nhất tách được *"bố cục khó"* khỏi *"bố cục này rơi trúng mix nặng"*.
   Nói thẳng trong prompt rằng phải dùng nó để phân biệt hai chuyện.
4. **Điểm theo renderer** — 3 dòng.
5. **15 `role` tệ nhất**, gộp từ `worst_fields`.
6. **Mix hiện tại** từ `sample_distribution` — theo thuộc tính và theo họ.
7. **Trọng số hiện hành**, chỉ những thuộc tính đáng đổi:
   `augmentation`, `visual`, `layout`, `content`.
8. **Danh sách bố cục hợp lệ** và **giá trị hợp lệ của từng thuộc tính** — model
   không được bịa `market_barcodes`.
9. **Nhắc luật trọng số:** *"weight là trọng số tương đối trong tập ứng viên
   CÒN LẠI SAU KHI LỌC, không phải xác suất. Tăng weight của một giá trị
   `requires` thẻ hiếm thì gần như không đổi gì."* Không nói thì model sẽ suy
   luận như thể đó là xác suất.
10. **Thiếu gì thì nói ra.** Không có `drift.json` thì viết
    `"drift.json: KHÔNG CÓ — không đánh giá được trôi phân phối"`, đừng lặng lẽ
    bỏ mục đó.

`SYSTEM` (ổn định, được cache) chứa: vai trò, ranh giới ba khoá cấm (§11), luật
trọng số, và yêu cầu mỗi override phải có một câu lý do dẫn ra số đo cụ thể.

---

## 8. Xác thực trước khi ghi

Theo đúng thứ tự này. **Không ghi file nào cho tới khi cả bốn bước xanh.**

```python
# 1. mọi override phân giải được — gọi chính cỗ máy, không viết lại luật
apply_overrides(load_rules(), {o.path: o.value for o in proposal.overrides})

# 2. mọi bố cục được nêu đều có thật
unknown = set(proposal.layouts) - set(rulebase.available_layouts())

# 3. mọi backend được nêu đều có thật (nay chỉ còn `html`)

# 4. dựng dict đầy đủ (seed/pairing/out do CÔNG CỤ đặt), safe_dump, rồi
#    Config.load() lên chính file vừa ghi ra
Config.load(out_dir / "pipeline.yaml")
```

Bước 4 là bước quyết định: nếu `Config.load()` nhận, thì `make run` cũng nhận.
Đừng tự đoán thay nó.

`apply_overrides` đã cho thông báo có địa chỉ — **đã chạy thử cả bốn kiểu sai**:

```
augmentation.no_such.weight    → ConfigError: names augmentation/'no_such', which does not exist
visual.laser_sharp.font_size   → ConfigError: sets 'font_size'  (chỉ weight/tags/requires/excludes)
nosuch.x.weight                → ConfigError: names attribute 'nosuch', which does not exist
augmentation.heavy             → ConfigError: should be 'attribute.value_id.field'
```

Bắt `ConfigError`, in nguyên văn, thêm danh sách giá trị hợp lệ, rồi thoát khác 0. Không tự sửa hộ model, không im lặng bỏ mục sai — vòng tự sửa là
việc của P5, không phải của P1.

---

## 9. CLI và task

```bash
python tools/plan_run.py \
    --goal "cần 5000 ảnh nghiêng về chỗ model đang yếu" \
    --report data/dataset60/proof/ocr_report.json \
    [--drift data/run01/drift.json] \
    [--out-dir proposals] \
    [--seed 2026] \
    [--dry-run]              # in brief rồi dừng, KHÔNG gọi mạng
```

`--dry-run` là bắt buộc, không phải tuỳ chọn: nó là cách một người xem prompt
trước khi tiêu tiền, và là cách test kiểm `build_brief` mà không chạm mạng.

`tasks.py`, theo đúng khuôn `monitor`:

```python
@task("plan-run", "LLM đọc số đo rồi đề xuất một pipeline.yaml")
def plan_run(args) -> None:
    command = [first_available_python(), REPO_ROOT / "tools" / "plan_run.py",
               "--goal", args.goal, "--report", args.report]
    run(command)
```

`tasks.py` **chỉ dùng thư viện chuẩn** — nó chạy trên system Python trước khi
có venv nào. Nên nó **gọi** `plan_run.py` bằng subprocess, **không import**.

---

## 10. Kiến trúc: giữ mạng ra khỏi lõi

Đây là file đầu tiên trong kho gọi ra mạng. Hai việc phải làm để câu *"Nothing
calls a network service"* vẫn đúng ở chỗ nó cần đúng:

1. **`import anthropic` phải muộn**, trong hàm, không ở đầu file. CI job `tests`
   chỉ cài `pytest` và `pyyaml`; một import ở đầu file làm đỏ CI, và làm
   `tests/test_plan_run.py` không chạy được ở máy không có gói.
2. **Thêm một test giữ ranh giới** (đề xuất trong
   [`duong-ong.md` §9](duong-ong.md#9-tóm-tắt-để-dán-lên-tường)):

```python
def test_no_network_client_reaches_the_deterministic_core():
    """Không file nào trong rulebase/, generators/, degradation/, pipeline/
    được import anthropic hay bất kỳ client HTTP nào."""
```

Test này đáng giá hơn một đoạn văn trong CONTRIBUTING, vì nó không phai.

---

## 11. Cấm — và vì sao

| cấm | vì sao |
| --- | --- |
| **Ghi ra `pipeline.yaml` ở gốc** | file đó là quyết định của người. Công cụ đề xuất, người chép |
| **Model đặt `run.seed`** | đổi seed là đổi bộ dữ liệu; không so được với bộ cũ |
| **Model đặt `run.pairing`** | `paired` là điều làm việc so ba renderer có nghĩa. Muốn đổi thì người truyền `--pairing`, và công cụ ghi lý do vào `inputs.json` |
| **Model đặt `run.out`** | thư mục ra là chuyện vận hành, không phải chuyện chiến lược |
| **Để model xuất YAML dạng chuỗi** | không ràng buộc được, hỏng tinh vi. Xin JSON, `safe_dump` bằng Python |
| **Viết lại luật của `apply_overrides`** | bản sao thứ hai sẽ lệch. Gọi hàm thật |
| **Tự sửa hộ khi model sai** | vòng tự sửa là P5. P1 báo lỗi rồi dừng |
| **Nhét cả `images[]` vào prompt** | hàng nghìn token, phần lớn vô ích. Gộp `worst_fields` lại |

---

## 12. Bẫy đã biết trước

**`layouts: []` nghĩa là "mọi bố cục".** Đúng cho một dataset, **sai** cho một
so sánh cố định: quota đi theo **thứ tự danh sách**, nên bộ hôm nay khác bộ
ngày mai nếu có ai thêm bố cục. Nếu mục tiêu có chữ "so sánh" / "đối chứng" /
"baseline", model **phải** liệt kê tên. Viết điều này vào `SYSTEM`.

**`weight` không phải xác suất.** Nếu không nhắc, model sẽ đề xuất
`layout.market_barcode.weight: 0.4` tưởng là "40% ảnh" — trong khi nó là trọng
số tương đối sau khi lọc, và `market_barcode` có `requires: [has_barcode]`.
Nhắc trong `SYSTEM`, **và** đưa mix thật từ `sample_distribution` vào brief để
model thấy khoảng cách giữa trọng số và kết quả.

**Prompt một mình không phải là ràng buộc.** Model *sẽ* thử đặt `seed` hoặc
`pairing`. Chặn bằng **schema** (không có trường đó) **và** kiểm lại sau khi
sinh. Hai lớp, vì mỗi lớp một mình đều đã từng thủng.

**`ocr_report.json` là `{"summary":…, "images":…}`.** Đọc thẳng `by_layout` ở
cấp cao nhất sẽ ra `None`, và một `None` lặng lẽ thành brief rỗng thành đề xuất
vô nghĩa. Kiểm `"summary" in report` và raise nếu không.

**`drift.json` chưa có file nào trong kho.** Chạy phải được khi thiếu, và nói ra.

---

## 13. Test phải viết — `tests/test_plan_run.py`

Không test nào được chạm mạng. Điều đó ép một ràng buộc kiến trúc có ích: **lời
gọi API nằm gọn trong một hàm; mọi thứ khác là hàm thuần.**

| test | khẳng định |
| --- | --- |
| `test_the_brief_names_every_layout_the_report_scored` | mọi khoá của `by_layout` xuất hiện trong `build_brief` |
| `test_the_brief_says_when_drift_is_missing` | `drift=None` → brief chứa chữ "KHÔNG CÓ", không im lặng bỏ mục |
| `test_the_brief_explains_that_weight_is_not_a_probability` | brief/`SYSTEM` có câu nhắc luật trọng số |
| `test_an_override_naming_a_missing_value_is_refused` | đề xuất giả có `augmentation.no_such.weight` → `ConfigError`, và **tên sai có trong thông báo** |
| `test_an_override_setting_a_forbidden_field_is_refused` | `visual.laser_sharp.font_size` → từ chối (chỉ `weight/tags/requires/excludes`) |
| `test_seed_and_pairing_come_from_the_tool` | đề xuất giả có `seed` → file ghi ra vẫn dùng seed của công cụ |
| `test_the_written_yaml_round_trips` | `safe_load(safe_dump(d)) == d` |
| `test_every_override_carries_a_reason` | override thiếu `reason` → từ chối |
| `test_the_tool_never_targets_the_repo_pipeline_yaml` | mọi đường dẫn ra đều nằm dưới `proposals/` |
| `test_no_network_client_reaches_the_deterministic_core` | §10 |

Dữ liệu test: dùng **`data/dataset60/proof/ocr_report.json` thật**, đã commit
sẵn. Đừng bịa một report giả — một report giả sẽ không có hình dạng thật.

---

## 14. Checklist nghiệm thu

- [ ] `python tools/plan_run.py --goal "..." --report data/dataset60/proof/ocr_report.json --dry-run` in ra brief, **không gọi mạng**
- [ ] Chạy thật ra `proposals/run-<ts>/` gồm ba file
- [ ] `Config.load()` trên `pipeline.yaml` vừa sinh: **xanh**
- [ ] **Mỗi mục `overrides:` có một dòng comment nói vì sao**, dẫn ra một số đo
- [ ] Một override trỏ vào thứ không có → **báo trước khi ghi**, exit ≠ 0, thông báo có tên sai + danh sách hợp lệ
- [ ] Đề xuất chứa `seed`/`pairing` → bị bỏ qua, và ghi lại là đã bỏ qua
- [ ] `pipeline.yaml` ở gốc **không đổi một byte** (`git diff --exit-code pipeline.yaml`)
- [ ] `python -m pytest tests/test_plan_run.py` xanh **khi không cài `anthropic`**
- [ ] `python tasks.py check` · `python tasks.py lint` xanh
- [ ] `.gitignore` có `proposals/`
- [ ] `README.md` §Tasks có `plan-run`

---

## 15. Ví dụ một lần chạy đúng

Mục tiêu: *"cần 5000 ảnh nghiêng về chỗ model đang yếu"*.

Lượt 1 nên đi tới một kết luận **có phân biệt**, đại loại:

> `market_barcode` 0,234 và `invoice_export` 0,296 là hai bố cục thấp nhất, so
> với `invoice_brand` 0,924 — chênh gần bốn lần. Nhưng `by_layout_augmentation`
> cho thấy `market_barcode` chỉ xuất hiện ở `medium` và `heavy`, còn
> `invoice_brand` phần lớn ở `real_paper`. Nên một phần khoảng cách là **mix
> làm cũ**, không phải bố cục. Đề xuất tách hai chuyện: nâng trọng số hai bố
> cục ấy *và* đồng thời hạ `heavy` một chút, rồi đo lại — nếu khoảng cách co
> lại thì nguyên nhân là mix.

`pipeline.yaml` ra sẽ trông như:

```yaml
# Nghiêng về market_barcode và invoice_export (hai bố cục thấp nhất, 0,234 và
# 0,296 so với 0,924 của invoice_brand). Đồng thời hạ `heavy` để tách "bố cục
# khó" khỏi "mix làm cũ nặng" — by_layout_augmentation cho thấy hai bố cục ấy
# hầu như chỉ xuất hiện ở medium/heavy.
run:
  out: data/run-weak-layouts
  per_backend: 1667
  seed: 2026          # do công cụ đặt, không phải model
  workers: auto
  pairing: paired     # do công cụ đặt
  layouts: [market_barcode, invoice_export, invoice_vat_form, invoice_brand]
backends: [html]        # bản gốc của brief này khai cả ba; hai kia đã xoá
shard: {size: 100}
overrides:
  # market_barcode 0,234 — thấp nhất trong 14 bố cục, chỉ 3 ảnh trong bộ đo
  layout.market_barcode.weight: 6
  # invoice_export 0,296 — thứ nhì từ dưới lên, 6 ảnh
  layout.invoice_export.weight: 5
  # hạ heavy để tách nguyên nhân; by_layout_augmentation cho thấy hai bố cục
  # trên tập trung ở medium/heavy
  augmentation.heavy.weight: 1
quality: {drift_tolerance: 0.15, sample_for_ocr: 500}
```

Ba comment, ba số đo. Đó là chuẩn đạt.

---

## Liên quan

| | |
| --- | --- |
| [`ke-hoach.md` §P1](ke-hoach.md#p1--toolsplan_runpy--llm-viết-pipelineyaml) | bối cảnh và vị trí trong lộ trình |
| [`tu-dong-hoa-bang-llm.md` §10 A4](tu-dong-hoa-bang-llm.md) · [Phụ lục C](tu-dong-hoa-bang-llm.md#phụ-lục-c--kinh-tế-đặt-llm-ở-đâu-thì-rẻ) | thiết kế tác nhân lập kế hoạch, và vì sao nó rẻ |
| [`duong-ong.md` §2](duong-ong.md#2-hai-mặt-phẳng) | ranh giới author-time / render-time mà việc này phải giữ |
| [`pipeline/config.py`](../pipeline/config.py) | `Config.load` · `apply_overrides` · các tập khoá hợp lệ |
| [`pipeline.yaml`](../pipeline.yaml) | mẫu để bắt chước — kể cả mật độ chú thích |
| [`brief-engine-html.md`](brief-engine-html.md) | brief trước, cùng khuôn |
