# Resources

Every path in the `config_*.yaml` files is **relative to `generators/synthdog/`**,
so run synthtiger from there and these resolve.

## In the repository

| path | what it is |
| ---- | ---------- |
| `corpus/vi/` | Vietnamese receipt corpus: `items.txt` (dish + price range), `shops.txt`, `streets.txt`, `footers.txt` |
| `corpus/{en,ja,ko,zh}wiki.txt` | wiki text for the original SynthDoG templates |

## You have to supply these

Fonts and paper photographs are not redistributable, so they are not committed
and `.gitignore` keeps them out. Generation fails without them — and because
synthtiger swallows exceptions and retries, **it hangs instead of erroring**, so
check here first if nothing is produced:

| path | what goes in it | where to get it |
| ---- | --------------- | --------------- |
| `font/vi/` | TTF/OTF with full Vietnamese diacritics | e.g. Noto Sans, Roboto, Be Vietnam Pro |
| `font/{en,ja,ko,zh}/` | fonts for the other SynthDoG templates | Google Fonts, Noto family |
| `paper/` | photographs of paper: creases, texture, shadows | [synthdog upstream](https://github.com/clovaai/donut/tree/master/synthdog/resources), or your own scans |
| `background/` | background images the sheet is composited onto | as above |

Check a font actually covers Vietnamese before a long run:

```bash
python tools/check_fonts.py --dir resources/font/vi
```
