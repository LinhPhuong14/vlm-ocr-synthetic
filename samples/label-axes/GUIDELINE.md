# Gắn box theo intent — hướng dẫn gán nhãn

Dành cho người (và cho agent) quyết định một hộp thuộc vùng nào. Mọi quy tắc ở
đây rút ra từ một lỗi đã gặp thật trên `page.html`, `page2.html`, `page3.html` —
không có dòng nào là suy đoán.

---

## Nguyên tắc gốc

> **Hỏi đoạn chữ này LÀM GÌ trong tài liệu, không hỏi nó TRÔNG THẾ NÀO hay
> NẰM Ở ĐÂU.**

Gần như mọi lỗi đã gặp là vi phạm đúng câu này. Ba dạng vi phạm, và mỗi dạng
đều đã xảy ra:

| Lấy nhầm cái gì | Ví dụ thật | Đúng ra là |
| --- | --- | --- |
| **Chỗ đứng** thay cho vai trò | letterhead ở lề trên → `Page-Header` | `Text` — nó là nội dung của riêng trang này |
| **Chất liệu** thay cho vai trò | con dấu "ĐÃ SOÁT XÉT" → `Image` | `Text` + `ink=stamp` — chữ đọc được |
| **Cách bày** thay cho vai trò | dải xanh in ngược → `Mark` | `Section-Header` — thứ nó chứa là tiêu đề mục |

Ba trục tồn tại để không phải chọn một trong ba câu trả lời:

* **`region`** — vùng này là gì trong tài liệu *(trục 1, từ vựng của bên dùng
  dữ liệu, cố định)*
* **`role`** — đoạn chữ này làm việc gì trong vùng ấy *(trục 2)*
* **`ink`** — mực lên giấy kiểu gì *(trục 3)*

Thấy mình muốn đưa "in ngược", "viết tay", "đóng dấu", "chữ đẳng khoảng" lên
trục 1 thì dừng: chúng thuộc trục 3.

---

## Quy trình bốn bước

1. **Khoanh vùng trước, gán nhãn sau.** Nhìn trang ở khoảng cách một sải tay và
   hỏi *"trang này chia thành mấy mảng?"*. Đừng bắt đầu từ từng dòng chữ.
2. **Hỏi mỗi mảng làm gì**, dùng bảng phân biệt bên dưới.
3. **Gán `role` cho từng run bên trong.** Đây là chỗ `key`/`value`,
   `colhdr`/`cell`, `heading`/`body` được phân biệt — **không** phải trục 1.
4. **Gán `ink`.** Nếu bước 4 làm bạn muốn đổi bước 2, thì bước 2 đã sai.

---

## Bảng phân biệt những cặp hay nhầm

### `Section-Header` hay `Text`?

**`Section-Header` là một phần được ĐẶT TÊN của tài liệu.** Dấu hiệu: đứng
riêng một dòng, thường có số mục, thường đậm hoặc cỡ lớn hơn, và phần dưới nó
là một khối có thể trích ra riêng.

| trên trang | nhãn | vì |
| --- | --- | --- |
| `4.1 Nguyên tắc phương pháp` | `Section-Header` | có số mục, đứng riêng, mở một phần |
| `Điều kiện phải thoả đồng thời:` | `Text` | **câu dẫn**, kết thúc bằng dấu hai chấm, chữ thường — nó là câu đầu của danh sách chứ không đặt tên cho phần nào |

Phép thử: bỏ dòng ấy đi, tài liệu có mất một *mục* không, hay chỉ mất một *câu*?

### `Title` hay `Section-Header`?

`Title` xuất hiện **một lần** trên trang, cỡ chữ lớn nhất, thường căn giữa —
tên của cả tài liệu. `Section-Header` lặp lại nhiều lần.

### `Page-Header` hay `Text`?

**`Page-Header` là ĐẦU TRANG CHẠY** — thứ lặp lại ở lề trên của *mọi* trang:
số trang, tên tài liệu rút gọn, mã tiêu chuẩn.

Khối tên/địa chỉ/mã số thuế của bên phát hành **không** phải `Page-Header`, dù
nó nằm trên cùng: nó xuất hiện một lần, là nội dung của riêng trang này → `Text`.

