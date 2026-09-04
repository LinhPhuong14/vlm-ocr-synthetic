# Ba renderer còn một — quyết định và hệ quả

Kho này dựng quanh **ba renderer vẽ cùng một tờ giấy ba cách**, và `pairing:
paired` tồn tại để phép so sánh ấy có nghĩa. Đó không còn là điều nó phục vụ.

| | trước | nay |
| --- | --- | --- |
| `html` (Chromium) | một trong ba | **renderer duy nhất sinh dataset** |
| `synthdog` (synthtiger) | renderer lưới ký tự | **đã xoá khỏi cây mã** |
| `genalog` (WeasyPrint) | renderer thứ ba | **đã xoá khỏi cây mã** |

Việc xoá diễn ra hai bước, cách nhau một quãng: trước hết chúng rời khỏi danh
sách backend nhưng vẫn nằm trên đĩa; sau đó mới bị xoá hẳn. Trang này ghi cả
hai, vì lý do của bước một là lý do kỹ thuật, còn bước hai chỉ là hệ quả.

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

## Xoá renderer không xoá được trang nó đã vẽ

`generators/genalog/` và `generators/synthdog/` không còn trên đĩa. **115 trang
chúng đã vẽ thì vẫn được commit** — `data/dataset60/`, `data/invoices54/`,
`data/forms16/`, `data/dataset_test/` — và vẫn phải đọc được. Nguyên tắc phân
đôi, giữ nguyên từ bước "nghỉ" sang bước "xoá":

> **Tắt phía *sinh*, giữ phía *đọc*.**

| công cụ | vai | trạng thái |
| --- | --- | --- |
| `pipeline/worker.BACKENDS` | điều phối tên → tiến trình | **chỉ `html`** |
| `pipeline/config.GONE_BACKENDS` | từ chối sớm, kèm lý do | chặn `genalog`, `synthdog` |
| `tools/generate_dataset.BACKENDS` | driver tuần tự | **chỉ `html`** |
| `tools/check_boxes.FRAMEWORKS` | **đọc** tập đã có | giữ cả ba |
| `pipeline/record.py`, `tools/ocr_proof.py`, `tools/monitor.py`, `pipeline/drift.py` | **đọc** | giữ cả ba |

Một công cụ đọc mà quên mất một renderer sẽ làm mù phần dữ liệu đã công bố, chứ
không làm sạch nó. Vì thế phía đọc không đổi một dòng nào — kể cả khi thư mục
renderer đã biến mất, tên `synthdog` và `genalog` vẫn nằm trong các bảng đọc, và
đó là cố ý.

`GONE_BACKENDS` cũng là cố ý, và không phải để tưởng nhớ: nếu bỏ hẳn hai tên đó
đi thì `backends: [genalog]` trong `pipeline.yaml` sẽ thành "không có backend
nào", tức chạy xong mà không vẽ gì, không lỗi. Một cái tên đã từng đúng phải báo
sai rõ ràng hơn một cái tên chưa từng có.

## Chỗ sẽ thấy khác

- `make setup` dựng **một** môi trường, không phải ba. `setup-synthdog` và
  `setup-genalog` không còn; `make receipts` và `make preview` cũng vậy, vì cả
  hai đều gọi backend lưới ký tự.
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
OpenCV — chúng **không** gọi synthtiger, chưa từng gọi. Đó là lý do chúng sống
sót qua lần xoá: phần "pattern" của kho này không nợ backend lưới ký tự dòng nào.
Cái thực sự mất đi cùng nó là `elements/background.py` và `elements/warp.py` —
nền và phép vặn giấy — hai thứ chỉ backend ấy dùng. `textures/` không đổi.

## Cái mất đi, nói thẳng

Bỏ hai renderer là bỏ **phép so sánh chéo**: `data/dataset60/` từng chứng minh
được "cùng hạt giống cho cùng chữ ở cùng cột, dù vẽ bằng glyph hay chụp từ trình
duyệt", và các tập mới sẽ không chứng minh được điều đó nữa. Xoá hẳn thì bỏ thêm
một thứ: **không dựng lại được**. Chừng nào mã còn trên đĩa, một lần chạy
`git stash` là kiểm chứng được lời khẳng định ấy lần nữa; giờ thì phải đi lấy
lịch sử git.

Đổi lại là một đường duy nhất để nuôi: một mô hình trang, một cách dựng hộp, một
môi trường — và một `make setup` không đòi Python 3.11, GTK, hay một bản
synthtiger ghim Pillow 9.5. Các tập đã công bố vẫn giữ nguyên bằng chứng cũ, và
mã đã xoá vẫn nằm trong lịch sử: `git log -- generators/synthdog` tìm ra nó.
