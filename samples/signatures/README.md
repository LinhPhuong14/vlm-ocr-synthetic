# signatures — chữ ký kéo giãn từ chữ viết tay

Bốn tệp để nhìn. Toàn bộ lý do chúng có hình dạng như thế nằm ở
[`docs/chu-ky.md`](../../docs/chu-ky.md) — khảo sát mẫu chữ ký trước, rồi mới
dựng engine.

| tệp | là gì |
| --- | --- |
| `styles.jpg` | 18 hạt giống, 5 cái tên: lưới để nhìn **dải tham số**, không phải một chữ ký |
| `signed-folio.jpg` | tờ **có in tên** dưới chú thích — chữ ký nằm đè lên tên |
| `signed-form.jpg` | tờ **để trắng** dưới chú thích — đa số bố cục là loại này |
| `signatures.json` | kiểu dáng của từng dấu ký, đúng như nó vào nhãn của bộ dữ liệu |

```bash
make signatures        # dựng lại cả bốn
```

## Nhìn cái gì ở lưới

![18 chữ ký](styles.jpg)

Nhãn dưới mỗi ô là `hạt-giống · chữ-còn-hình + số-chữ-đã-tan · đường-chân-chữ ·
paraph · tỷ-lệ`. Nên `Ng+2` đọc là: hai chữ `N` `g` còn giữ hình, hai chữ nữa
đã tan thành nét lượn.

Một chữ ký không chứng minh được gì; lưới thì có. Ba thứ đáng nhìn:

- **hầu hết đều không đọc ra chữ** — chỉ một hai chữ đầu còn hình, phần còn
  lại là nét lượn chạy. Đó là điều khảo sát nói và là điều lượt dựng đầu tiên
  làm sai: bóp hẹp một chữ thì nó vẫn là một chữ;
- **nét lượn giữ hướng của chữ nó thay**: chữ có đuôi (`g` `y` `p`) để lại vòng
  cắm xuống, chữ cao (`l` `h` `đ`) để lại vòng vắt lên. Vì thế `5` và `11` là
  hai nét lượn khác nhau chứ không phải một cái ngoằng dùng chung;
- **chữ cái đầu phóng to** và **nét cuối hất lên** — hai đặc điểm nhất quán
  nhất trong khảo sát, thấy rõ ở `4`, `8`, `15`.

Sáu ô vẫn đọc được, vì hai lý do khác nhau. `2`, `10`, `12`, `13`, `17` là
**chữ lồng toàn chữ hoa**, mà chữ hoa thì không bao giờ tan — ba chữ cái đầu là
để đọc, đó là toàn bộ công dụng của chữ lồng. `9`, `14`, `18` thì là một phần
mười số người ký **hình thành hết mọi chữ**, và đó cũng là chữ ký thật. Đo trên
300 hạt giống: 74 % tan thành nét lượn, 13 % là chữ lồng, 13 % giữ nguyên mọi
chữ.

Tỷ lệ khung rơi vào khoảng 0,98–3,05. Dải các bộ dữ liệu chữ ký offline thu mẫu
là 1,8–3,0; ở đây **không ép** vào dải ấy, chỉ báo cáo — xem `in_capture_box`
trong `signatures.json`.

## Nhìn cái gì ở hai tờ

`signed-folio.jpg` là `invoice_hotel_stay`, bố cục duy nhất trong bộ mẫu này có
`signature_names`: tên **được in sẵn**, và chữ ký nằm đè lên nó, vì đó là chỗ
cây bút đặt xuống.

`signed-form.jpg` là `invoice_vat_form`: dưới chú thích *(KÝ, GHI RÕ HỌ TÊN)*
chỉ có một dòng trắng. Tên người ký lấy từ `rulebase.corpus.people`, cùng kho
tên mà tài liệu rút người mua ra. Không có `names` thì khối ấy **để trắng và
được đếm**, không bịa.

Cả hai vẽ với `augmentation=pristine`: đây là ca-ta-lô mực, không phải bộ dữ
liệu. Bộ dữ liệu là `make dataset`.

## Điều phải nói thẳng

Nét là nét của **một mặt chữ**, kéo giãn. Đủ để làm hoa tiết trên tờ giấy —
mực mà bộ đọc phải học cách bỏ qua, nằm đúng chỗ chữ ký nằm — và **không** đủ
để làm mẫu chữ ký của một người. Hai dấu ký cùng hạt giống là giống hệt nhau,
và có hai mặt chữ chứ không phải 106 người viết. Cùng sự đánh đổi mà
[`samples/handwriting/`](../handwriting) đã ghi cho `FontHand`.
