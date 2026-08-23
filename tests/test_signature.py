"""The signature engine: the geometry, the policy, and the seam into a sheet.

Split the way `signature.py` is split, and for the same reason. The warps are
arithmetic over tuples of floats and are tested as arithmetic -- no font, no
browser, no dependency past the standard library, so they run in the CI job
that installs pytest and PyYAML and nothing else. Only the tests that need a
`.ttf` read one, and they say so with an `importorskip`.

The property that matters most is the last group's. A signature is ink with no
box and no text: it goes on the page and it must stay out of the label. If
signing a sheet ever changed `labelled_runs`, every signed page would be
reported as missing its fields -- and if it changed them quietly, the label
would describe a page that was never drawn. That is the same failure
`test_handwriting.py` guards at its own seam, and it is worth guarding twice.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "generators" / "html"))

import handwriting  # noqa: E402
import sheets  # noqa: E402
import signature  # noqa: E402

import rulebase  # noqa: E402

SQUARE = [signature.polyline([(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)])]


def _fonts() -> None:
    """Skip a test that needs a real outline, rather than fail it."""
    pytest.importorskip("fontTools", reason="outline tests need fontTools")
    if not (signature.HAND_FONT_DIR / signature.FACES[0]).exists():
        pytest.skip("no handwriting faces in fonts/hand/")


# ---------------------------------------------------------------- geometry


def test_a_line_segment_is_an_exact_cubic():
    """The colinear-controls trick, which every straight stroke here relies on.

    If it were only approximate, `ribbon` -- which is a polygon in cubic
    clothing -- would bulge at every sample point.
    """
    c1, c2 = signature.line_controls((0.0, 0.0), (3.0, 6.0))
    seg = ((0.0, 0.0), c1, c2, (3.0, 6.0))
    for t in (0.0, 0.25, 0.5, 0.75, 1.0):
        x, y = signature.at(seg, t)
        assert x == pytest.approx(3.0 * t)
        assert y == pytest.approx(6.0 * t)


def test_a_contour_holds_three_n_plus_one_points():
    """The invariant the whole representation rests on."""
    for contour in SQUARE:
        assert len(contour) % 3 == 1
        assert contour[0] == contour[-1], "a contour closes on its own start"


def test_tangent_is_a_unit_vector_along_the_curve():
    c1, c2 = signature.line_controls((0.0, 0.0), (1.0, 1.0))
    tx, ty = signature.tangent(((0.0, 0.0), c1, c2, (1.0, 1.0)), 0.5)
    assert math.hypot(tx, ty) == pytest.approx(1.0)
    assert tx == pytest.approx(ty)


def test_tangent_does_not_divide_by_zero_on_a_degenerate_segment():
    """A ribbon spine can collapse when two letters end up on top of each other."""
    point = (2.0, 2.0)
    assert signature.tangent((point, point, point, point), 0.5) == (1.0, 0.0)


def test_affine_shears_about_the_baseline():
    """Slant is a shear, and it must leave the baseline where it was.

    A signature sheared about the middle of its own box would slide sideways
    off the line it was placed on -- and the placement is done in `sign()`
    before the shear, so the pivot has to be y = 0.
    """
    fn = signature.affine(shear=0.5)
    assert fn((1.0, 0.0)) == pytest.approx((1.0, 0.0))
    assert fn((1.0, 2.0)) == pytest.approx((2.0, 2.0))


def test_bounds_of_a_known_path():
    assert signature.bounds(SQUARE) == pytest.approx((0.0, 0.0, 1.0, 1.0))


def test_bounds_of_nothing_is_a_point():
    assert signature.bounds([]) == (0.0, 0.0, 0.0, 0.0)


@pytest.mark.parametrize("warp", [
    lambda x0, x1: signature.bow(x0, x1, 0.0, 0.0),
    lambda x0, x1: signature.fade(x0, x1, 0.0),
    lambda x0, x1: signature.swell(x0, x1, 0.0),
])
def test_every_warp_is_the_identity_at_zero(warp):
    """A signer who writes level and even should get the letters untouched.

    Not pedantry: `Style` draws a rise of 0.0 often enough, and a warp that
    moved the ink by a rounding error at its own identity would put a wobble
    into every mark on every page and be very hard to find afterwards.
    """
    fn = warp(0.0, 4.0)
    for point in [(0.0, 0.0), (1.5, 2.0), (4.0, -1.0)]:
        assert fn(point) == pytest.approx(point)


def test_bow_lifts_the_right_hand_end_and_leaves_the_left():
    fn = signature.bow(0.0, 2.0, 0.5)
    assert fn((0.0, 0.0))[1] == pytest.approx(0.0)
    assert fn((1.0, 0.0))[1] == pytest.approx(0.25)
    assert fn((2.0, 0.0))[1] == pytest.approx(0.5)


def test_fade_squeezes_the_end_and_never_flips_it():
    """`1 - k` with k < 1: the letters get shorter, never upside down."""
    fn = signature.fade(0.0, 1.0, 0.5)
    assert fn((0.0, 2.0))[1] == pytest.approx(2.0)
    assert fn((1.0, 2.0))[1] == pytest.approx(1.0)
    assert fn((1.0, -2.0))[1] == pytest.approx(-1.0)


@pytest.mark.parametrize("k", [-0.22, 0.0, 0.22])
def test_swell_keeps_the_letters_in_order(k):
    """The one thing a horizontal warp must not do is reverse the writing."""
    fn = signature.swell(0.0, 1.0, k)
    xs = [fn((index / 40.0, 0.0))[0] for index in range(41)]
    assert xs == sorted(xs)


def test_subdividing_does_not_move_the_curve():
    """The price paid for warping control points, and the proof it is honest.

    Stated as a point-set property rather than by walking `t` in step, because
    the split is adaptive: a segment is halved until its control hull is short
    enough, so segment *i* of the result does not cover a fixed slice of the
    original's parameter range. What must hold is that the ink is in the same
    place, and that is what is checked.
    """
    curve = [[(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0)]]
    fine = signature.subdivided(curve, step=0.05)
    assert len(fine[0]) > len(curve[0])
    assert len(fine[0]) % 3 == 1
    assert fine[0][0] == pytest.approx(curve[0][0])
    assert fine[0][-1] == pytest.approx(curve[0][-1])

    # 20 001 samples over a curve about 2 long: the nearest sample to any point
    # actually on the curve is within half a spacing, ~5e-5. The tolerance is
    # that, not the arithmetic's -- de Casteljau itself is exact to a float.
    dense = [signature.at(tuple(curve[0]), index / 20000.0) for index in range(20001)]
    for start in range(0, len(fine[0]) - 1, 3):
        seg = tuple(fine[0][start:start + 4])
        for t in (0.0, 0.5, 1.0):
            x, y = signature.at(seg, t)
            assert min(math.hypot(x - px, y - py) for px, py in dense) < 1e-4


def test_subdividing_terminates_on_a_zero_length_segment():
    point = (1.0, 1.0)
    assert signature.subdivided([[point, point, point, point]], step=0.01)


def test_ribbon_is_as_wide_as_it_was_asked_to_be():
    """A stroke's width is the one thing about it a caller can check."""
    spine = ((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0))
    contour = signature.ribbon(spine, 0.2, 0.2, samples=8)
    _x0, y0, _x1, y1 = signature.bounds([contour])
    assert y1 - y0 == pytest.approx(0.2, abs=1e-9)


