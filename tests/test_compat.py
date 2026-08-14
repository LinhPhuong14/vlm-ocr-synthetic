"""Environment guarantees, checked on whatever interpreter is running.

Two properties matter enough to be enforced rather than documented:

1. the package works on this Python (3.10 through 3.14), and
2. rendering never pulls in pygame or synthtiger -- the dependency chain
   that cannot be installed on Python 3.14.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from vlm_ocr_synthetic.compat import (
    MIN_PYTHON,
    REQUIREMENTS,
    check_dependencies,
    environment_report,
    imaging_report,
    parse_version,
    problems,
)


def test_running_interpreter_is_supported():
    assert sys.version_info[:2] >= MIN_PYTHON


def test_environment_has_no_problems():
    """If this fails, `python -m vlm_ocr_synthetic doctor` explains why."""
    assert problems() == []


def test_every_requirement_meets_its_floor():
    for entry in check_dependencies():
        assert entry["status"] in {"ok", "not_installed"}, entry


def test_version_parsing_orders_the_floors_correctly():
    assert parse_version("2.11.9") < parse_version("2.12")
    assert parse_version("1.62.0") > parse_version("1.52")
    assert parse_version("6.0.3") > parse_version("6.0")
    assert parse_version("12.3.0") > parse_version("11.3")


@pytest.mark.parametrize("requirement", REQUIREMENTS, ids=lambda r: r.distribution)
def test_requirements_document_their_floor(requirement):
    assert requirement.note, "every floor needs a reason someone can check"
    if requirement.min_for_py314 is not None:
        assert parse_version(requirement.min_for_py314) > (0, 0, 0)


# --------------------------------------------------------------- no pygame

# The original synthdog (donut) renders through synthtiger, which pins
# pygame==2.6.1 -- no cp314 wheel, and the source build fails on 3.14.
# Our synthdog backend uses Pillow's FreeType binding instead; this test
# keeps it that way.
FORBIDDEN_MODULES = ("pygame", "synthtiger", "imgaug")
REPO_ROOT = Path(__file__).resolve().parent.parent

# NB: plain string substitution, not str.format -- the probe contains braces.
_IMPORT_PROBE = """
import sys
import vlm_ocr_synthetic.renderers.synthdog.renderer as synthdog
from vlm_ocr_synthetic.samples import get_sample

config = {"scale": 0.25, "paper": {"enabled": False}}
synthdog.SynthdogRenderer(config).render(get_sample("invoice"))

leaked = [name for name in FORBIDDEN if name in sys.modules]
print(",".join(leaked))
"""


def test_synthdog_backend_never_imports_pygame():
    """Run a real render in a clean interpreter and inspect sys.modules."""
    forbidden = ", ".join(repr(name) for name in FORBIDDEN_MODULES)
    probe = _IMPORT_PROBE.replace("FORBIDDEN", f"({forbidden})", 1)
    completed = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        timeout=180,
        cwd=REPO_ROOT,  # so `-c` finds the package without an install
    )

    assert completed.returncode == 0, completed.stderr
    leaked = completed.stdout.strip()
    assert leaked == "", f"synthdog pulled in: {leaked}"


def test_pillow_provides_the_freetype_stack_pygame_used_to():
    imaging = imaging_report()
    if not imaging["available"]:
        pytest.skip(f"Pillow not installed: {imaging['reason']}")

    assert imaging["freetype"], "Pillow without FreeType cannot draw text"


def test_doctor_report_is_json_serialisable():
    import json

    report = environment_report()
    payload = json.loads(json.dumps(report))

    assert payload["python"]["supported"] is True
    assert set(payload) == {"python", "renderers", "imaging", "dependencies"}
