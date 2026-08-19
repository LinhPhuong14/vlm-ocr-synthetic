"""The document hierarchy: twelve families, 101 leaves, one source of truth.

    from taxonomy import load
    tree = load()
    tree.resolve("prescription").id        -> 'medical.prescription'
    tree.node("business.receipt.retail").names
        -> ('Structured Business Document', 'Receipt', 'Retail Receipt')
    tree.leaves(under="business.receipt")  -> the four receipt types
    tree.generatable()                     -> the ones a run can actually produce

Nothing in this repository hard-codes a document type. The tree is `document.yaml`
plus one file per family in `families/`, and everything that needs to know what a
document *is* -- the sampler, the run planner, the label, the coverage report --
reads it from here. Adding a type is a YAML edit; adding a family is a file.

Three decisions are worth reading before editing the files.

**Depth is per branch, not global.** Family 1 puts `Invoice` and `Receipt`
between the family and the leaf; the other eleven do not. An id is therefore
`business.receipt.retail` in one place and `medical.prescription` in another,
and no code may assume a fixed number of segments. A tree that forced every
branch to the same depth would have to invent a middle level for eleven
families to satisfy a loop counter.

**A name that appears twice is either an alias or a bug.** `Certificate` is
under Identity and under Academic; `Financial Report` under Financial and under
Report; `Official Letter` under Identity and under Communication. Those are one
artefact filed in two places, and the tree says so with `same_as`. Any *other*
repeated name fails to load -- two leaves with one name mean a classifier with
two labels it cannot tell apart, and a coverage report that counts one document
twice.

**`engine` is what makes the tree a plan.** A type is not reachable because it
is named here; it is reachable when something can draw it. The grid engine
exists and covers tabular, fixed-width pages. `flow`, `card` and `canvas` are
declared, empty, and counted -- so `make taxonomy` answers "what would it take
to cover the tree" with three numbers instead of a shrug.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

import yaml

TAXONOMY_ROOT = Path(__file__).resolve().parent
ROOT_FILE = "document.yaml"
FAMILIES_DIR = "families"

ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# What a node may say. Anything else is a typo, and a typo that loads is a
# field nobody reads -- `enigne: grid` would leave the node on its parent's
# engine and look exactly like a node that meant to inherit it.
NODE_KEYS = {"id", "name", "name_vi", "status", "engine", "same_as", "notes", "children"}
FAMILY_KEYS = NODE_KEYS | {"number"}
ROOT_KEYS = {"version", "root", "statuses", "engines"}

# An alias is a filing decision, not a document. It may say where it points and
# why, and nothing else: status, engine and the Vietnamese name belong to the
# canonical node, so there is exactly one answer to "can we generate this".
ALIAS_KEYS = {"id", "name", "same_as", "notes"}


class TaxonomyError(ValueError):
    """The hierarchy files say something impossible."""


@dataclass(frozen=True)
class Node:
    """One node of the tree, family or leaf, with its ancestry resolved."""

    id: str                       # full dotted path: 'business.receipt.retail'
    slug: str                     # last segment: 'retail'
    name: str                     # English display name, as given in the tree
    name_vi: str                  # Vietnamese display name
    status: str                   # ready | draft | planned
    engine: str                   # grid | flow | card | canvas
    parent: str = ""              # full id, '' for a family
    children: tuple[str, ...] = ()
    number: int | None = None     # 1..12, families only
    same_as: str = ""             # full id of the canonical node, aliases only
    notes: str = ""
    names: tuple[str, ...] = ()   # display names, root-most first

    @property
    def is_leaf(self) -> bool:
        return not self.children

    @property
    def is_family(self) -> bool:
        return self.parent == ""

    @property
    def is_alias(self) -> bool:
        return bool(self.same_as)

    @property
    def family(self) -> str:
        """The id of the family this node belongs to."""
        return self.id.split(".")[0]

    @property
    def depth(self) -> int:
        """1 for a family, 2 for its children, and so on."""
        return self.id.count(".") + 1

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "name_vi": self.name_vi,
            "status": self.status,
            "engine": self.engine,
        }
        if self.number is not None:
            data["number"] = self.number
        if self.same_as:
            data["same_as"] = self.same_as
        if self.children:
            data["children"] = list(self.children)
        return data


@dataclass(frozen=True)
class Taxonomy:
    """The whole tree, flat: `id -> Node`, in depth-first declaration order.

    Flat because every question this repository asks is either "what is this id"
    or "everything under that id", and both are cheaper on a dict than on a
    nested structure. The shape is preserved in `parent` and `children`.
    """

    version: str
    root_name: str
    root_name_vi: str
    statuses: dict[str, str]
    engines: dict[str, dict[str, Any]]
    nodes: dict[str, Node] = field(default_factory=dict)
    source: Path | None = None

    # ------------------------------------------------------------- lookups

    def __contains__(self, node_id: object) -> bool:
        return node_id in self.nodes

    def __iter__(self) -> Iterator[Node]:
        return iter(self.nodes.values())

    def __len__(self) -> int:
        return len(self.nodes)

    def node(self, node_id: str) -> Node:
        """Exact lookup. Use `resolve` for anything a human typed."""
        try:
            return self.nodes[node_id]
        except KeyError:
            raise TaxonomyError(
                f"no document type {node_id!r} in the hierarchy"
                + _did_you_mean(node_id, self.nodes)
            ) from None

    def families(self) -> list[Node]:
        """The twelve, in the order their numbers give."""
        return sorted(
            (node for node in self.nodes.values() if node.is_family),
            key=lambda node: (node.number is None, node.number, node.id),
        )

    def children(self, node_id: str) -> list[Node]:
        return [self.nodes[child] for child in self.node(node_id).children]

    def subtree(self, node_id: str) -> list[Node]:
        """`node_id` and everything under it, depth-first."""
        node = self.node(node_id)
        found = [node]
        for child in node.children:
            found.extend(self.subtree(child))
        return found

    def leaves(self, under: str | None = None, aliases: bool = False) -> list[Node]:
        """Every document type, optionally restricted to one subtree.

        Aliases are left out by default: `academic.certificate` and
        `identity.certificate` are one artefact, and a quota that counted both
        would generate it twice while reporting two types covered.
        """
        nodes = self.subtree(under) if under else list(self.nodes.values())
        return [n for n in nodes if n.is_leaf and (aliases or not n.is_alias)]

    def generatable(self, under: str | None = None) -> list[Node]:
        """The leaves a run can actually produce today -- `status: ready`."""
        return [node for node in self.leaves(under) if node.status == "ready"]

    def canonical(self, node_id: str) -> Node:
        """Follow `same_as`. The identity for everything that is not an alias."""
        node = self.node(node_id)
        return self.node(node.same_as) if node.same_as else node

    def path(self, node_id: str) -> tuple[Node, ...]:
        """Root-most ancestor first, `node_id` last."""
        node = self.node(node_id)
        chain = [node]
        while chain[0].parent:
            chain.insert(0, self.nodes[chain[0].parent])
        return tuple(chain)

    # ------------------------------------------------------------ resolving

    def resolve(self, query: str) -> Node:
        """What a human typed -> a node. Exact id, dotted suffix, or bare slug.

        With a hundred types, `--doc business.receipt.retail` on every command
        line is a tax on the common case, so `--doc retail` and
        `--doc receipt.retail` both work. Ambiguity is never guessed at: the
        tree deliberately contains three names that appear twice, and picking
        one of them silently is how a run ends up generating a school
        certificate when it was asked for a government one.
        """
        wanted = str(query).strip().lower().replace("-", "_").replace("/", ".")
        if not wanted:
            raise TaxonomyError("empty document type")
        if wanted in self.nodes:
            return self.nodes[wanted]

        suffix = [
            node for node in self.nodes.values()
            if node.id == wanted or node.id.endswith("." + wanted)
        ]
        if len(suffix) == 1:
            return suffix[0]
        if len(suffix) > 1:
            raise TaxonomyError(
                f"{query!r} matches {len(suffix)} types: "
                f"{', '.join(node.id for node in suffix)}. Say which one."
            )

        by_name = [
            node for node in self.nodes.values()
            if node.name.lower().replace(" ", "_") == wanted.replace(".", "_")
        ]
        if len(by_name) == 1:
            return by_name[0]
        if len(by_name) > 1:
            raise TaxonomyError(
                f"{query!r} matches {len(by_name)} types: "
                f"{', '.join(node.id for node in by_name)}. Say which one."
            )
        raise TaxonomyError(
            f"no document type {query!r} in the hierarchy"
            + _did_you_mean(wanted, self.nodes)
        )

    def select(self, include: Iterable[str] | None = None,
               exclude: Iterable[str] = (),
               status: Iterable[str] | None = None) -> list[Node]:
        """The leaves under `include`, minus the ones under `exclude`.

        How a run says which slice of the tree it wants:
        `include: [business.receipt, medical]` is "receipts and everything
        medical". Each pattern is resolved, so `include: [prescription]` works
        too. `status` filters afterwards, which is what keeps a run from
        planning images for a type nothing can draw.
        """
        if include is None:
            chosen = self.leaves()
        else:
            chosen = []
            seen: set[str] = set()
            for pattern in include:
                for node in self.leaves(under=self.resolve(pattern).id):
                    if node.id not in seen:
                        seen.add(node.id)
                        chosen.append(node)

        for pattern in exclude:
            dropped = {node.id for node in self.subtree(self.resolve(pattern).id)}
            chosen = [node for node in chosen if node.id not in dropped]

        if status is not None:
            wanted = set(status)
            chosen = [node for node in chosen if node.status in wanted]
        return chosen

    # ----------------------------------------------------------- reporting

    def counts(self) -> dict[str, int]:
        """Totals for the header of any report over the tree."""
        leaves = self.leaves()
        return {
            "families": len(self.families()),
            "nodes": len(self.nodes),
            "leaves": len(leaves),
            "aliases": len([n for n in self.nodes.values() if n.is_alias]),
            **{
                status: len([n for n in leaves if n.status == status])
                for status in self.statuses
            },
        }

    def by_engine(self, status: str | None = None) -> dict[str, list[Node]]:
        """Leaves grouped by the engine they need -- the roadmap, in one call."""
        grouped: dict[str, list[Node]] = {engine: [] for engine in self.engines}
        for node in self.leaves():
            if status is None or node.status == status:
                grouped[node.engine].append(node)
        return grouped

    def to_dict(self) -> dict[str, Any]:
        """Serialisable form, for a dataset manifest to record what it was built against."""
        return {
            "version": self.version,
            "counts": self.counts(),
            "nodes": [node.to_dict() for node in self.nodes.values()],
        }

    def validate(self) -> list[str]:
        """Editorial checks: things that load fine and are still probably wrong.

        Structure is enforced at load time -- a bad id or a dangling `same_as`
        raises there, because a half-loaded tree is worse than none. What is
        left over is judgement: a family with one child, a `ready` type whose
        engine was never built. `make taxonomy --check` reports these; nothing
        fails because of them.
        """
        problems: list[str] = []
        for family in self.families():
            if len(family.children) < 2:
                problems.append(
                    f"{family.id}: a family with {len(family.children)} child is a "
                    f"leaf wearing a hat; either add siblings or move it"
                )
        for node in self.leaves():
            if node.status == "ready" and not self.engines[node.engine].get("built"):
                problems.append(
                    f"{node.id}: status ready but engine {node.engine!r} is not built"
                )
        numbers = [family.number for family in self.families()]
        if numbers != list(range(1, len(numbers) + 1)):
            problems.append(
                f"family numbers are {numbers}, expected 1..{len(numbers)} with no gaps"
            )
        return problems


def _did_you_mean(wanted: str, nodes: dict[str, Node]) -> str:
    """A short list of near misses. An error about one of a hundred ids needs it."""
    tail = wanted.split(".")[-1]
    near = [
        node.id for node in nodes.values()
        if tail and (tail in node.id or tail in node.name.lower())
    ][:6]
    return f"; did you mean {', '.join(near)}?" if near else ""


# ------------------------------------------------------------------ loading


def _require_mapping(raw: Any, where: str) -> dict:
    if not isinstance(raw, dict):
        raise TaxonomyError(f"{where}: expected a mapping, got {type(raw).__name__}")
    return raw


def _reject_unknown(raw: dict, allowed: set[str], where: str) -> None:
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise TaxonomyError(
            f"{where}: unknown keys {unknown}; allowed are {sorted(allowed)}"
        )


def _text(raw: dict, key: str) -> str:
    value = raw.get(key)
    return " ".join(str(value).split()) if value is not None else ""


def _walk(raw: dict, parent: Node | None, statuses: set[str], engines: set[str],
          where: str, out: dict[str, Node], pending_aliases: list[tuple[str, str]]) -> Node:
    """Parse one node and its children into `out`, depth first."""
    raw = _require_mapping(raw, where)
    is_alias = "same_as" in raw
    allowed = ALIAS_KEYS if is_alias else (FAMILY_KEYS if parent is None else NODE_KEYS)
    _reject_unknown(raw, allowed, where)

    slug = str(raw.get("id") or "")
    if not ID_PATTERN.match(slug):
        raise TaxonomyError(
            f"{where}: id {slug!r} must be lower-case letters, digits and "
            f"underscores, starting with a letter"
        )
    node_id = f"{parent.id}.{slug}" if parent else slug
    if node_id in out:
        raise TaxonomyError(f"{where}: duplicate id {node_id!r}")

    name = _text(raw, "name")
    if not name:
        raise TaxonomyError(f"{where}: {node_id} has no name")

    if is_alias:
        # Everything else is the canonical node's to say. Filled in by
        # `_link_aliases` once the whole tree is present, since `same_as`
        # points across families and the target may not be loaded yet.
        node = Node(
            id=node_id, slug=slug, name=name, name_vi="", status="", engine="",
            parent=parent.id if parent else "", same_as=str(raw["same_as"]).strip(),
            notes=_text(raw, "notes"),
            names=(parent.names if parent else ()) + (name,),
        )
        out[node_id] = node
        pending_aliases.append((node_id, where))
        return node

    name_vi = _text(raw, "name_vi")
    if not name_vi:
        raise TaxonomyError(
            f"{where}: {node_id} has no name_vi. Every type carries both names -- "
            f"the English one identifies it in code and labels, the Vietnamese one "
            f"is what a person reading a report about Vietnamese documents needs"
        )

    status = str(raw.get("status") or (parent.status if parent else "planned"))
    if status not in statuses:
        raise TaxonomyError(
            f"{where}: {node_id} has status {status!r}; allowed are {sorted(statuses)}")
    engine = str(raw.get("engine") or (parent.engine if parent else ""))
    if engine not in engines:
        raise TaxonomyError(
            f"{where}: {node_id} needs an engine ({sorted(engines)}), got {engine!r}")

    number = raw.get("number")
    if parent is None:
        if number is None:
            raise TaxonomyError(f"{where}: family {node_id} has no number")
        number = int(number)
    elif number is not None:
        raise TaxonomyError(f"{where}: only a family carries a number, {node_id} does not")

    node = Node(
        id=node_id, slug=slug, name=name, name_vi=name_vi, status=status,
        engine=engine, parent=parent.id if parent else "", number=number,
        notes=_text(raw, "notes"),
        names=(parent.names if parent else ()) + (name,),
    )
    out[node_id] = node

    children = raw.get("children") or []
    if not isinstance(children, list):
        raise TaxonomyError(f"{where}: {node_id} children must be a list")
    child_ids = []
    for index, child in enumerate(children):
        child_node = _walk(child, node, statuses, engines,
                           f"{where}[{node_id}.children[{index}]]", out, pending_aliases)
        child_ids.append(child_node.id)
    if child_ids:
        out[node_id] = Node(**{**node.__dict__, "children": tuple(child_ids)})
    return out[node_id]


def _link_aliases(out: dict[str, Node], pending: list[tuple[str, str]]) -> None:
    """Point each alias at its canonical node and inherit what it does not own."""
    for node_id, where in pending:
        node = out[node_id]
        target = out.get(node.same_as)
        if target is None:
            raise TaxonomyError(
                f"{where}: {node_id} is same_as {node.same_as!r}, which does not exist"
                + _did_you_mean(node.same_as, out)
            )
        if target.same_as:
            raise TaxonomyError(
                f"{where}: {node_id} points at {target.id}, which is itself an alias; "
                f"point both at the canonical node instead"
            )
        if target.children:
            raise TaxonomyError(
                f"{where}: {node_id} points at {target.id}, which has children; "
                f"an alias stands for one document, not a branch"
            )
        if target.family == node.family:
            raise TaxonomyError(
                f"{where}: {node_id} and {target.id} are in the same family. Two names "
                f"for one document inside one family is a duplicate, not an alias"
            )
        if target.name != node.name:
            raise TaxonomyError(
                f"{where}: {node_id} is named {node.name!r} but points at "
                f"{target.id}, named {target.name!r}. An alias is the same document "
                f"filed twice, so the names have to agree"
            )
        out[node_id] = Node(**{
            **node.__dict__,
            "name_vi": target.name_vi,
            "status": target.status,
            "engine": target.engine,
        })


def _check_unique_names(out: dict[str, Node]) -> None:
    """A display name may repeat only between an alias and its canonical node."""
    by_name: dict[str, list[Node]] = {}
    for node in out.values():
        by_name.setdefault(node.name.lower(), []).append(node)
    for name, nodes in sorted(by_name.items()):
        if len(nodes) < 2:
            continue
        ids = {node.id for node in nodes}
        # Legal shape: exactly one canonical node, every other one an alias
        # pointing at it. Three places could file the same document; what is
        # never allowed is two nodes with one name and no link between them.
        canonical = [node for node in nodes if not node.same_as]
        aliases = [node for node in nodes if node.same_as]
        if len(canonical) == 1 and all(a.same_as == canonical[0].id for a in aliases):
            continue
        raise TaxonomyError(
            f"the name {nodes[0].name!r} is used by {', '.join(sorted(ids))}. If they "
            f"are the same document filed twice, declare `same_as` on all but one; if "
            f"they are different documents, give them names that say how they differ"
        )


def load(root: Path | str = TAXONOMY_ROOT) -> Taxonomy:
    """Read `document.yaml` and every `families/*.yaml` into one tree.

    Strict on purpose, in the same way `rulebase.spec` is strict about rules
    files: a hierarchy that half-loads is a coverage report that lies. The
    editorial checks that are judgement calls rather than errors live in
    `Taxonomy.validate()`.
    """
    root = Path(root)
    root_path = root / ROOT_FILE
    if not root_path.exists():
        raise TaxonomyError(f"missing {root_path}: it declares the statuses and engines")
    meta = _require_mapping(
        yaml.safe_load(root_path.read_text(encoding="utf-8")) or {}, str(root_path))
    _reject_unknown(meta, ROOT_KEYS, str(root_path))

    statuses = _require_mapping(meta.get("statuses") or {}, f"{root_path}: statuses")
    engines_raw = _require_mapping(meta.get("engines") or {}, f"{root_path}: engines")
    if not statuses or not engines_raw:
        raise TaxonomyError(f"{root_path}: statuses and engines are both required")
    engines = {
        name: _require_mapping(body, f"{root_path}: engines.{name}")
        for name, body in engines_raw.items()
    }
    root_meta = _require_mapping(meta.get("root") or {}, f"{root_path}: root")

    family_dir = root / FAMILIES_DIR
    files = sorted(family_dir.glob("*.yaml"))
    if not files:
        raise TaxonomyError(f"no family files in {family_dir}")

    nodes: dict[str, Node] = {}
    pending: list[tuple[str, str]] = []
    for path in files:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        _walk(raw, None, set(statuses), set(engines), str(path), nodes, pending)

    _link_aliases(nodes, pending)
    _check_unique_names(nodes)

    numbers = [node.number for node in nodes.values() if node.is_family]
    if len(set(numbers)) != len(numbers):
        raise TaxonomyError(f"two families share a number: {sorted(numbers)}")

    return Taxonomy(
        version=str(meta.get("version") or "0"),
        root_name=str(root_meta.get("name") or "Document"),
        root_name_vi=str(root_meta.get("name_vi") or ""),
        statuses={str(k): str(v) for k, v in statuses.items()},
        engines=engines,
        nodes=nodes,
        source=root,
    )


@lru_cache(maxsize=4)
def _cached(root: str) -> Taxonomy:
    return load(Path(root))


def tree(root: Path | str = TAXONOMY_ROOT) -> Taxonomy:
    """`load`, memoised. What callers that only read the shipped tree should use."""
    return _cached(str(Path(root)))


# Module-level shorthands, so a one-line question stays a one-line call.

def node(node_id: str) -> Node:
    return tree().node(node_id)


def resolve(query: str) -> Node:
    return tree().resolve(query)


def leaves(under: str | None = None) -> list[Node]:
    return tree().leaves(under)


def families() -> list[Node]:
    return tree().families()


def select(include: Sequence[str] | None = None, exclude: Sequence[str] = (),
           status: Sequence[str] | None = None) -> list[Node]:
    return tree().select(include, exclude, status)


__all__ = [
    "FAMILIES_DIR",
    "Node",
    "ROOT_FILE",
    "TAXONOMY_ROOT",
    "Taxonomy",
    "TaxonomyError",
    "families",
    "leaves",
    "load",
    "node",
    "resolve",
    "select",
    "tree",
]
