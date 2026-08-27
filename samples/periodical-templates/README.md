# periodical-templates — mười trang báo & tạp chí, dựng tay

Mười file HTML+CSS **độc lập**, mỗi file dựng cho một dạng trang in định kỳ
phổ biến — năm trang nhật báo (ba khổ giấy khác nhau, một trang trong, một
trang rao vặt) và năm trang tạp chí (bìa, mục lục, một bài phỏng vấn, một
trang lưới mô-đun, một trải trang đôi phóng sự). Mở thẳng bằng trình duyệt,
không cần dựng môi trường; hoặc xem file `.jpg` bên cạnh.

| file | trang | khổ | N gốc |
| --- | --- | --- | --- |
| [`newspaper_front_broadsheet.html`](newspaper_front_broadsheet.html) | Trang nhất, khổ broadsheet, lưới 6 cột | 375×597mm | N-01 |
| [`newspaper_front_tabloid.html`](newspaper_front_tabloid.html) | Trang nhất, khổ tabloid, tít lớn tràn ảnh | 280×430mm | N-02 |
| [`newspaper_inside_berliner.html`](newspaper_inside_berliner.html) | Trang trong (kinh tế), khổ Berliner, 5 cột + quảng cáo | 315×470mm | N-03 |
| [`newspaper_opinion_page.html`](newspaper_opinion_page.html) | Trang xã luận & ý kiến: biếm hoạ, góc nhìn chuyên gia, thư bạn đọc | 315×470mm | N-04 |
| [`newspaper_classifieds.html`](newspaper_classifieds.html) | Trang rao vặt & thông báo: 6 cột hẹp, thông báo pháp lý, cáo phó | 280×430mm | N-10 |
| [`magazine_cover.html`](magazine_cover.html) | Bìa tạp chí: ảnh tràn lề (full bleed), coverline chính + phụ | A4 dọc | N-05 |
| [`magazine_contents.html`](magazine_contents.html) | Mục lục: bài đinh + lưới mục 2 cột theo chuyên mục | A4 dọc | N-06 |
| [`magazine_feature_spread.html`](magazine_feature_spread.html) | Trải trang đôi: ảnh tràn lề trang trái, chữ 3 cột trang phải | 420×297mm (2 trang) | N-07 |
| [`magazine_modular_grid.html`](magazine_modular_grid.html) | Trang lưới mô-đun: 12 thẻ, một thẻ nhấn chiếm 2 ô | A4 dọc | N-08 |
| [`magazine_qa_interview.html`](magazine_qa_interview.html) | Phỏng vấn hỏi–đáp: chân dung nửa trang + 2 cột hỏi/đáp | A4 dọc | N-09 |

`magazine_feature_spread.html` là file duy nhất mà phần tử trang gọi là
`.spread` chứ không phải `.sheet` — nó là **một** ảnh 420×297mm (hai trang A4
kề nhau qua một gáy sách), không phải hai `.sheet` riêng, khác với cách
`insurance_property_contract.html` làm ra trang 2 (hai `.sheet` trong cùng
file, chụp thành `-p1.jpg`/`-p2.jpg`). `render.py` xử lý khác biệt này bằng
cách dò `.sheet` trước, chỉ dò `.spread` khi không có.

Tên file **không** phải id của một bố cục có sẵn trong
[`rulebase/rules/layout.yaml`](../../rulebase/rules/layout.yaml) — giống hệt
`insurance-templates/`. Tên được chọn theo đúng quy ước của cả bốn thư mục
kia (`<domain>_<hình dạng trang>`) để khi có bố cục thật thì dùng lại làm id
luôn, không phải đổi tên.

```bash
make templates       # in lại cả bốn: invoice-, form-, insurance-, periodical-templates/
```

## Đây KHÔNG phải bố cục của rule-base — và CHƯA có engine

Giống hệt ghi chú trong `invoice-templates/README.md`, `form-templates/
README.md` và `insurance-templates/README.md`: mười file ở đây là **bản vẽ
tham chiếu**, HTML thường CSS thường, không đụng gì tới `rulebase`, không đi
qua `generators/html/sheets/`, nên chưa sinh ra nhãn dữ liệu. Đây là bước đọc
và lưu tham chiếu, làm trước bước viết layout/engine thật — đúng thứ tự đã
làm với root 1 (hoá đơn), root 3 (biểu mẫu) và tập bảo hiểm đang chờ ở
`insurance-templates/`.

Khác với ba root đã có engine (hoá đơn, biểu mẫu) hay với `insurance-
templates/` (vẫn còn nằm trong họ "chứng từ" — có bên bán/bên mua, có số
tiền, có chữ ký): mười trang báo/tạp chí này không có mô hình `Receipt` nào
tương ứng cả — không cửa hàng, không mặt hàng, không tổng tiền. Nội dung của
chúng là bài viết, tiêu đề, ảnh, số trang. Biến chúng thành bố cục sinh dữ
liệu thật sẽ cần một mô hình nội dung mới hoàn toàn (tiêu đề/sapo/byline/thân
bài/pull-quote/mục lục/rao vặt...), không phải chỉ thêm layout YAML vào mô
hình có sẵn — một quyết định phạm vi để hỏi người dùng trước, không tự suy
diễn.

## Hoạ tiết nền: không có gì phải bỏ lần này

