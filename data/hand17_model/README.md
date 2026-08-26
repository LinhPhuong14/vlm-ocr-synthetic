# hand17_model — mực **của mô hình**, đo trên toàn bộ không gian bố cục

17 ảnh, **17 bố cục — mọi bố cục đang có**, một trang mỗi bố cục, một renderer.
Mực đến từ checkpoint WriteViT chứ không phải mặt chữ: `--handwriting model`.

Đây **không phải tập để huấn luyện**. Nó là một **phép đo**: nguồn `model` phủ
được bao nhiêu, ở đâu, và chỗ nào nó không phủ được gì cả. Muốn một tập mọi ô
đều là nét bút thì xem [`hand12/`](../hand12) — nguồn `font`, 159/159 ô.

| | |
| --- | --- |
| renderer | `html` (Chromium), page model `--template auto` |
| nguồn mực | **`model`** — WriteViT VNDB, 106 người viết, chạy CPU |
| ô có mực | **25 / 197 run được mời viết = 13 %** |
| trang không có một nét mực nào | **9 / 17** |
| làm cũ | có, rút từ luật — 10 kiểu khác nhau trên 17 trang |
| box | 1 489 |

## Sinh lại

```bash
generators/html/.venv/bin/python generators/html/render.py \
    --template auto --handwriting model --jobs jobs.json -o html
```

Cần WriteViT: `python tools/writevit/setup.py` (clone cạnh kho, 294 MB trọng số
và style pickle). Nguồn `model` **không có đường lùi** — thiếu checkpoint thì
lượt chạy dừng chứ không lặng lẽ in máy ra.

Mỗi bố cục có khối hạt giống riêng (`7000 + 100·i`), nên một trang là hàm của
hạt giống của chính nó chứ không phải của chỗ nó đứng trong danh sách. Sinh lại
từ `jobs.json` ra **trùng từng byte**.

## Phủ được bao nhiêu, theo từng bố cục

| bố cục | mực | từ chối | tỉ lệ | làm cũ |
| --- | ---: | ---: | ---: | --- |
| `invoice_hotel_stay` | 5 | 10 | **33 %** | heavy |
| `invoice_vat_form` | 3 | 6 | **33 %** | heavy |
| `invoice_tax_en` | 2 | 5 | 29 % | torn_edges |
| `invoice_hotel_compact` | 4 | 11 | 27 % | pristine |
| `invoice_brand` | 1 | 4 | 20 % | torn_edges |
| `invoice_power` | 2 | 9 | 18 % | photocopy_stamped |
| `notebook_ledger` | 5 | 41 | 11 % | stains |
| `invoice_export` | 2 | 23 | 8 % | real_paper |
| `authorisation_letter` | 1 | 14 | 7 % | photocopy |
| `invoice_vat_summary` | 0 | 13 | **0 %** | light |
| `invoice_water` | 0 | 12 | **0 %** | flatbed_scan |
| `medical_statement` | 0 | 24 | **0 %** | forwarded_photo |
| `eatery_ascii` | 0 | 0 | **—** | light |
| `eatery_indexed` | 0 | 0 | **—** | forwarded_photo |
| `market_barcode` | 0 | 0 | **—** | photocopy |
| `market_compact` | 0 | 0 | **—** | pristine |
| `market_vat` | 0 | 0 | **—** | stains |
| | **25** | **172** | **13 %** | |

Lý do từ chối, cộng cả tập: `digit` 139, `allcaps` 27, `alphabet` 6. Chữ số là
82 % — đúng con số [`docs/handwriting-html.md`](../../docs/handwriting-html.md)
đo trên 16 bố cục × 20 hạt giống, nên tập này không nói điều gì mới về *lý do*;
nó nói bố cục nào chịu hậu quả.

## Hai loại số 0, và chúng khác hẳn nhau

Chín trang không có mực, nhưng vì hai lý do hoàn toàn khác nhau — và cột `kinds`
trong nhãn là thứ phân biệt được:

**`0 / 0` — không một run nào được *mời* viết.** Năm bố cục hoá đơn tính tiền
(`eatery_*`, `market_*`) không có kind `invoice.field`, `invoice.words` hay
`sign.name` nào cả, vì hoá đơn tính tiền không có ô cho người ta điền. Bật
`--handwriting model` trên chúng **không làm gì hết**, kể cả một lần từ chối.
Không phải lỗi — máy tính tiền in ra cả tờ.

**`0 / 13`, `0 / 12`, `0 / 24` — có mời, mô hình từ chối sạch.** Ba tờ này toàn
số: mã khách hàng, chỉ số điện nước, mã thuốc. Đây mới là chỗ nguồn `model`
thua, và không có cách nào trèo qua bằng mẹo — xem *Bức tường chữ số* trong
`docs/handwriting-html.md`.

Không có cột `kinds` thì "0 mực" của hai loại trên trông giống hệt nhau, và một
người đọc sẽ kết luận sai về năm bố cục chẳng có gì sai.

## Một khuyết điểm nằm ngay trong tập này

Checkpoint viết **nát tên thương hiệu không phải tiếng Việt**. Trong
`html_016.jpg` (`notebook_ledger`), run `WinMart` ra một vệt không đọc được,
trong khi `Khăn giấy`, `Gừng ta` cùng trang thì đọc được. Nhãn vẫn khai
`WinMart` còn ảnh thì không phải chữ ấy.

Lỗi này **có từ trước** và thuộc về checkpoint, không thuộc về tập này — nhưng
nó ở đây, nên phải nói. Cách sửa hiển nhiên nhất lại sai: không phải "từ ngoài
từ điển", vì `Nguyễn` không có trong 10 131 từ của `vn_words.txt` mà vẫn viết ra
đọc được. `docs/handwriting-html.md` ghi lại phép đo thay vì đoán một luật.

## Đã kiểm những gì

| phép đo | kết quả |
| --- | --- |
| `make check-boxes DATASET=data/hand17_model` | **sạch** — 1 489 hộp, mọi hộp trong khung và trên nét mực |
| `generators/html/overlap.py` | **0** cặp hộp chồng nhau >30 % |
| `pipeline/invariants.py` | **0** lỗi / 17 ảnh, không ngân sách nào vỡ |
| sinh lại từ `jobs.json` | trùng từng byte |

Một chú ý về phép kiểm đầu: `check_boxes` đọc `template` trong `dataset.json`,
và **thiếu file ấy thì nó mặc định là lưới ký tự** rồi báo 304 lỗi giả trên
đúng tập này. Đó là cái bẫy `sheets/__init__.py` nói tới — page model không bao
giờ được để mặc định.

## Đọc khối `handwriting`

Nằm trong `html/synthesis.json`, dưới `pages["html_000.jpg"]`:

```json
"handwriting": {
  "source": "model",
  "writer": 22,
  "pen": "#1c2a68",
  "height_em": 2.14,
  "kinds": ["invoice.field", "invoice.words", "sign.name"],
  "inked": [{"kind": "invoice.field",
             "text": "Một triệu không trăm bốn mươi tư nghìn đồng"}],
  "printed": {"allcaps": 4, "digit": 9, "alphabet": 1}
}
```

`kinds` là trường mới và là trường phân biệt hai loại số 0 ở trên: `"all"` nghĩa
là cả trang là phần người ta viết (chỉ `notebook_ledger`), còn danh sách nghĩa
là tờ in sẵn và chỉ những ô ấy mới đến lượt cây bút.
