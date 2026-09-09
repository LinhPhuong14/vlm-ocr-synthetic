# 🤖 `agent/` — mọi chỗ LLM được đụng vào kho này

> Một lượt chạy mà **mô hình quyết định từng trang**: loại giấy, phôi bố cục,
> cách dựng lại phôi, mực, hoạ tiết, cách làm cũ — 5000 lần, mỗi lần ghi lại
> được và dựng lại được. Và một bộ sinh **viết ra file** cho lượt chạy ấy đọc.

Gói này có hai nửa, gộp từ `agent/` và `tools/llm/`:

| nửa | mô hình làm gì | sản phẩm |
| :--- | :--- | :--- |
| **quyết định** (`planner`, `policy`, `rules`, `variants`, `redesign`, `distance`, `critic`, `guideline`, `client`) | chọn giá trị cho từng trang, ngay trước khi vẽ | `agent_plan.json` — sổ cái, rồi mới vẽ |
| **sinh** (`augment_content`, `augment_layout`, `corpus_rules`, `layout_schema`, `provenance`, `ollama`, `augmentable`) | viết vật liệu mới: dòng corpus, file layout | file thường trong git, có người đọc diff |

Hai nửa từng nằm hai thư mục vì chúng ra đời cách nhau, và đó là lý do duy
nhất. Chúng chia đúng một ranh giới, dùng chung một chính sách về chứng từ nào
được biến đổi, và cùng bị **một** assertion trong `tests/test_llm.py` giữ ở
ngoài đường render. Một ranh giới chung thì để một chỗ.

---

## 0. Ranh giới, và vì sao nó là toàn bộ kiến trúc

**Không file nào dưới `agent/` được `generators/`, `pipeline/`, `rulebase/`,
`degradation/` hay `components/` import, và `tests/test_llm.py` khẳng định điều
đó bằng một assertion.**

Thiết kế hấp dẫn là gọi model ngay lúc vẽ trang, để mỗi trang có chữ mới. Cái
giá của nó là lời hứa mà cả kho này dựng lên: **cùng seed thì ra cùng byte**.
`tools/baseline.py` vân tay từng ảnh, `tests/test_worklist.py` vẽ một trang hai
đường rồi so sha256, và `docs/renderers.md` so hai renderer trên đúng một tuyên
bố — chỉ cách vẽ khác nhau. Một bộ sinh nằm trong đường render cho cả ba nghỉ
việc, và cho nghỉ **lặng lẽ**: ảnh vẫn ra, chỉ là không còn là ảnh cũ nữa.

Nên model chạy **ở đây**, một bước riêng, và thứ nó tạo ra là **file thường
trong git** hoặc **một dòng trong sổ cái**. Có người đọc diff trước khi nó vẽ
ra bất cứ thứ gì. Renderer vẫn đọc file như trước, và không phân biệt được file
do model viết hay do người viết — đúng cái tính chất giữ đường render vừa
deterministic vừa offline.

```
agent/                              rulebase/                generators/
  ollama.py     ──────►               corpus/*.txt   ──────►   render.py
  corpus_rules.py  (gác cổng)         layouts/*.yaml           (không biết
  augment_content.py ──ghi──►         variants/*.yaml           agent/ tồn tại)
  provenance.py (đóng dấu)
  planner.py    ──────► agent_plan.json ────────────────────►
```

Chiều mũi tên là một chiều, và assertion kia là thứ giữ nó một chiều. `agent/`
được import `pipeline` và `rulebase` thoải mái — nó phải đọc bản ghi để chấm
bài; chiều ngược lại thì không.

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
| `--resume` | | bước quyết định bị ngắt giữa chừng thì tiếp tục từ checkpoint thay vì hỏi lại model những trang đã có |

Server không trả lời thì `alive()` bắt được và lượt chạy nói ra rồi chuyển sang
`coverage` — chứ không đứng chờ 5000 lần timeout.

**Bước quyết định có thanh tiến độ và tự lưu lại giữa chừng.** 5000 trang qua
model là hàng trăm lượt gọi mạng — mỗi lượt quyết một khối 24 trang theo mặc
định — không phải một phép tính tức thời, nên `agent/planner.py::plan()` vẽ
một thanh tiến độ (`pipeline/progress.py`, tự ẩn khi không phải terminal) và
ghi `agent_plan.json` **tạm** (`.partial`) sau mỗi khối trang, không đợi tới
trang cuối cùng. Mất kết nối tới server, hay tiến trình bị kill, chỉ mất tối
đa một khối vừa gọi dở chứ không mất từ đầu — chạy lại với `--resume` là đọc
tiếp từ đó. File tạm đó tự xoá khi bước quyết định xong xuôi và
`agent_plan.json` đã ghi thật; nó không phải sổ cái, chỉ là tấm lưới an toàn.

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
**Nửa quyết định**

