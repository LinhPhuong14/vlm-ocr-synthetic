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
> | `resources/corpus/*wiki.txt` — chữ wiki cho template SynthDoG gốc | `rulebase/corpus/vi/` — corpus hoá đơn tiếng Việt |
> | `resources/paper/` — ảnh chụp giấy bạn tự cung cấp (gitignore) | `textures/paper/` — giấy dùng chung, có sẵn trong repo |
> | `resources/font/` — font bạn tự cung cấp (gitignore) | `fonts/` — font dùng chung, có sẵn trong repo |
> | `generators/synthdog/layouts/` — code xếp lưới của SynthDoG gốc | `rulebase/layouts/` — 5 bố cục hoá đơn |

## In the repository

| path | what it is |
| ---- | ---------- |
| `corpus/{en,ja,ko,zh}wiki.txt` | wiki text for the **original** SynthDoG templates (`template.py`), not for receipts |

## You have to supply these

Nothing here is required for the receipt template — it falls back to the shared
`fonts/` and `textures/paper/` at the repository root. These directories are for
overriding that with material you cannot redistribute, and for the original
SynthDoG templates.

Generation fails without a background image, and because synthtiger swallows
exceptions and retries, **it hangs instead of erroring** — so check here first
if nothing is produced:

| path | what goes in it | where to get it |
| ---- | --------------- | --------------- |
| `background/` | ảnh nền tờ giấy được ghép lên — **cần cho template hoá đơn** | ảnh chụp mặt bàn của bạn, hoặc [synthdog upstream](https://github.com/clovaai/donut/tree/master/synthdog/resources) |
| `font/{mono,sans}/` | font riêng, được ưu tiên hơn `fonts/` ở gốc repo | e.g. Noto Sans, Roboto, Be Vietnam Pro |
| `font/{en,ja,ko,zh}/` | font cho các template SynthDoG khác | Google Fonts, Noto family |
| `paper/` | ảnh chụp giấy cho template SynthDoG gốc | as above |

Check a font actually covers Vietnamese before a long run — the shared set is
already checked, anything you add is not:

```bash
python tools/check_fonts.py resources/font/mono
python tools/check_fonts.py ../../fonts/mono      # bộ dùng chung
```
