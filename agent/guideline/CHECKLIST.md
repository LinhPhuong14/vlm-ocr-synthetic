<!-- Sinh tự động bởi agent/guideline.py ngày 2026-09-03 từ /home/user/vlm-ocr-synthetic/data/5k_llm. Đừng sửa tay: chạy lại `tools/critic_review.py --guideline` sau mỗi lần đổi rules. -->

# Soi lại trước khi trả lời

Đây chính là những gì `agent/critic.py` sẽ soi sau khi trang được vẽ. Nó chạy dù bạn có đọc hay không, và cái gì nó bắt được sẽ quay lại thành hệ số phạt cho đúng những giá trị bạn vừa chọn. Đọc trước thì rẻ hơn.

## Lỗi nặng — một trang dính là một trang hỏng

- **`chong_lan`** (đọc từ record) — hai box đè lên nhau — người đọc mất một trong hai trường
- **`tran_le`** (đọc từ record) — box nằm ngoài mép giấy — nội dung bị cắt mất
- **`o_trong`** (đọc từ record) — box có nhãn nhưng không có chữ — nhãn nói dối
- **`che_box`** (đọc từ record) — con dấu/QR/hoa văn đóng trùm lên một trường có nhãn
- **`khong_muc`** (đọc từ ảnh giấy) — chỗ có nhãn nhưng trên giấy không có mực
- **`nhat`** (đọc từ ảnh giấy) — mực và giấy quá sát nhau, không đọc được

## Lỗi nhẹ — chấp nhận được lác đác, không chấp nhận được cả loạt

- **`chu_nho`** (đọc từ record) — dòng chữ thấp dưới ngưỡng pixel, OCR không đọc nổi
- **`lap_noi_dung`** (đọc từ record) — một chuỗi lặp lại nhiều lần trong cùng một loại trường
- **`dac_thua`** (đọc từ record) — mật độ chữ trên trang ra ngoài khoảng của một tờ giấy thật
- **`chu_nhat_mau`** (đọc từ ảnh giấy) — chữ quá nhạt so với nền ngay trong ô của nó
- **`mo`** (đọc từ ảnh giấy) — ảnh nhoè, không đủ nét để đọc
- **`muc_lech`** (đọc từ ảnh giấy) — cả trang quá tối hoặc quá trắng

## Suy ra được gì khi đang chọn

Bạn chọn trước khi trang được vẽ, nên không thấy được ô nào đè ô nào. Nhưng phần lớn lỗi trên có nguyên nhân đoán được từ chính tổ hợp:

1. **Dấu to trên phôi chật.** Một con dấu hay QR cỡ lớn trên phôi kín chữ thì `clearest()` không còn chỗ để né. Phôi càng đặc thì dấu càng phải nhỏ, hoặc đừng đóng dấu.
2. **Làm cũ chồng làm cũ.** Photocopy chồng ố chồng chụp lệch thì mực và giấy dính vào nhau: đó là `nhat` và `chu_nhat_mau`. Một trang nên có một câu chuyện, không phải ba.
3. **Mực nhạt trên nền có hoa văn.** `faded_gray` cộng nền guilloche làm tiêu đề cột biến mất — lỗi `khong_muc` hay gặp nhất trong bộ hiện tại rơi vào `colhdr`.
4. **Lề rộng trên giấy hẹp.** Bộ áo đặt lề theo milimet tuyệt đối sẽ đẩy ô ra ngoài một cuộn giấy nhiệt 80 mm. Các bộ áo ấy gắn `excludes: [till_receipt]`, nên bộ luật đã chặn — đừng đề xuất.
5. **Cùng một món ba lần.** Nội dung lặp là `lap_noi_dung`. Nếu bạn cũng sinh nội dung, hãy để một hoá đơn kể một lần mua hàng có lý.

## Câu hỏi cuối

*Tờ giấy này có tồn tại ngoài đời không?* Nếu phải nghĩ quá ba giây để bênh nó thì đổi đi. Đa dạng mà vô lý còn tệ hơn là đơn điệu — dữ liệu vô lý dạy mô hình những thứ nó sẽ không bao giờ gặp.
