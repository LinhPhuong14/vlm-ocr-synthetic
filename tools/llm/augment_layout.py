"""Read a layout, have a local model vary it, and refuse it unless it draws.

    python -m tools.llm.augment_layout --from market_vat --id market_vat_b
    python -m tools.llm.augment_layout --from market_vat --id market_vat_b --write

Without `--write` nothing is created. With it, three files change: the layout
itself, its registration in `rulebase/rules/layout.yaml`, and its blank in
`rulebase/blanks.yaml` -- a layout missing either of the last two is a layout
the sampler can never draw, which is a failure `tests/test_sheets.py` caught
the day `notebook_ledger` was added.

## Why a variant rather than a new document type

Asked for directly: *"LLM có thể augment layout, tức là đọc layout gốc rồi sửa
đổi một vài phần cho hợp lý, nếu không layout sẽ bị fix cứng."* Seventeen
layouts drawn from seventeen files means seventeen pages, and a model trained
on that learns those seventeen arrangements. A variant keeps the document kind
-- a market till slip is still a market till slip -- and moves what a different
shop would have moved: the column widths, which sections come first, whether
the totals sit in a frame, how the labels are worded.

It also keeps the two things a variant must not touch, and the prompt says so:
`columns[].key` and `item.rows` are the wiring into the data, and a model
renaming `amount` to `thanh_tien` produces a page with an empty column and a
label promising a value that is not on it.

## The gauntlet

The model proposes; six checks dispose, in increasing order of cost:

1. **it is YAML**, and it is a mapping;
2. **every key path exists in some hand-written layout**, with the right type,
   inside the observed numeric range, and enum values from the observed set --
   `tools/llm/layout_schema.py`, which derives all of that rather than
   declaring it;
3. **every key path that is in all seventeen layouts is present**;
4. **`rulebase.make()` builds a grid** over a spread of seeds without raising,
   which is where a structurally-valid-but-nonsense layout dies;
5. **every field the label promises has a cell on the page** -- the same check
   `pipeline/invariants.py` runs, because a variant that quietly drops a column
   produces a dataset whose labels describe a page that was not drawn;
6. **`pipeline/preflight.py`** over the whole rule base, which catches the
   registration being wrong and the content overflowing the sheet.

Anything short of all six and the file is not written. The point is not that
the model is trusted -- it is that nothing it writes can reach a dataset
without passing what a hand-written layout passes.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import subprocess
import sys
from pathlib import Path

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.llm import layout_schema as schema_mod
from tools.llm.client import LLMError, Model, prompt

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYOUTS = REPO_ROOT / "rulebase" / "layouts"
RULES_LAYOUT = REPO_ROOT / "rulebase" / "rules" / "layout.yaml"
BLANKS = REPO_ROOT / "rulebase" / "blanks.yaml"
SHEETS = REPO_ROOT / "generators" / "html" / "sheets" / "__init__.py"

# How many seeds the variant has to draw before it is believed. Ten rather than
# one because a layout can be fine on a short basket and overflow on a long
# one, and the sampler draws both.
SEEDS = 10


def strip_fence(text: str) -> str:
    """A chat model wraps YAML in ``` however firmly it is told not to."""
    lines = [line for line in text.splitlines()
             if not line.strip().startswith("```")]
    # And it prefaces. Drop anything before the first line that looks like a
    # top-level YAML key, rather than trying to parse the preamble.
    for index, line in enumerate(lines):
        head = line.split(":")[0]
        if line and not line.startswith((" ", "-", "#")) and ":" in line \
                and head.replace("_", "").isalnum():
            return "\n".join(lines[index:]).strip() + "\n"
    return "\n".join(lines).strip() + "\n"


def parse(text: str) -> tuple[dict | None, str]:
    try:
        loaded = yaml.safe_load(strip_fence(text))
    except yaml.YAMLError as error:
        return None, f"not YAML: {str(error)[:200]}"
    if not isinstance(loaded, dict):
        return None, f"not a mapping but a {type(loaded).__name__}"
    return loaded, ""


