# 🤖 `agent/` — LLM chọn tham số thay cho seed

> Một lượt chạy mà **mô hình quyết định từng trang**: loại giấy, phôi bố cục,
> cách dựng lại phôi, mực, hoạ tiết, cách làm cũ — 5000 lần, mỗi lần ghi lại
> được và dựng lại được.

---

## 1. Vì sao không để `sample_recipe` bốc

`rulebase.sample_recipe` bốc **một** trang rất tốt: có trọng số, có ràng buộc,
và độc lập với trang trước. Chính chỗ "độc lập với trang trước" là chỗ một lượt
5000 ảnh không chịu nổi.

Bốc độc lập thì phần đuôi của không gian không bao giờ tới: những bộ ba
`document × layout × variant` hiếm nhất không xuất hiện lần nào, những bộ phổ
biến nhất xuất hiện hàng trăm lần, và **bộ dữ liệu hẹp hơn chính bộ luật đã
sinh ra nó**. Đo được: 400 lượt bốc độc lập (`pressure=0`) bỏ sót giá trị ở
nhiều thuộc tính; 400 lượt của agent (`pressure=0.72`) phủ hết — đó là
`test_coverage_beats_independent_draws_on_the_tail`.

Việc của agent là **nhớ nó đã vẽ những gì**.

---

## 2. Bảy trục để dựng lại một phôi

Một `layout` nói tờ giấy có cột nào. Một `variant` nói **nhà in đã làm gì với
phôi ấy**: tông giấy, nét kẻ, dải tiêu đề, sọc dòng, bộ chữ, độ nén dòng, và
hoạ tiết in kèm. Bảy trục ghép lại chứ không liệt kê sẵn, nên không gian rộng
hơn bất kỳ danh sách template viết tay nào:

| Trục | Hạng | Giá trị | Đổi cái gì |
| :--- | :--- | ---: | :--- |
| `stock` | livery | 6 | tông giấy — liên hồng, liên lục, giấy ngà |
| `rule` | livery | 6 | nét kẻ bảng: mảnh, đậm, nhạt, chỉ khung ngoài |
| `band` | livery | 6 | dải tiêu đề cột |
| `zebra` | livery | 3 | sọc dòng |
| `type` | free | 5 | bộ chữ: có chân, không chân, cột số kiểu máy in |
| `density` | free | 3 | độ nén dòng |
| `mark` | free | 8 | **hoạ tiết mới dựng bằng CSS** — vạch gáy, băng đỉnh, guilloche, răng cưa, nẹp góc, vệt chéo, lưới chân trang |

**648** cách phối chỉ-đổi-mực, **77 760** cách phối đầy đủ.

### Ranh giới không được vượt

Hộp nhãn đo từ DOM đã dàn xong, nên một luật CSS làm chữ **dịch chỗ** thì hộp
dịch theo và nhãn vẫn đúng. Có hai luật không như vậy, và đó là lý do kho biến
thể là danh sách được kiểm chứ không phải CSS tự do:

* `text-transform` — DOM giữ chuỗi gốc còn pixel hiện chuỗi khác, nên nhãn sẽ
  mô tả thứ tờ giấy không in.
* `content:` mang **chữ** — glyph không có hộp nào tả.

`sheets/variant.py::forbidden` kiểm lại từng chuỗi trước khi dán vào trang.
`content:''` **rỗng** thì được: đó là cách bật một pseudo-element trang trí, và
mọi hoạ tiết ở đây đều vẽ trên `::before`/`::after` với `z-index:-1` — ngoài
dòng chảy nên không đẩy chữ, dưới chữ nên không che nhãn.

---

## 3. Giấy nào được dựng lại, giấy nào không

Với phần lớn chứng từ, tự dựng lại bố cục là **đúng**: hai nhà in ra cùng một
tờ hoá đơn không bao giờ ra hai tờ giống nhau, và mô hình học trên một dáng duy
nhất sẽ học nhầm dáng ấy thành định nghĩa của loại giấy.

