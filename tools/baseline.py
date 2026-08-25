"""Fingerprint what the generator produces, and check it still produces it.

    python tools/baseline.py --write     # capture  (make baseline-write)
    python tools/baseline.py             # verify   (make baseline-verify)

W1 replaces the sequential driver with a sharded, parallel one. "The parallel
path gives the same result as the sequential one" is only checkable against a
record of what the sequential one gave, taken *before* it was touched -- so this
is captured first and everything after has to reproduce it.

The fingerprint is sha256 of every image, of every page's record, and of the
`synthesis.json` beside them -- all normalised. Not a count, not a spot
check: a driver that quietly drops one image or renumbers two of them passes a
count, and one that writes the right pixels from the wrong recipe passes on
pixels alone.

**What normalisation does, exactly.** Each record is parsed and re-dumped with
`sort_keys=True` and `ensure_ascii=False`, so key order and float spelling
cannot make an identical record hash differently. Nothing else is touched -- no
field is excluded. If a path or a timestamp ever enters a record this
verification starts failing on every machine, which is the correct outcome: both
belong in `timings.json`, not in a label.

**A metadata schema is a condition too.** Half the fingerprint is metadata
hashes, so changing the shape of a line makes every one of them differ without a
pixel moving. `inputs` therefore records `pipeline/record.py`'s schema version
alongside the rule hashes, and a bump reads as KẾ HOẠCH ĐÃ ĐỔI -- recapture --
rather than as the regression this file exists to catch.

**A plan names its layouts, and the file records them.** Both halves of that
were missing and it cost a week of ambiguity. `split_by_layout` hands quotas out
in list order, so `-n 5` meant "the first five layouts in the directory"; when
the rule-base grew from five layouts to fourteen those plans silently started
drawing a different five. The file recorded only the *output*, so it went red
and could not say whether the plan had moved or the renderer had regressed --
and the cheapest way to make it green was to recapture, i.e. to delete the
check. Every plan now states its layouts by name, and every capture writes down
the conditions it was taken under: layouts, seed, count, pairing, and a hash of
`rulebase/rules`, `rulebase/corpus`, and *the layout files that plan names* --
not the whole layouts directory, or the baseline would go red again the moment
someone added a layout no plan draws.

`baseline-verify` reports the two separately and they mean opposite things:

    KẾ HOẠCH ĐÃ ĐỔI          the conditions moved. Not a regression; recapture.
    CÙNG KẾ HOẠCH, KHÁC PIXEL  the regression this file exists to catch.

Three fixed plans, because one is not enough:

* `n3` is the plan the W1 brief names, on three named layouts.
* `n5` is every thermal layout -- the till-roll half of the rule-base.
* `n36` is every layout, one image each per backend.

Adding a fifteenth layout leaves all three green, which is the point: a
regression baseline must not move when someone adds unrelated content.

This needs all three renderer virtualenvs, so it is a hand-run command and not
part of the `tests` CI job. Keeping that job down to pytest and pyyaml is what
holds `rulebase/` to its one dependency.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from pipeline import record, synthesis  # noqa: E402

GOLDEN = REPO_ROOT / "tests" / "golden" / "baseline.json"

# Every plan NAMES ITS LAYOUTS. That is the whole of W2c and it is worth being
# blunt about why: `split_by_layout` hands quotas out in list order, so a plan
# that said only `-n 5` drew "the first five layouts in the directory". When the
# rule-base went from five layouts to fourteen, those plans quietly started
# drawing a different five, the baseline went red, and it had no way to say
# whether that was the plan moving or the renderer regressing. A regression
# baseline that shifts when someone adds unrelated content is not a baseline.
#
# Adding a plan is fine. Editing one means recapturing.
THERMAL = ["eatery_ascii", "eatery_indexed", "market_barcode",
           "market_compact", "market_vat"]
INVOICE = ["invoice_brand", "invoice_dense_table", "invoice_export",
           "invoice_header_table", "invoice_hotel_compact", "invoice_hotel_stay",
           "invoice_keyvalue", "invoice_logo_center", "invoice_logo_split",
           "invoice_minimalist", "invoice_multipage", "invoice_power",
           "invoice_remittance", "invoice_sidebar", "invoice_tax_en",
           "invoice_two_column", "invoice_vat_form", "invoice_vat_summary",
           "invoice_water"]
# Documents that are not a sale: a hospital's statement of treatment costs, an
# authorisation to collect money on somebody's behalf, and the ten root-3
# (Form / Application) layouts -- a questionnaire, a timesheet, a checkbox
# form, a government application, and so on. Cut sheets like the invoices, and
# drawn by the same three backends, but none of them is an invoice and none is
# named like one -- which is why they are their own list rather than an entry
# in the one above.
FORM = ["authorisation_letter", "form_activity_signature", "form_checkbox_heavy",
        "form_dense_registration", "form_government_app", "form_multi_section",
        "form_project_kv", "form_questionnaire", "form_table_based",
        "form_timesheet_grid", "form_two_column", "medical_statement"]

PLANS: dict[str, dict] = {
    # The plan the W1 brief names, on the three layouts it named.
    "n3": {"per_backend": 3, "seed": 2026, "layouts": THERMAL[:3]},
    # Every thermal layout: the till-roll half of the rule-base.
    "n5": {"per_backend": 5, "seed": 2026, "layouts": THERMAL},
    # Every layout, one image each per backend, so nothing is outside the net.
    # The name states the count, so it changes when the count does -- a plan
    # called `n14` that draws sixteen layouts is a plan nobody can check by
    # reading it. A rename means the golden file has no entry under the new key
    # and `make baseline-verify` says so, which is the correct report: the
    # generator grew, and the fingerprint has to be recaptured on a machine with
    # all three renderer environments. (Golden is still filed under `n14` from
    # this plan's growth to sixteen, and again to twenty-six -- neither
    # recapture was ever hand-run. All three are one `make baseline-write
    # REASON="..."` away.)
    "n36": {"per_backend": 36, "seed": 2026,
            "layouts": sorted(THERMAL + INVOICE + FORM)},
}

# What a plan's images are a function of, beyond the plan itself. A change to one
# of these changes the pixels legitimately, and the baseline should say so in
# those words rather than pointing at sixty differing hashes.
#
# **Scoped to the plan, not to the repository.** A whole-directory hash would put
# the baseline back where it started -- red the moment anyone adds a layout no
# plan draws. So:
#
#   rulebase/rules     the rule set as the sampler resolves it, with the layout
#                      attribute cut down to the layouts this plan names. Adding
#                      a fifteenth layout leaves it untouched, which is correct:
#                      a run pinned to `eatery_ascii` draws the same recipe
#                      before and after -- measured, not assumed.
#   rulebase/layouts   only the layout files the plan names.
#   rulebase/corpus    the whole directory: every line is in play for any plan.
CORPUS_ROOT = "rulebase/corpus"
LAYOUT_ROOT = "rulebase/layouts"
RULES_ROOT = "rulebase/rules"
FINGERPRINTED = (RULES_ROOT, LAYOUT_ROOT, CORPUS_ROOT)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _normalise(line: str) -> str:
    """One metadata line, in a form that hashes the same everywhere."""
    return json.dumps(json.loads(line), sort_keys=True, ensure_ascii=False)


def _digest(paths, root: Path) -> str:
    """Contents, not mtimes: a fresh clone must not look like a change."""
    digest = hashlib.sha256()
    for path in paths:
        digest.update(str(path.relative_to(root)).encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _canonical_rules(layouts) -> str:
    """The rule set the sampler would resolve, as stable text.

    Read through `load_rules` rather than off the YAML, so a comment or a
    reordering is not mistaken for a change and a genuine change cannot hide in
    formatting. The layout attribute is cut to the plan's own layouts: options
    it never draws are not inputs to it.
    """
    sys.path.insert(0, str(REPO_ROOT))
    from rulebase.spec import load_rules

    wanted = set(layouts)
    payload = []
    for attribute, options in load_rules().items():
        for option in options:
            if attribute == "layout" and option.id not in wanted:
                continue
            payload.append({
                "attribute": attribute,
                "id": option.id,
                "weight": option.weight,
                "group": option.group,
                "tags": sorted(option.tags),
                "requires": sorted(option.requires),
                "excludes": sorted(option.excludes),
                "params": option.params,
            })
    payload.sort(key=lambda entry: (entry["attribute"], entry["id"]))
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def rules_fingerprint(layouts) -> dict[str, str]:
    """One hash per input the plan's images are a function of.

    Per input rather than one number for all of them, so a red run can name
    *which* one moved.
    """
    corpus = REPO_ROOT / CORPUS_ROOT
    layout_root = REPO_ROOT / LAYOUT_ROOT
    return {
        RULES_ROOT: _sha(_canonical_rules(layouts).encode("utf-8")),
        LAYOUT_ROOT: _digest(
            [layout_root / f"{name}.yaml" for name in sorted(layouts)], layout_root),
        CORPUS_ROOT: _digest(
            sorted(p for p in corpus.rglob("*") if p.is_file()), corpus),
    }


def plan_inputs(plan: dict) -> dict:
    """Everything the plan is, written down beside what it produced.

    Law 8: a comparison has to record its own conditions. The old file pinned
    only the output, so when the world changed underneath it the file went red
    and could not distinguish "the plan moved" from "you broke the renderer" --
    and the cheapest way to make it green again was to delete the signal.
    """
    return {
        "layouts": list(plan["layouts"]),
        "seed": plan["seed"],
        "per_backend": plan["per_backend"],
        "pairing": plan.get("pairing", "paired"),
        "clean": bool(plan.get("clean", False)),
        # The shape of a metadata line is a *condition*, not an output. Half
        # this fingerprint is metadata hashes, so a schema change makes every
        # line differ while not a pixel moved -- and a check that called that a
        # regression would be teaching people to recapture on red, which is the
        # one thing `compare` exists to avoid.
        "schema": record.SCHEMA_VERSION,
        "rules": rules_fingerprint(plan["layouts"]),
    }


def fingerprint(root: Path) -> dict:
    """Hash every image, every metadata line and every provenance file."""
    images: dict[str, str] = {}
    metadata: dict[str, list[str]] = {}
    provenance: dict[str, str] = {}
    by_backend: dict[str, int] = {}
    by_layout: dict[str, int] = {}

    for backend_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        backend = backend_dir.name
        for image in sorted(backend_dir.glob("*.jpg")):
            images[f"{backend}/{image.name}"] = _sha(image.read_bytes())

        pages = [path for path in record.images(backend_dir)
                 if record.beside(path).exists()]
        if not pages:
            continue
        metadata[backend] = [
            _sha(_normalise(record.beside(path).read_text(encoding="utf-8"))
                 .encode("utf-8")) for path in pages]
        by_backend[backend] = len(pages)

        # The other half of the dataset. A run that produced the same pixels
        # and the same labels from a different recipe would pass on images and
        # metadata alone -- and a run that lost its provenance entirely would
        # pass on both while leaving images nothing can redraw.
        beside = synthesis.beside(backend_dir)
        if beside.exists():
            provenance[backend] = _sha(
                _normalise(beside.read_text(encoding="utf-8")).encode("utf-8"))
        drew = synthesis.read_if_there(backend_dir)
        for path in pages:
            layout = drew.layout(path.relative_to(backend_dir).as_posix())
            by_layout[layout] = by_layout.get(layout, 0) + 1

    summary = root / "dataset.json"
    return {
        "images": images,
        "metadata": metadata,
        "provenance": provenance,
        "counts": {"by_backend": by_backend, "by_layout": by_layout},
        "dataset_json": _sha(
            json.dumps(json.loads(summary.read_text(encoding="utf-8")),
                       sort_keys=True, ensure_ascii=False).encode("utf-8")
        ) if summary.exists() else None,
    }


def arguments(plan: dict) -> list[str]:
    """One plan as the driver's command line."""
    return ["-n", str(plan["per_backend"]), "--seed", str(plan["seed"]),
            "--layouts", *plan["layouts"]]


