# hand12 — tờ mẫu **điền tay**, chạy thử đoạn dây WriteViT → engine HTML

12 ảnh, 6 bố cục, một renderer. Đây là lần đầu trong kho này một giá trị trên
tờ giấy **không phải chữ in**: nó là nét bút thật do WriteViT sinh ra, ghép vào
ô trống rồi làm cũ cùng tờ giấy. Cách nối và các phép đo nằm trong
[`docs/handwriting-html.md`](../../docs/handwriting-html.md).

| | |
| --- | --- |
| renderer | `html` (Chromium), page model `--template auto` |
| ghép cặp | `unpaired` — chỉ một renderer; đường WeasyPrint chưa nối được, xem tài liệu |
| làm cũ | có, rút từ luật: `pristine`, `light`, `ghost_text`, `real_paper`, `stains`, `torn_edges`, `photocopy_stamped`, `forwarded_photo` |
| box | 1 219 |
| chữ viết tay | **30 ô**, 10 người viết khác nhau, 3 màu mực |

## Sinh lại

```bash
python tools/writevit/setup.py                # một lần, ~294 MB, clone cạnh kho
generators/html/.venv/bin/python generators/html/render.py \
    --template auto --handwriting --jobs data/hand12/jobs.json -o data/hand12/html
```

## Điền được bao nhiêu, và cái gì chặn

Mỗi ảnh mang thêm một khối `handwriting` trong `metadata.jsonl`: người viết, màu
mực, cỡ chữ, danh sách ô đã điền, và **lý do từng ô bị từ chối**.

| bố cục | ô điền tay | ô vẫn in máy | vì sao bị từ chối |
| --- | ---: | ---: | --- |
| `invoice_hotel_stay` | **15** | 24 | 24 chữ số |
| `invoice_vat_form` | 8 | 19 | 18 chữ số, 1 ký tự ngoài bảng |
| `invoice_tax_en` | 4 | 10 | 6 chữ số, 4 IN HOA |
| `authorisation_letter` | 3 | 27 | 18 chữ số, 7 IN HOA, 2 ký tự ngoài bảng |
| `invoice_export` | **0** | 25 | 17 chữ số, 8 IN HOA |
| `medical_statement` | **0** | 24 | 21 chữ số, 3 IN HOA |
| | **30** | **129** | |

Hai bố cục cuối ra **không một nét nào**, và chúng có mặt ở đây chính vì thế: tờ
xuất khẩu in tên hàng IN HOA và phần còn lại là số; bảng kê bệnh viện thì mười
ba cột đều là tiền. Một tập chỉ gồm những tờ điền được sẽ nói dối về độ phủ.

Một trang **100 % điền tay không dựng được từ mô hình**. Quét cả không gian luật
— 11 bố cục có ô trường × mọi tuỳ chọn `content` hợp lệ × 40 hạt giống — trang
nhiều mực nhất đạt **42 %**. Chặn ở đó là chữ số, thứ mọi hoá đơn đều phải có.

Đổi sang nguồn mực thứ hai thì lấp hết. Cùng 12 trang này, cùng `jobs.json`,
chỉ thay `--handwriting font`: **159 ô điền tay, 0 ô in máy**, `check_boxes`
vẫn sạch. Cái giá là mặt chữ lặp lại — xem
[`samples/handwriting/`](../../samples/handwriting), nơi để hai tờ cạnh nhau.

```bash
generators/html/.venv/bin/python generators/html/render.py \
    --template auto --handwriting font --jobs data/hand12/jobs.json -o out/html
```

`invoice_hotel_stay` dẫn đầu vì nó có thứ không tờ nào khác có: **tên người ký**
in dưới hai ô chữ ký, mà tên người là chữ hoa đầu từ — đúng thứ checkpoint viết
tốt nhất. Bốn ô ký của `authorisation_letter` đều đề *"(Ký và ghi rõ họ tên)"*
và đều để trắng, vì tài liệu ấy không bật `signature_names`.

## Đã kiểm những gì

| phép đo | kết quả |
| --- | --- |
| `make check-boxes DATASET=data/hand12` | **sạch** — 1 219 hộp, mọi hộp trong khung và trên nét mực |
| `tests/test_handwriting.py::…does_not_change_what_the_page_says` | `labelled_runs` trước và sau khi điền bằng nhau, 6 họ tờ giấy |
| `generators/html/overlap.py` | **0** cặp hộp chữ chồng nhau >30 % |
| `pipeline/invariants.py` | **0** lỗi / 12 ảnh |
| sinh lại từ `jobs.json` | `metadata.jsonl` **trùng từng byte** — chọn người viết, màu mực, cỡ chữ đều rút từ hạt giống của trang |

Phép đo thứ hai là phép đo đáng giá nhất ở đây. Mực **thay cách vẽ một giá trị,
không thay giá trị** — nếu nó đổi nhãn thì `check_boxes` sẽ báo mọi ảnh mất
trường, còn nếu nó đổi nhãn im lặng thì tập dữ liệu sẽ mô tả một tờ giấy chưa
từng được vẽ.

## Đọc khối `handwriting`

```json
{
  "writer": 66,
  "pen": "#1c2a68",
  "height_em": 2.11,
  "inked": [{"kind": "invoice.field", "text": "Lê Thị Kiều Trinh"}],
  "printed": {"digit": 6}
}
```

`writer` là chỉ số người viết trong `VN.pickle` (106 người ở split train), giữ
nguyên cho cả trang — một tờ giấy do một người điền. `printed` đếm theo lý do
chứ không liệt kê chữ, vì lý do mới là thứ nói được điều gì cần sửa: `digit`
cần một đợt huấn luyện lại, `allcaps` cũng thế, `alphabet` thì chỉ cần một bảng
chữ rộng hơn.
