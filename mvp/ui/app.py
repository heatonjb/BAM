"""Flask web UI for Business as a Machine MVP."""

import os
import sys
import json

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, render_template, jsonify, request
from mvp.loader import load_all
from mvp.transform import TransformationGraph
from mvp.kpi import KPITree
from mvp.agent import AgentHarness

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))

_state = {}

def get_state():
    if "harness" not in _state:
        business = load_all()
        graph = TransformationGraph(business)
        kpi_tree = KPITree(business, graph)
        harness = AgentHarness(business, graph, kpi_tree)
        _state["business"] = business
        _state["graph"] = graph
        _state["kpi_tree"] = kpi_tree
        _state["harness"] = harness
    return _state["harness"]


@app.route("/")
def index():
    harness = get_state()

    monthly = []
    for month, pnl in sorted(harness.business.monthly_pnl.items()):
        monthly.append({
            "month": month,
            "revenue": pnl.revenue,
            "cogs": pnl.cogs,
            "staff_costs": pnl.staff_costs,
            "overheads": pnl.overheads,
            "operating_profit": pnl.operating_profit,
            "net_profit": pnl.net_profit,
            "transactions": pnl.transactions
        })

    kpis = {}
    for name, kpi in harness.kpi_tree.kpis.items():
        kpis[name] = {
            "name": name,
            "value": kpi.value,
            "unit": kpi.unit,
            "benchmark": kpi.benchmark,
            "status": kpi.status,
            "parent": kpi.parent
        }

    opps = harness.kpi_tree.optimisation_opportunities()

    nodes = []
    for nid, node in harness.graph.nodes.items():
        nodes.append({
            "id": nid,
            "label": node.label,
            "value": round(node.value, 2) if node.value else 0,
            "type": node.node_type,
            "efficiency": round(node.efficiency, 2) if node.efficiency else None,
            "constraint": node.constraint,
            "lever": node.lever,
            "parents": node.parents
        })

    staff_data = []
    role_hours = {}
    role_costs = {}
    for p in harness.business.payroll:
        role = p["role"]
        role_hours[role] = role_hours.get(role, 0) + p["actual_hours_worked"] / 3
        role_costs[role] = role_costs.get(role, 0) + p["total_employer_cost"] / 3

    for role in sorted(role_hours):
        hours = role_hours[role]
        cost = role_costs[role]
        rev_per_hour = harness._revenue_for_role(role) / 3 / hours if hours > 0 else 0
        staff_data.append({
            "role": role,
            "hours": round(hours, 1),
            "cost": round(cost, 2),
            "revenue_per_hour": round(rev_per_hour, 2)
        })

    products = []
    product_stats = {}
    for t in harness.business.transactions:
        for item in t.items:
            name = item["item"]
            if name not in product_stats:
                product_stats[name] = {"count": 0, "revenue": 0, "category": item["category"], "price": item["price"]}
            product_stats[name]["count"] += 1
            product_stats[name]["revenue"] += item["price"]

    for name, stats in sorted(product_stats.items(), key=lambda x: -x[1]["revenue"]):
        products.append({
            "name": name,
            "count": stats["count"],
            "revenue": round(stats["revenue"], 2),
            "avg_price": round(stats["revenue"] / stats["count"], 2) if stats["count"] > 0 else 0,
            "category": stats["category"]
        })

    cat_revenue = {}
    for t in harness.business.transactions:
        for item in t.items:
            cat = item["category"]
            cat_revenue[cat] = cat_revenue.get(cat, 0) + item["price"]

    hourly = {}
    for t in harness.business.transactions:
        hour = int(t.timestamp.split("T")[1].split(":")[0])
        if hour not in hourly:
            hourly[hour] = {"revenue": 0, "transactions": 0}
        hourly[hour]["revenue"] += t.total
        hourly[hour]["transactions"] += 1

    hourly_data = [{"hour": h, "revenue": round(hourly[h]["revenue"], 2), "transactions": hourly[h]["transactions"]} for h in sorted(hourly)]

    company = {
        "name": harness.business.company_name,
        "number": harness.business.company_number,
        "period": "Oct-Dec 2024",
        "total_revenue": sum(pnl.revenue for pnl in harness.business.monthly_pnl.values()),
        "total_profit": sum(pnl.net_profit for pnl in harness.business.monthly_pnl.values())
    }

    return render_template("dashboard.html",
                         company=company,
                         monthly=monthly,
                         kpis=kpis,
                         opps=opps,
                         nodes=nodes,
                         staff=staff_data,
                         products=products,
                         cat_revenue=cat_revenue,
                         hourly=hourly_data)


@app.route("/api/query", methods=["POST"])
def api_query():
    data = request.json
    question = data.get("question", "")
    harness = get_state()
    answer = harness.query(question)
    return jsonify({"question": question, "answer": answer})


@app.route("/api/experiment", methods=["POST"])
def api_experiment():
    data = request.json
    harness = get_state()
    exp = harness.propose_experiment(
        name=data.get("name", "experiment"),
        description=data.get("description", ""),
        params=data.get("params", {})
    )
    return jsonify({
        "name": exp.name,
        "description": exp.description,
        "change": exp.change,
        "impact": exp.projected_impact,
        "assumptions": exp.assumptions
    })


@app.route("/api/experiments")
def api_list_experiments():
    harness = get_state()
    experiments = []
    for exp in harness.list_experiments():
        experiments.append({
            "name": exp.name,
            "description": exp.description,
            "change": exp.change,
            "impact": exp.projected_impact
        })
    return jsonify(experiments)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
