"""Multi-agent control models for BAM.

This module documents the design space of multi-agent control architectures and
provides a factory so the orchestrator can run different strategies against the
same specialist roster.

The question is not "which model is best" but "which model fits which decision".
BAM needs several because business optimisation has several distinct decision
types: routine rebalancing, exploratory growth, crisis response, and portfolio
construction.

─────────────────────────────────────────────────────────────────────────────
THE MODELS
─────────────────────────────────────────────────────────────────────────────

1. HIERARCHICAL / COMMAND-AND-CONTROL  (default for routine cycles)
   Root arbiter issues objectives → specialists propose within their domain →
   arbiter selects. Clear accountability, predictable cost, single decision
   point. Bottleneck risk at the root; good when the graph is well-understood.

2. BLACKBOARD  (best for cross-domain discovery)
   Specialists read and write to a shared "blackboard" (the hypothesis pool +
   graph state). Each reacts to what others have posted. An arbiter monitors and
   decides when to stop. Emergent cross-domain hypotheses (e.g. marketing sees a
   revenue node a staffing change would unlock). Higher token cost; needs a
   stopping rule.

3. CONTRACT NET  (best when the set of specialists is dynamic or heterogeneous)
   Arbiter announces a goal ("improve gross margin by 3pp"). Specialists bid
   with a hypothesis + confidence + effort estimate. Arbiter awards the contract
   to the best bid. Naturally handles specialists with different capabilities and
   avoids running every specialist on every cycle. Overhead per round is higher.

4. MARKET / PORTFOLIO AUCTION  (best for capital allocation across many ideas)
   Every hypothesis is an "investment" with expected return, risk, and cost. The
   arbiter runs a knapsack/portfolio optimisation: maximise risk-adjusted return
   subject to effort budget and constraints. This is what BAM's arbiter actually
   does by default — it is the market model layered on top of the hierarchy.

5. DELIBERATIVE / DEBATE  (best for high-stakes, ambiguous decisions)
   Two or more specialists argue for competing hypotheses; a judge (arbiter or a
   separate LLM) scores the arguments. Expensive but surfaces hidden assumptions.
   Use sparingly: major pivots, pricing architecture changes, new locations.

6. SUBSUMPTION  (best for real-time operational control)
   Layered reactive behaviours; higher layers override lower ones when triggered.
   E.g. "stockout imminent" overrides "run marketing campaign". Fast and cheap,
   but not strategic. Useful later for live operational loops, not for planning.

─────────────────────────────────────────────────────────────────────────────
RECOMMENDED STRATEGY FOR BAM
─────────────────────────────────────────────────────────────────────────────

Use a HYBRID: hierarchical structure for accountability + market/portfolio
auction for selection + blackboard for cross-domain discovery + debate for
high-stakes calls. Concretely:

  - Routine cycle (daily/weekly): hierarchical + portfolio auction.
  - Exploratory cycle (monthly): blackboard enabled so specialists can build on
    each other's hypotheses.
  - High-stakes cycle (quarterly or on major change): debate between the top two
    competing portfolios, judged by a separate arbiter pass.
  - Operational loop (future): subsumption for live alerts.

This module implements the four planning models; subsumption is stubbed for the
operational layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from ..model.core import BusinessGraph
from .arbiter import StrategyArbiter
from .constraint_checker import ConstraintCheckerAgent
from .hypothesis import Hypothesis, OptimisationPlan
from .specialist import SpecialistAgent


class ControlModel(str, Enum):
    HIERARCHICAL = "hierarchical"
    BLACKBOARD = "blackboard"
    CONTRACT_NET = "contract_net"
    MARKET_AUCTION = "market_auction"
    DEBATE = "debate"
    SUBSUMPTION = "subsumption"


@dataclass
class ControlModelSpec:
    """Describes a control model's characteristics and when to use it."""

    model: ControlModel
    name: str
    description: str
    best_for: str
    cost: str          # low | medium | high
    latency: str       # low | medium | high
    coordination: str  # how agents coordinate
    failure_mode: str


