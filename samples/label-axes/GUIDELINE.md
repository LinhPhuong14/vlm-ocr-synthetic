# Hướng dẫn gán nhãn bố cục trang — ba trục

**Đối tượng đọc: mô hình sinh trang và mô hình gán nhãn.** Tài liệu này tự đủ:
không cần đọc gì khác để làm đúng. Mọi quy tắc đều rút từ **một lỗi đã gặp
thật** trên ba trang mẫu trong thư mục này, kèm số đo — không có dòng nào là
suy đoán.

Đọc theo thứ tự: §1 nguyên tắc → §2–4 từ vựng → §5 quy trình → §6 phân biệt →
§7 hộp → §8 hợp đồng markup → §11 checklist.

---

## 1. Nguyên tắc gốc

> **Hỏi đoạn chữ này LÀM GÌ trong tài liệu.**
> Không hỏi nó TRÔNG THẾ NÀO. Không hỏi nó NẰM Ở ĐÂU.

Gần như mọi lỗi từng gặp là vi phạm đúng câu này, theo một trong ba dạng — và
cả ba dạng đều đã xảy ra thật:

| Lấy nhầm cái gì | Lỗi thật | Đúng ra là |
| --- | --- | --- |
| **Chỗ đứng** thay cho vai trò | letterhead ở lề trên → `Page-Header` | `Text` — nội dung riêng của trang này, không lặp lại |
| **Chất liệu** thay cho vai trò | con dấu "ĐÃ SOÁT XÉT" → `Image` | `Text` + `ink=stamp` — chữ đọc được |
| **Cách bày** thay cho vai trò | dải xanh in ngược → `Mark` | `Section-Header` — thứ nó chứa là tiêu đề mục |

**Ba trục tồn tại để không phải chọn một trong ba câu trả lời.** Thấy mình muốn
đưa *in ngược*, *viết tay*, *đóng dấu*, *chữ đẳng khoảng*, *nền xám* lên trục 1
thì dừng lại: chúng thuộc trục 3.

### Ranh giới trách nhiệm ba trục

| trục | thuộc tính | hỏi gì | ai sở hữu |
| --- | --- | --- | --- |
| 1 | `data-region` | vùng này **là gì** trong tài liệu | **bên dùng dữ liệu** — cố định, không tự thêm bớt |
| 2 | `data-role` | run này **làm gì** trong vùng ấy | kho này — sửa được |
| 3 | `data-ink` | mực lên giấy **kiểu gì** | kho này — sửa được |

Thêm `data-kind` là mã trường tự do (`sign.buyer.name`), dùng để truy vết,
không tham gia phân loại.

---

## 2. Trục 1 — `region` (18 lớp + 1 ở mức trang)

Mỗi hộp thuộc **đúng một** lớp. Thứ tự dưới đây là thứ tự nên thử.

### Nhóm khung trang

**`Page-Header`** — dòng lặp lại ở lề **trên** của *mọi* trang.
Dấu hiệu: số trang, mã tiêu chuẩn, tên tài liệu rút gọn.
**Không phải**: letterhead, khối phát hành, tiêu đề tài liệu — chúng xuất hiện
một lần.
**Mỗi mục là một vùng riêng.** Một dải chạy hết bề ngang chỉ 13% mực, rỗng ruột
ở giữa; mô hình học từ đó sẽ học rằng khoảng trắng giữa hai mục cũng là đầu trang.

**`Page-Footer`** — như trên, ở lề dưới. Cùng quy tắc tách từng mục.

### Nhóm tiêu đề

**`Title`** — tên của **cả tài liệu**. Xuất hiện **một lần**, cỡ chữ lớn nhất,
thường căn giữa.

**`Section-Header`** — tên của **một phần** trong tài liệu. Đứng riêng một dòng,
thường có số mục, thường đậm; phần dưới nó trích ra được thành một khối.
**Không phải**: câu dẫn kết bằng dấu hai chấm (xem §6).

### Nhóm nội dung chạy

**`Text`** — văn xuôi, và mọi thứ không thuộc lớp nào hẹp hơn. Đây là lớp mặc
định, nhưng **không phải sọt rác**: thử hết các lớp hẹp trước.

**`List-Group`** — danh sách có dấu đầu dòng hoặc đánh số.
**Hộp phải gồm cả dấu đầu dòng / số thứ tự** (xem §9 bẫy 2).
Tiêu đề của danh sách **nằm ngoài** vùng này.

**`Table`** — lưới có hàng và cột, có tiêu đề cột. Hộp lấy **theo đường kẻ**.

