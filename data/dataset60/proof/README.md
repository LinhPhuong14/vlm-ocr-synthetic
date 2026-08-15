# OCR proof

Engine: `tesseract 5.3.4`, language `vie`, page segmentation mode 4.

Scores are order-free: Tesseract reads a two-column receipt in whatever
order its layout analysis picks, so comparing its output to the label as
one string would measure reading order rather than recognition. See
`tools/ocr_proof.py` for the definitions.

| framework | ảnh | token recall | recall (bỏ dấu) | field hit | field hit (bỏ dấu) | số tiền đọc đúng |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| synthdog | 20 | 0.370 | 0.402 | 0.223 | 0.260 | 27/144 (19%) |
| html | 20 | 0.682 | 0.705 | 0.588 | 0.605 | 65/141 (46%) |
| genalog | 20 | 0.757 | 0.778 | 0.659 | 0.676 | 76/149 (51%) |

## Theo bố cục

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| eatery_indexed | 12 | 0.716 |
| market_barcode | 12 | 0.658 |
| market_vat | 12 | 0.608 |
| eatery_ascii | 12 | 0.602 |
| market_compact | 12 | 0.432 |

## Theo mức làm cũ

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| pristine | 4 | 0.907 |
| real_paper | 10 | 0.822 |
| ghost_text | 12 | 0.691 |
| medium | 11 | 0.561 |
| stains | 8 | 0.517 |
| photocopy | 9 | 0.502 |
| torn_edges | 6 | 0.201 |

## Theo kiểu máy in

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| laser_sharp | 14 | 0.773 |
| thermal_narrow | 13 | 0.586 |
| thermal_faint | 22 | 0.555 |
| thermal_dark | 10 | 0.536 |
| dot_matrix | 1 | 0.162 |

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
khiển được độ khó**: `pristine` và `real_paper` ở trên cùng,
`crumpled` ở dưới cùng, đơn điệu suốt dải. Chỉnh `weight` trong
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