| File | Việc |
| :--- | :--- |
| `policy.yaml` | ba hạng, và document nào vào hạng nào — **dữ liệu, sửa được** |
| `policy.py` | đọc và kiểm chính sách; document lạ thì báo lỗi chứ không mặc định |
| `variants.py` | bảy trục, và bộ ghép sinh ra kho biến thể |
| `redesign.py` | 22 thiết kế lại phôi, dựng trên bộ chọn của `variants.py` |
| `rules.py` | dựng rules root của lượt chạy: thẻ + thuộc tính `variant` |
| `client.py` | endpoint OpenAI bất kỳ, qua `urllib` — không thêm phụ thuộc |
| `planner.py` | bộ chọn có nhớ, hợp nhất đề xuất của mô hình, và `verify()` |
| `distance.py` | vẽ hai lần rồi đếm run đã dịch — "thiết kế này có đổi gì không" |
| `critic.py` | đọc bộ đã xong bằng mắt của người dùng bộ: 13 mã lỗi |
| `guideline.py` | sinh `guideline/` từ chính sách + luật + bài chấm |

**Nửa sinh**

| File | Việc |
| :--- | :--- |
| `ollama.py` | client Ollama (`/api/chat`) cho bước sinh — khác `client.py` ở trên, và đó là chỗ hai nửa còn chưa gộp |
| `augmentable.py` | đọc `rulebase/augmentable.yaml`: chứng từ nào được đề xuất biến đổi |
| `corpus_rules.py` | gác cổng dòng corpus; mọi ngưỡng đo từ corpus đã commit |
| `augment_content.py` | xin model viết dòng corpus mới, qua gác cổng, rồi ghi |
| `layout_schema.py` | schema suy ra từ 51 layout viết tay, không phải khai tay |
| `augment_layout.py` | **mức 2** — xin model sửa MỘT file layout, qua sáu cửa ải, rồi ghi |
| `constraints.yaml` | **mức 3** — khổ giấy nào đi với chứng từ nào, và ai đã duyệt |
| `constraints.py` | đọc và kiểm ràng buộc; document chưa duyệt thì từ chối |
| `compose_layout.py` | **mức 3** — soạn MỚI một bố cục từ *k* phôi, không sửa phôi nào |
| `provenance.py` | đóng dấu `# >>> llm …` quanh khối do model viết |
| `prompts/` | bốn prompt, là file markdown chứ không phải chuỗi trong code |

Ngoài gói này:
`generators/html/sheets/variant.py` (dán CSS vào trang, và từ chối CSS phá hợp
đồng hộp), `tools/agent_dataset.py` (driver), `tools/critic_review.py` (chạy
`critic` + `guideline` như một lệnh), `tools/layout_gallery.py` (thư viện thiết
kế), `tools/proof_boxes.py` (ảnh proof), `tests/test_agent.py`,
`tests/test_llm.py` và `tests/test_compose_layout.py`.

---

# Nửa sinh — mô hình viết vật liệu, không viết ảnh

Từ đây trở xuống là phần trước ở `tools/llm/README.md`. Lệnh đổi tiền tố
(`python -m agent.X` thành `python -m agent.X`); ngoài ra không có gì đổi.

```bash
ollama serve &
ollama pull qwen2.5:7b-instruct

# xem trước, không ghi gì
python -m agent.augment_content --file items_market --want 20
# ghi vào corpus
python -m agent.augment_content --file items_market --want 20 --write

# kiểm luật ngược lại chính corpus đang có
python -m agent.corpus_rules --audit
```

## 10. Chạy trên server hay chạy cục bộ — cách nhau một biến môi trường

```bash
export VLM_LLM_HOST=http://gpu-box.lan:11434    # mặc định: loopback
export VLM_LLM_MODEL=qwen2.5:32b-instruct
export VLM_LLM_TOKEN=...                        # nếu server có xác thực
```

Ollama từ xa nói đúng `/api/chat` như Ollama cục bộ, nên "đưa model lên máy có
GPU" là một hostname chứ không phải một bản viết lại. Loopback KHÔNG đi qua
proxy còn host xa thì có — `ollama.py::_opener_for` chọn theo host, vì
container này định tuyến mọi thứ ra ngoài qua một agent proxy.

Cái **không** đổi theo hostname là ranh giới ngay dưới đây. Xem
[`docs/llm-in-pipeline.md`](../docs/llm-in-pipeline.md) cho thiết kế lấy
được biến thể theo từng ảnh mà vẫn dựng lại được lượt chạy: model quyết định
**trước**, quyết định được ghi thành file, lúc vẽ chỉ đọc file.

## 9. Chứng từ nào được phép biến đổi

[`rulebase/augmentable.yaml`](../rulebase/augmentable.yaml) chia ba mức, và
`agent/augmentable.py` đọc nó:

```bash
python -m agent.augmentable --check
```

