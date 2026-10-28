"""Build a BusinessGraph for SaaS tenants from a company.json spec.

The graph follows the Pirate Metrics (AARRR) framework and standard SaaS
financial benchmarks.  Level 0 is the P&L summary; level 1 breaks revenue and
cost down; level 2 holds the growth-driver metric nodes.
"""

import json
import os
import random
from datetime import date, timedelta

from .model.core import (
    AggregateNode, BaseNode, BusinessGraph, CostNode, MetricNode,
    NodeType, RevenueNode, TrendDirection,
)


def _sparkline(base: float, growth_pct: float, days: int = 30, seed: int = 0) -> list:
    """Return a plausible daily series ending near *base* with *growth_pct* total growth."""
    rng = random.Random(seed)
    start = base / (1 + growth_pct / 100.0) if growth_pct else base
    step = (base - start) / max(days - 1, 1)
    series = []
    for i in range(days):
        val = start + step * i
        noise = rng.gauss(0, abs(val) * 0.015) if val else 0
        series.append(round(max(val + noise, 0), 2))
    return series


def _node_stats(base: float, growth_pct: float, seed: int = 0) -> dict:
    """Return the change/trend fields expected by BaseNode."""
    series = _sparkline(base, growth_pct, seed=seed)
    last7 = sum(series[-7:]) / 7
    prior7 = sum(series[-14:-7]) / 7
    last30 = sum(series[-30:]) / 30
    prior30 = sum(series[:30]) / 30 if len(series) >= 30 else last30
    ch7 = last7 - prior7
    ch7p = (ch7 / prior7 * 100) if prior7 else 0
    ch30 = last30 - prior30
    ch30p = (ch30 / prior30 * 100) if prior30 else 0
    trend = TrendDirection.UP if ch7p > 0.5 else TrendDirection.DOWN if ch7p < -0.5 else TrendDirection.FLAT
    return dict(
        change_7d=round(ch7, 2), change_7d_pct=round(ch7p, 1),
        change_30d=round(ch30, 2), change_30d_pct=round(ch30p, 1),
        trend=trend, sparkline=series,
    )


def _mk(cls, node_id, label, value, unit, icon, color, desc, level,
        parents=None, children=None, growth=0.0, seed=0, **extra):
    """Factory that fills the shared stats fields."""
    stats = _node_stats(value, growth, seed=seed)
    node = cls(
        id=node_id, label=label, value=value, unit=unit, icon=icon, color=color,
        description=desc, level=level, parents=parents or [], children=children or [],
        **stats, **extra,
    )
    return node


