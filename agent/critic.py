"""The second agent: what is wrong with the page the first one drew.

    python tools/critic_review.py --dataset data/5k_llm

`agent/planner.py` decides what every page is. Nothing until now read the page
back. A planner cannot catch its own mistakes because the mistakes are not in
the decision -- `ornament=qr_dau_trang` and `layout=form_dense` are both legal,
both sensible, and together they print a QR code over the title. That is only
visible after the browser has run, and only to something that looks.

So this is a reviewer, and it reviews the two things a reader would:

**The record.** Boxes that overlap, boxes off the page, boxes with no text,
boxes too small to read, the same sentence repeated. This is the HTML side --
"cái khung này có hợp lý chưa" -- and it needs no image, so it is cheap enough
to run over a whole set.

**The paper.** The same page as a photograph: is there ink where the label says
there is text, is the contrast enough to read, is it sharp enough to read at
all. This is "cắt ra làm bản giấy có hợp lý chưa", and it is the half that
catches what the DOM cannot know, because the DOM is measured before any of the
ageing happens.

Where a seal or a QR landed is checked on the record rather than here, against
the rectangles `ornament.py` wrote down as it struck them. Pixels cannot tell a
QR over a title from a bold heading on a thermal roll -- both come out about
60% dark -- and there is no need to guess at something the renderer recorded.

**Why the findings carry the attributes that drew the page.** A list of broken
pages is a bug report; a list of the *options* that break pages is a fix. Every
finding is joined back through `synthesis.json` to the eight values the agent
chose, so `rank()` can say `ornament=qr_dau_trang` fails at 40% against a base
rate of 3% and `penalties()` can hand the planner a number that makes it stop.
That is the loop the reviewer exists to close: it does not just complain, it
changes what the next run draws.

Nothing here imports the renderer. A review that shared state with the thing it
reviews could prove itself right, and this one has to be able to be wrong.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

# ---------------------------------------------------------------- thresholds
#
# Every number below is a judgement about paper, so each says what it is for.
# They are module constants rather than arguments because a review whose bar
# moves per call cannot be compared across runs, and comparing runs is the
# point.

# Two boxes overlap when their intersection covers this share of the smaller
# one. Table cells share a rule line and touch by a pixel or two; a QR code
# over a title covers a third of it. 0.15 is comfortably between.
OVERLAP = 0.15
# ...and the intersection is at least this many pixels, so a hairline contact
# between two 900-pixel-wide header rules is not a finding.
OVERLAP_PX = 24.0
# ...and the two boxes have to overlap VERTICALLY by at least this share of the
# shorter one. Two lines of one headline are stacked, full-width and share
# their leading, so their boxes touch by a few pixels over their whole width --
# which is a large *area* share and no collision at all. On the shipped
# newspaper phôi that pair already sat at 12%, and a design that tightened the
# line height by a hair pushed it over the area bar. A real collision -- two
# blocks landing on each other, a value printed over its own label -- overlaps
# deeply in both directions.
STACKED = 0.35

# A run shorter than this many pixels is not text an OCR engine can read. In
# pixels rather than as a share of the page on purpose: legibility is absolute.
# Measured page-relative, an A4 sheet's ordinary 14px type scored "too small"
# and a till roll's identical 14px type did not, which said nothing about
# either. Over the whole shipped set the smallest run is 12.3px, so this floor
# is quiet today and would speak the moment a dressing shrank the type.
TINY_PX = 10.0
# A box may hang this far past the trim before it counts as off the sheet:
# the renderer rounds quads outward, so exact equality would flag everything.
SLACK_PX = 2.0

# A page is washed out when this share of its own labelled fields came back
# blank or barely inked. Derived from the per-field measurements rather than
# measured again over the sheet -- see `read_paper`.
WASHED = 0.30
# Variance of the Laplacian below this is a photograph nobody can OCR.
SHARP = 12.0
# A page whose mean grey is outside this band is under- or over-inked as a
# whole -- not a field problem, a press problem.
GREY = (70.0, 252.0)

# Ink against paper INSIDE one labelled box: the difference between its
# lightest and darkest tone after a 3x3 median blur, whichever way round they
# are. The blur is what makes it a measurement rather than a lottery -- it
# removes the single stray pixels JPEG leaves behind, and leaves glyph strokes
# alone.
#
# Percentiles were tried twice and are wrong for this, because a labelled box
# is mostly margin and the share of it that is ink depends on how long the text
# happens to be. At the 10th percentile a perfectly legible `PHIẾU TÍNH TIỀN`
# scored 9. Moved to the 2nd, that box was fine but every REVERSED-TYPE run
# went blank -- `total.grand.label` on `invoice_hotel_compact` is white on a
# purple band, so its 90th percentile is still purple; it scored 29 against a
# bar of 12, and that one layout produced 88 of the 99 "severe" findings in the
# first review of `data/5k_llm`. Moved again to p98-p2, both of those passed
# and a three-letter `Bàn` in a 532px-wide meta row scored 7, because 98% of
# that box really is paper.
#
# The extremes have none of that width dependence. Over the shipped set the
# median box scores 189 and 99.75% score above 20, so these bars sit far below
# anything ordinary in any polarity at any text length.
NO_INK = 20.0          # nothing readable is in there at all
FAINT = 45.0           # something is, and only just

# An ornament may cover this share of a box before it is worth reporting, and
# this much before the field is gone rather than stamped. Not zero either way:
# a company seal landing across the signature block is the convention on
# Vietnamese paper, not an accident, and the marks are composited by
# multiplying at 0.55-0.85 opacity, so ordinary ink still reads through one.
# What no opacity saves is a field a mark covers outright -- the label still
# claims every word of a caption that is not there any more.
COVERED = 0.05
# ...where "gone" is the share of the field times how much solid ink the mark
# actually carries times its opacity -- `ornament.py::solidity` measures the
# first of those off the artwork and records it per mark. Geometry alone cannot
# tell a seal from a QR: a company seal is thin strokes on clear ground and
# measures 0.078 solid, a QR is 0.397 by construction, and at 86% of one
# signature caption the seal leaves it perfectly readable while the QR would
# take the caption with it. Both are "a mark over 86% of a box" to a rectangle.
BURIED = 0.15

# How much of a page may be labelled box before the layout has stopped being a
# document and started being a wall of text, and how little before it is empty.
DENSITY = (0.015, 0.80)

# The same string in this many boxes of one kind is generated content going
# round in a circle, not a document -- but only where repeating is not the
# point. Every signature block on a Vietnamese form carries the same
# *(Ký và ghi rõ họ tên)*, every column header repeats down a run of shards,
# and three items at 25,000đ is a Tuesday. So captions are exempt by kind, and
# a repeated string has to carry a letter and some length before it counts.
REPEATS = 3
REPEAT_MIN_CHARS = 8
CAPTIONS = frozenset({"colhdr", "footer", "note", "subtitle", "period",
                      "terms", "sign.note", "sign.title", "sign.caption"})

SEVERE = "nặng"
MINOR = "nhẹ"

# What each code means, in one line, for the report and the guideline. The
# checklist the swap-in LLM gets is generated from this table, so a check
# added here shows up in its instructions without anybody rewriting them.
CODES: dict[str, tuple[str, str, str]] = {
    # code: (severity, side, what it means)
    "chong_lan": (SEVERE, "record",
                  "hai box đè lên nhau — người đọc mất một trong hai trường"),
    "tran_le": (SEVERE, "record",
                "box nằm ngoài mép giấy — nội dung bị cắt mất"),
    "o_trong": (SEVERE, "record",
                "box có nhãn nhưng không có chữ — nhãn nói dối"),
    "chu_nho": (MINOR, "record",
                "dòng chữ thấp dưới ngưỡng pixel, OCR không đọc nổi"),
    "che_box": (SEVERE, "record",
                "con dấu/QR đóng lên một trường có nhãn và xoá mất chữ"),
    "cham_box": (MINOR, "record",
                 "con dấu chạm vào một trường có nhãn — đúng như dấu thật, "
                 "chữ vẫn đọc được qua nét dấu"),
    "lap_noi_dung": (MINOR, "record",
                     "một chuỗi lặp lại nhiều lần trong cùng một loại trường"),
    "dac_thua": (MINOR, "record",
                 "mật độ chữ trên trang ra ngoài khoảng của một tờ giấy thật"),
    "khong_muc": (SEVERE, "paper",
                  "chỗ có nhãn nhưng trên giấy không có mực"),
    "chu_nhat_mau": (MINOR, "paper",
                     "chữ quá nhạt so với nền ngay trong ô của nó"),
    "nhat": (SEVERE, "paper",
             "mực và giấy quá sát nhau, không đọc được"),
    "mo": (MINOR, "paper", "ảnh nhoè, không đủ nét để đọc"),
    "muc_lech": (MINOR, "paper", "cả trang quá tối hoặc quá trắng"),
}


@dataclass(frozen=True)
class Finding:
    """One thing wrong with one page."""

    code: str
    page: str
    detail: str                       # a Vietnamese sentence a person reads
    where: dict[str, Any] = field(default_factory=dict)  # numbers a tool reads

    @property
    def severity(self) -> str:
        return CODES.get(self.code, (MINOR, "?", ""))[0]

    @property
    def side(self) -> str:
        return CODES.get(self.code, (MINOR, "?", ""))[1]

    def to_dict(self) -> dict[str, Any]:
        return {"code": self.code, "severity": self.severity, "side": self.side,
                "page": self.page, "detail": self.detail, "where": self.where}


# ------------------------------------------------------------- the record side


def _rect(box: dict) -> tuple[float, float, float, float]:
    """(x1, y1, x2, y2) for a box, from its quad if it has one."""
    quad = box.get("quad")
    if isinstance(quad, list) and len(quad) >= 4:
        xs = [float(p[0]) for p in quad[:4]]
        ys = [float(p[1]) for p in quad[:4]]
        return min(xs), min(ys), max(xs), max(ys)
    bbox = box.get("bbox") or {}
    return (float(bbox.get("x1", 0)), float(bbox.get("y1", 0)),
            float(bbox.get("x2", 0)), float(bbox.get("y2", 0)))


def _area(rect) -> float:
    return max(0.0, rect[2] - rect[0]) * max(0.0, rect[3] - rect[1])


def _intersection(one, two) -> float:
    return (max(0.0, min(one[2], two[2]) - max(one[0], two[0]))
            * max(0.0, min(one[3], two[3]) - max(one[1], two[1])))


def overlaps(boxes: list[dict]) -> list[tuple[int, int, float, float]]:
    """Every pair that covers more of the smaller box than `OVERLAP`.

    Sorted by top edge and swept, so a page of 300 boxes costs what a page of
    300 boxes should rather than 45 000 comparisons: once a candidate's top is
    below this box's bottom, nothing further down the list can touch it.
    """
    order = sorted(range(len(boxes)), key=lambda i: _rect(boxes[i])[1])
    rects = {i: _rect(boxes[i]) for i in order}
    found: list[tuple[int, int, float, float]] = []
    for position, i in enumerate(order):
        one = rects[i]
        for j in order[position + 1:]:
            two = rects[j]
            if two[1] >= one[3]:
                break
            shared = _intersection(one, two)
            if shared < OVERLAP_PX:
                continue
            smaller = min(_area(one), _area(two))
            share = shared / smaller if smaller else 0.0
            if share <= OVERLAP:
                continue
            down = min(one[3], two[3]) - max(one[1], two[1])
            shortest = min(one[3] - one[1], two[3] - two[1]) or 1.0
            if down / shortest < STACKED:
                continue          # two lines of one run, sharing their leading
            found.append((i, j, round(share, 3), round(shared, 1)))
    return sorted(found, key=lambda row: -row[2])


def read_page(record: dict, name: str = "",
              marks: Iterable[dict] | None = None) -> list[Finding]:
    """What the record alone says is wrong. No image, no renderer.

    `marks` is the page's `ornament.marks` out of `synthesis.json` -- where the
    renderer actually struck each seal, QR and watermark. Given them, the
    "cái dấu đè lên chữ" check is arithmetic on two rectangles rather than a
    guess from pixels: a QR over a title and a bold heading on a thermal roll
    look the same to any ink-coverage test, and only one of them is a fault.
    """
    from pipeline import record as schema

    page = name or schema.file_name(record)
    boxes = schema.boxes(record)
    width, height = schema.page_size(record) or (0, 0)
    found: list[Finding] = []
    if not boxes or not height:
        return [Finding("o_trong", page, "trang không có box nào", {"boxes": 0})]

    for i, j, share, pixels in overlaps(boxes)[:12]:
        a, b = boxes[i], boxes[j]
        found.append(Finding(
            "chong_lan", page,
            f"{a.get('kind')} và {b.get('kind')} đè nhau "
            f"{share * 100:.0f}% diện tích box nhỏ hơn",
            {"kinds": [a.get("kind"), b.get("kind")], "share": share,
             "pixels": pixels, "rects": [_rect(a), _rect(b)]}))

    small: list[tuple[str, float]] = []
    for box in boxes:
        kind = str(box.get("kind", "?"))
        x1, y1, x2, y2 = _rect(box)
        if (x1 < -SLACK_PX or y1 < -SLACK_PX
                or x2 > width + SLACK_PX or y2 > height + SLACK_PX):
            found.append(Finding(
                "tran_le", page, f"{kind} nằm ngoài khổ giấy {width}x{height}",
                {"kind": kind, "rect": [x1, y1, x2, y2],
                 "page": [width, height]}))
        if not str(box.get("text", "")).strip():
            found.append(Finding("o_trong", page, f"{kind} không có chữ",
                                 {"kind": kind}))
        elif y2 - y1 < TINY_PX:
            small.append((kind, y2 - y1))
    # One finding per page rather than one per box: a dense hospital bill has
    # six hundred cells and would otherwise bury every other page in the run.
    if small:
        shortest = min(small, key=lambda row: row[1])
        found.append(Finding(
            "chu_nho", page,
            f"{len(small)} trường thấp dưới {TINY_PX:.0f}px, "
            f"thấp nhất {shortest[0]} {shortest[1]:.1f}px",
            {"count": len(small), "lowest": round(shortest[1], 1),
             "kinds": sorted({kind for kind, _ in small})[:8]}))

    # Where the renderer struck each mark, against where the labels are.
    for mark in marks or ():
        if mark.get("overprint"):
            # `page_full` and `page_center` are the watermark anchors: a
            # transparent BẢN SAO across the whole sheet is meant to cross the
            # text, and `ornament.OVERPRINT_ANCHORS` says so on purpose.
            continue
        rect = mark.get("box")
        if not (isinstance(rect, list) and len(rect) == 4):
            continue
        rect = tuple(float(v) for v in rect)
        # Older sets carry no `solidity`; assume the worst for them rather than
        # quietly downgrading a finding on data that cannot answer.
        ink = float(mark.get("solidity", 1.0)) * float(mark.get("opacity", 1.0))
        worst: tuple[float, str] = (0.0, "")
        for box in boxes:
            box_rect = _rect(box)
            area = _area(box_rect)
            if area <= 0:
                continue
            share = _intersection(rect, box_rect) / area
            if share > worst[0]:
                worst = (share, str(box.get("kind", "?")))
        lost = worst[0] * ink
        if worst[0] > COVERED:
            found.append(Finding(
                "che_box" if lost >= BURIED else "cham_box", page,
                f"{mark.get('pattern')} đóng ở {mark.get('anchor')} trùm "
                f"{worst[0] * 100:.0f}% lên {worst[1]}, mất "
                f"{lost * 100:.0f}% chữ",
                {"pattern": mark.get("pattern"), "anchor": mark.get("anchor"),
                 "kind": worst[1], "share": round(worst[0], 3),
                 "lost": round(lost, 4), "ink": round(ink, 4),
                 "moved_off_text": bool(mark.get("moved_off_text")),
                 "rect": list(rect)}))

    by_kind: dict[str, Counter] = defaultdict(Counter)
    for box in boxes:
        kind = str(box.get("kind", "?"))
        if kind.endswith(".label") or kind in CAPTIONS:
            continue
        text = " ".join(str(box.get("text", "")).split())
        digits = sum(c.isdigit() for c in text)
        # Mostly-digits is a money amount, and a receipt whose subtotal, total
        # and amount due are the same number is not a broken receipt.
        if (len(text) >= REPEAT_MIN_CHARS
                and sum(c.isalpha() for c in text) >= 3
                and digits / len(text) < 0.5):
            by_kind[kind][text] += 1
    for kind, counts in by_kind.items():
        text, times = counts.most_common(1)[0]
        if times >= REPEATS:
            found.append(Finding(
                "lap_noi_dung", page,
                f"{kind}: {text!r} lặp {times} lần",
                {"kind": kind, "text": text, "times": times}))

    covered = sum(_area(_rect(box)) for box in boxes) / float(width * height or 1)
    if not DENSITY[0] <= covered <= DENSITY[1]:
        found.append(Finding(
            "dac_thua", page, f"box phủ {covered * 100:.0f}% mặt giấy",
            {"density": round(covered, 3)}))
    return found


# -------------------------------------------------------------- the paper side


def read_paper(record: dict, image_path: Path, name: str = "") -> list[Finding]:
    """The same page as a photograph. Needs cv2; call it from the html venv.

    **Everything here is measured where the content is, not over the sheet.**
    A till receipt is two thirds blank paper, so the 5th and 95th percentile of
    the whole image are both paper: a perfectly legible thermal slip scored
    "ink and paper 11/255 apart" and was called illegible. Sharpness has the
    same flaw -- blur variance over a blank half-page is near zero whatever the
    text looks like. So the crops come first, and the page-level statements are
    made out of them.

    The record's boxes are in page coordinates and the image may have been
    resized on the way to disk, so the crops are scaled by the ratio of the
    two sizes. A skewed page defeats them -- the quad no longer bounds the ink
    -- so when the record says the page was warped, the ink checks are skipped
    rather than reporting a hundred false `khong_muc`.
    """
    import cv2
    import numpy as np

    from pipeline import record as schema

    page = name or schema.file_name(record)
    image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
    if image is None:
        return [Finding("khong_muc", page, "không đọc được ảnh",
                        {"path": str(image_path)})]

    found: list[Finding] = []
    height, width = image.shape[:2]
    page_size = schema.page_size(record) or (width, height)
    scale_x = width / float(page_size[0] or width)
    scale_y = height / float(page_size[1] or height)

    boxes = schema.boxes(record)
    if _warped(boxes):
        return found

    # Only "is there ink here at all", and "is there barely any". A test for
    # "is there TOO MUCH ink here" was tried and thrown away: over the shipped
    # set, a box under a QR code and a bold heading on a narrow thermal roll
    # both come out about 60% dark after a 5x5 erosion, so no coverage bar
    # separates them. Where a mark landed is not worth inferring from pixels
    # when the renderer wrote it down -- see `che_box` in `read_page`.
    blank: list[str] = []
    faint: list[tuple[str, float]] = []
    measured = 0
    hull: list[tuple[int, int, int, int]] = []
    for box in boxes:
        x1, y1, x2, y2 = _rect(box)
        top, bottom = max(0, int(y1 * scale_y)), min(height, int(math.ceil(y2 * scale_y)))
        left, right = max(0, int(x1 * scale_x)), min(width, int(math.ceil(x2 * scale_x)))
        crop = image[top:bottom, left:right]
        if crop.size < 200:
            continue
        measured += 1
        hull.append((left, top, right, bottom))
        if min(crop.shape[:2]) >= 3:
            crop = cv2.medianBlur(crop, 3)
        span = float(int(crop.max()) - int(crop.min()))
        if span < NO_INK:
            blank.append(str(box.get("kind", "?")))
        elif span < FAINT:
            faint.append((str(box.get("kind", "?")), span))

    # Reported per page rather than per box: forty blank boxes are one broken
    # page, and forty findings would drown every other page in the run.
    if blank:
        found.append(Finding(
            "khong_muc", page,
            f"{len(blank)} trường có nhãn nhưng không có mực: "
            f"{', '.join(sorted(set(blank))[:6])}",
            {"kinds": sorted(set(blank)), "count": len(blank),
             "share": round(len(blank) / max(measured, 1), 3)}))
    if faint:
        worst = min(faint, key=lambda row: row[1])
        found.append(Finding(
            "chu_nhat_mau", page,
            f"{len(faint)} trường chữ nhạt, nhạt nhất {worst[0]} "
            f"chênh {worst[1]:.0f}/255 giữa chỗ đậm nhất và chỗ nhạt nhất "
            f"trong ô",
            {"count": len(faint), "lowest": round(worst[1], 1),
             "kinds": sorted({kind for kind, _ in faint})[:8]}))

    # A page is washed out when most of its own fields are, which is a
    # statement about the fields rather than a second measurement of them.
    unreadable = (len(blank) + len(faint)) / float(measured or 1)
    if measured and unreadable > WASHED:
        found.append(Finding(
            "nhat", page,
            f"{unreadable * 100:.0f}% số trường trên trang mờ hoặc trắng trơn",
            {"share": round(unreadable, 3), "measured": measured,
             "blank": len(blank), "faint": len(faint)}))

    if hull:
        left = min(r[0] for r in hull)
        top = min(r[1] for r in hull)
        right = max(r[2] for r in hull)
        bottom = max(r[3] for r in hull)
        content = image[top:bottom, left:right]
        if content.size > 4096:
            sharpness = float(cv2.Laplacian(content, cv2.CV_64F).var())
            if sharpness < SHARP:
                found.append(Finding(
                    "mo", page,
                    f"độ nét {sharpness:.1f} trên vùng có chữ, dưới ngưỡng {SHARP}",
                    {"sharpness": round(sharpness, 2)}))
            grey = float(content.mean())
            if not GREY[0] <= grey <= GREY[1]:
                found.append(Finding(
                    "muc_lech", page,
                    f"vùng có chữ trung bình xám {grey:.0f}/255",
                    {"grey": round(grey, 1)}))
    return found


def _warped(boxes: Iterable[dict]) -> bool:
    """True when the quads are not axis aligned, so a bbox crop means nothing."""
    for box in boxes:
        quad = box.get("quad")
        if not (isinstance(quad, list) and len(quad) >= 4):
            continue
        xs = [float(p[0]) for p in quad[:4]]
        ys = [float(p[1]) for p in quad[:4]]
        span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
        if (abs(ys[0] - ys[1]) / span > 0.06 or abs(xs[0] - xs[3]) / span > 0.06):
            return True
    return False


# ------------------------------------------------------------------- the sweep


@dataclass
class Review:
    """Every finding over a set, and what the attributes had to do with it."""

    dataset: str
    pages: int
    findings: list[Finding]
    attributes: dict[str, dict[str, str]]     # page -> attribute -> option
    checked_paper: bool = True

    def by_code(self) -> dict[str, int]:
        return dict(Counter(f.code for f in self.findings).most_common())

    def bad_pages(self, severity: str = SEVERE) -> set[str]:
        return {f.page for f in self.findings if f.severity == severity}

    def rank(self, minimum: int = 25) -> list[dict]:
        """Which option values sit on broken pages more often than the run does.

        `lift` is the option's severe-fault rate over the run's. A value of 1
        means the option is exactly as bad as the average page, which is to say
        innocent; the ones worth acting on are the ones above 2, drawn often
        enough (`minimum`) that the rate is not three pages of noise.
        """
        bad = self.bad_pages()
        base = len(bad) / float(self.pages or 1)
        drawn: dict[tuple[str, str], int] = Counter()
        broke: dict[tuple[str, str], int] = Counter()
        for page, chosen in self.attributes.items():
            for attribute, option in chosen.items():
                drawn[(attribute, option)] += 1
                if page in bad:
                    broke[(attribute, option)] += 1
        rows = []
        for key, times in drawn.items():
            if times < minimum:
                continue
            rate = broke[key] / float(times)
            rows.append({
                "attribute": key[0], "option": key[1], "drawn": times,
                "broken": broke[key], "rate": round(rate, 4),
                "lift": round(rate / base, 2) if base else 0.0,
                "codes": dict(Counter(
                    f.code for f in self.findings
                    if f.severity == SEVERE
                    and self.attributes.get(f.page, {}).get(key[0]) == key[1]
                ).most_common(4)),
            })
        return sorted(rows, key=lambda row: (-row["lift"], -row["broken"]))

    def pairs(self, minimum: int = 8) -> list[dict]:
        """Combinations that fail together far more than either does alone.

        `layout=form_dense` is fine and `ornament=qr_dau_trang` is fine; the
        two of them print a QR over the title. A per-option penalty cannot see
        that, so the pairs are counted separately and banned as pairs.
        """
        bad = self.bad_pages()
        drawn: dict[tuple, int] = Counter()
        broke: dict[tuple, int] = Counter()
        for page, chosen in self.attributes.items():
            items = sorted(chosen.items())
            for index, one in enumerate(items):
                for two in items[index + 1:]:
                    if one[0] == two[0]:
                        continue
                    key = (one, two)
                    drawn[key] += 1
                    if page in bad:
                        broke[key] += 1
        rows = []
        for key, times in drawn.items():
            if times < minimum or broke[key] < minimum:
                continue
            rate = broke[key] / float(times)
            if rate < 0.6:
                continue
            rows.append({"a": list(key[0]), "b": list(key[1]), "drawn": times,
                         "broken": broke[key], "rate": round(rate, 3)})
        return sorted(rows, key=lambda row: (-row["rate"], -row["broken"]))[:40]


def attributes_of(dataset: Path, backend: str = "html") -> dict[str, dict[str, str]]:
    """What each page was drawn from, out of `synthesis.json`.

    Read from the dataset rather than from `agent_plan.json` on purpose: the
    plan says what was decided and the synthesis says what was drawn, and the
    reviewer has to be reviewing the second one. It is also what makes this
    usable on a set the ordinary driver produced, which has no plan at all.
    """
    path = Path(dataset) / backend / "synthesis.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, dict[str, str]] = {}
    for name, entry in (raw.get("pages") or {}).items():
        chosen = entry.get("attributes") or {}
        out[str(name)] = {str(k): str(v) for k, v in chosen.items()
                          if isinstance(v, str)}
    return out


def marks_of(dataset: Path, backend: str = "html") -> dict[str, list[dict]]:
    """Where each page's seals, QR codes and watermarks were actually struck.

    `generators/html/ornament.py::stamp` writes this as it prints -- the
    pattern, the anchor it was asked for, the rectangle it ended up in, and
    whether `clearest` had to move it off the text to get there. A set drawn
    before that report existed simply has none, and the `che_box` check goes
    quiet rather than guessing: silence about marks is honest, and inventing
    their positions from ink would not be.
    """
    path = Path(dataset) / backend / "synthesis.json"
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    out: dict[str, list[dict]] = {}
    for name, entry in (raw.get("pages") or {}).items():
        marks = (entry.get("ornament") or {}).get("marks") or []
        if marks:
            out[str(name)] = [m for m in marks if isinstance(m, dict)]
    return out


def _one(job: tuple) -> list[dict]:
    image, paper, marks = job
    from pipeline import record as schema

    record_path = schema.beside(Path(image))
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as problem:
        return [Finding("o_trong", Path(image).name,
                        f"không đọc được record: {problem}").to_dict()]
    found = read_page(record, Path(image).name, marks)
    if paper:
        found += read_paper(record, Path(image), Path(image).name)
    return [f.to_dict() for f in found]


def sweep(dataset: Path, backend: str = "html", *, paper: bool = True,
          workers: int = 1, limit: int = 0) -> Review:
    """Review every page in a dataset directory."""
    from pipeline import record as schema

    directory = Path(dataset) / backend
    images = schema.images(directory)
    if limit:
        images = images[:limit]
    struck = marks_of(Path(dataset), backend)
    jobs = [(str(image), paper, struck.get(image.name, [])) for image in images]

    rows: list[dict] = []
    if workers > 1 and len(jobs) > 1:
        from concurrent.futures import ProcessPoolExecutor

        with ProcessPoolExecutor(max_workers=workers) as pool:
            for part in pool.map(_one, jobs, chunksize=16):
                rows.extend(part)
    else:
        for job in jobs:
            rows.extend(_one(job))

    findings = [Finding(row["code"], row["page"], row["detail"], row["where"])
                for row in rows]
    return Review(dataset=str(dataset), pages=len(images), findings=findings,
                  attributes=attributes_of(Path(dataset), backend),
                  checked_paper=paper)


# ------------------------------------------------------- feedback, as numbers


# What an option's weight is multiplied by when it is over the lift bar. Not
# zero: the reviewer is a heuristic and a value it dislikes may be a value the
# set needs, so it gets rarer rather than forbidden. A ban is for pairs, which
# are specific enough to be sure about.
PENALTY = 0.25
LIFT = 2.0


def penalties(review: Review, lift: float = LIFT,
              minimum: int = 25) -> dict[str, dict[str, float]]:
    """Weight multipliers per attribute value, for `planner.Chooser`."""
    out: dict[str, dict[str, float]] = defaultdict(dict)
    for row in review.rank(minimum=minimum):
        if row["lift"] < lift or not row["broken"]:
            continue
        # Worse than the bar shrinks it further, floored so a value never
        # becomes undrawable by arithmetic alone.
        factor = max(0.05, PENALTY * (lift / row["lift"]))
        out[row["attribute"]][row["option"]] = round(factor, 3)
    return dict(out)


def feedback(review: Review, lift: float = LIFT) -> dict[str, Any]:
    """The whole review as the one file the pipeline reads back in."""
    counts = review.by_code()
    severe = review.bad_pages(SEVERE)
    return {
        "dataset": review.dataset,
        "pages": review.pages,
        "checked_paper": review.checked_paper,
        "pages_with_severe": len(severe),
        "share_severe": round(len(severe) / float(review.pages or 1), 4),
        "findings": counts,
        "codes": {code: {"severity": s, "side": side, "means": means}
                  for code, (s, side, means) in CODES.items()},
        "thresholds": {"overlap": OVERLAP, "tiny_px": TINY_PX,
                       "washed": WASHED, "sharp": SHARP, "no_ink": NO_INK,
                       "faint": FAINT, "buried": BURIED,
                       "covered": COVERED, "density": list(DENSITY),
                       "lift": lift},
        "rank": review.rank()[:60],
        "penalties": penalties(review, lift=lift),
        "ban": review.pairs(),
        "worst": [f.to_dict() for f in sorted(
            review.findings, key=lambda f: (f.severity != SEVERE, f.code))[:200]],
    }


def load_feedback(path: Path | str) -> tuple[dict[str, dict[str, float]], list]:
    """`(penalties, bans)` out of a feedback file, for the driver."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    weights = {str(a): {str(o): float(v) for o, v in (options or {}).items()}
               for a, options in (raw.get("penalties") or {}).items()}
    bans = [((row["a"][0], row["a"][1]), (row["b"][0], row["b"][1]))
            for row in (raw.get("ban") or []) if row.get("a") and row.get("b")]
    return weights, bans


