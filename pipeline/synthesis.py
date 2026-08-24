"""How a page was made, kept beside the dataset instead of inside every line.

    data/dataset60/html/
        html_000.jpg  html_000.json   one converter-shaped record per image
        …
        synthesis.json                how those images were made -- this file

`pipeline/record.py` writes the converter's schema and nothing else: a line is
what a converted page looks like, so a loader reads a drawn set and a scanned
set the same way. But a *drawn* page has a provenance a converted one cannot
have -- the seed, the six sampled attributes and their params, the flat reading
order -- and without it no committed image can be drawn again, `tools/check_boxes.py`
cannot rebuild what it checks, and the drift vectors have no axes.

That provenance used to ride in every line, under a `synthesis` key. It does not
belong there, and it was mostly the same text over and over: `ornament` and
`augmentation` are recipes for a *background*, and twenty pages that share one
augmentation chain wrote that chain out twenty times. So it moves here, and the
repetition goes with it:

* **params are written once, per option id.** `attributes` maps
  `augmentation -> real_paper -> {chain: [...]}`, and every page that drew it
  names `real_paper`. `Synthesis.recipe()` puts the two back together, returning
  the same `recipe.to_dict()` shape the rule-base produced -- so everything
  reading a recipe reads what it always did.
* **a page keeps only what is its own:** its seed, which option it drew for each
  attribute, its tags, its reading order, and its `job_id`, which is what joins
  it back to the line in `metadata.jsonl`.

**Streamed, not accumulated.** A run of 100k images must not need all of them in
memory at once -- the rule `record.write` is under, and the same one here. The
file is written as it goes: the header, then one page at a time, then
`attributes` at the end, which is the only part that has to be complete before
it can be written and the only part that is bounded (the rule-base has a fixed
set of options, however many pages draw them).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Iterator

# One per dataset directory, because it is a statement about the *set*: which
# options were drawn, and what the params behind each id are. The per-page
# records sit beside their images (`pipeline/record.py`); this sits beside them
# all. `beside()` is the only place that convention is written down.
NAME = "synthesis.json"

# The same number `pipeline/record.py` writes. The two files are one dataset and
# are read together; a pair that disagreed about which schema it is would be a
# dataset nobody can load without checking both.
SCHEMA_VERSION = 8


class SynthesisError(ValueError):
    """This file does not describe the images beside it."""


def beside(path: Path | str) -> Path:
    """The synthesis file for a dataset directory, for a file in it, or itself.

    Three things get passed around as "the dataset": the directory, a page
    inside it, and this file. All three name the same provenance, so all three
    resolve to it rather than each caller remembering which it has.
    """
    path = Path(path)
    if path.name == NAME:
        return path
    if path.suffix and not path.is_dir():
        return path.parent / NAME
    return path / NAME


# ------------------------------------------------------------------- writing


def _split(attributes: dict[str, Any]) -> tuple[dict[str, str], dict[str, dict]]:
    """One recipe's attributes into (what this page drew, what those ids mean)."""
    drew: dict[str, str] = {}
    means: dict[str, dict] = {}
    for name, value in (attributes or {}).items():
        if not isinstance(value, dict) or "id" not in value:
            continue
        identifier = str(value["id"])
        drew[name] = identifier
        # Everything except the id itself: `params` for five attributes, and
        # `group` as well for `layout`. Kept in the order the rule-base wrote
        # them, so a rehydrated recipe is the dict that went in.
        means[name] = {identifier: {key: sub for key, sub in value.items()
                                    if key != "id"}}
    return drew, means


class Writer:
    """`synthesis.json`, written as the pages arrive.

    Use it as a context manager: the file is only valid once `close` has run,
    because `attributes` is written last, so an abandoned run leaves a file that
    fails to parse rather than one that parses and is short. That is deliberate
    -- a truncated provenance that loads is the kind of thing nobody notices.
    """

    def __init__(self, path: Path | str, framework: str = "") -> None:
        self.path = Path(path)
        self.framework = framework
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = open(self.path, "w", encoding="utf-8")
        self._handle.write(
            "{\n"
            f'  "schema_version": {SCHEMA_VERSION},\n'
            f'  "framework": {json.dumps(framework, ensure_ascii=False)},\n'
            '  "pages": {'
        )
        self._written = 0
        self._attributes: dict[str, dict[str, dict]] = {}

    def __enter__(self) -> "Writer":
        return self

    def __exit__(self, *_exception) -> None:
        self.close()

    def add(self, filename: str, *, job_id: str = "", layout: str = "",
            recipe: dict[str, Any] | None = None, text_sequence: str = "",
            extra: dict[str, Any] | None = None) -> None:
        """One page's provenance. `recipe` is `Recipe.to_dict()`, as it comes."""
        recipe = recipe or {}
        drew, means = _split(recipe.get("attributes") or {})
        for name, options in means.items():
            for identifier, body in options.items():
                seen = self._attributes.setdefault(name, {}).get(identifier)
                if seen is not None and seen != body:
                    # An id is meant to be a name for one set of params. Two
                    # different bodies under one name would make every page
                    # that drew it ambiguous, and the file could not be
                    # rehydrated at all -- so it stops here rather than
                    # producing a file that reads as if it were fine.
                    raise SynthesisError(
                        f"{filename}: {name}={identifier!r} was already written "
                        f"with different params; one id must mean one thing")
                self._attributes[name][identifier] = body

        entry: dict[str, Any] = {"job_id": job_id, "seed": recipe.get("seed"),
                                 "layout": layout, "attributes": drew,
                                 "tags": recipe.get("tags") or []}
        if text_sequence:
            entry["text_sequence"] = text_sequence
        entry.update(extra or {})

        self._handle.write("" if self._written == 0 else ",")
        self._handle.write(
            f"\n    {json.dumps(str(filename), ensure_ascii=False)}: "
            f"{json.dumps(entry, ensure_ascii=False)}")
        self._written += 1

    def close(self) -> int:
        if self._handle.closed:
            return self._written
        self._handle.write("\n  " if self._written else "")
        self._handle.write(
            "},\n"
            f'  "attributes": {json.dumps(self._attributes, ensure_ascii=False, sort_keys=True)},\n'
            f'  "images": {self._written}\n'
            "}\n"
        )
        self._handle.close()
        return self._written


