"""BAM multi-agent optimisation system.

Hierarchical multi-agent control for business graph optimisation.

    from mvp.multiagent import MultiAgentOrchestrator, OrchestratorConfig
    from mvp.multiagent.control_models import ControlModel

    orch = MultiAgentOrchestrator(OrchestratorConfig(control_model=ControlModel.HIERARCHICAL))
    plan = orch.run_cycle(graph)
    print(plan.narrative)
"""

from .hypothesis import (
    Hypothesis, Initiative, InitiativeStatus, LeverType, OptimisationPlan, Prediction,
)
from .knowledge import HistoricalKnowledgeBase
from .specialist import (
    SpecialistAgent, RevenueOptimizer, CostController, MarketingAgent,
    OperationsAgent, StaffingAgent, default_specialists,
)
from .constraint_checker import ConstraintCheckerAgent, ValidationResult
from .arbiter import StrategyArbiter
from .control_models import ControlModel, get_runner, describe_models, SPECS
from .orchestrator import MultiAgentOrchestrator, OrchestratorConfig
from .controller import (
    AutonomousGraphController, GraphHealthMonitor, HealthThresholds,
    ControllerState, BranchDiagnosis,
)
from .external import (
    BaseConnector, ClaudeCodeConnector, XeroConnector, LovableConnector,
    CRMConnector, WebhookConnector, ConnectorRegistry, build_default_registry,
)

__all__ = [
    "Hypothesis", "Initiative", "InitiativeStatus", "LeverType",
    "OptimisationPlan", "Prediction",
    "HistoricalKnowledgeBase",
    "SpecialistAgent", "RevenueOptimizer", "CostController", "MarketingAgent",
    "OperationsAgent", "StaffingAgent", "default_specialists",
    "ConstraintCheckerAgent", "ValidationResult",
    "StrategyArbiter",
    "ControlModel", "get_runner", "describe_models", "SPECS",
    "MultiAgentOrchestrator", "OrchestratorConfig",
    "AutonomousGraphController", "GraphHealthMonitor", "HealthThresholds",
    "ControllerState", "BranchDiagnosis",
    "BaseConnector", "ClaudeCodeConnector", "XeroConnector", "LovableConnector",
    "CRMConnector", "WebhookConnector", "ConnectorRegistry", "build_default_registry",
]
