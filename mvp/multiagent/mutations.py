"""Graph mutation: propose, authorise, stage, release, commit.

Why agents cannot write to the graph
------------------------------------
A wrong *value* update is a bad number. A wrong *structural* mutation is a wrong
business. Adding a cost line that does not exist silently changes every margin
downstream, and nothing in the current model would flag it — the projections
would simply be computed against a business that isn't real. So no agent holds a
reference it can write through. Every change is a proposal, and the graph is only
ever moved by ``commit()``, which records what it replaced.

The five stages
---------------
1. **Propose** — an agent emits a ``GraphMutation`` with a rationale and the
   evidence ids that justify it. Nothing happens to the graph.
2. **Authorise** — checked *before* the agent does further work, not after. This
   is the cheap-gate lesson from ai-employees' ``guard.mjs``: a refusal that costs
   three small reads is nearly free, a refusal discovered after an agent has
   assembled context and burned a run is not.
3. **Stage** — the mutation lands in a queue the owner can open and read. It is
   never applied on proposal.
4. **Release** — structural changes always require an explicit owner release.
   Value updates inside a bounded band may auto-apply, because they are
   reversible and cheap to audit.
5. **Commit** — apply to the graph with provenance: who proposed, on what
   evidence, and what the previous value was.

The asymmetry is the point
--------------------------
Auto-applying a value inside a band is safe because the blast radius is one
number and the ledger holds the old one. Auto-applying a structural change is
not, because the blast radius is every metric computed from the graph. The band
exists so routine numeric drift does not need a human, while a new node or a
deleted revenue stream always does.
"""

from __future__ import annotations

import json
import pathlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from ..model.core import BaseNode, BusinessGraph, NodeType
from .interop import Reversibility

DATA_ROOT = pathlib.Path(__file__).resolve().parents[2] / "data"


class MutationKind(str, Enum):
    ADD_NODE = "add_node"
    REMOVE_NODE = "remove_node"
    UPDATE_VALUE = "update_value"
    ADD_EDGE = "add_edge"
    REMOVE_EDGE = "remove_edge"
    RELABEL_NODE = "relabel_node"


class MutationStatus(str, Enum):
    PROPOSED = "proposed"
    REJECTED = "rejected"
    STAGED = "staged"          # awaiting owner release
    COMMITTED = "committed"
    FAILED = "failed"


#: Kinds that change the *shape* of the business. These always need a release.
STRUCTURAL_KINDS = frozenset({
    MutationKind.ADD_NODE,
    MutationKind.REMOVE_NODE,
    MutationKind.ADD_EDGE,
    MutationKind.REMOVE_EDGE,
})

#: Kinds that adjust a value already in the graph. Reversible, so a bounded
#: change may auto-apply.
VALUE_KINDS = frozenset({MutationKind.UPDATE_VALUE, MutationKind.RELABEL_NODE})


class MutationRefused(PermissionError):
    """Raised when a proposal is not authorised. Carries the reason."""


@dataclass
class MutationPolicy:
    """What a tenant permits an agent to change, and how much.

    Defaults are deliberately narrow: no structural change is automatic, and a
    value may only drift by ``auto_apply_max_pct`` percent without a release.
    """

    #: Largest relative value change that may auto-apply. 0 disables auto-apply.
    auto_apply_max_pct: float = 10.0
    #: Kinds this tenant permits at all.
    allowed_kinds: List[str] = field(default_factory=lambda: [k.value for k in MutationKind])
    #: Structural changes always need a release, regardless of size.
    require_release_for_structural: bool = True
    #: Proposals per period, enforced before context is assembled.
    max_proposals_per_period: int = 50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "auto_apply_max_pct": self.auto_apply_max_pct,
            "allowed_kinds": list(self.allowed_kinds),
            "require_release_for_structural": self.require_release_for_structural,
            "max_proposals_per_period": self.max_proposals_per_period,
        }


@dataclass
class GraphMutation:
    """A proposed change to a tenant's business graph."""

    kind: str
    tenant_id: str
    node_id: str
    rationale: str = ""
    evidence_ids: List[str] = field(default_factory=list)
    proposed_by: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"mut_{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    status: str = MutationStatus.PROPOSED.value
    #: Filled at commit.
    previous_value: Optional[float] = None
    committed_at: Optional[str] = None
    released_by: Optional[str] = None

    @property
    def is_structural(self) -> bool:
        return self.kind in {k.value for k in STRUCTURAL_KINDS}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "tenant_id": self.tenant_id,
            "node_id": self.node_id,
            "rationale": self.rationale,
            "evidence_ids": list(self.evidence_ids),
            "proposed_by": self.proposed_by,
            "payload": dict(self.payload),
            "created_at": self.created_at,
            "status": self.status,
            "structural": self.is_structural,
            "previous_value": self.previous_value,
            "committed_at": self.committed_at,
            "released_by": self.released_by,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "GraphMutation":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        return cls(**{k: v for k, v in d.items() if k in known})


