"""Hypothesis and Initiative tracking for BAM.

A **Hypothesis** is a candidate change to the business graph, proposed by a
specialist agent. When selected and approved it becomes an **Initiative** — a
tracked graph mutation (project) with a predicted outcome and, later, a measured
actual outcome. This lets BAM learn which levers actually work.

Data flow:

    Specialist agent  ->  Hypothesis (candidate)
    Strategy arbiter  ->  selects portfolio of hypotheses
    Orchestrator      ->  registers Initiative with Prediction
    Reality           ->  actual outcome measured
    Knowledge base    ->  actual vs predicted → calibration for future scoring
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, List, Optional

if TYPE_CHECKING:
    from .projection import ProjectionResult


class InitiativeStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    RUNNING = "running"
    MEASURED = "measured"
    ABANDONED = "abandoned"


class LeverType(str, Enum):
    """Canonical lever taxonomy — used for historical calibration."""

    PRICE = "price"
    VOLUME = "volume"
    DEMAND_GEN = "demand_generation"
    COST_REDUCTION = "cost_reduction"
    PROCUREMENT = "procurement"
    STAFFING = "staffing"
    PROCESS = "process"
    MENU = "menu"
    RETENTION = "retention"
    CAPACITY = "capacity"
    MARKETING = "marketing"
    OTHER = "other"


@dataclass
class Prediction:
    """A single predicted metric outcome for an initiative."""

    metric: str                      # e.g. "monthly_revenue", "gross_margin_pct"
    baseline: float                  # value before the change
    predicted: float                 # expected value after the change
    unit: str = "GBP"
    horizon_days: int = 30           # measurement window
    confidence: float = 0.5          # 0..1
    rationale: str = ""

    @property
    def delta(self) -> float:
        return self.predicted - self.baseline

    @property
    def delta_pct(self) -> float:
        if self.baseline == 0:
            return 0.0
        return (self.delta / abs(self.baseline)) * 100.0

    def to_dict(self) -> dict:
        d = asdict(self)
        d["delta"] = round(self.delta, 2)
        d["delta_pct"] = round(self.delta_pct, 1)
        return d


@dataclass
class Hypothesis:
    """A candidate change proposed by a specialist agent."""

    id: str = field(default_factory=lambda: f"hyp_{uuid.uuid4().hex[:10]}")
    agent_id: str = ""
    node_id: str = ""
    node_label: str = ""
    title: str = ""
    description: str = ""
    lever_type: LeverType = LeverType.OTHER

    # Quantitative expectation
    expected_impact_gbp: float = 0.0      # monthly £ impact (signed)
    expected_impact_pct: float = 0.0      # % impact on the owned metric
    effort: float = 1.0                   # 1 (trivial) .. 10 (major programme)
    risk: float = 0.3                     # 0..1
    confidence: float = 0.5               # 0..1

    # Constraints
    constraints_ok: bool = True
    constraint_notes: List[str] = field(default_factory=list)
    soft_penalty_gbp: float = 0.0

    # Scoring (filled by ranker)
    score: float = 0.0
    rank: int = 0
    rationale: str = ""

    # Predictions
    predictions: List[Prediction] = field(default_factory=list)

    # Provenance
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    source: str = "llm"                   # "llm" | "heuristic" | "human"
    parent_hypothesis: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ── Derived ────────────────────────────────────────────────────────────

    @property
    def net_impact_gbp(self) -> float:
        """Impact after soft-constraint penalties."""
        return self.expected_impact_gbp - self.soft_penalty_gbp

    def risk_adjusted_value(self) -> float:
        """Expected value discounted by risk and effort."""
        if self.effort <= 0:
            effort = 1.0
        else:
            effort = self.effort
        return (self.net_impact_gbp * self.confidence * (1.0 - self.risk)) / effort

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "node_id": self.node_id,
            "node_label": self.node_label,
            "title": self.title,
            "description": self.description,
            "lever_type": self.lever_type.value if isinstance(self.lever_type, LeverType) else self.lever_type,
            "expected_impact_gbp": round(self.expected_impact_gbp, 2),
            "expected_impact_pct": round(self.expected_impact_pct, 2),
            "net_impact_gbp": round(self.net_impact_gbp, 2),
            "effort": self.effort,
            "risk": self.risk,
            "confidence": self.confidence,
            "risk_adjusted_value": round(self.risk_adjusted_value(), 2),
            "constraints_ok": self.constraints_ok,
            "constraint_notes": self.constraint_notes,
            "soft_penalty_gbp": round(self.soft_penalty_gbp, 2),
            "score": round(self.score, 4),
            "rank": self.rank,
            "rationale": self.rationale,
            "predictions": [p.to_dict() for p in self.predictions],
            "created_at": self.created_at,
            "source": self.source,
            "parent_hypothesis": self.parent_hypothesis,
            "metadata": self.metadata,
        }


@dataclass
class Initiative:
    """A tracked graph mutation / project selected from a hypothesis."""

    id: str = field(default_factory=lambda: f"ini_{uuid.uuid4().hex[:10]}")
    hypothesis_id: str = ""
    agent_id: str = ""
    node_id: str = ""
    node_label: str = ""
    title: str = ""
    description: str = ""
    lever_type: LeverType = LeverType.OTHER
    status: InitiativeStatus = InitiativeStatus.PROPOSED

    # What we predicted
    predictions: List[Prediction] = field(default_factory=list)
    predicted_impact_gbp: float = 0.0

    # What actually happened
    actual_impact_gbp: Optional[float] = None
    actual_metrics: Dict[str, float] = field(default_factory=dict)

    # Lifecycle timestamps
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    approved_at: Optional[str] = None
    started_at: Optional[str] = None
    measured_at: Optional[str] = None

    # Provenance
    owner: str = ""
    external_ref: Optional[str] = None    # e.g. Claude Code task id, Xero invoice id
    notes: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Time-phased projection (filled by MultiAgentOrchestrator.project_initiative)
    projection_result: Optional["ProjectionResult"] = None
    mechanism: Optional[str] = None       # registered mechanism name, e.g. "loyalty_card"

    # ── Derived ────────────────────────────────────────────────────────────

    @property
    def accuracy_ratio(self) -> Optional[float]:
        """actual / predicted. >1 = over-delivered."""
        if self.actual_impact_gbp is None or self.predicted_impact_gbp == 0:
            return None
        return self.actual_impact_gbp / self.predicted_impact_gbp

    @property
    def absolute_error_pct(self) -> Optional[float]:
        if self.actual_impact_gbp is None or self.predicted_impact_gbp == 0:
            return None
        return abs(self.actual_impact_gbp - self.predicted_impact_gbp) / abs(self.predicted_impact_gbp) * 100.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "hypothesis_id": self.hypothesis_id,
            "agent_id": self.agent_id,
            "node_id": self.node_id,
            "node_label": self.node_label,
            "title": self.title,
            "description": self.description,
            "lever_type": self.lever_type.value if isinstance(self.lever_type, LeverType) else self.lever_type,
            "status": self.status.value if isinstance(self.status, InitiativeStatus) else self.status,
            "predictions": [p.to_dict() for p in self.predictions],
            "predicted_impact_gbp": round(self.predicted_impact_gbp, 2),
            "actual_impact_gbp": round(self.actual_impact_gbp, 2) if self.actual_impact_gbp is not None else None,
            "actual_metrics": {k: round(v, 2) for k, v in self.actual_metrics.items()},
            "accuracy_ratio": round(self.accuracy_ratio, 3) if self.accuracy_ratio is not None else None,
            "absolute_error_pct": round(self.absolute_error_pct, 1) if self.absolute_error_pct is not None else None,
            "created_at": self.created_at,
            "approved_at": self.approved_at,
            "started_at": self.started_at,
            "measured_at": self.measured_at,
            "owner": self.owner,
            "external_ref": self.external_ref,
            "notes": self.notes,
            "metadata": self.metadata,
        }


def find_active_duplicate(hyp: Hypothesis, active: List[Initiative]) -> Optional[Initiative]:
    """Return the active initiative that ``hyp`` would duplicate, if any.

    A hypothesis duplicates committed work when it pulls the same lever on the
    same node, or carries the same title. Used by specialists and the arbiter so
    approved/running initiatives are not proposed again every cycle.
    """
    title = hyp.title.lower().strip()
    lever = hyp.lever_type.value if isinstance(hyp.lever_type, LeverType) else hyp.lever_type
    for ini in active:
        ini_lever = ini.lever_type.value if isinstance(ini.lever_type, LeverType) else ini.lever_type
        if ini.title.lower().strip() == title:
            return ini
        if hyp.node_id and ini.node_id == hyp.node_id and ini_lever == lever:
            return ini
    return None


@dataclass
class OptimisationPlan:
    """The arbiter's output: an ordered portfolio of initiatives to execute."""

    id: str = field(default_factory=lambda: f"plan_{uuid.uuid4().hex[:8]}")
    title: str = ""
    narrative: str = ""
    initiatives: List[Initiative] = field(default_factory=list)
    total_expected_impact_gbp: float = 0.0
    total_effort: float = 0.0
    total_risk: float = 0.0
    budget_used_pct: float = 0.0
    rejected: List[Hypothesis] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "narrative": self.narrative,
            "initiatives": [i.to_dict() for i in self.initiatives],
            "total_expected_impact_gbp": round(self.total_expected_impact_gbp, 2),
            "total_effort": round(self.total_effort, 2),
            "total_risk": round(self.total_risk, 3),
            "budget_used_pct": round(self.budget_used_pct, 1),
            "rejected": [h.to_dict() for h in self.rejected],
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
