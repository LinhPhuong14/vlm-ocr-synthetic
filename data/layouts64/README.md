# layouts64 — mọi bố cục **đang bật**, hai lần, không hai ảnh liền kề nào cùng bố cục

64 ảnh, **32 bố cục — mọi bố cục đang bật**, mỗi bố cục hai trang.

Con số trong tên là số bố cục nhân hai, và nó **phải đổi khi số ấy đổi** — cùng
quy ước với `hand18_model` và với các kế hoạch của `tools/baseline.py`. Tập này
từng tên `layouts84` khi kho còn 42 bố cục bật; mười bố cục **root 3
(Form / Application)** đã tắt (`enabled: false`), nên nó thành 64. Một tập tên
"84" mà khai "mọi bố cục" trong khi chỉ còn 32 là một tập nói dối về chính nó.

Mười bố cục đã tắt vẫn còn nguyên file trên đĩa và vẫn dựng lại được khi gọi
đích danh; xem `rulebase/layout.py::available` và `every`.

## Hai tính chất tập này dùng để chứng minh

**Một — chia bài, không xếp khối.**

    html_000  authorisation_letter    html_032  authorisation_letter
    html_001  eatery_ascii            html_033  eatery_ascii
    …                                 …
    html_031  notebook_ledger         html_063  notebook_ledger

Vòng một hết 32 bố cục rồi mới sang vòng hai. Đọc theo thứ tự file, **không vị
trí nào có hai ảnh cùng bố cục đứng cạnh nhau** — kể cả chỗ nối hai vòng
(`notebook_ledger` → `authorisation_letter`) và chỗ nối hai shard.

**Hai — hoạ tiết được in ra thật.** `ornament` là thuộc tính từng được bốc, được
ghi vào `synthesis.json` và **không renderer nào vẽ**; `generators/html/ornament.py`
là nửa còn thiếu ấy. Trong tập này: **48 dấu trên 33 / 64 trang**, trong đó 31
dấu đặt theo box thật của trang (`"placed": "boxes"`) và 17 rơi vào vị trí dự
phòng vì bố cục ấy không có khối tương ứng.

| | |
| --- | --- |
| renderer | `html` (Chromium), page model `--template auto` |
| bố cục | **32 / 32 đang bật**, mỗi bố cục 2 trang |
| box | **5 530** |
| hạt giống phân biệt | 64 / 64 |
| nhãn phân biệt | **64 / 64** |
| làm cũ | 17 giá trị `augmentation`, 7 `visual`, 4 `toner`, 3 `drum` |
| hoạ tiết in ra | 48 dấu / 33 trang, 15 giá trị `ornament` |
| pairing | `paired` |
| verdict | **PASS** — 4/4 shard, 4/4 cổng kiểm tra |

```json
"ornament": {"ornament": "qr_and_seal", "marks": [
  {"pattern": "qr_verify_sample", "anchor": "letterhead",
   "placed": "boxes", "box": [72, 72, 941, 148], "from_receipt": false},
  {"pattern": "seal_name_block_chief", "anchor": "signature_seller",
   "placed": "boxes", "box": [463, 549, 551, 564]}]}
```

`"from_receipt": false` là khoảng cách được khai chứ không giấu: luật muốn mã
vạch/QR mã hoá **số hoá đơn của chính trang này**, còn `textures/ornament/` mới
có ảnh mẫu. Không nhãn nào khai mã ấy nên trang không nói dối — nhưng ai định
giải mã mã vạch trong tập này thì phải biết trước.

**Dấu không mang nhãn**: không box nào được thêm cho con dấu, đúng luật mà mực
chữ ký đang theo — dấu là mực trên giấy, không phải một trường của chứng từ.

## Sinh lại

```bash
generators/html/.venv/bin/python pipeline/run.py -c pipeline.yaml \
    -o data/layouts64 --workers 4          # với run.per_backend: 64
```

`per_backend: auto` trong `pipeline.yaml` cho **một** ảnh mỗi bố cục (32); tập
này đặt 64 để có hai vòng, vì tính chất "liền kề khác nhau" chỉ có gì để chứng
minh khi có nhiều hơn một vòng.

Ảnh thứ k của một bố cục vẫn là hạt giống thứ k của khối bố cục đó, nên chia
bài là đổi **thứ tự**, không đổi một trang nào.

## Thời gian

Đo bằng `imagetimes.jsonl` nằm cạnh ảnh (mỗi ảnh một dòng, kèm chặng
`draw`/`write`):

| | giây |
| --- | ---: |
| trung bình mỗi ảnh | 2,28 |
| trung vị | 2,08 |
| p95 | 4,42 |
| chậm nhất (`html_060`, `medical_statement`) | 7,25 |
| thời gian thực của lượt chạy, 4 worker, 4 shard | **48,3** |

Con số này là **thuộc tính của cái máy đã vẽ**, không phải của tập dữ liệu: nó
không lặp lại được và không có gì so sánh nó giữa hai lượt chạy. Đó cũng là lý
do nó nằm ở file riêng chứ không nằm trong `synthesis.json` — file kia bị
`tools/baseline.py` băm để chứng minh một worker và tám worker cho ra đúng từng
byte.

## Ghi chú: `layouts84` đã báo một lỗi mà tập này không báo

Bản 84 ảnh trước đó dừng ở **83 nhãn phân biệt**: `magazine_contents` ở hai hạt
giống liền nhau cho ra ground truth trùng từng byte. Tập 64 ảnh này không gặp
lại **không phải vì lỗi đã sửa** — số bố cục đổi thì khối hạt giống của
`magazine_contents` dịch đi, thế thôi. Lỗi vẫn còn trong corpus periodical.
