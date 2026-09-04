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
| `measure.py` | render + đo, cả mức run lẫn mức khối |
| `proof.py` | vẽ hai loại ảnh proof: ba trục, và riêng trục 1 |
| `*.png` · `boxes.json` · `regions.json` | sinh ra, không commit |

Lần chạy gần nhất: **138 hộp run** (77 + 61) và **37 khối vùng** (16 + 21),
`region` **19/19**, `role` **13/13**, `ink` **6/6**, **0 hộp thiếu trục**.

## Hai loại ảnh proof, và vì sao phải có hai

| ảnh | đo ở mức | trả lời câu hỏi |
| --- | --- | --- |
| `*-proof.png` | **run** — mỗi đoạn chữ một hộp | ba trục có gán đúng cho từng đoạn chữ không |
| `*-region.png` | **khối** — mỗi vùng đúng một hộp | trục 1 chia trang có hợp lý không |

Hộp vùng **không phải** bao lồi của các run: bao lồi trong một bảng nằm gọn bên
trong đường kẻ — thiếu lề ô, thiếu hàng rỗng, thiếu chính đường kẻ.

Nhưng nó cũng **không phải** hộp của thẻ chứa: một `<div>` tiêu đề là block nên
rộng cả khổ giấy, trong khi chữ căn giữa chỉ chiếm một phần ba — và chỗ trống
hai bên không có gì được vẽ ra cả.

Định nghĩa đúng là thứ một người gán nhãn sẽ khoanh: **mực, cộng với hình mà
vùng ấy tự vẽ ra**. Hộp vùng là hợp của hai thứ — hộp của mọi run bên trong, và
hộp của mọi phần tử **có viền hoặc có nền**.

| vùng | ra hộp nào | vì |
| --- | --- | --- |
| `Table` | theo đường kẻ | bảng vẽ đường kẻ |
| `Section-Header` (dải xanh) | cả bề ngang | dải có nền |
| `Code-Block`, `Figure`, `Complex-Block` | cả khung | có viền/nền |
| `Title` | ôm sát chữ | không vẽ gì cả |
| `Text` (đoạn văn) | cả bề ngang | vì chữ căn đều thật sự rộng thế |

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

## Ba phép kiểm chú thích, chạy mỗi lần

Kiểm "mọi tag đều ra hộp" là kiểm **cơ học**: nó nói bộ từ vựng dùng được,
không nói bộ chú thích đúng. `measure.py` chạy thêm ba phép hỏi câu của người
gán nhãn, và trả về mã lỗi khác 0 nếu hỏng:

1. **Một vùng không chứa run của vùng khác.** Đây là phép bắt được lỗi thật:
   tiêu đề của một danh sách nằm trong hộp `List-Group` thì mô hình học rằng
   tiêu đề là một mục của danh sách. Trường hợp lồng nhau **hợp lệ** phải khai
   trong `MAY_NEST` — `Figure` chứa `Caption` là cấu trúc, không phải lỗi — vì
   phần lớn cái lồng còn lại là lỗi thật.
2. **Hai vùng không chồng nhau**, trừ thứ in đè (`MAY_OVERPRINT`): con dấu đè
   lên chữ ký là chuyện có thật trên giấy, nên cấm hẳn sẽ cấm luôn một thứ thật.
3. **Vùng mực phủ dưới 30% được liệt kê ra**, không phải để chặn mà để bắt
   giải thích.

Lần chạy gần nhất: **0 lỗi chú thích**, 8 vùng loãng — và cả tám giải thích
được:

| vùng | phủ | vì sao vẫn đúng |
| --- | ---: | --- |
| `Figure` | 7,7% | ảnh trong fixture là ô gạch chéo, gần như không có mực — trang thật thì raster phủ kín. **Hiện vật của fixture, không phải lỗi thiết kế.** |
| `Complex-Block` | 15,3% | khung có viền, bên trong là bảng — giấy trắng giữa các ô là phần của vùng |
| `Table` | 17,1% | một bảng phần lớn là giấy giữa các đường kẻ |
| `Diagram` | 20,0% | các nút cách nhau, khoảng giữa là phần của sơ đồ |
| `Section-Header` | 21,5% | dải có nền: cả dải là vùng, dù chữ chỉ ở hai đầu |
| `Table-Of-Contents` | 21,6% | dấu chấm dẫn **có được vẽ** nhưng không phải run — **phép đo đếm thiếu** |
| `Form` (chữ ký) | 25,7% | chỗ trống để ký chính là thứ định nghĩa khối chữ ký |
| `Form` (tổng kết) | 29,4% | nhãn trái, số phải, giữa để trống — đúng cách in |

Hai dòng in đậm là chỗ con số nói dối chứ không phải chú thích sai. Sáu dòng
còn lại: khoảng trắng **là** phần của vùng.

## `Page-Header` chỉ là đầu trang chạy

Khối tên/địa chỉ/mã số thuế của bên phát hành **không** phải `Page-Header`. Vùng
ấy là **dòng lặp lại ở lề trên mọi trang** — mẫu số, số trang. Và mỗi mục ở
đó là **một vùng riêng**, không phải một dải chạy hết bề ngang: dải ấy rỗng
ruột ở giữa (mực phủ 13%), nên mô hình học từ nó sẽ học rằng khoảng trắng giữa
hai mục cũng là đầu trang. Đây là cách DocLayNet gán nhãn, và là lý do hai vùng
loãng nhất biến mất khỏi bảng trên. Letterhead là nội
dung của riêng trang này, xuất hiện một lần, nên nó là `Text` (ba dòng danh
tính) cộng `Form` (cặp có nhãn: MST:, ĐT:). Đây là chỗ bản đầu của fixture gán
sai, và gán sai theo đúng kiểu đã làm hỏng trục 1: lấy **chỗ đứng trên trang**
thay cho **vai trò trong tài liệu**.

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

**2 · Thẻ inline lồng trong span nuốt cái hộp.** Gặp ba lần trên trang 2, cùng
một gốc: `<sub>` trong công thức, `<sub>` trong đoạn văn giải thích ký hiệu, và
`<i>` trong mục tài liệu viện dẫn. Hộp của cả phương trình hoá học rộng **5,3
px** thay vì 310,6 — nó là hộp của chữ số 4 trong (NH₄)₂SO₄; mục viện dẫn thì
chỉ ôm phần in nghiêng. Đây đúng là cái bẫy mà docstring của `span()` cảnh báo,
gặp lần đầu trên nội dung thật.

Cách xử lý **không sửa renderer**: bọc toàn bộ công thức trong đúng **một** thẻ
con và cho chuỗi chữ đi kèm ở `data-text` — chính là cơ chế renderer đã có cho
mực viết tay của WriteViT. Khi ấy `firstElementChild` là cả công thức và hộp đo
đúng. Đánh đổi: mất hộp cho từng ký hiệu bên trong. Với bài toán dò bố cục thì
đó là thứ đang cần; muốn có hộp bên trong thì phải **nới phép đo**, và đó là
một quyết định về hợp đồng chứ không phải một bản vá.

**3 · `display:block` làm hộp rộng bằng cả khối.** Tiêu đề tài liệu đo ra
**794 px** — đúng bề ngang tờ giấy — vì span được đặt `display:block`, nên hộp
là hộp của khối chứ không ôm chữ. `width:max-content` giữ được việc xuống dòng
mà hộp vẫn bám chữ. Bài học chung với bẫy 2: **hộp ở mức run phải tả CHỮ**; cái
tả khối là trục 1, và nó được đo riêng.
