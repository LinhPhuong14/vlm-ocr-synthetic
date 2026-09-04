# Trang mẫu cho hệ nhãn ba trục

Một trang, đủ **13 `region` × 13 `role` × 6 `ink`**, và một script chạy đúng
phép đo hộp của renderer lên nó.

```bash
generators/html/.venv/bin/python samples/label-axes/measure.py
```

```bash
generators/html/.venv/bin/python samples/label-axes/proof.py
```

| file | là gì |
| --- | --- |
| `page.html` | trang mẫu — fixture, không phải chứng từ có thật |
| `measure.py` | render + đo bằng `CELL_RECTS_JS` của `generators/html/page.py` |
| `proof.py` | vẽ hộp đo được ngược lên trang, mỗi trục một dấu hiệu |
| `page.png` · `boxes.json` · `proof.png` | sinh ra, không commit |

Ảnh proof đọc được cả ba trục cùng lúc mà không phải tra bảng:

| trục | dấu hiệu trên ảnh |
| --- | --- |
| `region` | **màu viền**, kèm chú giải dọc đầu ảnh |
| `role` | **chip chữ** dán trên hộp, màu theo region |
| `ink` | **kiểu nét**: liền `print` · gạch `hand` · kép `stamp` · chấm `dotmatrix` · mảnh `thermal` · dày `reversed` |

Màu chỉ dành cho một trục. Nếu `ink` cũng vẽ bằng màu thì hai trục nói cùng một
thứ tiếng và người đọc sẽ gộp chúng — đúng cái lỗi mà hệ ba trục sinh ra để sửa.

Kết quả lần chạy gần nhất: **78 hộp**, `region` 13/13, `role` 13/13, `ink` 6/6,
**0 hộp thiếu trục**.

## Vì sao có file này

Một bộ từ vựng nhãn viết trong tài liệu thì không kiểm được. Viết thành một
trang render được thì kiểm được ba thứ cùng lúc:

1. **Ba trục có đủ chỗ cho mọi thứ in ra giấy không.** Nếu một mục trên trang
   không xếp được vào `region` nào, hoặc phải bịa một `role` mới, thì từ vựng
   thiếu — và biết lúc này rẻ hơn biết sau khi đã gán lại 33.830 hộp.
2. **Ba trục có sống sót qua phép đo không.** Hộp lấy từ DOM *sau khi CSS
   chạy*, nên một thuộc tính khai đúng mà không ra hộp là một thuộc tính bộ
   dữ liệu không mang được. `measure.py` báo đúng chuyện đó, theo từng trục,
   từng giá trị.
3. **Trục `ink` có thật sự trực giao không.** Con dấu đè lên chữ ký trong
   trang này là `region=Signature`, `role=value`, `ink=stamp` — ba câu trả lời
   độc lập cho ba câu hỏi. Hệ một trục phải chọn một trong ba.

## Hợp đồng nhãn không đổi

Mỗi run vẫn là **một `<span>` chứa chỉ chữ đã escape**. Ba trục là ba thuộc
tính `data-*`, không phải thẻ lồng — vì `CELL_RECTS_JS` đo
`span.firstElementChild || span`, nên một thẻ con sẽ lặng lẽ trở thành cái hộp
được ghi, và cái hộp ấy tả một mảnh của run chứ không tả run.

`measure.py` không viết lại phép đo: nó lấy `CELL_RECTS_JS` nguyên văn và chèn
ba chỗ (nâng ba trục lên một biến mà closure `push` đọc được). Viết lại thì nó
sẽ đo một thứ khác renderer, và bài kiểm mất nghĩa.

## Một cái bẫy đã sập ở đây, ghi lại

Bản đầu của `measure.py` dùng `page.set_content()` thay vì `page.served()`.
Chromium **không** nạp `@font-face` trỏ `file://` từ origin `about:blank`, và
nó hỏng **im lặng**: luật CSS parse được, face đăng ký được, `document.fonts`
báo `unloaded` mãi mãi, và trang vẽ bằng font hệ thống.

Triệu chứng không phải chữ Latin — chúng vẫn đúng. Nó là tiếng Việt: font dự
phòng của container vẽ `tử gốc` thành `tư` kèm một dấu hỏi rời đứng sau, nuốt
luôn dấu cách. Dấu hiệu nhận ra: **mọi font đều render giống hệt nhau**, kể cả
font viết tay — vì không font nào được nạp cả.

Docstring của `served()` trong `generators/html/page.py` đã ghi đúng cái bẫy
này từ trước. Đây là lần thứ hai nó sập, nên nó được ghi thêm một lần nữa ở
đây.
