"""Whole page architectures, authored rather than composed.

`agent/variants.py` builds a dressing by picking one value on each of eight
axes. That reaches a large space cheaply and it has a ceiling: measured against
`agent/distance.py`, the axes moved 0.53-0.90 of a page's runs and most of the
mass sat below 0.70, because every combination is still *the same page with
different paint and margins*. Eight small decisions do not add up to a different
layout; one large decision does.

So these are ten designs, each written out as a page a print shop would actually
produce, and each declaring what it changes against the phôi so the report can
say it. A sidebar layout is not a margin change. A borderless ledger is not a
border width. A dark banner with reversed type is not a background colour.

**What a design may touch.** The block order (`sections:`), the container's
layout mode (a one-column flow becomes a two-column grid), the width and
placement of every block in it, the type system, the colour system, and how the
item table presents itself. What it may not touch is the box contract:
`sheets/variant.py::forbidden` still refuses `text-transform` and any `content`
carrying words, and every box is still measured off the DOM after the CSS ran.

**Why the selectors are lists.** The families do not agree on where the blocks
live: `modern`, `medical` and `periodical` put them straight under `#sheet`,
`statutory` nests them in `.frame > .inner`, `insurance` in `main`. A design
that named one of those would silently do nothing on the other three, so every
rule is emitted for all of them and lands wherever the blocks actually are.
"""

from __future__ import annotations

from dataclasses import dataclass

# Mirrors generators/html/sheets/base.py -- see the note in variants.py.
SERIF = "'LiberationSerif','DejaVu Serif',serif"
SANS = "'DejaVuSans','LiberationSans','DejaVu Sans',sans-serif"
MONO = "'LiberationMono','Cousine',monospace"

# Where a family keeps the blocks a design rearranges.
HOLDERS = ("#sheet", "#sheet .inner", "#sheet main")


def on(selector: str, body: str) -> str:
    """One rule, emitted for every container a family might be using."""
    return "\n".join(f"{holder}{selector}{{{body}}}" for holder in HOLDERS)


def sheet(body: str) -> str:
    return f"#sheet{{{body}}}"


@dataclass(frozen=True)
class Design:
    """One whole-page architecture, and what it changes about the phôi."""

    id: str
    label: str
    css: str
    # (mặt, phôi gốc, bản dựng lại) -- the report's own rows.
    changes: tuple[tuple[str, str, str], ...] = ()
    moves: tuple[tuple[str, str, str], ...] = ()
    # A design that needs a full-width sheet cannot be worn by a till roll.
    wide_only: bool = True
    graphic: bool = False        # a design meant to read as a designed piece

    def report(self) -> list[dict]:
        return [{"mặt": a, "phôi gốc": b, "bản dựng lại": c} for a, b, c in self.changes]


def _sidebar() -> Design:
    return Design(
        id="cot_nhan_dien_trai",
        label="Dải nhận diện dọc bên trái, nội dung dồn phải",
        graphic=True,
        css="\n".join([
            sheet("padding:0;"),
            on(" > *", "padding-left:44mm;padding-right:10mm;"),
            on(" > table.items", "width:calc(100% - 54mm);margin-left:44mm;"),
            # The stripe is out of flow, so it adds a column of ink without
            # taking a column of space from anything the label describes.
            "#sheet::before{content:'';position:absolute;left:0;top:0;bottom:0;"
            "width:36mm;background:linear-gradient(160deg,#12304f,#2f6ea8);z-index:-1;}",
            "#sheet::after{content:'';position:absolute;left:36mm;top:0;bottom:0;"
            "width:.6mm;background:#12304f;z-index:-1;}",
            on(" .head, #sheet .brand, #sheet .flag", "padding-top:12mm;"),
            sheet(f"font-family:{SANS};"),
            on(" table.items th", "background:#12304f;color:#fff;border-color:#12304f;"),
            on(" table.items td", "border-left:0;border-right:0;border-color:#c9d6e2;"),
            on(" .signs", "width:62%;margin-left:44mm;"),
            on(" .foot", "text-align:left;padding-left:44mm;"),
        ]),
        changes=(
            ("kiến trúc trang", "một cột dọc, lề đều hai bên",
             "hai vùng: dải nhận diện 36mm bên trái, nội dung thụt vào 44mm"),
            ("bộ chữ", "chữ có chân", "chữ không chân toàn trang"),
            ("bảng hàng", "kẻ ô bốn cạnh", "bỏ kẻ dọc, tiêu đề nền xanh chữ trắng"),
            ("khối chữ ký", "canh giữa hoặc hai cột đều", "dồn về mép nội dung bên phải"),
        ),
        moves=(("swap", "letterhead", "doctitle"),))