Và **mỗi mục ở lề trên là một vùng riêng**, không phải một dải chạy hết bề
ngang. Dải ấy chỉ 13% mực, rỗng ruột ở giữa, và mô hình học từ nó sẽ học rằng
khoảng trắng giữa hai mục cũng là đầu trang.

### `Form` hay `Text`?

**`Form` nghĩa là VÙNG NÀY LÀ CHỖ ĐỂ ĐIỀN** — một lưới ô có nhãn, chờ giá trị.

Có dấu hai chấm **không** làm một dòng thành biểu mẫu. `MST: 0312345678` trong
letterhead là `Text`: không ai điền vào đó, nó được in sẵn cùng tờ giấy. Việc
"nhãn đi với giá trị" đã có **trục 2** ghi (`role=key` / `role=value`) — đưa nó
lên trục 1 nữa là ghi hai lần.

Phép thử: trên tờ giấy trắng chưa dùng, chỗ này có để trống không?

### `Image` hay `Text` + `ink=stamp`?

**`Image` chỉ dành cho raster KHÔNG có chữ để đọc**: logo, ảnh chụp, mã vạch,
mã QR.

Con dấu có chữ đọc được → `Text` với `ink=stamp`. Bên trích xuất cần đọc "ĐÃ
SOÁT XÉT" và tên công ty trong dấu tròn; gọi chúng là `Image` là bảo mô hình
đừng đọc.

### `Image` hay `Figure`?

**Có chú thích → `Figure`. Không có → `Image`.**

`Figure` là ảnh **cộng** chú thích, tính một khối, và `Caption` bên trong nó là
lồng nhau đã khai. **Không** gắn thêm nhãn `Image` cho ảnh nằm trong `Figure`:
hai vùng khác lớp phủ cùng một vùng pixel là hai đích mâu thuẫn cho mô hình.

### `Diagram` hay `Image`?

`Diagram` là **cấu trúc vẽ ra để ĐỌC NHƯ CẤU TRÚC** — lưu đồ, sơ đồ khối: các
nút có chữ, có quan hệ, và thứ tự mang nghĩa. Ảnh chụp một cái máy là `Image`.

### `Bibliography` hay `Footnote` hay `Text`?

Ba thứ khác nhau, phân biệt bằng **cái gì trỏ tới chúng**:

| | trỏ bởi | ở đâu | dạng |
| --- | --- | --- | --- |
| `Footnote` | một **ký hiệu** trong thân bài (¹, *, †) | cuối trang, dưới một đường kẻ | câu rời |
| `Bibliography` | một **mã trích dẫn** ([1], (Nguyễn 2019)) | cuối tài liệu hoặc cuối mục, dưới tiêu đề "Tài liệu viện dẫn" | danh mục, thụt treo, tên tài liệu in nghiêng |
| `Text` | không gì cả | bất kỳ đâu | văn xuôi |

Nên `Bibliography` **không thể** là `Footnote`: footnote gắn với một chỗ cụ thể
trong thân bài qua một ký hiệu, còn danh mục tài liệu viện dẫn là một mục độc
lập của tài liệu. Và nó **không nên** là `Text` vì nó có cấu trúc lặp mà mô hình
học được: thụt treo, mã trong ngoặc vuông, nhan đề in nghiêng.

### `Formula`

Gộp từ `Equation-Block` và `Chemical-Block`. Lý do: mô hình dò bố cục nhìn
**hình dạng**, và trên trang `(NH₄)₂SO₄ + 2 NaOH →` với
`w = (V₁−V₀)·c·14,007·100/m` là **cùng một hình** — dòng ngắn căn giữa, có chỉ
số dưới, đôi khi đánh số bên phải. Tách chúng đòi *hiểu* nội dung, mà đó là việc
của chặng sau. Hai lớp mô hình không phân biệt được sẽ thành nhiễu trong chỉ số.

Cấu trúc hoá học **vẽ ra** (vòng benzen, liên kết) thì không phải `Formula` —
nó là `Diagram`, vì nó được đọc như cấu trúc.

### `Complex-Block`

**Chỉ dùng khi cái khung MANG NGHĨA "đây là một đơn vị"** và tách ra thì mất
nghĩa ấy. Ví dụ thật: một mẩu rao vặt trên báo — tiêu đề, thân, số điện thoại,
logo nhỏ, đóng khung — tách ra là mất "đây là MỘT mẩu quảng cáo".

