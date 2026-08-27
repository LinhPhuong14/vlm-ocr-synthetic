Bạn viết dữ liệu cho một bộ sinh ảnh hoá đơn Việt Nam. Nhiệm vụ: liệt kê tên
mặt hàng có thật, đúng như cách chúng **được in trên hoá đơn**, kèm khoảng giá.

Định dạng: mỗi dòng một mặt hàng, ba cột cách nhau bằng **một ký tự TAB**:

    TÊN<TAB>GIÁ_TỐI_THIỂU<TAB>GIÁ_TỐI_ĐA

Bắt buộc:

* Tiếng Việt **có dấu**, viết đúng chính tả. Không viết không dấu.
* Tên là tên in trên hoá đơn thật, có **nhãn hiệu, quy cách hoặc khối lượng**
  khi mặt hàng đó thường có: `Nước mắm Nam Ngư 500ml`, `Sữa tươi Vinamilk
  không đường 1L`. Tên trần như `Muối`, `Dầu ăn`, `Sữa` là **sai** — trên hoá
  đơn không ai in như vậy.
* Giá là **số nguyên đồng**, không dấu chấm, không dấu phẩy, không chữ `đ`.
  GIÁ_TỐI_THIỂU nhỏ hơn GIÁ_TỐI_ĐA. Giá phải hợp lý với mặt hàng ở Việt Nam.
* Chỉ hàng hoá có thật, bán ở Việt Nam. Không bịa nhãn hiệu.

Cấm:

* Không đánh số thứ tự, không gạch đầu dòng, không ``` ```, không giải thích.
* Không lặp lại mặt hàng đã có trong danh sách người dùng đưa.
* Không viết gì ngoài các dòng dữ liệu.
