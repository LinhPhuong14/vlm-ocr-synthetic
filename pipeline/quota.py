"""How many images each document type gets.

    from pipeline.quota import allocate, strata
    allocate(100, ["business.receipt.retail", "business.receipt.restaurant"])
        -> [('business.receipt.retail', 50), ('business.receipt.restaurant', 50)]

Balancing a dataset over a hierarchy is not the same problem as balancing it
over a flat list, and the difference is the reason this is its own module rather
than three lines in the planner.

**Why `family` is the default.** The tree is lopsided by nature: sixteen types
under Structured Business Document, six under Log. Splitting evenly over the
*leaves* hands business nearly three times the images of log, not because
business documents are three times as common or three times as hard, but because
somebody drew the tree with more branches on one side. Splitting evenly over the
families first and then within each family gives every family the same budget,
which is what "a balanced document dataset" almost always means. `equal` and
`weight` are there for when it does not.

**Every mode is deterministic.** Two runs of the same config produce the same
counts in the same order, remainders included -- a plan that shuffles is a plan
you cannot diff against the last one. Remainders go to the first types in
declaration order, the same rule `split_by_layout` has always used for layouts.

**Zero is a result, not an omission.** Asking for 5 images across 98 types
cannot give every type an image. The allocation returns the zeros instead of
dropping them, so the caller can say how many types got nothing rather than
quietly producing a dataset that covers a twentieth of the tree.
"""

from __future__ import annotations

from typing import Any, Iterable, Sequence

BALANCES = ("family", "equal", "weight")
DEFAULT_BALANCE = "family"


class QuotaError(ValueError):
    """The run asks for a share of the tree that cannot be given."""


def even_split(total: int, count: int) -> list[int]:
    """`total` over `count` shares, remainder to the front. Deterministic."""
    if count <= 0:
        return []
    base, extra = divmod(max(0, total), count)
    return [base + (1 if index < extra else 0) for index in range(count)]


def _family_of(node_id: str) -> str:
    return node_id.split(".")[0]


def _largest_remainder(total: int, weights: Sequence[float]) -> list[int]:
    """Apportion `total` in proportion to `weights`, exactly.

    Rounding each share independently loses or invents images -- 3 shares of
    33.3% of 100 is 99. Largest-remainder hands out the floors first and then
    the leftover one at a time, biggest fractional part first, ties to the
    earlier entry so the answer does not depend on sort stability.
    """
    if not weights:
        return []
    mass = float(sum(weights))
    if mass <= 0:
        return even_split(total, len(weights))
    exact = [total * weight / mass for weight in weights]
    shares = [int(value) for value in exact]
    remaining = total - sum(shares)
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] - shares[i]), i))
    for index in order[:remaining]:
        shares[index] += 1
    return shares


def allocate(total: int, node_ids: Sequence[str], balance: str = DEFAULT_BALANCE,
             weights: dict[str, float] | None = None) -> list[tuple[str, int]]:
    """`[(document type, images), ...]` for one backend, in the order given.

    `weights` is only read by `balance="weight"`; a type missing from it counts
    as 1 so that a partially weighted config is still a whole allocation.
    """
    if balance not in BALANCES:
        raise QuotaError(f"balance: expected one of {list(BALANCES)}, got {balance!r}")
    if total < 0:
        raise QuotaError(f"cannot allocate {total} images")
    node_ids = list(node_ids)
    if not node_ids:
        raise QuotaError("no document types to allocate over; nothing would be drawn")

    if balance == "equal":
        return list(zip(node_ids, even_split(total, len(node_ids))))

    if balance == "weight":
        weights = weights or {}
        return list(zip(node_ids, _largest_remainder(
            total, [float(weights.get(node_id, 1.0)) for node_id in node_ids])))

    # family: equal per family, then equal within it. Families keep the order
    # they first appear in, so the allocation reads down the tree.
    families: dict[str, list[str]] = {}
    for node_id in node_ids:
        families.setdefault(_family_of(node_id), []).append(node_id)
    per_family = even_split(total, len(families))

    quota: dict[str, int] = {}
    for (family, members), share in zip(families.items(), per_family):
        quota.update(zip(members, even_split(share, len(members))))
    return [(node_id, quota[node_id]) for node_id in node_ids]