def _card() -> Design:
    return Design(
        id="bang_thanh_the",
        label="Bảng hàng thành thẻ nổi trên nền có màu",
        graphic=True,
        css="\n".join([
            sheet("padding:14mm 8mm;background:#eef2f6;"),
            on(" > *", "background:#fff;padding:4mm 5mm;margin-bottom:4mm;"
                       "border-radius:2mm;box-shadow:0 .4mm 1.2mm rgba(20,40,70,.14);"),
            # The cards are staggered, not stacked. Uniform padding would be a
            # bulk shift and measure as no change at all.
            on(" > *:nth-child(odd)", "margin-right:26%;margin-left:0;"),
            on(" > *:nth-child(even)", "margin-left:26%;margin-right:0;"),
            on(" > table.items", "margin-left:0;margin-right:0;width:100%;"
                                 "background:#fff;border-radius:2mm;overflow:hidden;"
                                 "box-shadow:0 .4mm 1.2mm rgba(20,40,70,.14);"),
            on(" table.items th", "background:#1d3b5c;color:#fff;border:0;padding:1.6mm 1.4mm;"),
            on(" table.items td", "border:0;border-bottom:.2mm solid #dde5ec;padding:1.5mm 1.4mm;"),
            on(" .frame", "border:0;padding:0;background:transparent;box-shadow:none;"),
            on(" .inner", "border:0;padding:0;"),
            sheet(f"font-family:{SANS};line-height:1.38;"),
        ]),
        changes=(
            ("nền trang", "giấy trắng", "nền xám xanh, từng khối là thẻ trắng nổi"),
            ("khối nội dung", "chảy liền nhau trên một tờ, cùng lề",
             "mỗi khối một thẻ riêng bo góc có bóng, so le trái/phải 26%"),
            ("bảng hàng", "kẻ ô đầy đủ", "bỏ hết kẻ, chỉ còn kẻ chân dòng nhạt"),
            ("bộ chữ", "chữ có chân", "chữ không chân, dòng thoáng hơn"),
        ),
        moves=(("after", "words", "signatures"),))


def _two_column() -> Design:
    return Design(
        id="hai_cot_so_le",
        label="Khối lẻ dồn trái, khối chẵn dồn phải, bảng trải hết",
        css="\n".join([
            sheet("padding:13mm 10mm;"),
            # Differential, and that is the point: a uniform indent is a bulk
            # shift and `agent/distance.py` subtracts it, correctly -- the page
            # would have moved as one piece and rearranged nothing.
            on(" > *:nth-child(odd)", "margin-right:34%;margin-left:0;"),
            on(" > *:nth-child(even)", "margin-left:34%;margin-right:0;"),
            on(" > table.items", "margin-left:0;margin-right:0;width:100%;"),
            on(" table.items th, #sheet table.items td", "padding:1.1mm 1.2mm;"),
        ]),
        changes=(
            ("kiến trúc trang", "mọi khối trải hết bề ngang",
             "khối lẻ chiếm 2/3 bên trái, khối chẵn 2/3 bên phải, so le nhau"),
            ("bảng hàng", "thụt theo khung", "trải hết bề ngang, phá thế so le"),
            ("thứ tự khối", "tiêu đề trên letterhead",
             "letterhead lên trước, số tiền bằng chữ xuống dưới chữ ký"),
        ),
        moves=(("swap", "letterhead", "doctitle"), ("after", "words", "signatures")))


def _table_first() -> Design:
    return Design(
        id="bang_dan_dau",
        label="Bảng hàng lên đầu trang, khối nhận diện xuống dưới",
        css="\n".join([
            sheet("padding:10mm 9mm;"),
            on(" > table.items", "margin-top:2mm;margin-bottom:6mm;"),
            on(" > *:nth-child(n+3)", "margin-left:18%;"),
            on(" table.items th", "background:#222;color:#fff;border-color:#222;"),
            sheet(f"font-family:{SANS};font-size:8.2pt;"),
        ]),
        changes=(
            ("thứ tự đọc", "nhận diện → bảng → tổng → ký",
             "bảng → tổng → nhận diện → ký: đảo hẳn trục dọc của tờ giấy"),
            ("canh khối", "mọi khối cùng lề trái",
             "từ khối thứ ba trở đi thụt vào 18%, tạo bậc thang"),
            ("dải tiêu đề bảng", "nền xám nhạt", "nền đen chữ trắng"),
        ),
        moves=(("before", "table", "parties"), ("after", "words", "signatures"),
               ("before", "footer", "signatures")))


