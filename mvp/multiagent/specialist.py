"""Specialist agents for the BAM multi-agent hierarchy.

Each specialist owns a slice of the business graph (e.g. revenue nodes, cost
nodes, process nodes) and runs a four-step loop:

    1. assess()      — read current performance of its owned nodes
    2. generate()    — propose hypotheses (LLM + heuristics), calibrated by history
    3. rank()        — score by risk-adjusted expected value
    4. recommend()   — return the top-N hypotheses upward to the arbiter

The specialist never executes changes itself. It only recommends. Execution is
the orchestrator's job, after the arbiter selects a portfolio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..insights import call_llm
from ..model.core import BaseNode, BusinessGraph, NodeType, TrendDirection
from ..model.constraints import ConstraintStore
from .hypothesis import Hypothesis, LeverType, Prediction
from .knowledge import HistoricalKnowledgeBase

SPECIALIST_SYSTEM_PROMPT = """You are the {agent_name}, a specialist agent inside the
"Business as a Machine" (BAM) optimisation system. You own the {owned_description}.

Your job: assess the performance of the nodes you own and propose concrete,
quantified improvement hypotheses. You are NOT a general assistant — you are a
narrow, expert operator who thinks only about your domain.

## Your owned nodes
{owned_nodes_text}

## Current performance
{performance_text}

## Constraints you must respect
{constraints_text}

## What has worked and failed before (historical calibration)
{history_text}

## Research context
{research_context}

## Rules
1. Every hypothesis must be concrete and actionable — a specific change, not "improve X".
2. Quantify expected monthly £ impact. Be realistic; use the node's current value as baseline.
3. Estimate effort 1-10 (1 = a few hours, 10 = a major multi-month programme).
4. Estimate risk 0-1 (probability the hypothesis under-delivers or fails).
5. Estimate confidence 0-1 (your confidence in the quantified impact).
6. Use historical calibration to adjust confidence: if this lever under-delivered before, lower confidence and raise risk.
7. Do NOT propose anything that violates a hard constraint.
8. Prefer 3-6 hypotheses spanning different levers. Rank matters more than volume.
9. For each hypothesis, give 1-3 predictions with baseline, predicted value, metric name, and rationale.

