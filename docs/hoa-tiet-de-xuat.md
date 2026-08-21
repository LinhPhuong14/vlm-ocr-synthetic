# Hoạ tiết đề xuất — danh mục chưa làm

Thuộc tính `ornament` hiện có **27 mẫu**, sinh bằng `make ornaments`. Danh mục
dưới đây là **23 mẫu đã khảo sát nhưng chưa dựng** — trong đó bốn mẫu ở họ B đã
dựng một lần rồi gỡ đi — giữ lại ở đây để lần sau
khỏi phải nghĩ lại từ đầu, và để người đọc thấy chỗ nào của tờ giấy Việt Nam
vẫn còn trống trong bộ dữ liệu.

Mỗi mục ghi: nó là gì, nó nằm ở đâu trên tờ giấy thật, tờ nào dùng được, và —
chỗ này mới đáng giá — **vì sao chưa làm**.

Muốn dựng mục nào thì thêm một hàm vẽ vào [`tools/make_ornaments.py`](../tools/make_ornaments.py),
thêm một dòng vào `main()`, rồi khai báo trong
[`rulebase/rules/ornament.yaml`](../rulebase/rules/ornament.yaml).
`make preflight` sẽ đối chiếu luật với thư mục cả hai chiều.

---

## A · Dấu và mực đóng

### `seal_oval_branch` — Dấu bầu dục
Dấu của chi nhánh hoặc văn phòng đại diện: cùng lối chữ chạy hai cung như dấu
tròn nhưng ép dẹt, nên chữ **biến dạng theo trục ngang** — một bài khác hẳn cho
OCR so với chữ trên cung tròn đều.
*Hợp:* hoá đơn GTGT, lưu trú.
*Chưa làm vì:* `_arc_text` hiện đặt ký tự trên đường tròn bán kính không đổi.
Muốn ellipse thì phải tính lại tiếp tuyến theo tham số, và bước góc không còn
tỉ lệ thuận với bề rộng ký tự nữa.

### `seal_date_band` — Dấu ngày điều chỉnh
Dấu chữ nhật có ba dải số xoay tay: “NGÀY 12 THÁNG 03 NĂM 2025”. Chữ số thường
**lệch dòng nhau** vì ba dải xoay độc lập.
*Hợp:* mọi hoá đơn.
*Chưa làm vì:* nội dung phụ thuộc ngày của từng tờ, nên phải đi đường
`from_receipt` như mã vạch và mã QR, chứ không dựng sẵn thành file.

---

## B · Nét tay

> **Cả họ này đã dựng một lần rồi bỏ.** Chữ ký, chữ điền tay, gạch chân bút và
> vệt bút dạ quang đều đã có mã vẽ, đã sinh ra file, và đã bị gỡ khỏi
> `textures/ornament/` vì không đạt.
>
> Chỗ hỏng không phải ở tham số mà ở cách tiếp cận. **Chữ điền tay** dựng bằng
> cách lấy một mặt chữ in rồi làm lệch từng ký tự — nghiêng, xê dịch, đậm nhạt.
> Đặt cạnh một tờ scan thật thì nó vẫn là chữ in bị rung, vì hình dạng nét vẫn
> là hình dạng nét in: không có chỗ bút nhấc lên, không có nét nối, không có
> chỗ mực đọng ở cuối nét. **Chữ ký** dựng bằng chuỗi đường Bézier có bề rộng
> thay đổi — ra một hình ngoằn ngoèo, nhưng chữ ký người là một động tác đã
> luyện thành nếp, không phải một đường cong ngẫu nhiên; nhìn là biết máy vẽ.
>
> Làm cho đúng cần **dữ liệu nét thật** (toạ độ bút theo thời gian) hoặc **một
> mặt chữ viết tay có giấy phép cho phép phát hành lại** — chứ không phải thêm
> nhiễu vào cách cũ. Thêm nhiễu là chỗ đợt vừa rồi đã đi và đã sai.
>
> Mã vẽ cũ nằm trong lịch sử git, commit "Twenty more ornaments".

### `handwriting_fill` — Số và chữ điền tay
Ngày tháng, tên người mua, số tiền viết tay vào chỗ trống của tờ mẫu in sẵn.
Vẫn là **khoảng trống lớn nhất** của bộ dữ liệu: tờ mẫu sinh ra để được điền
tay, mà mọi tờ sinh ra đến giờ đều trống trơn hoặc in máy toàn bộ.
*Hợp:* tờ mẫu in sẵn (GTGT, xuất khẩu).
*Chưa làm vì:* xem khối trên. Cần mặt chữ viết tay có giấy phép, và nội dung
phải đi đường `from_receipt` để ảnh và nhãn không nói hai chuyện khác nhau.
Tám kho mã sinh chữ viết tay đã được khảo sát và xếp hạng trong
[`khao-sat-sinh-chu-viet-tay.md`](khao-sat-sinh-chu-viet-tay.md) — hai kho có
đường đi được, phần còn thiếu là chỗ nối `from_receipt` và điều khoản của dữ
liệu học.