def rule_weights(rules: dict[str, list[Any]]) -> dict[str, float]:
    """Per document type, the total weight of the rules values that produce it.

    What `balance="weight"` apportions by: the mix the rules already describe,
    scaled up to a whole run. A type produced by three values of weight 3, 3 and
    2 is asked for four times as often as one produced by a single value of
    weight 2 -- which is exactly what an unpinned draw would do.
    """
    found: dict[str, float] = {}
    for options in rules.values():
        for option in options:
            if option.doc_type and option.weight > 0:
                found[option.doc_type] = found.get(option.doc_type, 0.0) + option.weight
    return found


def select_types(config) -> tuple[list[tuple[str, int]], list[str]]:
    """The config's `taxonomy:` section -> `([(type, images)], skipped)`.

    Where the three sources of truth meet: the tree says which types exist and
    which slice was asked for, the rules and the builders say which of those can
    actually be drawn, and `allocate` divides the run between them.

    A type that cannot be generated is dropped with its name reported, *unless*
    the config named it directly -- `include: [prescription]` is a request for
    prescriptions, and quietly giving back receipts instead would be the worst
    possible answer. Asking for a whole family and getting the ready part of it
    is reasonable; asking for one type and getting something else is not.
    """
    import taxonomy
    from rulebase.documents import coverage
    from rulebase.spec import load_rules

    tree = taxonomy.tree()
    section = config.taxonomy or {}
    include = list(section.get("include") or []) or None
    exclude = list(section.get("exclude") or [])
    balance = str(section.get("balance") or DEFAULT_BALANCE)

    wanted = tree.select(include, exclude)
    if not wanted:
        raise QuotaError(
            f"taxonomy.include={include} and exclude={exclude} leave no document "
            f"types at all")

    can_build = coverage()
    for pattern in include or []:
        node = tree.resolve(pattern)
        state = can_build.get(node.id, {})
        if node.is_leaf and not state.get("generatable"):
            lacks = " and ".join(
                part for part, present in
                (("no rules value produces it", state.get("rules")),
                 ("no builder is registered for it", state.get("builder")))
                if not present)
            raise QuotaError(
                f"taxonomy.include names {node.id}, which cannot be generated yet: "
                f"{lacks}. `make taxonomy` lists what is ready")

    ready = [node.id for node in wanted if can_build.get(node.id, {}).get("generatable")]
    skipped = [node.id for node in wanted if node.id not in set(ready)]
    if not ready:
        raise QuotaError(
            f"none of the {len(wanted)} document types selected can be generated yet. "
            f"`make taxonomy` shows which ones are ready and what each of the others "
            f"is waiting for")

    weights = rule_weights(load_rules()) if balance == "weight" else None
    return allocate(config.per_backend, ready, balance, weights), skipped


def strata(node_ids: Sequence[str], counts: Iterable[int],
           layouts_for) -> list[tuple[str, str, int]]:
    """`[(doc type, layout, images), ...]` -- the units a plan is built from.

    A type's images are spread over the layouts that type can legally have,
    which `layouts_for` computes from the rules. Two reasons not to simply let
    the sampler pick:

    * A layout with a small weight can go unseen in a short run. The committed
      datasets have always pinned layouts for this reason, and a hierarchy makes
      it worse rather than better -- there are now more ways to be unlucky.
    * `market_barcode` is not drawable for a restaurant receipt at all. Pinning
      a type and a layout that contradict each other is a run that fails deep
      into rendering, so the pairs are computed here, once, from the rules.

    A type with no drawable layout is an error rather than a skip: it means the
    rules realise the type and no layout admits it, which is a rule-base bug
    that a silently shorter dataset would hide.
    """
    found: list[tuple[str, str, int]] = []
    for node_id, count in zip(node_ids, counts):
        if count <= 0:
            continue
        layouts = list(layouts_for(node_id))
        if not layouts:
            raise QuotaError(
                f"{node_id}: no layout can be drawn for this document type. Its rules "
                f"exist but every layout excludes it -- check requires/excludes in "
                f"rules/layout.yaml"
            )
        for layout, share in zip(layouts, even_split(count, len(layouts))):
            if share:
                found.append((node_id, layout, share))
    return found


__all__ = [
    "BALANCES",
    "DEFAULT_BALANCE",
    "QuotaError",
    "allocate",
    "even_split",
    "rule_weights",
    "select_types",
    "strata",
]