**`Table-Of-Contents`** — mục lục: mục + dấu chấm dẫn + số trang.

**`Form`** — **vùng này là chỗ để ĐIỀN**: lưới ô có nhãn đang chờ giá trị.
**Không phải**: mọi dòng có dấu hai chấm (xem §6).
Phép thử: *trên tờ giấy trắng chưa dùng, chỗ này có để trống không?*

**`Code-Block`** — khối mã nguồn hoặc lệnh, chữ đẳng khoảng, thường có nền hoặc
viền. Hộp lấy **cả tấm nền**.

**`Formula`** — biểu thức toán học **hoặc** hoá học viết thành dòng. Căn giữa,
có chỉ số trên/dưới, đôi khi đánh số bên phải.
Gộp từ `Equation-Block` + `Chemical-Block` — xem §6 để biết vì sao.
**Không phải**: cấu trúc hoá học **vẽ ra** (vòng benzen, liên kết) → đó là
`Diagram`.

### Nhóm phụ trợ

**`Caption`** — chú thích của bảng, hình, sơ đồ. Ở trên hoặc dưới thứ nó chú thích.

**`Footnote`** — ghi chú được trỏ tới bởi một **ký hiệu** trong thân bài
(¹, *, †), nằm cuối trang dưới một đường kẻ.

**`Bibliography`** — danh mục tài liệu viện dẫn, được trỏ tới bởi **mã trích
dẫn** ([1], (Nguyễn 2019)). Thụt treo, nhan đề in nghiêng.
Phân biệt với `Footnote` và `Text`: xem §6.

### Nhóm hình

**`Image`** — raster **không có chữ để đọc**: logo, ảnh chụp, mã vạch, mã QR.
**Không phải**: con dấu có chữ đọc được (xem §6).

**`Figure`** — ảnh **cộng chú thích**, tính **một khối**.
`Caption` bên trong nó là lồng nhau **đã khai**, hợp lệ.
**Không gắn thêm `Image`** cho ảnh nằm trong `Figure`: hai vùng khác lớp phủ
cùng vùng pixel là hai đích mâu thuẫn cho mô hình.

**`Diagram`** — cấu trúc **vẽ ra để đọc như cấu trúc**: lưu đồ, sơ đồ khối, cấu
trúc hoá học. Các nút có chữ, có quan hệ, thứ tự mang nghĩa.

### Lớp đặc biệt

**`Complex-Block`** — **chỉ khi cái khung MANG NGHĨA "đây là một đơn vị"** và
tách ra thì mất chính nghĩa ấy.
Ví dụ hợp lệ: mẩu rao vặt trên báo — tiêu đề, thân, số điện thoại, logo nhỏ,
đóng khung — tách ra là mất "đây là MỘT mẩu quảng cáo".
**Không dùng** cho bảng có chú thích trên và ghi chú dưới: tách sạch thành
`Caption` + `Table` + `Footnote`.
**Chọn lớp này vì không biết xếp vào đâu là dấu hiệu chọn sai.** Nó sẽ thành
sọt rác mới, đúng vai `Text` từng giữ.

**`Blank-Page`** — **thuộc tính của TRANG, không phải của hộp.** Trang trắng
không có hộp nào để gắn nhãn. Ghi ở `pages[].blank`, không ghi trong `blocks[]`.

---

## 3. Trục 2 — `role` (13 giá trị)

Vai của run **bên trong** vùng của nó. Đây là nơi phân biệt nhãn với giá trị —
**không** phải trục 1.

| role | nghĩa | hay đi với region |
| --- | --- | --- |
| `key` | nhãn của một trường | `Form`, `Text` |
| `value` | giá trị của trường ấy | `Form`, `Text` |
| `heading` | tiêu đề của vùng | `Title`, `Section-Header` |
| `subheading` | tiêu đề phụ | `Title`, `Section-Header` |
| `colhdr` | tiêu đề cột | `Table` |
| `rowhdr` | tiêu đề hàng / số thứ tự hàng | `Table` |
| `cell` | ô dữ liệu | `Table` |
| `total` | ô tổng kết | `Form`, `Table` |
| `body` | văn xuôi chạy | `Text`, `Formula`, `Code-Block` |
| `item` | một mục trong danh sách | `List-Group`, `Bibliography`, `Table-Of-Contents` |
| `caption` | chú thích | `Caption` |
| `note` | ghi chú, chỉ dẫn nhỏ | `Footnote`, `Text` |
| `mark` | dấu, logo, mã vạch | `Image`, `Text` (con dấu) |

