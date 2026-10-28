"""Strategy Arbiter & Controller — the root agent of the BAM hierarchy.

The arbiter receives ranked recommendations from every specialist, validates
them through the constraint checker, and selects a portfolio of initiatives that
maximises total risk-adjusted value subject to an effort budget and constraint
feasibility.

It then produces an OptimisationPlan with an LLM-written strategic narrative
that explains *why* this portfolio was chosen and what the business should do
next.

The arbiter does not execute. It decides. Execution is the orchestrator's job.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ..insights import call_llm
from ..model.core import BusinessGraph
from ..model.constraints import ConstraintStore
from .constraint_checker import ConstraintCheckerAgent, ValidationResult
from .hypothesis import (
    Hypothesis, Initiative, InitiativeStatus, LeverType, OptimisationPlan, find_active_duplicate,
)
from .knowledge import HistoricalKnowledgeBase

ARBITER_SYSTEM_PROMPT = """You are the Strategy Arbiter & Controller of "Business as a Machine"
(BAM). You sit at the root of a multi-agent hierarchy. Below you are specialist
agents (Revenue Optimizer, Cost Controller, Marketing Agent, Operations Agent,
Staffing Agent). Each has assessed its own slice of the business graph and
proposed ranked hypotheses.

Your job: select the best *portfolio* of initiatives to optimise the business
over the next 30 days. You are not a specialist — you are the strategist. You
balance across domains, avoid over-concentration, respect constraints and budget,
and explain your reasoning clearly to the business owner.

## Business context
{business_context}

## Specialist recommendations (ranked within each specialist)
{recommendations_text}

## Constraint verdicts
{constraints_text}

## Historical lessons
{history_text}

## Work already in flight
{active_text}

## Rules
1. Select a portfolio of 3-8 initiatives that maximises total risk-adjusted value.
2. Respect the effort budget of {budget_effort} units. Effort 1 = trivial, 10 = major programme.
3. Do not select more than 2 initiatives on the same node.
4. Prefer a balanced portfolio: at least one revenue-side and one cost-side initiative where sensible.
5. If a hypothesis was rejected by the constraint checker, do not select it.
6. Consider historical calibration: discount levers that have under-delivered before.
7. Write a short, direct narrative (4-8 sentences) explaining the strategy. No fluff. British English.
8. Give each selected initiative a one-line "why now" justification.
9. Active initiatives already hold part of the budget and count towards the per-node limit. Their
   predicted uplift is committed but not yet in the numbers. Favour work that complements them.

