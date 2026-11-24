"""Sign-up onboarding: from account to first useful answer.

The design constraint
---------------------
A new tenant has no integrations. The old flow created the account, dropped the
user on a dashboard built from a template they had never seen, and expected them
to connect Xero before anything made sense. Most people leave at that point.

This module inverts the order. The moment the account exists, the tenant already
has a populated graph cloned from its business-type template — real structure,
plausible numbers, working drill-downs. That is enough to *say something true
about the shape of the business* before a single OAuth token is fetched. The
integration step is then framed as an upgrade of an answer they already have,
not a precondition for getting one.

State is derived from the tenant's actual state (does a graph exist, how many
connections, have we produced insights) rather than stored as a session flag, so
progress survives logout, a new device, or a half-finished signup.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import types as type_registry


STEPS: List[Dict[str, str]] = [
    {"id": "account", "label": "Account", "title": "Create your account"},
    {"id": "business", "label": "Business", "title": "Describe the business"},
    {"id": "interview", "label": "Interview", "title": "Tell us how it works"},
    {"id": "plan", "label": "Your team", "title": "See the agents we'd run"},
    {"id": "connect", "label": "Connect", "title": "Connect your numbers"},
    {"id": "value", "label": "First look", "title": "Your first reading"},
]

STEP_IDS = [s["id"] for s in STEPS]

#: Provider categories worth leading with, per top-level type family.
#: Ordering matters — the first two are shown large, the rest behind "more".
_PRIORITY = {
    "retail": ["accounting", "pos", "payments", "analytics"],
    "saas": ["payments", "analytics", "crm", "accounting"],
    "service": ["accounting", "payments", "crm", "analytics"],
    "business": ["accounting", "payments", "analytics", "crm"],
}

#: Why a given category is worth connecting, in the tenant's own terms.
_CATEGORY_VALUE = {
    "accounting": "Pulls revenue, COGS and overheads so the P&L stops being an estimate.",
    "payments": "Adds transaction volume — the difference between a trend and a number.",
    "pos": "Gives basket-level detail: units, average spend, category mix.",
    "analytics": "Fills in traffic and conversion so demand-side drivers are measured, not assumed.",
    "crm": "Links pipeline to revenue so acquisition cost becomes real.",
    "marketing": "Attribution — which spend actually moved the metric.",
}


@dataclass
class StepState:
    id: str
    label: str
    title: str
    status: str            # "done" | "current" | "upcoming"
    detail: str = ""

    def to_dict(self) -> dict:
        return {"id": self.id, "label": self.label, "title": self.title,
                "status": self.status, "detail": self.detail}


# ---------------------------------------------------------------------------
# Provider recommendation
# ---------------------------------------------------------------------------


def _family_for(type_id: str) -> str:
    """Top-level family for a type id, e.g. ``retail.coffee_shop`` -> ``retail``."""
    try:
        lineage = type_registry.lineage(type_id)
    except Exception:
        lineage = [type_id]
    for candidate in lineage:
        if candidate in _PRIORITY:
            return candidate
    return "business"


def recommended_providers(type_id: str, limit: int = 8) -> List[Dict[str, Any]]:
    """Providers worth offering this business, ordered by relevance.

    Declarative rather than clever: the type family decides category order, the
    provider registry decides what exists. A type whose canonical fields are
    unknown still gets a sensible default set.
    """
    from .integrations import providers as registry

    try:
        resolved = type_registry.resolve(type_id)
        wanted_fields = set(getattr(resolved, "canonical_fields", set()) or set())
    except Exception:
        wanted_fields = set()

    family = _family_for(type_id)
    order = _PRIORITY.get(family, _PRIORITY["business"])

    specs = registry.all_specs()
    scored = []
    for spec in specs:
        cat_rank = order.index(spec.category) if spec.category in order else len(order) + 1
        overlap = len(set(spec.fields) & wanted_fields)
        scored.append((cat_rank, -overlap, spec.id, spec))
    scored.sort()

    out: List[Dict[str, Any]] = []
    for cat_rank, neg_overlap, _sid, spec in scored:
        out.append({
            "id": spec.id,
            "label": spec.label,
            "category": spec.category,
            "fields": list(spec.fields),
            "auth": spec.auth,
            "why": _CATEGORY_VALUE.get(spec.category, ""),
            "primary": cat_rank <= 1,
            "overlap": -neg_overlap,
        })
        if len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------------------
# Tenant state
# ---------------------------------------------------------------------------


def _connection_count(tenant_id: str) -> int:
    try:
        from .integrations import store as integ_store
        rows = integ_store.list_connections(tenant_id)
        return len(rows or [])
    except Exception:
        # Discovery-only: an unreadable integration store must not block
        # onboarding. The step simply reads as "not yet connected".
        return 0


def _has_graph(tenant_id: str) -> bool:
    try:
        from .loader import load_graph
        g = load_graph(tenant_id)
        return bool(getattr(g, "nodes", None))
    except Exception:
        return False


def _tenant_meta(tenant_id: str) -> Dict[str, Any]:
    try:
        from . import provisioning
        tenants = provisioning._read_tenants()
        return tenants.get(tenant_id, {}) or {}
    except Exception:
        return {}


def state(tenant_id: str) -> Dict[str, Any]:
    """Derive onboarding progress from what is actually true for this tenant."""
    meta = _tenant_meta(tenant_id)
    has_graph = _has_graph(tenant_id)
    connections = _connection_count(tenant_id)

    statuses: Dict[str, str] = {}
    details: Dict[str, str] = {}

    statuses["account"] = "done"
    details["account"] = "Signed in."

    if has_graph and _type_of(meta):
        statuses["business"] = "done"
        details["business"] = (
            f"{meta.get('name', 'Your business')} · "
            f"{_type_label(_type_of(meta))}"
        )
    else:
        statuses["business"] = "upcoming" if not has_graph else "current"
        details["business"] = "Pick the template that best matches your business."

    # Interview: the owner's own account of how the business works. Nothing is
    # connected yet — this is the step that earns the right to ask for data.
    from . import interview as interview_mod
    session = interview_mod.load(tenant_id)
    answered = len(session.get("answers") or {})
    if interview_mod.is_complete(tenant_id):
        statuses["interview"] = "done"
        details["interview"] = (
            "You described how the business works."
            if answered >= len(interview_mod.QUESTIONS)
            else f"You described how the business works — {answered} of "
                 f"{len(interview_mod.QUESTIONS)} answered, the rest can sharpen the plan."
        )
    else:
        statuses["interview"] = "upcoming"
        details["interview"] = (
            f"{answered} of {len(interview_mod.QUESTIONS)} questions answered."
            if answered else
            "A few questions about how the business works — no data needed."
        )

    agent_plan = interview_mod.plan(tenant_id)
    if agent_plan and agent_plan.get("acknowledged_at"):
        statuses["plan"] = "done"
        details["plan"] = f"{len(agent_plan.get('agents') or [])} agents proposed and reviewed."
    else:
        statuses["plan"] = "upcoming"
        details["plan"] = "See the agent team we'd run for you, and how they'd work together."

    value_seen = bool(meta.get("value_seen_at"))
    if connections:
        statuses["connect"] = "done"
        details["connect"] = f"{connections} source{'s' if connections != 1 else ''} connected."
    elif value_seen:
        # Reaching the reading means this step was passed. Say so plainly rather
        # than leaving the funnel parked on a step the owner already walked past.
        statuses["connect"] = "done"
        details["connect"] = "Skipped — nothing connected yet."
    elif interview_mod.is_plan_acknowledged(tenant_id):
        statuses["connect"] = "upcoming"
        details["connect"] = (
            "Now connect the sources your agents need — you've seen what they'll do with them."
        )
    else:
        # Connection is deliberately *not* offered until the plan is reviewed.
        statuses["connect"] = "upcoming"
        details["connect"] = "Connect accounting or payments — once you've seen the plan."

    if value_seen:
        statuses["value"] = "done"
        details["value"] = "Your first reading was delivered."
    else:
        statuses["value"] = "upcoming"
        details["value"] = "Three readings from your graph."

    # First non-done step becomes current, everything after it stays upcoming.
    current_set = False
    steps: List[StepState] = []
    for spec in STEPS:
        sid = spec["id"]
        st = statuses.get(sid, "upcoming")
        if st != "done":
            if not current_set:
                st = "current"
                current_set = True
            else:
                st = "upcoming"
        steps.append(StepState(sid, spec["label"], spec["title"], st, details.get(sid, "")))

    done = sum(1 for s in steps if s.status == "done")
    return {
        "tenant_id": tenant_id,
        "steps": [s.to_dict() for s in steps],
        "current": next((s.id for s in steps if s.status == "current"), "done"),
        "completed": done,
        "total": len(steps),
        "percent": round(done / len(steps) * 100),
        "has_graph": has_graph,
        "connections": connections,
        "business_type": _type_of(meta),
        "business_name": meta.get("name", ""),
    }


def _type_of(meta: Dict[str, Any]) -> str:
    """Best available type id for a tenant entry.

    ``type_template`` is the hierarchical id (retail.coffee_shop);
    ``business_type`` was the older flat field. Accept either.
    """
    for key in ("type_template", "business_type", "type"):
        val = (meta or {}).get(key)
        if val:
            return str(val).strip()
    return ""


def _type_label(type_id: str) -> str:
    try:
        return type_registry.get(type_id).label
    except Exception:
        return (type_id or "business").replace("_", " ").title()


# ---------------------------------------------------------------------------
# First value
# ---------------------------------------------------------------------------


def _num(node: Any, default: float = 0.0) -> float:
    try:
        return float(getattr(node, "value", default) or 0.0)
    except (TypeError, ValueError):
        return default


def mark_value_seen(tenant_id: str) -> None:
    """Record that the owner has been shown their first reading.

    Written once: the funnel's terminal step is "delivered", and rewriting the
    timestamp on every reload would make the stored state churn for no gain.
    """
    if _tenant_meta(tenant_id).get("value_seen_at"):
        return
    from . import provisioning
    provisioning.update_tenant_meta(
        tenant_id,
        {"value_seen_at": datetime.now(timezone.utc).isoformat()},
    )


def first_value(tenant_id: str) -> Dict[str, Any]:
    """Three readings a new tenant can act on before connecting anything.

    These are deliberately structural rather than predictive: "staff is 53% of
    revenue" is true of the template's shape and stays true once real numbers
    arrive, whereas "you will save £4,200" would be a fabrication. Framing each
    one as a question turns the template into a prompt for the real data.
    """
    from .loader import load_graph

    graph = load_graph(tenant_id)
    nodes = getattr(graph, "nodes", {}) or {}

    def val(*ids: str) -> Optional[float]:
        for nid in ids:
            node = nodes.get(nid)
            if node is not None:
                return _num(node)
        return None

    revenue = val("pnl_revenue", "rev_total", "saas_revenue")
    cogs = val("pnl_cogs", "cogs_total")
    staff = val("pnl_staff", "pnl_labour")
    overheads = val("pnl_overheads")
    gross = val("pnl_gross_profit")
    op = val("pnl_operating_profit", "saas_op_profit")

    findings: List[Dict[str, Any]] = []

    if revenue and cogs is not None and revenue > 0:
        gm = (revenue - cogs) / revenue
        findings.append({
            "title": "Gross margin",
            "value": f"{gm * 100:.0f}%",
            "reading": (
                f"Every £1 of revenue leaves {gm * 100:.0f}p after direct cost. "
                f"That is the ceiling on everything else."
            ),
            "question": "Is that typical for your type — and does it match your last quarter?",
            "template_gap": "Connect accounting to replace this estimate.",
        })

    if revenue and staff:
        share = staff / revenue
        findings.append({
            "title": "Staff as a share of revenue",
            "value": f"{share * 100:.0f}%",
            "reading": (
                f"Labour is £{staff:,.0f} a month against £{revenue:,.0f} of revenue. "
                f"At this ratio a 10% revenue drop removes "
                f"{'most' if share > 0.5 else 'a large part'} of the profit buffer."
            ),
            "question": "Is rostering matched to the hours that actually earn?",
            "template_gap": "Connect payroll or your rota tool to make this exact.",
        })

    if revenue and op is not None and revenue > 0:
        margin = op / revenue
        findings.append({
            "title": "Operating margin",
            "value": f"{margin * 100:.1f}%",
            "reading": (
                f"£{op:,.0f} a month on £{revenue:,.0f}. "
                + ("There is little room for a bad month." if margin < 0.08
                   else "There is room to absorb a bad month.")
            ),
            "question": "Which line would you cut first if revenue fell 15%?",
            "template_gap": "Connect accounting for the real figure.",
        })

    if not findings:
        findings.append({
            "title": "Your graph is ready",
            "value": "—",
            "reading": "The template built a full P&L structure with drill-downs on every node.",
            "question": "Connect a source to replace the starting estimates.",
            "template_gap": "Start with accounting.",
        })

    return {
        "tenant_id": tenant_id,
        "findings": findings[:3],
        "disclaimer": (
            "These are structural readings from your business-type template, not "
            "your actual accounts. Each one sharpens as you connect a source."
        ),
        "recommended": recommended_providers(
            _type_of(_tenant_meta(tenant_id)) or "business", limit=3
        ),
    }


# ---------------------------------------------------------------------------
# Nango connect
# ---------------------------------------------------------------------------


def connect_link(tenant_id: str, provider_id: str, email: str = "") -> Dict[str, Any]:
    """Return a hosted Nango auth link, or an explicit 'not configured' answer.

    Never pretends: if Nango has no secret key the caller gets ``configured:
    False`` with the reason, and the UI shows the connection as available-but-
    unconfigured rather than broken.
    """
    from .integrations import nango

    if not nango.available():
        return {
            "configured": False,
            "reason": "Nango is not configured on this deployment (NANGO_SECRET_KEY unset).",
            "connect_link": None,
        }
    try:
        client = nango.client_from_env()
        session = client.create_connect_session(
            integration_id=provider_id,
            end_user_id=tenant_id,
            end_user_email=email or None,
        )
        link = (session or {}).get("connect_link")
        return {"configured": True, "connect_link": link, "raw": session}
    except Exception as exc:  # network, auth, or malformed response
        return {"configured": True, "connect_link": None,
                "reason": f"Nango rejected the session request: {exc}"}


def next_step_url(tenant_id: str) -> str:
    """Where a tenant should land right now."""
    st = state(tenant_id)
    cur = st["current"]
    if cur in (None, "done"):
        return "/dashboard"
    if cur == "value":
        return "/onboarding/value"
    return f"/onboarding/{cur}"


__all__ = [
    "STEPS",
    "STEP_IDS",
    "StepState",
    "state",
    "first_value",
    "mark_value_seen",
    "recommended_providers",
    "connect_link",
    "next_step_url",
]