---

## 4. Trục 3 — `ink` (6 giá trị)

**Mực lên giấy kiểu gì.** Đo được từ lúc vẽ, không đoán từ ảnh.

| ink | nghĩa |
| --- | --- |
| `print` | in thường |
| `hand` | viết tay |
| `stamp` | đóng dấu |
| `dotmatrix` | máy in kim |
| `thermal` | giấy nhiệt, mực nhạt |
| `reversed` | chữ sáng trên nền đậm |

**Trục này gánh mọi thứ về chất liệu và cách bày.** Nếu một quan sát về *hình
thức* làm bạn muốn đổi trục 1, thì trục 1 đã sai.

---

## 5. Quy trình quyết định

1. **Khoanh vùng trước, gán nhãn sau.** Nhìn trang ở khoảng cách một sải tay:
   *"trang này chia thành mấy mảng?"*. **Đừng bắt đầu từ từng dòng chữ** — bắt
   đầu từ dòng chữ là cách trục 1 hết general.
2. **Kiểm tra ranh giới mảng.** Hai khối chữ cách nhau một khoảng rộng là **hai
   vùng**, không phải một vùng rỗng ruột. Phép thử: *hai khối này điền/đọc độc
   lập không?* (chữ ký bên mua và bên bán: có → hai vùng).
3. **Hỏi mỗi mảng LÀM GÌ.** Dùng §2, thử lớp hẹp trước, `Text` sau cùng.
4. **Gán `role` cho từng run.**
5. **Gán `ink`.** *Nếu bước này làm bạn muốn đổi bước 3, thì bước 3 đã sai.*
6. **Chạy ba phép kiểm §10.**

---

## 6. Các cặp hay nhầm — phép thử cho từng cặp

### `Section-Header` hay `Text`
**Phép thử:** bỏ dòng ấy đi — tài liệu mất một **mục** hay chỉ mất một **câu**?

| trên trang | nhãn | vì |
| --- | --- | --- |
| `4.1 Nguyên tắc phương pháp` | `Section-Header` | có số mục, đứng riêng, mở một phần |
| `Điều kiện phải thoả đồng thời:` | `Text` | câu dẫn — kết bằng hai chấm, chữ thường, không đặt tên phần nào |

### `Title` hay `Section-Header`
**Phép thử:** xuất hiện **một lần** hay lặp lại?

### `Page-Header` hay `Text`
**Phép thử:** thứ này có lặp lại ở lề trên **mọi** trang không?
`Mẫu số 01/GTKT3-001` là ca biên: nó không lặp lại trang khác và không phải chỉ
số trang, nên đọc chặt thì nó là trường định danh biểu mẫu (`Form`). **Ở kho
này giữ `Page-Header`** theo quyết định của chủ dự án.

### `Form` hay `Text`
**Phép thử:** trên tờ giấy trắng chưa dùng, chỗ này có **để trống** không?

* Lưới ô chờ điền → `Form`
* `MST: 0312345678` in sẵn trong letterhead → `Text`

**Dấu hai chấm không làm một dòng thành biểu mẫu.** Việc "nhãn đi với giá trị"
đã có trục 2 ghi (`role=key`/`role=value`) — đưa lên trục 1 nữa là ghi hai lần.

### `Image` hay `Text` + `ink=stamp`
**Phép thử:** có chữ **đọc được** không?
Con dấu có chữ → `Text` + `ink=stamp`. Gọi nó là `Image` là bảo mô hình **đừng
đọc** thứ mà bên trích xuất cần đọc.

### `Image` hay `Figure`
**Phép thử:** có **chú thích** không? Có → `Figure`. Không → `Image`.

### `Diagram` hay `Image`
**Phép thử:** có **đọc như cấu trúc** không? Nút có chữ, có quan hệ, thứ tự
mang nghĩa → `Diagram`.

### `Bibliography` / `Footnote` / `Text`
**Phép thử: cái gì TRỎ TỚI nó?**

| | trỏ bởi | ở đâu | dạng |
| --- | --- | --- | --- |
| `Footnote` | **ký hiệu** trong thân bài (¹, *, †) | cuối trang, dưới đường kẻ | câu rời |
| `Bibliography` | **mã trích dẫn** ([1], (Nguyễn 2019)) | cuối tài liệu/mục | danh mục, thụt treo, nhan đề nghiêng |
| `Text` | không gì cả | bất kỳ đâu | văn xuôi |

