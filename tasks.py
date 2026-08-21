"""Every task in this repository, runnable without `make`.

    python tasks.py                 # list the tasks
    python tasks.py setup
    python tasks.py dataset -n 5 -o data/thu
    python tasks.py proof --dataset data/dataset60

Windows has no `make`, and the Makefile is full of things `cmd.exe` cannot run
-- `bin/python`, `rm -rf`, `git ls-files | xargs`. Rather than keep a second
copy of the task list in a `.bat` that drifts, the tasks live here and the
Makefile is a thin wrapper that calls this file. There is one definition of
what `dataset` means, on every platform.

Only the standard library is used, so this runs on a bare system Python before
any virtualenv exists -- which it has to, since building them is a task.
"""

from __future__ import annotations

import argparse
import compileall
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))

from paths import (  # noqa: E402
    REPO_ROOT,
    VENDORED,
    VENVS,
    WINDOWS,
    first_available_python,
    venv_python,
    venv_tool,
)

SYNTHDOG = REPO_ROOT / "generators" / "synthdog"
TASKS: dict[str, tuple] = {}


def task(name: str, help: str):
    def register(function):
        TASKS[name] = (function, help)
        return function

    return register


def run(command, cwd: Path | None = None, check: bool = True) -> int:
    printable = " ".join(str(part) for part in command)
    print(f"$ {printable}")
    result = subprocess.run([str(part) for part in command], cwd=str(cwd or REPO_ROOT))
    if check and result.returncode != 0:
        raise SystemExit(result.returncode)
    return result.returncode


# ------------------------------------------------------------------ setup


PIP_FAILED = """
pip could not install into the {name} environment.

If the output above says CERTIFICATE_VERIFY_FAILED, this is not a repository
problem: something between this machine and pypi.org is re-signing TLS with a
certificate Python does not trust -- usually a corporate inspecting proxy. The
browser trusts it because Windows trusts it; Python ships its own trust store
and does not.

Teach Python to use the Windows store, once, and every environment this task
builds afterwards inherits it:

  py -m pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org pip_system_certs

docs/windows.md has the alternatives (a pip.ini, PIP_CERT, an exported CA) and
what to do about Playwright, which downloads through the same proxy.
"""


def _pip(python: Path, name: str, *arguments) -> None:
    """A pip step that explains itself when the network refuses it.

    Worth the wrapper because the raw failure is five identical retry warnings
    and an OSError, which reads like a broken repository rather than like a
    proxy -- and because it happens on the FIRST thing setup does, so there is
    nothing else on screen to suggest otherwise.
    """
    if run([python, "-m", "pip", *arguments], check=False) != 0:
        raise SystemExit(PIP_FAILED.format(name=name))


def _make_venv(name: str, requirements: Path, extra_first: list[str] | None = None) -> Path:
    venv = VENVS[name]
    run([sys.executable, "-m", "venv", venv])
    python = venv_python(venv)
    _pip(python, name, "install", "-q", "-U", "pip")
    if extra_first:
        _pip(python, name, "install", "-q", *extra_first)
    _pip(python, name, "install", "-q", "-r", str(requirements))
    return python


@task("setup-synthdog", "glyph renderer: synthtiger (needs Python 3.8-3.11)")
def setup_synthdog(args) -> None:
    if sys.version_info >= (3, 12):
        raise SystemExit(
            f"synthdog needs Python 3.8-3.11, this is {sys.version.split()[0]}.\n"
            "Run this task with an older interpreter:\n"
            "  py -3.11 tasks.py setup-synthdog        (Windows)\n"
            "  python3.11 tasks.py setup-synthdog      (Linux/macOS)\n"
            "See docs/python-versions.md for why the cap is real."
        )
    python = _make_venv(
        "synthdog", SYNTHDOG / "requirements.txt", ["-U", "setuptools", "wheel"]
    )
    run([python, "-c", "import synthtiger, PIL; print('synthtiger', synthtiger.__version__,"
                       " '| pillow', PIL.__version__)"])


@task("setup-html", "HTML renderer: playwright plus a headless browser")
def setup_html(args) -> None:
    python = _make_venv("html", REPO_ROOT / "generators" / "html" / "requirements.txt")
    run([python, "-c", "import playwright, cv2; print('html renderer ready')"])
    if WINDOWS:
        # No system browser is shipped on Windows, unlike the Linux container
        # this repository was built in, so Playwright has to fetch its own.
        run([python, "-m", "playwright", "install", "chromium"])


@task("setup-genalog", "genalog renderer: WeasyPrint plus PyMuPDF")
def setup_genalog(args) -> None:
    genalog = REPO_ROOT / "generators" / "genalog"
    python = _make_venv("genalog", genalog / "requirements.txt")
    # genalog itself is NOT installed from PyPI: its source is vendored under
    # generators/genalog/, and because that directory is the script directory of
    # render.py it lands on sys.path[0] and wins over anything pip installed.
    # Installing the package as well would leave two copies with the vendored
    # one silently shadowing the other.
    run([python, "-c", "import sys; sys.path.insert(0, r'%s');"
                       " import genalog, weasyprint;"
                       " print('genalog renderer ready:', genalog.__file__)" % genalog])
    if WINDOWS:
        print(
            "\nNOTE: WeasyPrint on Windows needs the GTK runtime for Pango and "
            "cairo.\n      See docs/windows.md."
        )