@dataclass
class Authorisation:
    """The pre-context decision. Cheap, pure, explains itself."""

    allowed: bool
    reason: str = ""
    auto_apply: bool = False
    requires_release: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "auto_apply": self.auto_apply,
            "requires_release": self.requires_release,
        }


def _parse_kind(kind: Any) -> str:
    if isinstance(kind, MutationKind):
        return kind.value
    return str(kind)


def authorise(
    mutation: GraphMutation,
    graph: BusinessGraph,
    policy: Optional[MutationPolicy] = None,
    proposals_this_period: int = 0,
) -> Authorisation:
    """Decide whether a proposal may proceed, before any expensive work.

    Pure and cheap by design: no I/O, no model calls, no context assembly. Call
    it first. A refusal here costs nothing; a refusal discovered after an agent
    has run costs the whole run.
    """
    policy = policy or MutationPolicy()
    kind = _parse_kind(mutation.kind)

    if kind not in policy.allowed_kinds:
        return Authorisation(False, f"tenant policy does not permit {kind!r}")

    if proposals_this_period >= policy.max_proposals_per_period:
        return Authorisation(
            False,
            f"proposal quota exhausted "
            f"({proposals_this_period}/{policy.max_proposals_per_period} this period)",
        )

    if not mutation.tenant_id:
        return Authorisation(False, "mutation has no tenant")

    if not mutation.rationale.strip():
        return Authorisation(False, "mutation has no rationale")

    existing = graph.get(mutation.node_id)

    # Existence rules per kind. Getting these wrong is how a graph silently
    # acquires two nodes with one id, or loses a parent link nobody noticed.
    if kind in {MutationKind.UPDATE_VALUE.value, MutationKind.RELABEL_NODE.value,
                MutationKind.REMOVE_NODE.value}:
        if existing is None:
            return Authorisation(False, f"node {mutation.node_id!r} does not exist")
    elif kind == MutationKind.ADD_NODE.value:
        if existing is not None:
            return Authorisation(False, f"node {mutation.node_id!r} already exists")

    if kind == MutationKind.ADD_EDGE.value:
        parent = mutation.payload.get("parent")
        child = mutation.payload.get("child")
        if not parent or not child:
            return Authorisation(False, "add_edge needs payload.parent and payload.child")
        if graph.get(parent) is None:
            return Authorisation(False, f"parent {parent!r} does not exist")
        if graph.get(child) is None:
            return Authorisation(False, f"child {child!r} does not exist")
        if child in (graph.get(parent).children or []):
            return Authorisation(False, f"edge {parent!r} -> {child!r} already exists")

    if kind == MutationKind.REMOVE_EDGE.value:
        parent = mutation.payload.get("parent")
        child = mutation.payload.get("child")
        if not parent or not child:
            return Authorisation(False, "remove_edge needs payload.parent and payload.child")
        pnode = graph.get(parent)
        if pnode is None or child not in (pnode.children or []):
            return Authorisation(False, f"edge {parent!r} -> {child!r} does not exist")

    if kind == MutationKind.ADD_NODE.value:
        nt = mutation.payload.get("node_type")
        if nt and nt not in {t.value for t in NodeType}:
            return Authorisation(False, f"unknown node_type {nt!r}")
        if not mutation.evidence_ids:
            # A new node claims something exists. That claim needs a source.
            return Authorisation(False, "adding a node requires at least one evidence id")
        # A node attached to nothing is invisible to every traversal and every
        # metric. Either it hangs off something real, or it is declared a root.
        parent = mutation.payload.get("parent")
        if parent:
            if graph.get(parent) is None:
                return Authorisation(False, f"parent {parent!r} does not exist")
        elif not mutation.payload.get("root"):
            return Authorisation(
                False,
                "add_node needs payload.parent, or payload.root=true for a "
                "level-0 node — an unattached node is unreachable by traversal",
            )

    if kind == MutationKind.REMOVE_NODE.value:
        if not mutation.evidence_ids:
            return Authorisation(False, "removing a node requires at least one evidence id")
        # Removing a parent orphans its children: they stay in the graph with no
        # link, contributing to no total and appearing in no drill-down. Deleting
        # has to be explicit about what happens to the contents.
        orphans = [c for c in (existing.children or []) if c in graph.nodes]
        if orphans and not mutation.payload.get("detach_children"):
            return Authorisation(
                False,
                f"removing {mutation.node_id!r} would orphan {len(orphans)} child "
                f"node(s) {orphans[:4]}. Re-parent them first, or set "
                f"payload.detach_children=true to accept the orphaning.",
            )

    # Classification: structural always needs release; values may auto-apply
    # inside the band, and stage outside it.
    if mutation.is_structural:
        if policy.require_release_for_structural:
            return Authorisation(True, "structural change staged for release",
                                 auto_apply=False, requires_release=True)
        return Authorisation(True, "structural change permitted", auto_apply=True,
                             requires_release=False)

    if kind == MutationKind.UPDATE_VALUE.value:
        if existing is None:
            return Authorisation(False, f"node {mutation.node_id!r} does not exist")
        try:
            new_value = float(mutation.payload.get("value"))
        except (TypeError, ValueError):
            return Authorisation(False, "update_value needs a numeric payload.value")
        old = float(getattr(existing, "value", 0.0) or 0.0)
        # Relative to zero there is no meaningful percentage, so any change from
        # a zero baseline is treated as unbounded and must be released.
        if old == 0.0:
            if new_value == 0.0:
                return Authorisation(True, "no change", auto_apply=False,
                                     requires_release=False)
            return Authorisation(True, "change from a zero baseline needs a release",
                                 auto_apply=False, requires_release=True)
        pct = abs(new_value - old) / abs(old) * 100.0
        if pct <= policy.auto_apply_max_pct:
            return Authorisation(True, f"value change {pct:.2f}% within band",
                                 auto_apply=True, requires_release=False)
        return Authorisation(True, f"value change {pct:.2f}% exceeds band",
                             auto_apply=False, requires_release=True)

    if kind == MutationKind.RELABEL_NODE.value:
        if not mutation.payload.get("label"):
            return Authorisation(False, "relabel_node needs payload.label")
        return Authorisation(True, "relabel is reversible", auto_apply=True,
                             requires_release=False)

    # Nothing else is known. Treating an unrecognised kind as a benign relabel
    # is how a typo in a mechanism name silently ships an unintended change.
    return Authorisation(False, f"unknown mutation kind {kind!r}")


