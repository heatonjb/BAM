"""Build the hierarchical business graph from JonCo data.

Each P&L line becomes a Level 0 AggregateNode.
Drilling down reveals Level 1 breakdown nodes.
Drilling further reveals Level 2 granular nodes.
All nodes extend BaseNode from model.core.
"""

import json
import os
from collections import defaultdict
from typing import Dict, List

from .model.core import (
    BaseNode, NodeType, RevenueNode, CostNode, ProcessNode,
    InputNode, AssetNode, LiabilityNode, MetricNode, AggregateNode,
    BusinessGraph
)

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "jonco")


def load_graph() -> BusinessGraph:
    """Build the full hierarchical graph from data files."""
    g = BusinessGraph()
    
    # ── Load raw data ──
    with open(os.path.join(DATA_DIR, "transactions.json")) as f:
        transactions = json.load(f)
    with open(os.path.join(DATA_DIR, "staff_roster.json")) as f:
        staff_roster = json.load(f)
    with open(os.path.join(DATA_DIR, "payroll.json")) as f:
        payroll = json.load(f)
    with open(os.path.join(DATA_DIR, "cogs_purchases.json")) as f:
        cogs_data = json.load(f)
    with open(os.path.join(DATA_DIR, "overheads.json")) as f:
        overheads_data = json.load(f)
    with open(os.path.join(DATA_DIR, "menu.json")) as f:
        menu = json.load(f)
    with open(os.path.join(DATA_DIR, "bottom_up_pl.json")) as f:
        pl_data = json.load(f)
    with open(os.path.join(DATA_DIR, "balance_sheet.json")) as f:
        bs_data = json.load(f)
    
    # ── Compute monthly averages ──
    monthly_rev = sum(p["revenue"]["total"] for p in pl_data["monthly"].values()) / 3
    monthly_cogs = sum(p["cost_of_goods_sold"]["total"] for p in pl_data["monthly"].values()) / 3
    monthly_staff = sum(p["staff_costs"]["total_employer_cost"] for p in pl_data["monthly"].values()) / 3
    monthly_oh = sum(p["overheads"]["total"] for p in pl_data["monthly"].values()) / 3
    monthly_op = monthly_rev - monthly_cogs - monthly_staff - monthly_oh
    monthly_gp = monthly_rev - monthly_cogs
    
    # Category revenues
    cat_rev = defaultdict(float)
    cat_units = defaultdict(int)
    for t in transactions:
        for item in t["items"]:
            cat_rev[item["category"]] += item["price"]
            cat_units[item["category"]] += 1
    
    # ──────────────────────────────────────────────
    # LEVEL 0: P&L Summary
    # ──────────────────────────────────────────────
    
    g.add(AggregateNode(
        id="pnl_revenue", label="Revenue", level=0,
        value=monthly_rev, unit="GBP/mo",
        description="Total revenue from all sales",
        icon="💰", color="#4caf50"
    ))
    g.add(AggregateNode(
        id="pnl_cogs", label="Cost of Goods Sold", level=0,
        value=monthly_cogs, unit="GBP/mo",
        description="Direct cost of ingredients and packaging",
        icon="📦", color="#ff5722"
    ))
    g.add(MetricNode(
        id="pnl_gross_profit", label="Gross Profit", level=0,
        value=monthly_gp, unit="GBP/mo",
        parents=["pnl_revenue", "pnl_cogs"],
        efficiency=monthly_gp / monthly_rev if monthly_rev > 0 else 0,
        efficiency_label=f"{monthly_gp/monthly_rev*100:.1f}% margin",
        description="Revenue minus COGS",
        icon="📈", color="#4caf50",
        benchmark=75.0, benchmark_source="UK Coffee Industry Report"
    ))
    g.add(AggregateNode(
        id="pnl_staff", label="Staff Costs", level=0,
        value=monthly_staff, unit="GBP/mo",
        description="Total employer labour costs (gross + NI + pension)",
        icon="👥", color="#ff9800"
    ))
    g.add(AggregateNode(
        id="pnl_overheads", label="Overheads", level=0,
        value=monthly_oh, unit="GBP/mo",
        description="Fixed operating costs",
        icon="🏢", color="#9c27b0"
    ))
    g.add(MetricNode(
        id="pnl_operating_profit", label="Operating Profit", level=0,
        value=monthly_op, unit="GBP/mo",
        parents=["pnl_gross_profit", "pnl_staff", "pnl_overheads"],
        efficiency=monthly_op / monthly_rev if monthly_rev > 0 else 0,
        efficiency_label=f"{monthly_op/monthly_rev*100:.1f}% margin",
        description="Gross profit minus staff and overheads",
        icon="📊", color="#4caf50" if monthly_op > 0 else "#f44336",
        benchmark=10.0, benchmark_source="UK Coffee Industry Report"
    ))
    
    # Set children for Level 0 nodes
    g.get("pnl_revenue").children = ["rev_coffee", "rev_pastry", "rev_hot_drink", "rev_cold_drink"]
    g.get("pnl_cogs").children = ["cog_beans", "cog_milk", "cog_pastries", "cog_packaging", "cog_consumables"]
    g.get("pnl_gross_profit").children = ["pnl_revenue", "pnl_cogs"]
    g.get("pnl_staff").children = ["staff_barista", "staff_supervisor", "staff_manager"]
    g.get("pnl_overheads").children = ["oh_premises", "oh_operations", "oh_technology", "oh_professional", "oh_marketing", "oh_depreciation"]
    g.get("pnl_operating_profit").children = ["pnl_gross_profit", "pnl_staff", "pnl_overheads"]
    
    # ──────────────────────────────────────────────
    # LEVEL 1: Revenue breakdown
    # ──────────────────────────────────────────────
    
    for cat in ["coffee", "pastry", "hot_drink", "cold_drink"]:
        rev = cat_rev.get(cat, 0) / 3
        units = cat_units.get(cat, 0) / 3
        avg_price = rev / units if units > 0 else 0
        node_id = f"rev_{cat}"
        g.add(RevenueNode(
            id=node_id, label=cat.replace("_", " ").title(), level=1,
            value=rev, unit="GBP/mo",
            volume=units, unit_type="items/mo",
            price=avg_price,
            parent_group="pnl_revenue",
            icon="☕" if "coffee" in cat or "hot" in cat else "🥐" if cat == "pastry" else "🥤"
        ))
    
    # Revenue node children point to Level 2 products
    g.get("rev_coffee").children = ["prod_latte", "prod_cappuccino", "prod_flat_white", "prod_americano", "prod_mocha", "prod_espresso", "prod_iced_latte", "prod_filter_coffee"]
    g.get("rev_pastry").children = ["prod_croissant", "prod_pain_au_chocolat", "prod_muffin", "prod_scone", "prod_cookie"]
    g.get("rev_hot_drink").children = ["prod_tea", "prod_hot_chocolate", "prod_chai_latte"]
    g.get("rev_cold_drink").children = ["prod_smoothie"]
    
    # ──────────────────────────────────────────────
    # LEVEL 1: COGS breakdown
    # ──────────────────────────────────────────────
    
    # Compute monthly COGS by category
    cog_cats = {
        "cog_beans": lambda k: "coffee" in k and "beans" in k and "filter" not in k,
        "cog_milk": lambda k: "milk" in k,
        "cog_pastries": lambda k: "pastries" in k,
        "cog_packaging": lambda k: k in ["cups_8oz", "cups_12oz", "lids_8oz", "lids_12oz", "napkins", "stirrers"],
        "cog_consumables": lambda k: k in ["chocolate_powder", "chai_concentrate", "tea_bags", "sugar_sachets", "smoothie_ingredients"],
    }
    
    for node_id, matcher in cog_cats.items():
        total = 0
        items_list = []
        for month, items in cogs_data.items():
            if month.startswith("_"):
                continue
            for key, item in items.items():
                if isinstance(item, dict) and "total" in item and matcher(key):
                    total += item["total"]
                    items_list.append(item)
        monthly = total / 3
        g.add(CostNode(
            id=node_id, label=node_id.replace("cog_", "").replace("_", " ").title(),
            level=1, value=monthly, unit="GBP/mo",
            cost_type="variable", is_controllable=True,
            parent_group="pnl_cogs",
            metadata={"items": items_list[:5]}
        ))
    
    g.get("cog_beans").children = ["bean_wholesale"]
    g.get("cog_milk").children = ["milk_whole_buy", "milk_oat_buy", "milk_almond_buy"]
    g.get("cog_pastries").children = ["pastry_croissant_buy", "pastry_pain_buy", "pastry_muffin_buy", "pastry_scone_buy", "pastry_cookie_buy"]
    g.get("cog_packaging").children = ["pkg_cups", "pkg_lids", "pkg_napkins"]
    g.get("cog_consumables").children = ["cons_chocolate", "cons_chai", "cons_tea", "cons_sugar"]
    
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
        
        # Revenue generated by this role
        role_staff_ids = [s["id"] for s in staff_roster if s["role"] == role]
        role_revenue = sum(t["total"] for t in transactions if t["staff_id"] in role_staff_ids) / 3
        rev_per_hour = role_revenue / hours if hours > 0 else 0
        
        g.add(ProcessNode(
            id=f"staff_{role}", label=role.replace("_", " ").title(),
            level=1, value=cost, unit="GBP/mo",
            throughput=hours, capacity=hours * 1.1,
            utilisation=hours / (hours * 1.1) * 100 if hours > 0 else 0,
            parent_group="pnl_staff",
            icon="👤" if role != "manager" else "👔",
            metadata={"avg_hourly_rate": round(avg_rate, 2), "revenue_per_hour": round(rev_per_hour, 2)}
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
        g.add(CostNode(
            id=node_id, label=node_id.replace("oh_", "").replace("_", " ").title(),
            level=1, value=total, unit="GBP/mo",
            cost_type="fixed", is_controllable=node_id != "oh_depreciation",
            parent_group="pnl_overheads",
            icon="🏠" if "premises" in node_id else "🔧" if "operations" in node_id else "💻" if "technology" in node_id else "💼" if "professional" in node_id else "📢" if "marketing" in node_id else "📉"
        ))
    
    # Set children for overhead nodes
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
            }
        ))
    
    # ──────────────────────────────────────────────
    # LEVEL 2: Individual products
    # ──────────────────────────────────────────────
    
    product_stats = defaultdict(lambda: {"count": 0, "revenue": 0, "category": ""})
    for t in transactions:
        for item in t["items"]:
            product_stats[item["item"]]["count"] += 1
            product_stats[item["item"]]["revenue"] += item["price"]
            product_stats[item["item"]]["category"] = item["category"]
    
    for product, stats in product_stats.items():
        monthly_rev = stats["revenue"] / 3
        monthly_units = stats["count"] / 3
        avg_price = monthly_rev / monthly_units if monthly_units > 0 else 0
        
        # COGS per unit
        item_menu = menu.get(product, {})
        if isinstance(item_menu, dict):
            cog_per_unit = 0
            if "cog_beans_per_shot" in item_menu and item_menu["cog_beans_per_shot"] > 0:
                cog_per_unit += item_menu["cog_beans_per_shot"] * item_menu.get("cog_beans_kg_price", 0)
            if "cog_milk_litres" in item_menu and item_menu["cog_milk_litres"] > 0:
                cog_per_unit += item_menu["cog_milk_litres"] * item_menu.get("cog_milk_price_per_litre", 0)
            for cost_key in ["cog_cup", "cog_lid", "cog_cost", "cog_chocolate", "cog_chai"]:
                cog_per_unit += item_menu.get(cost_key, 0)
        else:
            cog_per_unit = 0
        
        margin = (avg_price - cog_per_unit) / avg_price * 100 if avg_price > 0 else 0
        
        g.add(RevenueNode(
            id=f"prod_{product}", label=product.replace("_", " ").title(),
            level=2, value=monthly_rev, unit="GBP/mo",
            volume=monthly_units, unit_type="units/mo",
            price=avg_price,
            parent_group=f"rev_{stats['category']}",
            metadata={
                "cog_per_unit": round(cog_per_unit, 2),
                "margin_pct": round(margin, 1),
                "monthly_units": round(monthly_units, 0)
            }
        ))
    
    # ──────────────────────────────────────────────
    # LEVEL 2: COGS sub-items (suppliers, quantities)
    # ──────────────────────────────────────────────
    
    # Bean supplier
    g.add(InputNode(
        id="bean_wholesale", label="Has Bean Coffee Co",
        level=2, value=sum(cogs_data[m].get("coffee_beans", {}).get("total", 0) for m in cogs_data if not m.startswith("_")) / 3,
        unit="GBP/mo", quantity=85, unit_measure="kg/mo",
        supplier="Has Bean Coffee Co",
        parent_group="cog_beans",
        metadata={"price_per_kg": 22.00}
    ))
    
    # Milk suppliers
    for milk_type, key, label in [("Whole", "milk_whole", "Arla Foods"), ("Oat", "milk_oat", "Oatly UK"), ("Almond", "milk_almond", "Alpro UK")]:
        monthly = sum(cogs_data[m].get(key, {}).get("total", 0) for m in cogs_data if not m.startswith("_")) / 3
        qty = sum(cogs_data[m].get(key, {}).get("quantity_litres", 0) for m in cogs_data if not m.startswith("_")) / 3
        g.add(InputNode(
            id=f"milk_{milk_type.lower()}_buy", label=f"{milk_type} Milk — {label}",
            level=2, value=monthly, unit="GBP/mo",
            quantity=qty, unit_measure="L/mo",
            supplier=label,
            parent_group="cog_milk",
            metadata={"price_per_litre": round(monthly / qty, 2) if qty > 0 else 0}
        ))
    
    # Pastry purchases
    for p_key, p_name in [("pastries_croissant", "Croissant"), ("pastries_pain_au_chocolat", "Pain au Chocolat"), ("pastries_muffin", "Muffin"), ("pastries_scone", "Scone"), ("pastries_cookie", "Cookie")]:
        monthly = sum(cogs_data[m].get(p_key, {}).get("total", 0) for m in cogs_data if not m.startswith("_")) / 3
        qty = sum(cogs_data[m].get(p_key, {}).get("quantity", 0) for m in cogs_data if not m.startswith("_")) / 3
        g.add(InputNode(
            id=f"pastry_{p_key.replace('pastries_', '')}_buy", label=f"{p_name} — Bakers Delight",
            level=2, value=monthly, unit="GBP/mo",
            quantity=qty, unit_measure="units/mo",
            supplier="Bakers Delight Ltd",
            parent_group="cog_pastries",
            metadata={"price_per_unit": round(monthly / qty, 2) if qty > 0 else 0}
        ))
    
    # Packaging
    for pkg_group, items, label in [
        ("pkg_cups", ["cups_8oz", "cups_12oz"], "Vegware — Cups"),
        ("pkg_lids", ["lids_8oz", "lids_12oz"], "Vegware — Lids"),
        ("pkg_napkins", ["napkins", "stirrers"], "Vegware — Napkins & Stirrers")
    ]:
        monthly = sum(sum(cogs_data[m].get(k, {}).get("total", 0) for k in items) for m in cogs_data if not m.startswith("_")) / 3
        g.add(InputNode(
            id=pkg_group, label=label,
            level=2, value=monthly, unit="GBP/mo",
            supplier="Vegware",
            parent_group="cog_packaging"
        ))
    
    # Consumables
    cons_mapping = {
        "cons_chocolate": "chocolate_powder",
        "cons_chai": "chai_concentrate",
        "cons_tea": "tea_bags",
        "cons_sugar": "sugar_sachets",
    }
    for cons_key, orig_key in cons_mapping.items():
        monthly = sum(cogs_data[m].get(orig_key, {}).get("total", 0) for m in cogs_data if not m.startswith("_")) / 3
        cons_name_map = {
            "cons_chocolate": "Chocolate Powder — Callebaut",
            "cons_chai": "Chai Concentrate — TeaPigs",
            "cons_tea": "Tea Bags — TeaPigs",
            "cons_sugar": "Sugar Sachets — Whittard",
        }
        g.add(InputNode(
            id=cons_key, label=cons_name_map[cons_key],
            level=2, value=monthly, unit="GBP/mo",
            parent_group="cog_consumables"
        ))
    
    # ──────────────────────────────────────────────
    # LEVEL 2: Overhead sub-items
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
    
    # ──────────────────────────────────────────────
    # Build edges list for graph rendering
    # ──────────────────────────────────────────────
    for nid, node in g.nodes.items():
        for child_id in node.children:
            if child_id in g.nodes:
                g.edges.append({
                    "source": nid,
                    "target": child_id,
                    "label": g.nodes[child_id].label,
                    "value": round(g.nodes[child_id].value, 2)
                })
    
    return g
