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
    blanks,  # noqa: E402
    corpus,  # noqa: E402
    load_groups,
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

    # The blank registry: intention against what the tags actually resolve to.
    problems += blanks.problems(rules)

    # Chains and the registry, checked BOTH ways.
    #
    # One way is obvious: a chain may not name a model that does not exist.
    # The other way is the one that kept catching this repository out --
    # `docs/lam-cu-de-xuat.md` is a whole document about capability that was
    # built, paid for and then never reached by any chain. A model no chain
    # names is a model that has never been in a dataset, however good it is.
    #
    # `by_box` is the wrapper, so what IT names counts as reached too:
    # `[by_box, {effect: markup, ...}]` is what puts `markup` on a page.
    try:
        from degradation import names as degradation_names

        known = set(degradation_names())
        drawn: set[str] = set()
        for option in rules["augmentation"]:
            for entry in option.params.get("chain", []) or []:
                is_pair = isinstance(entry, (list, tuple))
                name = entry[0] if is_pair else entry
                drawn.add(name)
                if name not in known:
                    problems.append(
                        f"augmentation/{option.id}: unknown degradation {name!r}; "
                        f"have {', '.join(sorted(known))}"
                    )
                    continue
                if name != "by_box":
                    continue
                wrapped = (entry[1] or {}).get("effect") if is_pair and len(entry) > 1 else None
                if not wrapped:
                    problems.append(
                        f"augmentation/{option.id}: by_box without `effect`; it wraps a "
                        f"model and has nothing to run")
                elif wrapped == "by_box":
                    problems.append(f"augmentation/{option.id}: by_box wraps itself")
                elif wrapped not in known:
                    problems.append(
                        f"augmentation/{option.id}: by_box names unknown effect "
                        f"{wrapped!r}; have {', '.join(sorted(known))}")
                else:
                    drawn.add(wrapped)
        for unused in sorted(known - drawn):
            problems.append(
                f"degradation/{unused}: registered but no chain in rules/augmentation.yaml "
                f"names it, so it never reaches a dataset")
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
                        ) -> tuple[dict[str, Counter], dict[str, Counter], int]:
    """Draw `draws` recipes and count what came out.

    Returns (counts by value, counts by parent node, failures).

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
    families = {attribute: Counter() for attribute in ATTRIBUTES}
    failures = 0
    for index in range(draws):
        try:
            recipe = sample_recipe(seed=seed + index, rules=rules, force=force)
        except Exception:  # noqa: BLE001 - counted, and reported by the caller
            failures += 1
            continue
        for attribute, option in recipe.choices.items():
            counters[attribute][option.id] += 1
            if option.group:
                families[attribute][option.group] += 1
    return counters, families, failures


def distribution(draws: int, seed: int) -> None:
    counters, families, failures = sample_distribution(draws, seed)
    groups = load_groups()
    total = draws - failures
    print(f"{total} lần bốc thành công / {draws}\n")
    for attribute in ATTRIBUTES:
        print(f"[{attribute}]")
        # An attribute sorted into parent nodes is reported by node first. A
        # weight is relative to the candidates left after filtering, so a
        # family of five rare layouts and a family of one common one can read
        # identically value by value and be nothing alike as a mix.
        labels = {group.id: group.label for group in groups.get(attribute, [])}
        for name, count in families[attribute].most_common():
            share = count / total if total else 0
            print(f"  ({name}) {labels.get(name, '')}".rstrip())
            print(f"  {'':<28} {count:>5}  {share:>6.1%}")
        if families[attribute]:
            print()
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
    parser.add_argument("--blanks", action="store_true")
    parser.add_argument("-n", "--draws", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    if not (args.check or args.distribution or args.corpus or args.blanks):
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
            # Profiles are discovered, not listed: `rulebase/README.md` promises
            # that adding one is three text files and nothing else, and a
            # hard-coded pair here quietly left every profile added since off
            # the report while `corpus.check()` was validating them.
            for lang in corpus.languages():
                counts = {}
                for path in sorted((corpus.CORPUS_ROOT / lang).glob("items_*.txt")):
                    profile = path.stem[len("items_"):]
                    counts[profile] = len(corpus.items(profile, lang))
                shared = {
                    "streets": len(corpus.streets(lang)),
                    "wards": len(corpus.wards(lang)),
                    "payments": len(corpus.payments(lang)),
                    "people": len(corpus.people(lang)),
                }
                print(f"\ncorpus {lang}/ hợp lệ: "
                      + ", ".join(f"{k}={v}" for k, v in {**counts, **shared}.items()))

    if args.blanks:
        registry, documents = blanks.load_blanks()
        by_tags = blanks.resolved(load_rules())
        print("\nPHÔI GỐC theo từng loại document\n")
        for name, members in documents.items():
            print(f"  {name}  ({len(members)} phôi)")
            for member in members:
                blank = registry.get(member)
                if blank is None:
                    print(f"      {member:24} KHÔNG KHAI BÁO")
                    continue
                mark = "->" if blank.converted else "  chưa chuyển:"
                sheet = f"  [{blank.sheet}]" if blank.sheet else ""
                print(f"      {member:24} {mark} {blank.layout or ''}{sheet}")
                print(f"        {blank.source}")
            drift = by_tags[name] - {registry[m].layout for m in members
                                     if m in registry and registry[m].converted}
            if drift:
                print(f"      LỆCH: tag còn cho phép {', '.join(sorted(drift))}")
            print()
        total = len(registry)
        drawn = sum(1 for b in registry.values() if b.converted)
        print(f"  {total} phôi, {drawn} đã chuyển thành bố cục, "
              f"{sum(1 for b in registry.values() if b.sheet)} có tờ mẫu phát hành được")

    if args.distribution:
        print()
        distribution(args.draws, args.seed)

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
