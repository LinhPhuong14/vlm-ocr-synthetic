"""The agent that writes field VALUES, instead of the corpus.

    composed = compose.decide(decisions, rules, llm=client.from_env())
    compose.write(composed, out / "compose.jsonl", out / "content_overrides.json")

`agent/planner.py` decides WHICH document/layout/dressing a page draws.
This module decides what a handful of its TEXT fields actually SAY --
`store.name`, an item's name, a hospital admission's diagnosis -- instead of
`rulebase/content.py` drawing them from `rulebase/corpus/vi/*.txt`. Numbers
are never in scope: `amount`, every total, every derived split, stay exactly
what `rulebase/content.py` already computes, because `pipeline/invariants.py`
re-derives and checks them, and a model that adds wrong is a shard that fails
quietly.

Same shape as the planner, on purpose
--------------------------------------

Decide before render, write a file, never call the model from inside
`generators/`. `agent/planner.py` proved this pattern works this session
(`concurrency`, `pin`, byte-identical output regardless of how many threads
fetched it); this module reuses it rather than inventing a second one.

Where it differs: `planner.propose()` blocks by page index because every
block shares one schema (the six rule-base attributes never change shape).
Content does not -- a `medical` page's schema carries the diagnoses list, a
`market` page's does not -- so `decide()` blocks by **profile**, batching
consecutive same-profile pages and starting a new block early at a profile
boundary rather than padding a mixed-schema request.

`rulebase/` as a guideline, not a generator
--------------------------------------------

Every bound sent to the model is MEASURED, not invented: `store.name`'s
length/word-count comes from `agent.corpus_rules.envelopes()` run over the
same `rulebase/corpus/vi/shops_<profile>.txt` the rule-based path would have
drawn from, and a diagnosis is constrained to the exact `(code, name)` pairs
already sitting in `rulebase/documents/<doc>.yaml`'s own `diagnoses:` list --
the model picks one of THOSE, never invents an ICD code. `rulebase/` stays
the single source of truth for what a field may say; this module only asks a
model to pick a better answer within it than three unrelated dice rolls do.

Validation is the corpus's own rules, not a new opinion
----------------------------------------------------------

Every free-text value a model returns is checked by
`agent.corpus_rules.check_name()` -- the exact function that already gates
`agent/augment_content.py`'s corpus-growing lines -- plus one gate that
function does not have: `pipeline.drift.has_diacritics()`, required here
because the user asked for it explicitly, not added to `check_name`'s own
default (real corpus lines are legitimately diacritic-free sometimes --
`"Natri Clorid 0,9%"`, `"iPad"` -- and retrofitting a hard per-value
requirement there would start rejecting lines a person already wrote, which
is exactly the failure `corpus_rules`'s own history warns against). A
rejected value is dropped from that one page's overrides and `rulebase.
content.build()` falls back to corpus for it, exactly as if no override
existed -- a model having a bad day never fails a page.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pipeline.drift import has_diacritics
from pipeline.progress import Bar

from . import corpus_rules
from .client import LLMError

REPO_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = REPO_ROOT / "rulebase" / "corpus" / "vi"

# How many candidate item names to ask for per page, when the profile draws a
# basket at all. `content.build()` decides the REAL count per page (from the
# document's own `num_items` range) only once it runs, well after compose is
# done -- so this asks for the range's own ceiling, capped, and
# `apply_content_overrides` uses only as many as a page turns out to have.
# Asking for more than exist is harmless; asking for fewer would waste real
# ones on corpus after the model already wrote them.
MAX_ITEM_NAMES = 12

# Which fields compose may write, per `profile:` (see `rulebase/documents/
# *.yaml`). A judgement call -- "is this text or a number" -- not something
# walking the YAML can answer, so it is a short table, not a derivation.
# `medical` gets an ENUM override instead of free text: that is the one bug
# this session actually found (a department, its diagnosis and its billed
# services drawn by three unrelated `rng.choice()` calls -- see this module's
# own docstring) and constraining the model's answer to the document's own
# existing `diagnoses:`/`comorbidities:` lists fixes it by construction.
PROFILE_FIELDS: dict[str, dict[str, list[str]]] = {
    "market": {"free_text": ["store.name", "item_names"], "enum": []},
    "eatery": {"free_text": ["store.name", "item_names"], "enum": []},
    "bakery": {"free_text": ["store.name", "item_names"], "enum": []},
    "invoice": {"free_text": ["store.name"], "enum": []},
    "hotel": {"free_text": ["store.name"], "enum": []},
    "insurance": {"free_text": ["store.name"], "enum": []},
    "utility_power": {"free_text": ["store.name"], "enum": []},
    "utility_water": {"free_text": ["store.name"], "enum": []},
    "medical": {"free_text": [], "enum": ["admission.diagnosis", "admission.comorbid"]},
    # `export` and periodical documents (`kind: periodical`) are out of
    # scope for this increment -- see the module docstring's "not in scope"
    # note in the implementation plan. Any profile not listed here simply
    # gets no compose block; `rulebase.content.build()` behaves exactly as
    # before this module existed.
}


@dataclass
class ComposedPage:
    """One page, as compose settled it -- the content-side `Decision`."""

    seed: int
    document: str
    profile: str
    content: dict[str, str] = field(default_factory=dict)
    rejected: dict[str, str] = field(default_factory=dict)
    by: str = "coverage"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _corpus_text(stem: str) -> str:
    path = CORPUS_DIR / f"{stem}.txt"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _store_name_bounds(profile: str) -> tuple[corpus_rules.Shape, corpus_rules.Envelope]:
    stem = f"shops_{profile}"
    return corpus_rules.shape_of(stem), corpus_rules.envelope(_corpus_text(stem), column=0)


def _item_name_bounds(profile: str) -> tuple[corpus_rules.Shape, corpus_rules.Envelope]:
    stem = f"items_{profile}"
    return corpus_rules.shape_of(stem), corpus_rules.envelope(_corpus_text(stem), column=0)


def _diagnosis_enum(document: dict[str, Any], key: str) -> list[tuple[str, str]]:
    return [(str(code), str(name)) for code, name in (document.get(key) or [])]


def _string_spec(envelope: corpus_rules.Envelope) -> dict:
    """A JSON-schema string spec that encodes BOTH bounds `check_name` checks
    -- character length (`minLength`/`maxLength`, which the schema has a real
    keyword for) and word count (which it does not; a regex `pattern`
    counting whitespace-separated runs is the closest a JSON schema gets).
    Guided decoding enforcing this up front means fewer values `compose.py`
    has to throw away and re-ask for -- character bounds alone let through an
    answer three words long when the file it is headed to runs 6..13.
    """
    low_chars, high_chars = envelope.longest()
    low_words, high_words = envelope.widest()
    pattern = rf"^(?:\S+\s+){{{max(low_words - 1, 0)},{max(high_words - 1, 0)}}}\S+$"
    return {"type": "string", "minLength": low_chars, "maxLength": high_chars,
            "pattern": pattern}


def schema_for(profile: str, document: dict[str, Any], block: int) -> dict | None:
    """The JSON schema for one block of `block` same-profile pages, or None if
    `profile` has nothing compose is allowed to write (see `PROFILE_FIELDS`).
    """
    fields = PROFILE_FIELDS.get(profile)
    if not fields or not (fields["free_text"] or fields["enum"]):
        return None
    props: dict[str, Any] = {}
    required: list[str] = []
    for key in fields["free_text"]:
        if key == "store.name":
            _shape, envelope = _store_name_bounds(profile)
            props[key] = _string_spec(envelope)
            required.append(key)
        elif key == "item_names":
            _shape, envelope = _item_name_bounds(profile)
            props[key] = {"type": "array", "minItems": MAX_ITEM_NAMES,
                          "maxItems": MAX_ITEM_NAMES, "items": _string_spec(envelope)}
            required.append(key)
    for key in fields["enum"]:
        source = "diagnoses" if key.endswith("diagnosis") else "comorbidities"
        pairs = _diagnosis_enum(document, source)
        if not pairs:
            continue
        props[key] = {"type": "string", "enum": [code for code, _name in pairs]}
        required.append(key)
    if not props:
        return None
    page = {"type": "object", "properties": props, "required": required,
            "additionalProperties": False}
    return {"type": "object",
            "properties": {"pages": {"type": "array", "items": page,
                                     "minItems": block, "maxItems": block}},
            "required": ["pages"], "additionalProperties": False}


SYSTEM = """Bạn viết nội dung thật cho chứng từ Việt Nam (tên cửa hàng, tên mặt
hàng, hoặc chọn chẩn đoán y tế phù hợp). Đây là văn bản người thật sẽ đọc,
không phải bịa cho có.

