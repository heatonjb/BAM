"""Initiative impact analysis and the Progress Agent.

Two jobs, sharing one model of "what an initiative should do to the graph":

1. ``analyse_impact()`` — for the initiative detail view. Works out which graph
   nodes an initiative touches, why, and by how much, then phases that change
   month-by-month using the projection engine's ``AdoptionCurve`` (initiatives
   ramp up; they don't land in full on day one).

2. ``ProgressAgent`` — for active initiatives. Compares the *current* graph
   values of the impacted nodes against the baseline snapshot taken at
   activation and the time-phased expectation, and reports on-track / behind /
   ahead plus deviations and blockers.

Sign convention: ``predicted_impact_gbp`` is a monthly *benefit* (profit
uplift). Revenue nodes move up by the benefit; cost nodes (stored as positive
spend) move down; profit metrics move up.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..model.core import BusinessGraph, NodeType
from .hypothesis import Initiative
from .projection import AdoptionCurve, make_curve

PROJECTION_MONTHS = 6
# Progress tolerances: achieved/expected within ±15% is "on track".
AHEAD_RATIO = 1.15
BEHIND_RATIO = 0.85


# ── Impact model ──────────────────────────────────────────────────────────

def _root_of(graph: BusinessGraph, node_id: str) -> str:
    path = graph.get_drill_path(node_id)
    return path[0] if path else node_id


def benefit_direction(graph: BusinessGraph, node_id: str) -> int:
    """+1 if a profit benefit raises this node's value, -1 if it lowers it."""
    node = graph.get(node_id)
    if node is None:
        return 1
    if node.node_type in (NodeType.METRIC, NodeType.REVENUE):
        return 1
    root = graph.get(_root_of(graph, node_id))
    if root is not None and root.id == "pnl_revenue":
        return 1
    return -1


def _outcome_metrics(graph: BusinessGraph, start_id: str) -> List[str]:
    """Metric nodes (gross/operating profit) that roll up from ``start_id``."""
    out: List[str] = []
    frontier = [start_id]
    while frontier:
        nid = frontier.pop()
        for m in graph.get_by_type(NodeType.METRIC):
            if nid in m.children and m.id not in out:
                out.append(m.id)
                frontier.append(m.id)
    return out


def ramp_curve(initiative: Initiative) -> AdoptionCurve:
    """Logistic ramp scaled to effort: bigger programmes take longer to land."""
    effort = float(initiative.metadata.get("effort") or 3)
    midpoint = max(1.0, min(4.0, effort / 2.0))
    return make_curve("logistic", peak=1.0, midpoint=midpoint, steepness=1.2)


