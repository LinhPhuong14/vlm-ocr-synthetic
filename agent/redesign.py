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

from .variants import FIRST, GUARD, HOLDERS, on

# Mirrors generators/html/sheets/base.py -- see the note in variants.py.
SERIF = "'LiberationSerif','DejaVu Serif',serif"
SANS = "'DejaVuSans','LiberationSans','DejaVu Sans',sans-serif"
MONO = "'LiberationMono','Cousine',monospace"

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
    # ...and one that spends vertical room cannot be worn by a landscape card.
    # `short_only` is the other side of it: a design written FOR those cards,
    # which would look lost on a full sheet.
    short_only: bool = False
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
            on(" > *", "padding-left:26mm;padding-right:5mm;"),
            # The padding above lands on the table as well, and a margin on top
            # of it indented the table twice: 44mm of padding plus 44mm of
            # margin on a sheet 54mm narrower than it needed, which pushed the
            # amount column off the right edge. Zero the padding where the
            # margin takes over. `critic.tran_le` is what found this.
            # The table escapes the indent and runs the full measure, which is
            # what a print shop would do with it and what a dense phôi needs:
            # a VAT form has six columns, and 31mm of margins is width it does
            # not have to give -- an auto-layout table told to be narrower than
            # its columns need overflows to the right rather than shrinking,
            # and that put forty runs off the sheet.
            #
            # `border-collapse:collapse` also makes a table ignore padding, so
            # the indent has to be a margin and the inherited padding has to be
            # zeroed, or the table indents twice.
            on(" > table.items",
               "width:auto;margin-left:3mm;margin-right:3mm;"
               "padding-left:0;padding-right:0;"),
            on(" table.items th, #sheet table.items td", "padding:1mm .8mm;"),
            # The stripe is out of flow, so it adds a column of ink without
            # taking a column of space from anything the label describes.
            "#sheet::before{content:'';position:absolute;left:0;top:0;bottom:0;"
            "width:21mm;background:linear-gradient(160deg,#12304f,#2f6ea8);z-index:-1;}",
            "#sheet::after{content:'';position:absolute;left:21mm;top:0;bottom:0;"
            "width:.6mm;background:#12304f;z-index:-1;}",
            # Almost nothing: three of the eight prescribed documents are
            # landscape cards about 105mm tall whose content already fills
            # them, and 12mm here pushed their footers clean off the card.
            on(" .head, #sheet .brand, #sheet .flag", "padding-top:2mm;"),
            sheet(f"font-family:{SANS};"),
            on(" table.items th", "background:#12304f;color:#fff;border-color:#12304f;"),
            on(" table.items td", "border-left:0;border-right:0;border-color:#c9d6e2;"),
            on(" .signs", "width:auto;max-width:none;margin-left:26mm;"
               "margin-right:5mm;padding-left:0;padding-right:0;"),
            on(" .foot", "text-align:left;padding-left:26mm;"),
        ]),
        changes=(
            ("kiến trúc trang", "một cột dọc, lề đều hai bên",
             "hai vùng: dải nhận diện 21mm bên trái, khối chữ thụt vào 26mm, "
             "riêng bảng hàng chạy tràn hết bề ngang"),
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
            # Vertical room is spent sparingly on purpose: this design is one
            # of the two a prescribed document may wear, and three of those are
            # landscape cards about 105mm tall. At 14mm of sheet padding plus
            # 4mm per block it pushed their footers off the card -- which
            # `critic.tran_le` reported and nothing else would have.
            sheet("padding:4mm 6mm;background:#eef2f6;"),
            on(" > *", "background:#fff;padding:1.8mm 3.5mm;margin-bottom:1.8mm;"
                       "border-radius:2mm;box-shadow:0 .4mm 1.2mm rgba(20,40,70,.14);"),
            # The cards are staggered, not stacked. Uniform padding would be a
            # bulk shift and measure as no change at all.
            #
            # `width:auto` on both, and it is not optional: the families set
            # `width:100%` on these blocks, so a margin alone SHIFTED them
            # instead of narrowing them and every even card ran off the right
            # trim -- the guest block and the signature block on a hotel folio
            # came out with their right-hand column cut in half.
            on(" > *:nth-child(odd)",
               "margin-right:26%;margin-left:0;width:auto;max-width:none;"),
            on(" > *:nth-child(even)",
               "margin-left:26%;margin-right:0;width:auto;max-width:none;"),
            on(" > table.items", "margin-left:0;margin-right:0;width:100%;"
                                 "background:#fff;border-radius:2mm;overflow:hidden;"
                                 "box-shadow:0 .4mm 1.2mm rgba(20,40,70,.14);"),
            on(" table.items th", "background:#1d3b5c;color:#fff;border:0;padding:1mm .9mm;"),
            on(" table.items td", "border:0;border-bottom:.2mm solid #dde5ec;padding:.9mm .9mm;"),
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
            on(" > *:nth-child(odd)",
               "margin-right:34%;margin-left:0;width:auto;max-width:none;"),
            on(" > *:nth-child(even)",
               "margin-left:34%;margin-right:0;width:auto;max-width:none;"),
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
            on(" > *:nth-child(n+3)",
               "margin-left:18%;width:auto;max-width:none;"),
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
            on(" > table.items", "width:auto;margin-left:4mm;margin-right:4mm;"
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
            on(" > *", "margin-left:34mm;margin-right:6mm;"
                       "width:auto;max-width:none;"),
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
            on(FIRST, "background:#14263a;color:#eef4fb;"
                                   "padding:9mm 12mm 8mm;margin-bottom:6mm;"),
            # ...and everything inside it, or a family rule that colours the
            # title keeps it dark and the banner prints black on black. The
            # reviewer caught that as `khong_muc` on three different phôi.
            on(FIRST + " *", "color:#eef4fb;"),
            on(" > table.items", "width:auto;margin-left:6mm;margin-right:6mm;"),
            on(" table.items th", "background:#e8edf3;border-color:#b9c6d4;"),
            on(" table.items td", "border-color:#d8e0e8;"),
            on(" .frame, #sheet .inner", "border:0;padding:0;"),
            sheet(f"font-family:{SANS};"),
        ]),
        changes=(
            ("đầu trang", "chữ đen trên giấy trắng, cùng lề với thân",
             "băng nền xanh đậm tràn hết bề ngang, chữ đảo màu"),
            ("kiến trúc trang", "một lề chung",
             "băng tràn mép, thân thụt 22mm, bảng thụt 6mm — ba mức lề khác nhau"),
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
            on(" > *", "width:auto;max-width:none;"),
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
            on(" > *", "width:auto;max-width:none;"),
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


# ------------------------------------------------------------------ the card
#
# Four of the fifty-two phôi are landscape cards -- an A6 motorbike insurance
# slip, an A5 car certificate, a credit-card-sized health card. They are about
# 105mm tall and their content already fills them, so a design that spends
# vertical room is not a design for them: `bang_thanh_the` at 1.8mm of padding
# per block pushed a moto certificate's footer 360px past the bottom edge.
#
# So these spend none. Everything they do is horizontal -- where a block starts,
# how wide it is, how many columns the page has -- plus colour, which is free.
# `critic.tran_le` is what made the distinction necessary and it is what checks
# that these keep to it.


def _card_panel() -> Design:
    return Design(
        id="the_hai_mang",
        label="Thẻ hai mảng: dải màu dọc bên trái, khối chữ xếp bậc thang",
        wide_only=False, short_only=True, graphic=True,
        css="\n".join([
            sheet("padding:0;"),
            "#sheet::before{content:'';position:absolute;left:0;top:0;bottom:0;"
            "width:30%;background:linear-gradient(155deg,#123f36,#2f8a76);"
            "z-index:-1;}",
            # A staircase, not one indent: a uniform shift is what the distance
            # metric subtracts as bulk, and it would measure as no change.
            on(" > *", "margin-left:32%;margin-right:3%;width:auto;"
                       "max-width:none;padding-left:0;padding-right:0;"),
            on(" > *:nth-child(2)", "margin-left:36%;"),
            on(" > *:nth-child(3)", "margin-left:34%;"),
            on(" > *:nth-child(n+4)", "margin-left:38%;margin-right:2%;"),
            on(" .frame, #sheet .inner", "border:0;"),
            sheet(f"font-family:{SANS};"),
            on(" table.items th", "background:#123f36;color:#fff;border:0;"),
            on(" table.items td", "border:0;border-bottom:.15mm solid #cfe0da;"),
        ]),
        changes=(
            ("kiến trúc thẻ", "một vùng, lề đều hai bên",
             "dải màu dọc chiếm 30% bên trái, chữ dồn sang phải theo bậc thang "
             "32-38%"),
            ("bộ chữ", "chữ có chân", "chữ không chân"),
            ("bảng hàng", "kẻ ô", "bỏ kẻ dọc, tiêu đề nền xanh chữ trắng"),
        ))


def _card_split() -> Design:
    return Design(
        id="the_chia_hai_cot",
        label="Thẻ chia hai cột: nội dung chảy sang cột phải khi hết cột trái",
        wide_only=False, short_only=True, graphic=True,
        css="\n".join([
            # Multi-column is the one restructuring a short wide sheet is
            # actually built for: it costs no height at all -- it gives height
            # back -- and it moves every run after the break to the other side
            # of the page.
            on("", "column-count:2;column-gap:7mm;column-rule:.3mm solid #b9c4cd;"),
            on(" > *", "break-inside:avoid;margin-bottom:1mm;width:auto;"
                       "max-width:none;"),
            on(FIRST, "column-span:all;"
                                   "border-bottom:.5mm solid #1d3b5c;"
                                   "margin-bottom:2mm;"),
            on(" .frame, #sheet .inner", "border:0;"),
            sheet(f"font-family:{SANS};"),
            on(" table.items th", "background:#1d3b5c;color:#fff;border:0;"),
        ]),
        changes=(
            ("dòng chảy", "một cột dọc từ trên xuống",
             "hai cột: hết cột trái thì chảy sang cột phải, có đường kẻ ngăn"),
            ("khối đầu", "cùng cột với phần còn lại",
             "chạy hết bề ngang cả hai cột, kẻ chân đậm"),
            ("bộ chữ", "chữ có chân", "chữ không chân"),
        ))


def _card_right() -> Design:
    return Design(
        id="the_lech_phai",
        label="Thẻ dồn phải: chữ canh phải, bậc thang thụt từ bên phải vào",
        wide_only=False, short_only=True,
        css="\n".join([
            on(" > *", "margin-left:8%;margin-right:2%;text-align:right;"
                       "width:auto;max-width:none;"),
            on(" > *:nth-child(odd)", "margin-left:18%;"),
            on(" > *:nth-child(n+4)", "margin-left:26%;"),
            on(" table.items", "text-align:right;"),
            on(" table.items th:first-child", "text-align:left;"),
            on(" table.items td:first-child", "text-align:left;"),
            on(" .frame", "border-width:.2mm;border-style:double;"),
        ]),
        changes=(
            ("canh chữ", "canh trái", "canh phải toàn thẻ, trừ cột đầu của bảng"),
            ("lề khối", "một lề chung",
             "bậc thang 8-26% tính từ trái, khối lẻ và khối chẵn khác nhau"),
            ("viền thẻ", "một nét", "nét đôi"),
        ))


def _card_bands() -> Design:
    return Design(
        id="the_dai_ngang",
        label="Thẻ dải ngang: mỗi khối một dải nền, bề rộng so le",
        wide_only=False, short_only=True,
        css="\n".join([
            on(" > *", "width:auto;max-width:none;margin-right:0;"),
            on(" > *:nth-child(odd)", "background:#f0f3f6;margin-left:0;"
                                      "margin-right:14%;"),
            on(" > *:nth-child(even)", "background:#fff;margin-left:14%;"
                                       "margin-right:0;"),
            on(FIRST, "background:#1f2a36;color:#f3f6f9;"
                                   "margin-left:0;margin-right:0;"),
            on(FIRST + " *", "color:#f3f6f9;"),
            on(" .frame, #sheet .inner", "border:0;"),
            on(" table.items td", "border-color:#c8d1d9;"),
            on(" table.items th", "border-color:#c8d1d9;"),
        ]),
        changes=(
            ("nền khối", "giấy trắng suốt",
             "dải nền xám và trắng xen kẽ, khối đầu nền tối chữ đảo màu"),
            ("bề rộng khối", "mọi khối rộng bằng nhau",
             "khối lẻ hụt 14% bên phải, khối chẵn hụt 14% bên trái"),
        ))



def _card_tight() -> Design:
    return Design(
        id="the_nen_chat",
        label="Thẻ nén chữ: cỡ chữ nhỏ hơn, dòng sát hơn, đầu thẻ nền tối",
        wide_only=False, short_only=True, graphic=True,
        css="\n".join([
            # The one move that is guaranteed safe on a full card: it gives
            # height back rather than spending it. Every run below the first
            # moves up by a different amount, which is cumulative and therefore
            # not a bulk shift -- on the roll the same idea measured 0.99.
            # On the holders as well as `#sheet`: the insurance families
            # restate the type size on their own panel, so a rule against
            # `#sheet` alone changed nothing at all and the design measured
            # 0.000 -- which the gallery correctly threw away as "did not
            # reach this phôi".
            on("", f"font-size:6.6pt;line-height:1.12;font-family:{SANS};"),
            on(FIRST, "background:#16233a;color:#f2f6fb;"
                                   "padding:1.5mm 3mm;margin-bottom:1.5mm;"),
            on(FIRST + " *", "color:#f2f6fb;"),
            on(" .frame", "border-width:.25mm;border-style:solid;"
                          "border-color:#16233a;"),
            on(" table.items th", "background:#16233a;color:#fff;border:0;"),
            on(" table.items td", "border:0;border-bottom:.12mm solid #d6dde6;"),
            on(" .foot", "border-top:.4mm solid #16233a;"),
        ]),
        changes=(
            ("cỡ chữ và nhịp", "cỡ mặc định của phôi, dòng giãn 1.3",
             "6.6pt, dòng giãn 1.12 — cả thẻ dồn lên, chừa khoảng trống ở đáy"),
            ("đầu thẻ", "chữ đen trên nền giấy",
             "dải nền xanh đen, chữ đảo màu"),
            ("viền và kẻ", "nét mặc định",
             "viền thẻ và các nét kẻ đổi sang cùng một màu xanh đen"),
        ))


# --------------------------------------------------------------- the roll
#
# An 80mm thermal roll cannot have a sidebar, a two-column grid or a 34mm
# indent, so every design above carries `wide_only` and the rules keep them off
# it. That left seven of the fifty-two phôi -- the whole `till` family plus the
# ledger notebook -- with no whole-page redesign at all, which is not a limit of
# the paper: a roll's architecture is its *rhythm*. Where the amount sits
# relative to the item name, whether a row is one line or two, whether the head
# is centred or ranged left, whether the totals are a bar or a boxed block --
# those move every labelled run on the page and they all fit in 80mm.
#
# These four target the till family's own class names (`.head`, `.meta`,
# `.mrow`, `.foot` from `sheets/till.py`) as well as the generic holders, so a
# narrow layout in another family gets what it can of them.


def _roll_two_line() -> Design:
    return Design(
        id="cuon_hai_dong_moi_mon",
        label="Cuộn giấy: mỗi món hai dòng, tiền xuống dòng riêng canh phải",
        wide_only=False,
        css="\n".join([
            "#sheet{padding:4mm 3mm 9mm;}",
            "#sheet .head{text-align:right;margin-bottom:4mm;}",
            "#sheet .head .n{font-size:1.3em;}",
            "#sheet .meta{border:0;border-bottom:.5mm solid #222;"
            "padding:0 0 2mm;margin:0 0 4mm;}",
            "#sheet .mrow .k{font-size:.85em;}",
            # Rows stop being table rows, so every cell reflows: the name takes
            # the first line and the numbers range right underneath it.
            "#sheet table.items{display:block;width:100%;}",
            "#sheet table.items tbody,#sheet table.items thead{display:block;width:100%;}",
            "#sheet table.items tbody tr{display:block;width:100%;"
            "padding:.8mm 0;border-bottom:.15mm dotted #999;}",
            "#sheet table.items tbody td{display:inline-block;padding:0 .6mm;}",
            "#sheet table.items tbody td:first-child{display:block;width:100%;"
            "font-weight:bold;}",
            "#sheet table.items tbody td.r{float:right;}",
            # Not `display:none` on the header: the record has a box for
            # every column title, and hiding one would leave a label pointing
            # at blank paper. `sheets/variant.py::forbidden` refuses it, and
            # `critic.khong_muc` would have caught it on the paper anyway.
            "#sheet table.items thead tr{display:block;width:100%;"
            "border-bottom:.4mm solid #222;padding-bottom:.5mm;}",
            "#sheet table.items thead th{display:inline-block;padding:0 .6mm;"
            "font-size:.85em;letter-spacing:.3pt;}",
            "#sheet tr.total,#sheet tr.grand{display:block;width:100%;"
            "text-align:right;}",
            "#sheet tr.total td,#sheet tr.grand td{display:inline-block;"
            "border:0;padding:.3mm .6mm;}",
        ]),
        changes=(
            ("dòng hàng", "mỗi món một dòng, các cột nằm ngang",
             "mỗi món hai dòng: tên chiếm trọn dòng trên, số lượng và tiền "
             "dồn xuống dòng dưới canh phải"),
            ("tiêu đề cột", "một hàng ô kẻ ngang",
             "gom thành một dòng chữ nhỏ nằm trên vạch đậm"),
            ("khối tổng", "nằm trong bảng, kẻ ngang",
             "tách khỏi bảng, xếp thành khối canh phải"),
            ("đầu trang", "canh giữa, kẹp giữa hai vạch đứt",
             "dồn phải, khối thông tin chỉ còn một vạch đậm dưới chân"),
        ))


def _roll_left() -> Design:
    return Design(
        id="cuon_dau_lech_trai",
        label="Cuộn giấy: đầu trang dồn trái, thông tin xếp dọc",
        wide_only=False,
        css="\n".join([
            "#sheet{padding:4mm 3mm 10mm;}",
            "#sheet .head{text-align:left;border-bottom:.5mm solid #222;"
            "padding-bottom:2.5mm;margin-bottom:4mm;}",
            "#sheet .head .n{font-size:1.6em;letter-spacing:-.3pt;"
            "line-height:1.1;}",
            "#sheet .head .doc{text-align:right;margin-top:4mm;"
            "font-size:1.2em;}",
            # The meta block stops being two columns and becomes a stack, which
            # moves every value off the right margin and under its own label.
            "#sheet .meta{border:0;border-left:.8mm solid #222;"
            "padding:1mm 0 1mm 3mm;margin:0 0 5mm;}",
            "#sheet .mrow{display:block;width:100%;padding-bottom:1mm;}",
            "#sheet .mrow .k{display:block;font-size:.85em;color:#444;}",
            "#sheet .mrow .v{display:block;text-align:left;font-weight:bold;}",
            # The item column takes half the roll rather than what is left over,
            # so every number column starts somewhere new.
            "#sheet table.items td:first-child,#sheet table.items th:first-child"
            "{width:52%;}",
            "#sheet table.items td{padding:1.8mm .3mm;}",
            "#sheet table.items th{padding-bottom:2mm;text-align:right;}",
            "#sheet table.items th:first-child{text-align:left;}",
            "#sheet tr.total td,#sheet tr.grand td{padding-top:2.2mm;}",
            "#sheet .foot{text-align:left;border-top:.2mm dashed #666;"
            "padding-top:3mm;margin-top:6mm;}",
        ]),
        changes=(
            ("đầu trang", "canh giữa", "dồn trái, tên cửa hàng cỡ lớn, "
             "tên chứng từ đẩy sang phải"),
            ("khối thông tin", "nhãn trái - giá trị phải trên cùng một dòng",
             "nhãn trên, giá trị dưới, cả khối kẻ vạch dọc bên trái"),
            ("bảng hàng", "cột tên rộng bao nhiêu tuỳ phần thừa",
             "cột tên chốt 52% bề ngang, các cột số dồn phải, dòng giãn gấp ba"),
            ("chân trang", "canh giữa", "dồn trái dưới một vạch đứt"),
        ))


def _roll_boxed() -> Design:
    return Design(
        id="cuon_khung_kep",
        label="Cuộn giấy: đầu trang trong khung, tổng tiền trong hộp riêng",
        wide_only=False,
        css="\n".join([
            "#sheet{padding:3mm 2mm 12mm;}",
            "#sheet .head{border:.5mm solid #222;padding:4mm 2mm;"
            "margin-bottom:4mm;text-align:left;}",
            "#sheet .head .n{font-size:1.4em;}",
            "#sheet .head .doc{display:inline-block;border-top:.2mm solid #222;"
            "padding-top:2mm;margin-top:2.5mm;}",
            # Each block is boxed with its own padding, and the paddings differ,
            # so the blocks separate from one another instead of the whole roll
            # sliding down by one amount -- which the distance metric subtracts.
            "#sheet .meta{border:.3mm solid #999;background:#efefec;"
            "padding:3mm 2.5mm;margin:0 0 5mm;}",
            "#sheet .mrow{display:block;width:100%;padding:.4mm 0;}",
            "#sheet .mrow .k{display:block;font-size:.85em;}",
            "#sheet .mrow .v{display:block;text-align:right;font-weight:bold;}",
            "#sheet table.items th{border-bottom:.5mm solid #222;"
            "padding-bottom:2.5mm;}",
            "#sheet table.items td{padding:1.5mm .5mm;}",
            "#sheet table.items tbody tr:nth-child(even) td{background:#f4f4f2;}",
            "#sheet tr.grand td{border:.4mm solid #222;background:#e8e8e5;"
            "padding:3mm .6mm;font-size:1.3em;}",
            "#sheet .foot{border:.2mm dashed #444;padding:3mm 2mm;"
            "margin-top:6mm;}",
        ]),
        changes=(
            ("đầu trang", "chữ trần trên nền giấy", "đóng khung viền đậm"),
            ("khối thông tin", "kẹp giữa hai vạch đứt, nhãn và giá trị cùng dòng",
             "đóng khung nền xám, nhãn trên giá trị dưới"),
            ("dòng tổng", "chỉ kẻ chân", "đóng hộp viền đậm, nền xám, chữ to hơn"),
            ("chân trang", "chữ trần", "đóng khung nét đứt"),
        ))


def _roll_airy() -> Design:
    return Design(
        id="cuon_thua_dong",
        label="Cuộn giấy: giãn dòng, mỗi khối cách nhau một khoảng trắng",
        wide_only=False,
        css="\n".join([
            "#sheet{padding:9mm 4mm;line-height:1.75;}",
            "#sheet .head{margin-bottom:6mm;}",
            "#sheet .head .n{font-size:1.35em;letter-spacing:.6pt;}",
            "#sheet .meta{border-top:0;border-bottom:0;margin:5mm 0;}",
            "#sheet .mrow{padding:.9mm 0;border-bottom:.12mm dotted #bbb;}",
            "#sheet table.items{margin:5mm 0;}",
            "#sheet table.items td{padding:1.6mm .4mm;}",
            "#sheet table.items th{border-bottom:0;padding-bottom:2.5mm;"
            "letter-spacing:.5pt;}",
            "#sheet tr.total td,#sheet tr.grand td{border-top:0;"
            "padding-top:2.5mm;}",
            "#sheet .foot{margin-top:8mm;letter-spacing:.4pt;}",
        ]),
        changes=(
            ("nhịp trang", "dòng sát nhau, giấy vừa đủ dài",
             "giãn dòng 1.75, mỗi khối cách nhau 5-8mm, cuộn dài hẳn ra"),
            ("vạch ngăn", "vạch đứt giữa các khối",
             "bỏ vạch, dùng khoảng trắng để ngăn; chỉ mỗi dòng thông tin "
             "còn một nét chấm mảnh"),
        ))



def _roll_banner() -> Design:
    return Design(
        id="cuon_bang_ron_toi",
        label="Cuộn giấy: băng đầu nền tối chữ đảo màu, thông tin hai cột",
        wide_only=False,
        graphic=True,
        css="\n".join([
            "#sheet{padding:0 0 10mm;}",
            "#sheet .head{background:#1d1d1d;color:#fff;padding:5mm 3mm 4mm;"
            "text-align:center;margin-bottom:4mm;}",
            "#sheet .head .n{font-size:1.45em;letter-spacing:.8pt;}",
            "#sheet .head .doc{border-top:.3mm solid #888;margin-top:3mm;"
            "padding-top:2mm;}",
            # Two columns of label/value pairs instead of one full-width row,
            # so half the meta values move left and up at once.
            "#sheet .meta{border:0;margin:0 0 5mm;padding:0;"
            "display:grid;grid-template-columns:1fr 1fr;gap:1.5mm 3mm;}",
            "#sheet .mrow{display:block;width:auto;border-bottom:.12mm solid #ccc;}",
            "#sheet .mrow .k{display:block;font-size:.8em;color:#555;}",
            "#sheet .mrow .v{display:block;text-align:left;}",
            # No margin and no width calc on the table: an auto-layout table
            # whose cells need more room than the declared width overflows it
            # rather than shrinking, and on an 80mm roll that put the amount
            # column past the trim. The sheet's own padding sets the measure,
            # and the cells stay tight enough to fit inside it.
            "#sheet{padding-left:3mm;padding-right:3mm;}",
            "#sheet .head{margin-left:-3mm;margin-right:-3mm;}",
            "#sheet table.items th{background:#1d1d1d;color:#fff;"
            "border-bottom:0;padding:1.2mm .3mm;}",
            "#sheet table.items tbody tr:nth-child(odd) td{background:#f1f1ef;}",
            "#sheet table.items td{padding:1.2mm .3mm;}",
            "#sheet tr.grand td{background:#1d1d1d;color:#fff;font-size:1.15em;"
            "padding:1.8mm .3mm;}",
            "#sheet .foot{margin:6mm 0 0;padding-top:2mm;"
            "border-top:.4mm solid #1d1d1d;}",
        ]),
        changes=(
            ("đầu trang", "chữ đen trên giấy, kẹp vạch đứt",
             "băng nền đen tràn mép, chữ đảo màu trắng"),
            ("khối thông tin", "mỗi dòng một cặp nhãn - giá trị chiếm cả bề ngang",
             "xếp lưới hai cột, nhãn trên giá trị dưới"),
            ("bảng hàng", "tiêu đề kẻ chân, dòng trắng",
             "tiêu đề nền đen chữ trắng, dòng lẻ nền xám"),
            ("dòng tổng", "kẻ chân đậm", "cả dòng nền đen chữ trắng"),
        ))


def _roll_hanging() -> Design:
    return Design(
        id="cuon_treo_dong",
        label="Cuộn giấy: tên món treo lề, số lượng và đơn giá lên dòng trên",
        wide_only=False,
        css="\n".join([
            "#sheet{padding:5mm 3mm 8mm;}",
            "#sheet .head{text-align:left;margin-bottom:3mm;}",
            "#sheet .meta{border-top:0;padding-top:0;}",
            "#sheet .mrow .k{font-weight:bold;}",
            "#sheet table.items{display:block;width:100%;}",
            "#sheet table.items thead,#sheet table.items tbody{display:block;}",
            "#sheet table.items thead tr{display:block;text-align:right;"
            "border-bottom:.3mm solid #444;}",
            "#sheet table.items thead th{display:inline-block;padding:0 .5mm;"
            "font-size:.8em;}",
            "#sheet table.items tbody tr{display:block;padding:1.2mm 0 1.2mm 6mm;"
            "text-indent:-6mm;border-bottom:.12mm dotted #aaa;}",
            # The numbers come FIRST and the name hangs under them, which is the
            # opposite reading order to `cuon_hai_dong_moi_mon` and moves a
            # different set of runs.
            "#sheet table.items tbody td{display:inline;padding:0 1mm 0 0;}",
            "#sheet table.items tbody td:first-child{display:block;"
            "padding-left:6mm;text-indent:0;font-weight:bold;}",
            "#sheet tr.total td,#sheet tr.grand td{display:inline-block;"
            "border:0;}",
            "#sheet tr.total,#sheet tr.grand{display:block;text-align:right;"
            "padding-right:1mm;}",
            "#sheet .foot{text-align:right;margin-top:5mm;}",
        ]),
        changes=(
            ("dòng hàng", "một dòng, các cột thẳng hàng dọc",
             "số lượng và đơn giá chạy thành một dòng chảy, tên món treo "
             "xuống dòng dưới thụt vào 6mm"),
            ("tiêu đề cột", "thẳng hàng với các cột",
             "gom về phải thành một dòng chữ nhỏ"),
            ("chân trang", "canh giữa", "dồn phải"),
        ))


def _roll_tight() -> Design:
    return Design(
        id="cuon_nen_chat",
        label="Cuộn giấy: nén chặt, cỡ chữ nhỏ, cuộn ngắn hẳn lại",
        wide_only=False,
        css="\n".join([
            # Compression is not a bulk shift: every run below the head moves
            # up by a different amount, which is exactly what the distance
            # metric is built to see through a uniform margin change.
            "#sheet{padding:2mm 2mm 4mm;line-height:1.05;font-size:7pt;}",
            "#sheet .head{margin-bottom:1mm;}",
            "#sheet .head .n{font-size:1.15em;line-height:1;}",
            "#sheet .head .doc{margin-top:.5mm;}",
            "#sheet .meta{padding:.3mm 0;margin:.8mm 0;}",
            "#sheet .mrow{line-height:1.05;}",
            "#sheet table.items th{padding:.3mm .2mm;}",
            "#sheet table.items td{padding:.2mm .2mm;}",
            "#sheet tr.grand td{font-size:1.05em;}",
            "#sheet .foot{margin-top:1.5mm;}",
        ]),
        changes=(
            ("nhịp trang", "giãn dòng 1.25, đệm 5mm",
             "giãn dòng 1.05, đệm 2mm, cỡ chữ 7pt — cuộn ngắn lại rõ rệt"),
            ("khoảng cách khối", "mỗi khối cách nhau 1.5-3mm",
             "nén còn dưới 1mm, các khối gần như dính nhau"),
        ))


# Appended to every design, after its own CSS, so it wins on equal specificity.
#
# Whatever a design does to the blocks, the item table keeps the phôi's own
# measure. Two things kept going wrong and this is one rule for both. A design
# that indents `> *` indents the table too, and adding a margin on top of that
# indented it twice. And an auto-layout table told to be narrower than its
# columns need does not shrink -- it overflows to the RIGHT, off the trim,
# silently, on exactly the dense phôi that could least afford it. Between them
# they put runs off the sheet on four families; `critic.tran_le` is what said
# so, on pages nobody would have looked at twice.
def _guarded(design: Design) -> Design:
    from dataclasses import replace

    return replace(design, css=design.css + "\n" + GUARD)


DESIGNS: tuple[Design, ...] = tuple(_guarded(design) for design in (
    _sidebar(), _card(), _two_column(), _table_first(), _editorial(),
    _ledger(), _dark_banner(), _centred(), _three_column(), _stamped_form(),
    _roll_two_line(), _roll_left(), _roll_boxed(), _roll_airy(),
    _roll_banner(), _roll_hanging(), _roll_tight(),
    _card_panel(), _card_tight(), _card_split(), _card_right(), _card_bands(),
))

# The ones an 80mm roll can wear, and the ones a landscape card can. Both are
# the same fact from the caller's side: a design belongs to exactly one of
# three page shapes, and showing it on the other two is how a footer ends up
# 360px off the bottom of a motorbike insurance slip.
NARROW = tuple(design for design in DESIGNS
               if not design.wide_only and not design.short_only)
CARD = tuple(design for design in DESIGNS if design.short_only)
WIDE = tuple(design for design in DESIGNS
             if design.wide_only and not design.short_only)

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
                    moves=design.moves, needs_wide=design.wide_only)
            for design in (designs or DESIGNS)]


__all__ = ["BY_ID", "CARD", "DESIGNS", "GRAPHIC", "HOLDERS", "MONO", "NARROW",
           "SANS", "SERIF", "WIDE",
           "Design", "as_variants", "catalogue", "on", "sheet"]