def generate(plan: dict, out: Path, driver: list[str]) -> None:
    command = [sys.executable, *driver, "-o", str(out), *arguments(plan)]
    result = subprocess.run(command, cwd=REPO_ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout).strip().splitlines()[-15:]
        raise SystemExit("generation failed:\n" + "\n".join(tail))


def capture(driver: list[str]) -> dict:
    """Run every plan into a throwaway directory and fingerprint the result."""
    captured: dict[str, dict] = {}
    for name, plan in PLANS.items():
        workspace = Path(tempfile.mkdtemp(prefix=f"baseline-{name}-"))
        try:
            out = workspace / "dataset"
            print(f"  [{name}] {' '.join(arguments(plan))}")
            generate(plan, out, driver)
            captured[name] = {"inputs": plan_inputs(plan), **fingerprint(out)}
        finally:
            shutil.rmtree(workspace, ignore_errors=True)
    return {
        "plans": captured,
        "normalisation": (
            "each record is json.loads then json.dumps(sort_keys=True, "
            "ensure_ascii=False); no field is excluded"
        ),
    }


def input_changes(want: dict, have: dict) -> list[str]:
    """How the conditions moved, if they did. Empty means same plan, same world."""
    a = want.get("inputs")
    b = have.get("inputs")
    if a is None:
        return ["the baseline predates input pinning, so it cannot say whether "
                "the plan moved or the renderer did — recapture once to fix that"]
    changes: list[str] = []
    if a["layouts"] != b["layouts"]:
        added = [x for x in b["layouts"] if x not in a["layouts"]]
        gone = [x for x in a["layouts"] if x not in b["layouts"]]
        detail = ", ".join(filter(None, [
            f"+{', +'.join(added)}" if added else "",
            f"-{', -'.join(gone)}" if gone else "",
        ])) or "reordered"
        changes.append(f"layouts {len(a['layouts'])} -> {len(b['layouts'])} ({detail})")
    for key in ("seed", "per_backend", "pairing", "clean"):
        if a.get(key) != b.get(key):
            changes.append(f"{key} {a.get(key)!r} -> {b.get(key)!r}")
    if a.get("schema") != b.get("schema"):
        changes.append(f"metadata schema {a.get('schema')!r} -> {b.get('schema')!r}; "
                       f"the labels are written differently, the pixels are not")
    for directory, digest in (b.get("rules") or {}).items():
        if (a.get("rules") or {}).get(directory) != digest:
            changes.append(f"{directory}/ changed")
    for directory in (a.get("rules") or {}):
        if directory not in (b.get("rules") or {}):
            changes.append(f"{directory}/ is no longer fingerprinted")
    return changes


