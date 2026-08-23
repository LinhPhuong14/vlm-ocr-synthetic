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

Nhãn dưới mỗi ô là `hạt-giống · mức-dễ-đọc · đường-chân-chữ · paraph · tỷ-lệ`.

Một chữ ký không chứng minh được gì; lưới thì có. Ba thứ đáng nhìn:

- **chữ cái đầu phóng to** so với phần thân — đặc điểm nhất quán nhất trong
  khảo sát, và là thứ hiện ra rõ nhất ở đây (`4`, `8`, `17`);
- **nét cuối hất lên** và **paraph** — hai nét duy nhất engine vẽ ra mà không
  thuộc chữ cái nào, đúng như giám định mô tả chúng;
- **mức dễ đọc** trôi từ cả họ tên (`5`, `11`) xuống chỉ chữ cái đầu (`2`,
  `10`, `13`) — người ký nhiều lần mỗi ngày ký ngắn.

Tỷ lệ khung rơi vào khoảng 1,1–3,9. Dải các bộ dữ liệu chữ ký offline thu mẫu
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