def test_ribbon_tapers_from_one_end_to_the_other():
    """What makes a terminal sweep a sweep rather than a rule."""
    spine = ((0.0, 0.0), (1.0, 0.0), (2.0, 0.0), (3.0, 0.0))
    contour = signature.ribbon(spine, 0.30, 0.02, bulge=0.0, samples=24)
    at_start = [p[1] for p in contour if p[0] < 0.05]
    at_end = [p[1] for p in contour if p[0] > 2.95]
    assert max(at_start) - min(at_start) > max(at_end) - min(at_end)


def test_d_emits_one_curve_per_segment_and_closes():
    text = signature.d(SQUARE)
    assert text.startswith("M") and text.endswith("Z")
    assert text.count("C") == (len(SQUARE[0]) - 1) // 3


def test_d_skips_a_contour_too_short_to_draw():
    assert signature.d([[(0.0, 0.0)]]) == ""


# ------------------------------------------------------------------- names


def test_a_vietnamese_name_puts_the_given_name_last():
    """The whole reason `parts_of` exists rather than a `split()` at the call
    site: `tên` is the last word, not the first."""
    assert signature.parts_of("Nguyễn Thị Bích Ngọc")[-1] == "Ngọc"
    assert signature.parts_of("  Lê   Quang  Đạo ") == ["Lê", "Quang", "Đạo"]
    assert signature.parts_of("   ") == []


