"""`synthesis.json`: the half of a dataset a converter could not have produced.

Three things this file has to get right, and all three fail quietly if it does
not:

* **the recipe comes back the shape it went in.** Everything that redraws a
  page -- `tools/check_boxes.py` above all -- hands the rebuilt recipe straight
  to `rulebase.make`. A rehydration that lost a `params` block would rebuild a
  *different* page and report every field of every image as missing, which is
  exactly what this repository spent a wave chasing once already.
* **params are written once.** That is the whole reason the provenance moved
  out of the index, so it is asserted rather than assumed.
* **a half-written file does not load.** The `attributes` block is written last,
  so a run killed in the middle leaves a file that fails to parse. A truncated
  provenance that parsed would be the worst outcome of the three: it would look
  like a dataset whose pages simply have no recipe.

Nothing here renders. Everything is a function of dicts and one temporary file.
"""

from __future__ import annotations

import json

import pytest

from pipeline import synthesis as S

LAYOUT = {"id": "eatery_ascii", "group": "retail_receipt", "params": {"width": 40}}
AGEING = {"id": "real_paper", "params": {"chain": [["paper_texture", {"alpha": 0.35}]]}}


def a_recipe(seed=2026, **attributes):
    return {"seed": seed,
            "attributes": {"layout": LAYOUT, "augmentation": AGEING, **attributes},
            "tags": ["thermal", "till_receipt"]}


def written(tmp_path, pages=2, framework="html"):
    path = tmp_path / S.NAME
    with S.Writer(path, framework) as writer:
        for index in range(pages):
            writer.add(f"html_{index:03d}.jpg", job_id=f"job-{index}",
                       layout="eatery_ascii", recipe=a_recipe(2026 + index),
                       text_sequence=f"page {index}")
    return path


# ------------------------------------------------------------------ the file


def test_the_file_says_what_it_is_and_how_many_pages_it_holds(tmp_path):
    raw = json.loads(written(tmp_path, pages=3).read_text(encoding="utf-8"))
    assert raw["schema_version"] == S.SCHEMA_VERSION
    assert raw["framework"] == "html"
    assert raw["images"] == 3
    assert list(raw["pages"]) == ["html_000.jpg", "html_001.jpg", "html_002.jpg"]


def test_a_file_with_no_pages_is_still_a_file(tmp_path):
    path = tmp_path / S.NAME
    with S.Writer(path, "html"):
        pass
    assert json.loads(path.read_text(encoding="utf-8"))["images"] == 0
    assert len(S.read(path)) == 0


def test_the_params_are_written_once_however_many_pages_drew_them(tmp_path):
    """The reason the provenance moved out of every line."""
    raw = json.loads(written(tmp_path, pages=20).read_text(encoding="utf-8"))

    assert raw["attributes"]["augmentation"] == {"real_paper": {"params": AGEING["params"]}}
    for page in raw["pages"].values():
        # A page names the option; it does not carry it.
        assert page["attributes"] == {"layout": "eatery_ascii",
                                      "augmentation": "real_paper"}
    assert raw["attributes"]["layout"]["eatery_ascii"] == {
        "group": LAYOUT["group"], "params": LAYOUT["params"]}


def test_one_id_meaning_two_things_stops_rather_than_being_written(tmp_path):
    """An id is a name for one set of params, so a second set is not a merge.

    Written out, it would make every page that drew that id ambiguous and the
    file impossible to rehydrate -- so it is refused where it happens, naming
    the page that did it.
    """
    with pytest.raises(S.SynthesisError, match="one id must mean one thing"):
        with S.Writer(tmp_path / S.NAME, "html") as writer:
            writer.add("a.jpg", recipe=a_recipe())
            writer.add("b.jpg", recipe={"seed": 1, "attributes": {
                "augmentation": {"id": "real_paper", "params": {"chain": []}}}})


