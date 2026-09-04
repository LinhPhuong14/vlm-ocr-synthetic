"""Grow a corpus file with a local model, one validated block at a time.

    python -m agent.augment_content --file items_market --want 20
    python -m agent.augment_content --file items_market --want 20 --write

Without `--write` it prints what it would add and what it threw away, and
touches nothing. That is the default on purpose: the model is a proposer, and
the interesting output of a run is usually the rejection list.

## Why the corpus is worth growing at all

`rulebase/corpus/vi/` is 828 lines. Every page the engine has ever drawn takes
its shop names, its item names and its addresses from those lines, so the
dataset repeats them -- a model trained on it learns `Nho đỏ không hạt Mỹ` as a
thing rather than learning to read Vietnamese product names. Layout variety was
solved by adding layouts; text variety has to be solved by adding text.

## The shape of a round

Ask for more than is wanted, validate hard, keep what survives, repeat until
there is enough or the model stops producing anything new:

    ask ── lines_of ── sift ─┬─ kept  ──► block, stamped
                             └─ rejected ──► printed, with the reason

Two lines of defence, and they are different in kind. `corpus_rules` is
mechanical -- shape, charset, bounds, duplicates -- and catches the model
answering in English, inventing a 200-character name, or handing back a price
with a dot in it. What it cannot catch is a plausible line that is simply not
true: `Dầu-tahini` is well-formed Vietnamese and is not a thing a tạp hoá
sells. That is what the provenance stamp and the review of the diff are for,
and it is why `--write` does not commit.

## Cost

A 7B at 4-bit on a CPU writes about five tokens a second, so a round of twenty
item lines is two to three minutes and most of a corpus file is an afternoon.
Progress is printed per round for that reason.
"""

from __future__ import annotations

import argparse
import datetime as _datetime
import hashlib
import sys
from pathlib import Path

if __package__ in (None, ""):                       # `python augment_content.py`
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent import corpus_rules as rules
from agent.ollama import LLMError, Model, lines_of, prompt, retab
from agent.provenance import Stamp, human

CORPUS_VI = rules.CORPUS_ROOT / "vi"

# Which prompt a family is asked with. `items` and `catalogue` carry a price
# band; everything else is one value a line.
PROMPTS = {"items": "items", "catalogue": "items"}
DEFAULT_PROMPT = "plain"

# What to call the family in Vietnamese when asking. A prompt that says
# "liệt kê shops_market" gets shop-shaped nonsense; one that says "siêu thị và
# cửa hàng tiện lợi" gets shops.
SUBJECTS = {
    "items_market": "mặt hàng bán ở siêu thị hoặc cửa hàng tiện lợi Việt Nam",
    "items_eatery": "món ăn và đồ uống trong thực đơn quán ăn Việt Nam",
    "items_bakery": "bánh và đồ uống bán ở tiệm bánh Việt Nam",
    "items_hotel": "dịch vụ khách sạn ghi trên hoá đơn phòng",
    "shops_market": "tên siêu thị hoặc chuỗi cửa hàng tiện lợi ở Việt Nam",
    "shops_eatery": "tên quán ăn, nhà hàng ở Việt Nam",
    "shops_bakery": "tên tiệm bánh ở Việt Nam",
    "people": "họ và tên đầy đủ của người Việt Nam",
    "streets": "tên đường phố ở Việt Nam",
    "wards": "phường, quận và thành phố ở Việt Nam",
}


def subject_for(stem: str) -> str:
    if stem in SUBJECTS:
        return SUBJECTS[stem]
    raise SystemExit(
        f"no Vietnamese description for {stem!r}. Add one to SUBJECTS in "
        f"{Path(__file__).name}: asking the model for '{stem}' by its file name "
        "gets file-name-shaped nonsense back.\nHave: "
        + ", ".join(sorted(SUBJECTS)))


def ask(model: Model, stem: str, want: int, existing: list[str], seed: int):
    """One round. Returns the reply, so the caller can stamp what it keeps."""
    family = rules.family_of(stem)
    system = prompt(PROMPTS.get(family, DEFAULT_PROMPT))
    # The existing lines go in the ask, not to be copied but to be avoided --
    # and they double as the format example, which a small model follows far
    # better than it follows a description of a format.
    sample = "\n".join(existing[:40])
    user = (f"Liệt kê {want} {subject_for(stem)}.\n\n"
            f"Đây là những dòng đã có. KHÔNG lặp lại chúng, và viết đúng định "
            f"dạng này:\n\n{sample}\n")
    return model.chat(system, user, seed=seed,
                      num_predict=max(200, want * 40))


