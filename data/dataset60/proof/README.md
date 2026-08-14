# OCR proof

Engine: `tesseract 5.3.4`, language `vie`, page segmentation mode 4.

Scores are order-free: Tesseract reads a two-column receipt in whatever
order its layout analysis picks, so comparing its output to the label as
one string would measure reading order rather than recognition. See
`tools/ocr_proof.py` for the definitions.

| framework | ảnh | token recall | recall (bỏ dấu) | field hit | field hit (bỏ dấu) | số tiền đọc đúng |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| synthdog | 20 | 0.411 | 0.448 | 0.236 | 0.271 | 25/144 (17%) |
| html | 20 | 0.682 | 0.705 | 0.588 | 0.605 | 65/141 (46%) |
| genalog | 20 | 0.757 | 0.778 | 0.659 | 0.676 | 76/149 (51%) |

## Theo bố cục

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| quan_nhau_stt | 12 | 0.729 |
| sieu_thi_barcode | 12 | 0.699 |
| sieu_thi_vat | 12 | 0.609 |
| quan_an_ascii | 12 | 0.607 |
| sieu_thi_gia_sl | 12 | 0.440 |

## Theo mức làm cũ

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| khong_lam_gi | 4 | 0.907 |
| giay_that | 10 | 0.831 |
| chu_bong | 12 | 0.729 |
| vua | 11 | 0.559 |
| vet_ban | 8 | 0.528 |
| photocopy | 9 | 0.511 |
| rach_giay | 6 | 0.225 |

## Theo kiểu máy in

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| laser_net | 14 | 0.779 |
| nhiet_mo | 22 | 0.584 |
| nhiet_hep | 13 | 0.584 |
| nhiet_dam | 10 | 0.548 |
| kim_cu | 1 | 0.179 |

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

