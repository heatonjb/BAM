"""Build the hierarchical business graph from JonCo data.

Every node carries:
  - current value (monthly average, last 30 days)
  - change_7d / change_7d_pct (last 7 days vs prior 7)
  - change_30d / change_30d_pct (last 30 days vs prior 30)
  - trend: "up" | "down" | "flat"
  - sparkline: last 30 daily values
"""

import json
import os
import pickle
from collections import defaultdict

from .model.core import (
    BaseNode, NodeType, TrendDirection,
    RevenueNode, CostNode, ProcessNode, InputNode,
    AssetNode, LiabilityNode, MetricNode, AggregateNode,
    BusinessGraph
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jonco")
DATA_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TENANTS_PATH = os.path.join(DATA_ROOT, "tenants.json")
STATS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rolling_stats.pkl")


def _trend(val):
    if val == "up": return TrendDirection.UP
    if val == "down": return TrendDirection.DOWN
    return TrendDirection.FLAT


def _apply_stats(node, stats_dict):
    """Attach rolling stats to a node."""
    if not stats_dict:
        return
    node.change_7d = stats_dict.get("change_7d", 0)
    node.change_7d_pct = stats_dict.get("change_7d_pct", 0)
    node.change_30d = stats_dict.get("change_30d", 0)
    node.change_30d_pct = stats_dict.get("change_30d_pct", 0)
    node.trend = _trend(stats_dict.get("trend_7d", "flat"))
    node.sparkline = stats_dict.get("sparkline", [])


def _load_cafe_graph(data_dir: str = None, stats_path: str = None) -> BusinessGraph:
    """Build the full hierarchical graph from one café tenant's data files.

    ``data_dir`` must name the tenant's own directory. It used to be a module
    constant pointing at ``data/jonco``, so every café-type tenant rendered
    JonCo's books — the same class of bug as the unscoped ``load_all()``. Callers
    must pass the tenant's directory; the default is retained only so scripts
    that read the original café keep working.
    """
    data_dir = data_dir or DATA_DIR
    stats_path = stats_path or STATS_PATH
    g = BusinessGraph()

    # ── Load raw data ──
    with open(os.path.join(data_dir, "transactions.json")) as f:
        transactions = json.load(f)
    with open(os.path.join(data_dir, "staff_roster.json")) as f:
        staff_roster = json.load(f)
    with open(os.path.join(data_dir, "payroll.json")) as f:
        payroll = json.load(f)
    with open(os.path.join(data_dir, "cogs_purchases.json")) as f:
        cogs_data = json.load(f)
    with open(os.path.join(data_dir, "overheads.json")) as f:
        overheads_data = json.load(f)
    with open(os.path.join(data_dir, "menu.json")) as f:
        menu = json.load(f)
    with open(os.path.join(data_dir, "bottom_up_pl.json")) as f:
        pl_data = json.load(f)

    # ── Load rolling stats ──
    # A cloned tenant carries its own rolling_stats.pkl when one exists;
    # otherwise fall back to the shared file rather than failing the load.
    if not os.path.exists(stats_path):
        stats_path = STATS_PATH
    with open(stats_path, "rb") as f:
        S = pickle.load(f)

    # ── Compute monthly averages ──
    monthly_rev = sum(p["revenue"]["total"] for p in pl_data["monthly"].values()) / 3
    monthly_cogs = sum(p["cost_of_goods_sold"]["total"] for p in pl_data["monthly"].values()) / 3
    monthly_staff = sum(p["staff_costs"]["total_employer_cost"] for p in pl_data["monthly"].values()) / 3
    monthly_oh = sum(p["overheads"]["total"] for p in pl_data["monthly"].values()) / 3
    monthly_gp = monthly_rev - monthly_cogs
    monthly_op = monthly_rev - monthly_cogs - monthly_staff - monthly_oh

    # Category revenues (monthly avg)
    cat_rev = defaultdict(float)
    cat_units = defaultdict(int)
    for t in transactions:
        for item in t["items"]:
            cat_rev[item["category"]] += item["price"]
            cat_units[item["category"]] += 1

    # Product stats (monthly avg)
    product_stats_agg = defaultdict(lambda: {"count": 0, "revenue": 0, "category": ""})
    for t in transactions:
        for item in t["items"]:
            product_stats_agg[item["item"]]["count"] += 1
            product_stats_agg[item["item"]]["revenue"] += item["price"]
            product_stats_agg[item["item"]]["category"] = item["category"]

    # ──────────────────────────────────────────────
    # LEVEL 0: P&L Summary
    # ──────────────────────────────────────────────

    rev_stats = S["revenue"]
    g.add(AggregateNode(
        id="pnl_revenue", label="Revenue", level=0,
        value=monthly_rev, unit="GBP/mo",
        description="Total revenue from all sales",
        icon="💰", color="#4caf50",
        change_7d=rev_stats["change_7d"], change_7d_pct=rev_stats["change_7d_pct"],
        change_30d=rev_stats["change_30d"], change_30d_pct=rev_stats["change_30d_pct"],
        trend=_trend(rev_stats["trend_7d"]),
        sparkline=rev_stats["sparkline"]
    ))

    # COGS aggregate - compute rolling from daily_cogs
    total_cogs_daily = [sum(S["daily_cogs"].get(d, {}).get(c, 0) for c in S["daily_cogs"].get(d, {})) for d in S["all_dates"]]
    cogs_series = {d: v for d, v in zip(S["all_dates"], total_cogs_daily)}
    cur7 = sum(total_cogs_daily[-7:]) / 7
    pri7 = sum(total_cogs_daily[-14:-7]) / 7
    cur30 = sum(total_cogs_daily[-30:]) / 30
    pri30 = sum(total_cogs_daily[-60:-30]) / 30
    cogs_7d = cur7 - pri7
    cogs_7d_pct = (cogs_7d / pri7 * 100) if pri7 else 0
    cogs_30d = cur30 - pri30
    cogs_30d_pct = (cogs_30d / pri30 * 100) if pri30 else 0

    g.add(AggregateNode(
        id="pnl_cogs", label="Cost of Goods Sold", level=0,
        value=monthly_cogs, unit="GBP/mo",
        description="Direct cost of ingredients and packaging",
        icon="📦", color="#ff5722",
        change_7d=cogs_7d, change_7d_pct=cogs_7d_pct,
        change_30d=cogs_30d, change_30d_pct=cogs_30d_pct,
        trend=_trend("up" if cogs_7d_pct > 3 else "down" if cogs_7d_pct < -3 else "flat"),
        sparkline=total_cogs_daily[-30:]
    ))

    # Gross Profit
    gp_7d = rev_stats["change_7d"] - cogs_7d
    gp_30d = rev_stats["change_30d"] - cogs_30d
    g.add(MetricNode(
        id="pnl_gross_profit", label="Gross Profit", level=0,
        value=monthly_gp, unit="GBP/mo",
        parents=["pnl_revenue", "pnl_cogs"],
        efficiency=monthly_gp / monthly_rev if monthly_rev > 0 else 0,
        efficiency_label=f"{monthly_gp/monthly_rev*100:.1f}% margin",
        description="Revenue minus COGS",
        icon="📈", color="#4caf50" if monthly_gp > 0 else "#f44336",
        benchmark=75.0, benchmark_source="UK Coffee Industry Report",
        change_7d=gp_7d, change_7d_pct=0,
        change_30d=gp_30d, change_30d_pct=0,
        trend=_trend("up" if gp_7d > 0 else "down"),
        sparkline=[r - c for r, c in zip(rev_stats["sparkline"], total_cogs_daily[-30:])]
    ))

    # Staff aggregate
    staff_daily = [sum(S["daily_staff"].get(d, {}).get(r, 0) for r in ["barista", "shift_supervisor", "manager"]) for d in S["all_dates"]]
    staff_7d = sum(staff_daily[-7:]) / 7 - sum(staff_daily[-14:-7]) / 7
    staff_7d_pct = (staff_7d / (sum(staff_daily[-14:-7]) / 7) * 100) if sum(staff_daily[-14:-7]) > 0 else 0
    staff_30d = sum(staff_daily[-30:]) / 30 - sum(staff_daily[-60:-30]) / 30
    staff_30d_pct = (staff_30d / (sum(staff_daily[-60:-30]) / 30) * 100) if sum(staff_daily[-60:-30]) > 0 else 0

    g.add(AggregateNode(
        id="pnl_staff", label="Staff Costs", level=0,
        value=monthly_staff, unit="GBP/mo",
        description="Total employer labour costs (gross + NI + pension)",
        icon="👥", color="#ff9800",
        change_7d=staff_7d, change_7d_pct=staff_7d_pct,
        change_30d=staff_30d, change_30d_pct=staff_30d_pct,
        trend=_trend("up" if staff_7d_pct > 3 else "down" if staff_7d_pct < -3 else "flat"),
        sparkline=staff_daily[-30:]
    ))

    # Overheads aggregate (fixed = flat)
    oh_daily = [sum(S["daily_oh"].get(d, {}).get(o, 0) for o in S["daily_oh"].get(d, {})) for d in S["all_dates"]]
    g.add(AggregateNode(
        id="pnl_overheads", label="Overheads", level=0,
        value=monthly_oh, unit="GBP/mo",
        description="Fixed operating costs",
        icon="🏢", color="#9c27b0",
        change_7d=0, change_7d_pct=0,
        change_30d=0, change_30d_pct=0,
        trend=TrendDirection.FLAT,
        sparkline=oh_daily[-30:]
    ))

    # Operating Profit
    op_7d = gp_7d - staff_7d  # overheads flat
    op_30d = gp_30d - staff_30d
    g.add(MetricNode(
        id="pnl_operating_profit", label="Operating Profit", level=0,
        value=monthly_op, unit="GBP/mo",
        parents=["pnl_gross_profit", "pnl_staff", "pnl_overheads"],
        efficiency=monthly_op / monthly_rev if monthly_rev > 0 else 0,
        efficiency_label=f"{monthly_op/monthly_rev*100:.1f}% margin",
        description="Gross profit minus staff and overheads",
        icon="📊", color="#4caf50" if monthly_op > 0 else "#f44336",
        benchmark=10.0, benchmark_source="UK Coffee Industry Report",
        change_7d=op_7d, change_7d_pct=0,
        change_30d=op_30d, change_30d_pct=0,
        trend=_trend("up" if op_7d > 0 else "down"),
        sparkline=[gp - s - oh for gp, s, oh in zip(
            [r - c for r, c in zip(rev_stats["sparkline"], total_cogs_daily[-30:])],
            staff_daily[-30:],
            oh_daily[-30:]
        )]
    ))

    # Set children
    g.get("pnl_revenue").children = ["rev_coffee", "rev_pastry", "rev_hot_drink", "rev_cold_drink"]
    g.get("pnl_cogs").children = ["cog_beans", "cog_milk", "cog_pastries", "cog_packaging", "cog_consumables"]
    g.get("pnl_gross_profit").children = ["pnl_revenue", "pnl_cogs"]
    g.get("pnl_staff").children = ["staff_barista", "staff_shift_supervisor", "staff_manager"]
    g.get("pnl_overheads").children = ["oh_premises", "oh_operations", "oh_technology", "oh_professional", "oh_marketing", "oh_depreciation"]
    g.get("pnl_operating_profit").children = ["pnl_gross_profit", "pnl_staff", "pnl_overheads"]

    # Compute child contribution % for Level 0
    for parent_id in g.root_nodes:
        parent = g.get(parent_id)
        if not parent or not parent.children or parent.value == 0:
            continue
        for child_id in parent.children:
            child = g.get(child_id)
            if child:
                parent.child_contribution_pct[child_id] = round(abs(child.value) / abs(parent.value) * 100, 1)

    # ──────────────────────────────────────────────
    # LEVEL 1: Revenue breakdown
    # ──────────────────────────────────────────────

    for cat in ["coffee", "pastry", "hot_drink", "cold_drink"]:
        rev = cat_rev.get(cat, 0) / 3
        units = cat_units.get(cat, 0) / 3
        avg_price = rev / units if units > 0 else 0
        cs = S["categories"].get(cat, {})
        g.add(RevenueNode(
            id=f"rev_{cat}", label=cat.replace("_", " ").title(), level=1,
            value=rev, unit="GBP/mo",
            volume=units, unit_type="items/mo",
            price=avg_price,
            parent_group="pnl_revenue",
            icon="☕" if "coffee" in cat else "🥐" if cat == "pastry" else "🫖" if cat == "hot_drink" else "🥤",
            change_7d=cs.get("change_7d", 0), change_7d_pct=cs.get("change_7d_pct", 0),
            change_30d=cs.get("change_30d", 0), change_30d_pct=cs.get("change_30d_pct", 0),
            trend=_trend(cs.get("trend_7d", "flat")),
            sparkline=cs.get("sparkline", [])
        ))

    # Product children for revenue categories
    g.get("rev_coffee").children = ["prod_latte", "prod_cappuccino", "prod_flat_white", "prod_americano", "prod_mocha", "prod_espresso", "prod_iced_latte", "prod_filter_coffee"]
    g.get("rev_pastry").children = ["prod_croissant", "prod_pain_au_chocolat", "prod_muffin", "prod_scone", "prod_cookie"]
    g.get("rev_hot_drink").children = ["prod_tea", "prod_hot_chocolate", "prod_chai_latte"]
    g.get("rev_cold_drink").children = ["prod_smoothie"]

    # ──────────────────────────────────────────────
    # LEVEL 1: COGS breakdown
    # ──────────────────────────────────────────────

    for node_id in ["cog_beans", "cog_milk", "cog_pastries", "cog_packaging", "cog_consumables"]:
        cs = S["cogs"].get(node_id, {})
        total = sum(cs.get("sparkline", []))  # sum of last 30 daily = approximate monthly
        monthly = total  # already daily * 30
        g.add(CostNode(
            id=node_id, label=node_id.replace("cog_", "").replace("_", " ").title(),
            level=1, value=monthly, unit="GBP/mo",
            cost_type="variable", is_controllable=True,
            parent_group="pnl_cogs",
            change_7d=cs.get("change_7d", 0), change_7d_pct=cs.get("change_7d_pct", 0),
            change_30d=cs.get("change_30d", 0), change_30d_pct=cs.get("change_30d_pct", 0),
            trend=_trend(cs.get("trend_7d", "flat")),
            sparkline=cs.get("sparkline", [])
        ))

    # COGS children
    g.get("cog_beans").children = ["bean_wholesale"]
    g.get("cog_milk").children = ["milk_whole_buy", "milk_oat_buy", "milk_almond_buy"]
    g.get("cog_pastries").children = ["pastry_croissant_buy", "pastry_pain_au_chocolat_buy", "pastry_muffin_buy", "pastry_scone_buy", "pastry_cookie_buy"]
    g.get("cog_packaging").children = ["pkg_cups", "pkg_lids", "pkg_napkins"]
    g.get("cog_consumables").children = ["cons_chocolate", "cons_chai", "cons_tea", "cons_sugar", "cons_smoothie"]

    # Contribution % for COGS
    for parent_id in ["pnl_cogs", "pnl_revenue"]:
        parent = g.get(parent_id)
        if not parent or not parent.children or parent.value == 0:
            continue
        for child_id in parent.children:
            child = g.get(child_id)
            if child:
                parent.child_contribution_pct[child_id] = round(abs(child.value) / abs(parent.value) * 100, 1)

    # ──────────────────────────────────────────────
    # LEVEL 1: Staff breakdown
    # ──────────────────────────────────────────────

    role_costs = defaultdict(float)
    role_hours = defaultdict(float)
    for p in payroll:
        role_costs[p["role"]] += p["total_employer_cost"] / 3
        role_hours[p["role"]] += p["actual_hours_worked"] / 3

    for role in ["barista", "shift_supervisor", "manager"]:
        cost = role_costs.get(role, 0)
        hours = role_hours.get(role, 0)
        avg_rate = cost / hours if hours > 0 else 0
        role_staff_ids = [s["id"] for s in staff_roster if s["role"] == role]
        role_revenue = sum(t["total"] for t in transactions if t["staff_id"] in role_staff_ids) / 3
        rev_per_hour = role_revenue / hours if hours > 0 else 0

        ss = S["staff"].get(role, {})
        g.add(ProcessNode(
            id=f"staff_{role}", label=role.replace("_", " ").title(),
            level=1, value=cost, unit="GBP/mo",
            throughput=hours, capacity=hours * 1.1,
            utilisation=hours / (hours * 1.1) * 100 if hours > 0 else 0,
            parent_group="pnl_staff",
            icon="👤" if role != "manager" else "👔",
            metadata={"avg_hourly_rate": round(avg_rate, 2), "revenue_per_hour": round(rev_per_hour, 2)},
            change_7d=ss.get("change_7d", 0), change_7d_pct=ss.get("change_7d_pct", 0),
            change_30d=ss.get("change_30d", 0), change_30d_pct=ss.get("change_30d_pct", 0),
            trend=_trend(ss.get("trend_7d", "flat")),
            sparkline=ss.get("sparkline", [])
        ))

    g.get("staff_barista").children = ["staff_s001", "staff_s002", "staff_s004"]
    g.get("staff_shift_supervisor").children = ["staff_s003"]
    g.get("staff_manager").children = ["staff_s005"]

    # ──────────────────────────────────────────────
    # LEVEL 1: Overhead breakdown
    # ──────────────────────────────────────────────

    oh_categories = {
        "oh_premises": ["rent", "business_rates", "utilities_electric", "utilities_water", "utilities_gas"],
        "oh_operations": ["insurance", "waste_collection", "cleaning", "equipment_maintenance"],
        "oh_technology": ["internet", "pos_software", "phone"],
        "oh_professional": ["accountant", "bank_charges"],
        "oh_marketing": ["marketing", "music_licence"],
        "oh_depreciation": ["depreciation"],
    }

    for node_id, items in oh_categories.items():
        total = sum(overheads_data.get(k, {}).get("amount", 0) for k in items)
        os_stats = S["overheads"].get(node_id, {})
        g.add(CostNode(
            id=node_id, label=node_id.replace("oh_", "").replace("_", " ").title(),
            level=1, value=total, unit="GBP/mo",
            cost_type="fixed", is_controllable=node_id != "oh_depreciation",
            parent_group="pnl_overheads",
            icon="🏠" if "premises" in node_id else "🔧" if "operations" in node_id else "💻" if "technology" in node_id else "💼" if "professional" in node_id else "📢" if "marketing" in node_id else "📉",
            change_7d=os_stats.get("change_7d", 0), change_7d_pct=os_stats.get("change_7d_pct", 0),
            change_30d=os_stats.get("change_30d", 0), change_30d_pct=os_stats.get("change_30d_pct", 0),
            trend=_trend(os_stats.get("trend_7d", "flat")),
            sparkline=os_stats.get("sparkline", [])
        ))

    g.get("oh_premises").children = ["oh_rent", "oh_rates", "oh_utilities"]
    g.get("oh_operations").children = ["oh_insurance", "oh_cleaning", "oh_maintenance"]
    g.get("oh_technology").children = ["oh_internet", "oh_pos", "oh_phone"]
    g.get("oh_professional").children = ["oh_accountant", "oh_bank"]
    g.get("oh_marketing").children = ["oh_marketing_ads", "oh_music"]

    # ──────────────────────────────────────────────
    # LEVEL 2: Individual staff members
    # ──────────────────────────────────────────────

    for s in staff_roster:
        sid = s["id"]
        s_payroll = [p for p in payroll if p["staff_id"] == sid]
        s_cost = sum(p["total_employer_cost"] for p in s_payroll) / 3
        s_hours = sum(p["actual_hours_worked"] for p in s_payroll) / 3
        s_revenue = sum(t["total"] for t in transactions if t["staff_id"] == sid) / 3

        sms = S["staff_members"].get(sid, {})
        g.add(ProcessNode(
            id=f"staff_{sid.lower()}", label=s["name"],
            level=2, value=s_cost, unit="GBP/mo",
            throughput=s_hours, capacity=s["contract_hours_per_week"] * 4.33,
            utilisation=s_hours / (s["contract_hours_per_week"] * 4.33) * 100 if s["contract_hours_per_week"] > 0 else 0,
            parent_group=f"staff_{s['role']}",
            description=f"{s['role']} @ £{s['hourly_rate']:.2f}/hr",
            metadata={
                "hourly_rate": s["hourly_rate"],
                "contract_hours": s["contract_hours_per_week"],
                "revenue_per_hour": round(s_revenue / s_hours, 2) if s_hours > 0 else 0
            },
            change_7d=sms.get("change_7d", 0), change_7d_pct=sms.get("change_7d_pct", 0),
            change_30d=sms.get("change_30d", 0), change_30d_pct=sms.get("change_30d_pct", 0),
            trend=_trend(sms.get("trend_7d", "flat")),
            sparkline=sms.get("sparkline", [])
        ))

    # ──────────────────────────────────────────────
    # LEVEL 2: Individual products
    # ──────────────────────────────────────────────

    for product, agg in product_stats_agg.items():
        monthly_rev = agg["revenue"] / 3
        monthly_units = agg["count"] / 3
        avg_price = monthly_rev / monthly_units if monthly_units > 0 else 0

        item_menu = menu.get(product, {})
        cog_per_unit = 0
        if isinstance(item_menu, dict):
            if "cog_beans_per_shot" in item_menu and item_menu["cog_beans_per_shot"] > 0:
                cog_per_unit += item_menu["cog_beans_per_shot"] * item_menu.get("cog_beans_kg_price", 0)
            if "cog_milk_litres" in item_menu and item_menu["cog_milk_litres"] > 0:
                cog_per_unit += item_menu["cog_milk_litres"] * item_menu.get("cog_milk_price_per_litre", 0)
            for cost_key in ["cog_cup", "cog_lid", "cog_cost", "cog_chocolate", "cog_chai"]:
                cog_per_unit += item_menu.get(cost_key, 0)

        margin = (avg_price - cog_per_unit) / avg_price * 100 if avg_price > 0 else 0

        ps = S["products"].get(product, {})
        g.add(RevenueNode(
            id=f"prod_{product}", label=product.replace("_", " ").title(),
            level=2, value=monthly_rev, unit="GBP/mo",
            volume=monthly_units, unit_type="units/mo",
            price=avg_price,
            parent_group=f"rev_{agg['category']}",
            metadata={
                "cog_per_unit": round(cog_per_unit, 2),
                "margin_pct": round(margin, 1),
                "monthly_units": round(monthly_units, 0)
            },
            change_7d=ps.get("change_7d", 0), change_7d_pct=ps.get("change_7d_pct", 0),
            change_30d=ps.get("change_30d", 0), change_30d_pct=ps.get("change_30d_pct", 0),
            trend=_trend(ps.get("trend_7d", "flat")),
            sparkline=ps.get("sparkline", [])
        ))

    # ──────────────────────────────────────────────
    # LEVEL 2: COGS sub-items
    # ──────────────────────────────────────────────

    g.add(InputNode(
        id="bean_wholesale", label="Has Bean Coffee Co", level=2,
        value=sum(cogs_data[m].get("coffee_beans", {}).get("total", 0) for m in cogs_data if not m.startswith("_")) / 3,
        unit="GBP/mo", quantity=85, unit_measure="kg/mo",
        supplier="Has Bean Coffee Co", parent_group="cog_beans",
        metadata={"price_per_kg": 22.00}
    ))

    for milk_type, key, label in [("Whole", "milk_whole", "Arla Foods"), ("Oat", "milk_oat", "Oatly UK"), ("Almond", "milk_almond", "Alpro UK")]:
        monthly = sum(cogs_data[m].get(key, {}).get("total", 0) for m in cogs_data if not m.startswith("_")) / 3
        qty = sum(cogs_data[m].get(key, {}).get("quantity_litres", 0) for m in cogs_data if not m.startswith("_")) / 3
        g.add(InputNode(
            id=f"milk_{milk_type.lower()}_buy", label=f"{milk_type} Milk — {label}",
            level=2, value=monthly, unit="GBP/mo",
            quantity=qty, unit_measure="L/mo", supplier=label,
            parent_group="cog_milk",
            metadata={"price_per_litre": round(monthly / qty, 2) if qty > 0 else 0}
        ))

    for p_key, p_name in [("pastries_croissant", "Croissant"), ("pastries_pain_au_chocolat", "Pain au Chocolat"), ("pastries_muffin", "Muffin"), ("pastries_scone", "Scone"), ("pastries_cookie", "Cookie")]:
        monthly = sum(cogs_data[m].get(p_key, {}).get("total", 0) for m in cogs_data if not m.startswith("_")) / 3
        qty = sum(cogs_data[m].get(p_key, {}).get("quantity", 0) for m in cogs_data if not m.startswith("_")) / 3
        g.add(InputNode(
            id=f"pastry_{p_key.replace('pastries_', '')}_buy", label=f"{p_name} — Bakers Delight",
            level=2, value=monthly, unit="GBP/mo",
            quantity=qty, unit_measure="units/mo", supplier="Bakers Delight Ltd",
            parent_group="cog_pastries",
            metadata={"price_per_unit": round(monthly / qty, 2) if qty > 0 else 0}
        ))

    for pkg_group, items, label in [
        ("pkg_cups", ["cups_8oz", "cups_12oz"], "Vegware — Cups"),
        ("pkg_lids", ["lids_8oz", "lids_12oz"], "Vegware — Lids"),
        ("pkg_napkins", ["napkins", "stirrers"], "Vegware — Napkins & Stirrers")
    ]:
        monthly = sum(sum(cogs_data[m].get(k, {}).get("total", 0) for k in items) for m in cogs_data if not m.startswith("_")) / 3
        g.add(InputNode(id=pkg_group, label=label, level=2, value=monthly, unit="GBP/mo",
                        supplier="Vegware", parent_group="cog_packaging"))

    cons_mapping = {
        "cons_chocolate": ("chocolate_powder", "Chocolate Powder — Callebaut"),
        "cons_chai": ("chai_concentrate", "Chai Concentrate — TeaPigs"),
        "cons_tea": ("tea_bags", "Tea Bags — TeaPigs"),
        "cons_sugar": ("sugar_sachets", "Sugar Sachets — Whittard"),
        "cons_smoothie": ("smoothie_ingredients", "Smoothie Ingredients — Fresh Direct"),
    }
    for cons_key, (orig_key, cons_name) in cons_mapping.items():
        monthly = sum(cogs_data[m].get(orig_key, {}).get("total", 0) for m in cogs_data if not m.startswith("_")) / 3
        g.add(InputNode(id=cons_key, label=cons_name, level=2, value=monthly, unit="GBP/mo",
                        parent_group="cog_consumables"))

    # ──────────────────────────────────────────────
    # LEVEL 2: Overhead sub-items (fixed = flat)
    # ──────────────────────────────────────────────

    g.add(CostNode(id="oh_rent", label="Rent", level=2, value=2200, unit="GBP/mo", cost_type="fixed", is_controllable=False, parent_group="oh_premises", metadata={"landlord": "Highcross Estates Ltd"}))
    g.add(CostNode(id="oh_rates", label="Business Rates", level=2, value=480, unit="GBP/mo", cost_type="fixed", is_controllable=False, parent_group="oh_premises"))
    g.add(CostNode(id="oh_utilities", label="Utilities", level=2, value=555, unit="GBP/mo", cost_type="fixed", is_controllable=True, parent_group="oh_premises"))
    g.add(CostNode(id="oh_insurance", label="Insurance", level=2, value=175, unit="GBP/mo", cost_type="fixed", is_controllable=True, parent_group="oh_operations"))
    g.add(CostNode(id="oh_cleaning", label="Cleaning", level=2, value=200, unit="GBP/mo", cost_type="fixed", is_controllable=True, parent_group="oh_operations"))
    g.add(CostNode(id="oh_maintenance", label="Equipment Maintenance", level=2, value=120, unit="GBP/mo", cost_type="fixed", is_controllable=True, parent_group="oh_operations"))
    g.add(CostNode(id="oh_internet", label="Internet", level=2, value=65, unit="GBP/mo", cost_type="fixed", is_controllable=True, parent_group="oh_technology"))
    g.add(CostNode(id="oh_pos", label="POS Software", level=2, value=79, unit="GBP/mo", cost_type="fixed", is_controllable=True, parent_group="oh_technology"))
    g.add(CostNode(id="oh_phone", label="Phone", level=2, value=45, unit="GBP/mo", cost_type="fixed", is_controllable=True, parent_group="oh_technology"))
    g.add(CostNode(id="oh_accountant", label="Accountant", level=2, value=200, unit="GBP/mo", cost_type="fixed", is_controllable=True, parent_group="oh_professional"))
    g.add(CostNode(id="oh_bank", label="Bank Charges", level=2, value=35, unit="GBP/mo", cost_type="fixed", is_controllable=True, parent_group="oh_professional"))
    g.add(CostNode(id="oh_marketing_ads", label="Marketing & Ads", level=2, value=150, unit="GBP/mo", cost_type="fixed", is_controllable=True, parent_group="oh_marketing"))
    g.add(CostNode(id="oh_music", label="Music Licence", level=2, value=25, unit="GBP/mo", cost_type="fixed", is_controllable=False, parent_group="oh_marketing"))

    # Build edges with contribution %
    for nid, node in g.nodes.items():
        for child_id in node.children:
            if child_id in g.nodes:
                child = g.nodes[child_id]
                contrib = round(abs(child.value) / abs(node.value) * 100, 1) if node.value != 0 else 0
                node.child_contribution_pct[child_id] = contrib
                g.edges.append({
                    "source": nid,
                    "target": child_id,
                    "label": child.label,
                    "value": round(child.value, 2),
                    "contribution_pct": contrib,
                    "trend": child.trend.value if hasattr(child.trend, 'value') else str(child.trend),
                    "change_pct": round(child.change_7d_pct, 1)
                })

    return g



# ---------------------------------------------------------------------------
# Legacy flat loader — kept for the CLI / transform.py / KPI path.
# The hierarchical load_graph() above powers the UI. This returns a plain
# object with the flat attributes those older modules expect.
# ---------------------------------------------------------------------------

def load_all(tenant_id):
    """Load a tenant's flat business object (legacy API).

    ``tenant_id`` is mandatory and has no default on purpose: a silent fallback
    to the café tenant is exactly how cross-tenant data leaked into the SaaS
    dashboard. Callers must name the tenant they are reading.
    """
    cfg = load_tenant_config(tenant_id)
    data_dir = os.path.join(DATA_ROOT, cfg["data_dir"])
    if os.path.exists(os.path.join(data_dir, "company_profile.json")):
        return _load_business_from_dir(data_dir)
    return _business_from_graph(load_graph(tenant_id), cfg)


def _load_business_from_dir(data_dir):
    """Read the flat JSON export for one tenant's own data directory."""
    from types import SimpleNamespace

    with open(os.path.join(data_dir, "company_profile.json")) as f:
        profile = json.load(f)
    with open(os.path.join(data_dir, "transactions.json")) as f:
        raw_txns = json.load(f)
    with open(os.path.join(data_dir, "payroll.json")) as f:
        payroll = json.load(f)
    with open(os.path.join(data_dir, "cogs_purchases.json")) as f:
        cogs = json.load(f)
    with open(os.path.join(data_dir, "overheads.json")) as f:
        overheads = json.load(f)
    with open(os.path.join(data_dir, "menu.json")) as f:
        menu = json.load(f)
    with open(os.path.join(data_dir, "bottom_up_pl.json")) as f:
        pl_data = json.load(f)
    with open(os.path.join(data_dir, "balance_sheet.json")) as f:
        balance_sheet = json.load(f)

    with open(os.path.join(data_dir, "staff_roster.json")) as f:
        staff_list = json.load(f)
    staff = {s["id"]: SimpleNamespace(**s) for s in staff_list}

    txns = [SimpleNamespace(**t) for t in raw_txns]

    monthly_pnl = {}
    for month, data in pl_data["monthly"].items():
        monthly_pnl[month] = SimpleNamespace(
            month=month,
            revenue=data["revenue"]["total"],
            cogs=data["cost_of_goods_sold"]["total"],
            gross_profit=data["gross_profit"]["amount"],
            staff_costs=data["staff_costs"]["total_employer_cost"],
            overheads=data["overheads"]["total"],
            operating_profit=data["operating_profit"]["amount"],
            net_profit=data["net_profit"]["amount"],
            transactions=data["revenue"]["transaction_count"],
        )

    return SimpleNamespace(
        company_name=profile["company_name"],
        company_number=profile["company_number"],
        transactions=txns,
        staff=staff,
        payroll=payroll,
        cogs=cogs,
        overheads=overheads,
        menu=menu,
        monthly_pnl=monthly_pnl,
        balance_sheet=balance_sheet,
    )

def _business_from_graph(g, cfg):
    """Synthesise a flat business object for tenants that ship no JSON export.

    SaaS tenants only have ``company.json``; their financials live in the graph.
    Everything below is derived from *this tenant's own nodes*, so nothing can
    cross-contaminate. The shape matches the cafe JSON loader so the dashboard
    template works unchanged.
    """
    from types import SimpleNamespace
    from datetime import date
    from dateutil.relativedelta import relativedelta

    def _val(node_id, default=0.0):
        node = g.get(node_id)
        return float(node.value) if node is not None else default

    def _series(node_id, n=30):
        node = g.get(node_id)
        s = list(getattr(node, "sparkline", []) or []) if node is not None else []
        return s[-n:] if s else []

    revenue, cogs, opex = _val("saas_revenue"), _val("saas_cogs"), _val("saas_opex")
    rev_s, cogs_s = _series("saas_revenue"), _series("saas_cogs")

    months = []
    today = date.today()
    for i in (2, 1, 0):
        d = today.replace(day=1) - relativedelta(months=i)
        months.append((d.strftime("%Y-%m"), d.strftime("%b %Y")))

    monthly_pnl = {}
    for idx, (key, label) in enumerate(months):
        # Sparkline points are monthly run-rate observations (each ~£45k), not
        # daily values — so a month's revenue is the *mean* of its chunk. Summing
        # would inflate revenue by the chunk size.
        if len(rev_s) >= 3:
            chunk = rev_s[idx * len(rev_s) // 3:(idx + 1) * len(rev_s) // 3]
            rev = sum(chunk) / len(chunk) if chunk else revenue
        else:
            rev = revenue
        if len(cogs_s) >= 3:
            cchunk = cogs_s[idx * len(cogs_s) // 3:(idx + 1) * len(cogs_s) // 3]
            cg = sum(cchunk) / len(cchunk) if cchunk else cogs
        else:
            cg = cogs
        gp = rev - cg
        op = gp - opex
        monthly_pnl[key] = SimpleNamespace(
            month=label, revenue=round(rev, 2), cogs=round(cg, 2),
            gross_profit=round(gp, 2), staff_costs=0.0,
            overheads=round(opex, 2), operating_profit=round(op, 2),
            net_profit=round(op, 2), transactions=0,
        )

    menu, payroll = {}, []
    for nid, node in g.nodes.items():
        ntype = node.node_type.value
        if ntype == "revenue" and nid != "saas_revenue":
            menu[node.label] = {"price": round(float(node.value), 2), "category": "subscription"}
        elif ntype == "cost" and nid.startswith("opex_"):
            payroll.append({"month": months[-1][0], "role": node.label,
                            "actual_hours_worked": 0,
                            "total_employer_cost": round(float(node.value), 2)})

    return SimpleNamespace(
        company_name=cfg.get("name", "Unknown"), company_number=cfg.get("number", ""),
        transactions=[], staff={}, payroll=payroll, cogs={}, overheads={},
        menu=menu, monthly_pnl=monthly_pnl, balance_sheet={},
    )


# ---------------------------------------------------------------------------
# Multi-tenant dispatcher
# ---------------------------------------------------------------------------

class UnknownTenantError(KeyError):
    """Raised when a tenant id is not present in the registry."""


def load_tenant_config(tenant_id: str) -> dict:
    """Return the registry entry for a tenant.

    Raises ``UnknownTenantError`` for an unknown id. It used to fall back to
    jonco, which meant a typo or a stale id silently rendered the café's books
    under another tenant's name — a data-leak bug in its own right.
    """
    with open(TENANTS_PATH) as f:
        tenants = json.load(f)
    if tenant_id not in tenants:
        raise UnknownTenantError(f"unknown tenant: {tenant_id!r}")
    return tenants[tenant_id]


def list_tenants() -> dict:
    """Return the full tenant registry."""
    with open(TENANTS_PATH) as f:
        return json.load(f)


def load_graph(tenant_id: str = "jonco") -> BusinessGraph:
    """Load the correct graph for the given tenant.

    Dispatches to the SaaS loader for ``type == "saas"`` and the existing
    cafe loader for ``type == "cafe"``.
    """
    tenant = load_tenant_config(tenant_id)
    tenant_dir = os.path.join(DATA_ROOT, tenant["data_dir"])
    if tenant.get("type") == "saas":
        from .saas_loader import build_saas_graph
        company_path = os.path.join(tenant_dir, "company.json")
        return build_saas_graph(company_path)
    return _load_cafe_graph(
        data_dir=tenant_dir,
        stats_path=os.path.join(tenant_dir, "rolling_stats.pkl"),
    )