def output_changes(name: str, want: dict, have: dict) -> list[str]:
    """Every difference in what was produced, named precisely enough to act on."""
    problems: list[str] = []
    for key in sorted(set(want["images"]) | set(have["images"])):
        if key not in want["images"]:
            problems.append(f"{name}: {key} is new")
        elif key not in have["images"]:
            problems.append(f"{name}: {key} was not produced")
        elif want["images"][key] != have["images"][key]:
            problems.append(f"{name}: {key} differs")

    for backend in sorted(set(want["metadata"]) | set(have["metadata"])):
        a = want["metadata"].get(backend, [])
        b = have["metadata"].get(backend, [])
        if len(a) != len(b):
            problems.append(
                f"{name}/{backend}: {len(b)} metadata lines, baseline has {len(a)}")
            continue
        differing = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if differing:
            problems.append(f"{name}/{backend}: metadata lines {differing[:8]} differ")

    for backend in sorted(set(want.get("provenance") or {})
                          | set(have.get("provenance") or {})):
        a = (want.get("provenance") or {}).get(backend)
        b = (have.get("provenance") or {}).get(backend)
        if a != b:
            problems.append(
                f"{name}/{backend}: {synthesis.NAME} differs"
                if a and b else
                f"{name}/{backend}: {synthesis.NAME} is "
                f"{'new' if a is None else 'no longer written'}")

    if want["counts"] != have["counts"]:
        problems.append(f"{name}: counts differ\n      baseline {want['counts']}"
                        f"\n      now      {have['counts']}")
    if want.get("dataset_json") != have.get("dataset_json"):
        problems.append(f"{name}: dataset.json differs")
    return problems


