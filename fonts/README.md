# Fonts

Shared by all three renderers. `rules/visual.yaml` names a directory
(`font_dir: mono`) for the glyph renderer and a CSS stack (`font_family`) for
the two HTML renderers; both must resolve to the same typeface, or the
backends wrap lines differently and stop being comparable.

These are committed, unlike the fonts under
`generators/synthdog/resources/font/`, because every one of them is
redistributable and a clone with no fonts cannot render anything at all.

| directory | fonts | licence |
| --- | --- | --- |
| `mono/` | Liberation Mono (Regular, Bold) | SIL Open Font License 1.1 |
| `mono/` | Cousine (Regular, Bold) | Apache License 2.0 |
| `mono/` | Noto Mono | SIL Open Font License 1.1 |
| `sans/` | Liberation Sans, Arimo | OFL 1.1 / Apache 2.0 |
| `sans/` | DejaVu Sans (Regular, Bold) | Bitstream Vera / Public domain additions |
| `sans/` | Noto Sans | SIL Open Font License 1.1 |

## Vietnamese coverage is not optional

Every font here has been checked to cover the full Vietnamese alphabet. That
check is not a formality — **DejaVu Sans Mono fails it**, missing 46 characters
including `Ấ Ầ Ẩ Ẫ Ắ Ế Ề Ể Ễ Ố Ồ Ổ Ỗ`, which is why it is not in `mono/` even
though it is the obvious monospace choice. A missing glyph renders as a blank
box, and the label still claims the word was printed.

Check anything you add before a long run:

```bash
generators/synthdog/.venv/bin/python generators/synthdog/tools/check_fonts.py fonts/mono
```

Fonts you cannot redistribute go in `generators/synthdog/resources/font/`
instead, which `.gitignore` keeps out of the repository.