SPECS: Dict[ControlModel, ControlModelSpec] = {
    ControlModel.HIERARCHICAL: ControlModelSpec(
        model=ControlModel.HIERARCHICAL,
        name="Hierarchical / Command-and-Control",
        description="Root arbiter issues objectives; specialists propose within domain; arbiter selects.",
        best_for="Routine rebalancing when the graph is well-understood and domains are cleanly separable.",
        cost="low",
        latency="low",
        coordination="Top-down objectives, bottom-up proposals.",
        failure_mode="Root bottleneck; misses cross-domain opportunities.",
    ),
    ControlModel.BLACKBOARD: ControlModelSpec(
        model=ControlModel.BLACKBOARD,
        name="Blackboard",
        description="Specialists read/write a shared hypothesis pool and react to each other's posts.",
        best_for="Cross-domain discovery and emergent hypotheses.",
        cost="high",
        latency="medium",
        coordination="Shared state; opportunistic triggering; arbiter stopping rule.",
        failure_mode="Runaway token cost; convergence failure without a stopping rule.",
    ),
    ControlModel.CONTRACT_NET: ControlModelSpec(
        model=ControlModel.CONTRACT_NET,
        name="Contract Net Protocol",
        description="Arbiter announces a goal; specialists bid with hypothesis + confidence + effort; arbiter awards.",
        best_for="Dynamic specialist sets and goal-directed allocation.",
        cost="medium",
        latency="medium",
        coordination="Announce → bid → award.",
        failure_mode="Bid inflation; specialists over-claim to win contracts.",
    ),
    ControlModel.MARKET_AUCTION: ControlModelSpec(
        model=ControlModel.MARKET_AUCTION,
        name="Market / Portfolio Auction",
        description="Hypotheses are investments; arbiter maximises risk-adjusted return under budget and constraints.",
        best_for="Capital allocation across many competing ideas.",
        cost="low",
        latency="low",
        coordination="Price discovery via scoring; knapsack selection.",
        failure_mode="Gaming if scoring is visible; ignores non-financial value.",
    ),
    ControlModel.DEBATE: ControlModelSpec(
        model=ControlModel.DEBATE,
        name="Deliberative / Debate",
        description="Competing hypotheses are argued; a judge scores the arguments.",
        best_for="High-stakes, ambiguous decisions (pricing architecture, new locations, pivots).",
        cost="high",
        latency="high",
        coordination="Advocate → rebut → judge.",
        failure_mode="Persuasion over truth; expensive.",
    ),
    ControlModel.SUBSUMPTION: ControlModelSpec(
        model=ControlModel.SUBSUMPTION,
        name="Subsumption",
        description="Layered reactive behaviours; higher layers override lower when triggered.",
        best_for="Real-time operational control and alerts.",
        cost="low",
        latency="very low",
        coordination="Layer priority; no deliberation.",
        failure_mode="Myopic; no strategic memory.",
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Runner implementations
# ─────────────────────────────────────────────────────────────────────────────

class HierarchicalRunner:
    """Hierarchical + portfolio auction (the default BAM cycle)."""

    model = ControlModel.HIERARCHICAL

    def run(self, graph: BusinessGraph, specialists: List[SpecialistAgent],
            arbiter: StrategyArbiter, research_context: str = "") -> OptimisationPlan:
        recommendations = []
        for s in specialists:
            try:
                rec = s.recommend(graph, research_context)
                recommendations.append(rec)
            except Exception as e:
                recommendations.append({
                    "agent_id": s.agent_id, "agent_name": s.name,
                    "assessment": {"summary": f"Specialist failed: {e}"},
                    "hypotheses": [],
                })
        return arbiter.decide(graph, recommendations, research_context)


class BlackboardRunner:
    """Shared hypothesis pool; specialists build on each other's posts."""

    model = ControlModel.BLACKBOARD

    def __init__(self, rounds: int = 2):
        self.rounds = rounds

    def run(self, graph: BusinessGraph, specialists: List[SpecialistAgent],
            arbiter: StrategyArbiter, research_context: str = "") -> OptimisationPlan:
        blackboard: List[Hypothesis] = []
        for r in range(self.rounds):
            round_recs = []
            for s in specialists:
                # Give each specialist the blackboard as extra context
                prior = "\n".join(
                    f"- [{h.lever_type.value}] {h.title} (impact £{h.expected_impact_gbp:,.0f})"
                    for h in blackboard[-12:]
                )
                ctx = research_context + (
                    f"\n\nBLACKBOARD (hypotheses already posted this cycle):\n{prior}"
                    if prior else ""
                )
                try:
                    rec = s.recommend(graph, ctx)
                except Exception as e:
                    rec = {"agent_id": s.agent_id, "agent_name": s.name,
                           "assessment": {"summary": f"failed: {e}"}, "hypotheses": []}
                round_recs.append(rec)
                for hd in rec.get("hypotheses", []):
                    h = arbiter._dict_to_hypothesis(hd)
                    if h:
                        blackboard.append(h)
            # Stop early if the pool is large enough
            if len(blackboard) >= 25:
                break
        # Build synthetic recommendations from the pooled blackboard
        grouped: Dict[str, List[Dict[str, Any]]] = {}
        for h in blackboard:
            grouped.setdefault(h.agent_id, []).append(h.to_dict())
        recommendations = [
            {"agent_id": aid, "agent_name": aid, "assessment": {}, "hypotheses": hs}
            for aid, hs in grouped.items()
        ]
        return arbiter.decide(graph, recommendations, research_context)


class ContractNetRunner:
    """Goal announcement → bids → award."""

    model = ControlModel.CONTRACT_NET

    def __init__(self, goal: str = "Maximise risk-adjusted profit improvement over 30 days."):
        self.goal = goal

    def run(self, graph: BusinessGraph, specialists: List[SpecialistAgent],
            arbiter: StrategyArbiter, research_context: str = "") -> OptimisationPlan:
        announcements = []
        for s in specialists:
            try:
                rec = s.recommend(graph, f"GOAL: {self.goal}\n\n{research_context}")
            except Exception as e:
                rec = {"agent_id": s.agent_id, "agent_name": s.name,
                       "assessment": {"summary": f"failed: {e}"}, "hypotheses": []}
            announcements.append(rec)
        return arbiter.decide(graph, announcements, research_context)


class DebateRunner:
    """Top-two portfolios argued and judged."""

    model = ControlModel.DEBATE

    def run(self, graph: BusinessGraph, specialists: List[SpecialistAgent],
            arbiter: StrategyArbiter, research_context: str = "") -> OptimisationPlan:
        # First pass: hierarchical selection
        base_plan = HierarchicalRunner().run(graph, specialists, arbiter, research_context)
        # Second pass: arbiter re-decides with explicit debate framing
        debate_context = (
            research_context
            + "\n\nDEBATE MODE: A rival plan has been proposed. Argue for or against each "
            "selected initiative on strategic grounds (risk, brand, operational load, "
            "second-order effects). Then finalise the portfolio."
        )
        recommendations = []
        for s in specialists:
            try:
                rec = s.recommend(graph, debate_context)
                recommendations.append(rec)
            except Exception:
                continue
        if not recommendations:
            return base_plan
        return arbiter.decide(graph, recommendations, debate_context)


class MarketAuctionRunner(HierarchicalRunner):
    """Identical to hierarchical but explicitly frames selection as an auction."""

    model = ControlModel.MARKET_AUCTION


RUNNERS = {
    ControlModel.HIERARCHICAL: HierarchicalRunner,
    ControlModel.BLACKBOARD: BlackboardRunner,
    ControlModel.CONTRACT_NET: ContractNetRunner,
    ControlModel.MARKET_AUCTION: MarketAuctionRunner,
    ControlModel.DEBATE: DebateRunner,
}


def get_runner(model: ControlModel, **kwargs):
    cls = RUNNERS.get(model, HierarchicalRunner)
    return cls(**kwargs)


def describe_models() -> str:
    """Human-readable comparison of all control models."""
    lines = ["# Multi-Agent Control Models for BAM\n"]
    for spec in SPECS.values():
        lines.append(f"## {spec.name}")
        lines.append(f"**Model:** `{spec.model.value}`  ")
        lines.append(f"**Description:** {spec.description}  ")
        lines.append(f"**Best for:** {spec.best_for}  ")
        lines.append(f"**Cost:** {spec.cost} | **Latency:** {spec.latency}  ")
        lines.append(f"**Coordination:** {spec.coordination}  ")
        lines.append(f"**Failure mode:** {spec.failure_mode}\n")
    lines.append("## Recommended strategy")
    lines.append(
        "Hybrid: hierarchical + market auction for routine cycles; blackboard for "
        "monthly exploration; debate for high-stakes calls; subsumption for future "
        "real-time operations."
    )
    return "\n".join(lines)
