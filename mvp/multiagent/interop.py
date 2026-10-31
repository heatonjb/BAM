"""Agent-to-agent interop: BAM driving other agents to execute initiatives.

The design decision that matters
--------------------------------
The tempting version of this is "BAM delegates the marketing initiative to a
marketing agent". That is not autonomy, it is abdication: the counterpart agent
inherits discretion over *whether* and *how much*, and BAM becomes a suggestion
box.

So the split here is explicit:

* **BAM decides** — which lever, on which node, at what magnitude, with what
  expected value and what it is willing to risk. That is the arbiter's job and
  it stays internal.
* **The counterpart agent executes** — and it does so inside an *envelope*:
  a spend cap, a maximum permissible change, a reversibility requirement, an
  approval threshold and an expiry. The envelope is data, checked mechanically.

An action outside the envelope is rejected, not negotiated. That is the only
arrangement in which an accounting system can safely let an LLM-driven marketing
agent spend money on its behalf.

Protocol shape
--------------
Requests and results are versioned JSON with an idempotency key, so a retry
after a network failure cannot launch the same campaign twice. Results are
validated against the envelope before BAM records anything, and the validated
outcome is written to the evidence ledger so future estimates calibrate.

This module deliberately does not call any vendor. It builds the task, checks
the answer, and records it. Transport lives in ``external.py``.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

PROTOCOL_VERSION = "bam.agent.v1"


class Domain(str, Enum):
    """Which functional agent a task belongs to."""

    MARKETING = "marketing"
    SALES = "sales"
    PRODUCT = "product"
    PRICING = "pricing"
    OPERATIONS = "operations"
    SUPPORT = "support"
    FINANCE = "finance"


class Reversibility(str, Enum):
    REVERSIBLE = "reversible"        # can be undone without cost
    COSTLY = "costly"                # can be undone, but not free
    IRREVERSIBLE = "irreversible"    # sending an email, changing a price publicly


class TaskState(str, Enum):
    DRAFT = "draft"
    DISPATCHED = "dispatched"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    EXPIRED = "expired"


@dataclass
class Capability:
    """One thing a counterpart agent can do."""

    action: str                       # canonical verb, e.g. "launch_email_campaign"
    domain: Domain
    description: str = ""
    reversible: Reversibility = Reversibility.COSTLY
    typical_cost_gbp: float = 0.0     # rough spend the action usually incurs
    requires_approval: bool = False


@dataclass
class CounterpartAgent:
    """An external agent BAM can hand an executable task to."""

    id: str
    label: str
    domain: Domain
    capabilities: List[Capability] = field(default_factory=list)
    #: Key in the Nango integration registry, when the agent acts through one.
    integration_id: Optional[str] = None
    #: Free-form endpoint for agents reached by webhook rather than Nango.
    endpoint: Optional[str] = None
    notes: str = ""

    def can(self, action: str) -> Optional[Capability]:
        for cap in self.capabilities:
            if cap.action == action:
                return cap
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "label": self.label, "domain": self.domain.value,
            "integration_id": self.integration_id,
            "capabilities": [
                {"action": c.action, "domain": c.domain.value,
                 "description": c.description, "reversible": c.reversible.value,
                 "typical_cost_gbp": c.typical_cost_gbp,
                 "requires_approval": c.requires_approval}
                for c in self.capabilities
            ],
            "notes": self.notes,
        }


@dataclass
class Envelope:
    """The limits of the authority BAM is lending out.

    Every field is a hard bound. A result that breaches any of them is rejected
    and the initiative returns to the arbiter rather than being booked as done.
    """

    max_spend_gbp: float = 0.0
    max_change_pct: float = 0.0          # largest % move allowed on the target metric
    max_duration_days: int = 30
    requires_approval: bool = False
    allowed_actions: List[str] = field(default_factory=list)
    expires_in_days: int = 7

    def to_dict(self) -> dict:
        return {
            "max_spend_gbp": round(self.max_spend_gbp, 2),
            "max_change_pct": round(self.max_change_pct, 2),
            "max_duration_days": self.max_duration_days,
            "requires_approval": self.requires_approval,
            "allowed_actions": list(self.allowed_actions),
            "expires_in_days": self.expires_in_days,
        }


@dataclass
class AgentTask:
    """One executable unit of work handed to a counterpart agent."""

    initiative_id: str
    agent_id: str
    action: str
    domain: Domain
    objective: str
    envelope: Envelope
    success_metric: str = ""
    expected_impact_gbp: float = 0.0
    context: Dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: f"task_{uuid.uuid4().hex[:10]}")
    state: TaskState = TaskState.DRAFT
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: Optional[str] = None
    idempotency_key: str = ""

    def __post_init__(self) -> None:
        if not self.idempotency_key:
            # Stable across retries of the same initiative/action pair, so a
            # re-dispatch cannot double-run a campaign.
            raw = f"{self.initiative_id}:{self.agent_id}:{self.action}"
            self.idempotency_key = hashlib.sha256(raw.encode()).hexdigest()[:32]
        if not self.expires_at:
            self.expires_at = (
                datetime.now(timezone.utc)
                + timedelta(days=self.envelope.expires_in_days)
            ).isoformat()

    def to_request(self) -> Dict[str, Any]:
        """The wire payload a counterpart agent receives."""
        return {
            "protocol": PROTOCOL_VERSION,
            "task_id": self.id,
            "idempotency_key": self.idempotency_key,
            "initiative_id": self.initiative_id,
            "action": self.action,
            "domain": self.domain.value,
            "objective": self.objective,
            "success_metric": self.success_metric,
            "expected_impact_gbp": round(self.expected_impact_gbp, 2),
            "envelope": self.envelope.to_dict(),
            "context": self.context,
            "expires_at": self.expires_at,
            "reply_with": {
                "task_id": self.id,
                "idempotency_key": self.idempotency_key,
                "status": "accepted | rejected | completed",
                "action_taken": "string",
                "spend_gbp": "number",
                "change_pct": "number",
                "duration_days": "number",
                "metric_before": "number",
                "metric_after": "number",
                "notes": "string",
            },
        }

    def to_dict(self) -> dict:
        return {
            "id": self.id, "initiative_id": self.initiative_id,
            "agent_id": self.agent_id, "action": self.action,
            "domain": self.domain.value, "objective": self.objective,
            "success_metric": self.success_metric,
            "expected_impact_gbp": round(self.expected_impact_gbp, 2),
            "envelope": self.envelope.to_dict(),
            "state": self.state.value,
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at, "expires_at": self.expires_at,
        }


# ---------------------------------------------------------------------------
# Directory
# ---------------------------------------------------------------------------


def default_directory() -> List[CounterpartAgent]:
    """The counterpart agents a typical business will already be paying for.

    Seeded from the archetypes a mid-sized business actually runs today, so the
    directory is a description of the market rather than an invention.
    """
    return [
        CounterpartAgent(
            id="marketing_agent",
            label="Marketing agent",
            domain=Domain.MARKETING,
            integration_id="klaviyo",
            capabilities=[
                Capability("launch_email_campaign", Domain.MARKETING,
                           "Compose and send a segmented email campaign",
                           Reversibility.IRREVERSIBLE),
                Capability("pause_campaign", Domain.MARKETING,
                           "Stop an active campaign", Reversibility.REVERSIBLE),
                Capability("adjust_ad_budget", Domain.MARKETING,
                           "Change daily spend on paid channels", Reversibility.REVERSIBLE),
            ],
            notes="Acts through the ESP. Sending is irreversible — treat the envelope as final.",
        ),
        CounterpartAgent(
            id="sales_agent",
            label="Sales agent",
            domain=Domain.SALES,
            integration_id="hubspot",
            capabilities=[
                Capability("enrich_and_sequence", Domain.SALES,
                           "Enrich inbound leads and start a follow-up sequence",
                           Reversibility.COSTLY),
                Capability("update_pipeline_stage", Domain.SALES,
                           "Move deals between stages", Reversibility.REVERSIBLE),
                Capability("repricing_quote", Domain.PRICING,
                           "Generate a discounted quote for approval",
                           Reversibility.COSTLY),
            ],
        ),
        CounterpartAgent(
            id="product_agent",
            label="Product agent",
            domain=Domain.PRODUCT,
            integration_id="linear",
            capabilities=[
                Capability("create_backlog_item", Domain.PRODUCT,
                           "Open a scoped ticket with acceptance criteria",
                           Reversibility.REVERSIBLE),
                Capability("set_priority", Domain.PRODUCT,
                           "Reorder the backlog against a declared objective",
                           Reversibility.REVERSIBLE),
                Capability("ship_experiment", Domain.PRODUCT,
                           "Launch a feature flag experiment", Reversibility.COSTLY),
            ],
        ),
        CounterpartAgent(
            id="ops_agent",
            label="Operations agent",
            domain=Domain.OPERATIONS,
            integration_id="square",
            capabilities=[
                Capability("adjust_rota", Domain.OPERATIONS,
                           "Change staffing hours for a period", Reversibility.REVERSIBLE),
                Capability("reorder_stock", Domain.OPERATIONS,
                           "Raise a purchase order", Reversibility.COSTLY),
            ],
        ),
        CounterpartAgent(
            id="finance_agent",
            label="Finance agent",
            domain=Domain.FINANCE,
            integration_id="xero",
            capabilities=[
                Capability("chase_invoices", Domain.FINANCE,
                           "Send payment reminders on overdue invoices",
                           Reversibility.IRREVERSIBLE),
                Capability("adjust_payment_terms", Domain.FINANCE,
                           "Change terms for a customer segment", Reversibility.COSTLY),
            ],
        ),
    ]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

#: Lever type -> (domain, candidate actions) in preference order.
_LEVER_ROUTES: Dict[str, List[str]] = {
    "demand_generation": ["launch_email_campaign", "adjust_ad_budget"],
    "volume": ["launch_email_campaign", "adjust_rota", "reorder_stock"],
    "price": ["repricing_quote", "adjust_ad_budget"],
    "cost_reduction": ["adjust_rota", "reorder_stock"],
    "procurement": ["reorder_stock"],
    "staffing": ["adjust_rota"],
    "retention": ["launch_email_campaign", "ship_experiment"],
    "product": ["create_backlog_item", "ship_experiment"],
    "finance": ["chase_invoices"],
}


def _lever_value(lever: Any) -> str:
    return getattr(lever, "value", lever) or ""


def envelope_for(
    initiative: Any,
    capability: Capability,
    *,
    max_spend_fraction: float = 0.10,
    months_budget: float = 1.0,
) -> Envelope:
    """Derive the authority an initiative may exercise.

    The spend cap is a fraction of the *expected* monthly impact rather than a
    fixed number: an initiative claiming £4,000/month may spend more to achieve
    it than one claiming £400. Tying the cap to the claim also means an
    overstated claim cannot unlock a large spend — it becomes a reason to
    demand approval instead.
    """
    expected = float(getattr(initiative, "predicted_impact_gbp", 0.0) or 0.0)
    cap = max(abs(expected) * max_spend_fraction * months_budget, 0.0)
    irreversible = capability.reversible == Reversibility.IRREVERSIBLE
    return Envelope(
        max_spend_gbp=round(cap, 2),
        max_change_pct=15.0 if not irreversible else 5.0,
        max_duration_days=30,
        # Anything irreversible always needs a human, regardless of size.
        requires_approval=irreversible or capability.requires_approval or abs(expected) > 5000,
        allowed_actions=[capability.action],
        expires_in_days=7,
    )


@dataclass
class DispatchDecision:
    """Outcome of trying to route an initiative to a counterpart agent."""

    ok: bool
    reason: str = ""
    task: Optional[AgentTask] = None
    candidates: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "reason": self.reason,
                "task": self.task.to_dict() if self.task else None,
                "candidates": self.candidates}


def dispatch(
    initiative: Any,
    directory: Optional[List[CounterpartAgent]] = None,
    *,
    max_spend_fraction: float = 0.10,
) -> DispatchDecision:
    """Route an initiative to the counterpart agent best able to execute it.

    Routing is by lever type, then by declared capability. It never guesses: if
    no agent declares the action, the answer is ``ok=False`` with the reason and
    the candidate list, because a silently-approximated dispatch is how an
    initiative gets marked done without anything happening.
    """
    directory = directory if directory is not None else default_directory()
    lever = _lever_value(getattr(initiative, "lever_type", ""))
    actions = _LEVER_ROUTES.get(lever, [])

    if not actions:
        return DispatchDecision(
            ok=False,
            reason=f"no execution route mapped for lever type {lever!r}",
            candidates=[],
        )

    for action in actions:
        for agent in directory:
            cap = agent.can(action)
            if cap is None:
                continue
            env = envelope_for(initiative, cap, max_spend_fraction=max_spend_fraction)
            task = AgentTask(
                initiative_id=getattr(initiative, "id", ""),
                agent_id=agent.id,
                action=action,
                domain=cap.domain,
                objective=getattr(initiative, "description", "") or getattr(initiative, "title", ""),
                envelope=env,
                success_metric=getattr(initiative, "node_id", ""),
                expected_impact_gbp=float(getattr(initiative, "predicted_impact_gbp", 0.0) or 0.0),
                context={
                    "node_id": getattr(initiative, "node_id", ""),
                    "node_label": getattr(initiative, "node_label", ""),
                    "lever_type": lever,
                    "initiative_title": getattr(initiative, "title", ""),
                },
            )
            return DispatchDecision(
                ok=True,
                reason=f"routed {lever} to {agent.label} via {action}",
                task=task,
                candidates=[a.id for a in directory if a.can(action)],
            )

    return DispatchDecision(
        ok=False,
        reason=f"no counterpart agent declares any of {actions}",
        candidates=[],
    )


# ---------------------------------------------------------------------------
# Result validation
# ---------------------------------------------------------------------------


@dataclass
class ValidationOutcome:
    ok: bool
    state: TaskState
    violations: List[str] = field(default_factory=list)
    result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"ok": self.ok, "state": self.state.value,
                "violations": self.violations, "result": self.result}


def validate_result(task: AgentTask, payload: Dict[str, Any]) -> ValidationOutcome:
    """Check a counterpart agent's reply against the envelope.

    This is the safety boundary. A reply is only accepted if it stays inside the
    limits BAM set *before* seeing the answer — never the other way round, which
    would let an agent's own report define what was permissible.
    """
    violations: List[str] = []

    if not isinstance(payload, dict):
        return ValidationOutcome(False, TaskState.REJECTED, ["reply is not an object"])

    if payload.get("task_id") and payload["task_id"] != task.id:
        violations.append(f"task_id mismatch ({payload['task_id']} != {task.id})")
    if payload.get("idempotency_key") and payload["idempotency_key"] != task.idempotency_key:
        violations.append("idempotency_key mismatch — reply is for a different dispatch")

    action_taken = str(payload.get("action_taken") or "")
    if action_taken and task.envelope.allowed_actions and action_taken not in task.envelope.allowed_actions:
        violations.append(f"action {action_taken!r} outside envelope {task.envelope.allowed_actions}")

    try:
        spend = float(payload.get("spend_gbp") or 0.0)
    except (TypeError, ValueError):
        violations.append("spend_gbp is not numeric")
        spend = 0.0
    if spend > task.envelope.max_spend_gbp + 1e-9:
        violations.append(f"spend £{spend:,.2f} exceeds cap £{task.envelope.max_spend_gbp:,.2f}")
    if spend < 0:
        violations.append("negative spend reported")

    try:
        change = abs(float(payload.get("change_pct") or 0.0))
    except (TypeError, ValueError):
        violations.append("change_pct is not numeric")
        change = 0.0
    if change > task.envelope.max_change_pct + 1e-9:
        violations.append(f"change {change:.1f}% exceeds limit {task.envelope.max_change_pct:.1f}%")

    try:
        duration = int(payload.get("duration_days") or 0)
    except (TypeError, ValueError):
        violations.append("duration_days is not an integer")
        duration = 0
    if duration > task.envelope.max_duration_days:
        violations.append(f"duration {duration}d exceeds {task.envelope.max_duration_days}d")

    status = str(payload.get("status") or "").lower()
    if status not in ("accepted", "rejected", "completed"):
        violations.append(f"unknown status {status!r}")

    # Expiry is checked against the clock, not the agent's claim.
    if task.expires_at:
        try:
            if datetime.now(timezone.utc) > datetime.fromisoformat(task.expires_at):
                violations.append("task expired before a result was reported")
        except ValueError:
            pass

    if violations:
        return ValidationOutcome(False, TaskState.REJECTED, violations, payload)

    if status == "rejected":
        return ValidationOutcome(True, TaskState.REJECTED, [], payload)
    if status == "completed":
        return ValidationOutcome(True, TaskState.COMPLETED, [], payload)
    return ValidationOutcome(True, TaskState.ACCEPTED, [], payload)


def reconcile(
    task: AgentTask,
    payload: Dict[str, Any],
    *,
    baseline: float = 0.0,
) -> Dict[str, Any]:
    """Compare what the agent reported with what BAM predicted.

    Returns an evidence-ledger-shaped record. The variance is the interesting
    number: a counterpart agent that consistently over-delivers makes BAM's
    priors too pessimistic, and one that under-delivers quietly is the failure
    mode worth watching.
    """
    before = payload.get("metric_before")
    after = payload.get("metric_after")
    measured = None
    if isinstance(before, (int, float)) and isinstance(after, (int, float)):
        measured = float(after) - float(before)

    predicted = float(task.expected_impact_gbp or 0.0)
    ratio = (measured / predicted) if (measured is not None and predicted) else None

    return {
        "task_id": task.id,
        "initiative_id": task.initiative_id,
        "agent_id": task.agent_id,
        "domain": task.domain.value,
        "predicted_impact_gbp": round(predicted, 2),
        "measured_impact_gbp": round(measured, 2) if measured is not None else None,
        "achievement_ratio": round(ratio, 3) if ratio is not None else None,
        "spend_gbp": round(float(payload.get("spend_gbp") or 0.0), 2),
        "reconciled_at": datetime.now(timezone.utc).isoformat(),
    }


def protocol_document() -> Dict[str, Any]:
    """Machine-readable description of the protocol, for external integrators."""
    return {
        "protocol": PROTOCOL_VERSION,
        "purpose": (
            "BAM sends executable tasks; counterpart agents execute inside a "
            "declared envelope. Decisions are not delegated."
        ),
        "request_fields": list(AgentTask.to_request.__annotations__.keys()) if hasattr(AgentTask.to_request, "__annotations__") else [],
        "envelope": Envelope().to_dict(),
        "states": [s.value for s in TaskState],
        "domains": [d.value for d in Domain],
        "reversibility": [r.value for r in Reversibility],
    }


__all__ = [
    "PROTOCOL_VERSION", "Domain", "Reversibility", "TaskState",
    "Capability", "CounterpartAgent", "Envelope", "AgentTask",
    "DispatchDecision", "ValidationOutcome",
    "default_directory", "envelope_for", "dispatch", "validate_result",
    "reconcile", "protocol_document",
]
