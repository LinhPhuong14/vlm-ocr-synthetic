"""A gallery of `generators/html/table.py`, one shape per case in its docstring.

    python3 tools/table_showcase.py -o samples/table-component

Every table below is the SAME 3x4 grid of made-up line items, drawn with a
different `Border`/`zebra`/`Cell` attribute -- so what changes from one panel
to the next is provably the attribute named under it, not the content. Two
panels break that rule on purpose: the merged-cell panel needs a spanning
total row to have something to merge, and the nested-table panel needs a
smaller table to nest.

Needs `playwright` and a Chromium `generators/html/page.find_chromium` can
find (the container this repository develops in already has one).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

from sheets import base  # noqa: E402
from table import Border, Cell, Column, Line, Row, TableSpec, render_table  # noqa: E402

COLUMNS = [Column(10, align="center"), Column(), Column(18, align="right"),
           Column(18, align="right")]
ITEMS = [
    ("1", "Phở bò tái", "45.000", "45.000"),
    ("2", "Trà đá x2", "10.000", "20.000"),
    ("3", "Bánh flan", "15.000", "15.000"),
]


def _rows(header: list[str]) -> list[Row]:
    return [Row.of(*header, header=True)] + [Row.of(*item) for item in ITEMS]


PANELS: list[tuple[str, TableSpec]] = [
    ("Border.grid() — có viền đầy đủ",
     TableSpec(columns=COLUMNS, border=Border.grid(),
               rows=_rows(["STT", "Tên món", "Đơn giá", "Thành tiền"]))),

    ("Border.none() — không viền",
     TableSpec(columns=COLUMNS, border=Border.none(),
               rows=_rows(["STT", "Tên món", "Đơn giá", "Thành tiền"]))),

    ("Border.rows() — không viền dọc (ledger style)",
     TableSpec(columns=COLUMNS, border=Border.rows(0.3),
               rows=_rows(["STT", "Tên món", "Đơn giá", "Thành tiền"]))),

    ("Border.columns() — không viền ngang",
     TableSpec(columns=COLUMNS, border=Border.columns(0.3),
               rows=_rows(["STT", "Tên món", "Đơn giá", "Thành tiền"]))),

    ('Border.grid().without("left", "right") — không viền hai bên',
     TableSpec(columns=COLUMNS, border=Border.grid().without("left", "right"),
               rows=_rows(["STT", "Tên món", "Đơn giá", "Thành tiền"]))),

    ('Border.grid().without("top", "bottom") — không viền trên dưới',
     TableSpec(columns=COLUMNS, border=Border.grid().without("top", "bottom"),
               rows=_rows(["STT", "Tên món", "Đơn giá", "Thành tiền"]))),

    ("Border.frame() — chỉ viền ngoài, không viền trong",
     TableSpec(columns=COLUMNS, border=Border.frame(0.5),
               rows=_rows(["STT", "Tên món", "Đơn giá", "Thành tiền"]))),

    ("header_divider — chỉ một gạch dưới tiêu đề",
     TableSpec(columns=COLUMNS, border=Border.none(),
               header_divider=Line(0.5, color="#333"),
               rows=_rows(["STT", "Tên món", "Đơn giá", "Thành tiền"]))),

    ("Border ngoài dày, trong mỏng + double ở khung",
     TableSpec(columns=COLUMNS,
               border=Border(top=Line(1.0, "double"), right=Line(1.0, "double"),
                              bottom=Line(1.0, "double"), left=Line(1.0, "double"),
                              inner_h=Line(0.2), inner_v=Line(0.2)),
               rows=_rows(["STT", "Tên món", "Đơn giá", "Thành tiền"]))),

    ("zebra rows + tô màu ô/hàng riêng",
     TableSpec(columns=COLUMNS, border=Border.rows(0.25, color="#bbb"),
               zebra=("#ffffff", "#f2f6ff"),
               rows=[Row.of("STT", "Tên món", "Đơn giá", "Thành tiền", header=True),
                     Row.of("1", "Phở bò tái", "45.000", "45.000"),
                     Row([Cell("2"), Cell("Trà đá x2", bg="#fff3cd"), Cell("10.000"),
                          Cell("20.000")]),
                     Row.of("3", "Bánh flan", "15.000", "15.000")])),
]


def _merge_panel() -> TableSpec:
    rows = _rows(["STT", "Tên món", "Đơn giá", "Thành tiền"])
    rows.append(Row([Cell("Tổng cộng", colspan=3, align="right", bold=True,
                          border={"top": Line(0.6)}),
                     Cell("80.000", align="right", bold=True, border={"top": Line(0.6)})]))
    return TableSpec(columns=COLUMNS, border=Border.grid(), rows=rows)


def _nested_panel() -> TableSpec:
    breakdown = TableSpec(
        border=Border.rows(0.2, color="#999"), width="auto",
        rows=[Row.of("hàng", "35.000"), Row.of("thuế", "10.000")],
    )
    rows = [Row.of("STT", "Khoản mục", "Chi tiết", "Thành tiền", header=True),
            Row([Cell("1"), Cell("Combo trưa"), Cell(breakdown), Cell("45.000")])]
    return TableSpec(columns=[Column(10, align="center"), Column(),
                              Column(38), Column(18, align="right")],
                     border=Border.grid(), rows=rows)


PANELS.append(("Ô merge (colspan) — dòng tổng cộng chạy 3 cột", _merge_panel()))
PANELS.append(("Nested table — một bảng con bên trong một ô", _nested_panel()))


def gallery_html() -> str:
    rows_counter = base.Rows()
    blocks = []
    for title, spec in PANELS:
        blocks.append(
            f'<div class="panel"><div class="cap">{base.esc(title)}</div>'
            f'{render_table(spec, rows=rows_counter)}</div>')
    css = """
.panel{margin-bottom:6mm;}
.cap{font-family:%s;font-weight:bold;font-size:8pt;color:#333;
     margin-bottom:1.4mm;}
table{font-family:%s;font-size:8pt;}
""" % (base.SANS, base.SERIF)
    return base.document("".join(blocks), css, paper="A4", padding="8mm")


def render(out_dir: Path) -> Path:
    from page import find_chromium, served  # noqa: E402
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    markup = gallery_html()
    (out_dir / "gallery.html").write_text(markup, encoding="utf-8")

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=find_chromium())
        page = browser.new_page(device_scale_factor=2.0)
        try:
            with served(markup) as uri:
                page.goto(uri, wait_until="load")
            page.wait_for_timeout(60)
            image_path = out_dir / "gallery.jpg"
            page.query_selector("#sheet").screenshot(path=str(image_path), type="jpeg",
                                                      quality=90)
        finally:
            browser.close()
    return image_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("-o", "--out", type=Path,
                        default=REPO_ROOT / "samples" / "table-component")
    args = parser.parse_args()
    image_path = render(args.out)
    print(f"{len(PANELS)} panels -> {image_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
