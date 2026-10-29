"""Plans, quotas and usage metering.

The marketing site sells three tiers; this module is the single source of truth
for what each tier actually allows. The pricing page renders from ``PLANS`` so
the copy can never drift from the enforcement.

Enforcement point: ``consume(tenant_id, metric)`` is called immediately before a
billable action (an arbiter run, an insight generation). It raises
``QuotaExceeded`` when the tenant is out of allowance for the current period.
Nothing else in the app may increment counters directly.

Design notes
------------
* Usage is metered per calendar month, UTC, keyed ``(tenant_id, metric, period)``.
  Period strings look like ``2026-10`` so a row is a plain text key and the
  table stays cheap to query without date maths.
* Plans live in SQLite next to the other per-instance state (``data/usage.db``),
  never in ``tenants.json`` — the registry file is read on every request and a
  concurrent write there would be a corruption risk.
* ``-1`` means unlimited. Absence of a limit key means the metric is not metered
  on that plan, which is treated as unlimited.
* Tenants that predate billing are seeded on ``pro`` so the owner's own
  businesses are never gated. New sign-ups land on ``free``.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Optional

DB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "usage.db"
)

_lock = threading.Lock()


# ── Plan definitions ─────────────────────────────────────────────────────────
# Order matters: index 0 is the default for new tenants.
PLANS: Dict[str, Dict[str, Any]] = {
    "free": {
        "name": "Free",
        "price_gbp": 0,
        "cadence": "forever",
        "tagline": "Model one business and see what the arbiter would do.",
        "limits": {
            "arbiter_runs": 2,          # strategy portfolios per month
            "insight_generations": 20,  # per-node LLM insight calls
            "businesses": 1,
            "integrations": 1,
            "history_days": 7,
            "specialists": 2,           # revenue + cost only
        },
        "features": [
            "1 business, modelled end to end",
            "2 arbiter runs per month",
            "2 specialist agents (revenue, cost)",
            "1 live integration",
            "7 days of metric history",
            "Constraint checking on every recommendation",
        ],
        "not_included": [
            "Autonomous dispatch",
            "Cross-type benchmarking",
            "Initiative outcome measurement",
        ],
    },
    "pro": {
        "name": "Pro",
        "price_gbp": 99,
        "cadence": "per month",
        "tagline": "Run the loop: arbitrate, dispatch, measure, learn.",
        "limits": {
            "arbiter_runs": 40,
            "insight_generations": 1000,
            "businesses": 5,
            "integrations": 10,
            "history_days": 365,
            "specialists": 5,
        },
        "features": [
            "5 businesses",
            "40 arbiter runs per month",
            "All five specialist agents",
            "10 live integrations",
            "12 months of history",
            "Autonomous controller with approval gate",
            "Initiative activation and outcome measurement",
            "Cross-type benchmarking once a peer group exists",
        ],
        "not_included": ["White-label branding", "SSO", "Custom graph templates"],
        "highlight": True,
    },
    "scale": {
        "name": "Scale",
        "price_gbp": 499,
        "cadence": "per month",
        "tagline": "White-label BAM across a portfolio or a franchise network.",
        "limits": {
            "arbiter_runs": -1,
            "insight_generations": -1,
            "businesses": -1,
            "integrations": -1,
            "history_days": -1,
            "specialists": 5,
        },
        "features": [
            "Unlimited businesses and arbiter runs",
            "White-label branding and custom domain",
            "SSO and role-based access",
            "Custom business-type graph templates",
            "Portfolio-level roll-up and benchmarking",
            "API access and webhooks",
            "Priority support and onboarding",
        ],
        "not_included": [],
    },
}

DEFAULT_PLAN = "free"

# Metrics whose units are user-visible. Anything not listed is metered silently.
METRIC_LABELS = {
    "arbiter_runs": "arbiter runs",
    "insight_generations": "insight generations",
}


class QuotaExceeded(Exception):
    """Raised when a tenant has no allowance left for an action this period."""

    def __init__(self, tenant_id: str, metric: str, used: int, limit: int, plan: str):
        self.tenant_id = tenant_id
        self.metric = metric
        self.used = used
        self.limit = limit
        self.plan = plan
        super().__init__(
            f"{plan} plan allows {limit} {METRIC_LABELS.get(metric, metric)} per month; "
            f"{used} already used"
        )


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _lock, _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tenant_plan (
                tenant_id   TEXT PRIMARY KEY,
                plan        TEXT NOT NULL,
                since       TEXT NOT NULL,
                stripe_customer_id TEXT
            );
            CREATE TABLE IF NOT EXISTS usage (
                tenant_id   TEXT NOT NULL,
                metric      TEXT NOT NULL,
                period      TEXT NOT NULL,
                count       INTEGER NOT NULL DEFAULT 0,
                updated_at  TEXT NOT NULL,
                PRIMARY KEY (tenant_id, metric, period)
            );
            """
        )