def compare(expected: dict, actual: dict) -> tuple[list[str], list[str]]:
    """Two lists, because red means two entirely different things.

    * **the plan moved** -- the layouts, the seed, the count, or the rule-base
      the images are a function of is not what the baseline was taken under.
      The pixels are *expected* to differ and the file needs recapturing.
    * **same plan, different pixels** -- this is the regression the baseline
      exists to catch, and the only one worth waking anyone for.

    Told apart because a baseline that cannot tell them apart teaches people to
    recapture on red, which is the same as deleting the check.
    """
    moved: list[str] = []
    regressed: list[str] = []
    for name in sorted(set(expected["plans"]) | set(actual["plans"])):
        want = expected["plans"].get(name)
        have = actual["plans"].get(name)
        if want is None:
            moved.append(f"{name}: a new plan, not in the baseline")
            continue
        if have is None:
            moved.append(f"{name}: in the baseline but not in this run")
            continue

        changes = input_changes(want, have)
        if changes:
            moved.append(f"{name}: " + "; ".join(changes))
            continue                 # its pixels are not evidence of anything
        regressed += output_changes(name, want, have)
    return moved, regressed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true",
                        help="capture and overwrite the golden file")
    parser.add_argument("--reason", default="",
                        help="why the golden file is being replaced. Required "
                             "with --write, and kept in the file: a comparison "
                             "point that changed without saying why is one "
                             "nobody can argue with later")
    parser.add_argument("--driver", default="tools/generate_dataset.py",
                        help="the generator to fingerprint")
    args = parser.parse_args()

    driver = args.driver.split()
    print(f"baseline via {' '.join(driver)}")
    actual = capture(driver)

    if args.write:
        # The eighth standing law, applied to the golden file itself: it is the
        # comparison point everything else is held to, so it has to carry the
        # conditions it was taken under -- including the reason the previous
        # one stopped being true. Without this, recapturing is the cheap way
        # out of a red baseline and leaves no trace that it was taken.
        if not args.reason.strip():
            raise SystemExit(
                "refusing to overwrite the golden file without --reason.\n"
                "  A recapture is a claim that the old pixels were wrong and "
                "the new ones are right.\n"
                "  Say why, in one sentence; it is kept in the file.\n"
                '  e.g. make baseline-write REASON="glyph pages now reseed '
                'imgaug, so a page is a function of its seed"')
        actual["reason"] = args.reason.strip()
        previous = (json.loads(GOLDEN.read_text(encoding="utf-8"))
                    if GOLDEN.exists() else {})
        if previous.get("reason"):
            actual["replaced"] = previous["reason"]
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(json.dumps(actual, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8")
        total = sum(len(plan["images"]) for plan in actual["plans"].values())
        print(f"\nwrote {GOLDEN.relative_to(REPO_ROOT)}: "
              f"{len(actual['plans'])} plans, {total} images")
        return 0

    if not GOLDEN.exists():
        raise SystemExit(f"no baseline at {GOLDEN}; capture one with --write")
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))
    moved, regressed = compare(expected, actual)

    # Two headings, never one. "The plan changed" is a fact about the
    # repository and asks for `--write`; "same plan, different pixels" is a
    # regression and asks for a diff. Printed under one heading they read the
    # same, and the cheap way out of both is to recapture -- which is exactly
    # how a baseline stops being one.
    if moved:
        print(f"\nKẾ HOẠCH ĐÃ ĐỔI: {len(moved)} — KHÔNG phải hồi quy\n")
        for change in moved:
            print(f"  - {change}")
        print("\n  Ảnh của những kế hoạch này không nói lên điều gì cho tới khi"
              "\n  chụp lại: `make baseline-write`, commit riêng, nêu rõ vì sao.")
    if regressed:
        print(f"\nCÙNG KẾ HOẠCH, KHÁC PIXEL: {len(regressed)} — đây là hồi quy\n")
        for problem in regressed[:40]:
            print(f"  - {problem}")
        if len(regressed) > 40:
            print(f"  ... and {len(regressed) - 40} more")
    if moved or regressed:
        return 1

    total = sum(len(plan["images"]) for plan in actual["plans"].values())
    print(f"\nbaseline khớp: {total} ảnh, {len(actual['plans'])} kế hoạch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
