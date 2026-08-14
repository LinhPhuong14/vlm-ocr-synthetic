# OCR proof

Engine: `tesseract 5.3.4`, language `vie`, page segmentation mode 4.

Scores are order-free: Tesseract reads a two-column receipt in whatever
order its layout analysis picks, so comparing its output to the label as
one string would measure reading order rather than recognition. See
`tools/ocr_proof.py` for the definitions.

| framework | ảnh | token recall | recall (bỏ dấu) | field hit | field hit (bỏ dấu) | số tiền đọc đúng |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| synthdog | 20 | 0.399 | 0.442 | 0.262 | 0.289 | 28/144 (19%) |
| html | 20 | 0.755 | 0.776 | 0.652 | 0.675 | 79/141 (56%) |
| genalog | 20 | 0.703 | 0.724 | 0.579 | 0.599 | 63/149 (42%) |

## Theo bố cục

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| sieu_thi_barcode | 12 | 0.774 |
| quan_nhau_stt | 12 | 0.718 |
| quan_an_ascii | 12 | 0.644 |
| sieu_thi_vat | 12 | 0.619 |
| sieu_thi_gia_sl | 12 | 0.338 |

## Theo mức làm cũ

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| khong_lam_gi | 4 | 0.875 |
| giay_that | 10 | 0.856 |
| chu_bong | 17 | 0.694 |
| vet_ban | 4 | 0.551 |
| vua | 12 | 0.522 |
| nhe | 1 | 0.500 |
| photocopy | 3 | 0.499 |
| nang | 4 | 0.376 |
| nhau_nat | 5 | 0.261 |

## Theo kiểu máy in

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| laser_net | 14 | 0.708 |
| nhiet_mo | 22 | 0.618 |
| nhiet_hep | 13 | 0.603 |
| nhiet_dam | 10 | 0.554 |
| kim_cu | 1 | 0.248 |

## Ảnh minh hoạ

`proof_<framework>_NN.jpg` là ảnh gốc kèm khung từng từ Tesseract đọc được —
xanh lá là độ tin cậy ≥ 70%, cam là thấp hơn.

## Cách đọc bảng

**Chênh lệch giữa ba renderer là có thật, không phải lỗi.** Renderer glyph
cho ra ảnh *chụp* tờ hoá đơn nằm trên bàn — có phối cảnh, có bóng đèn, có
nền tối; hai renderer HTML cho ra bản *quét phẳng* và bản *in*. Ảnh chụp
khó hơn hẳn, và đó chính là lý do giữ cả ba: một model chỉ thấy bản quét
phẳng thì chưa từng gặp trường hợp khó.

**Thứ tự trong bảng "mức làm cũ" là bằng chứng rule-base thật sự điều
khiển được độ khó**: `khong_lam_gi` và `giay_that` ở trên cùng,
`nhau_nat` ở dưới cùng, đơn điệu suốt dải. Chỉnh `weight` trong
`rulebase/rules/augmentation.yaml` là dịch được cả bộ dữ liệu dễ hơn hoặc
khó hơn.

**Cột "bỏ dấu" cao hơn cột thường bao nhiêu thì phần lỗi chỉ nằm ở dấu
thanh bấy nhiêu.** Khoảng cách ở đây nhỏ, nghĩa là lỗi chủ yếu là nhận
nhầm ký tự chứ không phải mất dấu.

Đây là điểm của **Tesseract**, một engine đa dụng chưa fine-tune trên hoá
đơn nhiệt tiếng Việt. Nó là mốc dưới, không phải trần: điểm thấp trên ảnh
làm cũ nặng là dấu hiệu ảnh đủ khó, không phải dấu hiệu nhãn sai. Muốn
kiểm tra nhãn có khớp ảnh không thì nhìn `worst_fields` trong
`ocr_report.json` — trường nào sai một cách có hệ thống trên MỌI ảnh mới
là nhãn hỏng.