Return ONLY valid JSON matching this schema:
{{
  "assessment": "2-3 sentence summary of current performance and the biggest gap",
  "hypotheses": [
    {{
      "title": "short action title",
      "description": "what exactly to do and why",
      "lever_type": "price|volume|demand_generation|cost_reduction|procurement|staffing|process|menu|retention|capacity|marketing|other",
      "expected_impact_gbp": 1234.0,
      "expected_impact_pct": 2.5,
      "effort": 3,
      "risk": 0.25,
      "confidence": 0.7,
      "predictions": [
        {{"metric": "monthly_revenue", "baseline": 50000.0, "predicted": 51234.0, "unit": "GBP", "horizon_days": 30, "confidence": 0.7, "rationale": "why"}}
      ],
      "rationale": "why this hypothesis, drawing on the performance data and history"
    }}
  ]
}}
"""


@dataclass
class SpecialistAgent:
    """Base specialist. Subclasses declare which nodes they own."""

    agent_id: str = "specialist"
    name: str = "Specialist Agent"
    description: str = "Generic specialist"
    owned_types: List[NodeType] = field(default_factory=list)
    owned_node_ids: List[str] = field(default_factory=list)
    max_hypotheses: int = 5
    model: str = "deepseek/deepseek-v4.1-flash"
    use_llm: bool = False   # heuristics-first by default; enable LLM for richer hypotheses
    llm_timeout: int = 40

    # Injected at construction
    knowledge: Optional[HistoricalKnowledgeBase] = None
    constraint_store: Optional[ConstraintStore] = None

    # ── Ownership ─────────────────────────────────────────────────────────

    def owns(self, node: BaseNode) -> bool:
        if self.owned_node_ids and node.id in self.owned_node_ids:
            return True
        if self.owned_types and node.node_type in self.owned_types:
            return True
        return False

    def owned_nodes(self, graph: BusinessGraph) -> List[BaseNode]:
        return [n for n in graph.nodes.values() if self.owns(n)]

    # ── Step 1: Assess ────────────────────────────────────────────────────

    def assess(self, graph: BusinessGraph) -> Dict[str, Any]:
        """Summarise current performance across owned nodes."""
        nodes = self.owned_nodes(graph)
        if not nodes:
            return {"agent": self.agent_id, "node_count": 0, "nodes": [], "summary": "No owned nodes."}

        total = sum(n.value for n in nodes)
        declining = [n for n in nodes if n.trend == TrendDirection.DOWN]
        growing = [n for n in nodes if n.trend == TrendDirection.UP]
        underperforming = [
            n for n in nodes
            if n.efficiency is not None and n.efficiency < 1.0
        ]
        # Sort by absolute value so the biggest levers come first
        ranked = sorted(nodes, key=lambda n: abs(n.value), reverse=True)
        return {
            "agent": self.agent_id,
            "node_count": len(nodes),
            "total_value": round(total, 2),
            "declining_count": len(declining),
            "growing_count": len(growing),
            "underperforming_count": len(underperforming),
            "nodes": [n.to_dict() for n in ranked[:12]],
            "declining": [n.to_dict() for n in declining[:5]],
            "underperforming": [n.to_dict() for n in underperforming[:5]],
        }

    # ── Step 2: Generate ──────────────────────────────────────────────────

    def _owned_nodes_text(self, graph: BusinessGraph, limit: int = 8) -> str:
        nodes = sorted(self.owned_nodes(graph), key=lambda n: abs(n.value), reverse=True)[:limit]
        lines = []
        for n in nodes:
            eff = f", efficiency {n.efficiency:.2f}x" if n.efficiency is not None else ""
            lines.append(
                f"- {n.label} ({n.node_type.value}) id={n.id}: £{n.value:,.2f}/month, "
                f"7d {n.change_7d_pct:+.1f}%, 30d {n.change_30d_pct:+.1f}%, trend={n.trend.value}{eff}"
            )
        return "\n".join(lines) or "None."

    def _performance_text(self, assessment: Dict[str, Any]) -> str:
        return (
            f"Owned nodes: {assessment['node_count']}. "
            f"Total monthly value: £{assessment.get('total_value', 0):,.2f}. "
            f"Growing: {assessment.get('growing_count', 0)}, declining: {assessment.get('declining_count', 0)}, "
            f"underperforming efficiency: {assessment.get('underperforming_count', 0)}."
        )

    def _constraints_text(self, graph: BusinessGraph) -> str:
        if not self.constraint_store:
            return "No constraints loaded."
        nodes = self.owned_nodes(graph)
        seen = set()
        lines = []
        for n in nodes:
            for c in self.constraint_store.get_for_node(n.id, graph):
                if c.id in seen:
                    continue
                seen.add(c.id)
                lines.append(
                    f"- [{c.severity.value.upper()}] {c.name}: {c.description} "
                    f"(type={c.constraint_type.value}, applies_to={c.applicable_to or 'ALL'})"
                )
        return "\n".join(lines[:20]) or "No constraints apply."

    def _history_text(self) -> str:
        if not self.knowledge:
            return "No historical knowledge base."
        parts = []
        # Lever-specific calibration across all our likely levers
        for lever in self.relevant_levers():
            c = self.knowledge.calibration(lever_type=lever.value)
            if c["n"] > 0:
                parts.append(
                    f"- {lever.value}: {c['n']} past initiatives, "
                    f"mean actual/predicted {c['mean_accuracy']:.2f}x, "
                    f"success rate {c['success_rate']*100:.0f}%"
                )
        lessons = self.knowledge.lessons_text(limit=6)
        if parts:
            return "Calibration by lever:\n" + "\n".join(parts) + "\n\n" + lessons
        return lessons

    def relevant_levers(self) -> List[LeverType]:
        """Override in subclasses."""
        return [LeverType.OTHER]

    def generate(self, graph: BusinessGraph, research_context: str = "") -> List[Hypothesis]:
        """Propose hypotheses using the LLM, calibrated by history."""
        assessment = self.assess(graph)
        if assessment["node_count"] == 0:
            return []

        system_prompt = SPECIALIST_SYSTEM_PROMPT.format(
            agent_name=self.name,
            owned_description=self.description,
            owned_nodes_text=self._owned_nodes_text(graph),
            performance_text=self._performance_text(assessment),
            constraints_text=self._constraints_text(graph),
            history_text=self._history_text(),
            research_context=research_context[:8000] or "None provided.",
        )
        user_prompt = (
            f"Assess your nodes and propose up to {self.max_hypotheses} hypotheses. "
            "Return JSON only."
        )
        # 1. Always generate deterministic heuristics first — instant and reliable.
        heuristics = self._heuristic_hypotheses(graph)

        # 2. Try the LLM as an optional enrichment, with a hard cap.
        llm_hyps: List[Hypothesis] = []
        if self.use_llm:
            try:
                raw = call_llm(
                    [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_prompt}],
                    model=self.model,
                    timeout=self.llm_timeout,
                    max_tokens=1800,
                )
                llm_hyps = self._parse_hypotheses(raw, graph)
            except Exception:
                llm_hyps = []

        # 3. Merge: LLM hypotheses first (richer), heuristics as guaranteed floor.
        seen_titles = {h.title.lower() for h in llm_hyps}
        merged = list(llm_hyps)
        for h in heuristics:
            if h.title.lower() not in seen_titles:
                merged.append(h)
        return merged

    def _parse_hypotheses(self, raw: str, graph: Optional[BusinessGraph] = None) -> List[Hypothesis]:
        """Parse the LLM JSON into Hypothesis objects."""
        text = raw.strip()
        # Strip code fences
        if "```" in text:
            start = text.find("```")
            end = text.rfind("```")
            if end > start:
                text = text[start:end]
                text = text.replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to find the first { ... } block
            try:
                s = text.find("{")
                e = text.rfind("}")
                data = json.loads(text[s:e + 1])
            except Exception:
                return []

        out: List[Hypothesis] = []
        for h in data.get("hypotheses", []):
            try:
                lever = LeverType(h.get("lever_type", "other"))
            except ValueError:
                lever = LeverType.OTHER
            preds = []
            for p in h.get("predictions", []):
                try:
                    preds.append(Prediction(
                        metric=p.get("metric", "monthly_impact"),
                        baseline=float(p.get("baseline", 0)),
                        predicted=float(p.get("predicted", 0)),
                        unit=p.get("unit", "GBP"),
                        horizon_days=int(p.get("horizon_days", 30)),
                        confidence=float(p.get("confidence", 0.5)),
                        rationale=p.get("rationale", ""),
                    ))
                except (TypeError, ValueError):
                    continue
            hyp = Hypothesis(
                agent_id=self.agent_id,
                title=h.get("title", "Untitled hypothesis"),
                description=h.get("description", ""),
                lever_type=lever,
                expected_impact_gbp=float(h.get("expected_impact_gbp", 0)),
                expected_impact_pct=float(h.get("expected_impact_pct", 0)),
                effort=float(h.get("effort", 3)),
                risk=float(h.get("risk", 0.3)),
                confidence=float(h.get("confidence", 0.5)),
                predictions=preds,
                rationale=h.get("rationale", ""),
                metadata={"assessment": data.get("assessment", "")},
            )
            # Attach the primary owned node so the arbiter knows the target
            if graph is not None:
                owned = sorted(self.owned_nodes(graph), key=lambda n: abs(n.value), reverse=True)
                if owned:
                    hyp.node_id = owned[0].id
                    hyp.node_label = owned[0].label
            out.append(hyp)
        return out

    def _heuristic_hypotheses(self, graph: BusinessGraph) -> List[Hypothesis]:
        """Rule-based fallback when the LLM is unavailable or returns nothing.

        Produces conservative, obviously-reasonable hypotheses from the
        performance data so the arbiter always has something to work with.
        """
        nodes = sorted(self.owned_nodes(graph), key=lambda n: abs(n.value), reverse=True)
        out: List[Hypothesis] = []
        for n in nodes[:3]:
            if n.value <= 0:
                continue
            # Declining node → stabilise / recover
            if n.trend == TrendDirection.DOWN or n.change_7d_pct < -2:
                out.append(Hypothesis(
                    agent_id=self.agent_id,
                    node_id=n.id, node_label=n.label,
                    title=f"Arrest decline in {n.label}",
                    description=f"{n.label} is down {abs(n.change_7d_pct):.1f}% over 7 days. "
                                f"Diagnose the cause (volume vs price vs mix) and apply a targeted corrective lever.",
                    lever_type=LeverType.RETENTION,
                    expected_impact_gbp=abs(n.value) * 0.03,
                    expected_impact_pct=3.0,
                    effort=3, risk=0.35, confidence=0.45,
                    rationale="Rule-based fallback: declining trend detected.",
                    source="heuristic",
                ))
            # Underperforming efficiency → process lever
            if n.efficiency is not None and n.efficiency < 1.0:
                gap = (1.0 - n.efficiency)
                out.append(Hypothesis(
                    agent_id=self.agent_id,
                    node_id=n.id, node_label=n.label,
                    title=f"Close efficiency gap on {n.label}",
                    description=f"{n.label} runs at {n.efficiency:.2f}x efficiency. "
                                f"Investigate waste, rework, or idle capacity and close the gap.",
                    lever_type=LeverType.PROCESS,
                    expected_impact_gbp=abs(n.value) * gap * 0.2,
                    expected_impact_pct=gap * 20,
                    effort=4, risk=0.4, confidence=0.4,
                    rationale="Rule-based fallback: efficiency below 1.0x.",
                    source="heuristic",
                ))
            # Growing node → lean in
            if n.trend == TrendDirection.UP and n.change_7d_pct > 2:
                out.append(Hypothesis(
                    agent_id=self.agent_id,
                    node_id=n.id, node_label=n.label,
                    title=f"Lean into growth in {n.label}",
                    description=f"{n.label} is up {n.change_7d_pct:.1f}% over 7 days. "
                                f"Identify what is working and amplify it before the trend fades.",
                    lever_type=LeverType.VOLUME,
                    expected_impact_gbp=abs(n.value) * 0.02,
                    expected_impact_pct=2.0,
                    effort=2, risk=0.3, confidence=0.5,
                    rationale="Rule-based fallback: positive momentum detected.",
                    source="heuristic",
                ))
        return out

    # ── Step 3: Rank ──────────────────────────────────────────────────────

    def rank(self, hypotheses: List[Hypothesis]) -> List[Hypothesis]:
        """Score and sort hypotheses by risk-adjusted expected value."""
        for h in hypotheses:
            # Blend in historical calibration for the lever
            calib_factor = 1.0
            if self.knowledge:
                c = self.knowledge.calibration(lever_type=h.lever_type.value)
                if c["n"] >= 3 and c["mean_accuracy"] is not None:
                    calib_factor = max(0.5, min(1.5, c["mean_accuracy"]))
            h.score = h.risk_adjusted_value() * calib_factor
            h.metadata["calibration_factor"] = round(calib_factor, 3)
        ranked = sorted(hypotheses, key=lambda h: h.score, reverse=True)
        for i, h in enumerate(ranked):
            h.rank = i + 1
        return ranked

    # ── Step 4: Recommend ─────────────────────────────────────────────────

    def recommend(self, graph: BusinessGraph, research_context: str = "") -> Dict[str, Any]:
        """Full loop: assess → generate → rank → return top-N."""
        assessment = self.assess(graph)
        hypotheses = self.generate(graph, research_context)
        ranked = self.rank(hypotheses)
        top = ranked[: self.max_hypotheses]
        if self.knowledge:
            for h in ranked:
                try:
                    self.knowledge.record_hypothesis(h)
                except Exception:
                    pass
        return {
            "agent_id": self.agent_id,
            "agent_name": self.name,
            "assessment": assessment,
            "hypotheses": [h.to_dict() for h in top],
            "all_hypothesis_count": len(ranked),
        }


# ── Concrete specialists ──────────────────────────────────────────────────

@dataclass
class RevenueOptimizer(SpecialistAgent):
    agent_id: str = "revenue_optimizer"
    name: str = "Revenue Optimizer"
    description: str = "revenue nodes — pricing, volume, mix, and channel economics"
    owned_types: List[NodeType] = field(default_factory=lambda: [NodeType.REVENUE])

    def relevant_levers(self):
        return [LeverType.PRICE, LeverType.VOLUME, LeverType.MENU, LeverType.RETENTION]


@dataclass
class CostController(SpecialistAgent):
    agent_id: str = "cost_controller"
    name: str = "Cost Controller"
    description: str = "cost nodes — COGS, overheads, procurement, waste"
    owned_types: List[NodeType] = field(default_factory=lambda: [NodeType.COST])

    def relevant_levers(self):
        return [LeverType.COST_REDUCTION, LeverType.PROCUREMENT]


@dataclass
class MarketingAgent(SpecialistAgent):
    agent_id: str = "marketing_agent"
    name: str = "Marketing & Demand Agent"
    description: str = "demand-side levers on revenue nodes — campaigns, local marketing, promotions, loyalty"
    owned_types: List[NodeType] = field(default_factory=lambda: [NodeType.REVENUE])

    def relevant_levers(self):
        return [LeverType.DEMAND_GEN, LeverType.MARKETING, LeverType.RETENTION]


@dataclass
class OperationsAgent(SpecialistAgent):
    agent_id: str = "operations_agent"
    name: str = "Operations Agent"
    description: str = "process nodes — throughput, cycle time, utilisation, capacity"
    owned_types: List[NodeType] = field(default_factory=lambda: [NodeType.PROCESS])

    def relevant_levers(self):
        return [LeverType.PROCESS, LeverType.CAPACITY]


@dataclass
class StaffingAgent(SpecialistAgent):
    agent_id: str = "staffing_agent"
    name: str = "Staffing & Labour Agent"
    description: str = "labour and input nodes — rota design, productivity, wage efficiency"
    owned_types: List[NodeType] = field(default_factory=lambda: [NodeType.INPUT])

    def relevant_levers(self):
        return [LeverType.STAFFING, LeverType.PROCESS]


def default_specialists(model: str = "deepseek/deepseek-v4.1-flash",
                        knowledge: Optional[HistoricalKnowledgeBase] = None,
                        constraint_store: Optional[ConstraintStore] = None) -> List[SpecialistAgent]:
    """Build the standard specialist roster."""
    specs = [
        RevenueOptimizer(model=model),
        CostController(model=model),
        MarketingAgent(model=model),
        OperationsAgent(model=model),
        StaffingAgent(model=model),
    ]
    for s in specs:
        s.knowledge = knowledge
        s.constraint_store = constraint_store
    return specs