def period_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def get_plan(tenant_id: str, default: str = DEFAULT_PLAN) -> str:
    """Return the tenant's plan id, falling back to ``default``."""
    init_db()
    with _connect() as conn:
        row = conn.execute(
            "SELECT plan FROM tenant_plan WHERE tenant_id = ?", (tenant_id,)
        ).fetchone()
    if row and row["plan"] in PLANS:
        return row["plan"]
    return default


def set_plan(tenant_id: str, plan: str, stripe_customer_id: Optional[str] = None) -> None:
    """Assign a plan. Raises ``ValueError`` for an unknown plan id."""
    if plan not in PLANS:
        raise ValueError(f"unknown plan: {plan!r}")
    init_db()
    with _lock, _connect() as conn:
        conn.execute(
            """INSERT INTO tenant_plan (tenant_id, plan, since, stripe_customer_id)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(tenant_id) DO UPDATE SET
                 plan = excluded.plan,
                 since = excluded.since,
                 stripe_customer_id = COALESCE(
                   excluded.stripe_customer_id, tenant_plan.stripe_customer_id
                 )""",
            (tenant_id, plan, datetime.now(timezone.utc).isoformat(), stripe_customer_id),
        )


def limit_for(tenant_id: str, metric: str) -> int:
    """Return the monthly limit for a metric, or ``-1`` for unlimited."""
    plan = PLANS[get_plan(tenant_id)]
    return int(plan["limits"].get(metric, -1))


def used(tenant_id: str, metric: str, period: Optional[str] = None) -> int:
    init_db()
    p = period or period_now()
    with _connect() as conn:
        row = conn.execute(
            "SELECT count FROM usage WHERE tenant_id = ? AND metric = ? AND period = ?",
            (tenant_id, metric, p),
        ).fetchone()
    return int(row["count"]) if row else 0


def check(tenant_id: str, metric: str) -> None:
    """Raise ``QuotaExceeded`` if the tenant cannot afford one more call."""
    limit = limit_for(tenant_id, metric)
    if limit == -1:
        return
    current = used(tenant_id, metric)
    if current >= limit:
        raise QuotaExceeded(tenant_id, metric, current, limit, get_plan(tenant_id))


def consume(tenant_id: str, metric: str, amount: int = 1) -> Dict[str, Any]:
    """Check, then increment. Returns the post-increment status.

    Ordering matters: checking before incrementing means a rejected call leaves
    the counter untouched, so a client retrying after an upgrade is not charged
    for the attempts it could not make.
    """
    check(tenant_id, metric)
    init_db()
    p = period_now()
    with _lock, _connect() as conn:
        conn.execute(
            """INSERT INTO usage (tenant_id, metric, period, count, updated_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(tenant_id, metric, period) DO UPDATE SET
                 count = usage.count + excluded.count,
                 updated_at = excluded.updated_at""",
            (tenant_id, metric, p, amount, datetime.now(timezone.utc).isoformat()),
        )
    return {"metric": metric, "used": used(tenant_id, metric), "limit": limit_for(tenant_id, metric)}


def status(tenant_id: str) -> Dict[str, Any]:
    """Full plan + usage snapshot for the UI and the billing page."""
    plan_id = get_plan(tenant_id)
    plan = PLANS[plan_id]
    metrics = {}
    for metric, limit in plan["limits"].items():
        if metric in ("businesses", "integrations", "history_days", "specialists"):
            continue
        metrics[metric] = {
            "used": used(tenant_id, metric),
            "limit": limit,
            "label": METRIC_LABELS.get(metric, metric),
        }
    return {
        "tenant_id": tenant_id,
        "plan": plan_id,
        "plan_name": plan["name"],
        "price_gbp": plan["price_gbp"],
        "cadence": plan["cadence"],
        "limits": plan["limits"],
        "usage": metrics,
        "period": period_now(),
    }


def seed_default_plans(tenant_ids: Optional[list] = None, plan: str = "pro") -> None:
    """Give pre-existing tenants an ungated plan so the owner is never billed."""
    init_db()
    ids = tenant_ids or []
    for tid in ids:
        with _connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM tenant_plan WHERE tenant_id = ?", (tid,)
            ).fetchone()
        if not row:
            set_plan(tid, plan)