Nhưng có loại giấy mà **dáng chính là nội dung**. Bằng lái xe, giấy chứng nhận
nhà nước cấp, phôi biểu mẫu Bộ Tài chính ban hành — chúng có một dáng hợp lệ
duy nhất, và một bộ dữ liệu tự bịa ra dáng thứ hai sẽ dạy mô hình rằng tờ giả
cũng là tờ thật.

`agent/policy.yaml` chia ba hạng:

| Hạng | Được làm gì | Trong kho này |
| :--- | :--- | :--- |
| `locked` | **chỉ ornament** — không variant, không đổi nét, không đổi nền | `vat_invoice_form`, `hospital_bill` |
| `livery` | đổi mực và nền; hình học giữ nguyên | `export_invoice`, `utility_power`, `utility_water`, `tax_invoice_en`, `authorisation_letter` |
| `free` | đổi tất cả, và sinh thêm hoạ tiết mới | 10 chứng từ thương mại còn lại |

> Kho này **chưa có** phôi giấy tờ tuỳ thân nào. `locked` là chỗ chúng sẽ vào
> nếu được thêm.

**Chính bộ luật là bên chặn, không phải một câu `if` trong planner.** Mỗi
document được gắn thẻ `aug_locked` / `aug_livery` / `aug_free`, và mỗi variant
khai `requires`/`excludes` theo thẻ ấy:

```
none            không ràng buộc     mọi document đều bốc được
variant livery  excludes aug_locked  phôi nhà nước không với tới
variant free    requires aug_free    chỉ chứng từ thương mại
```

Nên `make check-rules` nhìn thấy chính sách, và một lỗi trong planner **không
thể** dựng lại một tờ giấy tờ nhà nước.

Bù lại: trang `locked`/`livery` bị đẩy mạnh ra khỏi giá trị "không hoạ tiết"
(`BARE_PENALTY`), vì đó là chỗ duy nhất chúng còn được đa dạng. Đo trên lượt
chạy: **99%** trang loại này mang con dấu hoặc hoa văn.

---

## 4. Agent quyết định thế nào

Đi theo đúng thứ tự bốc của bộ luật, mỗi thuộc tính chọn trong tập
`Option.allowed()` cho phép ứng với các thẻ đã gom — cùng một vòng
`_draw_once` đi. Nên **kế hoạch không thể chứa tổ hợp bộ luật cấm**, dù giá trị
đến từ mô hình hay từ mục tiêu phủ. `planner.verify()` bốc lại từng quyết định
qua `sample_recipe` để chứng minh điều đó trước khi mở trình duyệt.

Điểm của mỗi giá trị hợp lệ:

```
weight / (1 + số lần đã dùng) ** pressure
```

`pressure = 0` là đúng bộ bốc gốc; `pressure = 1` là gần như phủ đều; ở giữa
thì giữ được tính thật do người viết luật cân (`weight: 8` vẫn phổ biến) mà
vẫn đẩy lượt chạy đi qua các góc của không gian. **`pressure` là con số duy
nhất nói agent đang cố tới đâu.**

### Hai chế độ, ghi lại theo từng trang

| `by` | nghĩa là |
| :--- | :--- |
| `llm` | có server, và id nó trả về hợp lệ |
| `coverage` | không có server, hoặc id nó chọn cho thuộc tính đó không hợp lệ |

Nửa offline không phải cái chống cháy gắn thêm: nó **chính là mục tiêu mà
prompt yêu cầu mô hình**, viết thành công thức. Một lượt chạy âm thầm tụt hạng
mới là kết cục xấu; một lượt chạy ghi rõ từng trang do ai quyết thì không.

---

## 5. Chạy