def test_dropping_the_marks_keeps_the_consonants():
    assert signature.undiacritic("Nguyễn Thị Bích Ngọc") == "Nguyen Thi Bich Ngoc"
    assert signature.undiacritic("Đặng Đình Đức") == "Dang Dinh Duc"


@pytest.mark.parametrize("legibility,drawn", [
    ("full", "Lê Quang Đạo"),
    ("given", "Đạo"),
    ("initials", "LQĐạo"),
    ("monogram", "LQĐ"),
])
def test_each_legibility_draws_what_it_says(legibility, drawn):
    style = signature.Style(1)
    style.legibility, style.marks = legibility, True
    assert signature.letters_of("Lê Quang Đạo", style) == drawn


def test_a_hand_that_drops_its_marks_drops_them_everywhere():
    style = signature.Style(1)
    style.legibility, style.marks = "full", False
    assert signature.letters_of("Lê Quang Đạo", style) == "Le Quang Dao"


# ------------------------------------------------- letters that stop being letters
#
# The correction this group exists for. The first engine squeezed and faded the
# body and left it a body: marks came out reading "Nguyễn Thị Bích Ngọc" in a
# slightly slanted hand, and a signature you can read like that is not what
# comes back on a form. These guard the fix -- and the last one guards the
# symptom directly, because a range that drifts back toward legible would pass
# every other test in this file.


def test_the_first_letters_survive_and_the_rest_do_not():
    style = signature.Style(1)
    style.scrawl, style.survives = True, 2
    assert signature.head_and_tail("Ngoc", style) == ("Ng", "oc")


def test_a_capital_never_degenerates():
    """Initials are the part of a signature meant to be read. A monogram whose
    letters had collapsed would be a squiggle with nothing left to identify."""
    style = signature.Style(1)
    style.scrawl, style.survives = True, 1
    assert signature.head_and_tail("LQD", style) == ("LQD", "")
    assert signature.head_and_tail("LQDao", style) == ("LQD", "ao")


def test_the_hand_does_not_pick_the_letters_back_up():
    """Everything past the first degenerated character goes, spaces included --
    a hand that has let go does not re-form the next word."""
    style = signature.Style(1)
    style.scrawl, style.survives = True, 1
    head, tail = signature.head_and_tail("Nguyen Thi Bich Ngoc", style)
    assert head == "N"
    assert tail == "guyen Thi Bich Ngoc"


def test_a_signer_who_does_not_scrawl_keeps_every_letter():
    style = signature.Style(1)
    style.scrawl = False
    assert signature.head_and_tail("Ngoc", style) == ("Ngoc", "")


def test_a_ribbon_follows_a_spine_of_more_than_one_segment():
    """What the scrawl needed: the wave is many segments, not one curve."""
    spine = signature.polyline([(0.0, 0.0), (1.0, 1.0), (2.0, 0.0), (3.0, 1.0)])
    contour = signature.ribbon(spine, 0.1, 0.1, samples=6)
    x0, _y0, x1, _y1 = signature.bounds([contour])
    assert x1 - x0 == pytest.approx(3.0, abs=0.2)
    assert len(contour) % 3 == 1


def test_the_wave_keeps_the_direction_of_the_letters_it_replaced():
    """The idea the scrawl is built on: the movement survives the form.

    A degenerated `g` still dives under the baseline and a degenerated `l`
    still throws a loop over it, so two different tails give two different
    waves rather than the same squiggle twice.

    Measured on `_scrawl` rather than on a whole mark, which is not fussiness:
    the enlarged initial is 1.35-2.4 x-heights tall and sets the top of the box
    whatever the wave does, so a mark-level assertion about height compares two
    capitals and passes or fails for nothing.
    """
    _fonts()
    with signature.Signer(3) as signer:
        below = signature.bounds(signer._scrawl("gggg", (0.0, 0.0)))
        above = signature.bounds(signer._scrawl("llll", (0.0, 0.0)))
    assert below[1] < above[1], "descenders should hang lower than loops"
    assert above[3] > below[3], "ascenders should reach higher"


def test_a_long_name_does_not_get_one_hump_per_letter():
    """A hand that has given up on nine letters puts down five or six humps
    and lifts off; the wave is shorter than the name it stands for."""
    _fonts()
    with signature.Signer(3) as signer:
        signer.style.scrawl, signer.style.survives = True, 1
        short = signer.sign("Nguyen")
        long = signer.sign("Nguyen Thi Bich Ngoc Mai Lan")
    assert long.width < short.width * 2.2


