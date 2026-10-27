"""Constraint Checker Agent — the gatekeeper of the BAM hierarchy.

Sits between specialists and the arbiter. Every hypothesis must pass through
this agent before it can be selected. It does three things:

1. Hard-constraint validation — reject hypotheses that violate a hard constraint.
2. Soft-constraint pricing — convert soft violations into £ penalties so the
   arbiter can make an economically rational trade-off.
3. Portfolio interaction checking — catch conflicts between initiatives that are
   individually valid but jointly infeasible (e.g. two initiatives both needing
   the same 10 staff-hours).

The agent returns an adjusted Hypothesis (net_impact_gbp) plus a structured
verdict. It never modifies the graph.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..model.constraints import (
    Constraint, ConstraintSeverity, ConstraintStore, ConstraintType,
)
from ..model.core import BusinessGraph
from .hypothesis import Hypothesis


@dataclass
class ValidationResult:
    hypothesis_id: str
    ok: bool
    hard_violations: List[Dict[str, Any]] = field(default_factory=list)
    soft_violations: List[Dict[str, Any]] = field(default_factory=list)
    soft_penalty_gbp: float = 0.0
    adjusted_impact_gbp: float = 0.0
    interaction_notes: List[str] = field(default_factory=list)
    verdict: str = ""

    def to_dict(self) -> dict:
        return {
            "hypothesis_id": self.hypothesis_id,
            "ok": self.ok,
            "hard_violations": self.hard_violations,
            "soft_violations": self.soft_violations,
            "soft_penalty_gbp": round(self.soft_penalty_gbp, 2),
            "adjusted_impact_gbp": round(self.adjusted_impact_gbp, 2),
            "interaction_notes": self.interaction_notes,
            "verdict": self.verdict,
        }


class ConstraintCheckerAgent:
    """Validates hypotheses against the constraint model."""

    agent_id = "constraint_checker"
    name = "Constraint Checker Agent"
    description = "Ensures no initiative violates hard constraints; prices soft violations."

    # Keyword maps for matching free-text hypotheses against constraint types.
    # Deliberately conservative: only flags when the text strongly suggests a
    # constraint domain. False positives are cheap (soft note); false negatives
    # are expensive (illegal or unsafe action).
    _TYPE_KEYWORDS: Dict[ConstraintType, List[str]] = {
        ConstraintType.LEGAL: ["legal", "law", "licence", "license", "regulation",
                                "minimum wage", "working time", "gdpr", "health and safety",
                                "food safety", "alcohol", "premises"],
        ConstraintType.ETHICAL: ["ethical", "fair wage", "sourcing", "sustainable",
                                  "brand value", "exploit", "child labour", "animal welfare"],
        ConstraintType.CAPACITY: ["capacity", "max throughput", "maximum hours",
                                   "staff hours", "seating", "kitchen capacity", "volume limit"],
        ConstraintType.TEMPORAL: ["opening hours", "operating hours", "day of week",
                                   "seasonal", "out of hours", "late night", "sunday trading"],
        ConstraintType.PHYSICAL: ["equipment limit", "space", "floor space", "storage",
                                   "fridge space", "oven capacity", "physical limit"],
        ConstraintType.SEASONAL: ["seasonal", "season", "supply season", "availability window"],
        ConstraintType.QUALITY: ["freshness", "use-by", "quality threshold", "waste threshold",
                                  "food quality", "consistency"],
        ConstraintType.FINANCIAL: ["budget", "cashflow", "cash flow", "credit limit",
                                    "spend cap", "capital", "loan covenant"],
    }

    def __init__(self, constraint_store: Optional[ConstraintStore] = None):
        self.constraint_store = constraint_store

    # ── Single hypothesis validation ──────────────────────────────────────

    def validate(self, hypothesis: Hypothesis, graph: BusinessGraph) -> ValidationResult:
        """Validate one hypothesis against all applicable constraints."""
        result = ValidationResult(
            hypothesis_id=hypothesis.id,
            ok=True,
            adjusted_impact_gbp=hypothesis.expected_impact_gbp,
        )
        if not self.constraint_store:
            result.verdict = "No constraint store loaded — hypothesis accepted by default."
            return result

        constraints = self.constraint_store.get_for_node(hypothesis.node_id, graph)
        text = f"{hypothesis.title} {hypothesis.description} {hypothesis.rationale}".lower()

        for c in constraints:
            if not self._mentions_domain(text, c.constraint_type):
                # Still run explicit numeric checks for financial/capacity constraints
                if not self._numeric_check(hypothesis, c):
                    continue
            # Domain is implicated — decide severity
            if c.severity == ConstraintSeverity.HARD:
                # A hard constraint only rejects if the hypothesis plausibly
                # breaches it. Since we cannot prove a breach from text alone,
                # we require explicit numeric evidence or a strong keyword hit.
                if self._numeric_check(hypothesis, c) or self._strong_keyword_hit(text, c):
                    result.ok = False
                    result.hard_violations.append({
                        "constraint_id": c.id,
                        "name": c.name,
                        "description": c.description,
                        "source": c.source,
                    })
            else:
                penalty = self._estimate_penalty(hypothesis, c)
                if penalty > 0:
                    result.soft_violations.append({
                        "constraint_id": c.id,
                        "name": c.name,
                        "description": c.description,
                        "penalty_gbp": round(penalty, 2),
                    })
                    result.soft_penalty_gbp += penalty

        result.adjusted_impact_gbp = hypothesis.expected_impact_gbp - result.soft_penalty_gbp
        hypothesis.constraints_ok = result.ok
        hypothesis.soft_penalty_gbp = result.soft_penalty_gbp
        hypothesis.constraint_notes = [v["name"] for v in result.hard_violations + result.soft_violations]

        if not result.ok:
            result.verdict = (
                f"REJECTED — violates hard constraint(s): "
                f"{', '.join(v['name'] for v in result.hard_violations)}."
            )
        elif result.soft_penalty_gbp > 0:
            result.verdict = (
                f"ACCEPTED with £{result.soft_penalty_gbp:,.2f}/month soft-constraint penalty. "
                f"Net impact £{result.adjusted_impact_gbp:,.2f}/month."
            )
        else:
            result.verdict = "ACCEPTED — no constraint violations detected."
        return result

    # ── Portfolio validation ──────────────────────────────────────────────

    def validate_portfolio(self, hypotheses: List[Hypothesis],
                           graph: BusinessGraph,
                           budget_effort: float = 20.0) -> Dict[str, Any]:
        """Check whether a set of hypotheses can coexist."""
        notes: List[str] = []
        accepted: List[Hypothesis] = []
        rejected: List[Hypothesis] = []

        for h in hypotheses:
            r = self.validate(h, graph)
            if r.ok:
                accepted.append(h)
            else:
                rejected.append(h)
                notes.append(f"{h.title}: {r.verdict}")

        # Effort budget
        total_effort = sum(h.effort for h in accepted)
        if total_effort > budget_effort:
            notes.append(
                f"Combined effort {total_effort:.1f} exceeds budget {budget_effort:.1f}; "
                "arbiter must trim the portfolio."
            )

        # Node collisions: multiple initiatives on the same node
        by_node: Dict[str, List[Hypothesis]] = {}
        for h in accepted:
            by_node.setdefault(h.node_id, []).append(h)
        for node_id, group in by_node.items():
            if len(group) > 1:
                notes.append(
                    f"Node {node_id} has {len(group)} competing initiatives "
                    f"({', '.join(g.title for g in group)}) — select at most one or verify they compose."
                )

        # Lever collisions: e.g. two price changes on different nodes could interact
        by_lever: Dict[str, List[Hypothesis]] = {}
        for h in accepted:
            by_lever.setdefault(h.lever_type.value, []).append(h)
        for lever, group in by_lever.items():
            if len(group) > 2:
                notes.append(
                    f"{len(group)} '{lever}' initiatives — watch for cannibalisation or over-correction."
                )

        return {
            "accepted": [h.to_dict() for h in accepted],
            "rejected": [h.to_dict() for h in rejected],
            "notes": notes,
            "total_effort": round(total_effort, 2),
            "budget_effort": budget_effort,
        }

    # ── Internals ─────────────────────────────────────────────────────────

    def _mentions_domain(self, text: str, ctype: ConstraintType) -> bool:
        keywords = self._TYPE_KEYWORDS.get(ctype, [])
        return any(k in text for k in keywords)

    def _strong_keyword_hit(self, text: str, c: Constraint) -> bool:
        """A hard constraint is only rejected on a strong, specific hit."""
        strong = [c.name.lower()] + [t.lower() for t in c.tags]
        return any(s and s in text for s in strong)

    def _numeric_check(self, hypothesis: Hypothesis, c: Constraint) -> bool:
        """Check explicit numeric parameters against a constraint."""
        params = c.parameters or {}
        # Capacity: compare hypothesis effort/volume against a numeric cap if present
        for key in ("max_staff_hours", "max_hours", "max_volume", "max_throughput", "max_gbp"):
            if key in params:
                cap = params[key]
                try:
                    cap_val = float(cap)
                except (TypeError, ValueError):
                    continue
                # Look for a matching numeric hint in the hypothesis metadata
                hint = hypothesis.metadata.get(key)
                if hint is not None:
                    try:
                        if float(hint) > cap_val:
                            return True
                    except (TypeError, ValueError):
                        pass
        return False

    def _estimate_penalty(self, hypothesis: Hypothesis, c: Constraint) -> float:
        """Estimate £ penalty for a soft-constraint violation."""
        if c.penalty_per_unit and hypothesis.metadata.get("units_affected") is not None:
            try:
                return float(c.penalty_per_unit) * float(hypothesis.metadata["units_affected"])
            except (TypeError, ValueError):
                pass
        # Fallback: a soft violation costs a fraction of expected impact,
        # scaled by severity implied by the constraint's penalty setting.
        base = abs(hypothesis.expected_impact_gbp)
        if c.penalty_per_unit:
            return min(base * 0.25, float(c.penalty_per_unit) * 10)
        return base * 0.10

    # ── Reporting ─────────────────────────────────────────────────────────

    def summary(self, results: List[ValidationResult]) -> str:
        ok = sum(1 for r in results if r.ok)
        rej = len(results) - ok
        penalty = sum(r.soft_penalty_gbp for r in results)
        return (
            f"{len(results)} hypotheses checked: {ok} accepted, {rej} rejected, "
            f"£{penalty:,.2f}/month in soft penalties."
        )