def analyse_impact(initiative: Initiative, graph: BusinessGraph,
                   baseline_values: Optional[Dict[str, float]] = None,
                   months: int = PROJECTION_MONTHS) -> Dict[str, Any]:
    """Impacted nodes with reasoning, plus a month-by-month projection for each.

    ``baseline_values`` lets the caller pin the baseline (e.g. the snapshot
    taken at activation); otherwise current graph values are used.
    """
    target = graph.get(initiative.node_id)
    benefit = float(initiative.predicted_impact_gbp or 0.0)
    lever = initiative.lever_type.value if hasattr(initiative.lever_type, "value") else str(initiative.lever_type)
    baseline_values = baseline_values or {}

    def base(nid: str) -> float:
        if nid in baseline_values:
            return float(baseline_values[nid])
        n = graph.get(nid)
        return float(n.value) if n else 0.0

    impacted: List[Dict[str, Any]] = []
    if target is None:
        return {"impacted": [], "projection": {"months": [], "curve": []}, "benefit_gbp": benefit,
                "warning": f"Node '{initiative.node_id}' not found in the current graph."}

    t_dir = benefit_direction(graph, target.id)
    t_base = base(target.id)
    impacted.append({
        "node_id": target.id, "label": target.label, "type": target.node_type.value,
        "role": "target", "direction": t_dir, "baseline": t_base,
        "delta_gbp": t_dir * benefit,
        "reasoning": (
            f"Directly targeted by the {lever.replace('_', ' ')} lever. "
            f"A £{abs(benefit):,.0f}/mo benefit means this "
            f"{'revenue line rises' if t_dir > 0 else 'cost line falls'} by that amount at full effect."
        ),
    })

    # Drivers: children share the change in proportion to their current contribution.
    child_total = sum(abs(base(c)) for c in target.children if graph.get(c))
    for cid in target.children:
        child = graph.get(cid)
        if not child or child_total == 0:
            continue
        share = abs(base(cid)) / child_total
        impacted.append({
            "node_id": cid, "label": child.label, "type": child.node_type.value,
            "role": "driver", "direction": t_dir, "baseline": base(cid),
            "delta_gbp": t_dir * benefit * share,
            "reasoning": (
                f"Makes up {share * 100:.0f}% of {target.label}; assumed to carry a proportional "
                f"share of the change unless the initiative targets it specifically."
            ),
        })

    # Roll-up: every ancestor in the drill path moves by the same £.
    for aid in reversed(graph.get_drill_path(target.id)[:-1]):
        anc = graph.get(aid)
        if not anc:
            continue
        a_dir = benefit_direction(graph, aid)
        impacted.append({
            "node_id": aid, "label": anc.label, "type": anc.node_type.value,
            "role": "rollup", "direction": a_dir, "baseline": base(aid),
            "delta_gbp": a_dir * benefit,
            "reasoning": f"Parent of {target.label} in the P&L hierarchy — the change rolls up one-for-one.",
        })

    # Outcomes: profit metrics fed by the top of the chain.
    for mid in _outcome_metrics(graph, _root_of(graph, target.id)):
        m = graph.get(mid)
        impacted.append({
            "node_id": mid, "label": m.label, "type": m.node_type.value,
            "role": "outcome", "direction": 1, "baseline": base(mid),
            "delta_gbp": benefit,
            "reasoning": f"Profit metric downstream of {target.label}; the benefit lands here as +£{benefit:,.0f}/mo.",
        })

    curve = ramp_curve(initiative)
    fractions = curve.series(months)
    for item in impacted:
        item["level"] = getattr(graph.get(item["node_id"]), "level", 0)
        item["projection"] = [round(item["baseline"] + item["delta_gbp"] * f, 2) for f in fractions]
        item["baseline"] = round(item["baseline"], 2)
        item["delta_gbp"] = round(item["delta_gbp"], 2)

    return {
        "benefit_gbp": round(benefit, 2),
        "impacted": impacted,
        "projection": {
            "months": list(range(1, months + 1)),
            "curve": [round(f, 3) for f in fractions],
            "curve_kind": curve.name,
            "cumulative_benefit_gbp": round(sum(benefit * f for f in fractions), 2),
        },
    }


def baseline_snapshot(initiative: Initiative, graph: BusinessGraph) -> Dict[str, float]:
    """Node values at activation — the yardstick the Progress Agent measures from."""
    return {i["node_id"]: i["baseline"] for i in analyse_impact(initiative, graph)["impacted"]}


# ── Progress Agent ────────────────────────────────────────────────────────

def _parse_ts(ts: Optional[str]) -> Optional[datetime]:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


