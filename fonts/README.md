# Fonts

`rules/visual.yaml` names both a directory (`font_dir: mono`) and a CSS stack
(`font_family`), and the two must resolve to the same typeface. That mattered
literally when three renderers drew the same page two different ways; it still
matters now, because `pipeline/preflight.py` estimates a page's height from the
directory while Chromium lays it out from the stack, and a disagreement there
is a page that passes preflight and overflows.

These are committed because every one of them is redistributable and a clone
with no fonts cannot render anything at all.

| directory | fonts | licence |
| --- | --- | --- |
| `mono/` | Liberation Mono (Regular, Bold) | SIL Open Font License 1.1 |
| `mono/` | Cousine (Regular, Bold) | Apache License 2.0 |
| `mono/` | Noto Mono | SIL Open Font License 1.1 |
| `sans/` | Liberation Sans, Arimo | OFL 1.1 / Apache 2.0 |
| `sans/` | DejaVu Sans (Regular, Bold) | Bitstream Vera / Public domain additions |
| `sans/` | Noto Sans | SIL Open Font License 1.1 |
| `serif/` | Liberation Serif (Regular, Bold) | SIL Open Font License 1.1 |
| `hand/` | Patrick Hand, Indie Flower | SIL Open Font License 1.1 |

## `hand/` is not a fourth printing font

Nothing sets a page in these. They are the ink for `--handwriting font` --
values a person writes into a printed form -- and `page.font_faces()`
deliberately does not walk this directory, so a `font-family` stack can never
fall through into one. `generators/html/handwriting.py` embeds the one face it
picked, per page.

They are here rather than generated because
[`docs/hoa-tiet-de-xuat.md`](../docs/hoa-tiet-de-xuat.md) named exactly two
honest ways to put handwriting on a page -- real stroke data, or **a
handwriting typeface with a licence that allows redistribution** -- after an
earlier attempt at jittering a printed face was removed for being printing with
a tremor. Both files are redistributed verbatim under the OFL, unmodified.

**The Vietnamese check caught one.** Caveat is the obvious casual-hand choice
and is **missing 80 Vietnamese characters** -- `Ơ Ư ơ ư Ạ Ả Ấ Ầ Ẩ Ẫ Ậ Ắ Ằ ...`
-- so it would have drawn empty boxes while the label claimed the word was
written. It is not here. Dancing Script passes the check but ships only as a
variable font, and instantiating a static cut would mean redistributing a
modified face under a Reserved Font Name; it is not here either.

**Two more, checked while looking for a third face.** Finesse (Republish /
Behalf Studio) passes the Vietnamese check, but its own specimen sheet says
"Only Finesse Oblique is released under SIL Open Font License" -- Roman,
Italic, Flair and Future, the cuts that would actually stand in for a plain
hand, are not. Every one of the five files' embedded metadata agrees they are
not OFL: `Copyright © 2020 by Behalf Studio. All rights reserved.`, with no
`licenseDescription` name record at all -- Patrick Hand's and Indie Flower's
both carry the OFL's, verbatim, so the absence here is a real signal and not a
quirk of how it was checked. Oblique itself carries no such record either,
despite the specimen's claim for it: one licensing document disagreeing with
itself is a reason to leave the whole family out, not to pick the cut it
happens to bless. Playwrite VN (Google Fonts) is genuinely OFL but ships only
as a variable font with no static instances published, the same reason
Dancing Script is not here, and would additionally need checking against
WeasyPrint's variable-font support before `--handwriting font` could use it on
both HTML renderers. Neither is here.

## Vietnamese coverage is not optional

Every font here has been checked to cover the full Vietnamese alphabet. That
check is not a formality — **DejaVu Sans Mono fails it**, missing 46 characters
including `Ấ Ầ Ẩ Ẫ Ắ Ế Ề Ể Ễ Ố Ồ Ổ Ỗ`, which is why it is not in `mono/` even
though it is the obvious monospace choice. A missing glyph renders as a blank
box, and the label still claims the word was printed.

Check anything you add before a long run:

```bash
generators/html/.venv/bin/python tools/check_fonts.py fonts/mono
```

Any interpreter with `fontTools` will do; the renderer's venv is named because
it is the one that certainly has it.

A font you cannot redistribute must not be committed. Put it outside the repo
and point `font_dir` at it, or add its directory to `.gitignore` first.