### `signature_scrawl` — Chữ ký tay
Nét ký nhanh bằng bút bi hoặc bút mực. Mọi hoá đơn đều có hai ô chữ ký và đến
giờ cả hai đều để trắng.
*Hợp:* mọi hoá đơn.
*Chưa làm vì:* xem khối trên. Hướng khả dĩ là lấy một tập chữ ký viết tay có
giấy phép rồi tách nền, chứ không dựng bằng đường cong.

### `pen_underline` — Gạch chân bằng bút
Đường tay run gạch dưới dòng tổng tiền. *Hợp:* mọi hoá đơn.
*Chưa làm vì:* bỏ cùng cả họ. Đây là mục dễ cứu nhất trong sáu mục — một nét
thẳng run thì không đòi hình dạng chữ — nhưng một mình nó không đáng giữ lại
cả một node trong luật.

### `highlighter_swipe` — Vệt bút dạ quang
Mảng vàng trong suốt quét ngang dòng tổng. *Hợp:* mọi hoá đơn.
*Chưa làm vì:* bỏ cùng cả họ, và nó còn cần bên ghép ảnh biết trộn kiểu
multiply — phủ đè thì chữ dưới mất.

### `tick_accounting` — Dấu tích kế toán
Nét “✓” viết tay cạnh dòng đã kiểm, thường bút đỏ hoặc bút chì, rơi vào cột
trống hoặc đè lên số.
*Hợp:* hoá đơn GTGT, lưu trú.
*Chưa làm vì:* rẻ và dễ về mặt vẽ, nhưng cùng cái bẫy của cả họ: nét tay vẽ
bằng máy nhìn ra nét máy. Một dấu tích thì đơn giản hơn một chữ ký nhiều, nên
đây có lẽ là chỗ nên thử lại trước.

### `strikethrough_line` — Gạch xoá dòng
Nét gạch ngang một dòng hàng bị huỷ, đôi khi kèm chữ “huỷ” viết tay bên lề.
Dạy mô hình rằng **chữ đọc được chưa chắc là chữ còn hiệu lực**.
*Hợp:* hoá đơn GTGT, lưu trú.
*Chưa làm vì:* muốn đúng thì nhãn dữ liệu phải nói dòng nào bị xoá — tức là
đụng tới `ground_truth()`, không chỉ đụng tới lớp ảnh. Đáng làm, nhưng là một
việc lớn hơn một hoạ tiết.

---

## C · Nét in bảo an

### `guilloche_border` — Viền guilloche
Dải hoa văn xoắn chạy dọc khung viền thay vì hoa thị giữa trang — đúng lối viền
tờ hoá đơn xuất khẩu và giấy tờ có giá.
*Hợp:* tờ mẫu in sẵn.
*Chưa làm vì:* hàm `guilloche` hiện sinh hoa thị theo toạ độ cực. Viền là bài
khác: một mô-típ lặp dọc đường thẳng rồi bo bốn góc.

### `microtext_rule` — Dòng chữ siêu nhỏ
Đường kẻ nhìn xa là nét liền, soi gần là chuỗi chữ lặp cỡ 0,5mm. Nét bảo an
thật, và là bài kiểm tra thẳng vào **giới hạn phân giải** của mô hình.
*Hợp:* tờ mẫu in sẵn.
*Chưa làm vì:* chỉ có nghĩa nếu ảnh xuất ra đủ độ phân giải. Ở 150 dpi dòng chữ
ấy thành một vệt xám — đúng như ngoài đời, nhưng khi ấy nó không dạy được gì mà
một đường kẻ thường không dạy.

### `dot_screen_panel` — Nền tram điểm
Mảng chấm halftone làm nền cho khối tiêu đề hoặc khối tổng tiền: chữ nằm trên
nền chấm chứ không trên nền đặc.
*Hợp:* tờ tự thiết kế, lưu trú.
*Chưa làm vì:* dễ, nhưng chồng lên chữ thì phải trộn kiểu multiply. Bên ghép
ảnh chưa có, nên chưa kiểm chứng được.

### `hatch_band` — Dải gạch chéo
Dải kẻ nghiêng đều nhau, ngăn khối hoặc **lấp ô trống của bảng** — cách tờ mẫu
chặn người ta viết thêm vào chỗ trống.
*Hợp:* tờ mẫu in sẵn.
*Chưa làm vì:* muốn đúng thì phải biết bảng còn thừa mấy dòng, tức là đọc
`Grid` chứ không chỉ dán một ảnh vào một neo.

