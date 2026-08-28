"""Every link and every image a document points at has to actually be there.

Written after a real failure, and after the check that should have caught it
did not. Eleven figures were built into `docs/figures/con-dau/`, embedded in
`docs/co-che-sinh-con-dau.md`, and verified with a script that resolved each
path **on disk**. Every one resolved. None of them was in git: `.gitignore`
ignores images by default and lets them back one directory at a time, and that
directory had no exception yet.

So the document was correct locally and would have shown eleven broken images
to everyone else — the exact shape of failure this repository keeps writing
tests for. Resolving a path on disk is not the question. The question is
whether a reader who clones the repo gets the file, and only `git ls-files`
answers that.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

# `![alt](target)` and `[text](target)`; the leading `!` is what separates an
# embedded image from an ordinary link, and both are checked the same way.
LINK = re.compile(r"(!?)\[[^\]]*\]\(([^)\s]+)\)")

# Suffixes git has to be carrying, because a reader cannot follow them unless
# the clone contains them. A link to a `.py` or `.md` is checked too; anything
# with no suffix is a directory link and checked as a path.
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}


def _tracked() -> set[str]:
    listing = subprocess.run(
        ["git", "ls-files"], cwd=str(REPO_ROOT),
        capture_output=True, text=True, check=True).stdout.split("\n")
    return {name for name in listing if name}


def _documents() -> list[Path]:
    return sorted([REPO_ROOT / "README.md", *(REPO_ROOT / "docs").rglob("*.md")])


def _targets(document: Path):
    """(is_image, target) for each local link, anchors and URLs dropped."""
    for bang, target in LINK.findall(document.read_text(encoding="utf-8")):
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        yield bool(bang), target.split("#")[0]


@pytest.mark.parametrize("document", _documents(), ids=lambda p: p.name)
def test_every_link_in_a_document_resolves(document: Path):
    missing = []
    for _is_image, target in _targets(document):
        if target and not (document.parent / target).resolve().exists():
            missing.append(target)
    assert missing == [], (
        f"{document.relative_to(REPO_ROOT)} points at files that are not there:\n  "
        + "\n  ".join(missing))


def test_every_committed_figure_is_embedded_by_some_document():
    """The other direction: a figure nobody embeds is a figure nobody sees.

    Written after the headline figure of `co-che-sinh-con-dau.md` lost its
    embed during a rewrite of the section around it. The file stayed on disk,
    stayed in git, and stopped being referenced by anything — so neither the
    link test nor the tracking test above had anything to say about it.
    """
    root = REPO_ROOT / "docs" / "figures"
    embedded = {
        (document.parent / target).resolve()
        for document in _documents()
        for _is_image, target in _targets(document)
        if target
    }
    orphans = sorted(
        path.relative_to(REPO_ROOT).as_posix()
        for path in root.rglob("*")
        if path.suffix.lower() in IMAGE_SUFFIXES
        and path.relative_to(REPO_ROOT).as_posix() in _tracked()
        and path.resolve() not in embedded)
    assert orphans == [], (
        "these figures are committed but no document embeds them, so they are "
        "carried and never read:\n  " + "\n  ".join(orphans))


@pytest.mark.parametrize("document", _documents(), ids=lambda p: p.name)
def test_every_image_a_document_embeds_is_tracked_by_git(document: Path):
    """On disk is not enough. `.gitignore` ignores images by default.

    This is the check that was missing when `docs/figures/con-dau/` was added:
    the files existed, the paths resolved, and `git ls-files` returned nothing.
    """
    tracked = _tracked()
    untracked = []
    for is_image, target in _targets(document):
        if not target:
            continue
        path = (document.parent / target).resolve()
        if not path.exists():
            continue                      # the test above owns that failure
        if not (is_image or path.suffix.lower() in IMAGE_SUFFIXES):
            continue
        relative = path.relative_to(REPO_ROOT).as_posix()
        if relative not in tracked:
            untracked.append(relative)
    assert untracked == [], (
        f"{document.relative_to(REPO_ROOT)} embeds images that are on this disk "
        f"but not in git, so every other reader sees a broken image:\n  "
        + "\n  ".join(untracked)
        + "\n\n.gitignore ignores images by default and lets them back one "
          "directory at a time. Add a negation for the directory, with the "
          "reason on its own line -- git reads a trailing comment as part of "
          "the pattern.")
