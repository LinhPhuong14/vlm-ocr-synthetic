"""The dressings an agent can put on a phôi, and the axes it composes them from.

A layout says which columns exist. A *variant* says what the print shop did to
them: the tone of the stock, the weight of the rules, whether the header band
is tinted, whether the type is serif or sans, how tightly the rows are set, and
what decoration got printed alongside. Seven axes, composed rather than
enumerated, because seven small choices give a space no hand-written list of
templates would reach -- and diversity of *dáng* is the point of the whole run.

    catalogue = variants.build(count=48, seed=2026)

Each entry becomes one value of a `variant` attribute in the rules root a run
materialises for itself, so the choice lands in `recipe.to_dict()` beside every
other attribute and the page replays from the record like any other.

Two axes are held back from documents the policy calls `livery`
--------------------------------------------------------------

`type` and `density` change how much room a run takes, and `mark` prints ink
the phôi never had. On a form whose geometry is prescribed those are exactly
the changes that would make the page a different form. So a variant declares
its `level`: `livery` variants move only paint (stock, rules, band, zebra),
`free` variants move everything. `agent/policy.py` decides which documents can
draw which, and the rules enforce it by tag -- see `agent/rules.py`.

Nothing here may use `text-transform` or generated `content:`; both change
pixels without changing the DOM the boxes are measured off.
`sheets/variant.py::forbidden` re-checks every string this module emits.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

# Mirrors `generators/html/sheets/base.py`. Duplicated rather than imported:
# this module runs under the repository's bare interpreter (it writes rules),
# and `sheets` imports the renderer's dependencies.
SERIF = "'LiberationSerif','DejaVu Serif',serif"
SANS = "'DejaVuSans','LiberationSans','DejaVu Sans',sans-serif"
MONO = "'LiberationMono','Cousine',monospace"

# `#sheet ` prefixes every selector so a variant outranks the family sheet it
# is appended after: `table.items th` is (0,1,2) and `#sheet table.items th` is
# (1,1,2), which wins without `!important` -- and leaves a later stage able to
# override it, which `!important` would not.
S = "#sheet"
ITEM = f"{S} table.items th,{S} table.items td"


@dataclass(frozen=True)
class Axis:
    """One thing about a sheet that can differ, and the ways it can differ.

    A value is `(label, css)` or `(label, css, moves)`. `moves` is what makes
    `structure` different in kind from the other six: the others hand the family
    a stylesheet, that one hands it a **different layout spec** -- the blocks of
    the phôi in another order. See `_structure`.
    """

    name: str
    level: str               # livery | free -- the widest class that may use it
    values: dict[str, tuple] = field(default_factory=dict)


def _stock() -> Axis:
    """Tông giấy. Liên 2 hồng, liên 3 xanh -- màu liên là chuyện có thật."""
    return Axis("stock", "livery", {
        "trang": ("giấy trắng", f"{S}{{background:#ffffff;}}"),
        "nga": ("giấy ngà", f"{S}{{background:#fbf7ee;}}"),
        "xam": ("giấy xám nhạt", f"{S}{{background:#f6f6f4;}}"),
        "hong": ("liên hồng", f"{S}{{background:#fdf4f4;}}"),
        "xanh_luc": ("liên xanh lục", f"{S}{{background:#f2faf4;}}"),
        "xanh_lam": ("liên xanh lam", f"{S}{{background:#f3f7fc;}}"),
    })


def _rule() -> Axis:
    """Nét kẻ bảng: máy in, giấy và tuổi của bản kẽm đều đọc được ở đây."""
    return Axis("rule", "livery", {
        "manh": ("nét mảnh", f"{ITEM}{{border-width:.18mm;}}"),
        "chuan": ("nét chuẩn", f"{ITEM}{{border-width:.3mm;}}"),
        "dam": ("nét đậm", f"{ITEM}{{border-width:.5mm;}}"),
        "nhat": ("nét nhạt", f"{ITEM}{{border-width:.25mm;border-color:#8d8d8d;}}"),
        "muc_den": ("nét mực đen", f"{ITEM}{{border-width:.3mm;border-color:#1c1c1c;}}"),
        "khung_ngoai": (
            "chỉ khung ngoài đậm",
            f"{ITEM}{{border-width:.2mm;}}\n"
            f"{S} table.items{{outline:.55mm solid #333;outline-offset:0;}}"),
    })


def _band() -> Axis:
    """Dải tiêu đề cột."""
    return Axis("band", "livery", {
        "trong": ("tiêu đề không nền", f"{S} table.items th{{background:transparent;}}"),
        "xam": ("tiêu đề nền xám", f"{S} table.items th{{background:#ececea;}}"),
        "xam_dam": ("tiêu đề nền xám đậm", f"{S} table.items th{{background:#d8d8d5;}}"),
        "lam": ("tiêu đề nền lam", f"{S} table.items th{{background:#e4ecf6;}}"),
        "luc": ("tiêu đề nền lục", f"{S} table.items th{{background:#e3f1e6;}}"),
        "gach_chan": (
            "tiêu đề gạch chân dày",
            f"{S} table.items th{{background:transparent;border-bottom-width:.7mm;}}"),
    })


def _zebra() -> Axis:
    """Sọc dòng. Bảng kê dài kẻ sọc để mắt không trượt dòng."""
    return Axis("zebra", "livery", {
        "khong": ("không sọc", ""),
        "nhat": ("sọc rất nhạt",
                 f"{S} table.items tr:nth-child(even) td{{background:#fafafa;}}"),
        "xam": ("sọc xám",
                f"{S} table.items tr:nth-child(even) td{{background:#f2f2f0;}}"),
    })


def _type() -> Axis:
    """Bộ chữ. Đổi được cả trang, hoặc chỉ đổi phần tiêu đề/con số."""
    return Axis("type", "free", {
        "co_dien": ("chữ có chân", f"{S}{{font-family:{SERIF};}}"),
        "hien_dai": ("chữ không chân", f"{S}{{font-family:{SANS};}}"),
        "tieu_de_khong_chan": (
            "thân có chân, tiêu đề không chân",
            f"{S}{{font-family:{SERIF};}}\n"
            f"{S} table.items th{{font-family:{SANS};letter-spacing:.15pt;}}"),
        "so_may": (
            "chữ không chân, cột số kiểu máy in",
            f"{S}{{font-family:{SANS};}}\n"
            f"{S} td.r,{S} th.r{{font-family:{MONO};letter-spacing:-.1pt;}}"),
        "gian_chu": ("chữ giãn", f"{S}{{font-family:{SANS};letter-spacing:.22pt;}}"),
    })


def _density() -> Axis:
    """Độ nén dòng. Trang cao thêm thì khung ảnh cao thêm, hộp vẫn nằm trong."""
    return Axis("density", "free", {
        "nen": ("nén dòng",
                f"{ITEM}{{padding:.55mm .9mm;}}\n{S}{{line-height:1.18;}}"),
        "chuan": ("dòng chuẩn",
                  f"{ITEM}{{padding:1mm 1.2mm;}}\n{S}{{line-height:1.3;}}"),
        "thoang": ("dòng thoáng",
                   f"{ITEM}{{padding:1.5mm 1.7mm;}}\n{S}{{line-height:1.42;}}"),
    })


def _mark() -> Axis:
    """Hoạ tiết in kèm — đồ hoạ MỚI, dựng bằng CSS chứ không lấy từ kho ảnh.

    Tất cả vẽ trên `::before`/`::after` với `z-index:-1`: chúng nằm ngoài dòng
    chảy nên không đẩy một chữ nào, và nằm DƯỚI chữ nên không che nhãn. Đây là
    lý do được phép sinh thêm đồ hoạ mà không phá hợp đồng hộp.
    """
    def under(rules: str) -> str:
        return (f"{S}::before{{content:'';position:absolute;z-index:-1;"
                f"pointer-events:none;{rules}}}")

    def over_edge(rules: str) -> str:
        return (f"{S}::after{{content:'';position:absolute;z-index:-1;"
                f"pointer-events:none;{rules}}}")

    return Axis("mark", "free", {
        "khong": ("không hoạ tiết", ""),
        "vach_gay": ("vạch gáy trái",
                     under("left:0;top:0;bottom:0;width:3.2mm;"
                           "background:linear-gradient(90deg,#2f5d8a,#2f5d8a55);")),
        "bang_dinh": ("băng đỉnh trang",
                      under("left:0;right:0;top:0;height:3mm;"
                            "background:linear-gradient(90deg,#1f6f4a,#7cc0a1);")),
        "guilloche": ("nền hoa văn chìm",
                      under("left:0;right:0;top:0;bottom:0;opacity:.055;"
                            "background:repeating-linear-gradient(38deg,#20406b 0 .5mm,"
                            "transparent .5mm 2.6mm),"
                            "repeating-linear-gradient(-38deg,#20406b 0 .5mm,"
                            "transparent .5mm 2.6mm);")),
        "rang_cua": ("mép răng cưa phải",
                     over_edge("right:0;top:0;bottom:0;width:2.4mm;"
                               "background:repeating-linear-gradient(180deg,#c9c9c4 0 1.6mm,"
                               "transparent 1.6mm 3.2mm);")),
        "goc_vuong": ("nẹp góc trên phải",
                      under("right:4mm;top:4mm;width:16mm;height:16mm;"
                            "border-top:.8mm solid #b4482f;border-right:.8mm solid #b4482f;")),
        "vet_cheo": ("vệt loang chéo",
                     under("left:-10%;top:-10%;width:120%;height:120%;opacity:.05;"
                           "background:linear-gradient(28deg,transparent 42%,#213a5c 50%,"
                           "transparent 58%);")),
        "luoi_chan": ("lưới mờ chân trang",
                      under("left:0;right:0;bottom:0;height:14mm;opacity:.09;"
                            "background:repeating-linear-gradient(0deg,#333 0 .25mm,"
                            "transparent .25mm 2mm);")),
    })


def _structure() -> Axis:
    """Dựng lại tờ giấy, không phải sơn lại nó.

    The six axes above hand the family a stylesheet. This one hands it a
    different `sections:` -- the list every sheet family loops over to decide
    which block of the phôi comes next -- so the page comes out with its parts
    in another order, which is what "many layouts from one phôi" has to mean if
    it means anything. Eleven of the sixteen layouts declare `sections:` and
    five of the six families read it.

    Every move is attested rather than invented. Three layouts print
    `letterhead` above `doctitle` and two print it below, so swapping them is
    something Vietnamese paper actually does; `words` sits above the signatures
    on some forms and below on others; a footer note above the signature block
    is ordinary on a printed form. A move whose blocks are not in this layout is
    a no-op, so one value works across every family.

    The CSS half moves geometry the section list cannot: margins, the width of
    the text block, where the signature and total blocks sit, how big the title
    is. All of it reflows -- nothing is clipped -- because `#sheet` has a
    `min-height` and no maximum, so a page that grows stays a taller page and
    every box is still measured off the laid-out DOM.
    """
    return Axis("structure", "free", {
        # No "leave it alone" value. A `free` document is one whose dáng nobody
        # prescribes, and the run is measured on how far its pages sit from the
        # phôi; a dressing that changes nothing fails that by construction.
        # `variant=none` is still there for a document that may not be
        # restructured at all.
        #
        # Eight values, and every one of them moves blocks AND the geometry the
        # blocks sit in. That pairing is not decoration: measured over 83
        # dressings on five phôi, the values that only reordered sections
        # averaged 0.53-0.62 -- a swapped letterhead leaves the other eight
        # blocks exactly where they were -- while the ones that did both
        # averaged 0.69-0.90. The light values are gone and their moves are
        # folded into these.
        "truong_hai_cot": (
            "khối trường xếp hai cột, lề rộng, ký cuối",
            f"{S}{{padding:15mm 14mm;}}\n"
            f"{S} .f{{display:inline-table;width:48%;vertical-align:top;}}\n"
            f"{S} .block .f:nth-child(odd){{padding-right:2mm;}}\n"
            f"{S} table.items{{width:100%;margin-top:3mm;}}",
            (("swap", "letterhead", "doctitle"), ("after", "words", "signatures"))),

        "bang_len_truoc": (
            "bảng hàng lên trước khối bên mua/bên bán",
            f"{S}{{padding:8mm 7mm;}}\n"
            f"{S} .parties,{S} .seller{{padding-top:3mm;}}\n"
            f"{S} table.items{{margin-top:0;}}",
            (("before", "table", "parties"), ("after", "words", "signatures"),
             ("before", "footer", "signatures"))),

        "dan_lai_toan_bo": (
            "dàn lại cả trang: đầu trang xếp chồng, bảng hẹp giữa, ký giữa",
            f"{S}{{padding:16mm 15mm;}}\n"
            f"{S} .head{{display:block;}}\n"
            f"{S} .head > div{{display:block;width:auto;text-align:left;}}\n"
            f"{S} table.items{{width:82%;margin-left:auto;margin-right:auto;}}\n"
            f"{S} .signs{{width:70%;margin:0 auto;}}\n"
            f"{S} .frame{{border:0;padding:0;}}\n{S} .inner{{border:0;}}",
            (("swap", "letterhead", "doctitle"), ("before", "notes", "table"),
             ("after", "words", "signatures"))),

        "ky_len_tren_tong": (
            "chữ ký và chân trang đảo lên trên khối tổng, lề hẹp",
            f"{S}{{padding:11mm 6mm;}}\n"
            f"{S} .signs{{width:100%;padding-top:2mm;}}\n"
            f"{S} .foot{{text-align:right;padding-top:1mm;}}\n"
            f"{S} table.items{{width:96%;}}",
            (("before", "signatures", "totals"), ("before", "footer", "signatures"),
             ("swap", "letterhead", "doctitle"))),

        "le_rong_dao_khoi": (
            "lề rộng, đầu trang xếp chồng, ghi chú lên trước bảng",
            f"{S}{{padding:18mm 17mm;}}\n"
            f"{S} .head{{display:block;}}\n"
            f"{S} .head > div{{display:block;width:auto;text-align:left;}}\n"
            f"{S} table.items{{width:94%;}}",
            (("before", "notes", "table"), ("swap", "letterhead", "doctitle"),
             ("after", "words", "signatures"))),

        "le_hep_tieu_de_lon": (
            "lề hẹp, tiêu đề phóng to, chân trang lên trước chữ ký",
            f"{S}{{padding:5mm 5mm;}}\n"
            f"{S} .t1,{S} .title{{font-size:20pt;letter-spacing:.4pt;}}\n"
            f"{S} table.items{{width:100%;}}\n"
            f"{S} .signs{{width:60%;margin-left:auto;}}",
            (("before", "footer", "signatures"), ("before", "notes", "table"))),

        "tong_trai_ky_phai": (
            "khối tổng dồn trái, chữ ký dồn phải, bảng thu hẹp",
            f"{S}{{padding:13mm 12mm;}}\n"
            f"{S} .signs{{width:50%;margin-left:auto;}}\n"
            f"{S} .foot{{text-align:left;}}\n"
            f"{S} table.items{{width:86%;}}\n"
            f"{S} .frame{{border:0;padding:0;}}\n{S} .inner{{border:0;}}",
            (("before", "footer", "signatures"), ("swap", "letterhead", "doctitle"),
             ("after", "words", "signatures"))),

        "bang_giua_ky_trai": (
            "bảng canh giữa hẹp, chữ ký dồn trái, ghi chú lên đầu",
            f"{S}{{padding:14mm 9mm;}}\n"
            f"{S} table.items{{width:78%;margin-left:auto;margin-right:auto;}}\n"
            f"{S} .signs{{width:58%;margin-right:auto;margin-left:0;}}\n"
            f"{S} .head{{display:block;}}\n"
            f"{S} .head > div{{display:block;width:auto;}}",
            (("before", "notes", "table"), ("before", "signatures", "totals"),
             ("after", "words", "signatures"))),
    })


# Every structure value sets the page's own margins in millimetres now, so all
# of them are wide-only: a thermal roll about 80 mm across has no design margins
# to vary, and `till.py` sets its width itself after `base.document`.
WIDE_ONLY_STRUCTURE = frozenset({
    "truong_hai_cot", "bang_len_truoc", "dan_lai_toan_bo", "ky_len_tren_tong",
    "le_rong_dao_khoi", "le_hep_tieu_de_lon", "tong_trai_ky_phai",
    "bang_giua_ky_trai",
})

AXES: tuple[Axis, ...] = (_stock(), _rule(), _band(), _zebra(),
                          _type(), _density(), _mark(), _structure())

LIVERY_AXES = tuple(axis for axis in AXES if axis.level == "livery")


@dataclass(frozen=True)
class Variant:
    """One dressing: an id, what a person would call it, the CSS, the moves."""

    id: str
    level: str
    label: str
    css: str
    axes: dict[str, str]
    moves: tuple = ()
    # Set by an authored design, which knows its own width requirement; left
    # None by a composed dressing, whose requirement is read off its axes.
    needs_wide: bool | None = None

    @property
    def wide_only(self) -> bool:
        """Whether this dressing needs a sheet wider than a till roll.

        A composed dressing declares this through its `structure` axis. An
        authored one in `agent/redesign.py` cannot -- it has no axes to read --
        so it sets `needs_wide` instead. Before that field existed, every
        authored design reported False here, which is how a two-column sidebar
        layout came to be admissible on an 80 mm thermal roll: `agent/rules.py`
        only writes `excludes: [till_receipt]` for a dressing that says it is
        wide, and none of them said so.
        """
        if self.needs_wide is not None:
            return bool(self.needs_wide)
        return self.axes.get("structure", "") in WIDE_ONLY_STRUCTURE


def _compose(picks: dict[str, str], level: str, axes: tuple[Axis, ...]) -> Variant:
    by_name = {axis.name: axis for axis in axes}
    parts, labels = [], []
    moves: list = []
    for name, value in picks.items():
        entry = by_name[name].values[value]
        label, css = entry[0], entry[1]
        if css.strip():
            parts.append(css)
        if len(entry) > 2:
            moves.extend(entry[2])
        labels.append(label)
    ident = f"{level[0]}_" + "_".join(picks[axis.name] for axis in axes if axis.name in picks)
    return Variant(id=ident, level=level, label=", ".join(labels),
                   css="\n".join(parts), axes=dict(picks),
                   moves=tuple(tuple(move) for move in moves))


def build(count: int = 48, seed: int = 2026, livery_share: float = 0.35) -> list[Variant]:
    """`count` distinct dressings, deterministic in `seed`.

    Distinct by their axis tuple, not by their CSS: two combinations that
    happen to render alike are still two points the sampler can weight apart,
    and collapsing them would quietly bias the mix toward whatever was left.

    `livery_share` of them move paint only, so a form whose geometry is
    prescribed still has somewhere to vary. Below that share a `livery`
    document would draw the same handful of dressings all run.
    """
    if count < 2:
        raise ValueError("a catalogue of fewer than two dressings is not a catalogue")
    rng = random.Random(seed)
    want_livery = max(1, round(count * livery_share))
    out: list[Variant] = []
    seen: set[tuple] = set()

    def take(level: str, axes: tuple[Axis, ...], wanted: int) -> None:
        tries = 0
        made = 0
        # Bounded: the axis space is finite, and a request for more dressings
        # than it holds must fail loudly rather than spin.
        budget = 400 * max(wanted, 1)
        while made < wanted and tries < budget:
            tries += 1
            picks = {axis.name: rng.choice(sorted(axis.values)) for axis in axes}
            key = (level,) + tuple(sorted(picks.items()))
            if key in seen:
                continue
            seen.add(key)
            out.append(_compose(picks, level, axes))
            made += 1
        if made < wanted:
            raise ValueError(
                f"only {made} distinct {level!r} dressings exist, {wanted} asked for")

    take("livery", LIVERY_AXES, want_livery)
    take("free", AXES, count - want_livery)
    return out


def space() -> dict[str, int]:
    """How many distinct dressings each level can reach. For the report."""
    livery = 1
    for axis in LIVERY_AXES:
        livery *= len(axis.values)
    free = 1
    for axis in AXES:
        free *= len(axis.values)
    return {"livery": livery, "free": free}


__all__ = ["AXES", "LIVERY_AXES", "MONO", "SANS", "SERIF", "WIDE_ONLY_STRUCTURE",
           "Axis", "Variant", "build", "space"]
