# generators/html — HTML rendered in a headless browser

Draws the rule-base grid with CSS and screenshots it in Chromium.

```bash
make setup-html
generators/html/.venv/bin/python generators/html/render.py -o outputs -c 10
```

| flag | |
| --- | --- |
| `-c`, `--count` | how many pages |
| `--seed` | first seed; image *n* uses `seed + n` |
| `--layout` | pin one bố cục (`eatery_indexed`, `market_vat`, …) |
| `--scale` | browser device scale factor; higher renders larger before the downscale |

Output: JPEGs plus a `metadata.jsonl` with the same fields the other two
renderers write — `file_name`, `ground_truth`, `text_sequence`, `recipe`.

## How it stays comparable with the glyph renderer

Each cell of the grid becomes one absolutely-positioned span, and positions are
in `ch` units — the width of a character in the sheet's own monospace font. A
column is therefore a character wide in the browser exactly as it is on the
character grid, so the same seed puts the same word in the same column here as
in the glyph render.

Two details that are easy to get wrong, and both were:

* **`ch` is relative to the element's own font size.** Scaling the positioned
  span would scale the grid with it, so a 1.5em grand total would be
  right-aligned against a box 1.5 columns too wide and run off the paper. The
  positioned span keeps the sheet's font size; an inner element does the
  scaling.
* **An element screenshot clips at the element's box.** Cells set above 1em
  overflow their fixed-height line box, so the sheet reserves the tallest
  cell's overflow as padding — without it the shop name on the first row is
  decapitated.

An enlarged cell is clamped to its column width, exactly as the glyph renderer
clamps it, so neither backend can produce an overflow the other does not.

## What is deliberately different

The browser brings its own text shaping, font fallback and synthetic bolding,
and the result is a **flat scan**: no background, no perspective, no lamp. The
glyph renderer produces a photograph and genalog produces a print. Those three
are different distributions on purpose — a model that has only seen one has not
seen the others.

Fonts are embedded as `@font-face` from `fonts/`, never left to a CSS stack
falling through to whatever the container has. A fallback font without
Vietnamese diacritics renders blank boxes while the label still claims the
diacritics were printed.

## Chromium

The Claude Code container ships a build under `/opt/pw-browsers`, which
`find_chromium()` locates. **Do not run `playwright install`** — it re-downloads
several hundred megabytes and is not needed. Elsewhere, install a browser the
usual way or point `find_chromium` at one.