@task("setup", "build all three renderer environments")
def setup(args) -> None:
    setup_synthdog(args)
    setup_html(args)
    setup_genalog(args)


# ------------------------------------------------------------- generation


@task("textures", "regenerate the generated paper sheets in textures/paper")
def textures(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "make_textures.py"])


@task("ornaments", "regenerate the seals and flourishes in textures/ornament")
def ornaments(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "make_ornaments.py"])


@task("templates", "print the reference sheets in samples/")
def templates(args) -> None:
    for directory in ("invoice-templates", "form-templates"):
        run([first_available_python(),
             REPO_ROOT / "samples" / directory / "render.py"])


@task("blanks", "the standard forms each document is drawn from")
def blanks(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "rules_report.py",
         "--blanks"])


@task("dataset", "labelled dataset with all three renderers (-n per renderer)")
def dataset(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "generate_dataset.py",
         "-o", args.out, "-n", str(args.count)])


@task("dataset-clean", "the same dataset with no ageing and no distortion")
def dataset_clean(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "generate_dataset.py",
         "-o", f"{args.out}_clean", "-n", str(args.count), "--clean"])


@task("tables", "table-structure images, from the html backend")
def tables(args) -> None:
    # The html backend's interpreter, because the table generator IS the html
    # backend: same Chromium, same boxes off the same laid-out DOM. There is no
    # fourth environment to build any more.
    run([venv_python(VENVS["html"]), REPO_ROOT / "tools" / "generate_tables.py",
         "-o", args.out, "-n", str(args.count)])


@task("handwriting", "regenerate data/hand12: the fields a person fills in, in ink")
def handwriting(args) -> None:
    # The html backend's own interpreter, and a job list rather than -n: which
    # layouts are in the set is the measurement, not a quota. `setup-writevit`
    # has to have run -- there is no fallback that draws letters, so a missing
    # checkpoint stops the run rather than typing the values and calling them
    # handwriting. See docs/handwriting-html.md.
    out = Path(args.out if args.out != str(Path("data") / "dataset60")
               else Path("data") / "hand12")
    run([venv_python(VENVS["html"]), REPO_ROOT / "generators" / "html" / "render.py",
         "--template", "auto", "--handwriting",
         "--jobs", REPO_ROOT / "data" / "hand12" / "jobs.json",
         "-o", out / "html"])


@task("setup-writevit", "clone WriteViT beside the repo and fetch its weights")
def setup_writevit(args) -> None:
    # Not one of the three renderer environments and deliberately not part of
    # `setup`: nothing here imports WriteViT, its weights and data are 294 MB,
    # and only `--handwriting` needs it.
    run([first_available_python(), REPO_ROOT / "tools" / "writevit" / "setup.py"])


@task("run", "run pipeline.yaml: preflight, shards in parallel, assemble")
def run_pipeline(args) -> None:
    command = [first_available_python(), REPO_ROOT / "pipeline" / "run.py"]
    if args.out != str(Path("data") / "dataset60"):
        command += ["-o", args.out]
    run(command)


@task("baseline-write", "capture the golden fingerprint of the generator")
def baseline_write(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "baseline.py", "--write",
         "--reason", args.reason])


@task("baseline-verify", "regenerate the fixed plans and compare to the golden file")
def baseline_verify(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "baseline.py"])


@task("proof", "read a dataset back with Tesseract and score it")
def proof(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "ocr_proof.py", args.dataset])


@task("profile", "time every stage of every renderer and write a cost model")
def profile(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "profile_pipeline.py",
         "-c", str(args.count), "-o", args.out])


@task("check-boxes", "verify every renderer's boxes still land on its text")
def check_boxes(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "check_boxes.py", args.dataset])


@task("showcase", "one before/after image per degradation model")
def showcase(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "degradation_showcase.py"])


@task("receipts", "100 receipts with the glyph renderer, via the synthtiger CLI")
def receipts(args) -> None:
    run([venv_tool(VENVS["synthdog"], "synthtiger"),
         "-o", "./outputs/VNReceipt", "-c", "100", "-w", "4", "-v",
         "template_receipt.py", "SynthVNReceipt", "config_vi_receipt.yaml"],
        cwd=SYNTHDOG)


@task("preview", "render a grid of sample receipts")
def preview(args) -> None:
    run([venv_python(VENVS["synthdog"]), "tools/preview_receipt.py",
         "--count", "8", "--grid", "4", "--seed", "2026", "--out", args.out],
        cwd=SYNTHDOG)


@task("preview-grid", "print sampled receipts as text (--layout to pin one)")
def preview_grid(args) -> None:
    command = [sys.executable, REPO_ROOT / "tools" / "preview_grid.py"]
    command += ["--layout", args.layout] if args.layout else ["--all"]
    run(command)


# -------------------------------------------------------------- the rules