Return ONLY valid JSON:
{{
  "title": "short plan title",
  "narrative": "4-8 sentence strategic explanation",
  "selected": [
    {{"hypothesis_id": "...", "why_now": "one line"}}
  ],
  "rejected_reasons": {{"hypothesis_id": "why not selected"}}
}}
"""


@dataclass
class StrategyArbiter:
    """Root agent: aggregates, validates, and selects the optimisation portfolio."""

    agent_id: str = "strategy_arbiter"
    name: str = "Strategy Arbiter & Controller"
    model: str = "deepseek/deepseek-v4.1-flash"
    budget_effort: float = 20.0
    max_initiatives: int = 6
    use_llm: bool = True
    # Active (APPROVED/RUNNING) initiatives consume team capacity, so their
    # effort is deducted from this cycle's budget. Turn off to plan as if idle.
    reserve_budget_for_active: bool = True

    knowledge: Optional[HistoricalKnowledgeBase] = None
    constraint_store: Optional[ConstraintStore] = None
    checker: Optional[ConstraintCheckerAgent] = None

    # ── Aggregation ───────────────────────────────────────────────────────

    def collect(self, recommendations: List[Dict[str, Any]]) -> List[Hypothesis]:
        """Flatten specialist recommendations into a single hypothesis pool, deduped."""
        pool: List[Hypothesis] = []
        seen = set()
        for rec in recommendations:
            for h_dict in rec.get("hypotheses", []):
                h = self._dict_to_hypothesis(h_dict)
                if h is None:
                    continue
                # Dedupe by (node_id, title) — different specialists may propose the same action
                key = (h.node_id, h.title.lower().strip())
                if key in seen:
                    continue
                seen.add(key)
                pool.append(h)
        return pool

    def _dict_to_hypothesis(self, d: Dict[str, Any]) -> Optional[Hypothesis]:
        try:
            lever = LeverType(d.get("lever_type", "other"))
        except ValueError:
            lever = LeverType.OTHER
        from .hypothesis import Prediction
        preds = []
        for p in d.get("predictions", []):
            try:
                preds.append(Prediction(
                    metric=p.get("metric", ""),
                    baseline=float(p.get("baseline", 0)),
                    predicted=float(p.get("predicted", 0)),
                    unit=p.get("unit", "GBP"),
                    horizon_days=int(p.get("horizon_days", 30)),
                    confidence=float(p.get("confidence", 0.5)),
                    rationale=p.get("rationale", ""),
                ))
            except (TypeError, ValueError):
                continue
        return Hypothesis(
            id=d.get("id", ""),
            agent_id=d.get("agent_id", ""),
            node_id=d.get("node_id", ""),
            node_label=d.get("node_label", ""),
            title=d.get("title", ""),
            description=d.get("description", ""),
            lever_type=lever,
            expected_impact_gbp=float(d.get("expected_impact_gbp", 0)),
            expected_impact_pct=float(d.get("expected_impact_pct", 0)),
            effort=float(d.get("effort", 3)),
            risk=float(d.get("risk", 0.3)),
            confidence=float(d.get("confidence", 0.5)),
            constraints_ok=d.get("constraints_ok", True),
            soft_penalty_gbp=float(d.get("soft_penalty_gbp", 0)),
            score=float(d.get("score", 0)),
            rank=int(d.get("rank", 0)),
            rationale=d.get("rationale", ""),
            predictions=preds,
            metadata=d.get("metadata", {}),
        )

    # ── Validation ────────────────────────────────────────────────────────

    def validate_pool(self, pool: List[Hypothesis], graph: BusinessGraph) -> List[ValidationResult]:
        if not self.checker:
            self.checker = ConstraintCheckerAgent(self.constraint_store)
        return [self.checker.validate(h, graph) for h in pool]

    # ── Portfolio selection ───────────────────────────────────────────────

    def select_portfolio(self, pool: List[Hypothesis],
                         validations: List[ValidationResult],
                         budget_effort: Optional[float] = None,
                         active: Optional[List[Initiative]] = None) -> List[Hypothesis]:
        """Greedy knapsack by score/effort ratio, respecting node collision rules.

        ``active`` initiatives pre-occupy their nodes (so the max-2-per-node rule
        counts committed work) and, when ``reserve_budget_for_active`` is set,
        their recorded effort is reserved out of the budget.
        """
        budget = budget_effort if budget_effort is not None else self.budget_effort
        if active and self.reserve_budget_for_active:
            budget -= self._active_effort(active)
        vmap = {v.hypothesis_id: v for v in validations}

        candidates = []
        for h in pool:
            v = vmap.get(h.id)
            if v and not v.ok:
                continue
            h.constraints_ok = v.ok if v else True
            h.soft_penalty_gbp = v.soft_penalty_gbp if v else 0.0
            # Recompute score with penalty applied
            h.score = h.risk_adjusted_value()
            candidates.append(h)

        candidates.sort(key=lambda h: h.score, reverse=True)

        selected: List[Hypothesis] = []
        used_effort = 0.0
        node_counts: Dict[str, int] = {}
        for ini in active or []:
            node_counts[ini.node_id] = node_counts.get(ini.node_id, 0) + 1
        for h in candidates:
            if len(selected) >= self.max_initiatives:
                break
            if used_effort + h.effort > budget:
                continue
            if node_counts.get(h.node_id, 0) >= 2:
                continue
            selected.append(h)
            used_effort += h.effort
            node_counts[h.node_id] = node_counts.get(h.node_id, 0) + 1
        return selected

    # ── Active-initiative awareness ───────────────────────────────────────

    @staticmethod
    def _active_effort(active: List[Initiative]) -> float:
        # Effort is stored in metadata from this version on; older records count as 0.
        return sum(float(i.metadata.get("effort") or 0) for i in active)

    def _active_initiatives(self) -> List[Initiative]:
        if not self.knowledge:
            return []
        try:
            return self.knowledge.active_initiatives()
        except Exception:
            return []

    def _active_text(self, active: List[Initiative]) -> str:
        if not active or not self.knowledge:
            return "None — no initiatives are approved or running."
        pending = sum(i.predicted_impact_gbp for i in active)
        return (self.knowledge.active_initiatives_text() +
                f"\nCommitted but unrealised uplift: £{pending:,.0f}/mo. "
                f"Effort reserved: {self._active_effort(active):.1f} units.")

    # ── LLM narrative ─────────────────────────────────────────────────────

    def _business_context(self, graph: BusinessGraph) -> str:
        roots = [graph.nodes[r] for r in graph.root_nodes if r in graph.nodes]
        if not roots:
            return "No root node found."
        r = roots[0]
        return (
            f"{r.label}: £{r.value:,.2f}/month, 7d {r.change_7d_pct:+.1f}%, "
            f"30d {r.change_30d_pct:+.1f}%, trend {r.trend.value}. "
            f"Description: {r.description}"
        )

    def _recommendations_text(self, recommendations: List[Dict[str, Any]]) -> str:
        lines = []
        for rec in recommendations:
            lines.append(f"### {rec.get('agent_name', rec.get('agent_id'))}")
            assessment = rec.get("assessment", {})
            if isinstance(assessment, dict) and assessment.get("summary"):
                lines.append(f"Assessment: {assessment['summary']}")
            for h in rec.get("hypotheses", [])[:5]:
                lines.append(
                    f"- [{h.get('lever_type')}] {h.get('title')} | "
                    f"impact £{h.get('expected_impact_gbp', 0):,.0f}/mo | "
                    f"effort {h.get('effort')} | risk {h.get('risk')} | "
                    f"confidence {h.get('confidence')} | score {h.get('score', 0):.1f} | "
                    f"id={h.get('id')} | node={h.get('node_id')}"
                )
        return "\n".join(lines)

    def _constraints_text(self, validations: List[ValidationResult]) -> str:
        lines = []
        for v in validations:
            if not v.ok:
                lines.append(f"- {v.hypothesis_id}: REJECTED — {v.verdict}")
            elif v.soft_penalty_gbp > 0:
                lines.append(f"- {v.hypothesis_id}: £{v.soft_penalty_gbp:,.2f} soft penalty")
        return "\n".join(lines) or "No constraint issues."

    def _history_text(self) -> str:
        if not self.knowledge:
            return "No history."
        return self.knowledge.lessons_text(limit=8)

    def decide(self, graph: BusinessGraph,
               recommendations: List[Dict[str, Any]],
               research_context: str = "") -> OptimisationPlan:
        """Full arbiter loop: collect → validate → select → narrate.

        Active initiatives (APPROVED/RUNNING in the knowledge base) shape every
        cycle:
          * hypotheses duplicating them (same node + lever, or same title) are
            removed from the pool and listed in ``plan.rejected`` with the reason
            in ``metadata["rejected_reason"]`` — no duplicate work;
          * they count towards the max-2-per-node rule and, by default, their
            effort is reserved from the budget (see ``select_portfolio``);
          * the LLM sees them, with their committed-but-unrealised uplift, so it
            treats the current numbers as "before" and favours complementary work.
        """
        active = self._active_initiatives()
        pool = self.collect(recommendations)
        duplicates: List[Hypothesis] = []
        if active:
            kept = []
            for h in pool:
                dup = find_active_duplicate(h, active)
                if dup is None:
                    kept.append(h)
                else:
                    h.metadata["rejected_reason"] = f"Duplicates active initiative '{dup.title}' ({dup.id})"
                    duplicates.append(h)
            pool = kept
        if not pool:
            return OptimisationPlan(title="No hypotheses", narrative="No specialist produced a viable hypothesis.",
                                    rejected=duplicates,
                                    metadata={"active_initiatives": [self._active_summary(i) for i in active]})

        validations = self.validate_pool(pool, graph)
        selected = self.select_portfolio(pool, validations, active=active)

        # LLM narrative — give it the selected set and the full pool
        system_prompt = ARBITER_SYSTEM_PROMPT.format(
            business_context=self._business_context(graph),
            recommendations_text=self._recommendations_text(recommendations),
            constraints_text=self._constraints_text(validations),
            history_text=self._history_text(),
            active_text=self._active_text(active),
            budget_effort=self.budget_effort,
        )
        selected_ids = [h.id for h in selected]
        if self.use_llm:
            user_prompt = (
                "Select the portfolio and explain. The pre-scored candidates are listed above. "
                f"Pre-computed selection by the knapsack solver: {selected_ids}. "
                "You may adjust this selection if the strategy demands it. Return JSON only."
            )
            try:
                raw = call_llm(
                    [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_prompt}],
                    model=self.model,
                    timeout=40,
                    max_tokens=1500,
                )
                decision = self._parse_decision(raw, pool)
            except Exception:
                decision = {"title": "Portfolio plan", "narrative": "", "selected_ids": selected_ids, "why_now": {}}
        else:
            decision = {
                "title": "Portfolio plan (deterministic)",
                "narrative": f"Selected {len(selected)} initiatives by risk-adjusted value within budget £{self.budget_effort:.0f}.",
                "selected_ids": selected_ids,
                "why_now": {h.id: h.rationale for h in selected},
            }

        # Build initiatives from the final selection
        chosen_ids = decision.get("selected_ids") or selected_ids
        by_id = {h.id: h for h in pool}
        vmap = {v.hypothesis_id: v for v in validations}
        initiatives: List[Initiative] = []
        total_impact = 0.0
        total_effort = 0.0
        total_risk = 0.0
        for hid in chosen_ids:
            h = by_id.get(hid)
            if not h:
                continue
            v = vmap.get(hid)
            if v and not v.ok:
                continue
            why = decision.get("why_now", {}).get(hid, h.rationale)
            ini = Initiative(
                hypothesis_id=h.id,
                agent_id=h.agent_id,
                node_id=h.node_id,
                node_label=h.node_label,
                title=h.title,
                description=h.description,
                lever_type=h.lever_type,
                status=InitiativeStatus.PROPOSED,
                predictions=h.predictions,
                predicted_impact_gbp=h.net_impact_gbp,
                owner=self.agent_id,
                metadata={
                    "why_now": why,
                    "validation": v.to_dict() if v else None,
                    # Carried so the detail view, progress agent and future
                    # budget reservation don't need the hypothesis record.
                    "effort": h.effort,
                    "risk": h.risk,
                    "confidence": h.confidence,
                    "rationale": h.rationale,
                    "expected_impact_pct": h.expected_impact_pct,
                    "source": h.source,
                },
            )
            initiatives.append(ini)
            total_impact += h.net_impact_gbp
            total_effort += h.effort
            total_risk += h.risk

        plan = OptimisationPlan(
            title=decision.get("title", "Optimisation Plan"),
            narrative=decision.get("narrative", ""),
            initiatives=initiatives,
            total_expected_impact_gbp=total_impact,
            total_effort=total_effort,
            total_risk=total_risk / max(len(initiatives), 1),
            budget_used_pct=(total_effort / self.budget_effort * 100) if self.budget_effort else 0,
            rejected=[h for h in pool if h.id not in chosen_ids] + duplicates,
            metadata={
                "validations": [v.to_dict() for v in validations],
                "active_initiatives": [self._active_summary(i) for i in active],
                "skipped_as_active_duplicate": [h.id for h in duplicates],
                "effort_reserved_for_active": self._active_effort(active) if self.reserve_budget_for_active else 0.0,
            },
        )
        return plan

    @staticmethod
    def _active_summary(ini: Initiative) -> Dict[str, Any]:
        return {"id": ini.id, "title": ini.title, "node_id": ini.node_id,
                "status": ini.status.value, "predicted_impact_gbp": round(ini.predicted_impact_gbp, 2)}

    def _parse_decision(self, raw: str, pool: List[Hypothesis]) -> Dict[str, Any]:
        text = raw.strip()
        if "```" in text:
            s = text.find("```"); e = text.rfind("```")
            if e > s:
                text = text[s:e].replace("```json", "").replace("```", "").strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            try:
                s = text.find("{"); e = text.rfind("}")
                data = json.loads(text[s:e + 1])
            except Exception:
                # Fallback: accept all pre-scored candidates
                return {"title": "Auto-selected plan",
                        "narrative": "LLM narrative unavailable; using knapsack selection.",
                        "selected_ids": [h.id for h in pool[:self.max_initiatives]],
                        "why_now": {}}
        selected = []
        for item in data.get("selected", []):
            hid = item.get("hypothesis_id") if isinstance(item, dict) else str(item)
            if hid:
                selected.append(hid)
        why = {}
        for item in data.get("selected", []):
            if isinstance(item, dict) and item.get("hypothesis_id"):
                why[item["hypothesis_id"]] = item.get("why_now", "")
        return {
            "title": data.get("title", "Optimisation Plan"),
            "narrative": data.get("narrative", ""),
            "selected_ids": selected,
            "why_now": why,
        }