```bash
# Không cần server — chế độ coverage
python tools/agent_dataset.py -o data/5k_llm -n 5000 --workers 3

# Có server (vLLM / SGLang / llama.cpp / Ollama — bất kỳ endpoint OpenAI nào)
vllm serve Qwen/Qwen3.5-9B --port 8000 --served-model-name planner \
     --structured-outputs-config.backend xgrammar \
     --structured-outputs-config.enable_in_reasoning=True

export VLM_LLM_URL=http://127.0.0.1:8000/v1
export VLM_LLM_MODEL=planner
python tools/agent_dataset.py -o data/5k_llm -n 5000 --workers 3
```

Cờ đáng chỉnh:

| Cờ | Mặc định | Ý nghĩa |
| :--- | ---: | :--- |
| `--dressings` | 48 | kho biến thể to bao nhiêu |
| `--pressure` | 0.72 | 0 = bốc như bộ gốc, 1 = đuổi theo phủ |
| `--shard` | 125 | số ảnh mỗi tiến trình render (mỗi shard một trình duyệt) |
| `--plan-only` | | quyết định và báo cáo, không vẽ |
| `--no-proof` | | bỏ qua ảnh proof |

Server không trả lời thì `alive()` bắt được và lượt chạy nói ra rồi chuyển sang
`coverage` — chứ không đứng chờ 5000 lần timeout.

---

## 6. Lượt chạy để lại những gì

```
data/5k_llm/
  html/            5000 ảnh + 5000 bản ghi + synthesis.json
  proof/           5000 ảnh proof — hộp nhãn vẽ đè, tô màu theo họ
  rules/           bộ luật của riêng lượt này (8 thuộc tính, có variant)
  agent_plan.json  từng quyết định: index, seed, force, by, note
  agent_report.json  phủ, chính sách, kho biến thể, thời gian từng chặng
  dataset.json     bộ đã lắp, đúng schema mọi bộ khác trong kho
```

`agent_plan.json` là thứ khiến lượt chạy **dựng lại được**: `force` + `seed`
của một dòng cho ra đúng trang ấy. Đó là câu trả lời cho chuyện agent thay chỗ
của seed — seed vẫn còn, chỉ là nó không còn quyết định nữa.

---

## 7. Ảnh proof

`tools/check_boxes.py` trả lời "hộp có nằm trên mực không" bằng một con số —
đúng dạng cho một cửa kiểm, sai dạng cho một người. `tools/proof_boxes.py` vẽ
ra ảnh: từng đoạn có nhãn được khoanh trên chính trang nó đọc được, tô màu theo
họ (`menu`, `total`, `invoice`, `store`, `sign`, …), kèm chú giải.

Cố ý **không** nằm trong renderer: một ảnh proof là một lượt **đọc lại** bộ đã
xong — nó chỉ dùng ảnh và bản ghi bên cạnh, đúng thứ người dùng bộ dữ liệu có —
nên nó không thể tự chứng minh mình đúng bằng cách dùng chung trạng thái với
thứ đã vẽ ra trang.

```bash
python tools/proof_boxes.py --dataset data/5k_llm --workers 3
```

---

## 8. Các file

| File | Việc |
| :--- | :--- |
| `policy.yaml` | ba hạng, và document nào vào hạng nào — **dữ liệu, sửa được** |
| `policy.py` | đọc và kiểm chính sách; document lạ thì báo lỗi chứ không mặc định |
| `variants.py` | bảy trục, và bộ ghép sinh ra kho biến thể |
| `rules.py` | dựng rules root của lượt chạy: thẻ + thuộc tính `variant` |
| `client.py` | endpoint OpenAI bất kỳ, qua `urllib` — không thêm phụ thuộc |
| `planner.py` | bộ chọn có nhớ, hợp nhất đề xuất của mô hình, và `verify()` |

Ngoài gói này:
`generators/html/sheets/variant.py` (dán CSS vào trang, và từ chối CSS phá hợp
đồng hộp), `tools/agent_dataset.py` (driver), `tools/proof_boxes.py` (ảnh
proof), `tests/test_agent.py` (20 test, kể cả đường LLM qua server giả).
