"""CLI wiring: listing backends and rendering with one or all of them."""

from __future__ import annotations

import json

import pytest

from vlm_ocr_synthetic.cli import main
from vlm_ocr_synthetic.renderers import renderer_names
from vlm_ocr_synthetic.samples import get_sample


def test_list_reports_every_backend(capsys):
    assert main(["list"]) == 0

    out = capsys.readouterr().out
    for name in renderer_names():
        assert name in out
    assert "invoice" in out


def test_list_json_is_machine_readable(capsys):
    assert main(["list", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert set(payload) == set(renderer_names())


def test_unknown_subcommand_exits_with_usage_error():
    with pytest.raises(SystemExit):
        main(["nope"])


@pytest.mark.slow
def test_render_all_writes_one_directory_per_backend(tmp_path, capsys):
    exit_code = main(["render", "-r", "all", "-o", str(tmp_path), "--scale", "0.4"])
    captured = capsys.readouterr()

    assert exit_code == 0
    rendered = {p.name for p in tmp_path.iterdir() if p.is_dir()}
    skipped = {
        line.split(":")[0].removeprefix("[skip] ")
        for line in captured.err.splitlines()
        if line.startswith("[skip]")
    }
    assert rendered | skipped == set(renderer_names())

    for name in rendered:
        assert (tmp_path / name / "page.png").exists()
        assert (tmp_path / name / "page.json").exists()


@pytest.mark.slow
def test_render_from_a_document_file(tmp_path):
    document_path = tmp_path / "doc.json"
    document_path.write_text(get_sample("invoice").model_dump_json(), encoding="utf-8")

    exit_code = main(
        [
            "render",
            "-r",
            "synthdog",
            "-d",
            str(document_path),
            "-o",
            str(tmp_path / "out"),
            "--stem",
            "invoice",
            "--scale",
            "0.4",
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "out" / "synthdog" / "invoice.png").exists()


@pytest.mark.slow
def test_render_with_a_shipped_config(tmp_path):
    from pathlib import Path

    config = Path(__file__).resolve().parent.parent / "configs" / "synthdog_default.yaml"
    exit_code = main(
        ["render", "-c", str(config), "-o", str(tmp_path), "--scale", "0.4"]
    )

    assert exit_code == 0
    assert (tmp_path / "synthdog" / "page.png").exists()


def test_doctor_reports_a_healthy_environment(capsys):
    assert main(["doctor"]) == 0

    out = capsys.readouterr().out
    assert "python" in out and "renderers" in out
    assert "no problems found" in out


def test_doctor_json_lists_dependencies(capsys):
    assert main(["doctor", "--json"]) == 0

    payload = json.loads(capsys.readouterr().out)
    distributions = {entry["distribution"] for entry in payload["dependencies"]}
    assert {"pydantic", "Pillow", "PyYAML"} <= distributions