`fixed` (6 loại) — hoá đơn GTGT theo mẫu, tiền điện, tiền nước, bảng kê viện
phí, hoá đơn xuất khẩu: **không đổi bố cục**, vì hình dạng của chúng do quy
định ban hành chứ không do người in quyết. `styled` (13) — cửa hàng tự thiết
kế. `free` (4) — báo và tạp chí, càng nhiều biến thể càng tốt.

Loại chưa khai được coi là `fixed`. Mặc định phải là mức chặt nhất: quên khai
thì mất một biến thể, chứ không phải bịa ra một giấy tờ pháp lý.

> **Còn hai file chính sách, và chúng nói về cùng 41 chứng từ.**
> `rulebase/augmentable.yaml` (`fixed`/`styled`/`free`) nói bộ **sinh** được đề
> xuất tới đâu; `agent/policy.yaml` (`locked`/`livery`/`free`) nói bộ **quyết
> định** được dựng lại tới đâu. Hai câu hỏi khác nhau, nhưng hai bảng có thể
> bất đồng về cùng một tờ giấy mà không gì báo. Gộp chúng là việc còn lại của
> lần refactor này.

## 11. Cái gì lặp lại được, cái gì không

Model nhận seed và temperature, Ollama tôn trọng cả hai, nên cùng prompt trên
cùng trọng số và cùng bản build **thường** ra cùng chữ. "Thường" là xa nhất
file này dám nói: đổi bản Ollama, đổi mức lượng tử hoá, đổi số luồng đều có thể
xê một token, và không thứ gì phía sau được phép dựa vào chuyện nó không xê.

Cái **lặp lại được** là file đã commit. Đó mới là sản phẩm; prompt và model
được ghi ngay bên cạnh nó bởi `provenance.py`. Chạy lại bộ sinh là cách lấy
**thêm** vật liệu, không phải cách lấy **lại** vật liệu cũ.

## 12. Dấu vết trong corpus

Một khối do model viết được rào bằng comment — mọi trình đọc sẵn có đều bỏ qua
dòng bắt đầu bằng `#`, và đã bỏ qua từ trước khi có file này:

```
# >>> llm qwen2.5:7b-instruct@845dbda0ea48 prompt=items:3f2a seed=11 2026-08-26
Nước mắm Nam Ngư 500ml	28000	35000
# <<< llm
```

Có nó thì câu hỏi "dòng này là thật hay 7B bịa ra?" mới có chỗ trả lời. Không
có nó thì corpus có hai loại dòng mà người đọc không phân biệt được — và người
đọc chính là người phải sửa khi model viết sai.

## 13. Gác cổng: `corpus_rules.py`

Model là bên **đề xuất**; luật trong `corpus_rules.py` là thứ duy nhất đứng
giữa nó và dataset. Mọi ngưỡng ở đó **đo từ corpus đã commit**, không phải chọn
— và `--audit` là phép thử của chính bộ luật:

> **Luật nào loại một dòng người đã viết là luật sai, không phải dòng sai.**

Bản đầu đoán thay vì đo, và audit ném đi **354/737 dòng, 48 %**. Vòng hai còn
**209/828, 25,2 %** — toàn bộ vì đúng một ký tự: `đ` và `Đ` không phân rã được
bằng NFD, nên phép thử Latin viết theo dải `a`–`z` loại sạch mọi từ tiếng Việt
chứa chữ cái Việt Nam nhất. Vòng ba còn 6 dòng vì bao ngưỡng đo theo cột 1 mà
áp cho cột 2 (chi nhánh dài hơn tên chuỗi). Vòng bốn còn 8 dòng vì `Quận 1` là
một chữ số. Hiện tại **0/828**, và lệnh trả về mã lỗi khác 0 nếu không còn thế.

Bao ngưỡng độ dài đo **theo từng file và từng cột**, và chỉ đo trên **dòng do
người viết**: nếu tính cả dòng model viết thì mỗi vòng nới ra một chút, và vòng
thứ mười sẽ được kiểm bằng sai sót của vòng thứ chín.

## 14. Cái gác cổng KHÔNG bắt được

Luật là cơ học. Nó bắt được model trả lời bằng tiếng Anh, bịa một cái tên 200
ký tự, hay ghi giá có dấu chấm. Nó **không** bắt được một dòng đúng ngữ pháp mà
sai sự thật: `Dầu-tahini` là tiếng Việt hợp lệ và không phải thứ tiệm tạp hoá
nào bán. Đó là việc của dấu vết provenance và của người đọc diff — và là lý do
`--write` chỉ ghi file chứ không commit.

## 15. Giá phải trả

Qwen2.5 7B lượng tử hoá 4-bit chạy CPU: **~5 token/giây**. Một vòng 20 dòng mất
hai tới ba phút, và một file corpus là cả buổi chiều. Bộ sinh in tiến độ từng
vòng vì lý do đó. Máy có GPU thì `--model` trỏ sang model lớn hơn.

