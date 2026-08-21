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
    with pytest.raises(KeyError):
        handwriting.source("crayon")


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


def test_compose_puts_the_words_on_one_baseline():
    np = pytest.importorskip("numpy")
    image = pytest.importorskip("PIL.Image")

    def tile(width):
        return image.fromarray(np.zeros((32, width), dtype="uint8"), mode="L")

    # "Tiền" reaches high and stops at the baseline; "mưa" is all x-height.
    # After composing, the tall word must start at the top and the short one
    # must be pushed down by its missing ascender -- that offset is the fix.
    line = handwriting.compose([("Tiền", tile(64)), ("mưa", tile(48))])
    unit = 32 / (handwriting.ABOVE_TALL + handwriting.X_HEIGHT
                 + handwriting.BELOW_TAIL)
    assert line.height == round((handwriting.ABOVE_TALL
                                 + handwriting.X_HEIGHT) * unit)
    ink = np.asarray(line) < 128
    columns = np.where(ink.any(axis=0))[0]
    assert columns.size, "the composed line has no ink at all"
    # Two words with a gap between them, and the second lower than the first.
    tall_rows = np.where(ink[:, columns[0]])[0]
    short_rows = np.where(ink[:, columns[-1]])[0]
    assert short_rows[0] > tall_rows[0]
    assert short_rows[-1] == tall_rows[-1]      # one baseline