@dataclass
class ProgressAgent:
    """Checks an active initiative's nodes against its time-phased projection."""

    agent_id: str = "progress_agent"
    name: str = "Progress Agent"

    def check(self, initiative: Initiative, graph: BusinessGraph,
              constraint_store: Any = None,
              other_active: Optional[List[Initiative]] = None,
              now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or datetime.now(timezone.utc)
        snapshot = initiative.metadata.get("activation_snapshot") or {}
        impact = analyse_impact(initiative, graph, baseline_values=snapshot)
        benefit = impact["benefit_gbp"]
        deviations: List[Dict[str, Any]] = []
        blockers: List[str] = []

        started = _parse_ts(initiative.started_at) or _parse_ts(initiative.approved_at)
        if started is None:
            blockers.append("Initiative has no start date — activate it before tracking progress.")
            elapsed_months = 0.0
        else:
            elapsed_months = max(0.0, (now - started).total_seconds() / (30 * 86400))
        if not snapshot:
            blockers.append("No activation snapshot — baseline is today's value, so progress reads as zero.")

        curve = ramp_curve(initiative)
        # The curve is defined on whole months; interpolate linearly within a month.
        lo = int(elapsed_months)
        f_lo = curve.at(lo) if lo > 0 else 0.0
        f_hi = curve.at(lo + 1)
        expected_frac = f_lo + (f_hi - f_lo) * (elapsed_months - lo)
        expected_benefit = benefit * expected_frac

        nodes_report = []
        target_achieved = 0.0
        for item in impact["impacted"]:
            node = graph.get(item["node_id"])
            current = float(node.value) if node else item["baseline"]
            # Benefit achieved so far, measured in the node's own direction.
            achieved = (current - item["baseline"]) * item["direction"]
            if abs(achieved) < 0.005:
                achieved = 0.0
            expected = abs(item["delta_gbp"]) * expected_frac
            gap = achieved - expected
            entry = {
                "node_id": item["node_id"], "label": item["label"], "role": item["role"],
                "baseline": item["baseline"], "current": round(current, 2),
                "expected_now": round(item["baseline"] + item["delta_gbp"] * expected_frac, 2),
                "achieved_benefit_gbp": round(achieved, 2),
                "expected_benefit_gbp": round(expected, 2),
                "gap_gbp": round(gap, 2),
                "trend": node.trend.value if node else "unknown",
                "change_7d_pct": round(node.change_7d_pct, 1) if node else 0.0,
            }
            nodes_report.append(entry)
            if item["role"] == "target":
                target_achieved = achieved
            # Drivers carry an assumed proportional split, so only flag them when
            # they move the wrong way; target/rollup/outcome are judged against plan.
            is_driver = item["role"] == "driver"
            if (is_driver and achieved < -1) or (not is_driver and expected > 1 and abs(gap) > 0.25 * expected):
                deviations.append({
                    "node_id": item["node_id"], "label": item["label"],
                    "message": (f"{item['label']} is £{abs(gap):,.0f}/mo "
                                f"{'ahead of' if gap > 0 else 'behind'} the projection "
                                f"(achieved £{achieved:,.0f} vs expected £{expected:,.0f})."),
                })
            # Moving against the desired direction is a blocker regardless of timing.
            if node and node.change_7d_pct * item["direction"] < -2 and item["role"] in ("target", "outcome"):
                blockers.append(f"{item['label']} moved {node.change_7d_pct:+.1f}% over 7d — against the initiative's intended direction.")

        if snapshot and all(abs(n["current"] - n["baseline"]) < 0.005 for n in nodes_report):
            blockers.append("Impacted node values are unchanged since activation — the graph has no newer data. "
                            "Reload data (POS/Xero) before trusting this verdict.")

        if constraint_store is not None:
            try:
                hard = [c for c in constraint_store.get_for_node(initiative.node_id, graph)
                        if c.severity.value == "hard"]
                if hard:
                    blockers.append("Hard constraints on target node: " + ", ".join(c.name for c in hard[:3]))
            except Exception:
                pass

        for other in other_active or []:
            if other.id != initiative.id and other.node_id == initiative.node_id:
                blockers.append(f"Shares target node with active initiative '{other.title}' — attribution will be mixed.")

        too_early = expected_benefit < max(1.0, 0.05 * abs(benefit))
        if too_early:
            status = "ahead" if target_achieved > max(1.0, 0.05 * abs(benefit)) else "on_track"
            ratio = None
        else:
            ratio = target_achieved / expected_benefit
            status = "ahead" if ratio >= AHEAD_RATIO else "behind" if ratio < BEHIND_RATIO else "on_track"

        summary = self._summarise(initiative, status, too_early, elapsed_months,
                                  target_achieved, expected_benefit, benefit, len(blockers))
        return {
            "agent": self.agent_id,
            "initiative_id": initiative.id,
            "checked_at": now.isoformat(),
            "status": status,
            "too_early": too_early,
            "elapsed_months": round(elapsed_months, 2),
            "expected_ramp_fraction": round(expected_frac, 3),
            "predicted_benefit_gbp": benefit,
            "expected_benefit_now_gbp": round(expected_benefit, 2),
            "achieved_benefit_gbp": round(target_achieved, 2),
            "achievement_ratio": round(ratio, 3) if ratio is not None else None,
            "nodes": nodes_report,
            "deviations": deviations,
            "blockers": blockers,
            "summary": summary,
        }

    @staticmethod
    def _summarise(ini: Initiative, status: str, too_early: bool, elapsed: float,
                   achieved: float, expected: float, benefit: float, n_blockers: int) -> str:
        label = {"on_track": "on track", "behind": "behind", "ahead": "ahead"}[status]
        if too_early:
            s = (f"'{ini.title}' is {elapsed:.1f} months in — too early for the ramp to show "
                 f"(expected £{expected:,.0f} of £{benefit:,.0f}/mo so far). Provisionally {label}.")
        else:
            s = (f"'{ini.title}' is {label}: £{achieved:,.0f}/mo achieved vs £{expected:,.0f}/mo "
                 f"expected at {elapsed:.1f} months (full effect £{benefit:,.0f}/mo).")
        if n_blockers:
            s += f" {n_blockers} blocker(s) flagged."
        return s


__all__ = ["analyse_impact", "baseline_snapshot", "benefit_direction", "ramp_curve", "ProgressAgent"]
