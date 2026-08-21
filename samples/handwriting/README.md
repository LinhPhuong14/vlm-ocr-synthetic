# handwriting — một trang điền tay, ở mức tối đa mô hình làm được

`hand-filled-folio.jpg` là **trang nhiều mực nhất** dựng được từ luật hiện có:
folio khách sạn, nhãn in sẵn, **5 trong 12 ô giá trị là nét bút thật**. Đây là
tờ để nhìn, không phải một bộ dữ liệu — bộ dữ liệu là
[`data/hand12/`](../../data/hand12), 12 trang có làm cũ.

```bash
generators/html/.venv/bin/python generators/html/render.py \
    --template auto --handwriting --layout invoice_hotel_stay \
    --force content=invoice_vi_upper --force augmentation=pristine \
    --seed 24 -c 1 -o samples/handwriting
```

`hand-filled-folio.json` là bản ghi `metadata.jsonl` của chính trang ấy: hộp,
nhãn, và khối `handwriting` nói ô nào là mực, ô nào vẫn in và vì sao.

| | |
| --- | --- |
| viết tay | Khách hàng, Loại phòng, Nguồn khách, và **hai tên dưới ô ký** |
| vẫn in máy | Số hoá đơn `HD4488`, Ngày, Phòng `1201`, Ngày nhận, Ngày trả, Số đêm `3`, Số khách `2` |
| lý do | cả bảy đều là **chữ số** |
| làm cũ | tắt (`pristine`), để nhìn rõ nét bút — bản có làm cũ ở `data/hand12/` |

## 42 % là trần, không phải may rủi

Quét toàn bộ không gian luật — 11 bố cục có ô trường × mọi tuỳ chọn `content`
hợp lệ × 40 hạt giống — không trang nào vượt được **42 %**:

| bố cục | tốt nhất | |
| --- | ---: | --- |
| `invoice_hotel_stay` / `_compact` | **42 %** | 5/12 |
| `invoice_vat_form` | 33 % | 3/9 |
| `invoice_tax_en` | 29 % | 2/7 |
| `invoice_vat_summary` | 23 % | 3/13 |
| `authorisation_letter` | 20 % | 3/15 |
| `invoice_export` | 16 % | 4/25 |
| `medical_statement` | 12 % | 3/24 |

Ghim `content` bỏ được **toàn bộ** nhóm bị chặn vì IN HOA — chữ hoa toàn phần là
do `prob_uppercase` và `prob_ascii_fold` trong luật, không phải bản chất tài
liệu. Bỏ xong thì thứ duy nhất còn đứng là **chữ số**, và nó không bỏ đi được:
mọi hoá đơn trong kho đều có số hoá đơn, ngày, mã số thuế, số tài khoản. Một
trang **100 % điền tay không dựng được** từ mô hình hiện tại — không phải vì
chưa tìm đúng hạt giống, mà vì đó là thứ tài liệu này *là*.

Bốn đường mở nốt chỗ ấy, hai đường đã đo và đã chết:

| đường | trạng thái |
| --- | --- |
| cắt ảnh chữ số thật từ `VN.pickle` | **chết** — cả kho có đúng một ảnh số `0` |
| dùng checkpoint tiếng Anh (`eng_ckpt.pth`) | **chết** — đã tải và chạy thử: `0 1 2 … 9` ra nét giống chữ cái. Lexicon IAM có 26 token chứa chữ số trên 460.907, tức bộ sinh gần như chưa từng thấy chữ số, đúng lỗi lọc từ điển như bản tiếng Việt |
| huấn luyện tiếp WriteViT cho `lex_upper_number` | làm được, cần GPU và một đợt huấn luyện |
| một **mặt chữ viết tay** có giấy phép phát hành lại | làm được ngay, nhưng đổi bản chất nguồn mực — [`hoa-tiet-de-xuat.md`](../../docs/hoa-tiet-de-xuat.md) có nêu đây là đường hợp lệ |

Chi tiết và cách nối trong [`docs/handwriting-html.md`](../../docs/handwriting-html.md).
