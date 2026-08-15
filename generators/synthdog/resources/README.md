# Resources — riêng của renderer glyph

Every path in the `config_*.yaml` files is **relative to `generators/synthdog/`**,
so run synthtiger from there and these resolve.

> **Đây KHÔNG phải chỗ để corpus tiếng Việt.** Corpus hoá đơn dùng chung cho cả
> ba renderer nằm ở [`rulebase/corpus/vi/`](../../../rulebase/corpus/vi). Thư mục
> này chỉ còn những thứ chỉ mình renderer glyph dùng.
>
> Cẩn thận với vài cái tên trùng nhau trong repo:
>
> | ở đây | dùng chung ở gốc repo |
> | --- | --- |
> | `resources/paper/` — ảnh chụp giấy bạn tự cung cấp (gitignore) | `textures/paper/` — giấy dùng chung, có sẵn trong repo |
> | `resources/font/` — font bạn tự cung cấp (gitignore) | `fonts/` — font dùng chung, có sẵn trong repo |
> | `generators/synthdog/layouts/` — code xếp lưới của SynthDoG gốc | `rulebase/layouts/` — 5 bố cục hoá đơn |

## In the repository

Không có gì. Thư mục này chỉ chứa thứ bạn tự cung cấp — xem bảng dưới.

Bản gốc của SynthDoG (`template.py`, `config_{en,ja,ko,zh}.yaml`, và corpus
wiki 6.7 MB đi kèm) đã **bỏ khỏi repo**: chúng sinh trang wiki đa ngôn ngữ,
không liên quan tới hoá đơn, và không có gì trong repo này gọi tới. Cần lại thì
lấy từ lịch sử git hoặc từ [clovaai/donut](https://github.com/clovaai/donut).

## You have to supply these

Nothing here is required for the receipt template — it falls back to the shared
`fonts/` and `textures/paper/` at the repository root. These directories are for
overriding that with material you cannot redistribute, and for the original
SynthDoG templates.

Không có gì ở đây là bắt buộc nữa: mặt bàn lấy từ `textures/background/` và
font lấy từ `fonts/`, cả hai đều có sẵn trong repo. Thư mục này chỉ để **ghi đè**
bằng tài nguyên riêng của bạn.

Vẫn nên biết: synthtiger nuốt exception rồi retry, nên thiếu tài nguyên thì nó
**treo chứ không báo lỗi** — kiểm tra ở đây trước nếu chạy mãi không ra ảnh.

| path | what goes in it | where to get it |
| ---- | --------------- | --------------- |
| `background/` | ảnh chụp mặt bàn của riêng bạn; trỏ `background.image.paths` vào đây thì nó thay cho `textures/background/` | ảnh chụp bằng điện thoại — vài chục tấm là cải thiện realism rẻ nhất |
| `font/{mono,sans}/` | font riêng, được ưu tiên hơn `fonts/` ở gốc repo | e.g. Noto Sans, Roboto, Be Vietnam Pro |

Check a font actually covers Vietnamese before a long run — the shared set is
already checked, anything you add is not:

```bash
python tools/check_fonts.py resources/font/mono
python tools/check_fonts.py ../../fonts/mono      # bộ dùng chung
```