def build_saas_graph(company_json_path: str) -> BusinessGraph:
    """Read a SaaS company.json and return a fully populated BusinessGraph."""
    with open(company_json_path) as f:
        spec = json.load(f)

    fin = spec["financials"]
    pm = spec["pirate_metrics"]
    tiers = spec["tiers"]

    g = BusinessGraph()

    # ── Derived financials ──
    mrr = fin["mrr"]
    cogs = round(mrr * (100 - fin["gross_margin_pct"]) / 100.0, 2)
    gross_profit = round(mrr - cogs, 2)
    # Operating expenses split by typical SaaS ratios (S&M 45%, R&D 30%, G&A 15% of revenue)
    sm = round(mrr * 0.45, 2)
    rd = round(mrr * 0.30, 2)
    ga = round(mrr * 0.15, 2)
    opex = round(sm + rd + ga, 2)
    op_profit = round(gross_profit - opex, 2)
    arr = fin["arr"]

    # ── Tier revenues ──
    tier_rev = {}
    for t in tiers:
        tier_rev[t["name"]] = round(t["price_monthly"] * t["customers"], 2)
    tier_customers = {t["name"]: t["customers"] for t in tiers}

    # ══════════════════════════════════════════════
    # LEVEL 0 — P&L summary
    # ══════════════════════════════════════════════
    rev = _mk(AggregateNode, "saas_revenue", "Revenue (MRR)", mrr, "GBP/mo",
              "💰", "#4caf50", "Monthly recurring revenue from all paid tiers",
              0, children=["tier_pro", "tier_enterprise", "saas_rev_other", "saas_cogs"],
              growth=8.5, seed=1)
    g.add(rev)

    cogs_node = _mk(CostNode, "saas_cogs", "Cost of Revenue", cogs, "GBP/mo",
                    "☁️", "#ef5350", "Hosting, infrastructure, and support delivery costs",
                    0, parents=["saas_revenue"], children=["cogs_hosting", "cogs_support"],
                    growth=6.2, seed=2, cost_type="variable", is_controllable=True)
    g.add(cogs_node)

    gp = _mk(AggregateNode, "saas_gross_profit", "Gross Profit", gross_profit, "GBP/mo",
             "📈", "#66bb6a", "Revenue minus cost of revenue",
             0, parents=["saas_revenue"], children=[],
             growth=9.1, seed=3)
    g.add(gp)

    opex_node = _mk(AggregateNode, "saas_opex", "Operating Expenses", opex, "GBP/mo",
                    "🧾", "#ffa726", "Sales & marketing, R&D, and general administration",
                    0, parents=["saas_gross_profit"], children=["opex_sm", "opex_rd", "opex_ga"],
                    growth=7.4, seed=4)
    g.add(opex_node)

    op = _mk(AggregateNode, "saas_op_profit", "Operating Profit", op_profit, "GBP/mo",
             "🏆", "#42a5f5", "Gross profit minus operating expenses",
             0, parents=["saas_gross_profit"], children=[],
             growth=12.3, seed=5)
    g.add(op)

    # ══════════════════════════════════════════════
    # LEVEL 1 — Revenue by tier
    # ══════════════════════════════════════════════
    for i, t in enumerate(tiers):
        name = t["name"]
        if name == "Free":
            continue  # free tier generates no direct revenue
        node_id = f"tier_{name.lower()}"
        node = _mk(RevenueNode, node_id, f"{name} Tier", tier_rev[name], "GBP/mo",
                   "💳", "#26a69a", f"{name} plan at £{t['price_monthly']}/mo × {t['customers']} customers",
                   1, parents=["saas_revenue"], growth=10.0 + i * 2.5, seed=10 + i,
                   volume=t["customers"], unit_type="customers", price=t["price_monthly"],
                   growth_rate=round(10.0 + i * 2.5, 1))
        g.add(node)

    # Other revenue (services/onboarding) to balance to MRR
    other_rev = round(mrr - sum(tier_rev.values()), 2)
    other = _mk(RevenueNode, "saas_rev_other", "Services & Other", other_rev, "GBP/mo",
                "🔧", "#26c6da", "Professional services and add-on revenue",
                1, parents=["saas_revenue"], growth=4.0, seed=15,
                volume=0, unit_type="services", price=0, growth_rate=4.0)
    g.add(other)

    # ══════════════════════════════════════════════
    # LEVEL 1 — Cost breakdown
    # ══════════════════════════════════════════════
    hosting = _mk(CostNode, "cogs_hosting", "Cloud Hosting", round(cogs * 0.65, 2), "GBP/mo",
                  "🖥️", "#e57373", "AWS/GCP compute and storage", 1,
                  parents=["saas_cogs"], growth=5.5, seed=20,
                  cost_type="variable", is_controllable=True)
    g.add(hosting)

    support = _mk(CostNode, "cogs_support", "Customer Support", round(cogs * 0.35, 2), "GBP/mo",
                  "🎧", "#ef9a9a", "Support team and tooling", 1,
                  parents=["saas_cogs"], growth=8.0, seed=21,
                  cost_type="variable", is_controllable=True)
    g.add(support)

    sm_node = _mk(CostNode, "opex_sm", "Sales & Marketing", sm, "GBP/mo",
                  "📣", "#ffb74d", "Paid acquisition, content, and sales team", 1,
                  parents=["saas_opex"], growth=9.2, seed=22,
                  cost_type="fixed", is_controllable=True)
    g.add(sm_node)

    rd_node = _mk(CostNode, "opex_rd", "R&D", rd, "GBP/mo",
                  "🛠️", "#ffcc80", "Engineering and product development", 1,
                  parents=["saas_opex"], growth=6.0, seed=23,
                  cost_type="fixed", is_controllable=True)
    g.add(rd_node)

    ga_node = _mk(CostNode, "opex_ga", "G&A", ga, "GBP/mo",
                  "🏢", "#ffe082", "Finance, legal, and administration", 1,
                  parents=["saas_opex"], growth=4.0, seed=24,
                  cost_type="fixed", is_controllable=True)
    g.add(ga_node)

    # ══════════════════════════════════════════════
    # LEVEL 2 — Pirate Metrics (AARRR)
    # ══════════════════════════════════════════════

    # ACQUISITION
    acq = _mk(MetricNode, "pm_acquisition", "Acquisition", pm["acquisition"]["signups_monthly"],
              "signups/mo", "🧲", "#5c6bc0",
              "New free-trial signups per month", 2,
              parents=["opex_sm"], growth=11.0, seed=30,
              formula="New signups per month", benchmark="3,000 signups/mo",
              benchmark_source="SaaS benchmark (SaaS Capital 2024)", direction="up")
    g.add(acq)

    visitors = _mk(MetricNode, "pm_visitors", "Website Visitors", pm["acquisition"]["visitors_monthly"],
                   "visits/mo", "👀", "#7986cb", "Monthly website traffic", 2,
                   parents=["pm_acquisition"], growth=9.0, seed=31,
                   formula="Monthly unique visitors", benchmark="45,000 visits/mo",
                   benchmark_source="Industry median", direction="up")
    g.add(visitors)

    cac = _mk(MetricNode, "pm_cac", "CAC", pm["acquisition"]["cac"], "GBP",
              "💸", "#9fa8da", "Customer acquisition cost (blended)", 2,
              parents=["opex_sm"], growth=-3.0, seed=32,
              formula="Total S&M spend / new customers", benchmark="£200",
              benchmark_source="SaaS Capital 2024", direction="down")
    g.add(cac)

    # ACTIVATION
    act = _mk(MetricNode, "pm_activation", "Activation Rate", pm["activation"]["activated_users_pct"],
              "%", "⚡", "#26a69a",
              "Percentage of signups who complete onboarding and create a first record", 2,
              parents=["saas_revenue"], growth=2.5, seed=33,
              formula="Activated users / signups", benchmark="40%",
              benchmark_source="OpenView SaaS Benchmarks 2024", direction="up")
    g.add(act)

    ttv = _mk(MetricNode, "pm_time_to_value", "Time to Value", pm["activation"]["time_to_value_days"],
              "days", "⏱️", "#4db6ac", "Median days from signup to first value moment", 2,
              parents=["pm_activation"], growth=-8.0, seed=34,
              formula="Median days to first record", benchmark="2.0 days",
              benchmark_source="Product-led growth benchmark", direction="down")
    g.add(ttv)

    # RETENTION
    churn = _mk(MetricNode, "pm_churn", "Monthly Churn", pm["retention"]["monthly_churn_pct"],
                "%", "📉", "#ef5350", "Monthly customer churn rate", 2,
                parents=["saas_revenue"], growth=-1.5, seed=35,
                formula="Churned customers / starting customers", benchmark="2.0%",
                benchmark_source="SaaS Capital 2024", direction="down")
    g.add(churn)

    nrr = _mk(MetricNode, "pm_nrr", "Net Revenue Retention", pm["retention"]["net_revenue_retention_pct"],
              "%", "🔁", "#66bb6a", "Revenue retained from existing customers including expansion", 2,
              parents=["saas_revenue"], growth=3.0, seed=36,
              formula="(Starting MRR + expansion - churn) / starting MRR", benchmark="105%",
              benchmark_source="SaaS Capital 2024", direction="up")
    g.add(nrr)

    dau_mau = _mk(MetricNode, "pm_dau_mau", "DAU/MAU", pm["retention"]["dau_mau_pct"],
                  "%", "📊", "#81c784", "Daily active users as a percentage of monthly active users", 2,
                  parents=["pm_retention"], growth=1.0, seed=37,
                  formula="DAU / MAU", benchmark="25%",
                  benchmark_source="SaaS engagement benchmark", direction="up")
    g.add(dau_mau)

    # REFERRAL
    viral = _mk(MetricNode, "pm_viral", "Viral Coefficient", pm["referral"]["viral_coefficient"],
                "ratio", "🦠", "#ab47bc", "Average invitations sent per user that convert", 2,
                parents=["saas_revenue"], growth=5.0, seed=38,
                formula="Invites sent × conversion rate", benchmark="0.30",
                benchmark_source="PLG benchmark", direction="up")
    g.add(viral)

    nps = _mk(MetricNode, "pm_nps", "NPS", pm["referral"]["nps"], "score",
              "❤️", "#ce93d8", "Net Promoter Score", 2,
              parents=["pm_referral"], growth=2.0, seed=39,
              formula="% promoters - % detractors", benchmark="40",
              benchmark_source="SaaS NPS benchmark", direction="up")
    g.add(nps)

    # REVENUE METRICS
    arpu = _mk(MetricNode, "pm_arpu", "ARPU", pm["revenue"]["arpu"], "GBP",
               "👤", "#42a5f5", "Average revenue per paying user", 2,
               parents=["saas_revenue"], growth=2.0, seed=40,
               formula="MRR / paying customers", benchmark="£50",
               benchmark_source="SaaS Capital 2024", direction="up")
    g.add(arpu)

    ltv = _mk(MetricNode, "pm_ltv", "LTV", fin["ltv"], "GBP",
              "💎", "#1e88e5", "Customer lifetime value", 2,
              parents=["saas_revenue"], growth=4.0, seed=41,
              formula="ARPU / monthly churn rate", benchmark="£2,000",
              benchmark_source="SaaS Capital 2024", direction="up")
    g.add(ltv)

    ltv_cac = _mk(MetricNode, "pm_ltv_cac", "LTV:CAC", pm["revenue"]["ltv_cac_ratio"],
                  "ratio", "⚖️", "#3949ab", "LTV to CAC ratio", 2,
                  parents=["saas_revenue"], growth=3.0, seed=42,
                  formula="LTV / CAC", benchmark="3.0x",
                  benchmark_source="SaaS Capital 2024", direction="up")
    g.add(ltv_cac)

    free_to_paid = _mk(MetricNode, "pm_free_to_paid", "Free→Paid Conversion",
                       pm["revenue"]["free_to_paid_pct"], "%", "🔄", "#5e35b1",
                       "Percentage of free users converting to paid", 2,
                       parents=["saas_revenue"], growth=4.5, seed=43,
                       formula="Paid conversions / free signups", benchmark="3.0%",
                       benchmark_source="PLG benchmark", direction="up")
    g.add(free_to_paid)

    # ══════════════════════════════════════════════
    # TOP-LEVEL KPI MetricNodes (for the KPI strip)
    # ══════════════════════════════════════════════
    kpis = [
        ("kpi_mrr", "MRR", mrr, "GBP/mo", "💰", "#4caf50", "Monthly Recurring Revenue", "£45,000", "SaaS Capital 2024", "up", 8.5, 50),
        ("kpi_arr", "ARR", arr, "GBP/yr", "📅", "#66bb6a", "Annual Recurring Revenue", "£540,000", "SaaS Capital 2024", "up", 8.5, 51),
        ("kpi_cac", "CAC", fin["cac"], "GBP", "💸", "#ef5350", "Customer Acquisition Cost", "£200", "SaaS Capital 2024", "down", -3.0, 52),
        ("kpi_ltv", "LTV", fin["ltv"], "GBP", "💎", "#42a5f5", "Customer Lifetime Value", "£2,000", "SaaS Capital 2024", "up", 4.0, 53),
        ("kpi_churn", "Monthly Churn", pm["retention"]["monthly_churn_pct"], "%", "📉", "#e57373", "Monthly customer churn", "2.0%", "SaaS Capital 2024", "down", -1.5, 54),
        ("kpi_nrr", "NRR", pm["retention"]["net_revenue_retention_pct"], "%", "🔁", "#81c784", "Net Revenue Retention", "105%", "SaaS Capital 2024", "up", 3.0, 55),
        ("kpi_ltv_cac", "LTV:CAC", pm["revenue"]["ltv_cac_ratio"], "ratio", "⚖️", "#7e57c2", "LTV to CAC ratio", "3.0x", "SaaS Capital 2024", "up", 3.0, 56),
        ("kpi_nps", "NPS", pm["referral"]["nps"], "score", "❤️", "#ec407a", "Net Promoter Score", "40", "SaaS NPS benchmark", "up", 2.0, 57),
    ]
    for kid, label, val, unit, icon, color, desc, bench, src, direction, growth, seed in kpis:
        node = _mk(MetricNode, kid, label, val, unit, icon, color, desc, 3,
                   growth=growth, seed=seed,
                   formula=desc, benchmark=bench, benchmark_source=src, direction=direction)
        g.add(node)

    # Register parent/child relationships that the factory couldn't express cleanly
    _link(g, "saas_gross_profit", "saas_opex")
    _link(g, "saas_op_profit", "saas_gross_profit", "saas_opex")
    _link(g, "pm_acquisition", "saas_revenue")
    _link(g, "pm_activation", "saas_revenue")
    _link(g, "pm_churn", "saas_revenue")
    _link(g, "pm_nrr", "saas_revenue")
    _link(g, "pm_viral", "saas_revenue")

    return g


def _link(g: BusinessGraph, parent_id: str, *child_ids: str):
    """Ensure parent lists the children and each child lists the parent."""
    parent = g.get(parent_id)
    if not parent:
        return
    for cid in child_ids:
        child = g.get(cid)
        if not child:
            continue
        if cid not in parent.children:
            parent.children.append(cid)
        if parent_id not in child.parents:
            child.parents.append(parent_id)
        # contribution
        if parent.value:
            parent.child_contribution_pct[cid] = round(abs(child.value) / abs(parent.value) * 100, 1)
