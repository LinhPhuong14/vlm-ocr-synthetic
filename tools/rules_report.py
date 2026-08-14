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
        if paper and paper != "auto" and paper not in papers:
            problems.append(
                f"visual/{option.id}: paper {paper!r} not in textures/paper "
                f"({', '.join(sorted(papers)) or 'empty -- run `make textures`'})"
            )
    return problems


def distribution(draws: int, seed: int) -> None:
    counters = {attribute: Counter() for attribute in ATTRIBUTES}
    failures = 0
    for index in range(draws):
        try:
            recipe = sample_recipe(seed=seed + index)
        except Exception:
            failures += 1
            continue
        for attribute, option in recipe.choices.items():
            counters[attribute][option.id] += 1

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
                "items_quan": len(corpus.items("quan")),
                "items_sieuthi": len(corpus.items("sieuthi")),
                "shops_quan": len(corpus.shops("quan")),
                "shops_sieuthi": len(corpus.shops("sieuthi")),
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
