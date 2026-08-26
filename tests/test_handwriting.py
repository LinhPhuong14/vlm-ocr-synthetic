"""The handwriting seam, everything above the checkpoint.

No torch and no browser here, and -- deliberately -- no numpy or Pillow either
in anything but the two tests that ask for them. `handwriting.py` keeps its
pixel work behind local imports for exactly this reason: what is worth testing
is a policy over strings and a rewrite of markup, and CI runs the suite on
pytest and PyYAML alone.

The property that matters most is the last one here. Inking a page must not
change what the page **says**: the ink replaces the drawing of a value, never
the value, and `labelled_runs` -- which is what `check_boxes` rebuilds a page's
expected fields from -- must return exactly the same pairs before and after.
A break there would not look like a break. It would look like a dataset.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

import handwriting  # noqa: E402
import sheets  # noqa: E402

import rulebase  # noqa: E402


class FakeHand:
    """A hand that writes nothing and reports what it was asked to write.

    An ink source is four methods -- `writable`, `refusal`, `span`, `css` --
    and `fill` calls nothing else, which is why the double is this small and
    why `FontHand` could be added without `fill` learning a second shape. The
    policy under test here is the model's, so it delegates to the module.
    """

    source = "fake"

    def __init__(self, refuse: set[str] | None = None):
        self.asked: list[str] = []
        self.refuse = refuse or set()

    def writable(self, text, page):
        return handwriting.writable(text)

    def refusal(self, text, page):
        return handwriting.refusal(text)

    def span(self, kind, classes, text, page):
        if text in self.refuse:
            raise ValueError("characters outside the alphabet: '@'")
        self.asked.append(text)
        # Real ink is a PNG; the double never makes one. What `fill` is
        # responsible for is the markup around it, and that is what comes back.
        return handwriting.ink_span(kind, classes, text, b"png", (16 * len(text), 32),
                                    page.height_em, page.sit())

    def css(self, page):
        return handwriting.CSS


# --------------------------------------------------------------- the policy

@pytest.mark.parametrize("text", [
    "Lê Thị Kiều Trinh",
    "Chuyển khoản",
    "Hai trăm ba mươi tám triệu đồng",
    "Đinh Công Khanh",
    "A",                      # a lone capital is a word, not an all-caps word
])
def test_writable(text):
    assert handwriting.writable(text)


@pytest.mark.parametrize("text,why", [
    ("15/06/2018", "digit"),          # a slash AND digits: the digit is named
    ("3.920.000", "digit"),
    ("243 Nguyễn Văn Cừ", "digit"),
    ("LÊ QUANG ĐẠO", "allcaps"),
    ("TPHCM", "allcaps"),
    ("Tân Mai - Biên Hoà", "alphabet"),
    ("", "empty"),
    ("   ", "empty"),
])
def test_not_writable(text, why):
    assert not handwriting.writable(text)
    assert handwriting.refusal(text) == why


def test_digit_is_named_before_case():
    """A run that is both is reported as a digit, and that ordering is load-bearing.

    Widening the alphabet or teaching the model capitals would still leave the
    digit; a report that called this one "allcaps" would understate the only
    blocker that matters. See docs/handwriting-html.md.
    """
    assert handwriting.refusal("SO 15") == "digit"


def test_alphabet_covers_vietnamese():
    """Every letter the corpus prints must have a slot, or the policy is a lie."""
    for word in ("Nguyễn", "Thuỷ", "Đặng", "Vũ", "Hoà", "quỳnh", "ưở"):
        assert handwriting.writable(word), word


# --------------------------------------------------------------- the metrics

def test_extent_reads_the_letters():
    above, below = handwriting.extent("mưa")          # all x-height
    assert (above, below) == (0.0, 0.0)
    assert handwriting.extent("Tiền")[0] == handwriting.ABOVE_TALL   # T
    assert handwriting.extent("mặt")[0] == handwriting.ABOVE_TALL    # t
    assert handwriting.extent("mặt")[1] == handwriting.BELOW_DOT     # dấu nặng
    assert handwriting.extent("ngay")[1] == handwriting.BELOW_TAIL   # g, y
    # A mark above lifts a word less than an ascender does; that difference is
    # the whole reason `compose` can put "Tiền" and "mưa" on one baseline.
    assert 0 < handwriting.extent("mề")[0] < handwriting.ABOVE_TALL


# ----------------------------------------------------------- the markup pass

def _fill(markup, hand=None, **kw):
    return handwriting.fill(markup, hand or FakeHand(), **kw)


def test_inks_only_the_kinds_a_person_fills_in():
    markup = (
        "<style></style>"
        '<span data-kind="store.name">Công ty Hoà Bình</span>'
        '<span data-kind="invoice.field.label">Tên người mua hàng:</span>'
        '<span data-kind="invoice.field" class="v">Lê Thị Kiều Trinh</span>'
    )
    hand = FakeHand()
    filled, report = _fill(markup, hand)
    assert hand.asked == ["Lê Thị Kiều Trinh"]
    # The letterhead and the printed label are furniture: they are on the blank
    # form before anybody picks up a pen.
    assert "Công ty Hoà Bình</span>" in filled
    assert "Tên người mua hàng:</span>" in filled
    assert [item["text"] for item in report["inked"]] == ["Lê Thị Kiều Trinh"]


def test_the_inked_run_keeps_its_kind_its_classes_and_its_text():
    markup = ('<style></style>'
              '<span data-kind="invoice.field" class="v">Chuyển khoản</span>')
    filled, _ = _fill(markup)
    assert 'data-kind="invoice.field"' in filled
    assert 'data-text="Chuyển khoản"' in filled
    assert 'class="v hand"' in filled
    assert "<img" in filled and "data:image/png;base64," in filled


def test_a_refused_run_stays_printed_and_is_counted():
    markup = ('<style></style>'
              '<span data-kind="invoice.field">15/06/2018</span>'
              '<span data-kind="invoice.field">TPHCM</span>')
    filled, report = _fill(markup)
    assert filled.count("<img") == 0
    assert report["printed"] == {"digit": 1, "allcaps": 1}
    assert report["inked"] == []


def test_the_report_names_the_source():
    markup = '<style></style><span data-kind="invoice.field">Tiền mặt</span>'
    assert _fill(markup)[1]["source"] == "fake"


def test_a_worker_refusal_is_recorded_rather_than_raised():
    """The policy and the checkpoint disagreeing is data, not a crashed shard."""
    markup = '<style></style><span data-kind="invoice.field">Chuyển khoản</span>'
    filled, report = _fill(markup, FakeHand(refuse={"Chuyển khoản"}))
    assert filled.count("<img") == 0
    assert report["inked"] == []
    assert any(key.startswith("worker:") for key in report["printed"])


def test_css_is_added_only_when_something_was_inked():
    printed = '<style></style><span data-kind="invoice.field">00751439</span>'
    assert handwriting.CSS not in _fill(printed)[0]
    inked = '<style></style><span data-kind="invoice.field">Tiền mặt</span>'
    assert handwriting.CSS in _fill(inked)[0]


def test_one_writer_and_one_pen_per_page():
    """A form is filled in by one person, so the report names one of each."""
    markup = ('<style></style>'
              '<span data-kind="invoice.field">Tiền mặt</span>'
              '<span data-kind="invoice.field">Chuyển khoản</span>')
    _, report = _fill(markup)
    assert isinstance(report["writer"], int)
    assert report["pen"].startswith("#") and len(report["pen"]) == 7
    assert handwriting.INK_HEIGHT_EM[0] <= report["height_em"] <= handwriting.INK_HEIGHT_EM[1]


def test_the_same_seed_fills_the_same_page():
    markup = '<style></style><span data-kind="invoice.field">Tiền mặt</span>'
    assert _fill(markup, seed=7)[0] == _fill(markup, seed=7)[0]
    assert _fill(markup, seed=7)[1] != _fill(markup, seed=8)[1]


def test_a_run_containing_markup_is_an_error_not_a_silent_miss():
    """`RUN` cannot match a nested element, so the contract is checked, not hoped for."""
    with pytest.raises(RuntimeError, match="contains markup"):
        _fill('<style></style>'
              '<span data-kind="invoice.field"><b>Tiền mặt</b></span>')


# ---------------------------------------------------- the page, and its label

LAYOUTS = ("invoice_vat_form", "authorisation_letter", "invoice_hotel_stay",
           "medical_statement", "invoice_brand", "eatery_ascii")


@pytest.mark.parametrize("layout", LAYOUTS)
def test_inking_does_not_change_what_the_page_says(layout):
    """The one property a dataset depends on, over six families.

    `check_boxes` rebuilds a page's expected fields by building the sheet again
    -- without ink -- and comparing `labelled_runs`. If ink changed that list,
    every hand-filled image would be reported as missing its fields, and if it
    changed it *silently* the label would describe a page that was never drawn.
    """
    recipe, receipt, _rng = rulebase.make_content(seed=7, force={"layout": layout})
    markup = sheets.build(recipe, receipt)
    filled, report = _fill(markup, seed=7)
    assert sheets.labelled_runs(filled) == sheets.labelled_runs(markup)
    # And the report accounts for every field run on the page, once.
    fields = [text for kind, text in sheets.labelled_runs(markup)
              if kind in handwriting.HAND_KINDS]
    assert len(report["inked"]) + sum(report["printed"].values()) == len(fields)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_sheet_family_satisfies_the_run_contract(layout):
    recipe, receipt, _rng = rulebase.make_content(seed=2026, force={"layout": layout})
    handwriting._check_contract(sheets.build(recipe, receipt))


def test_structure_tokens_survive_inking():
    """A cell whose value is ink still has its text in the structure label."""
    recipe, receipt, _rng = rulebase.make_content(
        seed=7, force={"layout": "invoice_hotel_stay"})
    markup = sheets.build(recipe, receipt)
    filled, _ = _fill(markup, seed=7)
    assert sheets.structure_from_markup(filled) == sheets.structure_from_markup(markup)


# ------------------------------------------------------------- the font source

def _font():
    # `FontHand.writable` reads the face's cmap, which is fontTools -- absent in
    # the dependency-free CI job, where this test has nothing to say.
    pytest.importorskip("fontTools")
    hand = handwriting.FontHand()
    if not hand.faces:
        pytest.skip("no handwriting faces in fonts/hand/")
    return hand.open()


def test_every_declared_face_is_on_disk():
    """A face named in FACES and missing is a page set in the system font.

    `FontHand` skips a missing file rather than failing, so the check that the
    shipped list is complete has to be here.
    """
    for _family, filename, _size in handwriting.FACES:
        assert (handwriting.HAND_FONT_DIR / filename).exists(), filename


@pytest.mark.parametrize("text", [
    "15/06/2018", "3.920.000", "LÊ QUANG ĐẠO", "0956100526",
    "Tân Mai - Biên Hoà - Đồng Nai", "01GTKT0/731",
])
def test_the_font_writes_what_the_model_refuses(text):
    """The whole reason this source exists: digits, capitals and punctuation.

    Each of these is a run the checkpoint cannot draw -- and they are 85 % of
    the fields on a form. A face that could not draw them would be adding a
    second hand for nothing.
    """
    hand = _font()
    page = handwriting.Page(7)
    assert not handwriting.writable(text), "the model was supposed to refuse this"
    assert hand.writable(text, page), text


@pytest.mark.parametrize("text", ["Nguyễn Thị Bích Ngọc", "Chuyển khoản",
                                 "Hai trăm ba mươi tám triệu đồng"])
def test_the_font_also_writes_everything_the_model_writes(text):
    """Otherwise switching source would trade one set of blank fields for another."""
    assert handwriting.writable(text)
    assert _font().writable(text, handwriting.Page(7)), text


def test_the_font_source_keeps_the_text_a_text_node():
    """No <img> and no `data-text`: the browser boxes it as it boxes any text.

    That is what lets a long value WRAP and be boxed per line, which an image
    of ink cannot do -- and it is why neither box reader needed changing for
    this source.
    """
    hand = _font()
    page = handwriting.Page(7)
    drawn = hand.span("invoice.field", ' class="v"', "15/06/2018", page)
    assert "<img" not in drawn
    assert "data-text" not in drawn
    assert ">15/06/2018</span>" in drawn
    assert 'class="v hand"' in drawn


def test_the_font_css_embeds_the_face_it_names():
    hand = _font()
    page = handwriting.Page(7)
    family, filename, _size = hand.face_for(page)
    css = hand.css(page)
    assert f"@font-face{{font-family:'{family}'" in css
    assert filename in css
    assert page.pen_hex in css


def test_the_font_source_is_not_relatively_positioned():
    """`position:relative` here silently costs 81 boxes on the WeasyPrint path.

    Relative positioning paints in a later stacking pass, so every inked run
    landed at the END of the PDF's text layer rather than in document order --
    and `match_runs` walks the run list beside that layer. Measured on one VAT
    form: 16 boxes recovered instead of 97, with no error anywhere. The nudge
    off the rule is `vertical-align`, which is an inline shift and creates no
    stacking context.
    """
    hand = _font()
    page = handwriting.Page(7)
    drawn = hand.span("invoice.field", "", "15/06/2018", page)
    assert "vertical-align" in drawn
    assert "position" not in drawn + hand.css(page)


def test_source_by_name():
    assert isinstance(handwriting.source("font"), handwriting.FontHand)
    assert isinstance(handwriting.source("model"), handwriting.Hand)
    assert isinstance(handwriting.source("both"), handwriting.BothHands)
    with pytest.raises(KeyError):
        handwriting.source("crayon")


def test_both_builds_its_own_pair_so_the_renderer_needs_no_special_case():
    """`source("both")` has to be the same one call as `source("model")`."""
    both = handwriting.source("both")
    assert isinstance(both.primary, handwriting.Hand)
    assert isinstance(both.fallback, handwriting.FontHand)


# ------------------------------------------------------------- the two hands

class FakeFont:
    """A source that writes anything with a character in it. Stands in for the
    typeface half, whose real refusal is a missing glyph and needs fontTools."""

    source = "font"
    device = "browser"

    def __init__(self):
        self.asked: list[str] = []

    def open(self):
        return self

    def close(self):
        pass

    def writable(self, text, page):
        return bool(text.strip())

    def refusal(self, text, page):
        return "empty"

    def span(self, kind, classes, text, page):
        self.asked.append(text)
        return f'<span data-kind="{kind}" class="hand hand-font">{text}</span>'

    def css(self, page):
        return "/*font*/"


# One run the checkpoint can write, three it cannot: a date, an amount and a
# name in capitals. That ratio is the point of the class -- on the measured
# `notebook_ledger` pages the model reached 8 % of the runs.
MIXED = ('<style></style>'
         '<span data-kind="menu.name">Nước mắm Nam Ngư</span>'
         '<span data-kind="menu.amount">27.000</span>'
         '<span data-kind="meta.value">15/06/2018</span>'
         '<span data-kind="store.name">TẠP HOÁ BÌNH MINH</span>')


def _both(refuse=None):
    return handwriting.BothHands(FakeHand(refuse=refuse), FakeFont())


def test_both_leaves_no_run_in_type():
    """The whole reason the class exists: a ledger written 8 % by the model and
    92 % in type is not a ledger."""
    hand = _both()
    filled, report = handwriting.fill(MIXED, hand, kinds=handwriting.ALL_KINDS)
    assert report["printed"] == {}
    assert len(report["inked"]) == 4
    assert "<style>" in filled  # the runs were rewritten, not the page dropped


def test_both_records_which_half_of_the_page_came_from_where():
    """The two hands do not match. That is a cost, and a cost in the label is
    a cost a reader can find; one nowhere is a cost that gets forgotten."""
    hand = _both()
    # Keyed on each source's own name -- here the double's, `fake`.
    assert (hand.primary.source, hand.fallback.source) == ("fake", "font")
    _, report = handwriting.fill(MIXED, hand, kinds=handwriting.ALL_KINDS)
    assert report["by_source"] == {"fake": 1, "font": 3}
    assert hand.primary.asked == ["Nước mắm Nam Ngư"]
    assert hand.fallback.asked == ["27.000", "15/06/2018", "TẠP HOÁ BÌNH MINH"]


def test_a_single_source_does_not_claim_a_split():
    """Two numbers for one fact is two numbers that can disagree."""
    _, report = _fill(MIXED, kinds=handwriting.ALL_KINDS)
    assert "by_source" not in report


def test_both_keeps_the_run_when_the_model_refuses_one_its_policy_allowed():
    """The disagreement `fill` records as `worker:` for a single source. With a
    fallback there is no reason to lose the run over it -- it is counted as a
    fallback like any other."""
    hand = _both(refuse={"Nước mắm Nam Ngư"})
    _, report = handwriting.fill(MIXED, hand, kinds=handwriting.ALL_KINDS)
    assert report["printed"] == {}
    assert report["by_source"] == {"font": 4}
    assert len(report["inked"]) == 4


def test_both_refuses_only_what_both_refuse():
    page = handwriting.Page(7)
    hand = _both()
    assert hand.writable("15/06/2018", page)          # model no, font yes
    assert hand.writable("Chuyển khoản", page)        # both yes
    assert not hand.writable("   ", page)             # neither
    assert hand.refusal("   ", page) == "empty"


def test_the_font_half_is_scoped_so_it_cannot_resize_the_model_ink():
    """A real defect, not a style preference.

    `FontHand.css` sets `font-size` on the runs it matches, and `ink_span`
    states the model's image width in `em`. One rule reaching both would scale
    the model's ink by the typeface's size factor -- so the two sources must
    not share a selector.
    """
    hand = handwriting.FontHand(mark=handwriting.BothHands.FONT_MARK)
    if not hand.faces:
        pytest.skip("no handwriting faces in fonts/hand/")
    css = hand.open().css(handwriting.Page(7))
    assert "#sheet span.hand-font{" in css
    assert "#sheet span.hand{" not in css
    # and the run still carries `hand`, which is what CSS keys `white-space`
    # and the `<img>` rules off for both sources.
    drawn = hand.span("menu.amount", "", "27.000", handwriting.Page(7))
    assert 'class="hand hand-font"' in drawn


def test_line_extent_is_the_maximum_over_the_words():
    """The same maxima `compose` takes, available before any ink exists."""
    assert handwriting.line_extent("kem") == (handwriting.ABOVE_TALL, 0.0)
    assert handwriting.line_extent("gao") == (0.0, handwriting.BELOW_TAIL)
    assert handwriting.line_extent("kem gao") == (handwriting.ABOVE_TALL,
                                                  handwriting.BELOW_TAIL)
    assert handwriting.line_extent("") == (0.0, 0.0)


def test_the_two_hands_are_one_size_even_though_they_are_two_styles():
    """Measured, not asserted by eye, and it was wrong before this.

    `INK_HEIGHT_EM` and `FontHand`'s per-face factor were each calibrated
    against a printed field on their own, so nothing made them agree: on a
    rendered `notebook_ledger` page the model's x-height came out about 1.5x
    the typeface's and read as a second, larger hand. The matched height puts
    the model's x-height on the face's, so the ratio here is 1.
    """
    font = handwriting.FontHand(mark=handwriting.BothHands.FONT_MARK)
    if not font.faces:
        pytest.skip("no handwriting faces in fonts/hand/")
    pytest.importorskip("fontTools")
    both = handwriting.BothHands(FakeHand(), font.open())
    page = handwriting.Page(7)

    for text in ("Nước mắm Nam Ngư", "kem", "gao", "Chuyển khoản"):
        above, below = handwriting.line_extent(text)
        tile = both._matched_height(text, page)
        # A tile covers `above + 1 + below` x-heights, so dividing gives the
        # model's x-height in em -- which must be the face's.
        model_x = tile / (above + handwriting.X_HEIGHT + below)
        assert model_x == pytest.approx(font.x_height_em(page), rel=1e-9), text


def test_a_fallback_that_cannot_state_an_x_height_leaves_the_model_alone():
    """`None`, not a guessed number: a guess would mis-size one half of every
    page and look exactly like a calibration nobody wrote down."""
    assert _both()._matched_height("Chuyển khoản", handwriting.Page(7)) is None


def test_model_of_reaches_through_the_pair():
    """`--signature model` borrows the worker rather than loading a second
    checkpoint: 11 s and 294 MB, twice, for one model."""
    both = handwriting.BothHands(handwriting.Hand(), FakeFont())
    assert handwriting.model_of(both) is both.primary
    assert handwriting.model_of(handwriting.Hand()).source == "model"
    assert handwriting.model_of(handwriting.FontHand()) is None
    assert handwriting.model_of(_both()) is None      # the double is not one
    assert handwriting.model_of(None) is None


# -------------------------------------------------- which runs a pen reaches

def test_the_sentinel_is_the_same_string_on_both_sides():
    """`handwriting` and `sheets` must not import each other, so the one value
    they share is restated -- and pinned here rather than hoped for."""
    assert handwriting.ALL_KINDS == sheets.EVERY_RUN


def test_all_kinds_writes_runs_a_printed_form_would_leave_alone():
    hand = FakeHand()
    markup = ('<style></style>'
              '<span data-kind="store.name">Tạp hoá Bình Minh</span>'
              '<span data-kind="menu.name">Nước mắm</span>')
    _fill(markup, hand, kinds=handwriting.ALL_KINDS)
    assert hand.asked == ["Tạp hoá Bình Minh", "Nước mắm"]
    # ... and the default still leaves them printed.
    other = FakeHand()
    _fill(markup, other)
    assert other.asked == []


def test_only_the_notebook_is_written_end_to_end():
    """Every other family is a printed form: a letterhead and a column title
    were printed before anybody picked up a pen, and inking them would be
    claiming a press run that did not happen."""
    default = handwriting.HAND_KINDS
    written = [layout for layout in sheets.names()
               if sheets.hand_kinds(layout, default) == sheets.EVERY_RUN]
    assert written == ["notebook_ledger"]
    for layout in sheets.names():
        if layout not in written:
            assert sheets.hand_kinds(layout, default) is default


# ------------------------------------------------------------- the pixel half

def test_ink_png_makes_the_paper_transparent():
    np = pytest.importorskip("numpy")
    image = pytest.importorskip("PIL.Image")
    import io

    tile = image.fromarray(np.array([[255, 255], [0, 128]], dtype="uint8"), mode="L")
    rgba = np.asarray(image.open(io.BytesIO(handwriting.ink_png(tile, (10, 20, 30)))))
    # White paper -> fully transparent, black ink -> fully opaque, and the
    # colour is the pen's everywhere. Compositing this over a dotted rule must
    # not erase the rule, which pasting the grey tile would.
    assert rgba[0, 0, 3] == 0
    assert rgba[1, 0, 3] == 255
    assert list(rgba[1, 0, :3]) == [10, 20, 30]


def test_ink_gamma_darkens_without_inventing():
    """Below 1 it deepens partial coverage; the two endpoints must not move.

    Paper unwritten-on has to stay fully transparent and a saturated stroke
    fully opaque whatever the gamma, or the field's dotted rule is either
    erased or shows through the ink.
    """
    np = pytest.importorskip("numpy")
    image = pytest.importorskip("PIL.Image")
    import io

    assert 0.5 < handwriting.INK_GAMMA <= 1.0
    tile = image.fromarray(np.array([[255, 128, 0]], dtype="uint8"), mode="L")
    rgba = np.asarray(image.open(io.BytesIO(handwriting.ink_png(tile, (0, 0, 0)))))
    assert rgba[0, 0, 3] == 0, "unwritten paper must stay transparent"
    assert rgba[0, 2, 3] == 255, "a saturated stroke must stay opaque"
    assert rgba[0, 1, 3] > 127, "a half-covered pixel is darker than half paint"


def test_compose_puts_the_words_on_one_baseline():
    np = pytest.importorskip("numpy")
    image = pytest.importorskip("PIL.Image")

    def tile(width):
        return image.fromarray(np.zeros((32, width), dtype="uint8"), mode="L")

    # "Tiền" reaches high and stops at the baseline; "mưa" is all x-height.
    # After composing, the tall word must start at the top and the short one
    # must be pushed down by its missing ascender -- that offset is the fix.
    line = handwriting.compose([("Tiền", tile(64)), ("mưa", tile(48))])
    # The band the two words share: "Tiền" reaches an ascender above the
    # x-height, neither drops below it.
    # "mưa" is the tightest tile -- it fills its whole band -- so it is what
    # sets the scale, and no tile is downscaled.
    unit = 32 / handwriting.X_HEIGHT
    assert line.height == round(
        (handwriting.ABOVE_TALL + handwriting.X_HEIGHT) * unit)

    ink = np.asarray(line) < 128
    columns = np.where(ink.any(axis=0))[0]
    assert columns.size, "the composed line has no ink at all"
    # Two words with a gap between them, and the second lower than the first.
    tall_rows = np.where(ink[:, columns[0]])[0]
    short_rows = np.where(ink[:, columns[-1]])[0]
    assert short_rows[0] > tall_rows[0]
    assert short_rows[-1] == tall_rows[-1]      # one baseline


def test_compose_never_downscales_a_tile():
    """A downscale here is paid for twice: the browser scales the ink back up.

    The first version sized the line so a word using the FULL band kept the
    generator's 32 px -- and most words do not use the full band, so most lines
    were shrunk and then enlarged again. Measured on one field, the mean stroke
    value went from 91 in the generator's output to 133 on the page.
    """
    np = pytest.importorskip("numpy")
    image = pytest.importorskip("PIL.Image")

    def tile(width):
        return image.fromarray(np.zeros((32, width), dtype="uint8"), mode="L")

    for words in (["Chu", "Văn", "Lâm"],          # nothing below the baseline
                  ["mưa"],                        # nothing above it either
                  ["Ngô", "Thị", "Hồng", "Nhung"]):  # a mix
        pairs = [(word, tile(16 * len(word))) for word in words]
        line = handwriting.compose(pairs)
        for word, source in pairs:
            above, below = handwriting.extent(word)
            band = above + handwriting.X_HEIGHT + below
            drawn = line.height * band / (
                max(handwriting.extent(w)[0] for w, _ in pairs)
                + handwriting.X_HEIGHT
                + max(handwriting.extent(w)[1] for w, _ in pairs))
            assert drawn >= source.height - 1, (words, word, drawn, source.height)
