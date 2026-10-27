"""Autonomous Graph Controller — human-in-the-loop orchestration.

The controller sits above the specialist roster and the arbiter. It is *stateful*:
it holds a pending diagnosis / dispatch / approval across API calls so that a
human can review at two distinct gates before anything executes.

State machine
-------------
    IDLE
      │  diagnose(graph)
      ▼
    DIAGNOSED            ← Gate 1: user reviews unhealthy branches + which
      │  dispatch(specialist_ids)      specialists to spin up
      ▼
    DISPATCHED           ← Gate 2: user reviews hypotheses + which initiatives
      │  approve(initiative_ids)       to actually execute
      ▼
    COMPLETED

Design rules
------------
1. Trigger is THRESHOLD-ONLY. The controller never runs on a timer. It only
   runs when a caller explicitly invokes diagnose() — normally a human.
2. The controller NEVER executes a graph mutation itself. Execution is the
   orchestrator's job; the controller only proposes and records approvals.
3. Every transition is explicit and recorded so the UI can render the current
   gate and the user can inspect what was proposed.
4. Specialists are only instantiated/dispatched for branches that are actually
   unhealthy — not the whole roster. This is the "spin up sub-agents down the
   graph" behaviour.

Thresholds are configurable via HealthThresholds. A branch is unhealthy when a
node's trend is DOWN and its 7-day percentage change breaches the threshold.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..model.core import BusinessGraph, BaseNode, NodeType, TrendDirection
from .hypothesis import Hypothesis, Initiative, InitiativeStatus, LeverType, OptimisationPlan
from .specialist import SpecialistAgent


# ── Configuration ──────────────────────────────────────────────────────────


@dataclass
class HealthThresholds:
    """Thresholds that decide whether a branch is unhealthy."""

    # A node is unhealthy if trend is DOWN and change_7d_pct <= this (negative).
    change_7d_pct: float = -5.0
    # Optional secondary trigger on the 30-day change.
    change_30d_pct: float = -10.0
    # Ignore branches smaller than this absolute monthly value (noise floor).
    min_abs_value_gbp: float = 100.0
    # How deep to walk from each root when diagnosing.
    max_depth: int = 4
    # Cap the number of branches returned in a proposal.
    max_branches: int = 12


class ControllerState(str, Enum):
    IDLE = "idle"
    DIAGNOSED = "diagnosed"
    DISPATCHED = "dispatched"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"


# ── Diagnosis primitives ───────────────────────────────────────────────────


@dataclass
class BranchDiagnosis:
    """One unhealthy branch found while walking down from a root."""

    root_id: str
    root_label: str
    worst_node_id: str
    worst_node_label: str
    node_type: str
    value: float
    change_7d_pct: float
    change_30d_pct: float
    severity: float                      # 0..1, higher = worse
    cause_chain: List[str] = field(default_factory=list)
    suggested_specialists: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "root_id": self.root_id,
            "root_label": self.root_label,
            "worst_node_id": self.worst_node_id,
            "worst_node_label": self.worst_node_label,
            "node_type": self.node_type,
            "value": round(self.value, 2),
            "change_7d_pct": round(self.change_7d_pct, 2),
            "change_30d_pct": round(self.change_30d_pct, 2),
            "severity": round(self.severity, 3),
            "cause_chain": self.cause_chain,
            "suggested_specialists": self.suggested_specialists,
        }


class GraphHealthMonitor:
    """Walks the graph downward from its roots and finds unhealthy branches.

    A branch starts at a root node. We descend through children, tracking the
    path (the "cause chain") and the worst-breach node. This is how the root
    agent discovers *which* leaf is actually driving a top-line decline, so it
    can dispatch the specialist that owns that leaf — not the whole roster.
    """

    def __init__(self, thresholds: Optional[HealthThresholds] = None):
        self.thresholds = thresholds or HealthThresholds()

    # ── Public ─────────────────────────────────────────────────────────────

    def scan(self, graph: BusinessGraph) -> List[BranchDiagnosis]:
        """Return unhealthy branches, worst first."""
        branches: List[BranchDiagnosis] = []
        seen_worst: set = set()

        roots = [graph.get(r) for r in graph.root_nodes]
        roots = [r for r in roots if r is not None]

        for root in roots:
            found = self._walk_branch(graph, root)
            if found is None:
                continue
            if found.worst_node_id in seen_worst:
                continue
            seen_worst.add(found.worst_node_id)
            branches.append(found)

        branches.sort(key=lambda b: b.severity, reverse=True)
        return branches[: self.thresholds.max_branches]

    # ── Internals ──────────────────────────────────────────────────────────

    def _breach(self, node: BaseNode) -> Optional[float]:
        """Return severity in 0..1 if the node breaches a threshold, else None."""
        t = self.thresholds
        if node.node_type in (NodeType.ASSET, NodeType.LIABILITY, NodeType.EQUITY):
            # Balance-sheet nodes are not "declining revenue" signals.
            return None
        if abs(node.value) < t.min_abs_value_gbp:
            return None

        trend = node.trend.value if isinstance(node.trend, TrendDirection) else str(node.trend)
        c7 = float(node.change_7d_pct or 0.0)
        c30 = float(node.change_30d_pct or 0.0)

        short_breach = trend == "down" and c7 <= t.change_7d_pct
        long_breach = c30 <= t.change_30d_pct
        if not (short_breach or long_breach):
            return None

        # Severity scales with how far past the threshold we are.
        over_7 = max(0.0, (t.change_7d_pct - c7) / abs(t.change_7d_pct)) if short_breach else 0.0
        over_30 = max(0.0, (t.change_30d_pct - c30) / abs(t.change_30d_pct)) if long_breach else 0.0
        return min(1.0, 0.7 * over_7 + 0.3 * over_30)

    def _walk_branch(self, graph: BusinessGraph, root: BaseNode) -> Optional[BranchDiagnosis]:
        """DFS from a root; return the worst breach with its cause chain."""
        worst: Optional[tuple] = None  # (severity, node, chain)
        visited: set = set()

        def _dfs(node: BaseNode, chain: List[str], depth: int):
            nonlocal worst
            if node.id in visited or depth > self.thresholds.max_depth:
                return
            visited.add(node.id)
            sev = self._breach(node)
            if sev is not None:
                if worst is None or sev > worst[0]:
                    worst = (sev, node, chain[:])
            for child_id in node.children:
                child = graph.get(child_id)
                if child is not None:
                    _dfs(child, chain + [child_id], depth + 1)

        _dfs(root, [root.id], 0)
        if worst is None:
            return None

        severity, node, chain = worst
        return BranchDiagnosis(
            root_id=root.id,
            root_label=root.label,
            worst_node_id=node.id,
            worst_node_label=node.label,
            node_type=node.node_type.value if isinstance(node.node_type, NodeType) else str(node.node_type),
            value=float(node.value or 0.0),
            change_7d_pct=float(node.change_7d_pct or 0.0),
            change_30d_pct=float(node.change_30d_pct or 0.0),
            severity=severity,
            cause_chain=chain,
        )


# ── The controller ─────────────────────────────────────────────────────────


@dataclass
class AutonomousGraphController:
    """Stateful, human-gated controller for autonomous graph optimisation.

    Typical human-driven flow::

        ctrl = AutonomousGraphController(specialists)
        proposal = ctrl.diagnose(graph)          # Gate 1 payload
        # ... user picks specialist ids ...
        result = ctrl.dispatch(selected_ids)     # Gate 2 payload (hypotheses)
        # ... user picks initiative ids ...
        done = ctrl.approve(initiative_ids)      # executes/records

    The controller is deliberately *not* automatic: nothing runs unless a caller
    explicitly invokes a transition. Thresholds decide what is *offered*, not
    what is *executed*.
    """

    specialists: List[SpecialistAgent] = field(default_factory=list)
    thresholds: HealthThresholds = field(default_factory=HealthThresholds)
    monitor: Optional[GraphHealthMonitor] = None
    research_context: str = ""

    # ── State ──────────────────────────────────────────────────────────────
    session_id: str = field(default_factory=lambda: f"ses_{uuid.uuid4().hex[:8]}")
    state: ControllerState = ControllerState.IDLE
    branches: List[BranchDiagnosis] = field(default_factory=list)
    dispatched_specialist_ids: List[str] = field(default_factory=list)
    hypotheses: List[Hypothesis] = field(default_factory=list)
    approved_initiative_ids: List[str] = field(default_factory=list)
    initiatives: List[Initiative] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        if self.monitor is None:
            self.monitor = GraphHealthMonitor(self.thresholds)

    # ── Gate 0: Diagnosis (no execution) ───────────────────────────────────

    def diagnose(self, graph: BusinessGraph) -> Dict[str, Any]:
        """Walk the graph, find unhealthy branches, and propose specialists.

        This does NOT run any specialist and does NOT mutate anything. It only
        produces the Gate 1 payload for the human to review.
        """
        self.state = ControllerState.IDLE
        self.hypotheses = []
        self.initiatives = []
        self.approved_initiative_ids = []

        assert self.monitor is not None, "monitor not initialised"
        branches = self.monitor.scan(graph)
        for b in branches:
            b.suggested_specialists = self._match_specialists(b, graph)
        self.branches = branches
        self.state = ControllerState.DIAGNOSED

        # Build a unique list of specialists that could be spun up.
        suggested: Dict[str, Dict[str, Any]] = {}
        for b in branches:
            for sid in b.suggested_specialists:
                sp = self._find_specialist(sid)
                if sp and sid not in suggested:
                    suggested[sid] = {
                        "agent_id": sp.agent_id,
                        "name": sp.name,
                        "description": sp.description,
                        "why": [],
                    }
                if sp:
                    suggested[sid]["why"].append(
                        f"{b.worst_node_label} down {b.change_7d_pct:.1f}% (7d)"
                    )

        payload = {
            "session_id": self.session_id,
            "state": self.state.value,
            "gate": "diagnosis",
            "thresholds": {
                "change_7d_pct": self.thresholds.change_7d_pct,
                "change_30d_pct": self.thresholds.change_30d_pct,
                "min_abs_value_gbp": self.thresholds.min_abs_value_gbp,
            },
            "healthy": len(branches) == 0,
            "branches": [b.to_dict() for b in branches],
            "suggested_specialists": list(suggested.values()),
            "available_specialists": [
                {"agent_id": s.agent_id, "name": s.name, "description": s.description}
                for s in self.specialists
            ],
            "next_action": (
                "No unhealthy branches at the configured thresholds. Nothing to dispatch."
                if not branches
                else "Review the branches and call dispatch(specialist_ids) with the "
                     "specialists you want spun up. Nothing runs until you do."
            ),
        }
        self._log("diagnose", payload)
        return payload

    # ── Gate 1 → Dispatch (runs selected specialists only) ─────────────────

    def dispatch(self, specialist_ids: List[str], graph: BusinessGraph,
                 use_llm: bool = False) -> Dict[str, Any]:
        """Spin up ONLY the approved specialists against the affected branches.

        Requires state == DIAGNOSED. Returns hypotheses for the human to review.
        Does not create or execute initiatives.
        """
        if self.state != ControllerState.DIAGNOSED:
            return {
                "ok": False,
                "error": f"dispatch() requires state=diagnosed, current={self.state.value}. "
                         f"Call diagnose() first.",
            }

        # Resolve approved specialists, preserving order and dropping unknowns.
        resolved: List[SpecialistAgent] = []
        unknown: List[str] = []
        for sid in specialist_ids:
            sp = self._find_specialist(sid)
            if sp is None:
                unknown.append(sid)
            else:
                resolved.append(sp)

        if not resolved:
            return {
                "ok": False,
                "error": "None of the supplied specialist_ids match the roster.",
                "unknown_ids": unknown,
                "available_specialists": [s.agent_id for s in self.specialists],
            }

        affected_ids = set()
        for b in self.branches:
            affected_ids.add(b.worst_node_id)
            affected_ids.update(b.cause_chain)

        # Build a filtered graph view containing affected nodes + their ancestors.
        view = self._subgraph_view(graph, affected_ids)

        hypotheses: List[Hypothesis] = []
        errors: List[str] = []
        for sp in resolved:
            try:
                sp.use_llm = use_llm
                rec = sp.recommend(view, self.research_context)
                for hd in rec.get("hypotheses", []):
                    h = self._dict_to_hypothesis(hd)
                    if h is not None:
                        hypotheses.append(h)
            except Exception as e:  # noqa: BLE001 - specialist failures must not abort the gate
                errors.append(f"{sp.agent_id}: {e}")

        # Dedupe by (node_id, title)
        deduped: List[Hypothesis] = []
        seen = set()
        for h in hypotheses:
            key = (h.node_id, h.title.lower().strip())
            if key in seen:
                continue
            seen.add(key)
            deduped.append(h)

        self.hypotheses = deduped
        self.dispatched_specialist_ids = [s.agent_id for s in resolved]
        self.state = ControllerState.DISPATCHED

        payload = {
            "ok": True,
            "session_id": self.session_id,
            "state": self.state.value,
            "gate": "hypotheses",
            "dispatched_specialists": self.dispatched_specialist_ids,
            "unknown_ids": unknown,
            "errors": errors,
            "hypothesis_count": len(deduped),
            "hypotheses": [h.to_dict() for h in deduped],
            "next_action": (
                "Review the hypotheses and call approve(initiative_ids) with the "
                "hypothesis ids you want turned into initiatives. Nothing executes until you do."
            ),
        }
        self._log("dispatch", payload)
        return payload

    # ── Gate 2 → Approve (creates initiatives; execution stays external) ────

    def approve(self, hypothesis_ids: List[str]) -> Dict[str, Any]:
        """Turn approved hypotheses into initiatives ready for execution.

        Requires state == DISPATCHED. Does not call external connectors — it
        produces Initiative objects in APPROVED status for the orchestrator or
        UI to hand off. This is the final human gate.
        """
        if self.state not in (ControllerState.DISPATCHED, ControllerState.AWAITING_APPROVAL):
            return {
                "ok": False,
                "error": f"approve() requires state=dispatched, current={self.state.value}. "
                         f"Call dispatch() first.",
            }

        by_id = {h.id: h for h in self.hypotheses}
        selected = [by_id[hid] for hid in hypothesis_ids if hid in by_id]
        missing = [hid for hid in hypothesis_ids if hid not in by_id]

        if not selected:
            return {
                "ok": False,
                "error": "No supplied hypothesis ids exist in the current dispatch.",
                "missing_ids": missing,
                "available_hypothesis_ids": list(by_id.keys()),
            }

        initiatives: List[Initiative] = []
        for h in selected:
            ini = Initiative(
                hypothesis_id=h.id,
                agent_id=h.agent_id,
                node_id=h.node_id,
                node_label=h.node_label,
                title=h.title,
                description=h.description,
                lever_type=h.lever_type if isinstance(h.lever_type, LeverType) else LeverType.OTHER,
                status=InitiativeStatus.APPROVED,
                predictions=h.predictions,
                predicted_impact_gbp=h.net_impact_gbp,
                owner="human_approval",
                metadata={
                    "why_now": h.rationale,
                    "session_id": self.session_id,
                    "approved_by": "human",
                },
            )
            initiatives.append(ini)

        self.initiatives = initiatives
        self.approved_initiative_ids = [i.id for i in initiatives]
        self.state = ControllerState.COMPLETED

        payload = {
            "ok": True,
            "session_id": self.session_id,
            "state": self.state.value,
            "gate": "approved",
            "approved_count": len(initiatives),
            "missing_ids": missing,
            "initiatives": [i.to_dict() for i in initiatives],
            "next_action": "Hand these initiatives to the orchestrator/connectors to execute.",
        }
        self._log("approve", payload)
        return payload

    # ── Introspection ──────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "state": self.state.value,
            "branches_found": len(self.branches),
            "dispatched_specialists": self.dispatched_specialist_ids,
            "hypotheses": len(self.hypotheses),
            "approved_initiatives": len(self.initiatives),
            "history": self.history,
        }

    def reset(self) -> Dict[str, Any]:
        sid = self.session_id
        self.__init__(  # type: ignore[misc]
            specialists=self.specialists,
            thresholds=self.thresholds,
            research_context=self.research_context,
        )
        return {"ok": True, "reset_from": sid, "new_session_id": self.session_id}

    # ── Internals ──────────────────────────────────────────────────────────

    def _log(self, event: str, payload: Dict[str, Any]) -> None:
        self.history.append({
            "event": event,
            "state": payload.get("state"),
            "at": _now_iso(),
            "summary": {
                "branches": len(payload.get("branches", [])) or None,
                "specialists": payload.get("dispatched_specialists"),
                "hypotheses": payload.get("hypothesis_count"),
                "approved": payload.get("approved_count"),
            },
        })

    def _find_specialist(self, agent_id: str) -> Optional[SpecialistAgent]:
        for s in self.specialists:
            if s.agent_id == agent_id:
                return s
        return None

    def _match_specialists(self, branch: BranchDiagnosis, graph: BusinessGraph) -> List[str]:
        """Map an unhealthy branch to specialists that own its nodes."""
        node = graph.get(branch.worst_node_id)
        matched: List[str] = []
        for s in self.specialists:
            try:
                if node is not None and s.owns(node):
                    matched.append(s.agent_id)
                    continue
                # Fall back: any owned node appears in the cause chain.
                owned = set(s.owned_node_ids)
                if owned & set(branch.cause_chain):
                    matched.append(s.agent_id)
            except Exception:
                continue
        if not matched and self.specialists:
            matched.append(self.specialists[0].agent_id)
        return matched

    def _subgraph_view(self, graph: BusinessGraph, node_ids: set) -> BusinessGraph:
        """Build a filtered BusinessGraph containing the given nodes + ancestors."""
        keep = set(node_ids)
        for nid in list(keep):
            node = graph.get(nid)
            if node is None:
                continue
            keep.update(node.parents)

        view = BusinessGraph()
        for nid in keep:
            node = graph.get(nid)
            if node is None:
                continue
            # Copy so specialists cannot mutate the real graph.
            import copy
            view.add(copy.deepcopy(node))
        # Preserve root metadata even if roots were not in keep.
        view.root_nodes = [r for r in graph.root_nodes if r in view.nodes] or view.root_nodes
        return view

    def _dict_to_hypothesis(self, d: Dict[str, Any]) -> Optional[Hypothesis]:
        try:
            lever = LeverType(d.get("lever_type", "other"))
        except ValueError:
            lever = LeverType.OTHER
        try:
            return Hypothesis(
                id=d.get("id") or f"hyp_{uuid.uuid4().hex[:10]}",
                agent_id=d.get("agent_id", ""),
                node_id=d.get("node_id", ""),
                node_label=d.get("node_label", ""),
                title=d.get("title", ""),
                description=d.get("description", ""),
                lever_type=lever,
                expected_impact_gbp=float(d.get("expected_impact_gbp", 0.0) or 0.0),
                expected_impact_pct=float(d.get("expected_impact_pct", 0.0) or 0.0),
                effort=float(d.get("effort", 1.0) or 1.0),
                risk=float(d.get("risk", 0.3) or 0.3),
                confidence=float(d.get("confidence", 0.5) or 0.5),
                rationale=d.get("rationale", ""),
                metadata=d.get("metadata", {}) or {},
            )
        except Exception:
            return None


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