def _editorial() -> Design:
    return Design(
        id="dan_bao_chi",
        label="Dàn kiểu toà soạn: khối đầu tràn mép, thân thụt sâu",
        graphic=True,
        css="\n".join([
            sheet(f"padding:14mm 0 12mm;font-family:{SERIF};line-height:1.5;"),
            on(" > *", "padding-left:46mm;padding-right:10mm;"),
            on(" > *:nth-child(-n+2)", "padding-left:6mm;padding-right:6mm;"
                                       "border-bottom:.7mm solid #111;padding-bottom:4mm;"),
            on(" > table.items", "width:calc(100% - 56mm);margin-left:46mm;"
                                 "border-top:.7mm solid #111;border-bottom:.7mm solid #111;"),
            on(" table.items th", "background:transparent;border:0;"
                                  "border-bottom:.3mm solid #111;padding:1.6mm .8mm;"),
            on(" table.items td", "border:0;padding:1.4mm .8mm;"),
            on(" .frame, #sheet .inner", "border:0;padding:0;"),
        ]),
        changes=(
            ("kiến trúc trang", "một lề chung cho cả tờ",
             "hai khối đầu tràn ra mép 6mm, phần thân thụt vào 46mm"),
            ("khung trang", "khung viền bao quanh", "bỏ khung, kẻ ngang dày phân vùng"),
            ("bảng hàng", "lưới ô kẻ bốn cạnh", "chỉ kẻ trên và dưới, trong lòng để trống"),
        ),
        moves=(("swap", "letterhead", "doctitle"), ("before", "notes", "table")))


def _ledger() -> Design:
    return Design(
        id="so_cai_khong_vien",
        label="Kiểu sổ cái: bảng tràn mép, khối chữ thụt sâu",
        css="\n".join([
            sheet(f"padding:15mm 6mm;font-family:{SANS};font-size:8pt;"),
            on(" > *", "margin-left:34mm;margin-right:6mm;"),
            on(" > table.items", "margin-left:0;margin-right:0;width:100%;"),
            on(" table.items th, #sheet table.items td", "border:0;"
               "border-bottom:.2mm solid #b9b9b9;padding:1.5mm 1.6mm;"),
            on(" table.items th", "background:transparent;border-bottom:.6mm solid #333;"),
            on(" table.items tr:nth-child(even) td", "background:#f7f7f5;"),
            on(" .frame, #sheet .inner", "border:0;padding:0;"),
            on(" td.r, #sheet th.r", f"font-family:{MONO};letter-spacing:-.15pt;"),
        ]),
        changes=(
            ("kiến trúc trang", "bảng và chữ cùng một lề",
             "bảng tràn hết bề ngang, mọi khối chữ thụt vào 34mm"),
            ("bảng hàng", "lưới ô kẻ bốn cạnh", "bỏ hết viền, chỉ kẻ chân từng dòng"),
            ("cột số", "cùng bộ chữ với phần còn lại", "bộ chữ máy in, chữ số đều bề ngang"),
        ),
        moves=(("before", "footer", "signatures"),))


def _dark_banner() -> Design:
    return Design(
        id="bang_ron_toi",
        label="Băng đầu trang nền tối tràn mép, thân trang thụt vào",
        graphic=True,
        css="\n".join([
            sheet("padding:0 0 12mm;"),
            on(" > *", "padding-left:22mm;padding-right:12mm;"),
            on(" > *:first-child", "background:#14263a;color:#eef4fb;"
                                   "padding:9mm 12mm 8mm;margin-bottom:6mm;"),
            on(" > table.items", "width:calc(100% - 20mm);margin-left:10mm;"),
            on(" table.items th", "background:#e8edf3;border-color:#b9c6d4;"),
            on(" table.items td", "border-color:#d8e0e8;"),
            on(" .frame, #sheet .inner", "border:0;padding:0;"),
            sheet(f"font-family:{SANS};"),
        ]),
        changes=(
            ("đầu trang", "chữ đen trên giấy trắng, cùng lề với thân",
             "băng nền xanh đậm tràn hết bề ngang, chữ đảo màu"),
            ("kiến trúc trang", "một lề chung",
             "băng tràn mép, thân thụt 22mm, bảng thụt 10mm — ba mức lề khác nhau"),
        ),
        moves=(("swap", "letterhead", "doctitle"), ("after", "words", "signatures")))