Khác với `insurance-templates/` (đã bỏ lưới chéo giấy bảo an + chữ mờ "BẢN
MẪU" ở LO-02, và nền guilloche ở LO-05, chuyển ý tưởng "giấy có kết cấu" đó
sang augmentation dùng chung): mười trang ở đây **không có** hoạ tiết nền
kiểu đó để bỏ. Ô xám có nhãn "ẢNH" / "ẢNH CHÂN DUNG" xuất hiện ở cả mười file
là **placeholder ảnh** — đánh dấu chỗ một tấm ảnh thật sẽ nằm, vì bản vẽ này
chưa có ảnh thật để đặt vào — không phải một lớp phủ trang trí che nội dung
thật bên dưới như hai trường hợp kia. Bỏ nhãn "ẢNH" đi sẽ để lại một khối xám
vô nghĩa, khó hiểu hơn là giữ lại, nên nhãn này được giữ nguyên trong cả
mười file.

## Một dòng CSS được thêm vào bốn file

Không phải mọi trong mười file đều lưu y nguyên byte-for-byte. Khi chụp ảnh
lần đầu, bốn trang — `newspaper_classifieds.html`, `magazine_qa_interview.html`,
`magazine_contents.html`, `magazine_modular_grid.html` — cho ảnh chụp bị hụt
nội dung: `newspaper_classifieds.html` chỉ hiện đúng 1 trong 6 cột, năm cột
sau trắng trơn, mất toàn bộ mục "Thông báo" và "Cáo phó · Cảm tạ".

Nguyên nhân không phải lỗi nội dung, mà là một hành vi CSS mặc định:
`.cols`/`.qa`/`.grid` ở bốn file này đều vừa là **flex item** (`flex:1`, để
"chiếm hết phần còn lại của trang") vừa là **container cột/lưới cho chính
nội dung dài của nó**. Theo đặc tả flexbox, một flex item mặc định có
`min-height:auto`, nghĩa là nó **không chịu co xuống thấp hơn chiều cao nội
dung** của chính nó trừ khi được khai `min-height:0` rõ ràng. Khi container
cột/lưới không co xuống đúng phần còn lại của trang, Chromium tính sai chiều
cao dùng để chia cột/lưới: với `newspaper_classifieds.html`
(`column-fill:auto`), điều đó khiến toàn bộ nội dung dồn vào cột 1 (một cột
"cao vô hạn") thay vì chảy đều qua 6 cột; với `.sheet{overflow:hidden}` bọc
ngoài, phần vượt khỏi khổ trang bị cắt mất chứ không lộ ra thành lỗi rõ ràng
— nên ảnh chụp trông như một trang gần như trống, không như một trang bị lỗi.

Sửa bằng đúng một khai báo chuẩn cho lỗi flexbox này — `min-height:0` — trên
phần tử flex item liên quan (`.cols` ở `newspaper_classifieds.html`; `main`
và `.qa` ở `magazine_qa_interview.html`; `.cols` ở `magazine_contents.html`;
`.grid` ở `magazine_modular_grid.html`). Đã đo trực tiếp bằng
`getBoundingClientRect()` (chiều cao nội dung thật so với chiều cao khai báo
của trang) trước và sau, không chỉ nhìn ảnh:

| file | trước | sau |
| --- | --- | --- |
| `newspaper_classifieds.html` | tràn 1153px / 1625px trang | khớp, tràn 0px |
| `magazine_qa_interview.html` | tràn 69px / 1123px trang | khớp, tràn ~0px |
| `magazine_contents.html` | tràn 189px / 1123px trang | còn tràn 167px |
| `magazine_modular_grid.html` | tràn 383px / 1123px trang | còn tràn 343px |

Hai file đầu hết tràn hoàn toàn — đúng là lỗi CSS thuần, sửa xong ảnh chụp
khớp lại toàn bộ nội dung nguồn. Hai file sau **vẫn còn tràn sau khi sửa**:
đó không còn là lỗi trình duyệt mà là nội dung của chính bản vẽ dài hơn chỗ
chứa nó ở cỡ chữ đã chọn —

* `magazine_contents.html`: cột phải (Đời sống, Kiến trúc & thiết kế, Đọc
  chậm — nhiều mục có ảnh 22mm hơn cột trái) tự nó đã dài hơn một trang A4.
* `magazine_modular_grid.html`: thẻ nhấn (`.hi`) chiếm 2 ô trong hàng đầu,
  nên 12 thẻ cần đúng 5 hàng chứ không phải 4 — khiến `grid-auto-rows:1fr`
  luôn thiếu một hàng so với khổ trang thiết kế.

Cả hai đều được **giữ nguyên**, không cắt bớt nội dung hay thu nhỏ chữ để
"vừa khít" — đó là một quyết định thiết kế (bố cục nào chọn cỡ chữ nào, mục
lục dài bao nhiêu mục) của bản vẽ gốc, không phải một lỗi kỹ thuật của tôi
được phép tự sửa. Viết ra ở đây để ai đọc `magazine_contents.jpg`/
`magazine_modular_grid.jpg` biết vì sao mục cuối/thẻ 12 và chân trang không
xuất hiện trong ảnh, thay vì đoán nhầm là ảnh chụp thiếu.

## Tên tờ báo/tạp chí và dữ liệu

Toàn bộ tên tờ báo ("Minh Hoạ", "Nhật báo Minh Hoạ"), tên tạp chí ("Bến"),
tên phóng viên ("Minh Khuê", "Trần Hải", "Hoàng Vân"...), tên nhân vật, địa
danh ("rạch Mẫu", "xã Mẫu Thượng", "Đường Mẫu") và số hiệu (số báo, giấy
phép, mã vạch) trên cả mười tờ đều là **dữ liệu tự đặt** ngay từ bản gốc do
người dùng cung cấp — tên miền dùng `.example`/`example.vn`, đúng lệ của ba
thư mục kia. Không tờ nào mang tên một tờ báo, tạp chí hay cá nhân có thật.
