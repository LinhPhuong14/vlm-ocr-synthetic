# Trang mẫu cho hệ nhãn ba trục

Hai trang, đủ **19 `region` × 13 `role` × 6 `ink`**, và hai script chạy đúng
phép đo hộp của renderer lên chúng.

```bash
generators/html/.venv/bin/python samples/label-axes/measure.py
generators/html/.venv/bin/python samples/label-axes/proof.py
```

| file | là gì |
| --- | --- |
| `page.html` | hoá đơn GTGT — chứng từ giao dịch, loại phôi kho đang có |
| `page2.html` | trang tiêu chuẩn kỹ thuật — loại phôi kho **chưa** có |
| `measure.py` | render + đo bằng `CELL_RECTS_JS` của `generators/html/page.py` |
| `proof.py` | vẽ hộp đo được ngược lên trang, mỗi trục một dấu hiệu |
| `*.png` · `boxes.json` | sinh ra, không commit |

Lần chạy gần nhất: **137 hộp** (77 + 60), `region` **19/19**, `role` **13/13**,
`ink` **6/6**, **0 hộp thiếu trục**.

## Ba trục, và trục nào thuộc về ai

| trục | hỏi gì | từ vựng của ai |
| --- | --- | --- |
| `region` | hộp này thuộc vùng nào của trang | **bên dùng dữ liệu** — cố định, như `PAGE_LABELS` |
| `role` | nó làm việc gì trong vùng ấy | kho này — không ai ở ngoài đọc |
| `ink` | mực lên giấy kiểu gì | kho này |

Trục 1 là danh sách section mà bên huấn luyện model yêu cầu, sửa đúng hai chỗ:

* **thêm `Title`** — danh sách có `Section-Header` nhưng không có tên tài liệu,
  và hai thứ ấy khác nhau với bài toán dò bố cục: tên tài liệu xuất hiện một
  lần, cỡ chữ lớn nhất, thường căn giữa.
* **`Blank-Page` xuống mức trang** — một trang trắng không có hộp nào để gắn
  nhãn, nên chỗ của nó là bản ghi trang (`pages[].blank`), không phải `blocks[]`.

Ba lớp hình cần một quy tắc, nếu không chú thích sẽ trôi: `Image` là raster
không có cấu trúc đọc được (logo, dấu, QR); `Figure` là ảnh **cộng chú thích**,
tính là một khối gộp; `Diagram` là cấu trúc vẽ ra để **đọc như cấu trúc** (lưu
đồ, sơ đồ khối). `Complex-Block` phải định nghĩa chặt — khối con có `region`
**khác nhau** và tách ra thì mất nghĩa — nếu không nó thành cái sọt rác mới,
đúng vai `Text` đang giữ.

## Vì sao có hai trang

Chiếu 33.830 hộp đã commit lên bộ section này thì **9 lớp về 0**:
`Equation-Block`, `Code-Block`, `Chemical-Block`, `Diagram`, `Figure`,
`Bibliography`, `Complex-Block`, `List-Group`, `Blank-Page`.

Đó không phải "9 lớp thừa". Bên yêu cầu liệt kê chúng vì họ cần model **nhận ra
chúng**, nên số 0 là **thiếu loại tài liệu**, không phải thiếu từ vựng.
`page2.html` là bằng chứng: một trang tiêu chuẩn kỹ thuật tiếng Việt sinh ra 8
trong 9 lớp ấy. Lớp thứ chín không thể là một hộp.

## Ảnh proof

| trục | dấu hiệu trên ảnh |
| --- | --- |
| `region` | **màu viền**, kèm chú giải dọc đầu ảnh |
| `role` | **chip chữ** dán trên hộp, màu theo region |
| `ink` | **kiểu nét**: liền `print` · gạch `hand` · kép `stamp` · chấm `dotmatrix` · mảnh `thermal` · dày `reversed` |

Màu chỉ dành cho một trục. Nếu `ink` cũng vẽ bằng màu thì hai trục nói cùng một
thứ tiếng và người đọc sẽ gộp chúng — đúng cái lỗi hệ ba trục sinh ra để sửa.

## Hợp đồng nhãn không đổi

Mỗi run vẫn là **một `<span>` chứa chỉ chữ đã escape**. Ba trục là ba thuộc
tính `data-*`, không phải thẻ lồng — vì `CELL_RECTS_JS` đo
`span.firstElementChild || span`, nên một thẻ con sẽ lặng lẽ trở thành cái hộp
được ghi, và cái hộp ấy tả một mảnh của run chứ không tả run.

`measure.py` không viết lại phép đo: nó lấy `CELL_RECTS_JS` nguyên văn và chèn
ba chỗ (nâng ba trục lên một biến mà closure `push` đọc được). Viết lại thì nó
sẽ đo một thứ khác renderer, và bài kiểm mất nghĩa.

## Hai cái bẫy đã sập ở đây, ghi lại

**1 · Font không nạp, và chỉ tiếng Việt mới lộ.** Bản đầu của `measure.py` dùng
`page.set_content()` thay vì `page.served()`. Chromium **không** nạp
`@font-face` trỏ `file://` từ origin `about:blank`, và nó hỏng **im lặng**:
luật CSS parse được, face đăng ký được, `document.fonts` báo `unloaded` mãi mãi,
và trang vẽ bằng font hệ thống. Chữ Latin vẫn đúng. Tiếng Việt thì font dự
phòng vẽ `tử gốc` thành `tư` kèm một dấu hỏi rời đứng sau, nuốt luôn dấu cách.
Dấu hiệu nhận ra: **mọi font render giống hệt nhau**, kể cả font viết tay — vì
không font nào được nạp cả. Docstring của `served()` đã ghi đúng cái bẫy này từ
trước; đây là lần thứ hai nó sập.

**2 · `<sub>` nuốt cái hộp.** `Equation-Block` và `Chemical-Block` cần
`<sub>`/`<sup>`. Bản đầu của `page2.html` viết chúng trực tiếp trong span, và
hộp của cả phương trình hoá học rộng **5,3 px** thay vì 310,6 px — nó là hộp
của chữ số 4 trong (NH₄)₂SO₄. Đây đúng là cái bẫy mà docstring của `span()`
cảnh báo, gặp lần đầu trên dữ liệu thật.

Cách xử lý **không sửa renderer**: bọc toàn bộ công thức trong đúng **một** thẻ
con và cho chuỗi chữ đi kèm ở `data-text` — chính là cơ chế renderer đã có cho
mực viết tay của WriteViT. Khi ấy `firstElementChild` là cả công thức và hộp đo
đúng. Đánh đổi: mất hộp cho từng ký hiệu bên trong. Với bài toán dò bố cục thì
đó là thứ đang cần; muốn có hộp bên trong thì phải **nới phép đo**, và đó là
một quyết định về hợp đồng chứ không phải một bản vá.