## 16. Augment layout: `augment_layout.py`

```bash
python -m agent.augment_layout --from market_vat --id market_vat_b          # xem trước
python -m agent.augment_layout --from market_vat --id market_vat_b --write  # chạy hàng rào
```

Đọc `rulebase/layouts/<parent>.yaml`, bảo model viết một **biến thể** — cùng
loại chứng từ, khác cách in — rồi **chỉ giữ lại nếu nó qua được đúng những gì
một layout viết tay phải qua**:

| # | kiểm | bắt được gì |
| --- | --- | --- |
| 1 | là YAML và là mapping | model viết văn xuôi |
| 2 | mọi key path có trong layout viết tay, đúng kiểu, trong dải đã đo, enum đúng tập | `meta.style: one_column`, `columns[].width: 30` |
| 3 | mọi khoảng `[min, max]` đúng thứ tự | `width: [48, 42]` — đảo là **mọi seed** đều `ValueError` |
| 4 | có đủ key mà cả 17 layout **viết tay** đều có | thiếu `sections`, thiếu `id` |
| 5 | `rulebase.make()` dựng được trang qua nhiều seed | layout hợp lệ về hình thức nhưng vô nghĩa |
| 6 | `pipeline/preflight.py` toàn bộ rule base | quên đăng ký, nội dung tràn khổ giấy |

Hỏng ở bất kỳ bước nào: file bị xoá và **cả ba đăng ký được hoàn nguyên**
(`rules/layout.yaml`, `blanks.yaml`, `sheets.FAMILIES`). Một layout đăng ký nửa
vời là rule base trỏ tới file không tồn tại, và preflight sẽ báo đó là lỗi của
kho chứ không phải lỗi của lệnh này.

Đăng ký chèn **theo văn bản**, không dùng `yaml.safe_dump`: hai file kia nhiều
comment hơn dữ liệu — chúng giải thích vì sao từng layout loại trừ cái gì — và
dump lại sẽ xoá sạch phần giải thích ấy.

### Đã chạy thật, và bắt được đúng những gì thiết kế để bắt

| vòng | model viết | hàng rào |
| --- | --- | --- |
| 1 | `width: [48, 42]` | bước 3 — trong vài giây |
| 2 | `meta.style: one_column`, `columns[].width: 30` | bước 2 |
| 3 | schema sạch, 8 trang dựng được | bước 6 — **thiếu sheet CSS** |
| 4 | schema sạch | qua hết, `check_boxes` sạch 428 hộp / 6 ảnh |

Hai lần sửa **prompt** chứ không sửa luật: model liên tục viết `[48, 42]` vì nó
muốn "rộng hơn" nên để số lớn trước, và viết `rule_char: '—'`. Prompt nay nói
thẳng hai điều đó.

**Biến thể sinh ra chưa được commit.** Nó qua hàng rào, nhưng đưa một layout mới
vào kho đòi chụp lại golden baseline, mà việc đó đang bị chặn bởi một lỗi có sẵn
(`invoice_export` seed 6026: `menu.nm` có trong nhãn mà không có hộp nào). Máy
móc đã xong và đã chứng minh; dữ liệu sinh ra thì chờ lỗi kia được sửa.

## 17. Soạn bố cục: `compose_layout.py` — mức 3

```bash
python -m agent.compose_layout --document invoice_detailed --explain          # ba lớp §8.1
python -m agent.compose_layout --document invoice_detailed --id invoice_kiosk # xem trước
python -m agent.compose_layout --document invoice_detailed --id invoice_kiosk --write
python -m agent.compose_layout --document invoice_detailed --distance invoice_kiosk
```

Ba mức, và chúng hỏi ba câu khác nhau về **cùng một tờ giấy**:

| mức | file | được đổi | câu hỏi |
| :--- | :--- | :--- | :--- |
| 1 · dùng lại | `variants.py` | mực: nét kẻ, tông giấy, bộ chữ, hoạ tiết | *tờ này, in mực khác?* |
| 2 · dựng lại | `redesign.py`, `augment_layout.py` | thứ tự khối, số cột, chỗ đặt khối tổng | *tờ này, bày khác đi?* |
| **3 · soạn mới** | **`compose_layout.py`** | **có mấy khối, khối nào, khổ giấy nào** | *một nhà in KHÁC sẽ làm ra tờ gì?* |

Khác biệt với mức 2 không phải là diff to hơn. Mức 2 **nhận một file layout rồi
sửa**, nên đầu ra luôn là đầu vào cộng thay đổi và về cấu trúc không thể bỏ một
khối mà phôi cha có. Mức 3 nhận *k* phôi làm **bằng chứng về một loại chứng
từ**, cộng đặc tả trường, cộng ràng buộc — rồi viết ra một cấu trúc không có
trong phôi nào.