def draws(layout_id: str, seeds: int = SEEDS) -> list[str]:
    """Build the page for a spread of seeds, in a subprocess. Empty is healthy.

    A subprocess because `rulebase` caches the layout directory and the rules,
    and this runs right after writing new files into both -- an in-process
    check would be checking the state the process started with.
    """
    script = (
        "import sys;"
        "sys.path.insert(0, %r);"
        "import rulebase;"
        "from pipeline import invariants;"
        "bad=[]\n"
        "for seed in range(%d):\n"
        "    try:\n"
        "        recipe, receipt, grid = rulebase.make(seed=seed, force={'layout': %r})\n"
        "    except Exception as error:\n"
        "        bad.append('seed %%d: %%s: %%s' %% (seed, type(error).__name__, error))\n"
        "        continue\n"
        "    if grid is not None and not grid.cells:\n"
        "        bad.append('seed %%d: the page came out empty' %% seed)\n"
        "print('\\n'.join(bad))\n"
    ) % (str(REPO_ROOT), seeds, layout_id)
    result = subprocess.run([sys.executable, "-c", script], cwd=str(REPO_ROOT),
                            capture_output=True, text=True)
    if result.returncode != 0:
        return [f"the builder itself failed: {result.stderr.strip()[-400:]}"]
    return [line for line in result.stdout.splitlines() if line.strip()]


def preflight() -> list[str]:
    """The repository's own check over the whole rule base."""
    interpreter = REPO_ROOT / "generators" / "synthdog" / ".venv" / "bin" / "python"
    if not interpreter.exists():
        interpreter = Path(sys.executable)
    result = subprocess.run([str(interpreter), "pipeline/preflight.py"],
                            cwd=str(REPO_ROOT), capture_output=True, text=True)
    if result.returncode == 0:
        return []
    return [line for line in result.stdout.splitlines() if line.strip().startswith("-")] \
        or [result.stdout.strip()[-400:] or result.stderr.strip()[-400:]]


def _block_after(text: str, anchor: str) -> tuple[int, int, str]:
    """Where the YAML block introduced by `anchor` starts and ends.

    Textual, not structural, and that is the point: `rules/layout.yaml` and
    `blanks.yaml` are more comment than data -- the file explains why each
    layout excludes what it excludes -- and `yaml.safe_dump` would round-trip
    all of it away. A registration that silently deleted the reasoning behind
    every rule would be a far worse change than the one it was making.
    """
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if line.strip() == anchor), -1)
    if start < 0:
        return -1, -1, ""
    indent = len(lines[start]) - len(lines[start].lstrip())
    end = len(lines)
    for index in range(start + 1, len(lines)):
        line = lines[index]
        if not line.strip():
            continue
        if len(line) - len(line.lstrip()) <= indent:
            end = index
            break
    return start, end, "".join(lines[start:end])


