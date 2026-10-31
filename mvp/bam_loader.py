"""BAM's own business graph — the company running on itself.

Why a bespoke loader
--------------------
BAM is a subscription business with a cost structure that does not look like
generic SaaS. The dominant variable cost is *inference*: every arbiter run costs
money, and the free tier lets people run without paying. That coupling —
usage drives cost, cost drives gross margin, and the free tier is a deliberate
loss leader — is the thing the graph has to show. A generic SaaS template would
hide it behind a single "COGS" line.

So this loader models the specific machine: priced tiers, a free tier that
consumes inference, per-run unit economics, and the conversion funnel that has
to pay for it.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List

from .model.core import BusinessGraph, BaseNode, NodeType, TrendDirection


def _spark(base: float, shape: str = "flat") -> List[float]:
    """A 30-point daily series with the right order of magnitude and drift."""
    if base <= 0:
        return []
    if shape == "up":
        return [round(base * (0.7 + 0.6 * i / 29), 2) for i in range(30)]
    if shape == "down":
        return [round(base * (1.3 - 0.6 * i / 29), 2) for i in range(30)]
    return [round(base * (0.95 + 0.1 * ((i * 7) % 5) / 4), 2) for i in range(30)]


def _node(nid: str, label: str, ntype: NodeType, value: float, *,
          unit: str = "GBP", level: int = 1, spark: str = "flat",
          efficiency: float = None, efficiency_label: str = None,
          description: str = "", tags: List[str] = None, icon: str = "",
          trend: TrendDirection = TrendDirection.UNKNOWN) -> BaseNode:
    daily = value / 30.0
    return BaseNode(
        id=nid, label=label, node_type=ntype, value=round(value, 2),
        unit=unit, level=level, trend=trend,
        sparkline=_spark(daily, spark),
        efficiency=efficiency, efficiency_label=efficiency_label,
        description=description, tags=tags or [], icon=icon,
    )


def _link(g: BusinessGraph, parent: str, *children: str) -> None:
    p = g.nodes.get(parent)
    if p is None:
        return
    for cid in children:
        c = g.nodes.get(cid)
        if c is None:
            continue
        if cid not in p.children:
            p.children.append(cid)
        if parent not in c.parents:
            c.parents.append(parent)
        g._adjacency.setdefault(parent, []).append(cid) if False else None
        g.edges.append({"source": parent, "target": cid, "kind": "composes"})
    g._adjacency[parent] = p.children[:]


def build_bam_graph(data_dir: str = "") -> BusinessGraph:
    """Build the graph from ``company.json`` in ``data_dir``."""
    path = os.path.join(data_dir, "company.json") if data_dir else ""
    if path and os.path.isfile(path):
        with open(path) as fh:
            spec: Dict[str, Any] = json.load(fh)
    else:
        spec = _defaults()

    tiers = spec.get("tiers", [])
    fin = spec.get("financials", {})
    funnel = spec.get("funnel", {})
    cost = spec.get("costs", {})

    pro = next((t for t in tiers if t.get("id") == "pro"), {"price_monthly": 99, "customers": 0})
    scale = next((t for t in tiers if t.get("id") == "scale"), {"price_monthly": 499, "customers": 0})
    free = next((t for t in tiers if t.get("id") == "free"), {"price_monthly": 0, "customers": 0})

    pro_mrr = float(pro["price_monthly"]) * float(pro["customers"])
    scale_mrr = float(scale["price_monthly"]) * float(scale["customers"])
    mrr = pro_mrr + scale_mrr

    runs = float(fin.get("arbiter_runs_per_month", 0)) or 1.0
    cost_per_run = float(cost.get("inference_per_run_gbp", 0.0))
    inference = runs * cost_per_run
    infra = float(cost.get("infra_monthly_gbp", 0.0))
    fees = mrr * float(cost.get("payment_fee_pct", 0.0)) / 100.0
    cogs = inference + infra + fees

    staff_salary = float(cost.get("staff_monthly_gbp", 0.0))
    overheads = float(cost.get("overheads_monthly_gbp", 0.0))
    gross = mrr - cogs
    op = gross - staff_salary - overheads

    g = BusinessGraph()

    g.add(_node("bam_mrr", "Monthly recurring revenue", NodeType.AGGREGATE, mrr,
                level=0, spark="up", icon="💷",
                description="Paid subscription revenue across all tiers.",
                tags=["revenue", "core"]))
    g.add(_node("bam_pro_mrr", "Pro tier MRR", NodeType.REVENUE, pro_mrr,
                level=1, spark="up", icon="⭐",
                description="£99/mo tier — the volume product.",
                tags=["revenue", "tier"]))
    g.add(_node("bam_scale_mrr", "Scale tier MRR", NodeType.REVENUE, scale_mrr,
                level=1, spark="flat", icon="🏢",
                description="£499/mo tier — multi-business, white-label.",
                tags=["revenue", "tier"]))
    g.add(_node("bam_free_users", "Free tier accounts", NodeType.METRIC, float(free.get("customers", 0)),
                unit="accounts", level=1, spark="up", icon="🆓",
                description="Non-paying accounts. They consume inference and are the top of the funnel.",
                tags=["growth", "funnel"]))

    g.add(_node("bam_cogs", "Cost of revenue", NodeType.AGGREGATE, cogs,
                level=0, spark="up", icon="⚙️",
                description="Inference, infrastructure and payment processing.",
                tags=["cost", "core"]))
    g.add(_node("bam_inference_cost", "Inference cost", NodeType.COST, inference,
                level=1, spark="up", icon="🧠",
                description="Model calls. Scales with arbiter runs, including free-tier runs.",
                tags=["cost", "variable", "usage"]))
    g.add(_node("bam_infra_cost", "Infrastructure", NodeType.COST, infra,
                level=1, spark="flat", icon="🖥️",
                description="Hosting, database, monitoring.",
                tags=["cost", "fixed"]))
    g.add(_node("bam_payment_fees", "Payment fees", NodeType.COST, fees,
                level=1, spark="flat", icon="💳",
                description="Processor fees on collected revenue.",
                tags=["cost", "variable"]))

    g.add(_node("bam_gross_profit", "Gross profit", NodeType.METRIC, gross,
                level=0, spark="up", icon="📈",
                efficiency=(gross / mrr if mrr else 0.0),
                efficiency_label=f"{(gross / mrr * 100):.0f}% margin" if mrr else "",
                description="Revenue less cost of revenue.",
                tags=["profit"]))

    g.add(_node("bam_staff", "Staff costs", NodeType.AGGREGATE, staff_salary,
                level=0, spark="flat", icon="👥",
                description="Salaries and contractor costs.",
                tags=["cost", "people"]))
    g.add(_node("bam_overheads", "Overheads", NodeType.AGGREGATE, overheads,
                level=0, spark="flat", icon="🏠",
                description="Tools, legal, accounting, insurance.",
                tags=["cost", "fixed"]))

    g.add(_node("bam_op_profit", "Operating profit", NodeType.METRIC, op,
                level=0, spark="up", icon="🎯",
                efficiency=(op / mrr if mrr else 0.0),
                efficiency_label=f"{(op / mrr * 100):.1f}% margin" if mrr else "",
                description="What the machine actually earns.",
                tags=["profit", "outcome"]))

    # ── Growth machine ────────────────────────────────────────────────────
    signups = float(funnel.get("signups_per_month", 0))
    activation = float(funnel.get("activation_rate_pct", 0)) / 100.0
    conv = float(funnel.get("free_to_paid_pct", 0)) / 100.0
    churn = float(funnel.get("monthly_churn_pct", 0)) / 100.0
    cac = float(funnel.get("cac_gbp", 0))
    arpu = (mrr / max(float(pro["customers"]) + float(scale["customers"]), 1)) if mrr else 0.0
    ltv = (arpu / churn) if churn else 0.0

    g.add(_node("bam_signups", "Sign-ups", NodeType.PROCESS, signups,
                unit="accounts/mo", level=2, spark="up", icon="✍️",
                description="Free accounts created per month.",
                tags=["growth", "funnel"]))
    g.add(_node("bam_activations", "Activated accounts", NodeType.PROCESS, signups * activation,
                unit="accounts/mo", level=2, spark="up", icon="⚡",
                description="Accounts that reached a first reading — the onboarding target.",
                tags=["growth", "funnel"]))
    g.add(_node("bam_paid_conversions", "Free → paid", NodeType.PROCESS, signups * conv,
                unit="accounts/mo", level=2, spark="flat", icon="🔁",
                description="Accounts converting to a paid tier each month.",
                tags=["growth", "funnel"]))
    g.add(_node("bam_churn", "Monthly churn", NodeType.METRIC, churn * 100,
                unit="%", level=2, spark="down", icon="📉",
                description="Share of paying accounts lost each month.",
                tags=["retention"]))
    g.add(_node("bam_cac", "Customer acquisition cost", NodeType.METRIC, cac,
                level=2, spark="flat", icon="🎣",
                description="Sales and marketing spend per paid account won.",
                tags=["growth"]))
    g.add(_node("bam_ltv", "Lifetime value", NodeType.METRIC, ltv,
                level=2, spark="up", icon="💎",
                description="ARPU divided by monthly churn.",
                tags=["growth"]))
    g.add(_node("bam_arbiter_runs", "Arbiter runs", NodeType.PROCESS, runs,
                unit="runs/mo", level=2, spark="up", icon="🔮",
                description="Optimisation cycles executed. The usage driver behind inference cost.",
                tags=["usage", "cost-driver"]))

    # ── Structure ─────────────────────────────────────────────────────────
    _link(g, "bam_mrr", "bam_pro_mrr", "bam_scale_mrr", "bam_free_users")
    _link(g, "bam_cogs", "bam_inference_cost", "bam_infra_cost", "bam_payment_fees")
    _link(g, "bam_gross_profit", "bam_mrr", "bam_cogs")
    _link(g, "bam_staff", )
    _link(g, "bam_op_profit", "bam_gross_profit", "bam_staff", "bam_overheads")
    _link(g, "bam_signups", "bam_activations")
    _link(g, "bam_activations", "bam_paid_conversions")
    # The coupling that defines the business: usage drives inference cost.
    _link(g, "bam_arbiter_runs", "bam_inference_cost")

    if not g.root_nodes:
        g.root_nodes = ["bam_mrr", "bam_cogs", "bam_gross_profit",
                        "bam_staff", "bam_overheads", "bam_op_profit"]
    return g


def _defaults() -> Dict[str, Any]:
    """Default assumptions, used when no company.json is present."""
    return {
        "tiers": [
            {"id": "free", "price_monthly": 0, "customers": 380},
            {"id": "pro", "price_monthly": 99, "customers": 40},
            {"id": "scale", "price_monthly": 499, "customers": 4},
        ],
        "financials": {"arbiter_runs_per_month": 900},
        "costs": {
            "inference_per_run_gbp": 1.20,
            "infra_monthly_gbp": 120.0,
            "payment_fee_pct": 1.5,
            "staff_monthly_gbp": 3500.0,
            "overheads_monthly_gbp": 450.0,
        },
        "funnel": {
            "signups_per_month": 180,
            "activation_rate_pct": 55,
            "free_to_paid_pct": 6,
            "monthly_churn_pct": 3.5,
            "cac_gbp": 210,
        },
    }


__all__ = ["build_bam_graph"]
