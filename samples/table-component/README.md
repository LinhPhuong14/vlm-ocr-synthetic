# table-component — một bảng, mười hai cách viền/tô/gộp

`generators/html/components/table.py` là một component bảng dùng chung:
khai báo bằng `TableSpec`/`Border`/`Row`/`Cell`, `render_table()` trả về
một `<table>` tự đủ (CSS nhúng inline, không cần khớp với stylesheet nào
khác) — nên **thêm một bố cục mới không phải viết CSS**, chỉ chỉnh
attribute. Chi tiết mô hình viền (6 đường: 4 cạnh ngoài + 2 loại gạch
trong) nằm ở docstring đầu
[`generators/html/components/table.py`](../../generators/html/components/table.py).

**Đang dùng thật trong pipeline**, không chỉ là bản demo: `sheets/base.py`'s
`items_table()` (bảng hàng hoá — dùng chung bởi cả 5 family: statutory,
lodging, medical, modern, till) và `sheets/statutory.py`'s `_summary_table()`
(bảng "Tổng hợp" theo thuế suất) đều dựng `Row`/`Cell` rồi gọi
`render_table()` thay vì tự ghép chuỗi `<tr>`/`<td>` như trước. Mỗi family
vẫn giữ nguyên diện mạo riêng (viền, màu tiêu đề, zebra...) qua CSS
`<style>` của chính nó — component chỉ đảm nhận phần hình học (colspan/
rowspan, `data-cell`/`data-row`/`data-col`, `<thead>`/`<tbody>`), gọi qua
`border=Border.none()` + `Cell.cls`/`Row.cls` để nhường quyền vẽ viền lại
cho CSS đó (xem "Compatibility, not a dependency" trong docstring của
module).

`gallery.jpg` là **cùng một bảng 3 dòng hàng**, vẽ lại 12 lần — mỗi lần chỉ
đổi một attribute — để chứng minh cái đổi giữa các khung thật sự là
attribute được ghi dưới nó, không phải nội dung.

```bash
python3 tools/table_showcase.py -o samples/table-component
```

![Mười hai bố cục bảng, mỗi bố cục một attribute](gallery.jpg)

| # | Panel | Attribute |
| --: | --- | --- |
| 1 | có viền đầy đủ | `Border.grid()` |
| 2 | không viền | `Border.none()` |
| 3 | không viền dọc (ledger) | `Border.rows()` |
| 4 | không viền ngang | `Border.columns()` |
| 5 | không viền hai bên | `Border.grid().without("left", "right")` |
| 6 | không viền trên dưới | `Border.grid().without("top", "bottom")` |
| 7 | chỉ viền ngoài, không viền trong | `Border.frame()` |
| 8 | một gạch dưới tiêu đề, không gì khác | `TableSpec(header_divider=Line(...))` |
| 9 | viền ngoài dày + kiểu double, viền trong mỏng | `Border(top=Line(..., "double"), ...)` |
| 10 | zebra rows, cộng một ô/hàng tô màu riêng | `TableSpec.zebra=` + `Cell.bg=` / `Row.bg=` |
| 11 | ô merge (colspan) — dòng tổng cộng chạy 3 cột | `Cell(colspan=3, ...)` |
| 12 | bảng lồng bên trong một ô | `Cell(content=<TableSpec khác>)` |

`gallery.html` đi kèm là chính trang đã chụp — mở thẳng trong trình duyệt để
xem markup, không cần dựng gì.

Kiểm chứng ở mức thuộc tính/markup (không cần trình duyệt) nằm trong
[`tests/test_table.py`](../../tests/test_table.py) — 62 test, mỗi case trong
bảng trên có ít nhất một test khẳng định đúng cạnh nào được/không được vẽ.
[`tests/test_table_bbox.py`](../../tests/test_table_bbox.py) (8 test, cần
Chromium) đi xa hơn một bước: dựng bảng thật, đọc `page.CELL_REGIONS_JS` —
đúng hàm pipeline dùng để lấy hộp — rồi kiểm hình học trên pixel thật
(coverage, không chồng lấn, hộp bảng lồng không rò ra ngoài, hộp merge
đúng kích thước, mọi ô có chữ đều có mực bên dưới).

Xác nhận hai điểm vào (`items_table`, `_summary_table`) không đổi pixel so
với trước khi chuyển sang component:
[`tests/test_sheets.py`](../../tests/test_sheets.py) quét toàn bộ layout ×
seed (occupancy, không chồng cột, mọi trường trong nhãn đều xuất hiện trên
trang), và `python tools/baseline.py` (golden hash) — sau khi chuyển
`items_table()` một lần recapture (đổi từ `width:` trên từng `<th>` sang
`<colgroup>`, không đảm bảo giống hệt byte dưới `table-layout:auto`), còn
`_summary_table()` khớp baseline ngay không cần recapture.
