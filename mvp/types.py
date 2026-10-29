"""Hierarchical business-type registry.

A business type is a *template*, not a label. It declares the scaffold a tenant
of that type gets: which node families must exist, which canonical data fields
the graph needs, which specialists should run, and which benchmark population
the business is compared against. Child types inherit the parent's scaffold and
may add to it or override named attributes — a coffee shop is a retail business
with a menu and wastage; a developer-tools company is a SaaS business with usage
based pricing.

Why inheritance rather than flat types
--------------------------------------
Benchmarking needs a population. With flat types every new vertical starts with
a cohort of one and no reference distribution. With inheritance, a coffee shop
can fall back to the retail cohort until enough coffee shops exist. That is the
whole point of the hierarchy: *comparison depth* degrades gracefully upwards.

Resolution
----------
``resolve("coffee_shop")`` walks the ancestry, merges scaffolds parent-first,
and records the lineage. Later entries override scalar attributes; sets are
unioned so a child never accidentally drops a capability its parent declared
unless it explicitly names it in ``excludes``.

Adding a type
-------------
Register it in ``BUILTIN`` or put a JSON object in ``data/types.json`` (a list
under the key ``types``). A JSON type must name a parent that already exists;
validation runs on load and refuses cycles or dangling parents rather than
silently flattening them.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Set

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CUSTOM_PATH = os.path.join(PROJECT_ROOT, "data", "types.json")


class TypeRegistryError(Exception):
    """Raised for unknown types, dangling parents or inheritance cycles."""


@dataclass(frozen=True)
class TypeSpec:
    """One node in the type hierarchy."""

    id: str
    label: str
    parent: Optional[str] = None

    # Which loader builds a graph for this type. A child may inherit it.
    loader: Optional[str] = None

    # Node families the graph must contain. Families are stable identifiers the
    # loaders use (revenue, cogs, staff, overheads, ...), not node ids.
    node_families: Set[str] = field(default_factory=set)

    # Canonical fields the type needs from integrations (see data_gaps.py).
    canonical_fields: Set[str] = field(default_factory=set)

    # Families the child does not want even though the parent declares them.
    excludes: Set[str] = field(default_factory=set)

    # Which specialists should run for this type.
    specialists: Set[str] = field(default_factory=set)

    # Benchmark population to compare against. Falls back up the lineage.
    benchmark_cohort: Optional[str] = None

    # Presentation + starter-model metadata.
    icon: str = "📊"
    color: str = "#607d8b"
    period: str = "Starter model (monthly averages)"


@dataclass(frozen=True)
class ResolvedType:
    """A type with its whole ancestry merged in."""

    id: str
    label: str
    lineage: List[str]
    loader: str
    node_families: Set[str]
    canonical_fields: Set[str]
    specialists: Set[str]
    benchmark_cohort: Optional[str]
    icon: str
    color: str
    period: str

    @property
    def is_child(self) -> bool:
        return len(self.lineage) > 1

    def cohort_chain(self) -> List[str]:
        """Benchmark cohorts from most to least specific.

        The first entry is the type itself; the last is the broadest ancestor
        cohort. Callers use this to widen a peer group when the specific cohort
        is too thin to be meaningful.
        """
        # lineage is root-first; peer groups must widen from specific to broad.
        chain = [self.id] + list(reversed(self.lineage[:-1]))
        if self.benchmark_cohort and self.benchmark_cohort not in chain:
            chain.append(self.benchmark_cohort)
        seen: List[str] = []
        for c in chain:
            if c not in seen:
                seen.append(c)
        return seen


# ── Root and parent types ────────────────────────────────────────────────────
# Roots carry the loader and the broadest scaffold. They are never assigned to
# a tenant directly; they exist to be inherited from.
BUILTIN: Dict[str, TypeSpec] = {
    "business": TypeSpec(
        id="business",
        label="Any business",
        canonical_fields={"revenue", "cogs", "gross_margin"},
        specialists={"revenue", "cost"},
    ),
    # ── Physical retail ──
    "retail": TypeSpec(
        id="retail",
        label="Physical retail",
        parent="business",
        loader="cafe",
        node_families={"revenue", "cogs", "staff", "overheads", "gross_profit"},
        canonical_fields={"units", "visits_per_week", "avg_spend"},
        specialists={"revenue", "cost", "staffing", "operations"},
        benchmark_cohort="retail",
        icon="🛍",
        color="#8d6e63",
    ),
    "coffee_shop": TypeSpec(
        id="coffee_shop",
        label="Café / coffee shop",
        parent="retail",
        node_families={"menu", "wastage"},
        canonical_fields={"customer_segments"},
        specialists={"marketing"},
        benchmark_cohort="coffee_shop",
        icon="☕",
        color="#8d6e63",
    ),
    # ── SaaS ──
    "saas": TypeSpec(
        id="saas",
        label="SaaS / recurring software",
        parent="business",
        loader="saas",
        node_families={"revenue", "cogs", "gross_profit", "opex", "tiers"},
        canonical_fields={"adoption_rate", "customer_segments"},
        specialists={"revenue", "cost", "marketing", "operations"},
        benchmark_cohort="saas",
        icon="🧩",
        color="#5c6bc0",
    ),
    "developer_tools": TypeSpec(
        id="developer_tools",
        label="Developer tools",
        parent="saas",
        node_families={"usage", "self_serve_funnel"},
        canonical_fields={"volume_lift"},
        benchmark_cohort="developer_tools",
        icon="🛠",
        color="#3949ab",
    ),
    # ── Services and commerce ──
    "services": TypeSpec(
        id="services",
        label="Professional services",
        parent="business",
        loader="saas",
        node_families={"revenue", "cogs", "gross_profit", "opex", "staff"},
        canonical_fields={"units", "avg_spend"},
        specialists={"revenue", "cost", "staffing"},
        benchmark_cohort="services",
        icon="📐",
        color="#4db6ac",
    ),
    "ecommerce": TypeSpec(
        id="ecommerce",
        label="E-commerce",
        parent="retail",
        loader="saas",
        node_families={"fulfilment", "returns"},
        canonical_fields={"units", "visits_per_week", "avg_spend", "volume_lift"},
        specialists={"marketing"},
        benchmark_cohort="ecommerce",
        icon="🛒",
        color="#ff8a65",
    ),
}

_TYPES: Dict[str, TypeSpec] = dict(BUILTIN)
_loaded_custom = False


def _custom_specs() -> List[TypeSpec]:
    if not os.path.isfile(CUSTOM_PATH):
        return []
    with open(CUSTOM_PATH) as f:
        raw = json.load(f)
    entries = raw.get("types", []) if isinstance(raw, dict) else raw
    specs: List[TypeSpec] = []
    for e in entries:
        try:
            specs.append(
                TypeSpec(
                    id=e["id"],
                    label=e.get("label", e["id"]),
                    parent=e.get("parent"),
                    loader=e.get("loader"),
                    node_families=set(e.get("node_families", [])),
                    canonical_fields=set(e.get("canonical_fields", [])),
                    excludes=set(e.get("excludes", [])),
                    specialists=set(e.get("specialists", [])),
                    benchmark_cohort=e.get("benchmark_cohort"),
                    icon=e.get("icon", "📊"),
                    color=e.get("color", "#607d8b"),
                    period=e.get("period", "Starter model (monthly averages)"),
                )
            )
        except KeyError as exc:
            raise TypeRegistryError(f"type entry missing field {exc}") from exc
    return specs


def load_custom_types(force: bool = False) -> None:
    """Merge ``data/types.json`` into the registry once per process."""
    global _loaded_custom
    if _loaded_custom and not force:
        return
    for spec in _custom_specs():
        register(spec, overwrite=True)
    _loaded_custom = True
    validate()


def register(spec: TypeSpec, overwrite: bool = False) -> None:
    if spec.id in _TYPES and not overwrite:
        raise TypeRegistryError(f"type {spec.id!r} is already registered")
    _TYPES[spec.id] = spec


def get(type_id: str) -> TypeSpec:
    """Return the raw spec, loading custom types on first use."""
    load_custom_types()
    try:
        return _TYPES[type_id]
    except KeyError as exc:
        raise TypeRegistryError(f"unknown business type: {type_id!r}") from exc


def all_types(include_roots: bool = False) -> List[TypeSpec]:
    load_custom_types()
    out = [t for t in _TYPES.values() if include_roots or t.parent is not None]
    return sorted(out, key=lambda t: (t.parent or "", t.id))


def children_of(type_id: str) -> List[TypeSpec]:
    return sorted(
        (t for t in _TYPES.values() if t.parent == type_id), key=lambda t: t.id
    )


def lineage(type_id: str) -> List[str]:
    """Ancestry from root to the type itself, oldest first."""
    chain: List[str] = []
    cursor: Optional[str] = type_id
    guard = 0
    while cursor is not None:
        guard += 1
        if guard > 32:
            raise TypeRegistryError(f"inheritance cycle at {type_id!r}")
        spec = get(cursor)
        chain.append(spec.id)
        cursor = spec.parent
    return list(reversed(chain))


def validate() -> None:
    """Refuse dangling parents and cycles at load time, not at render time."""
    for spec in _TYPES.values():
        seen: Set[str] = set()
        cursor: Optional[str] = spec.id
        while cursor is not None:
            if cursor in seen:
                raise TypeRegistryError(f"inheritance cycle involving {spec.id!r}")
            seen.add(cursor)
            if cursor not in _TYPES:
                raise TypeRegistryError(
                    f"type {spec.id!r} has unknown parent {cursor!r}"
                )
            cursor = _TYPES[cursor].parent


def resolve(type_id: str) -> ResolvedType:
    """Merge a type with its ancestry and return the effective template."""
    chain = lineage(type_id)
    loader: Optional[str] = None
    families: Set[str] = set()
    fields_: Set[str] = set()
    specialists: Set[str] = set()
    cohort: Optional[str] = None

    # Parent-first so children override scalars and extend sets.
    for tid in chain:
        spec = get(tid)
        if spec.loader:
            loader = spec.loader
        families |= spec.node_families
        fields_ |= spec.canonical_fields
        specialists |= spec.specialists
        families -= spec.excludes
        fields_ -= spec.excludes
        if spec.benchmark_cohort:
            cohort = spec.benchmark_cohort

    leaf = get(type_id)
    if loader is None:
        raise TypeRegistryError(
            f"type {type_id!r} has no loader in its lineage; declare one on a parent"
        )

    return ResolvedType(
        id=leaf.id,
        label=leaf.label,
        lineage=chain,
        loader=loader,
        node_families=families,
        canonical_fields=fields_,
        specialists=specialists,
        benchmark_cohort=cohort,
        icon=leaf.icon,
        color=leaf.color,
        period=leaf.period,
    )


def loader_for(type_id: str) -> str:
    """The graph builder a tenant of this type should use."""
    return resolve(type_id).loader


def assert_scaffold(type_id: str, present: Iterable[str]) -> List[str]:
    """Return the node families a built graph is missing for its type.

    Used by tests and by provisioning verification: a template that claims a
    scaffold the loader cannot produce is a lie the benchmark layer would
    inherit, so it is surfaced early.
    """
    required = resolve(type_id).node_families
    have = set(present)
    return sorted(required - have)