Bắt buộc:
1. TIẾNG VIỆT CÓ DẤU ĐẦY ĐỦ. Không viết không dấu, không viết tiếng Anh trừ
   khi tên riêng thật sự là tiếng Anh (ví dụ một thương hiệu).
2. Thật như đời sống Việt Nam hiện tại — tên cửa hàng, tên mặt hàng phải là
   thứ có thật hoặc hợp lý y như thật, không phải chuỗi ký tự ngẫu nhiên.
3. CẢ LÔ đa dạng — đừng lặp lại một tên hai lần trong cùng một lô.
4. Nếu được cho danh sách chẩn đoán/bệnh kèm theo có sẵn, chỉ chọn ĐÚNG một
   mã trong danh sách đó, chọn mã hợp lý nhất với khoa/loại hình đã cho —
   không tự bịa mã mới.

Chỉ trả JSON đúng schema, không giải thích."""


def _user_message(profile: str, document: dict[str, Any], count: int) -> str:
    parts = [f"Viết nội dung cho {count} trang, cùng loại chứng từ (profile={profile})."]
    if profile == "medical":
        diagnoses = _diagnosis_enum(document, "diagnoses")
        comorbid = _diagnosis_enum(document, "comorbidities")
        branch = document.get("title", profile)
        parts.append(f"Đây là bảng kê của một khoa cụ thể ({branch!r} nếu có trong tên "
                     "bệnh viện) -- chọn chẩn đoán và bệnh kèm theo PHÙ HỢP với khoa đó, "
                     "không chọn ngẫu nhiên.")
        parts.append("Danh sách chẩn đoán được phép (mã - tên): " +
                     "; ".join(f"{c}-{n}" for c, n in diagnoses))
        parts.append("Danh sách bệnh kèm theo được phép (mã - tên): " +
                     "; ".join(f"{c}-{n}" for c, n in comorbid))
    return "\n".join(parts)


def _validate_free_text(value: Any, shape: corpus_rules.Shape,
                        envelope: corpus_rules.Envelope) -> str:
    """'' when `value` is fine, else why not -- `check_name` plus the
    diacritic gate this module adds on top of it (see the module docstring
    for why that gate lives here and not inside `corpus_rules` itself)."""
    if not isinstance(value, str):
        return "not a string"
    problem = corpus_rules.check_name(value, shape, envelope)
    if problem:
        return problem
    if not has_diacritics(value):
        return "no Vietnamese diacritic"
    return ""


def _decide_block(llm, profile: str, document: dict[str, Any],
                  pages: list[ComposedPage]) -> None:
    """Fill `content`/`rejected`/`by` on every page in `pages`, in place."""
    schema = schema_for(profile, document, len(pages))
    if schema is None or llm is None:
        return
    try:
        answer = llm.decide(SYSTEM, _user_message(profile, document, len(pages)), schema)
    except LLMError:
        return
    proposals = answer.get("pages")
    if not isinstance(proposals, list) or len(proposals) != len(pages):
        return
    store_shape, store_env = (_store_name_bounds(profile)
                              if "store.name" in PROFILE_FIELDS[profile]["free_text"]
                              else (None, None))
    item_shape, item_env = (_item_name_bounds(profile)
                            if "item_names" in PROFILE_FIELDS[profile]["free_text"]
                            else (None, None))
    diagnoses = dict(_diagnosis_enum(document, "diagnoses"))
    comorbid = dict(_diagnosis_enum(document, "comorbidities"))
    for page, proposal in zip(pages, proposals):
        if not isinstance(proposal, dict):
            continue
        used_any = False
        if "store.name" in proposal and store_shape is not None:
            problem = _validate_free_text(proposal["store.name"], store_shape, store_env)
            if problem:
                page.rejected["store.name"] = problem
            else:
                page.content["store.name"] = proposal["store.name"]
                used_any = True
        names = proposal.get("item_names")
        if isinstance(names, list) and item_shape is not None:
            for index, name in enumerate(names):
                problem = _validate_free_text(name, item_shape, item_env)
                key = f"menu[{index}].name"
                if problem:
                    page.rejected[key] = problem
                else:
                    page.content[key] = name
                    used_any = True
        diag = proposal.get("admission.diagnosis")
        if diag is not None:
            if diag in diagnoses:
                page.content["admission.diagnosis"] = diag
                used_any = True
            else:
                page.rejected["admission.diagnosis"] = "not in the document's own list"
        como = proposal.get("admission.comorbid")
        if como is not None:
            if como in comorbid:
                page.content["admission.comorbid"] = como
                used_any = True
            else:
                page.rejected["admission.comorbid"] = "not in the document's own list"
        if used_any:
            page.by = "llm"


def decide(decisions: list, rules: dict, *, llm=None, concurrency: int = 1) -> list[ComposedPage]:
    """One `ComposedPage` per `decision`, in the same order.

    Blocks by `(profile, run of consecutive pages)` -- see the module
    docstring for why that is not the same as `agent.planner.plan()`'s
    page-index blocking. `concurrency` prefetches that many blocks' worth of
    proposals over threads, exactly like `agent.planner.plan()`; applying a
    block's answers stays sequential (there is nothing here an earlier page
    needs from a later one, but the pattern is kept identical on purpose --
    one concurrency story in this codebase, not two).
    """
    by_document = {option.id: option.params for option in rules.get("document", [])}
    pages = []
    for decision in decisions:
        document_id = decision.force.get("document", "")
        params = by_document.get(document_id, {})
        profile = params.get("profile", "") if params.get("kind") != "periodical" else ""
        pages.append(ComposedPage(seed=decision.seed, document=document_id, profile=profile))

    # Group consecutive pages sharing a profile into blocks -- a profile
    # boundary always starts a new block, even mid-way through what would
    # otherwise be a full one, because the schema itself changes at that
    # boundary (see module docstring).
    blocks: list[list[int]] = []
    for index, page in enumerate(pages):
        if blocks and pages[blocks[-1][0]].profile == page.profile \
                and len(blocks[-1]) < 24:
            blocks[-1].append(index)
        else:
            blocks.append([index])

    eligible = [b for b in blocks if pages[b[0]].profile in PROFILE_FIELDS]
    if not eligible or llm is None:
        with Bar(len(pages), "trang") as bar:
            bar.advance(len(pages))
        return pages

    def run_block(indices: list[int]) -> None:
        profile = pages[indices[0]].profile
        document_id = pages[indices[0]].document
        document = by_document.get(document_id, {})
        block_pages = [pages[i] for i in indices]
        _decide_block(llm, profile, document, block_pages)

    with Bar(len(pages), "trang") as bar:
        if concurrency > 1 and len(eligible) > 1:
            import concurrent.futures as cf  # noqa: PLC0415 -- this branch only

            with cf.ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = {pool.submit(run_block, indices): indices for indices in eligible}
                for future in cf.as_completed(futures):
                    future.result()
                    bar.advance(len(futures[future]))
        else:
            for indices in eligible:
                run_block(indices)
                bar.advance(len(indices))
        skipped = len(pages) - sum(len(b) for b in eligible)
        if skipped:
            bar.advance(skipped)
    return pages


def write(pages: list[ComposedPage], ledger_path, overrides_path) -> None:
    """`compose.jsonl` (rich, audit) and `content_overrides.json` (lean, the
    file `rulebase/content.py` actually reads -- see its own `VLM_CONTENT_
    OVERRIDES`). Two files for the same reason `synthesis.json` and `--force`
    already are two different shapes in this repository: one for a person to
    read, one for a subprocess to load fast.
    """
    ledger_path = Path(ledger_path)
    overrides_path = Path(overrides_path)
    with open(ledger_path, "w", encoding="utf-8") as ledger:
        for page in pages:
            ledger.write(json.dumps(page.to_dict(), ensure_ascii=False) + "\n")
    overrides = {str(page.seed): page.content for page in pages if page.content}
    overrides_path.write_text(json.dumps(overrides, ensure_ascii=False, indent=1) + "\n",
                              encoding="utf-8")


__all__ = ["ComposedPage", "PROFILE_FIELDS", "SYSTEM", "decide", "schema_for", "write"]