def test_most_signatures_are_not_readable():
    """The property that was reported missing, stated as a count.

    Three hundred seeds over five names, because eighty was inside its own
    noise -- the first version of this asserted a bound it then failed by one
    mark. Measured on the engine as it stands: 222 degenerate, 39 are short
    all-capital monograms, 39 keep every letter. The bounds below are those
    numbers with room, so ordinary re-weighting passes and a drift back toward
    legible does not.

    Monograms are counted separately and deliberately not held against the
    engine: three capitals are *meant* to be read, and a signature that is
    three initials is a real signature rather than a failure to degenerate.
    """
    _fonts()
    ink = signature.Ink(signature.FACES[0]).open()
    try:
        scrawled = readable = 0
        for seed in range(300):
            signer = signature.Signer(seed, ink=ink)
            mark = signer.sign(NAMES[seed % len(NAMES)])
            scrawled += bool(mark.tail)
            readable += not mark.tail and len(mark.head) > 3
    finally:
        ink.close()
    assert scrawled >= 190, f"only {scrawled}/300 signatures degenerated"
    assert readable <= 60, f"{readable}/300 signatures are still fully readable"


# ------------------------------------------------------------------- style


def test_one_seed_is_one_signer():
    assert signature.Style(11).report() == signature.Style(11).report()


def test_different_seeds_are_different_signers():
    """Not a distribution test -- just that the seed reaches the parameters."""
    reports = [signature.Style(seed).report() for seed in range(40)]
    assert len({tuple(sorted(r.items())) for r in reports}) > 20


def test_a_style_settles_everything_in_its_constructor():
    """The bug this guards: a draw at sign time made a mark depend on how many
    names the signer had already signed, so a page was not reproducible from
    `(seed, name)` alone. The property is deliberately loud."""
    with pytest.raises(AttributeError, match="__init__"):
        signature.Style(3).rng


def test_the_slant_stays_inside_the_surveyed_band():
    for seed in range(200):
        degrees = signature.Style(seed).report()["slant_deg"]
        assert math.degrees(math.atan(signature.SLANT[0])) - 0.05 <= degrees
        assert degrees <= math.degrees(math.atan(signature.SLANT[1])) + 0.05


def test_every_weighted_table_can_be_drawn_from():
    for table in (signature.LEGIBILITY, signature.BASELINE, signature.PARAPH):
        assert table and all(weight > 0 for _name, weight in table)


# ------------------------------------------------------- letters into a mark


def test_every_declared_face_is_on_disk():
    """A face named in FACES and missing is a page signed in nothing at all.

    `Ink.open` raises rather than falling back, so the check that the shipped
    list is complete has to live here.
    """
    for filename in signature.FACES:
        assert (signature.HAND_FONT_DIR / filename).exists(), filename


def test_a_missing_face_is_an_error_with_the_path_in_it():
    with pytest.raises(FileNotFoundError, match="fonts/README.md"):
        signature.Ink("NotAFace.ttf").open()


def test_an_outline_arrives_one_x_height_tall():
    """The unit the whole engine reckons in, read off the face rather than
    trusted to OS/2 -- a wrong unit here would look like a style choice."""
    _fonts()
    with signature.Ink() as ink:
        _x0, y0, _x1, y1 = signature.bounds(ink.outline("x")[0])
        assert y1 - y0 == pytest.approx(1.0, abs=0.02)
        assert y0 == pytest.approx(0.0, abs=0.02), "the baseline is y = 0"


def test_a_tall_letter_reaches_above_the_x_height():
    _fonts()
    with signature.Ink() as ink:
        assert signature.bounds(ink.outline("l")[0])[3] > 1.2


def test_the_stem_is_a_plausible_stroke_width():
    _fonts()
    with signature.Ink() as ink:
        assert 0.02 < ink.stem() < 0.5


def test_a_composite_glyph_keeps_its_marks():
    """`ề` is a composite, and the glyph set has to decompose it -- otherwise
    the accent is dropped and the mark says a different name."""
    _fonts()
    with signature.Ink() as ink:
        plain = signature.bounds(ink.outline("e")[0])
        marked = signature.bounds(ink.outline("ề")[0])
        assert marked[3] > plain[3] + 0.2