def write(path: Path | str, framework: str, entries: Iterable[tuple[str, dict]]) -> int:
    """The whole file at once, for a caller that already has every page."""
    with Writer(path, framework) as writer:
        for filename, entry in entries:
            writer.add(filename, **entry)
    return writer.close()


# ------------------------------------------------------------------- reading


class Synthesis:
    """`synthesis.json`, with the params folded back into each page's recipe."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.schema_version = payload.get("schema_version")
        self.framework = str(payload.get("framework", ""))
        self.attributes: dict[str, dict[str, dict]] = payload.get("attributes") or {}
        self.pages: dict[str, dict] = payload.get("pages") or {}

    def __len__(self) -> int:
        return len(self.pages)

    def __contains__(self, filename: str) -> bool:
        return str(filename) in self.pages

    def __iter__(self) -> Iterator[str]:
        return iter(self.pages)

    def entry(self, filename: str) -> dict[str, Any]:
        return self.pages.get(str(filename)) or {}

    def recipe(self, filename: str) -> dict[str, Any]:
        """The page's `Recipe.to_dict()`, rebuilt from its ids and the params.

        The dict that went in, key for key -- which is what lets everything that
        reads a recipe keep reading one, and what
        `python tools/check_boxes.py` hands straight back to `rulebase.make`.
        """
        page = self.entry(filename)
        if not page:
            return {}
        attributes: dict[str, Any] = {}
        for name, identifier in (page.get("attributes") or {}).items():
            body = (self.attributes.get(name) or {}).get(str(identifier))
            if body is None:
                # Named but not defined. Reported as a hole rather than filled
                # with an empty params dict, which would rebuild a *different*
                # page and say nothing about it.
                raise SynthesisError(
                    f"{filename}: {name}={identifier!r} is not in `attributes`, "
                    f"so this page's recipe cannot be rebuilt")
            attributes[name] = {"id": str(identifier), **body}
        return {"seed": page.get("seed"), "attributes": attributes,
                "tags": page.get("tags") or []}

    def layout(self, filename: str) -> str:
        """The layout the plan asked for, falling back to the one drawn."""
        page = self.entry(filename)
        named = page.get("layout")
        if named:
            return str(named)
        return str((page.get("attributes") or {}).get("layout", "?"))

    def drawn_layout(self, filename: str) -> str:
        """What the recipe says was drawn, with no fallback to the plan's name."""
        return str((self.entry(filename).get("attributes") or {}).get("layout", ""))

    def text_sequence(self, filename: str) -> str:
        return str(self.entry(filename).get("text_sequence", ""))

    def content_source(self, filename: str, default: str = "") -> str:
        return str(self.entry(filename).get("content_source", default))

    def problems(self, filenames: Iterable[str]) -> list[str]:
        """Everything the two files disagree about, most important first."""
        wanted = [str(name) for name in filenames]
        out: list[str] = []
        if self.schema_version != SCHEMA_VERSION:
            out.append(f"schema_version must be {SCHEMA_VERSION}, "
                       f"got {self.schema_version!r}")
        missing = [name for name in wanted if name not in self.pages]
        if missing:
            out.append(f"{len(missing)} image(s) have no synthesis entry, "
                       f"first {missing[0]!r}")
        spare = [name for name in self.pages if name not in set(wanted)]
        if spare:
            out.append(f"{len(spare)} synthesis entr(ies) name no image, "
                       f"first {spare[0]!r}")
        return out


EMPTY = Synthesis({"schema_version": SCHEMA_VERSION, "framework": "",
                   "attributes": {}, "pages": {}})


def read(path: Path | str) -> Synthesis:
    """Read `synthesis.json`, given it or the `metadata.jsonl` beside it."""
    path = beside(path)
    if not path.exists():
        raise SynthesisError(f"no {NAME} beside {path.parent}; a dataset written "
                             f"before it existed is brought forward with "
                             f"`python tools/migrate_metadata.py`")
    return Synthesis(json.loads(path.read_text(encoding="utf-8")))


def read_if_there(path: Path | str) -> Synthesis:
    """The same, but an absent file is an empty one rather than an error.

    For the readers that would otherwise refuse to run at all -- a monitor, a
    figure script -- where "no provenance" is a thing to report and not a thing
    to stop for.
    """
    try:
        return read(path)
    except (SynthesisError, json.JSONDecodeError):
        return EMPTY


def merge(destination: Path | str, framework: str,
          sources: Iterable[Path | str]) -> int:
    """Fold several shards' files into one, in the order they are given."""
    with Writer(destination, framework) as writer:
        for source in sources:
            found = read(source)
            for filename in found:
                page = dict(found.entry(filename))
                writer.add(filename, job_id=str(page.pop("job_id", "")),
                           layout=str(page.pop("layout", "")),
                           recipe=found.recipe(filename),
                           text_sequence=str(page.pop("text_sequence", "")),
                           extra={key: value for key, value in page.items()
                                  if key not in ("seed", "attributes", "tags")})
    return writer.close()


__all__ = [
    "EMPTY",
    "NAME",
    "SCHEMA_VERSION",
    "Synthesis",
    "SynthesisError",
    "Writer",
    "beside",
    "merge",
    "read",
    "read_if_there",
    "write",
]