`Bibliography` **không thể** là `Footnote`: footnote gắn với một chỗ cụ thể qua
một ký hiệu, còn danh mục viện dẫn là một mục độc lập. Và **không nên** là
`Text` vì nó có cấu trúc lặp mô hình học được.

### `Formula` — vì sao gộp `Equation` với `Chemical`

> **Ranh giới lớp đặt ở chỗ mục tiêu huấn luyện cần, không đặt ở chỗ nội dung
> khác nhau.**

* `Formula` tách khỏi `Text` — **cần**: bày khác, đọc khác, xử lý phía sau khác.
  Mô hình hiểu nội dung đủ để biết "đây là công thức" là bình thường và cần thiết.
* `Equation` tách khỏi `Chemical` — **không ai dùng tới**: không đổi cách trích
  xuất, không đổi cách hiển thị, không đổi bước xử lý nào. Chia thêm chỉ tạo hai
  lớp mà người gán nhãn khó nhất quán và chỉ số đo khó đọc.

**Phép thử dùng cho MỌI lần định thêm một lớp vào trục 1:**
*"có bước nào phía sau đối xử với hai lớp này khác nhau không?"* Không có thì gộp.

---

## 7. Hộp của một vùng lấy tới đâu

> **Hộp vùng = mực bên trong + hình mà vùng ấy TỰ VẼ RA.**

Không phải bao lồi của chữ: bao lồi trong bảng nằm gọn bên trong đường kẻ,
thiếu lề ô, thiếu hàng rỗng, thiếu chính đường kẻ.

Không phải hộp của thẻ chứa: `<div>` tiêu đề là block nên rộng cả khổ giấy,
trong khi chữ căn giữa chỉ chiếm một phần ba.

| vùng | hộp lấy tới đâu | vì |
| --- | --- | --- |
| `Table` | theo đường kẻ | bảng tự vẽ đường kẻ |
| `Code-Block` | cả tấm nền | nền là thật, người đọc thấy cả tấm nền là khối mã |
| `Section-Header` có nền | cả dải | dải tự vẽ nền |
| `Figure` | cả khung + chú thích | khung là thật |
| `Title`, `Text` | ôm sát chữ | không vẽ gì cả |
| `List-Group` | **gồm cả số thứ tự** | số thứ tự là mực thuộc về danh sách |

### Hai cảnh báo

**Khung vẽ cho dễ nhìn sẽ định nghĩa cái vùng.** Một khung nét đứt quanh sơ đồ,
thêm vào chỉ để thấy khối, đã kéo hộp `Diagram` từ **387 lên 794 px**.
→ *Khung nào không có trên giấy thật thì không được có trong phôi.*

**Hộp vùng chỉ chặt bằng cái thẻ mà dấu ngồi lên.** Đánh dấu trên một thẻ bố
cục là gán nhãn cho **bố cục**, không phải cho **vùng**. Lỗi này đã gặp ba lần:
letterhead bao hai cột, đầu trang bao hai mục, chữ ký bao hai ô — lần cuối cho
một hộp 536,6 px với 25,7% mực, thay vì hai hộp 120,9 và 128,3 px.

---

## 8. Hợp đồng markup — bắt buộc khi sinh trang

Hộp được đo **từ DOM sau khi CSS chạy**, bằng `CELL_RECTS_JS` trong
`generators/html/page.py`. Nên cách viết markup quyết định hộp có đúng không.

### Luật 1 — một run là MỘT `<span>` chứa CHỈ chữ đã escape

```html
<span data-region="Form" data-role="value" data-ink="hand"
      data-kind="sign.buyer.name">Bích Trâm</span>
```

Ba trục là **thuộc tính**, không phải thẻ lồng. Phép đo lấy
`span.firstElementChild || span`, nên **một thẻ con lặng lẽ trở thành cái hộp**.

### Luật 2 — cần thẻ lồng thì bọc ĐÚNG MỘT thẻ con và dùng `data-text`

```html
<span data-region="Formula" data-role="body" data-ink="print"
      data-kind="eq.body"
      data-text="wN = (V1 − V0) · c · 14,007 · 100 / m"><span class="tex">w<sub>N</sub>
      = (V<sub>1</sub> − V<sub>0</sub>) · c · 14,007 · 100 / m</span></span>
```

Đây là cơ chế renderer đã có cho mực viết tay của WriteViT. Đánh đổi: mất hộp
cho từng ký hiệu bên trong — với dò bố cục thì đó là thứ đang cần.