@task("preflight", "every check that must pass before generating an image")
def preflight(args) -> None:
    run([first_available_python(), REPO_ROOT / "pipeline" / "preflight.py"])


@task("check-rules", "validate rules/: unreachable values, bad tags, missing files")
def check_rules(args) -> None:
    run([first_available_python(), REPO_ROOT / "tools" / "rules_report.py", "--check"])


@task("check-corpus", "validate corpus/: missing files, wrong column counts")
def check_corpus(args) -> None:
    run([sys.executable, REPO_ROOT / "tools" / "rules_report.py", "--corpus"])


@task("distribution", "show what 2000 draws from the rules look like")
def distribution(args) -> None:
    run([sys.executable, REPO_ROOT / "tools" / "rules_report.py", "--distribution"])


@task("monitor", "the whole rule space, or a run while it is still going")
def monitor(args) -> None:
    # `--static` needs nothing but the rules; a run directory needs nothing at
    # all beyond what is already on disk. Either way it writes nothing, so it is
    # safe to point at a job a pool of workers is in the middle of.
    command = [first_available_python(), REPO_ROOT / "tools" / "monitor.py"]
    command += [args.run] if getattr(args, "run", None) else ["--static"]
    run(command)


@task("list-degradations", "names usable in an augmentation chain")
def list_degradations(args) -> None:
    run([first_available_python(), "-c",
         "import degradation; print(chr(10).join(degradation.names()))"])


# ---------------------------------------------------------------- quality


def _tracked_python() -> list[Path]:
    listing = subprocess.run(
        ["git", "ls-files", "*.py"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, check=True,
    ).stdout.split()
    return [
        REPO_ROOT / name for name in listing
        if not name.startswith(VENDORED)
    ]


@task("check", "byte-compile every tracked Python file (no dependencies needed)")
def check(args) -> None:
    files = _tracked_python()
    ok = True
    for path in files:
        # `quiet=1` still prints the traceback of a real syntax error, which is
        # the only thing this task exists to surface.
        if not compileall.compile_file(path, quiet=1, force=True):
            ok = False
    if not ok:
        raise SystemExit("some files failed to compile")
    print(f"all {len(files)} python files compile")


@task("lint", "ruff: correctness and imports, not formatting")
def lint(args) -> None:
    run([_ruff(), "check", "."])


@task("format", "apply the fixes ruff can make safely")
def format_(args) -> None:
    run([_ruff(), "check", "--fix", "."])


def _ruff():
    """Prefer a ruff inside a venv; fall back to one on PATH."""
    for venv in VENVS.values():
        candidate = venv_tool(venv, "ruff")
        if candidate.exists():
            return candidate
    found = shutil.which("ruff")
    if found:
        return found
    raise SystemExit("ruff not found: `pip install ruff`, or run `python tasks.py setup`")


# Directories `clean` must never walk into. A bare `rglob("__pycache__")`
# descends into every virtualenv and deletes site-packages caches -- harmless,
# but it is not what "remove caches and generated output" means, and on a slow
# disk it makes the next run of every tool noticeably slower.
SKIP_DIRS = {".git", ".venv", "node_modules"}


@task("clean", "remove caches and generated output")
def clean(args) -> None:
    targets = [
        REPO_ROOT / ".ruff_cache",
        REPO_ROOT / ".pytest_cache",
        SYNTHDOG / "outputs",
    ]
    targets += [
        path for path in REPO_ROOT.rglob("__pycache__")
        if not SKIP_DIRS.intersection(path.relative_to(REPO_ROOT).parts)
    ]
    for target in targets:
        if target.exists():
            print(f"rm -r {target.relative_to(REPO_ROOT)}")
            shutil.rmtree(target, ignore_errors=True)


# ------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("task", nargs="?", choices=sorted(TASKS), help="task to run")
    parser.add_argument("-o", "--out", default=str(Path("data") / "dataset60"),
                        help="output directory (dataset, dataset-clean, preview)")
    parser.add_argument("-n", "--count", type=int, default=20,
                        help="images per renderer (dataset, dataset-clean)")
    parser.add_argument("--dataset", default=str(Path("data") / "dataset60"),
                        help="dataset to score (proof)")
    parser.add_argument("--layout", help="pin one bố cục (preview-grid)")
    parser.add_argument("--reason", default="",
                        help="why the golden baseline is being replaced "
                             "(baseline-write); kept in the file")
    # No default on purpose: `monitor` with nothing to point at reports the rule
    # space, and a default would silently turn that into "monitor whichever
    # dataset happens to be the usual one".
    parser.add_argument("--run", help="a run directory to monitor")
    args = parser.parse_args()

    if not args.task:
        width = max(len(name) for name in TASKS)
        print("Tasks:\n")
        for name in sorted(TASKS):
            print(f"  {name:<{width}}  {TASKS[name][1]}")
        print(f"\n  python {Path(__file__).name} <task> [-n N] [-o DIR]")
        return 0

    if args.task == "preview" and args.out == str(Path("data") / "dataset60"):
        args.out = str(Path(os.environ.get("TEMP", "/tmp")) / "preview")

    TASKS[args.task][0](args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
