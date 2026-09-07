# Tổng hợp dự án — chốt lại một lượt, 05/09/2026

> **Đọc file này để làm gì:** đây là điểm chốt sau nhiều vòng hỏi-đáp giữa
> product owner (Claude Code) và người ra quyết định (chủ repo). Hai đối
> tượng đọc: (1) Claude Code ở các phiên sau — dùng làm ngữ cảnh thay vì hỏi
> lại từ đầu; (2) đồng nghiệp cùng làm domain này.
>
> **Không phải bản thay thế `docs/muc-tieu.md`/`docs/ke-hoach.md`.** Hai file
> đó (921 dòng, kế hoạch 10 việc P1–P10) có thể chồng lấn với những gì đã xây
> — xem mục 6. Chủ repo chưa review, và file này không tự ý hợp nhất/xoá gì.

---

## 1. Dự án là gì, đánh giá bằng gì

**Một engine sinh dữ liệu tổng hợp phục vụ training OCR/VLM** trên chứng từ
Việt Nam (hoá đơn, biểu mẫu). Sản phẩm giao là **cái engine**, không phải một
model đã train.

**Đánh giá bởi giáo viên hướng dẫn** dựa trên: output (dữ liệu sinh ra),
performance, scale — không đánh giá bằng độ đẹp của code.

**Vì sao LLM là must-have, không phải phần mở rộng** (nguyên văn lý do chủ
repo đưa ra): trước đây engine chủ yếu rule-based; rule-base giới hạn layout,
content và nhiều component khi render HTML. LLM lấp gap đó. **Mục tiêu xuyên
suốt là làm đa dạng data pool**, không phải làm engine "thông minh hơn" theo
nghĩa chung chung.

---

## 2. Kiến trúc — bản rất tóm tắt

Chi tiết đầy đủ nằm ở [`README.md`](../README.md) (674 dòng, đã cập nhật).
Ở đây chỉ nêu khung để hiểu phần 3 bên dưới:

```
rulebase/          luật sinh nội dung — 8 thuộc tính có trọng số (từng là 11,
                   xem mục 5), thuần YAML/Python, không cần thư viện ảnh
generators/html/   renderer DUY NHẤT — Chromium qua Playwright, đọc hộp nhãn
                   thẳng từ DOM vừa dàn (không đoán, không LLM)
pipeline/          một lượt chạy: chia shard, chạy song song, resume,
                   invariants, đo drift, vân tay vàng (byte-for-byte)
degradation/       26 mô hình làm cũ + degradation/blender/ (render 3D thật,
                   thay cho xấp xỉ numpy cũ — merge cùng đợt PR #24)
agent/             xem mục 3 — TRỌNG TÂM hiện tại
```

**Bất biến quan trọng nhất, liên quan trực tiếp tới mọi câu hỏi về LLM:**
nhãn/hộp **không bao giờ** do LLM sinh ra, ở bất kỳ thiết kế nào đã bàn. Box
luôn được đo từ DOM thật sau khi render. LLM chỉ chọn **tham số cấp thuộc
tính** (layout nào, dressing nào...), không bao giờ chạm vào toạ độ.

---

## 3. Trọng tâm hiện tại: hệ thống `agent/` (LLM)

### 3.1 Đã kết nối LLM thật, đã xác nhận hoạt động

`agent/client.py` (OpenAI-compatible) → server nội bộ `10.148.20.19:8008/v1`,
model `Qwen/Qwen3.8-27B-FP8`. Chạy thật `tools/agent_dataset.py`, kết quả:

```json
{"coverage": {"by": {"llm": 20, "coverage": 0}}}
```

Toàn bộ 20 trang thử do model thật quyết định. (Trước đó, kể cả tập
`data/5k_llm/` 5000 ảnh đã công bố, 100% chạy ở chế độ dự phòng ngoại tuyến —
chưa từng có server nào được nối thật cho tới đợt này.)

### 3.2 Các mảnh ghép, vai trò từng cái

| File | Vai trò |
| :--- | :--- |
| `agent/client.py` | Gọi model, OpenAI-compatible. Không sinh quyết định, chỉ là đường ống. |
| `agent/planner.py` | `Chooser`/`Decision`/`plan()` — chọn từng thuộc tính theo `pressure` (0 = như luật gốc, 1 = đuổi theo phủ đều), nhận `penalty`/`ban` từ critic. |
| `agent/variants.py` | Ghép 7 trục CSS (tông giấy, nét kẻ, bộ chữ, mật độ, hoạ tiết...) thành ~48 "dressing" — **đây là chỗ bị chê "hardcode/mixed"**, xem mục 5.3. |
| `agent/critic.py` + `tools/critic_review.py` | Đọc lại ảnh đã vẽ, sinh `feedback.json`; `tools/agent_dataset.py --feedback` đưa nhận xét vào lượt sinh kế tiếp (giá trị gây lỗi vẽ ít lại, cặp chỉ hỏng khi đi cùng nhau bị cấm hẳn). |
| `agent/policy.py` (`locked`/`livery`/`free`) | Chứng từ nào được đổi bố cục tới đâu — dùng bởi `agent/rules.py`. |
| `rulebase/augmentable.yaml` (`fixed`/`styled`/`free`) | **Cùng mục đích, khác tên, khác file** — dùng bởi thiết kế `docs/llm-in-pipeline.md` cũ hơn. Hai hệ song song, xem mục 6. |

### 3.3 Câu hỏi kiến trúc đã bàn và chốt