def test_a_file_that_was_never_closed_does_not_load(tmp_path):
    """Law 3, applied to a killed run: not loading beats loading and being short."""
    path = tmp_path / S.NAME
    writer = S.Writer(path, "html")
    writer.add("html_000.jpg", recipe=a_recipe())
    # No close: the process died here.
    with pytest.raises(json.JSONDecodeError):
        json.loads(path.read_text(encoding="utf-8"))


# --------------------------------------------------------------- the reading


def test_the_recipe_comes_back_the_shape_it_went_in(tmp_path):
    """What `rulebase.make(force=...)` is handed, so it has to be exact."""
    recipe = a_recipe(2026)
    with S.Writer(tmp_path / S.NAME, "html") as writer:
        writer.add("html_000.jpg", layout="eatery_ascii", recipe=recipe)

    assert S.read(tmp_path).recipe("html_000.jpg") == recipe


def test_an_id_with_no_params_behind_it_is_a_hole_not_an_empty_dict(tmp_path):
    """Filling it in would rebuild a different page and say nothing about it."""
    path = written(tmp_path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    del raw["attributes"]["augmentation"]["real_paper"]
    path.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(S.SynthesisError, match="cannot be rebuilt"):
        S.read(path).recipe("html_000.jpg")


def test_the_two_files_are_checked_against_each_other(tmp_path):
    drew = S.read(written(tmp_path, pages=2))
    assert drew.problems(["html_000.jpg", "html_001.jpg"]) == []

    short = drew.problems(["html_000.jpg", "html_001.jpg", "html_002.jpg"])
    assert any("no synthesis entry" in problem for problem in short), short

    spare = drew.problems(["html_000.jpg"])
    assert any("name no image" in problem for problem in spare), spare


def test_a_missing_file_is_an_error_where_that_matters_and_empty_where_it_does_not(tmp_path):
    with pytest.raises(S.SynthesisError, match="migrate_metadata"):
        S.read(tmp_path)
    # ...and a reader that would otherwise refuse to run at all gets an empty
    # one, so "no provenance" is something to report rather than to stop for.
    assert len(S.read_if_there(tmp_path)) == 0
    assert S.read_if_there(tmp_path).layout("anything.jpg") == "?"


@pytest.mark.parametrize("given", ["dir", "metadata.jsonl", "synthesis.json"])
def test_the_three_names_for_a_dataset_all_resolve_to_the_file(tmp_path, given):
    (tmp_path / "metadata.jsonl").write_text("", encoding="utf-8")
    target = tmp_path if given == "dir" else tmp_path / given
    assert S.beside(target) == tmp_path / S.NAME


# --------------------------------------------------------------- the merging


def test_shards_fold_into_one_file_without_losing_a_page(tmp_path):
    """What `pipeline/run.py` does when it assembles a dataset from shards."""
    shards = []
    for index in range(3):
        directory = tmp_path / f"shard-{index}"
        directory.mkdir()
        with S.Writer(S.beside(directory), "html") as writer:
            writer.add(f"html_{index:03d}.jpg", job_id=f"job-{index}",
                       layout="eatery_ascii", recipe=a_recipe(2026 + index),
                       text_sequence=f"page {index}",
                       extra={"handwriting": {"inked": [index]}})
        shards.append(directory)

    S.merge(tmp_path / "all" / S.NAME, "html", shards)
    merged = S.read(tmp_path / "all")

    assert len(merged) == 3
    assert list(merged) == ["html_000.jpg", "html_001.jpg", "html_002.jpg"]
    assert merged.recipe("html_001.jpg") == a_recipe(2027)
    assert merged.text_sequence("html_002.jpg") == "page 2"
    # An extra a renderer wrote survives the fold: it is a label nothing else
    # holds, not a detail of the shard it came from.
    assert merged.entry("html_000.jpg")["handwriting"] == {"inked": [0]}
    # ...and the deduplication is done again over the whole set, not per shard.
    raw = json.loads((tmp_path / "all" / S.NAME).read_text(encoding="utf-8"))
    assert list(raw["attributes"]["augmentation"]) == ["real_paper"]
