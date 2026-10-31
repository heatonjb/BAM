"""Multi-Agent Orchestrator — the engine that runs BAM optimisation cycles.

Ties together the specialist roster, the constraint checker, the strategy
arbiter, the historical knowledge base, and the external connectors.

Responsibilities:
  1. Build the agent roster for a given control model.
  2. Run an optimisation cycle and return an OptimisationPlan.
  3. Register selected initiatives in the knowledge base with predictions.
  4. Measure initiatives when actuals arrive, computing accuracy.
  5. Route execution to external tools when configured.

The orchestrator is stateless between cycles except for the knowledge base,
which persists in SQLite. A multi-tenant deployment would hold one orchestrator
per tenant with its own knowledge base path.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..context import get_research_context
from ..model.core import BusinessGraph
from ..model.constraints import ConstraintStore, build_default_constraints
from .arbiter import StrategyArbiter
from .constraint_checker import ConstraintCheckerAgent
from .control_models import ControlModel, get_runner
from .external import ConnectorRegistry, build_default_registry
from .hypothesis import Hypothesis, Initiative, InitiativeStatus, OptimisationPlan
from .knowledge import HistoricalKnowledgeBase
from .capabilities import get_tenant_mechanism
from .mechanisms import get_mechanism
from .montecarlo import (
    DriverSet, MonteCarloEngine, MonteCarloResult, drivers_from_graph, simulate,
)
from .projection import (
    AdoptionCurve, ProjectionEngine, ProjectionResult, baseline_from_business,
)
from .specialist import SpecialistAgent, default_specialists


@dataclass
class OrchestratorConfig:
    tenant_id: str = "jonco"
    model: str = "deepseek/deepseek-v4.1-flash"
    control_model: ControlModel = ControlModel.HIERARCHICAL
    budget_effort: float = 20.0
    max_initiatives: int = 6
    db_path: Optional[str] = None
    connectors: Optional[ConnectorRegistry] = None


@dataclass
class MultiAgentOrchestrator:
    """Runs BAM optimisation cycles end-to-end."""

    config: OrchestratorConfig = field(default_factory=OrchestratorConfig)
    knowledge: Optional[HistoricalKnowledgeBase] = None
    constraint_store: Optional[ConstraintStore] = None
    specialists: List[SpecialistAgent] = field(default_factory=list)
    arbiter: Optional[StrategyArbiter] = None
    checker: Optional[ConstraintCheckerAgent] = None
    registry: Optional[ConnectorRegistry] = None
    # Flat business object (loader output with ``monthly_pnl``) used as the
    # projection baseline. Optional so existing construction is unaffected.
    business: Any = None

    def __post_init__(self):
        if self.knowledge is None:
            kw = {}
            if self.config.db_path:
                kw["db_path"] = self.config.db_path
            self.knowledge = HistoricalKnowledgeBase(**kw)
        if self.constraint_store is None:
            self.constraint_store = ConstraintStore()
            for c in build_default_constraints():
                self.constraint_store.add(c)
        if self.checker is None:
            self.checker = ConstraintCheckerAgent(self.constraint_store)
        if not self.specialists:
            self.specialists = default_specialists(
                model=self.config.model,
                knowledge=self.knowledge,
                constraint_store=self.constraint_store,
            )
        if self.arbiter is None:
            self.arbiter = StrategyArbiter(
                model=self.config.model,
                budget_effort=self.config.budget_effort,
                max_initiatives=self.config.max_initiatives,
                knowledge=self.knowledge,
                constraint_store=self.constraint_store,
                checker=self.checker,
            )
        if self.registry is None:
            self.registry = self.config.connectors or build_default_registry()

    @property
    def _kb(self) -> HistoricalKnowledgeBase:
        assert self.knowledge is not None, "knowledge base not initialised"
        return self.knowledge

    # ── Main cycle ────────────────────────────────────────────────────────

    def run_cycle(self, graph: BusinessGraph,
                  research_context: str = "") -> OptimisationPlan:
        """Run one full optimisation cycle."""
        if not research_context:
            # Pull research context for the root node type
            roots = [graph.nodes[r] for r in graph.root_nodes if r in graph.nodes]
            ntype = roots[0].node_type.value if roots else "graph"
            research_context = get_research_context(ntype, ntype, "business")

        runner = get_runner(self.config.control_model)
        plan = runner.run(graph, self.specialists, self.arbiter, research_context)

        # Register selected initiatives so predictions are captured before action
        for ini in plan.initiatives:
            try:
                self._kb.record_initiative(ini)
            except Exception:
                pass
        return plan

    # ── Execution & measurement ───────────────────────────────────────────

    def approve_initiative(self, initiative_id: str) -> Optional[Initiative]:
        ini = self._kb.get_initiative(initiative_id)
        if not ini:
            return None
        ini.status = InitiativeStatus.APPROVED
        from datetime import datetime, timezone
        ini.approved_at = datetime.now(timezone.utc).isoformat()
        self._kb.record_initiative(ini)
        return ini

    def start_initiative(self, initiative_id: str,
                         external_ref: Optional[str] = None) -> Optional[Initiative]:
        ini = self._kb.get_initiative(initiative_id)
        if not ini:
            return None
        ini.status = InitiativeStatus.RUNNING
        from datetime import datetime, timezone
        ini.started_at = datetime.now(timezone.utc).isoformat()
        if external_ref:
            ini.external_ref = external_ref
        self._kb.record_initiative(ini)
        return ini

    def execute_via_connector(self, initiative_id: str,
                              connector_name: str,
                              action: str,
                              params: Dict[str, Any]) -> Dict[str, Any]:
        """Route an initiative's execution to an external tool."""
        if not self.registry:
            return {"ok": False, "error": "No connector registry"}
        conn = self.registry.get(connector_name)
        if not conn:
            return {"ok": False, "error": f"Connector '{connector_name}' not found"}
        result = conn.execute(action, params)
        if result.get("ok") and result.get("external_ref"):
            self.start_initiative(initiative_id, external_ref=result["external_ref"])
        return result

    def measure_initiative(self, initiative_id: str,
                           actual_impact_gbp: float,
                           actual_metrics: Optional[Dict[str, float]] = None,
                           notes: Optional[List[str]] = None) -> Optional[Initiative]:
        return self._kb.measure(initiative_id, actual_impact_gbp, actual_metrics, notes)

    # ── Projection & constraint gating ────────────────────────────────────

    def project_initiative(self, initiative: Initiative,
                           mechanism_name: str,
                           months: int = 12,
                           *,
                           business: Any = None,
                           volume_lift: float = 0.0,
                           curve: Optional[AdoptionCurve] = None,
                           liability_treatment: Optional[str] = None,
                           tenant_id: Optional[str] = None,
                           **mechanism_params: Any) -> ProjectionResult:
        """Project an initiative's mechanism over ``months`` and attach the result.

        The baseline comes from ``business`` (falling back to ``self.business``)
        via ``baseline_from_business``. The baseline is also stashed in
        ``initiative.metadata["projection_baseline"]`` so ``constraint_gate``
        can scale penalties against it.
        """
        business = business if business is not None else self.business
        if business is None:
            raise ValueError(
                "project_initiative needs a business object (pass business= or set "
                "MultiAgentOrchestrator.business)"
            )
        baseline = baseline_from_business(business)
        # Tenant agents own which mechanisms exist; core only knows families.
        # With tenant_id set, resolution goes through the tenant's declarations
        # so one tenant can never instantiate another's commercial terms.
        if tenant_id:
            mechanism = get_tenant_mechanism(
                tenant_id, mechanism_name, overrides=mechanism_params or None
            )
        else:
            mechanism = get_mechanism(mechanism_name, **mechanism_params)
        engine = ProjectionEngine(baseline, volume_lift=volume_lift, months=months)
        result = engine.project(mechanism, curve=curve,
                                liability_treatment=liability_treatment)

        initiative.projection_result = result
        initiative.mechanism = mechanism_name
        initiative.metadata["projection_baseline"] = baseline
        return result

    def monte_carlo_initiative(
        self,
        initiative: Initiative,
        mechanism_name: Optional[str] = None,
        *,
        mechanism_params: Optional[Dict[str, Any]] = None,
        months: int = 12,
        draws: int = 2000,
        seed: Optional[int] = None,
        volume_lift: Optional[float] = None,
        confidence: Optional[float] = None,
        curve_kind: str = "logistic",
        curve_params: Optional[Dict[str, float]] = None,
        graph: Optional[BusinessGraph] = None,
        business: Any = None,
        constraint_probe=None,
    ) -> MonteCarloResult:
        """Attach a distribution of outcomes to an initiative.

        ``project_initiative`` answers "what does this do if my assumptions
        hold". This answers "how much could the answer move", by sampling the
        assumptions the projection is most sensitive to — the target node's own
        historical dispersion, the adoption ramp, and the mechanism's decision
        parameters — and projecting a full P&L curve for every draw.

        The result lands in ``initiative.metadata["monte_carlo"]`` so it travels
        with the initiative through the API and the knowledge base, and a
        two-number summary (P10/P90) is written to
        ``initiative.metadata["predicted_range_gbp"]`` for list views that do
        not want the full distribution.
        """
        business = business if business is not None else self.business
        if business is None:
            raise ValueError(
                "monte_carlo_initiative needs a business object (pass business= or "
                "set MultiAgentOrchestrator.business)"
            )
        assumed = False
        if mechanism_name is None:
            mechanism_name = getattr(initiative, "mechanism", None) or "loyalty_card"
            assumed = getattr(initiative, "mechanism", None) is None
        params = dict(mechanism_params or {})
        if not params:
            params = dict(initiative.metadata.get("mechanism_params") or {})
        if not params and mechanism_name == "loyalty_card":
            params = {"n_paid": 9}
            assumed = True

        conf = confidence
        if conf is None:
            try:
                conf = float(initiative.metadata.get("confidence", 0.5))
            except (TypeError, ValueError):
                conf = 0.5

        base = baseline_from_business(business)
        mech = get_mechanism(mechanism_name, **params)
        drivers = drivers_from_graph(
            graph,
            initiative.node_id,
            confidence=conf,
            base_lift=volume_lift,
            mechanism=mech,
            baseline=base,
            months=months,
        )
        engine = MonteCarloEngine(
            base, mech, drivers, months=months,
            curve_kind=curve_kind, curve_params=curve_params,
        )
        result = engine.run(draws=draws, seed=seed, constraint_probe=constraint_probe)

        payload = result.to_dict()
        payload["mechanism"] = mechanism_name
        payload["mechanism_params"] = params
        payload["assumed_mechanism"] = assumed
        payload["computed_at"] = datetime.now(timezone.utc).isoformat()
        initiative.metadata["monte_carlo"] = payload
        initiative.metadata["predicted_range_gbp"] = [
            round(result.p10, 2), round(result.p90, 2),
        ]
        initiative.mechanism = mechanism_name
        try:
            self.knowledge.record_initiative(initiative)
        except Exception:
            pass
        return result

    def constraint_gate(self, projection: ProjectionResult,
                        checker: Optional[ConstraintCheckerAgent] = None,
                        *,
                        initiative: Optional[Initiative] = None,
                        graph: Optional[BusinessGraph] = None,
                        baseline_units: Optional[float] = None) -> Dict[str, Any]:
        """Gate a projection through the constraint checker.

        HARD violations block the projection outright. SOFT penalties from the
        checker are monthly £ figures; they are scaled across the horizon by
        projected volume relative to baseline (more units → more customers
        hitting a soft limit), then deducted from projected operating profit.

        ``baseline_units`` defaults to the baseline stored on ``initiative`` by
        ``project_initiative``; without it the volume scale is 1.0.
        """
        checker = checker or self.checker
        n_months = len(projection.months)
        monthly_delta = projection.delta_operating_profit / n_months if n_months else 0.0

        # Synthetic hypothesis so the checker's existing matching logic applies.
        # Peak monthly volume is offered as a numeric hint for max_volume caps.
        probe = Hypothesis(expected_impact_gbp=monthly_delta)
        if initiative is not None:
            probe.node_id = initiative.node_id
            probe.node_label = initiative.node_label
            probe.title = initiative.title
            probe.description = initiative.description
            probe.lever_type = initiative.lever_type
            probe.metadata = dict(initiative.metadata)
        probe.metadata.setdefault(
            "max_volume", max((m.volume for m in projection.months), default=0.0)
        )
        verdict = checker.validate(probe, graph) if checker else None

        if baseline_units is None and initiative is not None:
            baseline_units = initiative.metadata.get("projection_baseline", {}).get("units")
        projected_units = sum(m.volume for m in projection.months)
        if baseline_units and n_months:
            volume_scale = projected_units / (baseline_units * n_months)
        else:
            volume_scale = 1.0

        monthly_soft = verdict.soft_penalty_gbp if verdict else 0.0
        soft_penalty_gbp = monthly_soft * n_months * volume_scale
        hard_violations = verdict.hard_violations if verdict else []

        return {
            "allowed": not hard_violations,
            "hard_violations": hard_violations,
            "soft_violations": verdict.soft_violations if verdict else [],
            "soft_penalty_gbp": round(soft_penalty_gbp, 2),
            "volume_scale": round(volume_scale, 4),
            "adjusted_operating_profit": round(
                projection.total_operating_profit - soft_penalty_gbp, 2
            ),
        }

    # ── Reporting ─────────────────────────────────────────────────────────

    def calibration_report(self) -> Dict[str, Any]:
        """Report on how well BAM's predictions have held up."""
        all_ini = [i for i in self._kb.list_initiatives(limit=500)
                   if i.actual_impact_gbp is not None]
        if not all_ini:
            return {"measured": 0, "message": "No measured initiatives yet."}
        ratios = [i.accuracy_ratio for i in all_ini if i.accuracy_ratio is not None]
        errors = [i.absolute_error_pct for i in all_ini if i.absolute_error_pct is not None]
        return {
            "measured": len(all_ini),
            "mean_accuracy_ratio": round(sum(ratios) / len(ratios), 3) if ratios else None,
            "mean_abs_error_pct": round(sum(errors) / len(errors), 1) if errors else None,
            "over_delivery_rate": round(sum(1 for r in ratios if r > 1) / len(ratios), 3) if ratios else None,
            "by_lever": {
                lever.value: self._kb.calibration(lever_type=lever.value)
                for lever in set(i.lever_type for i in all_ini)
            },
        }

    def status(self) -> Dict[str, Any]:
        """Current orchestrator state."""
        return {
            "tenant_id": self.config.tenant_id,
            "control_model": self.config.control_model.value,
            "specialists": [s.agent_id for s in self.specialists],
            "knowledge_db": self.knowledge.db_path if self.knowledge else None,
            "connectors": self.registry.names() if self.registry else [],
            "measured_initiatives": len([
                i for i in self._kb.list_initiatives(limit=500)
                if i.actual_impact_gbp is not None
            ]),
        }
