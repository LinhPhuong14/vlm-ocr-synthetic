# handwriting — hai tờ điền tay, hai nguồn mực

Hai tờ để nhìn, không phải một bộ dữ liệu — bộ dữ liệu là
[`data/hand12/`](../../data/hand12), dựng bằng nguồn `font`. Chúng khác nhau ở
đúng một thứ: **mực đến từ đâu**, và đó là toàn bộ sự đánh đổi.

`hand-filled-folio.jpg` là tờ mực-mô-hình **ở mức phủ cao nhất mô hình đạt
được**, tắt làm cũ để nhìn rõ nét bút. Muốn thấy nguồn `model` cư xử thế nào
trên cả không gian bố cục — kể cả chín trang nó không viết được gì — thì xem
[`data/hand18_model/`](../../data/hand18_model).

| | `hand-filled-form.jpg` | `hand-filled-folio.jpg` |
| --- | --- | --- |
| nguồn mực | **mặt chữ viết tay** (`fonts/hand/`) | **mô hình WriteViT** |
| ô điền tay | **9 / 9 — toàn bộ** | 5 / 12 |
| ô còn in máy | không | 7, tất cả đều là chữ số |
| nét chữ | một mặt chữ, mọi chữ `a` giống hệt nhau | sinh theo từng từ, mỗi lần một khác, 106 người viết |
| chữ số, IN HOA, dấu câu | viết được | **không viết được** |

```bash
# mọi giá trị là nét bút, chỉ nhãn là bản in
generators/html/render.py --template auto --handwriting font \
    --layout invoice_vat_form --force augmentation=pristine --seed 8

# mực thật của mô hình, ở mức phủ cao nhất nó đạt được
generators/html/render.py --template auto --handwriting model \
    --layout invoice_hotel_stay --force content=invoice_vi_upper \
    --force augmentation=pristine --seed 24
```

`*.json` bên cạnh là record của chính tờ ấy: hộp, nhãn, và
khối `handwriting` nói nguồn mực, ô nào là mực, ô nào vẫn in và vì sao. Cả hai
tắt làm cũ để nhìn rõ nét bút; bản có làm cũ ở `data/hand12/`.

## Vì sao cần hai

**Mô hình là thứ thật** — một bộ sinh có điều kiện theo người viết, nét mỗi lần
một khác. Nhưng nó **không viết được chữ số**, và chữ số là số hoá đơn, ngày,
mã số thuế, số tài khoản. Quét toàn bộ không gian luật — 11 bố cục có ô trường
× mọi tuỳ chọn `content` hợp lệ × 40 hạt giống — trang nhiều mực nhất chỉ đạt
**42 %**:

| bố cục | tốt nhất | |
| --- | ---: | --- |
| `invoice_hotel_stay` / `_compact` | **42 %** | 5/12 |
| `invoice_vat_form` | 33 % | 3/9 |
| `invoice_tax_en` | 29 % | 2/7 |
| `invoice_vat_summary` | 23 % | 3/13 |
| `authorisation_letter` | 20 % | 3/15 |
| `invoice_export` | 16 % | 4/25 |
| `medical_statement` | 12 % | 3/24 |

**Mặt chữ lấp hết**, vì một mặt chữ có đủ mười chữ số và mọi dấu. Cái giá là nó
**lặp lại**: một tờ là một nét chữ, mọi chữ `a` trên trang là cùng một chữ `a`,
và có hai mặt chữ chứ không phải 106 người viết. Không có chỗ nào làm lệch từng
ký tự để giấu chuyện đó — làm lệch chính là thứ `ff9a9f0` đã gỡ đi.

Cả hai đường đều được [`hoa-tiet-de-xuat.md`](../../docs/hoa-tiet-de-xuat.md)
nêu là hợp lệ: dữ liệu nét thật, **hoặc** một mặt chữ viết tay có giấy phép cho
phép phát hành lại. Đường thứ ba — huấn luyện tiếp WriteViT để nó biết chữ số —
mới là đường xoá được sự đánh đổi này, và nó cần một đợt huấn luyện có GPU.

Hai đường tắt đã đo và đã chết, để không ai thử lại:

| đường tắt | vì sao chết |
| --- | --- |
| cắt ảnh chữ số thật từ `VN.pickle` | cả kho VNOnDB có **đúng một** ảnh số `0`; `1.500.000` cần bốn |
| dùng checkpoint tiếng Anh `eng_ckpt.pth` | đã tải và chạy: `0 1 2 … 9` ra nét giống chữ cái. Lexicon IAM có **26 token chứa chữ số trên 460.907** — cùng lỗi lọc từ điển như bản tiếng Việt |

Chi tiết và cách nối trong [`docs/handwriting-html.md`](../../docs/handwriting-html.md).
