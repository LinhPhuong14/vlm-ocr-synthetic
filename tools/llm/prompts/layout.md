Bạn sửa **một phần** của một file bố cục chứng từ Việt Nam, viết bằng YAML.

Người dùng đưa cho bạn file gốc. Nhiệm vụ: trả về **một file YAML hoàn chỉnh**
là một biến thể hợp lý của nó — cùng loại giấy tờ, nhưng in ra khác đi, như thể
một cửa hàng khác dùng cùng loại chứng từ ấy.

Bắt buộc:

* Trả về **YAML thuần**, không ``` ```, không giải thích, không lời dẫn.
  Dòng đầu tiên là một khoá YAML.
* **Giữ nguyên mọi tên khoá.** Không thêm khoá mới, không đổi tên khoá, không
  bỏ khoá đang có. Chỉ đổi **giá trị**.
* `id` phải đúng bằng giá trị người dùng chỉ định.
* `name` và `source` viết lại cho khớp biến thể, tiếng Việt có dấu.
* Giá trị `true`/`false` giữ nguyên kiểu boolean; số giữ nguyên kiểu số.
* **Mọi danh sách hai số là một KHOẢNG viết theo thứ tự `[nhỏ nhất, lớn nhất]`.**
  `width: [42, 48]` nghĩa là rộng từ 42 tới 48. Muốn tờ giấy rộng hơn thì tăng
  **cả hai** số và vẫn giữ số nhỏ đứng trước: `[46, 52]`, **không phải**
  `[48, 42]`. Số đầu lớn hơn số sau là file hỏng, không dựng được trang nào.
* `rule_char` chỉ được là một trong ba ký tự `-`, `=`, `*`. Không dùng gạch dài.
* **`width: 0` trong `columns` là KÝ HIỆU ĐẶC BIỆT, không phải số 0.** Nó nghĩa
  là "cột này lấy hết phần còn lại của tờ giấy". Cột nào đang `width: 0` thì
  **giữ nguyên bằng 0**; cột nào đang là số thì giữ là số. Đổi `0` thành `10`
  là bóp cột tên xuống mười ký tự, và tên hàng kèm khối lượng sẽ bị cắt cụt
  trong khi nhãn vẫn khai đủ.
* **Nới cột này là bóp cột kia.** Cột `width: 0` lấy phần còn lại, nên phần của
  nó bằng `width của cả tờ − tổng các cột cố định`. Tăng `qty` từ 9 lên 10 và
  `unit_price` từ 12 lên 15 là lấy mất 4 ký tự của cột tên — mà tên hàng có kèm
  khối lượng (`Nho đỏ không hạt Mỹ 1,582 KG x 160,500`), nên nó bị cắt cụt và
  nhãn khai một thứ trang không in ra.

  **An toàn nhất: đừng đụng vào `columns[].width` cả.** Đổi `title` của cột,
  đổi cờ `true`/`false`, đổi `rule_char`, đổi các hệ số `scale` — đó là chỗ làm
  nên biến thể. Nếu vẫn muốn đổi độ rộng thì phải tăng `width` của cả tờ **ít
  nhất bằng** tổng phần đã cộng thêm vào các cột.

Nên đổi (đây là chỗ làm nên biến thể):

* thứ tự các mục trong `sections`
* `width`, `gutter`, độ rộng từng cột trong `columns`
* các cờ `true`/`false`: khung viền, dòng kẻ, in đậm, tiêu đề cột
* `rule_char`, `parties.style`, `meta.style`, `notes.style`
* nhãn tiếng Việt trong `letterhead.labels` và `columns[].title`
* các hệ số `scale`

Không nên đổi:

* danh sách `columns[].key` và `item.rows` — chúng nối vào dữ liệu, đổi là hỏng
* `sheet`

Nhớ: đây là chứng từ **in ra giấy** ở Việt Nam. Mọi nhãn phải là tiếng Việt có
dấu, đúng cách một tờ hoá đơn thật viết.
