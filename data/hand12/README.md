# hand12 — tờ mẫu **điền tay**, mọi ô là nét bút

12 ảnh, 6 bố cục, một renderer. Trên mỗi tờ, **mọi giá trị người ta điền vào đều
là chữ viết tay** — 159 ô, không ô nào còn in máy — rồi cả tờ được làm cũ cùng
nhau. Cách nối và các phép đo nằm trong
[`docs/handwriting-html.md`](../../docs/handwriting-html.md).

| | |
| --- | --- |
| renderer | `html` (Chromium), page model `--template auto` |
| nguồn mực | **`font`** — mặt chữ viết tay có giấy phép trong [`fonts/hand/`](../../fonts/hand) |
| ô điền tay | **159 / 159** — 0 ô in máy |
| làm cũ | có, rút từ luật: `pristine`, `light`, `ghost_text`, `real_paper`, `stains`, `torn_edges`, `photocopy_stamped`, `forwarded_photo` |
| box | 1 219 |

## Sinh lại

```bash
generators/html/.venv/bin/python generators/html/render.py \
    --template auto --handwriting font --jobs jobs.json -o html
```

hoặc `make handwriting`. Không cần WriteViT: nguồn `font` chỉ đọc hai file trong
`fonts/hand/`, cả hai đã nằm trong kho.

| bố cục | ô điền tay |
| --- | ---: |
| `invoice_hotel_stay` | 39 |
| `authorisation_letter` | 30 |
| `invoice_vat_form` | 27 |
| `invoice_export` | 25 |
| `medical_statement` | 24 |
| `invoice_tax_en` | 14 |
| | **159** |

## Vì sao là `font` chứ không phải mô hình

Có hai nguồn mực và chúng **không thay thế nhau**.

`model` là WriteViT — một bộ sinh có điều kiện theo người viết, nét mỗi lần một
khác, 106 người. Nhưng nó **không viết được chữ số**, mà chữ số là số hoá đơn,
ngày, mã số thuế, số tài khoản. Trên đúng 12 trang này nó điền được **30 ô và để
lại 129 ô in máy**; quét cả không gian luật thì trang nhiều mực nhất chỉ đạt
42 %.

`font` lấp hết, vì một mặt chữ có đủ mười chữ số và mọi dấu. **Cái giá là nó
lặp**: một tờ là một nét chữ, và có **hai** mặt chữ chứ không phải 106 người
viết — mọi chữ `a` trên một trang là cùng một chữ `a`. Không có chỗ nào làm lệch
từng ký tự để giấu điều đó; làm lệch chính là thứ `ff9a9f0` đã gỡ.

`record["handwriting"]["source"]` khai nguồn trên từng ảnh, nên một tập không
thể nhận mình là đằng này rồi thực ra là đằng kia.

**Sau đợt sinh lại này, không tập dữ liệu nào trong kho còn mang mực của mô
hình.** Trang mực-mô-hình duy nhất còn lại là
[`samples/handwriting/hand-filled-folio.jpg`](../../samples/handwriting) — một
tờ để nhìn, không làm cũ, ở mức phủ cao nhất mô hình đạt được.

## Đã kiểm những gì

| phép đo | kết quả |
| --- | --- |
| `make check-boxes DATASET=data/hand12` | **sạch** — 1 219 hộp, mọi hộp trong khung và trên nét mực |
| `tests/test_handwriting.py::…does_not_change_what_the_page_says` | `labelled_runs` trước và sau khi điền bằng nhau, 6 họ tờ giấy |
| `generators/html/overlap.py` | **0** cặp hộp chữ chồng nhau >30 % |
| `pipeline/invariants.py` | **0** lỗi / 12 ảnh |
| sinh lại từ `jobs.json` | `metadata.jsonl` **trùng từng byte** — mặt chữ, màu mực, cỡ chữ đều rút từ hạt giống của trang |

Phép đo thứ hai là phép đo đáng giá nhất ở đây. Mực **thay cách vẽ một giá trị,
không thay giá trị** — nếu nó đổi nhãn thì `check_boxes` sẽ báo mọi ảnh mất
trường, còn nếu nó đổi nhãn im lặng thì tập dữ liệu sẽ mô tả một tờ giấy chưa
từng được vẽ.

Nguồn `font` đặt chữ bằng CSS chứ không dán ảnh, nên một giá trị dài **xuống
dòng** như chữ thường và được cắt hộp theo từng dòng — thứ một ảnh mực không làm
được. Đó cũng là lý do trang dài ra so với bản in máy: `medical_statement` cao
2 809 px thay vì 2 692.

## Đọc khối `handwriting`

```json
{
  "source": "font",
  "writer": 66,
  "pen": "#1c2a68",
  "height_em": 2.11,
  "inked": [{"kind": "invoice.field", "text": "Lê Thị Kiều Trinh"}],
  "printed": {}
}
```

`writer` giữ nguyên tên cũ và vẫn rút từ hạt giống của trang; với nguồn `font`
nó chọn **mặt chữ** (`writer % 2`) chứ không chọn người viết trong `VN.pickle`.
`printed` rỗng ở mọi ảnh của tập này — đếm theo lý do chứ không liệt kê chữ, vì
lý do mới là thứ nói được điều gì cần sửa.
