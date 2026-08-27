# layouts84 — mọi bố cục, hai lần, và **không hai ảnh liền kề nào cùng bố cục**

84 ảnh, **42 bố cục — mọi bố cục đang có**, mỗi bố cục hai trang. Đây là tập
đầu tiên sinh ra sau khi `pipeline/plan.py` đổi từ **xếp khối** sang **chia
bài**, và nó tồn tại để chứng minh đúng một tính chất:

    html_000  authorisation_letter    html_042  authorisation_letter
    html_001  eatery_ascii            html_043  eatery_ascii
    html_002  eatery_indexed          html_044  eatery_indexed
    …                                 …
    html_041  notebook_ledger         html_083  notebook_ledger

Vòng một hết 42 bố cục rồi mới sang vòng hai. Đọc theo thứ tự file, **không vị
trí nào có hai ảnh cùng bố cục đứng cạnh nhau** — kể cả chỗ nối giữa hai vòng
(`notebook_ledger` → `authorisation_letter`) và kể cả chỗ nối giữa hai shard.

Trước thay đổi ấy, tập này sẽ là 2 ảnh `authorisation_letter`, rồi 2 ảnh
`eatery_ascii`, … — một loader không xáo trộn đọc hết loại giấy này mới sang
loại khác.

| | |
| --- | --- |
| renderer | `html` (Chromium), page model `--template auto` |
| bố cục | **42 / 42**, mỗi bố cục 2 trang |
| box | **6 346** |
| hạt giống phân biệt | 84 / 84 |
| nhãn phân biệt | **83 / 84** — xem "Một chỗ chưa xong" bên dưới |
| làm cũ | có, rút từ luật: 20 giá trị `augmentation`, 16 `ornament`, 7 `visual`, cộng `toner`/`drum`/`rollers` |
| pairing | `paired` |

## Sinh lại

```bash
generators/html/.venv/bin/python pipeline/run.py -c pipeline.yaml \
    -o data/layouts84 --workers 4          # với run.per_backend: 84
```

`per_backend: auto` trong `pipeline.yaml` cho **một** ảnh mỗi bố cục (42);
tập này đặt 84 để có hai vòng, vì tính chất "liền kề khác nhau" chỉ có gì để
chứng minh khi có nhiều hơn một vòng.

Ảnh thứ k của một bố cục vẫn là hạt giống thứ k của khối bố cục đó, y như
trước khi chia bài — nên đây là đổi **thứ tự**, không đổi một trang nào. Cách
tính hạt giống nằm trong `pipeline/plan.py`, và `plan.json` của lượt chạy ghi
lại đúng những gì đã sinh ra tập này.

## Thời gian

Đo bằng `imagetimes.jsonl` nằm cạnh ảnh (mỗi ảnh một dòng, kèm chặng
`draw`/`write`):

| | giây |
| --- | ---: |
| trung bình mỗi ảnh | 2,42 |
| trung vị | 2,18 |
| p95 | 4,87 |
| chậm nhất (`html_040`, `newspaper_front_broadsheet`) | 7,25 |
| tổng thời gian vẽ (cộng dồn mọi worker) | 203,5 |
| thời gian thực của lượt chạy, 4 worker, 5 shard | **61,1** |

Con số này là **thuộc tính của cái máy đã vẽ**, không phải của tập dữ liệu:
nó không lặp lại được và không có gì so sánh nó giữa hai lượt chạy. Đó cũng là
lý do nó nằm ở file riêng chứ không nằm trong `synthesis.json` — file kia bị
`tools/baseline.py` băm để chứng minh một worker và tám worker cho ra đúng
từng byte.

## Một chỗ chưa xong

84 ảnh nhưng chỉ **83 nhãn phân biệt**: `magazine_contents` ở hạt giống 35026
và 35027 cho ra ground truth **trùng từng byte**. Chuyện này **không phải do
chia bài** — hai hạt giống ấy là đúng hai hạt mà bất kỳ kế hoạch nào cỡ này
cũng bốc cho bố cục đó. Nó là một trường nội dung không đổi theo hạt giống
trong corpus periodical, và lượt chạy đã báo đúng như vậy:

    [FAIL] assembly: html: 84 images but only 83 distinct labels

Tập này được commit **kèm cả lỗi ấy**, không phải sinh lại cho đẹp: một tập
khai 84 mẫu phân biệt trong khi chỉ có 83 là thứ `pipeline/run.py` được viết ra
để phát hiện, và đây là bằng chứng nó phát hiện được.
