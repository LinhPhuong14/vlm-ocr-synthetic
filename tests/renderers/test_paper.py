"""The paper layer: shared by both backends, so it gets its own contract.

The genalog degradations (blur, bleed-through, salt, pepper) are checked
for the property that matters downstream -- they change pixels, never the
annotations, and always reproducibly.
"""

from __future__ import annotations

import random

import pytest
from pydantic import ValidationError

from vlm_ocr_synthetic.renderers.paper import (
    PaperConfig,
    apply_paper,
    crease_positions,
    fold_shading,
    paper_texture,
)

pytest.importorskip("PIL")


@pytest.fixture
def page():
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (120, 90), (255, 255, 255))
    ImageDraw.Draw(image).rectangle([20, 20, 60, 40], fill=(10, 10, 10))
    return image


def _mean(image) -> float:
    grayscale = image.convert("L")
    histogram = grayscale.histogram()
    total = sum(histogram)
    return sum(value * count for value, count in enumerate(histogram)) / total


def test_disabled_paper_returns_the_render_untouched(page):
    result = apply_paper(page, PaperConfig(enabled=False), random.Random(0))
    assert result.tobytes() == page.tobytes()


def test_white_sheet_without_effects_is_a_noop(page):
    config = PaperConfig(color=(255, 255, 255), grain=0)
    assert config.is_noop()
    assert apply_paper(page, config, random.Random(0)).tobytes() == page.tobytes()


def test_paper_tints_the_sheet_without_erasing_ink(page):
    config = PaperConfig(color=(240, 230, 200), grain=0)
    result = apply_paper(page, config, random.Random(1))

    assert result.getpixel((100, 80)) == (240, 230, 200)  # background takes the tint
    ink = result.getpixel((40, 30))
    assert max(ink) < 60  # ink stays dark


def test_tinted_sheet_is_never_a_noop():
    """The paper colour alone still has to be applied."""
    assert not PaperConfig(color=(250, 249, 245), grain=0).is_noop()


def test_grain_adds_variation_but_keeps_the_mean(page):
    flat = apply_paper(page, PaperConfig(grain=0), random.Random(2))
    grainy = apply_paper(page, PaperConfig(grain=8), random.Random(2))

    assert flat.tobytes() != grainy.tobytes()
    assert _mean(grainy) == pytest.approx(_mean(flat), abs=3.0)


def test_same_seed_same_paper(page):
    first = apply_paper(page, PaperConfig(grain=6), random.Random(7))
    second = apply_paper(page, PaperConfig(grain=6), random.Random(7))
    assert first.tobytes() == second.tobytes()


def test_different_seed_different_paper(page):
    first = apply_paper(page, PaperConfig(grain=6), random.Random(1))
    second = apply_paper(page, PaperConfig(grain=6), random.Random(2))
    assert first.tobytes() != second.tobytes()


def test_texture_is_the_requested_size():
    texture = paper_texture((64, 32), PaperConfig(grain=3), random.Random(0))
    assert texture.size == (64, 32)
    assert texture.mode == "RGB"


@pytest.mark.parametrize(
    "config",
    [
        PaperConfig(grain=0, blur=1.2),
        PaperConfig(grain=0, bleed_through=0.3),
        PaperConfig(grain=0, salt=0.05),
        PaperConfig(grain=0, pepper=0.05),
        PaperConfig(grain=0, vignette=0.5),
    ],
    ids=["blur", "bleed_through", "salt", "pepper", "vignette"],
)
def test_every_degradation_changes_the_page(page, config):
    """Each genalog-style effect must actually do something on its own."""
    baseline = apply_paper(page, PaperConfig(grain=0), random.Random(3))
    degraded = apply_paper(page, config, random.Random(3))

    assert degraded.size == page.size
    assert degraded.tobytes() != baseline.tobytes()


def test_pepper_darkens_and_salt_lightens(page):
    baseline = _mean(apply_paper(page, PaperConfig(grain=0), random.Random(4)))
    peppered = _mean(
        apply_paper(page, PaperConfig(grain=0, pepper=0.2), random.Random(4))
    )
    salted = _mean(apply_paper(page, PaperConfig(grain=0, salt=0.2), random.Random(4)))

    assert peppered < baseline
    assert salted > baseline