### Luật 3 — khối vùng đánh dấu bằng `data-region-box`, đặt trên thẻ HẸP NHẤT

```html
<div class="r-signature">                          <!-- thẻ bố cục: KHÔNG đánh dấu -->
  <div class="col" data-region-box="Form"> … </div>   <!-- vùng thật -->
  <div class="col" data-region-box="Form"> … </div>
</div>
```

### Luật 4 — không dùng `list-style`, in dấu đầu dòng thành run

```html
<ul data-region-box="List-Group" style="list-style:none;padding-left:0">
  <li><span class="no" data-region="List-Group" data-role="item" data-ink="print"
            data-kind="list.marker">—</span><span
            data-region="List-Group" data-role="item" data-ink="print"
            data-kind="list.item">Nội dung mục.</span></li>
</ul>
```

### Luật 5 — span có nhãn không được `display:block`

Dùng `display:block; width:max-content` — vẫn xuống dòng mà hộp vẫn bám chữ.

---

## 9. Bốn cái bẫy kỹ thuật, đã sập cả bốn

| # | Bẫy | Đo được | Cách tránh |
| --- | --- | --- | --- |
| 1 | thẻ inline lồng trong span (`<sub>`, `<i>`, `<code>`) nuốt hộp | công thức **5,3 px** thay vì 310,6; đoạn văn **60 px** thay vì 706 | Luật 2 |
| 2 | `list-style` không tạo node DOM | hộp `List-Group` bắt đầu **sau** chữ số; "1." là mực không nhãn | Luật 4 |
| 3 | `display:block` làm hộp rộng bằng cả khối | tiêu đề **794 px**, đúng bề ngang tờ giấy | Luật 5 |
| 4 | `@font-face` trỏ `file://` không nạp từ `about:blank` | `tử gốc` vẽ thành `tư` kèm dấu hỏi rời — **chỉ tiếng Việt mới lộ** | dùng `served()`; dấu hiệu: **mọi font render giống hệt nhau** |

---

## 10. Ba phép kiểm tự động

`measure.py` chạy mỗi lần, trả mã lỗi khác 0 nếu hỏng.

1. **Vùng không chứa run của vùng khác.** Ngoại lệ: lồng nhau **đã khai**
   (`MAY_NEST`: `Figure` chứa `Caption`) và mực in đè. Bắt lỗi thật: tiêu đề
   danh sách trong hộp `List-Group` dạy mô hình rằng tiêu đề là một mục.
2. **Hai vùng không chồng nhau.** Cùng hai ngoại lệ. **Ngoại lệ in đè khoá theo
   MỰC** (`ink=stamp`, `role=mark`), không theo tên vùng — con dấu là con dấu dù
   thuộc vùng nào. Khoá theo tên vùng đã vỡ ngay khi con dấu đổi từ `Image` sang
   `Text`.
3. **Vùng dưới 30% mực phải giải thích được.** Không chặn, nhưng phải trả lời
   *"khoảng trắng này có thuộc về vùng không"*. Bảng: có. Khối chữ ký: có — chỗ
   trống để ký định nghĩa nó. Khung trang trí: **không**.

**Lớp chưa có ví dụ thì KHAI RA, không chế.** `DECLARED_GAP` là chỗ khai.
Từng có một hàm Python đặt giữa một tiêu chuẩn hoá học chỉ để `Code-Block` xuất
hiện — **chế nội dung cho vừa cái nhãn là đúng thứ đầu độc bộ dữ liệu**.

---

## 11. Checklist trước khi nộp một trang

- [ ] Mỗi run có đủ **bốn** thuộc tính: `data-region`, `data-role`, `data-ink`,
      `data-kind`.
- [ ] Không span nào có thẻ lồng, trừ khi bọc đúng một thẻ + `data-text`.
- [ ] Không span có nhãn nào đặt `display:block` mà thiếu `width:max-content`.
- [ ] Danh sách dùng `list-style:none`, dấu đầu dòng là run có nhãn.
- [ ] `data-region-box` đặt trên thẻ **hẹp nhất** bao đúng vùng, không phải thẻ
      bố cục.
- [ ] Hai khối cách nhau khoảng rộng đã tách thành hai vùng.
- [ ] Không có khung/nền nào vẽ ra chỉ để dễ nhìn.
- [ ] Mọi chữ in trên trang đều có ít nhất một run — **không từ nào mồ côi**.
- [ ] `measure.py` trả về **0 lỗi chú thích**.
- [ ] Nội dung **có thật với loại tài liệu ấy** — không chế để lấp một lớp.
