# Ba renderer còn một — quyết định và hệ quả

Kho này dựng quanh **ba renderer vẽ cùng một tờ giấy ba cách**, và `pairing:
paired` tồn tại để phép so sánh ấy có nghĩa. Đó không còn là điều nó phục vụ.

| | trước | nay |
| --- | --- | --- |
| `html` (Chromium) | một trong ba | **renderer duy nhất sinh dataset** |
| `synthdog` (synthtiger) | renderer lưới ký tự | rời khỏi danh sách backend; phần còn lại là **sinh pattern** |
| `genalog` (WeasyPrint) | renderer thứ ba | **nghỉ** |

## Vì sao

**`synthdog` vẽ lưới ký tự, không vẽ tờ CSS.** Nó ghép từng glyph lên canvas và
không kẻ được một đường viền bảng, nên mọi bố cục thêm vào từ khi có
`generators/html/sheets/` — tờ mẫu GTGT có khung, bảng kê bệnh viện mười ba cột,
giấy uỷ quyền — nó không in được. `Config` từng có một luật riêng chỉ để chặn
một lượt chạy `--template` lỡ gọi kèm nó.

**`genalog` dựng lại hộp theo cách riêng.** `match_runs` đi song song giữa danh
sách run có nhãn và **lớp glyph của chính file PDF**, còn `html` đọc hộp từ DOM
đã dàn. Hai cách ấy là hai bản cài đặt của cùng một câu hỏi "run này nằm ở đâu
trên trang", và mỗi tính năng mới phải trả giá ở cả hai — chữ viết tay là ví dụ
gần nhất: nguồn `model` dán ảnh mực, không góp glyph nào, nên nó không đi được
đường PDF chút nào.

**`html` không có hai vấn đề trên.** Nó in mọi bố cục, đọc hộp từ chính DOM nó
vừa dàn, và là đường duy nhất cả hai nguồn mực viết tay chạy được.

## "Nghỉ" không phải là "xoá"

`generators/genalog/` và `generators/synthdog/` vẫn nằm trên đĩa, vẫn import
sạch, và **nửa dataset chúng đã vẽ vẫn được commit** — `data/dataset60/`,
`data/invoices54/`, `data/forms16/`, `data/dataset_test/`. Nguyên tắc phân đôi:

> **Tắt phía *sinh*, giữ phía *đọc*.**

| công cụ | vai | trạng thái |
| --- | --- | --- |
| `pipeline/worker.BACKENDS` | điều phối tên → tiến trình | **chỉ `html`** |
| `pipeline/config.RETIRED_BACKENDS` | từ chối sớm, kèm lý do | chặn `genalog`, `synthdog` |
| `tools/generate_dataset.BACKENDS` | driver tuần tự | **chỉ `html`** |
| `tools/check_boxes.FRAMEWORKS` | **đọc** tập đã có | giữ cả ba |
| `tools/ocr_proof.py`, `tools/monitor.py`, `pipeline/drift.py` | **đọc** | giữ cả ba |

Một công cụ đọc mà quên mất một renderer sẽ làm mù phần dữ liệu đã công bố, chứ
không làm sạch nó. Vì thế phía đọc không đổi một dòng nào.

## Chỗ sẽ thấy khác

- `make setup` dựng **một** môi trường, không phải ba. `setup-synthdog` và
  `setup-genalog` vẫn còn, cho ai muốn đọc lại tập cũ hoặc hồi sinh một backend.
- `pipeline.yaml` khai `backends: [html]`. Viết `genalog` vào đó là lỗi có kèm
  lý do, xảy ra **trước** khi vẽ bất cứ thứ gì.
- `--clean` không còn đi kèm lệnh render. Nó vốn tắt phần hình học *của riêng*
  backend lưới ký tự — độ cong tờ giấy và lần chụp lại — thứ mà chuỗi làm cũ
  không sở hữu. Không backend nào còn hình học kiểu ấy, nên một lượt chạy sạch
  giờ đúng bằng `augmentation=pristine`.
- `pairing` vẫn còn và số học seed trong `pipeline/plan.py` vẫn là N-backend.
  Đó là **cơ chế**, không phải quyết định biên tập; test của nó đặt tên backend
  riêng chứ không mượn tên thật, đúng như `tests/conftest.py` đã quy ước.

## Phần pattern

Cái mà mọi trang được ghép lên và đóng dấu — `textures/paper/`,
`textures/background/`, `textures/ornament/` — sinh bằng
[`tools/make_textures.py`](../tools/make_textures.py) và
[`tools/make_ornaments.py`](../tools/make_ornaments.py), gộp vào một tác vụ:

```bash
make patterns          # = make textures + make ornaments
```

Chúng sinh ra chứ không chụp lại, vì hai lẽ đã ghi trong chính hai file ấy: ảnh
chụp giấy thường không được phép phát hành lại, nên một bản clone mới sẽ không
có gì để ghép lên; và một hạt giống tái tạo đúng tờ giấy ấy, điều một bản scan
không làm được.

**Nói cho chính xác:** hai công cụ này chạy bằng bất kỳ Python nào có numpy và
OpenCV — chúng **không** gọi synthtiger. Cái thuộc về phía synthdog trong vai
trò pattern là `generators/synthdog/elements/` — `background.py` và `warp.py`,
tức nền và phép vặn giấy. Gọi đây là "phần pattern" là mô tả **vai trò còn lại**
của hướng ấy, không phải mô tả sai rằng synthtiger đang sinh ra các file trong
`textures/`.

## Cái mất đi, nói thẳng

Bỏ hai renderer là bỏ **phép so sánh chéo**: `data/dataset60/` từng chứng minh
được "cùng hạt giống cho cùng chữ ở cùng cột, dù vẽ bằng glyph hay chụp từ trình
duyệt", và các tập mới sẽ không chứng minh được điều đó nữa. Đổi lại là một
đường duy nhất để nuôi: một mô hình trang, một cách dựng hộp, một môi trường.
Các tập đã công bố vẫn giữ nguyên bằng chứng cũ.