def test_a_glyph_the_face_does_not_have_is_reported_not_guessed():
    _fonts()
    with signature.Ink() as ink:
        assert ink.has("a")
        assert not ink.has("中")
        assert ink.outline("中") == ([], 0.0)


# -------------------------------------------------------------------- marks

NAMES = ("Nguyễn Thị Bích Ngọc", "Lê Quang Đạo", "Trần Văn Hùng",
         "Phạm Minh Tuấn", "Đặng Đình Đức")


def test_a_mark_is_a_pure_function_of_seed_and_name():
    """One signer, two names, then back to the first -- the same mark.

    A dataset is only reproducible if this holds: `render.py` signs several
    blocks from one page seed, and the second block must not depend on what the
    first one was called.
    """
    _fonts()
    with signature.Signer(5) as signer:
        first = signature.d(signer.sign(NAMES[0]).path)
        signer.sign(NAMES[1])
        assert signature.d(signer.sign(NAMES[0]).path) == first
    with signature.Signer(5) as fresh:
        assert signature.d(fresh.sign(NAMES[0]).path) == first


@pytest.mark.parametrize("name", NAMES)
def test_every_name_in_the_corpus_can_be_signed(name):
    _fonts()
    for seed in range(6):
        with signature.Signer(seed) as signer:
            mark = signer.sign(name)
        assert mark.width > 0 and mark.height > 0
        assert mark.path


def test_signing_nothing_is_an_error_rather_than_an_empty_mark():
    _fonts()
    with signature.Signer(1) as signer:
        with pytest.raises(ValueError, match="nothing to sign"):
            signer.sign("   ")


def test_a_mark_is_wider_than_it_is_tall():
    """Not the capture-box check -- just that stretching, terminal and paraph
    together pull the mark sideways, which is the shape a signature has."""
    _fonts()
    wide = 0
    for seed in range(30):
        with signature.Signer(seed) as signer:
            wide += signer.sign("Nguyễn Thị Bích Ngọc").aspect > 1.0
    assert wide >= 27


def test_the_report_says_what_was_drawn_and_what_it_was_drawn_from():
    _fonts()
    with signature.Signer(2) as signer:
        report = signer.sign("Lê Quang Đạo").report()
    assert report["name"] == "Lê Quang Đạo"
    assert report["drawn"] in {"Lê Quang Đạo", "Le Quang Dao", "Đạo", "Dao",
                               "LQĐạo", "LQDao", "LQĐ", "LQD"}
    assert report["face"] in signature.FACES
    assert isinstance(report["in_capture_box"], bool)


def test_the_frame_holds_the_ink():
    """`view` is the only place the y flip and the margin happen, after a bug
    in which `mark_span` re-derived the box without the margin and put every
    signature a margin's width outside its own frame."""
    _fonts()
    with signature.Signer(4) as signer:
        mark = signer.sign("Trần Văn Hùng")
    body, width, height = signature.view(mark)
    numbers = [float(n) for n in re.findall(r"-?\d+\.?\d*", body)]
    xs, ys = numbers[0::2], numbers[1::2]
    assert min(xs) >= -1e-6 and max(xs) <= width + 1e-6
    assert min(ys) >= -1e-6 and max(ys) <= height + 1e-6


def test_svg_is_one_path_in_the_pen_colour():
    _fonts()
    with signature.Signer(4) as signer:
        body = signature.svg(signer.sign("Lê Quang Đạo"), colour="#123456")
    assert body.count("<path") == 1
    assert 'fill="#123456"' in body
    assert 'fill-rule="nonzero"' in body


def test_a_contact_sheet_draws_every_seed_it_was_given():
    _fonts()
    body = signature.sheet(list(NAMES), [1, 2, 3, 4], columns=2)
    assert body.count("<path") == 4
    assert body.count("<text") == 4


# ----------------------------------------------------- the seam into a sheet

BLOCK = (
    '<style>.x{}</style><div class="signs">'
    '<div class="sign"><span data-kind="sign.title" class="t">Lễ tân</span>'
    '<div class="n"><span data-kind="sign.note">(Ký, ghi rõ họ tên)</span></div>'
    '<div class="who"><span data-kind="sign.name">Lê Quang Đạo</span></div></div>'
    '<div class="sign"><div class="who"></div></div></div>')


