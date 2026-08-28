# `data/5k_llm` — 5000 trang do agent quyết định

Sinh bằng [`tools/agent_dataset.py`](../../tools/agent_dataset.py); cách agent
quyết định nằm trong [`agent/README.md`](../../agent/README.md).

```bash
python tools/agent_dataset.py -o data/5k_llm -n 5000 --seed 2026 --workers 3
```

## Cái gì nằm trong đây

Toàn bộ, ảnh và tất cả — 5000 trang cộng 5000 ảnh proof, khoảng 1,4 GB — theo
yêu cầu của chủ kho. Bộ được sinh thành **năm lô 1000 trang**, mỗi lô một
commit, để xem được trước khi lô sau vẽ.

| File | Nội dung |
| :--- | :--- |
| `agent_plan.json` | 5000 quyết định — `index`, `seed`, `force` (cả 8 thuộc tính), `by`, `note` |
| `rules/` | bộ luật của riêng lượt này: 7 thuộc tính gốc + `variant`, và thẻ hạng trên từng document |
| `agent_report.json` | phủ theo từng thuộc tính, chính sách, kho biến thể, thời gian từng chặng |
| `dataset.json` | bộ đã lắp, đúng schema mọi bộ khác trong kho |
| `html/` | 5000 ảnh + 5000 bản ghi + `synthesis.json` |
| `proof/` | 5000 ảnh proof — hộp nhãn vẽ đè, tô màu theo họ trường |

Chạy lại lệnh trên là có lại đúng bộ ấy — `seed` cố định và `force` ghi sẵn cho
từng trang.

## Dựng lại một trang bất kỳ

```python
import os, json
os.environ["VLM_RULES_ROOT"] = "data/5k_llm/rules"   # phải là bộ luật của lượt này

import rulebase
plan = {p["index"]: p for p in json.load(open("data/5k_llm/agent_plan.json"))}
page = plan[1234]
recipe, receipt, rng = rulebase.make_content(seed=page["seed"], force=page["force"])
```

`VLM_RULES_ROOT` là bắt buộc: thuộc tính `variant` chỉ tồn tại trong bộ luật
của lượt chạy, không có trong `rulebase/rules/` được ship — đó là điều giữ cho
mọi dataset cũ vẫn dựng lại được y nguyên.

## Kiểm

`tools/agent_dataset.py` chạy ba phép kiểm, mỗi phép bắt một thứ hai phép kia
không bắt được:

* `planner.verify()` — bốc lại từng quyết định qua `sample_recipe` **trước khi**
  mở trình duyệt;
* `planner.audit_drawn()` — đối chiếu `synthesis.json` với kế hoạch **sau khi**
  vẽ, tức là kiểm rằng kế hoạch thật sự tới được renderer;
* `pipeline/invariants.py` — từng ảnh, như mọi lượt chạy khác trong kho.
