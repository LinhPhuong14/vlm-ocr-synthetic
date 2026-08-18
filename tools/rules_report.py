"""Check the rules, and show what they actually produce.

    python tools/rules_report.py --check          # unreachable values, bad tags
    python tools/rules_report.py --distribution   # what 2000 draws look like
    python tools/rules_report.py --corpus         # missing or malformed corpus

The distribution matters because a weight is relative to *the candidates still
standing after filtering*, not an absolute probability. Raise the weight on a
value that `requires` a rare tag and almost nothing changes; the only way to
know what the mix really is, is to draw it.
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rulebase import (  # noqa: E402
    ATTRIBUTES,
    available_layouts,
    corpus,  # noqa: E402
    load_rules,
    sample_recipe,
    validate,
)
from rulebase.layout import LAYOUTS_ROOT  # noqa: E402


def check() -> list[str]:
    problems = validate()

    # Every bố cục named in the rules must have a file, and vice versa.
    rules = load_rules()
    declared = {option.id for option in rules["layout"]}
    on_disk = set(available_layouts())
    for missing in sorted(declared - on_disk):
        problems.append(f"layout/{missing}: declared in rules but no {LAYOUTS_ROOT}/{missing}.yaml")
    for orphan in sorted(on_disk - declared):
        problems.append(f"layouts/{orphan}.yaml: on disk but not declared in rules/layout.yaml")

    # Chains may only name degradations that exist.
    try:
        from degradation import names as degradation_names

        known = set(degradation_names())
        for option in rules["augmentation"]:
            for entry in option.params.get("chain", []) or []:
                name = entry[0] if isinstance(entry, (list, tuple)) else entry
                if name not in known:
                    problems.append(
                        f"augmentation/{option.id}: unknown degradation {name!r}; "
                        f"have {', '.join(sorted(known))}"
                    )
    except ImportError:
        problems.append("degradation not importable (needs numpy and opencv); chains unchecked")

    # A paper named by a visual value must exist, or the sheet silently falls
    # back to a generated one and the recipe stops describing the image.
    papers = {p.stem for p in (Path(__file__).resolve().parent.parent / "textures" / "paper")
              .glob("*.jpg")}
    for option in rules["visual"]:
        paper = option.params.get("paper")
        # `paper` is one sheet or a shortlist; every entry has to exist, since
        # a shortlist that is wrong in one place fails only on the seeds that
        # happen to draw that entry.
        wanted = paper if isinstance(paper, list) else [paper]
        for sheet in wanted:
            if sheet and sheet != "auto" and sheet not in papers:
                problems.append(
                    f"visual/{option.id}: paper {sheet!r} not in textures/paper "
                    f"({', '.join(sorted(papers)) or 'empty -- run `make textures`'})"
                )

    # A sheet nobody can draw is dead weight in the repository, and the usual
    # cause is a rename that missed one rule.
    used = set()
    for option in rules["visual"]:
        paper = option.params.get("paper")
        used.update(paper if isinstance(paper, list) else [paper])
    if "auto" not in used:
        for orphan in sorted(papers - used):
            problems.append(
                f"textures/paper/{orphan}.jpg: no visual value names it"
            )

    overlays = Path(__file__).resolve().parent.parent / "augmentations" / "data" / "image"
    chains = [
        name
        for option in rules["augmentation"]
        for name, _ in _chain_entries(option.params.get("chain") or [])
    ]
    if "paper_overlay" in chains and not list(overlays.glob("*.jpg")):
        problems.append(
            f"augmentation: a chain uses paper_overlay but {overlays} has no images; "
            "the step would silently do nothing"
        )
    return problems


def _chain_entries(chain):
    """(name, options) for each chain entry, in either YAML shape."""
    for entry in chain:
        if isinstance(entry, (list, tuple)):
            yield entry[0], (entry[1] if len(entry) > 1 else {})
        elif isinstance(entry, dict):
            yield from entry.items()
        else:
            yield str(entry), {}


def sample_distribution(draws: int, seed: int, rules=None,
                        force: dict[str, str] | None = None
                        ) -> tuple[dict[str, Counter], int]:
    """Draw `draws` recipes and count what came out. Returns (counts, failures).

    Split out from `distribution` so `pipeline/drift.py` can ask the same
    question without going through a printed report. `force` is here because a
    plan that pins the layout does not have the rule-base's layout mix, and
    comparing a run against an expectation that ignores its own pins would
    report drift on every run forever.
    """
    # Once, not once per draw. `sample_recipe(rules=None)` re-reads every YAML
    # file every time it is called, so leaving it to default here costs a full
    # parse of the rule-base per draw -- two thousand of them for one report.
    rules = load_rules() if rules is None else rules
    counters = {attribute: Counter() for attribute in ATTRIBUTES}
    failures = 0
    for index in range(draws):
        try:
            recipe = sample_recipe(seed=seed + index, rules=rules, force=force)
        except Exception:  # noqa: BLE001 - counted, and reported by the caller
            failures += 1
            continue
        for attribute, option in recipe.choices.items():
            counters[attribute][option.id] += 1
    return counters, failures


def distribution(draws: int, seed: int) -> None:
    counters, failures = sample_distribution(draws, seed)
    total = draws - failures
    print(f"{total} lần bốc thành công / {draws}\n")
    for attribute in ATTRIBUTES:
        print(f"[{attribute}]")
        for name, count in counters[attribute].most_common():
            share = count / total if total else 0
            bar = "#" * int(share * 40)
            print(f"  {name:<28} {count:>5}  {share:>6.1%} {bar}")
        print()
    if failures:
        print(f"CẢNH BÁO: {failures} lần bốc thất bại — luật có tổ hợp không giải được")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--distribution", action="store_true")
    parser.add_argument("--corpus", action="store_true")
    parser.add_argument("-n", "--draws", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if not (args.check or args.distribution or args.corpus):
        args.check = True

    failed = False
    if args.check:
        problems = check()
        if problems:
            failed = True
            print("LUẬT CÓ VẤN ĐỀ:")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print("luật hợp lệ: mọi giá trị đều bốc được, mọi tham chiếu đều tồn tại")

    if args.corpus:
        problems = corpus.check()
        if problems:
            failed = True
            print("\nCORPUS CÓ VẤN ĐỀ:")
            for problem in problems:
                print(f"  - {problem}")
        else:
            counts = {
                "items_eatery": len(corpus.items("eatery")),
                "items_market": len(corpus.items("market")),
                "shops_eatery": len(corpus.shops("eatery")),
                "shops_market": len(corpus.shops("market")),
                "streets": len(corpus.streets()),
                "wards": len(corpus.wards()),
                "payments": len(corpus.payments()),
            }
            print("\ncorpus hợp lệ: " + ", ".join(f"{k}={v}" for k, v in counts.items()))

    if args.distribution:
        print()
        distribution(args.draws, args.seed)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