**"Có nên multi-agent thay vì 1 LLM?"** → Chưa cần. `planner` + `critic` đã là
hai vai tách biệt (sinh / phản hồi) — đúng nghĩa multi-agent nhẹ. Thêm agent
chuyên biệt (một agent riêng cho layout, một riêng cho nội dung) chỉ nên làm
khi có việc **khác hẳn về bản chất** cần model khác làm — không phải để chia
nhỏ một quyết định một model đã làm tốt. Chia LLM để "gán nhãn box" không giải
quyết gì, vì box vốn dĩ không cần LLM (mục 2).

---

## 4. Việc đã hoàn thành trong đợt này (05/09/2026)

- **PR #24 merged**: gộp `tools/llm/` cũ vào `agent/`, kết nối vLLM thật, xoá
  hẳn 2 renderer đã nghỉ hưu (`generators/genalog/`, `generators/synthdog/`,
  225 file) — chi tiết xem PR description trên GitHub.
- **Xoá 3 thuộc tính `toner`/`drum`/`rollers`** khỏi rule-base (11 → 8 thuộc
  tính). Lý do: cả 3 chỉ còn đúng 1 giá trị "tắt" mỗi file từ lâu, LLM/planner
  vẫn bị hỏi nhưng không có gì để chọn thật — thuần dư thừa cho mục tiêu đa
  dạng hoá. Không giữ backward-compat (quyết định rõ ràng, khác với cách xử
  lý genalog/synthdog). **Còn sót một chỗ chưa sửa — xem mục 5.1.**
- **WriteViT cài đặt xong** (`tools/writevit/setup.py`), test sinh chữ tay
  tiếng Việt thành công.
- **Thử nghiệm hệ nhãn 3 trục** (`region` × `role` × `ink`) qua 3 fixture ở
  `samples/label-axes/` (`page.html`/`page2.html`/`page3.html`) + script đo
  thật `samples/label-axes/measure.py` (chạy qua Chromium + `CELL_RECTS_JS`
  thật, không phải suy đoán). Kết quả: sạch, phủ 17/19 nhãn `DOCSYNTH_LABELS`
  (2 nhãn còn lại — `Blank-Page`, `Complex-Block` — cố tình bằng 0, có lý do).
  Sửa được 1 bug thật (`store.logo` đo ra 0×0) và 2 chỗ tên nhãn lệch schema.
  **Chưa tích hợp vào `sheets/*.py` thật — tạm dừng theo yêu cầu, xem mục 7.**

---

## 5. Nợ kỹ thuật đang treo (chưa xử lý, đúng theo yêu cầu "dừng sửa code cũ")

### 5.1 README.md link tới 3 file rule vừa xoá

`test_docs.py::test_every_link_in_a_document_resolves[README.md0]` đang đỏ —
README.md dòng 131–133 vẫn link `rulebase/rules/toner.yaml`/`drum.yaml`/
`rollers.yaml`. Hậu quả trực tiếp của việc xoá ở mục 4, chưa dọn nốt.

### 5.2 988 record trong `data/5k_llm/` chưa qua validate

Thiếu `word_annotations`/`layout_annotations` (tính năng thêm sau khi bộ này
được commit). Công cụ sửa có sẵn: `pipeline.record.migrate(Path('data/5k_llm'))`.
Đã ghi rõ trong `tests/test_record.py`, chưa chạy theo yêu cầu trước đó.

### 5.3 Hai hệ phân loại chứng từ song song

`agent/policy.py` (`locked`/`livery`/`free`) và `rulebase/augmentable.yaml`
(`fixed`/`styled`/`free`) — cùng trả lời câu "chứng từ này được đổi bố cục
tới đâu", khác tên mức, khác file, có thể lệch nhau mà không ai biết. Đây
nhiều khả năng chính là phần bạn gọi là **"rulebase đang bị hardcode/mixed"**
ở `agent/variants.py` (7 trục ghép tổ hợp, không phải 1-thuộc-tính-1-trọng-số
như phần còn lại của rule-base) — **chưa đi sâu phân tích, dừng lại theo yêu
cầu chuyển hướng.**

### 5.4 `docs/muc-tieu.md` + `docs/ke-hoach.md` có thể đã lỗi thời một phần

921 dòng, kế hoạch 10 việc (P1–P10) viết trước khi `agent/` tồn tại ở hình
hài hiện tại. Vài việc trông như đã làm dưới tên khác (P9 "chữ viết tay thật"
≈ WriteViT đã xong; P5 "tác nhân soạn bố cục" ≈ `agent/variants.py`) — **chưa
xác nhận chắc chắn, cần bạn đọc và đối chiếu**, không tự ý coi là trùng.

### 5.5 5–6 branch git cũ chưa xem xét

`redesign/html-first`, `visualize`, `table-merge-work`, `seal-pipeline` — lệch
nhiều so với `master` (127–251 commit). Theo yêu cầu trước đó: **bỏ qua, không
xử lý** cho tới khi bạn tự xem.

---

## 6. Hướng tiếp theo

Từ đây tập trung vào `agent/` (LLM), không sửa thêm code cũ trừ khi nó chặn
đường làm LLM. Việc cụ thể tiếp theo — **chưa chốt, cần bạn nói rõ** khi bắt
đầu phiên làm việc kế: sinh dữ liệu quy mô lớn hơn với vLLM thật, giải quyết
mục 5.3 (hai hệ phân loại song song), hay hướng khác trong mảng LLM.

## Liên quan

- [`agent/README.md`](../agent/README.md) — thiết kế đầy đủ hệ agent, bảy trục dressing, cơ chế coverage/pressure.
- [`docs/llm-in-pipeline.md`](llm-in-pipeline.md) — thiết kế cũ hơn (tiền-merge PR #24), một phần đã lỗi thời.
- [`README.md`](../README.md) mục 3 — kiến trúc pipeline đầy đủ.