def test_vignette_darkens_corners_more_than_the_centre(page):
    result = apply_paper(page, PaperConfig(grain=0, vignette=0.8), random.Random(5))

    corner = sum(result.getpixel((1, 1)))
    centre = sum(result.getpixel((90, 45)))
    assert corner < centre


def test_config_rejects_unknown_keys():
    with pytest.raises(ValidationError):
        PaperConfig(noise_sigma=4)


# ------------------------------------------------ paper as a separate stage


@pytest.mark.slow
def test_render_returns_structure_then_paper_is_applied_on_top():
    """A backend renders the structure; paper is a stage after it."""
    from vlm_ocr_synthetic.renderers import get_renderer, get_renderer_class
    from vlm_ocr_synthetic.samples import get_sample

    if get_renderer_class("synthdog").check_available() is not None:
        pytest.skip("synthdog unavailable")

    document = get_sample("receipt_vn")
    structure = get_renderer(
        "synthdog", {"scale": 0.4, "paper": {"enabled": False}}
    ).render(document)
    aged = structure.with_paper(PaperConfig(grain=8, vignette=0.3))

    # structure survives untouched; only pixels move
    assert aged.document == structure.document
    assert aged.image.size == structure.image.size
    assert aged.image.tobytes() != structure.image.tobytes()
    assert aged.metadata["paper"]["grain"] == 8.0
    assert structure.metadata["paper"]["enabled"] is False


@pytest.mark.slow
def test_paper_applied_afterwards_matches_paper_applied_inline():
    """Same seed, same page -- whichever way the stage is invoked."""
    from vlm_ocr_synthetic.renderers import get_renderer, get_renderer_class
    from vlm_ocr_synthetic.samples import get_sample

    if get_renderer_class("synthdog").check_available() is not None:
        pytest.skip("synthdog unavailable")

    document = get_sample("invoice")
    paper = {"grain": 5.0, "pepper": 0.001}

    inline = get_renderer("synthdog", {"scale": 0.4, "seed": 3, "paper": paper}).render(
        document
    )
    two_stage = (
        get_renderer("synthdog", {"scale": 0.4, "seed": 3, "paper": {"enabled": False}})
        .render(document)
        .with_paper(PaperConfig(**paper), seed=3)
    )

    assert inline.image.tobytes() == two_stage.image.tobytes()


def test_several_papers_reuse_one_structural_render():
    """The point of the split: try presets without re-rendering."""
    from PIL import Image

    from vlm_ocr_synthetic.schemas.document import Document
    from vlm_ocr_synthetic.schemas.render import RenderResult

    structure = RenderResult(
        image=Image.new("RGB", (40, 20), (255, 255, 255)),
        document=Document(page_width=40, page_height=20),
        renderer="fake",
        metadata={"seed": 1},
    )

    clean = structure.with_paper(PaperConfig(color=(250, 249, 245), grain=0))
    scanned = structure.with_paper(PaperConfig(color=(250, 249, 245), grain=9))

    assert clean.image.tobytes() != scanned.image.tobytes()
    assert structure.image.getpixel((0, 0)) == (255, 255, 255)  # original intact


# ------------------------------------------------------------------ folds


def test_crease_positions_split_the_page_evenly():
    assert crease_positions(1, 0, random.Random(0)) == [0.5]
    assert crease_positions(2, 0, random.Random(0)) == pytest.approx([1 / 3, 2 / 3])
    assert crease_positions(0, 0, random.Random(0)) == []


def test_crease_jitter_is_seeded_and_stays_on_the_page():
    first = crease_positions(3, 0.05, random.Random(11))
    second = crease_positions(3, 0.05, random.Random(11))
    other = crease_positions(3, 0.05, random.Random(12))

    assert first == second != other
    assert all(0.02 <= position <= 0.98 for position in first)


def test_folds_need_both_a_count_and_a_strength():
    assert not PaperConfig(fold_rows=2).has_folds()  # strength defaults to 0
    assert not PaperConfig(fold_strength=0.8).has_folds()  # no creases asked for
    assert PaperConfig(fold_rows=2, fold_strength=0.8).has_folds()