# --------------------------------------------------------------- the report


def _bar(share: float, width: int = 28) -> str:
    filled = int(round(share * width))
    return "█" * filled + "·" * (width - filled)


def report(review: Review, lift: float = LIFT) -> str:
    """The review as Vietnamese markdown, for a person rather than a tool."""
    counts = review.by_code()
    severe = review.bad_pages(SEVERE)
    minor = review.bad_pages(MINOR) - severe
    clean = review.pages - len(severe) - len(minor)
    lines = [
        "# Báo cáo phản biện",
        "",
        f"Bộ dữ liệu: `{review.dataset}` — {review.pages} trang"
        f"{'' if review.checked_paper else ' (chỉ soi record, không soi ảnh)'}",
        "",
        "| | trang | tỉ lệ |",
        "|---|---:|---:|",
        f"| sạch | {clean} | {clean / max(review.pages, 1) * 100:.1f}% |",
        f"| lỗi nhẹ | {len(minor)} | {len(minor) / max(review.pages, 1) * 100:.1f}% |",
        f"| lỗi nặng | {len(severe)} | {len(severe) / max(review.pages, 1) * 100:.1f}% |",
        "",
        "## Lỗi theo loại",
        "",
        "| mã | mức | soi ở | số lần | nghĩa |",
        "|---|---|---|---:|---|",
    ]
    for code, times in counts.items():
        severity, side, means = CODES.get(code, (MINOR, "?", ""))
        where = "record" if side == "record" else "ảnh giấy"
        lines.append(f"| `{code}` | {severity} | {where} | {times} | {means} |")

    rows = [row for row in review.rank() if row["lift"] >= lift]
    lines += ["", "## Giá trị nào hay hỏng", "",
              f"`lift` là tỉ lệ hỏng của giá trị đó chia cho tỉ lệ hỏng chung của "
              f"cả lượt. `lift = 1` nghĩa là vô can; ở đây liệt kê những giá trị "
              f"từ {lift} trở lên.", ""]
    if not rows:
        lines.append("Không có giá trị nào vượt ngưỡng — lỗi rải đều, "
                     "không đổ được cho tham số nào.")
    else:
        lines += ["| thuộc tính | giá trị | vẽ | hỏng | tỉ lệ | lift | mã lỗi |",
                  "|---|---|---:|---:|---:|---:|---|"]
        for row in rows[:25]:
            codes = ", ".join(f"{k}×{v}" for k, v in row["codes"].items())
            lines.append(
                f"| {row['attribute']} | `{row['option']}` | {row['drawn']} | "
                f"{row['broken']} | {row['rate'] * 100:.0f}% | {row['lift']:.1f} | "
                f"{codes} |")

    bans = review.pairs()
    lines += ["", "## Cặp không nên đi cùng nhau", ""]
    if not bans:
        lines.append("Không có cặp nào hỏng đủ đều để cấm.")
    else:
        lines += ["| A | B | vẽ | hỏng | tỉ lệ |", "|---|---|---:|---:|---:|"]
        for row in bans[:20]:
            lines.append(f"| {row['a'][0]}=`{row['a'][1]}` | "
                         f"{row['b'][0]}=`{row['b'][1]}` | {row['drawn']} | "
                         f"{row['broken']} | {row['rate'] * 100:.0f}% |")

    lines += ["", "## Ví dụ", "",
              "Mỗi mã lỗi một trang, để mở ra xem tận mắt.", ""]
    seen: set[str] = set()
    for finding in review.findings:
        if finding.code in seen:
            continue
        seen.add(finding.code)
        lines.append(f"- `{finding.code}` — `{finding.page}`: {finding.detail}")

    weights = penalties(review, lift=lift)
    lines += ["", "## Phản hồi vào pipeline", "",
              "Những hệ số này được ghi vào `feedback.json`; "
              "`tools/agent_dataset.py --feedback` đọc lại và nhân vào trọng số "
              "khi chọn, nên lượt sau tự tránh.", ""]
    if not weights:
        lines.append("Không cần phạt giá trị nào.")
    for attribute, options in sorted(weights.items()):
        for option, factor in sorted(options.items(), key=lambda kv: kv[1]):
            lines.append(f"- `{attribute}={option}` × {factor} "
                         f"{_bar(1 - factor)}")
    return "\n".join(lines) + "\n"


__all__ = ["BURIED", "CAPTIONS", "CODES", "COVERED", "DENSITY", "FAINT",
           "Finding", "GREY", "STACKED", "WASHED",
           "LIFT", "MINOR", "NO_INK", "OVERLAP", "PENALTY", "REPEATS",
           "Review", "SEVERE", "SHARP", "TINY_PX", "attributes_of", "feedback",
           "load_feedback", "marks_of", "overlaps", "penalties", "read_page",
           "read_paper", "report", "sweep"]