class MutationQueue:
    """File-backed staging area plus an append-only ledger.

    Staged proposals are plain JSON files the owner can open — the same idea as
    ai-employees staging an unsent draft in the mailbox rather than sending it.
    The ledger is append-only and never rewritten, so a later commit cannot erase
    what an earlier one replaced.
    """

    def __init__(self, tenant_id: str, data_root: Optional[pathlib.Path] = None) -> None:
        self.tenant_id = tenant_id
        root = pathlib.Path(data_root) if data_root else DATA_ROOT
        self.base = root / tenant_id / "mutations"
        self.pending = self.base / "pending"
        self.ledger = self.base / "ledger.jsonl"
        self.policy_path = self.base / "policy.json"

    # -- policy ----------------------------------------------------------

    def load_policy(self) -> MutationPolicy:
        if not self.policy_path.exists():
            return MutationPolicy()
        raw = json.loads(self.policy_path.read_text())
        known = {f for f in MutationPolicy.__dataclass_fields__}  # type: ignore[attr-defined]
        return MutationPolicy(**{k: v for k, v in raw.items() if k in known})

    def save_policy(self, policy: MutationPolicy) -> pathlib.Path:
        self.base.mkdir(parents=True, exist_ok=True)
        self.policy_path.write_text(json.dumps(policy.to_dict(), indent=2) + "\n")
        return self.policy_path

    # -- propose ---------------------------------------------------------

    def propose(self, mutation: GraphMutation) -> GraphMutation:
        """Record a proposal. Does not touch the graph."""
        if mutation.tenant_id != self.tenant_id:
            raise MutationRefused(
                f"mutation belongs to tenant {mutation.tenant_id!r}, "
                f"queue is for {self.tenant_id!r}"
            )
        self.pending.mkdir(parents=True, exist_ok=True)
        mutation.status = MutationStatus.PROPOSED.value
        self._write(mutation)
        return mutation

    def _write(self, mutation: GraphMutation) -> pathlib.Path:
        path = self.pending / f"{mutation.id}.json"
        path.write_text(json.dumps(mutation.to_dict(), indent=2) + "\n")
        return path

    # -- read ------------------------------------------------------------

    def staged(self) -> List[GraphMutation]:
        """Proposals awaiting a decision, oldest first."""
        if not self.pending.exists():
            return []
        out = []
        for p in sorted(self.pending.glob("*.json")):
            try:
                out.append(GraphMutation.from_dict(json.loads(p.read_text())))
            except (ValueError, OSError, TypeError):
                continue
        out.sort(key=lambda m: m.created_at)
        return out

    def proposals_this_period(self) -> int:
        return len(self.staged())

    def history(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.ledger.exists():
            return []
        lines = self.ledger.read_text().splitlines()
        out = []
        for line in lines[-limit:]:
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
        return out

    # -- decide ----------------------------------------------------------

    def reject(self, mutation_id: str, reason: str = "") -> GraphMutation:
        m = self._load(mutation_id)
        m.status = MutationStatus.REJECTED.value
        self._append_ledger({"event": "rejected", "id": m.id, "reason": reason,
                             "at": _now()})
        self._remove(mutation_id)
        return m

    def release(self, mutation_id: str, released_by: str) -> GraphMutation:
        """Owner approves a staged change. Marks it released, not applied."""
        m = self._load(mutation_id)
        m.status = MutationStatus.STAGED.value
        m.released_by = released_by
        self._write(m)
        self._append_ledger({"event": "released", "id": m.id, "by": released_by,
                             "at": _now()})
        return m

    def _load(self, mutation_id: str) -> GraphMutation:
        path = self.pending / f"{mutation_id}.json"
        if not path.exists():
            raise KeyError(f"no staged mutation {mutation_id!r} for {self.tenant_id!r}")
        return GraphMutation.from_dict(json.loads(path.read_text()))

    # -- commit ----------------------------------------------------------

    def commit(self, mutation_id: str, graph: BusinessGraph,
               committed_by: str = "owner") -> GraphMutation:
        """Apply a released mutation to ``graph`` with provenance.

        Refuses if the mutation was not released, or if it has already been
        committed — the ledger is the record of truth and a double commit would
        make ``previous_value`` a lie.
        """
        if self._already_committed(mutation_id):
            raise MutationRefused(
                f"mutation {mutation_id!r} was already committed; refusing to "
                f"apply it twice"
            )
        m = self._load(mutation_id)
        if m.status != MutationStatus.STAGED.value or not m.released_by:
            raise MutationRefused(
                f"mutation {mutation_id!r} has not been released "
                f"(status={m.status!r})"
            )

        previous: Dict[str, Any] = {}
        try:
            previous = self._apply(m, graph)
        except Exception as exc:
            m.status = MutationStatus.FAILED.value
            self._write(m)
            self._append_ledger({"event": "failed", "id": m.id,
                                 "error": f"{type(exc).__name__}: {exc}", "at": _now()})
            raise

        m.status = MutationStatus.COMMITTED.value
        m.committed_at = _now()
        self._append_ledger({
            "event": "committed",
            "id": m.id,
            "tenant_id": self.tenant_id,
            "kind": m.kind,
            "node_id": m.node_id,
            "by": committed_by,
            "released_by": m.released_by,
            "proposed_by": m.proposed_by,
            "evidence_ids": list(m.evidence_ids),
            "rationale": m.rationale,
            "previous": previous,
            "at": m.committed_at,
        })
        self._remove(mutation_id)
        return m

    def _already_committed(self, mutation_id: str) -> bool:
        return any(h.get("event") == "committed" and h.get("id") == mutation_id
                   for h in self.history(limit=10_000))

    def _apply(self, m: GraphMutation, graph: BusinessGraph) -> Dict[str, Any]:
        """Mutate the graph, returning what was replaced."""
        kind = m.kind
        previous: Dict[str, Any] = {}

        if kind == MutationKind.ADD_NODE.value:
            p = m.payload
            nt = p.get("node_type", NodeType.PROCESS.value)
            node = BaseNode(
                id=m.node_id,
                label=p.get("label") or m.node_id,
                node_type=NodeType(nt) if isinstance(nt, str) else nt,
                value=float(p.get("value", 0.0) or 0.0),
                unit=p.get("unit", "GBP"),
                period=p.get("period", "monthly"),
                description=p.get("description", ""),
                level=int(p.get("level", 0) or 0),
                parent_group=p.get("parent_group"),
                tags=list(p.get("tags", [])),
                metadata={"provenance": _provenance(m)},
            )
            graph.add(node)
            # Wire into a parent if one was named, keeping both directions true.
            parent = p.get("parent")
            if parent and graph.get(parent) is not None:
                graph.get(parent).children.append(node.id)
                node.parents.append(parent)
                graph._adjacency.setdefault(parent, [])
                graph._adjacency[parent] = graph.get(parent).children[:]
                graph._reverse_adj.setdefault(node.id, [])
                graph._reverse_adj[node.id] = node.parents[:]
                graph.edges.append({"source": parent, "target": node.id,
                                    "kind": p.get("edge_kind", "composes")})

        elif kind == MutationKind.UPDATE_VALUE.value:
            node = graph.get(m.node_id)
            previous["value"] = float(getattr(node, "value", 0.0) or 0.0)
            node.value = float(m.payload["value"])
            meta = dict(getattr(node, "metadata", {}) or {})
            meta["provenance"] = _provenance(m)
            node.metadata = meta

        elif kind == MutationKind.RELABEL_NODE.value:
            node = graph.get(m.node_id)
            previous["label"] = node.label
            node.label = str(m.payload["label"])

        elif kind == MutationKind.ADD_EDGE.value:
            parent = graph.get(m.payload["parent"])
            child = graph.get(m.payload["child"])
            if m.payload["child"] not in parent.children:
                parent.children.append(m.payload["child"])
            if parent.id not in child.parents:
                child.parents.append(parent.id)
            graph._adjacency[parent.id] = parent.children[:]
            graph._reverse_adj[child.id] = child.parents[:]
            graph.edges.append({"source": parent.id, "target": child.id,
                                "kind": m.payload.get("edge_kind", "composes")})

        elif kind == MutationKind.REMOVE_EDGE.value:
            parent = graph.get(m.payload["parent"])
            child = graph.get(m.payload["child"])
            previous["edge"] = f"{parent.id} -> {child.id}"
            parent.children = [c for c in parent.children if c != child.id]
            child.parents = [p for p in child.parents if p != parent.id]
            graph._adjacency[parent.id] = parent.children[:]
            graph._reverse_adj[child.id] = child.parents[:]
            graph.edges = [e for e in graph.edges
                           if not (e.get("source") == parent.id
                                   and e.get("target") == child.id)]

        elif kind == MutationKind.REMOVE_NODE.value:
            node = graph.get(m.node_id)
            previous["node"] = node.to_dict()
            previous["orphaned_children"] = list(node.children)
            # Cascade: every edge referencing this node must go, on both sides,
            # or the graph keeps dangling ids that later traversals will follow.
            for parent_id in list(node.parents):
                p = graph.get(parent_id)
                if p is not None:
                    p.children = [c for c in p.children if c != node.id]
                    graph._adjacency[parent_id] = p.children[:]
            for child_id in list(node.children):
                c = graph.get(child_id)
                if c is not None:
                    c.parents = [p for p in c.parents if p != node.id]
                    graph._reverse_adj[child_id] = c.parents[:]
            graph.edges = [e for e in graph.edges
                           if e.get("source") != node.id and e.get("target") != node.id]
            graph.nodes.pop(node.id, None)
            graph._adjacency.pop(node.id, None)
            graph._reverse_adj.pop(node.id, None)
            graph.root_nodes = [r for r in graph.root_nodes if r != node.id]

        else:
            raise MutationRefused(f"unsupported mutation kind {kind!r}")

        return previous

    # -- ledger ----------------------------------------------------------

    def _append_ledger(self, entry: Dict[str, Any]) -> None:
        self.base.mkdir(parents=True, exist_ok=True)
        entry.setdefault("tenant_id", self.tenant_id)
        with self.ledger.open("a") as fh:
            fh.write(json.dumps(entry) + "\n")

    def _remove(self, mutation_id: str) -> None:
        path = self.pending / f"{mutation_id}.json"
        if path.exists():
            path.unlink()


def _provenance(m: GraphMutation) -> Dict[str, Any]:
    return {
        "mutation_id": m.id,
        "proposed_by": m.proposed_by,
        "released_by": m.released_by,
        "evidence_ids": list(m.evidence_ids),
        "rationale": m.rationale,
        "applied_at": _now(),
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "MutationKind",
    "MutationStatus",
    "MutationPolicy",
    "GraphMutation",
    "Authorisation",
    "MutationQueue",
    "MutationRefused",
    "authorise",
    "STRUCTURAL_KINDS",
    "VALUE_KINDS",
    "Reversibility",
]
