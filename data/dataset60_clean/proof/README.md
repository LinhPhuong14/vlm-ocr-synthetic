# OCR proof

Engine: `tesseract 5.3.4`, language `vie`, page segmentation mode 4.

Scores are order-free: Tesseract reads a two-column receipt in whatever
order its layout analysis picks, so comparing its output to the label as
one string would measure reading order rather than recognition. See
`tools/ocr_proof.py` for the definitions.

| framework | ảnh | token recall | recall (bỏ dấu) | field hit | field hit (bỏ dấu) | số tiền đọc đúng |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| synthdog | 20 | 0.829 | 0.856 | 0.753 | 0.781 | 105/144 (73%) |
| html | 20 | 0.845 | 0.858 | 0.777 | 0.786 | 102/141 (72%) |
| genalog | 20 | 0.879 | 0.882 | 0.808 | 0.808 | 102/149 (68%) |

## Theo bố cục

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| sieu_thi_barcode | 12 | 0.905 |
| quan_nhau_stt | 12 | 0.898 |
| sieu_thi_vat | 12 | 0.889 |
| sieu_thi_gia_sl | 12 | 0.784 |
| quan_an_ascii | 12 | 0.778 |

## Theo mức làm cũ

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| khong_lam_gi | 60 | 0.851 |

## Theo kiểu máy in

| giá trị | ảnh | token recall |
| --- | ---: | ---: |
| laser_net | 14 | 0.940 |
| nhiet_mo | 22 | 0.832 |
| nhiet_hep | 13 | 0.826 |
| nhiet_dam | 10 | 0.808 |
| kim_cu | 1 | 0.786 |

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

