# forms16 — hai chứng từ KHÔNG phải hoá đơn, chạy thử end-to-end

16 ảnh: **2 bố cục × 4 ảnh × 2 renderer**. Đây là lần đầu bộ sinh dựng ra thứ
không ghi lại một lần mua bán — và là bản chạy thử của đúng hai mẫu được phân
tích trong [`docs/phan-tich-2-mau-moi.html`](../../docs/phan-tich-2-mau-moi.html).

| bố cục | tờ giấy | mô hình |
| --- | --- | --- |
| `medical_statement` | Bảng kê chi phí điều trị nội trú (Mẫu số 01/KBCB) | bảng **13 cột**, tiêu đề hai tầng, dòng nhóm mang số cộng, khối quyết toán chia bốn nguồn |
| `authorisation_letter` | Giấy uỷ quyền nhận tiền của công ty bảo hiểm | **không có bảng nào cả** — hai khối trường dưới dải tiêu đề, dòng chấm để điền |

| | |
| --- | --- |
| renderer | `html` (Chromium) và `genalog` (WeasyPrint) |
| ghép cặp | `paired` — nhãn của cặp ảnh cùng chỉ số giống nhau 8/8 |
| làm cũ | có, rút từ luật: `medium`, `pristine`, `ghost_text`, `photocopy`, `stains`, `flatbed_scan` |
| box | 2 200 (html) / 2 204 (genalog) |

## Sinh lại

```bash
python tools/generate_dataset.py -o data/forms16 -n 8 \
    --frameworks html genalog --template --workers 2 \
    --layouts medical_statement authorisation_letter
```

## Đã kiểm những gì

| phép đo | kết quả |
| --- | --- |
| `pipeline/invariants.py` | **0** lỗi / 16 ảnh |
| `generators/html/overlap.py` | **0** cặp box chữ chồng nhau >30%, cả hai renderer |
| `make check-boxes DATASET=data/forms16` | mọi đoạn chữ có nhãn đều có box, box nào cũng nằm trên nét mực |
| lưới ký tự in đủ nhãn | 0 giá trị nhãn không được in, 5 seed × 2 bố cục |

## Bảng kê 01/KBCB: phép tính đóng lại

Mỗi dòng được định giá **hai lần** — một theo giá bệnh viện (`Đơn giá BV`), một
theo giá bảo hiểm cho phép (`Đơn giá BH`) — rồi số tiền chia làm **bốn nguồn**:

```
quỹ BHYT + người bệnh cùng chi trả + khác (miễn giảm) + người bệnh tự chi trả
    =  tổng chi phí
```

Bốn nguồn ấy được TÍNH TỪ các dòng chứ không bốc ra, nên phép cộng đóng lại
đúng bằng tổng — kiểm được từ chính nhãn, và đó là loại bất biến mà
[`pipeline/invariants.py`](../../pipeline/invariants.py) đang canh cho mọi
chứng từ khác.

Dòng nhóm ("3. Xét nghiệm") là **một dòng của bảng**, không phải cái tít trôi
phía trên: nó mang số cộng của nhóm. Nhưng nó **không nằm trong `menu`** của
nhãn — `menu` là danh sách các dòng hàng, và số cộng của một nhóm đã có sẵn
trong các dòng của nhóm ấy. Nó vẫn được vẽ và vẫn có box.

Trang thứ hai của bảng **không lặp lại tiêu đề**, đúng như tờ mẫu
(`repeat_header: false` trong file bố cục).

## Giấy uỷ quyền: chỗ chưa đạt, nói trước

Trên tờ giấy thật, **mọi giá trị đều viết tay** — tên in hoa, số CMND, ngày
cấp, địa chỉ, số tiền bằng chữ, và bốn chữ ký. Bản sinh này **đánh máy** chúng.

Ảnh vẫn đúng nhãn, box vẫn đúng chỗ, và tờ giấy vẫn là một tờ giấy hợp lệ. Nhưng
một mô hình chỉ học từ đây sẽ học đọc một loại biểu mẫu **không ai điền bằng máy
in**. Bộ nét tay cũ đã bị gỡ theo đánh giá "các nét tay đều không đạt yêu cầu";
tờ này chờ một nguồn chữ viết tay tiếng Việt tử tế trước khi dùng được cho việc
huấn luyện đọc trường điền.

Dùng nó cho cái gì thì được ngay: bố cục, khối trường, dải tiêu đề, mã vạch,
khung, chữ ký — nghĩa là mọi thứ thuộc về **phần in sẵn** của biểu mẫu.

Mã vạch dưới chân trang cũng cần nói rõ: nó có **hình dạng** Code 39 nhưng
không mã hoá gì — cùng một số hiệu luôn vẽ ra cùng một bộ vạch, số hiệu khác vẽ
khác, nhưng máy quét không đọc được. Xem `_barcode` trong
[`generators/html/sheets/statement.py`](../../generators/html/sheets/statement.py).

## Tên trên giấy

Tên bệnh viện và tên công ty bảo hiểm trong bộ này là **tên tự đặt**
(`rulebase/corpus/vi/shops_medical.txt`, `shops_insurance.txt`). Một bảng kê
mang tên bệnh viện thật kèm mã thẻ BHYT và chẩn đoán là một hồ sơ bệnh án giả,
không phải một mẫu dữ liệu; giấy uỷ quyền cũng vậy. Mã ICD-10 thì là mã thật —
chúng là bảng phân loại công khai, không phải danh tính của ai.
