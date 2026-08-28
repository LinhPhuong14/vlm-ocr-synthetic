# layouts_all — mọi bố cục đang bật, hai lần, không hai ảnh liền kề nào cùng bố cục

84 ảnh, **42 bố cục — mọi bố cục đang bật**, mỗi bố cục hai trang. Verdict của
lượt chạy: **PASS**, 84/84 nhãn phân biệt.

## Vì sao tên không mang con số

Kho này có quy ước "số trong tên phải đổi khi số ấy đổi" (`hand18_model`), và
tập này đổi tên hai lần trong một ngày vì đúng quy ước đó: `layouts84` → 42 bố
cục; `layouts64` khi mười bố cục root Form tắt; rồi lại 84 khi root bảo hiểm
được gộp vào. Một cái tên phải sửa mỗi lần kho lớn lên là một cái tên sẽ có
ngày nói dối.

`tools/baseline.py` đã gặp đúng chuyện này và giải đúng cách: `n14`, `n26`,
`n36` thành **`all`**, "định nghĩa là mọi thứ đang ship, nên không bao giờ lệch
pha được với thứ đang ship". Tập này theo đó. Con số nằm ở bảng ngay dưới và
trong `dataset.json`, hai chỗ được sinh lại cùng ảnh.

## Bốn tính chất tập này dùng để chứng minh

**Một — chia bài, không xếp khối.**

    html_000  authorisation_letter    html_042  authorisation_letter
    html_001  eatery_ascii            html_043  eatery_ascii
    …                                 …
    html_041  notebook_ledger         html_083  notebook_ledger

Vòng một hết 42 bố cục rồi mới sang vòng hai. Đọc theo thứ tự file, **không vị
trí nào có hai ảnh cùng bố cục đứng cạnh nhau** — kể cả chỗ nối hai vòng và chỗ
nối hai shard.

**Hai — hoạ tiết được in ra thật.** `ornament` từng được bốc, được ghi vào
`synthesis.json` và **không renderer nào vẽ**. Tập này: **60 dấu trên 50 / 84
trang**, 36 dấu đặt theo box thật của trang (`"placed": "boxes"`) và 24 rơi vào
vị trí dự phòng vì bố cục ấy không có khối tương ứng.

**Ba — mực bút do LUẬT bốc.** `handwriting` là thuộc tính 7, đứng **trước**
`augmentation`, nên nét bút mờ và nhoè y như chữ in trên cùng trang. Tập này:
**12 / 84 trang điền tay, 158 ô có nét bút**.

**Bốn — mục lục tạp chí thôi lặp lại.** `magazine_contents` từng cho **6 nhãn
phân biệt trên 200 hạt giống**: `_build_toc` bốc một trong sáu tài liệu của
corpus rồi chép nguyên. Nay nó ghép lại từ chính corpus ấy — chọn bài đinh,
chọn mục, chọn bài trong mục, đánh số trang tăng dần — và cho **200/200**. Ba
builder periodical còn lại vốn đã ghép như thế và vốn đã 200/200; đây là cái
lệch duy nhất, và nó là lý do hai lượt chạy 84 ảnh trước đó dừng ở 83 nhãn.

| | |
| --- | --- |
| renderer | `html` (Chromium), page model `--template auto` |
| bố cục | **42 / 42 đang bật**, mỗi bố cục 2 trang |
| box | **6 241** |
| hạt giống phân biệt | 84 / 84 |
| nhãn phân biệt | **84 / 84** |
| loại chứng từ | 33 |
| làm cũ | 15 giá trị `augmentation` (7 đang tắt), 7 `visual` |
| hoạ tiết in ra | 60 dấu / 50 trang, 13 giá trị `ornament` |
| mực bút | 12 / 84 trang, 158 ô, nguồn `hand_font` |
| máy photo | tắt cả ba (`toner`/`drum`/`rollers` chỉ còn giá trị sạch) |
| pairing | `paired` |
| verdict | **PASS** — 4/4 shard, 4/4 cổng kiểm tra |

Trong 42 bố cục có **mười bố cục bảo hiểm** vừa gộp từ master (giấy chứng nhận
TNDS xe cơ giới, thẻ BHYT, đơn bảo hiểm hàng hoá, hợp đồng bảo hiểm tài sản…) —
đây là tập đầu tiên vẽ chúng cùng phần còn lại.

## Sinh lại

```bash
generators/html/.venv/bin/python pipeline/run.py -c pipeline.yaml \
    -o data/layouts_all --workers 4        # với run.per_backend: 84
```

`per_backend: auto` cho **một** ảnh mỗi bố cục (42); tập này đặt 84 để có hai
vòng, vì tính chất "liền kề khác nhau" chỉ có gì để chứng minh khi có nhiều hơn
một vòng.

## Thời gian

Đo bằng `imagetimes.jsonl` nằm cạnh ảnh:

| | giây |
| --- | ---: |
| trung bình mỗi ảnh | 1,40 |
| trung vị | 1,35 |
| p95 | 2,23 |
| chậm nhất (`html_038`, `medical_statement`) | 3,08 |
| thời gian thực của lượt chạy, 4 worker, 4 shard | **34,3** |

Con số này là **thuộc tính của cái máy đã vẽ**, không phải của tập dữ liệu: nó
không lặp lại được và không có gì so sánh nó giữa hai lượt chạy. Đó là lý do nó
nằm ở file riêng chứ không nằm trong `synthesis.json` — file kia bị
`tools/baseline.py` băm để chứng minh một worker và tám worker cho ra đúng từng
byte.