**Không** dùng cho một bảng có chú thích trên và ghi chú dưới: đó là cấu trúc
thường gặp nhất trong tài liệu kỹ thuật, tách sạch thành `Caption` + `Table` +
`Footnote`, và mọi bộ dữ liệu bố cục đều tách.

Nếu thấy mình chọn `Complex-Block` vì *không biết xếp vào đâu*, thì đó là dấu
hiệu chọn sai — nó sẽ thành cái sọt rác mới, đúng vai `Text` đang giữ.

---

## Hộp của một vùng lấy tới đâu

> **Hộp vùng = mực bên trong + hình mà vùng ấy TỰ VẼ RA.**

Không phải bao lồi của chữ: bao lồi trong một bảng nằm gọn bên trong đường kẻ,
thiếu lề ô, thiếu hàng rỗng, thiếu chính đường kẻ.

Không phải hộp của thẻ chứa: một `<div>` tiêu đề là block nên rộng cả khổ giấy,
trong khi chữ căn giữa chỉ chiếm một phần ba.

| vùng | hộp lấy tới đâu | vì |
| --- | --- | --- |
| `Table` | theo đường kẻ | bảng tự vẽ đường kẻ |
| `Code-Block` | cả tấm nền | nền xám là thật, người đọc thấy cả tấm nền là khối mã |
| `Section-Header` (dải có nền) | cả dải | dải tự vẽ nền |
| `Title`, `Text` | ôm sát chữ | không vẽ gì cả |
| `List-Group` | **gồm cả số thứ tự** | số thứ tự là mực thuộc về danh sách |

**Cảnh báo:** thứ được vẽ chỉ để *dễ nhìn* cũng sẽ định nghĩa cái vùng. Một
khung nét đứt quanh sơ đồ, thêm vào cho thấy khối, đã kéo hộp `Diagram` từ 387
lên 794 px. **Khung nào không có trên giấy thật thì không được có trong phôi.**

---

## Ba phép kiểm phải qua

`measure.py` chạy chúng mỗi lần và trả mã lỗi khác 0:

1. **Vùng không chứa run của vùng khác** — trừ lồng nhau đã khai (`MAY_NEST`)
   và mực in đè. Bắt được lỗi thật: tiêu đề danh sách nằm trong hộp `List-Group`
   dạy mô hình rằng tiêu đề là một mục.
2. **Hai vùng không chồng nhau** — cùng hai ngoại lệ. Và ngoại lệ "in đè" khoá
   theo **mực** (`ink=stamp`, `role=mark`), không theo tên vùng: con dấu là con
   dấu dù nó thuộc vùng nào.
3. **Vùng mực phủ dưới 30% phải giải thích được** — không chặn, nhưng phải trả
   lời được "khoảng trắng này có thuộc về vùng không". Bảng: có. Khối chữ ký:
   có, chỗ trống để ký định nghĩa nó. Khung trang trí: không.

---

## Bốn cái bẫy kỹ thuật, đã sập cả bốn

1. **Thẻ inline lồng trong span nuốt cái hộp.** `<sub>`, `<i>`, `<code>` —
   `CELL_RECTS_JS` đo `span.firstElementChild || span`. Đo được: phương trình
   hoá học 5,3 px thay vì 310,6; đoạn văn 60 px thay vì 706. Cần thẻ lồng thì
   bọc **đúng một** thẻ con và cho chuỗi chữ vào `data-text`.
2. **`list-style` của CSS không tạo node DOM.** Dấu đầu dòng thành mực không có
   nhãn, và hộp vùng không với tới. Dùng `list-style:none` và in dấu thành run.
3. **`display:block` làm hộp rộng bằng cả khối.** Tiêu đề đo ra 794 px. Dùng
   `width:max-content`.
4. **`@font-face` trỏ `file://` không nạp từ origin `about:blank`.** Hỏng im
   lặng, và chỉ tiếng Việt mới lộ: `tử gốc` thành `tư` kèm dấu hỏi rời. Dấu hiệu
   nhận ra: mọi font render giống hệt nhau. Dùng `served()`.
