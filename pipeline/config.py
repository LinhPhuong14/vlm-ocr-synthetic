"""One file declares a whole run, and a typo in it stops the run.

    from pipeline.config import Config
    config = Config.load("pipeline.yaml")

`pipeline.yaml`:

    run:      {out: data/run01, per_backend: 5000, seed: 2026, workers: auto,
               pairing: paired}
    backends: [synthdog, html, genalog]
    shard:    {size: 250}
    overrides:
      augmentation.torn_edges.weight: 0.5
    quality:  {drift_tolerance: 0.15, sample_for_ocr: 500}

Two properties matter more than the shape:

**Unknown keys raise.** A `pipeline.yaml` with `ouput:` in it that runs anyway,
using the default, is the silent failure this repository keeps being bitten by
-- the same shape as a rules file the manifest forgets, or a tag with a typo in
it that simply makes a value undrawable.

**Every override must resolve.** `augmentation.no_such_value.weight` names
nothing; accepting it would mean the run quietly used the unmodified weights
while its config says otherwise, and nobody would find out from the output.

`quality:` is parsed and carried but unused here -- W2 reads it. It is declared
now so `pipeline.yaml` does not change shape between waves.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from .quota import BALANCES, DEFAULT_BALANCE

REPO_ROOT = Path(__file__).resolve().parent.parent

# Where a run-specific rules directory is announced to the renderers. Unset
# means the shipped `rulebase/rules/`, which is why a run without overrides is
# byte-identical to one from before this existed.
RULES_ENV = "VLM_RULES_ROOT"

RUN_KEYS = {"out", "per_backend", "seed", "workers", "clean", "force", "pairing"}
SHARD_KEYS = {"size"}
QUALITY_KEYS = {"drift_tolerance", "sample_for_ocr"}
TAXONOMY_KEYS = {"include", "exclude", "balance"}
TOP_KEYS = {"run", "backends", "shard", "overrides", "quality", "taxonomy"}

# Whether the backends draw the same receipts or different ones.
#
#   paired       all backends share one seed range: the same receipt, drawn
#                three ways. This is what makes "the same seed gives the same
#                words in the same columns whether the page was drawn glyph by
#                glyph or screenshotted from a browser" a fact about the data
#                rather than a claim about the sampler, and it is the only mode
#                in which comparing the renderers means anything.
#   independent  each backend gets its own seed block, so N backends give N
#                times the distinct pages. For volume, not for comparison.
#
# `paired` is the default because the comparison is what this repository is
# for, and because a dataset built the other way looks identical from outside.
PAIRINGS = ("paired", "independent")
DEFAULT_PAIRING = "paired"


class ConfigError(ValueError):
    """The run declaration is wrong, and running it would not mean what it says."""


def _reject_unknown(section: str, given: dict, known: set[str]) -> None:
    unknown = sorted(set(given) - known)
    if unknown:
        raise ConfigError(
            f"{section}: unknown keys {unknown}; allowed are {sorted(known)}"
        )


@dataclass(frozen=True)
class Config:
    out: Path
    per_backend: int
    seed: int
    workers: int          # already resolved: `auto` becomes a number here
    backends: tuple[str, ...]
    shard_size: int
    clean: bool = False
    force: tuple[str, ...] = ()
    pairing: str = DEFAULT_PAIRING
    overrides: dict[str, Any] = field(default_factory=dict)
    quality: dict[str, Any] = field(default_factory=dict)
    taxonomy: dict[str, Any] = field(default_factory=dict)
    source: Path | None = None

    @property
    def stratified(self) -> bool:
        """Is this run balanced over the hierarchy, or only over the layouts?

        Absent `taxonomy:`, a run splits its images over the layouts exactly as
        every run did before the hierarchy existed. That is not a deprecated
        path kept for politeness: it is what the golden baseline pins, and a
        config that says nothing about document types should not silently start
        planning by them.
        """
        return bool(self.taxonomy)

    @classmethod
    def load(cls, path: Path | str) -> "Config":
        path = Path(path)
        if not path.exists():
            raise ConfigError(f"no config at {path}")
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return cls.from_dict(raw, source=path)

    @classmethod
    def from_dict(cls, raw: dict, source: Path | None = None) -> "Config":
        if not isinstance(raw, dict):
            raise ConfigError("the config must be a mapping")
        _reject_unknown("config", raw, TOP_KEYS)

        run = raw.get("run") or {}
        if not isinstance(run, dict):
            raise ConfigError("run: must be a mapping")
        _reject_unknown("run", run, RUN_KEYS)

        shard = raw.get("shard") or {}
        _reject_unknown("shard", shard, SHARD_KEYS)

        quality = raw.get("quality") or {}
        _reject_unknown("quality", quality, QUALITY_KEYS)

        taxonomy_section = raw.get("taxonomy") or {}
        if not isinstance(taxonomy_section, dict):
            raise ConfigError("taxonomy: must be a mapping")
        _reject_unknown("taxonomy", taxonomy_section, TAXONOMY_KEYS)
        balance = str(taxonomy_section.get("balance", DEFAULT_BALANCE))
        if taxonomy_section and balance not in BALANCES:
            raise ConfigError(
                f"taxonomy.balance: expected one of {list(BALANCES)}, got {balance!r}")
        for key in ("include", "exclude"):
            value = taxonomy_section.get(key)
            if value is not None and not isinstance(value, list):
                raise ConfigError(f"taxonomy.{key}: must be a list of document types")

        backends = raw.get("backends")
        if not backends:
            raise ConfigError("backends: at least one is required")
        if not isinstance(backends, list):
            raise ConfigError("backends: must be a list")

        out = run.get("out")
        if not out:
            raise ConfigError("run.out: required")

        per_backend = int(run.get("per_backend", 0))
        if per_backend < 1:
            raise ConfigError(f"run.per_backend: must be >= 1, got {per_backend}")

        size = int(shard.get("size", 250))
        if size < 1:
            raise ConfigError(f"shard.size: must be >= 1, got {size}")

        overrides = raw.get("overrides") or {}
        if not isinstance(overrides, dict):
            raise ConfigError("overrides: must be a mapping of 'attr.id.field' to value")

        pairing = str(run.get("pairing", DEFAULT_PAIRING))
        if pairing not in PAIRINGS:
            raise ConfigError(
                f"run.pairing: expected one of {list(PAIRINGS)}, got {pairing!r}")

        return cls(
            # Absolute here, at the edge, once. A relative output path handed to
            # the glyph backend lands inside generators/synthdog/ instead --
            # silently, because the backend creates whatever directory it is
            # given. Resolving late is how that bug happens.
            out=Path(out).expanduser().resolve(),
            per_backend=per_backend,
            seed=int(run.get("seed", 2026)),
            workers=resolve_workers(run.get("workers", "auto")),
            backends=tuple(str(name) for name in backends),
            shard_size=size,
            clean=bool(run.get("clean", False)),
            force=tuple(str(item) for item in (run.get("force") or ())),
            pairing=pairing,
            overrides=dict(overrides),
            quality=dict(quality),
            taxonomy=(
                {
                    "include": [str(v) for v in (taxonomy_section.get("include") or [])],
                    "exclude": [str(v) for v in (taxonomy_section.get("exclude") or [])],
                    "balance": balance,
                }
                if taxonomy_section else {}
            ),
            source=source,
        )


def resolve_workers(value: Any) -> int:
    """`auto` -> one fewer than the CPUs, so the machine stays usable."""
    if isinstance(value, str):
        if value.strip().lower() != "auto":
            raise ConfigError(f"run.workers: expected a number or 'auto', got {value!r}")
        return max(1, (os.cpu_count() or 2) - 1)
    workers = int(value)
    if workers < 1:
        raise ConfigError(f"run.workers: must be >= 1, got {workers}")
    return workers


# ---------------------------------------------------------------- overrides


def apply_overrides(rules: dict, overrides: dict[str, Any]) -> dict:
    """Return `rules` with `attribute.id.field` entries replaced.

    Only fields that already exist on the option may be set. Inventing one --
    `visual.laser_sharp.wieght` -- would be accepted silently by a looser
    implementation and change nothing, which is the failure this rejects.
    """
    from rulebase.spec import Option

    if not overrides:
        return rules

    patched = {attribute: list(options) for attribute, options in rules.items()}
    for path, value in overrides.items():
        parts = str(path).split(".")
        if len(parts) != 3:
            raise ConfigError(
                f"overrides: {path!r} should be 'attribute.value_id.field', "
                f"e.g. augmentation.torn_edges.weight"
            )
        attribute, option_id, attr = parts
        if attribute not in patched:
            raise ConfigError(
                f"overrides: {path!r} names attribute {attribute!r}, which does not "
                f"exist; have {sorted(patched)}"
            )
        index = next((i for i, o in enumerate(patched[attribute]) if o.id == option_id), None)
        if index is None:
            raise ConfigError(
                f"overrides: {path!r} names {attribute}/{option_id!r}, which does not "
                f"exist; have {sorted(o.id for o in patched[attribute])}"
            )
        option = patched[attribute][index]
        if attr not in {"weight", "tags", "requires", "excludes"}:
            raise ConfigError(
                f"overrides: {path!r} sets {attr!r}; only weight, tags, requires "
                f"and excludes can be overridden (params belong in the rules file)"
            )
        raw = {
            "id": option.id,
            "weight": option.weight,
            "tags": sorted(option.tags),
            "requires": sorted(option.requires),
            "excludes": sorted(option.excludes),
            "params": option.params,
            "doc_type": option.doc_type,
        }
        raw[attr] = value
        patched[attribute][index] = Option.from_dict(raw, attribute)
    return patched


def materialise_rules(rules: dict, destination: Path) -> Path:
    """Write `rules` out as a rules directory a renderer can be pointed at.

    The renderers are separate processes with their own interpreters, so an
    override cannot be handed over as a Python object -- it has to become files.
    `_order.yaml` is written from the mapping's own order, which is where draw
    order lives since W0.

    An attribute that is a *directory* of files in `rulebase/rules/` is written
    back out as a single file. That is deliberate: the split exists so a person
    can find the family they want to edit, and nobody edits a materialised copy.
    `doc_type` has to survive the round trip or the run would relabel every
    image it produced -- an override that silently changed the document type
    would be the worst kind of quiet failure this file exists to prevent.
    """
    destination.mkdir(parents=True, exist_ok=True)
    for attribute, options in rules.items():
        payload = {"options": [
            {
                "id": option.id,
                "weight": option.weight,
                **({"doc_type": option.doc_type} if option.doc_type else {}),
                **({"tags": sorted(option.tags)} if option.tags else {}),
                **({"requires": sorted(option.requires)} if option.requires else {}),
                **({"excludes": sorted(option.excludes)} if option.excludes else {}),
                **({"params": option.params} if option.params else {}),
            }
            for option in options
        ]}
        (destination / f"{attribute}.yaml").write_text(
            yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    (destination / "_order.yaml").write_text(
        yaml.safe_dump({"order": list(rules)}, allow_unicode=True), encoding="utf-8")
    return destination


__all__ = [
    "Config",
    "ConfigError",
    "TAXONOMY_KEYS",
    "RULES_ENV",
    "apply_overrides",
    "materialise_rules",
    "resolve_workers",
]