def block_for(reply, stem: str, kept: list[str], today: str) -> str:
    digest = hashlib.sha256(
        prompt(PROMPTS.get(rules.family_of(stem), DEFAULT_PROMPT)).encode("utf-8")
    ).hexdigest()[:4]
    stamp = Stamp(model=reply.model, digest=reply.digest,
                  prompt=f"{PROMPTS.get(rules.family_of(stem), DEFAULT_PROMPT)}:{digest}",
                  seed=reply.seed, date=today)
    return stamp.block(kept)


def run(stem: str, want: int, *, rounds: int, seed: int, write: bool,
        model_name: str, today: str) -> int:
    path = CORPUS_VI / f"{stem}.txt"
    if not path.exists():
        raise SystemExit(f"no corpus file at {path}")
    shape = rules.shape_of(stem)
    text = path.read_text(encoding="utf-8")
    existing = rules.rows_of(path)
    by_hand = human(text)
    # Measured off THIS file, and off its human lines only -- see
    # `corpus_rules.Envelope`. A round checked against the previous round's
    # output would ratify its own drift.
    sizes = rules.envelopes(text)

    model = Model(model_name)
    if not model.available():
        raise SystemExit(
            f"the local model {model_name!r} is not loaded.\n"
            "  ollama serve &\n"
            f"  ollama pull {model_name}")

    first = sizes.get(0, rules.FALLBACK)
    print(f"{stem}: {len(existing)} lines ({len(by_hand)} written by hand), "
          f"{shape.columns} columns, names {first.words[0]}-{first.words[1]} words "
          f"over {first.sampled} human samples; want {want} more")

    kept_all: list[str] = []
    pool = list(existing)
    for index in range(rounds):
        if len(kept_all) >= want:
            break
        try:
            reply = ask(model, stem, want - len(kept_all) + 5, pool, seed + index)
        except LLMError as error:
            print(f"  round {index + 1}: {error}")
            break
        # The model reproduces the columns and loses the tab about half
        # the time; `retab` puts it back where that is unambiguous.
        wide = max(shape.columns)
        candidates = [retab(line, wide) for line in lines_of(reply.text)]
        if rules.foreign_batch(candidates):
            print(f"  round {index + 1}: the whole batch has no Vietnamese mark "
                  "in it -- the model answered in the wrong language; skipped")
            continue
        kept, thrown = rules.sift(candidates, pool + kept_all, shape, sizes)
        kept_all += kept
        pool += kept
        print(f"  round {index + 1}: {len(candidates)} proposed, {len(kept)} kept, "
              f"{len(thrown)} rejected  ({reply.seconds:.0f}s, "
              f"{reply.rate:.1f} tok/s)")
        for item in thrown:
            print(f"      ✗ {item.line[:58]:<58}  {item.why}")
        for line in kept:
            print(f"      ✓ {line}")

    if not kept_all:
        print("nothing survived; the corpus is unchanged either way")
        return 1

    block = block_for(reply, stem, kept_all[:want], today)
    if not write:
        print(f"\n-- would append to {path} (pass --write) --\n{block}")
        return 0

    with open(path, "a", encoding="utf-8") as handle:
        if not text.endswith("\n"):
            handle.write("\n")
        handle.write(block)
    print(f"\nappended {len(kept_all[:want])} lines to {path}")

    total, thrown = rules.audit()
    print(f"audit after writing: {len(thrown)} rejected of {total}")
    return 1 if thrown else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__.split("\n\n")[0],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", required=True, metavar="STEM",
                        help="corpus file stem, e.g. items_market")
    parser.add_argument("--want", type=int, default=20, help="lines to keep")
    parser.add_argument("--rounds", type=int, default=4,
                        help="give up after this many asks")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--model", default=None, help="ollama tag")
    parser.add_argument("--write", action="store_true",
                        help="append to the corpus; without it, print only")
    parser.add_argument("--date", default=None,
                        help="the day to stamp; defaults to today")
    args = parser.parse_args()

    from agent.ollama import MODEL

    return run(args.file, args.want, rounds=args.rounds, seed=args.seed,
               write=args.write, model_name=args.model or MODEL,
               today=args.date or _datetime.date.today().isoformat())


if __name__ == "__main__":
    raise SystemExit(main())
