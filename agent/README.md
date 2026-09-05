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
| `layout_schema.py` | schema suy ra từ 17 layout viết tay, không phải khai tay |
| `augment_layout.py` | xin model viết biến thể layout, qua sáu cửa ải, rồi ghi |
| `provenance.py` | đóng dấu `# >>> llm …` quanh khối do model viết |
| `prompts/` | ba prompt, là file markdown chứ không phải chuỗi trong code |

Ngoài gói này:
`generators/html/sheets/variant.py` (dán CSS vào trang, và từ chối CSS phá hợp
đồng hộp), `tools/agent_dataset.py` (driver), `tools/critic_review.py` (chạy
`critic` + `guideline` như một lệnh), `tools/layout_gallery.py` (thư viện thiết
kế), `tools/proof_boxes.py` (ảnh proof), `tests/test_agent.py` và
`tests/test_llm.py`.

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
