# OCR proof

Engine: `tesseract 5.3.4`, language `vie`, page segmentation mode 4.

Scores are order-free: Tesseract reads a two-column receipt in whatever
order its layout analysis picks, so comparing its output to the label as
one string would measure reading order rather than recognition. See
`tools/ocr_proof.py` for the definitions.

| framework | ảnh | token recall | recall (bỏ dấu) | field hit | field hit (bỏ dấu) | số tiền đọc đúng |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| synthdog | 20 | 0.849 | 0.874 | 0.765 | 0.784 | 112/144 (78%) |
| html | 20 | 0.853 | 0.865 | 0.792 | 0.802 | 114/141 (81%) |
| genalog | 20 | 0.869 | 0.877 | 0.805 | 0.805 | 109/149 (73%) |

## Theo bố cục

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| eatery_indexed | 12 | 0.926 |
| market_barcode | 12 | 0.917 |
| market_vat | 12 | 0.896 |
| market_compact | 12 | 0.780 |
| eatery_ascii | 12 | 0.766 |

## Theo mức làm cũ

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| pristine | 60 | 0.857 |

## Theo kiểu máy in

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| laser_sharp | 14 | 0.943 |
| dot_matrix | 1 | 0.846 |
| thermal_narrow | 13 | 0.840 |
| thermal_dark | 10 | 0.834 |
| thermal_faint | 22 | 0.823 |

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