### `void_pantograph` — Nền hiện chữ khi sao chụp
Nền tram mịn giấu chữ “VOID”: bản gốc nhìn phẳng, bản photocopy thì chữ nổi
lên. Sinh **cả hai trạng thái** thì thành một cặp ảnh dạy đúng khái niệm.
*Hợp:* tờ mẫu in sẵn.
*Chưa làm vì:* thú vị nhất danh mục này và cũng khó nhất — cần mô phỏng đáp
tuyến tần số của máy photocopy, không phải vẽ một hoạ tiết.

---

## D · Hoạ tiết thương hiệu

### `logo_monogram` — Chữ lồng làm logo
Logo sinh tự động từ một đến ba chữ cái đặt trong hình: tròn, khiên, lục giác,
hình thoi. Hiện mọi tờ đều dùng logo vẽ bằng CSS **giống hệt nhau**.
*Hợp:* mọi tờ có letterhead.
*Chưa làm vì:* chữ cái phải lấy từ tên doanh nghiệp mà `rulebase` bốc ra, nên
lại là đường `from_receipt`. Đáng làm sớm: đây là thứ khiến mỗi doanh nghiệp
trông ra một doanh nghiệp khác.

### `deco_corner_step` — Nẹp góc bậc thang
Góc art-deco nhiều bậc, đậm dần vào trong — khác nẹp góc vuông hiện có ở chỗ nó
có nhịp. *Hợp:* lưu trú, tự thiết kế. *Chưa làm vì:* trùng vai với
`corner_bracket` đang có.

### `ribbon_banner` — Dải ruy băng
Băng có đuôi cắt chữ V chạy sau tiêu đề, chữ âm bản trên nền màu.
*Hợp:* tự thiết kế, phiếu quà tặng. *Chưa làm vì:* chữ nằm TRÊN hoạ tiết, nên
nó không còn là overlay nữa mà là một phần bố cục.

### `laurel_wreath` — Vòng nguyệt quế
Vòng lá ôm lấy một con số hoặc một dòng chữ. *Hợp:* lưu trú, phiếu quà tặng.
*Chưa làm vì:* chưa có loại document nào là phiếu quà tặng.

### `divider_ornament` — Hoa thị ngăn dòng
Dấu hoa thị nhỏ giữa hai nét kẻ ngắn. *Hợp:* tự thiết kế, tiệm bánh.
*Chưa làm vì:* rẻ nhất danh mục; để dành cho đợt gom các mẫu nhỏ.

---

## E · Hoa văn Việt

Đợt này mới dựng `motif_dong_son`. Bốn mô-típ dưới đây cùng họ với nó và cùng
một cách dựng — toạ độ cực, hoặc một mô-típ lặp dọc dải.

### `motif_lotus` — Hoa sen cách điệu
Cánh sen xếp vòng, làm nẹp góc hoặc dấu chìm giữa trang. *Hợp:* lưu trú, tiệm bánh.

### `motif_wave_traditional` — Sóng nước cổ
Sóng vảy cá xếp lớp kiểu hoa văn đình chùa — **khác hẳn** `wave_band` hiện có,
vốn là đồ hoạ hiện đại vẽ bằng hình sin. *Hợp:* lưu trú, nhà hàng.

### `motif_cloud_scroll` — Vân mây
Mây xoắn kiểu chạm gỗ, chạy thành dải ngang hoặc ôm góc. *Hợp:* lưu trú, nhà hàng.

### `motif_lattice` — Chấn song hoa văn
Lưới ô kiểu cửa gỗ Huế, lặp đều — nền mờ cho khối tiêu đề, thay `rect_grid`.
*Hợp:* lưu trú, nhà hàng.

---

## F · Mã máy đọc

### `barcode_code128` — Mã Code 128 tem kho
Mã vạch dài trên tem kho hoặc phiếu xuất, kèm mã đơn hàng dạng chữ–số.
*Hợp:* xuất khẩu, phiếu xuất kho.
*Chưa làm vì:* Code 128 có ba bộ mã và chuyển bộ giữa chừng, phức tạp hơn
EAN-13 đáng kể; và chưa có loại document nào là phiếu xuất kho.

---

## Ranh giới với `augmentation`

Danh mục này chỉ nhận thứ **cố ý có mặt** trên tờ giấy: ai đó in nó, đóng nó,
hoặc viết nó. Vết bẩn, nếp gấp, lỗ ghim, mực loang, bóng gáy sách là *hư hại*
chứ không phải thiết kế — chúng thuộc [`degradation/`](../degradation) và
`rules/augmentation.yaml`, và phần lớn đã có ở đó.

Vệt bút dạ quang nằm sát ranh giới; nó được xếp vào `ornament` vì có người cầm
bút quét lên, chứ không phải tờ giấy tự hỏng.