### Model trả về CẤU TRÚC, không bao giờ trả về markup

`Composition` là khối, cột, khổ giấy và `reasoning`. `to_layout()` — **code,
không phải model** — biến nó thành đúng file `rulebase/layouts/*.yaml` mà người
vẫn viết, rồi `sheets/` biến file ấy thành HTML như từ trước tới nay.

Đó không phải gọn gàng, đó là **hợp đồng nhãn**. Mỗi run phải là một `<span>`
chứa chỉ chữ đã escape, vì phép đo lấy `span.firstElementChild || span` — một
thẻ lồng lặng lẽ trở thành cái hộp được ghi. Đã đo: một `<sub>` trong công thức
làm hộp rộng **5,3 px** thay vì 310,6. Model viết HTML thì hợp đồng ấy phụ
thuộc vào việc model không quên, ở mọi trang, trong 5000 trang; bộ dựng viết
thì nó đúng theo cấu trúc. Nên không chuỗi nào được chứa `<`, và một ký tự ấy
làm cả bố cục bị từ chối.

Ba thứ model **không** được đụng, và code viết thay: `item.rows` (dây nối vào
dữ liệu, suy từ chính các cột đã chọn), `source:` (xuất xứ — mọi phôi viết tay
dùng ô ấy để ghi tấm ảnh đã đo, còn bố cục soạn mới thì không đo từ ảnh nào),
và `family:`.

### Ba lớp của §8.1 được TÍNH, không phải được khai

`layers()` giao *k* phôi để ra cái chúng đều có (lớp 1+2 — bất biến pháp lý và
quy ước ngành) và trừ ra cái chúng khác nhau (lớp 3 — lựa chọn của nhà in). Đó
là một khẳng định về một tập file, nên nó được đọc từ file.

"Lớp 3" rộng hơn "phôi mang khối khác nhau", và phải rộng hơn: đọc hẹp thì
đúng **1 trên 33** chứng từ đủ điều kiện. `invoice_plain` có bốn phôi — logo
canh giữa, bảng dày, tối giản, nhiều trang — mang **cùng bốn khối, cùng thứ
tự**, và khác nhau ở `table.compact`, `table.blank_rows`, `totals.grand_scale`
và bề ngang. Bốn trang một người đã vẽ từ bốn tấm ảnh khác nhau, tức là đúng
định nghĩa lớp 3, mà phép giao nhìn một khoá thì gọi là rỗng. Nên `layers()`
đo bất đồng trên **sáu chiều**: khối, thứ tự khối, cột, thuộc tính cột, tuỳ
chọn khối, khổ giấy.

Phôi nào cũng giống nhau trên cả sáu thì **không có lớp 3**, và `layers()` nói
thế thay vì bịa ra một cái. Đúng §8.2 "báo lại, đừng bịa".

### Đủ điều kiện: 9/33, không phải 28

Spec (R-1) nói "28 chứng từ đủ điều kiện". Đo trên kho này thì **9**:

```
invoice_detailed   6 phôi  khối, thứ tự khối, thuộc tính cột, tuỳ chọn khối, khổ giấy
invoice_plain      4 phôi  thuộc tính cột, tuỳ chọn khối, khổ giấy
convenience_store  2 phôi  cột, thuộc tính cột, tuỳ chọn khối, khổ giấy
hotel_stay         2 phôi  ·  resort_stay 2  ·  pub_eatery 2  ·  street_eatery 2
supermarket        2 phôi  ·  supermarket_vat 2
```

24 chứng từ còn lại trượt, và trượt vì một lý do duy nhất: **22 cái chỉ có một
phôi**, `form_brief` có hai phôi giống hệt nhau, `restaurant_vat` có hai nhưng
một là do máy sinh nên không tính. Đó không phải giới hạn của bộ soạn — đó là
đo được rằng kho chưa có đủ bằng chứng để nói "một nhà in khác sẽ làm gì".
Muốn mở thêm thì đo thêm một phôi thật, không phải nới luật.

**Phôi do máy sinh không phải bằng chứng.** `layout_schema.py` loại chúng khỏi
phép suy schema vì "biến thể đầu nới rộng schema, biến thể sau bị kiểm theo lỗi
của biến thể đầu"; suy luận về lớp cũng hỏng đúng thế, chỉ chậm hơn. Chỉ cái
người đã đo từ giấy mới được tính.

### Hai cửa vào, và cả hai đều TỪ CHỐI thay vì mặc định

`policy.yaml` nói tờ này có được dựng lại dáng không — `locked` không bao giờ
tới đây. `constraints.yaml` nói được thì **trong khoảng nào**, và chứng từ chưa
có mục đã duyệt thì bị từ chối kèm tên file phải sửa. Không cái nào mặc định
là cho phép: quên khai một phôi thì mất một biến thể, còn mặc định cho phép thì
ra một tờ giấy tờ nhà nước do máy sinh.