def _centred() -> Design:
    return Design(
        id="cot_giua_hep",
        label="Cột chữ hẹp canh giữa, bảng và khối cuối tràn rộng",
        css="\n".join([
            sheet("padding:18mm 6mm;"),
            on(" > *", "margin-left:38mm;margin-right:38mm;text-align:center;"),
            on(" > table.items", "margin-left:0;margin-right:0;width:100%;text-align:left;"),
            on(" > *:last-child", "margin-left:0;margin-right:0;"),
            on(" .f, #sheet .fld", "text-align:left;"),
            on(" .frame", "border:.3mm solid #555;padding:4mm;"),
            sheet(f"font-family:{SERIF};line-height:1.42;"),
        ]),
        changes=(
            ("bề rộng cột chữ", "gần hết bề ngang tờ giấy",
             "khối chữ thụt 38mm hai bên, riêng bảng và khối cuối tràn hết"),
            ("canh lề khối", "canh trái", "khối chữ canh giữa, bảng giữ canh trái"),
        ),
        moves=(("before", "notes", "table"), ("swap", "letterhead", "doctitle")))


def _three_column() -> Design:
    return Design(
        id="bac_thang_phai",
        label="Bậc thang: mỗi khối thụt sâu hơn khối trên nó",
        css="\n".join([
            sheet("padding:11mm 8mm;"),
            on(" > *:nth-child(2)", "margin-left:6%;"),
            on(" > *:nth-child(3)", "margin-left:12%;"),
            on(" > *:nth-child(4)", "margin-left:18%;"),
            on(" > *:nth-child(n+5)", "margin-left:24%;margin-right:0;"),
            on(" > table.items", "margin-left:0;width:100%;"),
            on(" table.items th, #sheet table.items td", "padding:.9mm 1mm;"),
            sheet(f"font-family:{SANS};"),
        ]),
        changes=(
            ("kiến trúc trang", "mọi khối cùng lề trái",
             "bậc thang: khối thứ hai thụt 6%, thứ ba 12%, từ thứ năm trở đi 24%"),
            ("bảng hàng", "theo lề chung", "kéo về lề trái, phá thế bậc thang"),
            ("thứ tự khối", "ký rồi tới chân trang", "chân trang lên trước ký"),
        ),
        moves=(("before", "footer", "signatures"), ("after", "words", "signatures")))


def _stamped_form() -> Design:
    return Design(
        id="phieu_dong_dau_lon",
        label="Phiếu nén chặt, khối ký đóng khung đưa lên trước khối tổng",
        css="\n".join([
            sheet(f"padding:9mm 8mm;font-family:{SANS};font-size:7.8pt;line-height:1.2;"),
            on(" > *:nth-child(even)", "margin-left:12%;margin-right:0;"),
            on(" > *:nth-child(odd)", "margin-left:0;margin-right:12%;"),
            on(" > table.items", "margin-left:0;margin-right:0;width:100%;"),
            on(" .signs", "border:.4mm solid #444;padding:3mm;margin-bottom:5mm;"),
            on(" table.items th, #sheet table.items td", "padding:.7mm .9mm;"),
            on(" table.items th", "background:#ddd;"),
            on(" .frame", "border:.8mm double #444;padding:2mm;"),
        ]),
        changes=(
            ("khối chữ ký", "nằm cuối trang, không khung",
             "đóng khung, đưa lên trước khối tổng"),
            ("kiến trúc trang", "mọi khối cùng lề",
             "khối chẵn thụt trái 12%, khối lẻ hụt phải 12%, so le"),
            ("mật độ", "dòng chuẩn", "nén chặt: dòng 1.2, ô bảng mỏng"),
            ("khung trang", "viền đơn", "viền đôi"),
        ),
        moves=(("before", "signatures", "totals"), ("before", "footer", "signatures")))


DESIGNS: tuple[Design, ...] = (
    _sidebar(), _card(), _two_column(), _table_first(), _editorial(),
    _ledger(), _dark_banner(), _centred(), _three_column(), _stamped_form(),
)

BY_ID = {design.id: design for design in DESIGNS}

# Designs that read as a designed piece rather than a filled-in form. A phôi
# the law prescribes gets these two, per the owner's decision to let prescribed
# documents be redrawn in a more graphic direction -- the report still says
# which documents those are.
GRAPHIC = tuple(design for design in DESIGNS if design.graphic)


def catalogue() -> list[Design]:
    return list(DESIGNS)


def as_variants(designs=None) -> list:
    """The designs, in the shape `agent/rules.py` already materialises.

    A `Design` is authored and a `Variant` is composed, but from the rules'
    point of view they are the same thing: an id, a level, some CSS and some
    section moves. Reusing the shape means the whole run -- planning, the
    `variant` attribute, `sheets/variant.py`, the record, the replay -- works on
    these without knowing they were written by hand.
    """
    from .variants import Variant

    return [Variant(id=design.id, level="free", label=design.label,
                    css=design.css, axes={"design": design.id},
                    moves=design.moves)
            for design in (designs or DESIGNS)]


__all__ = ["BY_ID", "DESIGNS", "GRAPHIC", "HOLDERS", "MONO", "SANS", "SERIF",
           "Design", "as_variants", "catalogue", "on", "sheet"]