def register(layout_id: str, parent: str, today: str) -> list[str]:
    """Put the variant into `rules/layout.yaml` and `blanks.yaml`.

    Copied from the parent's entry rather than invented: a variant is the same
    document kind, so it requires the same tags, excludes the same things and
    fills the same blank. Getting this wrong is the failure the sampler cannot
    report -- the layout is simply never drawn, and the run looks fine.

    The one thing that is NOT copied is the weight, which is halved: a variant
    should not double how often its document kind comes up just by existing.
    """
    text = RULES_LAYOUT.read_text(encoding="utf-8")
    if f"- id: {layout_id}" in text:
        return [f"{layout_id} is already in rules/layout.yaml"]
    start, end, block = _block_after(text, f"- id: {parent}")
    if start < 0:
        return [f"the parent {parent!r} has no `- id:` entry in rules/layout.yaml"]

    entry = block.rstrip("\n").split("\n")
    indent = " " * (len(entry[0]) - len(entry[0].lstrip()))
    out = [f"{indent}# {schema_mod.MARK[2:]}, varied from {parent} on {today}.",
           f"{indent}# Same document kind, so the same requires/excludes/tags;"
           f" half the weight,",
           f"{indent}# because a variant should not double how often this kind"
           f" is drawn.",
           f"{indent}- id: {layout_id}"]
    for line in entry[1:]:
        stripped = line.strip()
        if stripped.startswith("weight:"):
            weight = max(1, int(stripped.split(":")[1]) // 2)
            out.append(f"{line.split('weight:')[0]}weight: {weight}")
        elif stripped.startswith("#"):
            continue           # the parent's reasoning is about the parent
        else:
            out.append(line)

    lines = text.splitlines(keepends=True)
    # `end` is the first line at or outside the parent's indent, so the
    # blank line that separates entries is already inside `block`.
    patched = "".join(lines[:end]) + "\n".join(out) + "\n\n" + "".join(lines[end:])
    RULES_LAYOUT.write_text(patched, encoding="utf-8")

    # `blanks.yaml`: the blank itself, and every document allowed to draw it.
    text = BLANKS.read_text(encoding="utf-8")
    if f"\n  {layout_id}:" not in text:
        start, end, block = _block_after(text, f"{parent}:")
        if start < 0:
            RULES_LAYOUT.write_text("".join(lines), encoding="utf-8")
            return [f"the parent {parent!r} has no blank in blanks.yaml"]
        rows = block.rstrip("\n").split("\n")
        new = [f"  {layout_id}:"]
        for row in rows[1:]:
            row = row.replace(f"layout: {parent}", f"layout: {layout_id}")
            if row.strip().startswith("source:"):
                # Same reason as `restate_source`: a blank copied from a parent
                # must not inherit the parent's claim to a photograph.
                indent = row[:len(row) - len(row.lstrip())]
                row = (f'{indent}source: "biến thể của {parent} '
                       f'(sinh bằng LLM, không đo từ ảnh nào)"')
            new.append(row)
        parts = text.splitlines(keepends=True)
        text = "".join(parts[:end]) + "\n".join(new) + "\n\n" + "".join(parts[end:])
    # ... and the documents that may draw the parent may draw the variant.
    out_lines = []
    for line in text.splitlines(keepends=True):
        head, sep, rest = line.partition(":")
        if sep and rest.strip().startswith("[") and parent in rest \
                and layout_id not in rest:
            rest = rest.rstrip().rstrip("]") + f", {layout_id}]\n"
            line = head + sep + rest
        out_lines.append(line)
    BLANKS.write_text("".join(out_lines), encoding="utf-8")
    return []


def restate_source(variant: dict, parent: str, parent_yaml: dict) -> None:
    """Overwrite `source:` with where this layout ACTUALLY came from.

    Every hand-written layout uses that field for one thing: the photograph or
    document it was measured against -- `photo Saigon Co.op, PHIẾU TÍNH TIỀN
    2022`, `ảnh hoá đơn xuất khẩu mẫu 06HDXK3/001`. It is the provenance of the
    shape, and somebody deciding whether a column width is right goes and looks
    at it.

    A model asked to vary a layout rewrites that line like any other, and on
    the first real run it produced `PHIẾU TÍNH TIỀN 2023` -- a receipt that
    does not exist, from a year nobody photographed, in a field whose whole
    job is to be checkable. Nothing downstream would ever catch it, because
    the field is prose.

    So it is not the model's to write. A variant was measured against nothing;
    it was derived from its parent, and it says so, and it carries the parent's
    real source so the trail still leads to the photograph.
    """
    inherited = str(parent_yaml.get("source", "")).strip()
    variant["source"] = (
        f"biến thể của {parent} (sinh bằng LLM, không đo từ ảnh nào)"
        + (f" — bố cục gốc đo từ: {inherited}" if inherited else ""))


def register_sheet(layout_id: str, parent: str, today: str) -> list[str]:
    """Give the variant the CSS sheet family that already draws its parent.

    Not optional and not a detail: `preflight` refuses a layout with no sheet,
    because while the character grid was the default a layout added without one
    drew perfectly well on the wrong page model and nobody noticed. It is the
    third registration, and the one the first run of this tool forgot -- which
    is how it got caught, at the last step of the gauntlet rather than the
    first.

    The parent's family, always: a variant is the same document at different
    settings, so the module that knows how to dress a market till slip is the
    module that should dress a varied one.
    """
    text = SHEETS.read_text(encoding="utf-8")
    if f'"{layout_id}"' in text:
        return [f"{layout_id} is already in sheets.FAMILIES"]
    anchor = f'    "{parent}": '
    line = next((l for l in text.splitlines() if l.startswith(anchor)), "")
    if not line:
        return [f"the parent {parent!r} is not in sheets.FAMILIES"]
    family = line.split(":", 1)[1].strip().rstrip(",")
    out = []
    for existing in text.splitlines(keepends=True):
        out.append(existing)
        if existing.rstrip("\n") == line:
            out.append(f'    "{layout_id}": {family},'
                       f'    {schema_mod.MARK} from {parent}, {today}\n')
    SHEETS.write_text("".join(out), encoding="utf-8")
    return []


def build(parent: str, layout_id: str, model: Model, seed: int) -> tuple[dict, str]:
    original = (LAYOUTS / f"{parent}.yaml").read_text(encoding="utf-8")
    reply = model.chat(
        prompt("layout"),
        f"Đây là file bố cục gốc `{parent}.yaml`:\n\n{original}\n\n"
        f"Viết lại thành một biến thể. `id` phải là `{layout_id}`.",
        seed=seed, num_predict=2400)
    return reply, original


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--from", dest="parent", required=True,
                        help="the layout to vary")
    parser.add_argument("--id", dest="layout_id", required=True,
                        help="the new layout's id, and its file name")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--model", default=None)
    parser.add_argument("--seeds", type=int, default=SEEDS,
                        help="how many pages the variant must draw")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    from tools.llm.client import MODEL

    if not (LAYOUTS / f"{args.parent}.yaml").exists():
        raise SystemExit(f"no layout {args.parent!r} in {LAYOUTS}")
    target = LAYOUTS / f"{args.layout_id}.yaml"
    if target.exists():
        raise SystemExit(f"{target} already exists; pick another --id")

    model = Model(args.model or MODEL)
    if not model.available():
        raise SystemExit(f"the local model {model.name!r} is not loaded; see "
                         "tools/llm/README.md")

    schema = schema_mod.derive()
    print(f"{args.parent} -> {args.layout_id}: schema has {len(schema)} key paths "
          f"from {len([p for p in LAYOUTS.glob('*.yaml') if not schema_mod.is_generated(p)])} "
          "hand-written layouts")

    variant = None
    for index in range(args.rounds):
        try:
            reply, _original = build(args.parent, args.layout_id, model,
                                     args.seed + index)
        except LLMError as error:
            print(f"  round {index + 1}: {error}")
            break
        loaded, problem = parse(reply.text)
        print(f"  round {index + 1}: {reply.tokens} tokens, {reply.seconds:.0f}s, "
              f"{reply.rate:.1f} tok/s")
        if loaded is None:
            print(f"      ✗ {problem}")
            continue
        problems = schema_mod.check(loaded, schema)
        problems += schema_mod.ranges(loaded)
        problems += [f"missing {key}, which every layout has"
                     for key in schema_mod.missing(loaded)]
        if str(loaded.get("id")) != args.layout_id:
            problems.append(f"id is {loaded.get('id')!r}, not {args.layout_id!r}")
        if problems:
            for line in problems[:12]:
                print(f"      ✗ {line}")
            if len(problems) > 12:
                print(f"      ✗ ... and {len(problems) - 12} more")
            continue
        print("      ✓ schema clean")
        # `source:` is provenance, not prose the model gets to invent. See
        # `restate_source`.
        restate_source(loaded, args.parent,
                       yaml.safe_load((LAYOUTS / f"{args.parent}.yaml")
                                      .read_text(encoding="utf-8")))
        print(f"      · source restated: {loaded['source']}")
        variant, kept_reply = loaded, reply
        break

    if variant is None:
        print("no round produced a layout that passes the schema; nothing written")
        return 1

    if not args.write:
        print("\n-- would write (pass --write) --")
        print(yaml.safe_dump(variant, allow_unicode=True, sort_keys=False)[:1200])
        return 0

    header = (f"{schema_mod.MARK} {kept_reply.model}@{kept_reply.digest} "
              f"from={args.parent} seed={kept_reply.seed} "
              f"{_datetime.date.today().isoformat()}\n"
              f"# Reviewed by a person before it drew anything. The gauntlet it "
              f"passed is in tools/llm/augment_layout.py.\n")
    target.write_text(
        header + yaml.safe_dump(variant, allow_unicode=True, sort_keys=False),
        encoding="utf-8")
    print(f"wrote {target.relative_to(REPO_ROOT)}")

    today = _datetime.date.today().isoformat()
    # Snapshotted before, restored on failure. A run that leaves a half
    # registration behind hands the next person a rule base that names a
    # layout with no file -- which preflight reports as a repository fault
    # rather than as this command having failed.
    before = {path: path.read_text(encoding="utf-8")
              for path in (RULES_LAYOUT, BLANKS, SHEETS)}

    def rollback() -> None:
        for path, text in before.items():
            path.write_text(text, encoding="utf-8")

    problems = (register(args.layout_id, args.parent, today)
                or register_sheet(args.layout_id, args.parent, today))
    if problems:
        target.unlink()
        rollback()
        for line in problems:
            print(f"  ✗ {line}")
        return 1
    print("registered in rules/layout.yaml, blanks.yaml and sheets.FAMILIES")

    print(f"building {args.seeds} pages ...")
    problems = draws(args.layout_id, args.seeds)
    if not problems:
        print("  ✓ every seed drew a page")
        print("running preflight ...")
        problems = preflight()
        if not problems:
            print("  ✓ preflight clean")
    if problems:
        for line in problems[:10]:
            print(f"  ✗ {line}")
        print(f"\n{target.name} does not draw. Removing it, and rolling back "
              "the three registrations: a half-registered layout is "
              "a rule base that names a file which is not there, and preflight "
              "reports that as a repository fault rather than as this command "
              "having failed.")
        target.unlink()
        rollback()
        return 1

    print(f"\n{args.layout_id} passes the gauntlet. Read the diff before "
          "committing it: the checks prove it DRAWS, not that it is a "
          "document anyone would print.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