`constraints.yaml` là **việc thủ công**, và cố ý thế. Số đo từ
`rulebase/layouts/` chỉ nói các phôi ĐANG thế nào; file này phải nói một nhà in
KHÁC còn được làm gì, và không phôi nào biết điều đó. Sáu phôi của
`invoice_detailed` đều rộng `[78, 92]` ký tự — đo thì ra "78..92", nhưng đó là
sáu lần cùng một lựa chọn chứ không phải một giới hạn.

### `couples:` — chỗ phép giao đếm sai

Phép giao đếm **KHỐI**; một trang làm bằng **TRƯỜNG**. Phôi bỏ một khối mà vẫn
in đủ trường của nó là vì khối khác được bảo làm thay:

| phôi bỏ | vì tuỳ chọn | in thay ở đâu |
| :--- | :--- | :--- |
| `strip` | `header.align: corner` | hộp góc phải đã vẽ số, ngày, hạn thanh toán |
| `totals` | `table.component: true` | ba dòng tổng thành ba dòng cuối bảng hàng |

Cặp là **loại trừ hai chiều**: không có khối và cũng không bật tuỳ chọn thì
nhãn không có mực (I-5); có cả hai thì cùng một trường in hai lần. Viết tay chứ
không suy ra, vì đây là chuyện hai hàm của bộ dựng tương tác với nhau — đọc bao
nhiêu phôi cũng không ra, phải đọc `sheets/modern.py`.

Bản đầu không có `couples:` mà đòi luôn cả hai khối. An toàn, và mất mọi biến
thể mà một nhà in thật đã làm.

Bản thứ hai có `couples:` nhưng để **model tự khai tuỳ chọn** — và nó hỏng theo
một kiểu đáng nhớ. Trên cả 52 phôi, `header.align: corner` đúng bằng "không có
`strip`" và `table.component: true` đúng bằng "không có `totals`": **một quyết
định**, mà danh sách khối đã nói rồi. Hỏi lần thứ hai là mời model tự mâu
thuẫn, và một server thật mâu thuẫn **ba vòng liên tiếp** — mỗi vòng đều muốn
tiêu đề hộp góc *và* dải ngày. Một trang hợp lý, bị từ chối vì không thống nhất
với chính nó về thứ nó bị hỏi hai lần.

Nay giá trị ghép bị **gạch khỏi schema** (`_settable`) và `to_layout` suy nó ra
từ danh sách khối, đúng cách `item.rows` được suy từ danh sách cột. Lá vẫn còn
nếu nó còn giá trị khác — `header.align: split` vẫn là một lựa chọn, vì nó là
một lựa chọn thật; `table.component` bị gỡ hẳn vì giá trị còn lại đúng bằng mặc
định, tức một câu hỏi chỉ có một đáp án.

**Bài học lặp lại lần thứ hai:** cửa 1 phải làm cái sai thành *không đánh vần
được*, không phải thành *bị từ chối*. Lần đầu là tuỳ chọn của khối khác; lần
này là một quyết định bị hỏi hai lần.

### Bảy cửa ải

| # | kiểm | ở đâu | bắt được gì |
| --- | --- | --- | --- |
| 1 | guided decoding theo schema | `schema_for()` | id không tồn tại, thiếu khoá, sai kiểu, **tuỳ chọn của khối khác** |
| 2 | trọng tài số | `check_numbers()` | cột co giãn hụt chỗ, khoảng đảo, khổ giấy sai |
| 3 | chữ in ra | `check_numbers()` + cửa 4 | tiêu đề cột rỗng, quá dài, không có chữ cái |
| 4 | schema bố cục | `layout_schema.check/ranges/missing` | key lạ, ngoài dải đã đo |
| 5 | hợp đồng nhãn | `check_contract()` | `<`, `text-transform`, `content:` mang chữ |
| 6 | dựng + preflight | `augment_layout.draws/preflight` | nhãn mồ côi, tràn khổ, đăng ký sai |
| 7 | critic | `--proof N` → `agent/critic.py` | chồng lấn, tràn lề, chữ nhỏ — 13 mã |

Sáu cửa đầu chạy trong `--write`. **Cửa 7 cần ảnh thật**, nên nó là một lệnh
riêng chạy sau khi layout đã được ghi:

```bash
python -m agent.compose_layout --document invoice_detailed --id invoice_thu --proof 12
```

Nó vẽ 12 trang vào `data/compose/<id>/html/` rồi đọc lại bằng `agent/critic.py`
— cùng đường mà `tools/critic_review.py` đọc một lượt chạy thật, nên bố cục
soạn ra được chấm bằng đúng con mắt chấm mọi trang khác.

**Hai trục bị ghim, năm trục vẫn bốc.** Đo trên 12 trang thật:

| thuộc tính | số giá trị | do đâu |
| :--- | ---: | :--- |
| `layout` | **1** | thứ model soạn ra — cả 12 trang cùng một file |
| `document` · `variant` · `augmentation` | 1 · 1 · 1 | ghim: `none` và `CLEAN_FORCES` |
| `content` · `color` · `visual` · `handwriting` · `ornament` | 3 · 4 · 2 · 3 · 6 | rulebase bốc theo seed |

Ghim `variant`/`augmentation` là vì hai trục ấy che mất thứ đang soi: một dải
guilloche hay một lớp mực mòn làm hộp nhãn dịch chỗ, và bản án về bố cục sẽ
phụ thuộc vào việc hạt giống trúng mô hình nào — lần đầu chạy nó trúng một mô
hình cần Blender và render chết luôn.

Năm trục kia **cố ý** không ghim: một bố cục chỉ sống được với đúng một màu
mực và đúng một kiểu nội dung là một bố cục tồi, và 12 trang cùng nội dung thì
không nói được điều đó. Đổi lại, một lỗi `critic` báo ra chưa chắc do bố cục —
`critic.rank()` quy trách nhiệm theo từng giá trị thuộc tính, nhưng cần nhiều
hơn 12 trang mới có ý nghĩa thống kê. Với 12 trang thì nó là **phép thử khói**,
không phải bản án.

Ảnh để lại chính là thứ A-5 cần: "một nhà in có thể đã in tờ này" là phán đoán
về một tấm ảnh giấy, không ai đưa ra được từ một file YAML. Vẽ hộp nhãn đè lên
để đọc nhanh hơn:

```bash
python tools/proof_boxes.py --dataset data/compose/<id> --mode layout
```

`layout` tô theo 18 vùng trục 1, `blocks` (mặc định) theo từng trường, `words`
theo từng từ.

Hỏng ở bất kỳ bước nào: file bị xoá và **cả hai đăng ký được hoàn nguyên**.
Cửa 6 báo nhãn mồ côi thì lệnh chỉ thẳng vào `sections.required` /`couples:` của
chứng từ ấy — đó là chỗ sửa, không phải chỗ nới luật.

#### Cửa 1 phải làm cái sai thành BẤT KHẢ, không phải thành bị-từ-chối

Bản đầu để tuỳ chọn nằm **trong** mỗi khối. Danh sách khối là một mảng JSON, mà
một mảng chỉ có một schema cho phần tử — nên tập tuỳ chọn phải là **hợp của mọi
khối**, và schema hoá ra *cho phép* `header.name_gap` (có thật, ở `signatures`)
và `table.indent` (có thật, ở `totals`). Model được mời điền thì nó điền, rồi
`check_structure` từ chối ngay sau đó.

Đo trên lần chạy thật đầu tiên với server local: **9/13 lỗi vòng 1, 12/14 vòng
2, 7/11 vòng 3** đúng là chuyện ấy — schema mời một khoá và cửa kiểm đuổi nó.

Nay tuỳ chọn nằm **cạnh** khối, khoá theo tên khối (`settings: {header: {...},
table: {...}}`), mỗi khối một object riêng với `additionalProperties: false`.
`header.name_gap` thành **không đánh vần được**. Tình cờ đó cũng đúng hình dạng
của file đang dựng: `sections: [...]` ở trên và `header: {...}` bên cạnh chính
là cách một layout YAML được viết.

Hai lỗi còn lại schema **không** diễn đạt được, nên chúng nằm ở prompt cộng cửa
kiểm — đúng cách mục 16 đã xử hai lần:

* **khoảng đảo ngược** (`[1.4, 1]`, `[84, 76]`) — JSON Schema không nói được
  "tăng dần";
* **cột trùng `key`** — `uniqueItems` so cả object, mà hai cột khác nhau đúng ở
  `title` vẫn là hai object khác nhau. Cái schema làm được là không cho xin
  nhiều cột hơn số khoá đang có.

### Đã chạy thật, và bắt được đúng những gì thiết kế để bắt

Bốn vòng của chế độ `coverage` trên `invoice_detailed`, mỗi vòng một lỗi thật:

| vòng | bộ soạn viết | cửa nào bắt |
| --- | --- | --- |
| 1 | cột co giãn còn 14 ký tự (cần 16) | 2 — trước khi vẽ gì |
| 2 | `source:` chứa `;`, ký tự không phôi nào in | 4 |
| 3 | bỏ `strip` rồi bỏ `totals` mà không bù | 6 — `invoice.strip.Ngày`, `total.Tổng cộng thanh toán`, cả 10 seed |
| 4 | không tuỳ chọn nào ⇒ `notes` về `style: block` | 6 — **108% khổ A4** ở seed 2 |

Và ba vòng của nhánh có model trên server local — 13 lỗi, rồi 1–2, rồi 1:

| vòng | model viết | ai sai | sửa ở đâu |
| --- | --- | --- | --- |
| 1 | `header.name_gap`, `table.indent`, `notes.rule_after` (9/13 lỗi) | **tôi** — schema gộp tuỳ chọn mọi khối | `settings` tách theo khối |
| 2 | cột cố định ăn hết bề ngang, cột tên còn 0 rồi −2 | **tôi** — trần cột là 48, phôi rộng nhất 15 | trần đo từ phôi = 21, và đưa phép tính vào prompt |
| 2 | `totals` + `table.component: true` | **tôi** — quên nói với model về `couples` | liệt kê cặp trong lượt người dùng |
| 3 | `totals.indent: 0` | **tôi** — JSON một kiểu số, `layout_schema` hai | `to_layout` viết theo kiểu corpus viết |
| 3 | `{"type":"integer","minimum":1.4285…}` → vLLM HTTP 500 | **tôi** — `bounds()` đệm SLACK nên luôn ra float | `ceil`/`floor` về số nguyên bao trong |
| 4 | `strip` + `header.align: corner`, ba vòng liền | **tôi** — một quyết định hỏi hai chỗ | gạch giá trị ghép khỏi schema, bộ dựng suy ra |

Sáu lỗi, **sáu lần là thiết kế sai chứ không phải model bịa**. Đó là cái đáng
ghi lại nhất ở đây: khi cửa 1 mời một câu trả lời rồi cửa 2 phạt nó, thứ hỏng
là cái cửa, không phải cái model.

Vòng 5 qua cả sáu cửa chạy được ngoại tuyến. Hai lần sửa là sửa **dữ liệu**
(`constraints.yaml`), một lần sửa **bộ soạn** (chép tuỳ chọn từ phôi xương sống
thay vì để trống), một lần sửa **đăng ký** (`augment_layout.register` chỉ vá
được danh sách `documents:` viết trên một dòng, mà `invoice_detailed` và
`invoice_plain` viết trên hai — nên đúng hai chứng từ nhiều phôi nhất bị bỏ
sót, lặng lẽ).

### A-2 đo được, và chế độ `coverage` TRƯỢT nó

`--distance` vẽ bố cục soạn ra cạnh từng phôi, cùng seed cùng dressing, rồi đếm
run đã dịch — dùng lại `compare`/`render` của `distance.py` không sửa gì. Lấy
**gần nhất** chứ không lấy trung bình: một tờ xa năm phôi mà trùng phôi thứ sáu
vẫn là bản sao.

```
0.708  invoice_two_column     ← gần nhất
0.782  invoice_keyvalue
0.793  invoice_logo_split
0.793  invoice_remittance
0.796  invoice_header_table
0.949  invoice_sidebar
```

**0.708 < 0.764**, và đó là câu trả lời đúng. Chế độ `coverage` chép thứ tự
khối, thứ tự cột và tuỳ chọn từ một phôi rồi mới xê dịch — nó không được thiết
kế để sáng tạo, nó được thiết kế để **lặp lại được** (R-6: cùng seed ra cùng
byte, thứ một LLM chỉ *thường* làm được). Vượt 0.764 là việc của nhánh có model.

### A-5 trên tờ đầu tiên: tạm được, và chỗ lộ nằm ở đâu

12 trang của `invoice_kiosk` (chế độ `coverage`): **0 trang lỗi nặng**, dưới
ngưỡng A-3 là 1,2%. Cửa 7 sạch.

Đọc bằng mắt thì khác. Tờ giấy đúng dáng hoá đơn GTGT — hộp góc phải có số,
ngày, hạn thanh toán; ba dòng tổng gộp vào cuối bảng; khối ngân hàng; tiền
bằng chữ; hai ô ký. Nhưng **khối `parties` là 11 dòng liền không ngắt**: năm
trường bên bán chảy thẳng vào sáu trường bên mua, không tiêu đề, không vạch
ngăn. Không nhà in nào dàn như thế.

Đó là `parties.style: stacked` — một giá trị hợp lệ, trong dải đã đo, có trên
phôi thật, và sai ở đây. (Chữ không dấu trên cùng trang ấy thì **không** phải
lỗi bố cục: `content: invoice_ascii` bốc trúng 2/12 trang, và nó là một kiểu
nội dung có thật của kho.) **Không cửa nào bắt được**, đúng như §10 lường trước:
ba trong năm kiểu sai không có cửa ải nào chặn, và A-5 là chỗ duy nhất chặn
được. Nó vừa chứng minh mình cần thiết ngay trên tờ đầu tiên.

### Bố cục soạn ra chưa được commit

Cùng lý do mục 16: nó qua hàng rào, nhưng thêm một layout vào kho làm
`test_agent.py::test_coverage_beats_independent_draws_on_the_tail` đỏ (400 lượt
bốc không còn phủ hết) và đòi chụp lại golden baseline. Máy móc đã xong và đã
chứng minh; layout sinh ra thì chờ.