def test_fold_shading_is_neutral_where_there_is_no_crease():
    config = PaperConfig(fold_rows=1, fold_strength=0.8, fold_jitter=0)
    shading = fold_shading((80, 200), config, random.Random(0))

    assert shading.size == (80, 200)
    # the panel interiors stay near neutral grey
    assert shading.getpixel((40, 10)) == pytest.approx(128, abs=30)


def test_the_crease_is_darker_than_the_panel_around_it():
    config = PaperConfig(fold_rows=1, fold_strength=1.0, fold_jitter=0, fold_softness=2)
    shading = fold_shading((60, 200), config, random.Random(0))

    crease_row = min(shading.getpixel((30, y)) for y in range(96, 105))
    panel_row = shading.getpixel((30, 160))
    assert crease_row < panel_row


@pytest.mark.parametrize(
    "config",
    [
        PaperConfig(grain=0, fold_rows=2, fold_strength=0.7),
        PaperConfig(grain=0, fold_columns=1, fold_strength=0.7),
        PaperConfig(grain=0, fold_rows=1, fold_columns=1, fold_strength=0.7),
    ],
    ids=["trifold", "vertical", "quarter"],
)
def test_folds_change_the_page(page, config):
    baseline = apply_paper(page, PaperConfig(grain=0), random.Random(3))
    folded = apply_paper(page, config, random.Random(3))

    assert folded.size == page.size
    assert folded.tobytes() != baseline.tobytes()


def test_folded_pages_are_reproducible(page):
    config = PaperConfig(grain=3, fold_rows=2, fold_columns=1, fold_strength=0.6)

    assert (
        apply_paper(page, config, random.Random(9)).tobytes()
        == apply_paper(page, config, random.Random(9)).tobytes()
    )
    assert (
        apply_paper(page, config, random.Random(9)).tobytes()
        != apply_paper(page, config, random.Random(10)).tobytes()
    )


# ---------------------------------------------------------------- textures


@pytest.fixture
def texture_dir(tmp_path):
    """Two fake paper photographs, the way synthdog ships resources/paper."""
    from PIL import Image

    for index, shade in enumerate((200, 160)):
        Image.new("L", (32, 32), shade).save(tmp_path / f"paper{index}.jpg")
    (tmp_path / "notes.txt").write_text("not an image", encoding="utf-8")
    return tmp_path


def test_texture_file_darkens_the_sheet(page, texture_dir):
    plain = apply_paper(page, PaperConfig(grain=0), random.Random(0))
    textured = apply_paper(
        page,
        PaperConfig(grain=0, texture=str(texture_dir / "paper1.jpg")),
        random.Random(0),
    )

    assert _mean(textured) < _mean(plain)


def test_texture_directory_picks_one_image_by_seed(page, texture_dir):
    first = apply_paper(
        page, PaperConfig(grain=0, texture=str(texture_dir)), random.Random(1)
    )
    same = apply_paper(
        page, PaperConfig(grain=0, texture=str(texture_dir)), random.Random(1)
    )

    assert first.tobytes() == same.tobytes()
    # a non-image sitting in the directory must not be picked up
    assert (texture_dir / "notes.txt").exists()


def test_texture_strength_blends_towards_a_plain_sheet(page, texture_dir):
    strong = apply_paper(
        page,
        PaperConfig(grain=0, texture=str(texture_dir / "paper1.jpg")),
        random.Random(0),
    )
    weak = apply_paper(
        page,
        PaperConfig(
            grain=0, texture=str(texture_dir / "paper1.jpg"), texture_strength=0.2
        ),
        random.Random(0),
    )

    assert _mean(weak) > _mean(strong)


def test_missing_texture_is_reported(page, tmp_path):
    with pytest.raises(FileNotFoundError):
        apply_paper(
            page, PaperConfig(texture=str(tmp_path / "nope.jpg")), random.Random(0)
        )

    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        apply_paper(page, PaperConfig(texture=str(empty)), random.Random(0))


def test_texture_alone_is_not_a_noop(texture_dir):
    assert not PaperConfig(
        color=(255, 255, 255), grain=0, texture=str(texture_dir)
    ).is_noop()