def test_the_pattern_matches_a_named_block_and_a_blank_one():
    """Both shapes `base.signature_block` emits. The blank one is the majority:
    only a document with `signature_names` prints a name at all."""
    found = signature.WHO.findall(BLOCK)
    assert len(found) == 2
    assert found[0][1] == "Lê Quang Đạo"
    assert found[1] == ("", "")


def test_a_blank_block_is_left_alone_and_counted_when_nobody_is_named():
    """No font is opened on this path, and the test proves it by not needing one.

    The refusal happens before a `Signer` is built, so the markup here is the
    blank block alone -- put a named block in front of it and the font would be
    opened for that one first, and this would stop being a test about the
    refusal. The count is the point: a page that wanted signatures and could
    not draw them says so in its own record rather than coming back quietly
    unsigned.
    """
    blank = '<style></style><div class="sign"><div class="who"></div></div>'
    filled, report = signature.fill(blank, seed=3, names=())
    assert report["skipped"] == {"unnamed": 1}
    assert report["marks"] == []
    assert 'class="sig"' not in filled


def test_a_blank_block_is_signed_when_the_caller_says_who():
    _fonts()
    _filled, report = signature.fill(BLOCK, seed=3, names=("Vũ Thị Lan",))
    assert report["skipped"] == {}
    assert len(report["marks"]) == 2
    assert [entry["printed"] for entry in report["marks"]] == [True, False]


def test_two_blocks_on_one_page_are_two_people():
    """The seller and the buyer do not share a hand."""
    _fonts()
    _filled, report = signature.fill(BLOCK, seed=3, names=("Vũ Thị Lan",))
    first, second = report["marks"]
    assert (first["slant_deg"], first["baseline"], first["paraph"]) != (
        second["slant_deg"], second["baseline"], second["paraph"])


def test_the_mark_is_never_a_labelled_run():
    """The property the whole design turns on: on the page, out of the label."""
    _fonts()
    filled, _report = signature.fill(BLOCK, seed=3, names=("Vũ Thị Lan",))
    marks = re.findall(r'<span class="sig"[^>]*>', filled)
    assert marks and all("data-kind" not in mark for mark in marks)


def test_css_is_added_only_when_something_was_signed():
    _fonts()
    signed, _ = signature.fill(BLOCK, seed=3, names=("Vũ Thị Lan",))
    assert "span.sig{display:block" in signed
    blank, report = signature.fill('<style></style><div class="who"></div>', seed=3)
    assert not report["marks"]
    assert "span.sig" not in blank


def test_a_signed_page_still_satisfies_the_handwriting_run_contract():
    """The two passes share a page, so the second must survive the first."""
    _fonts()
    filled, _report = signature.fill(BLOCK, seed=3, names=("Vũ Thị Lan",))
    handwriting._check_contract(filled)


LAYOUTS = ("invoice_vat_form", "authorisation_letter", "invoice_hotel_stay",
           "medical_statement", "invoice_brand", "eatery_ascii")


@pytest.mark.parametrize("layout", LAYOUTS)
def test_signing_does_not_change_what_the_page_says(layout):
    """The one property a dataset depends on, over six families.

    `check_boxes` rebuilds a page's expected fields by building the sheet again
    -- unsigned -- and comparing `labelled_runs`. Ink that changed that list
    would report every signed image as missing its fields; ink that changed it
    *silently* would give the set a label describing a page nobody drew.
    """
    _fonts()
    recipe, receipt, _rng = rulebase.make_content(seed=7, force={"layout": layout})
    markup = sheets.build(recipe, receipt)
    filled, _report = signature.fill(markup, seed=7, names=("Vũ Thị Lan", "Đỗ Bá Kỳ"))
    assert sheets.labelled_runs(filled) == sheets.labelled_runs(markup)
    assert sheets.structure_from_markup(filled) == sheets.structure_from_markup(markup)


@pytest.mark.parametrize("layout", LAYOUTS)
def test_every_signature_block_in_the_rule_space_gets_a_mark(layout):
    """A blank signature line that stays blank is the gap this engine closes,
    so a family that quietly signs nothing should fail here rather than ship."""
    _fonts()
    recipe, receipt, _rng = rulebase.make_content(seed=11, force={"layout": layout})
    markup = sheets.build(recipe, receipt)
    blocks = len(signature.WHO.findall(markup))
    _filled, report = signature.fill(markup, seed=11, names=("Vũ Thị Lan",))
    assert len(report["marks"]) == blocks
    assert not report["skipped"]
