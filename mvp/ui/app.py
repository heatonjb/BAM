"""Flask web UI for Business as a Machine MVP."""

import os
import sys
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

# Load env before importing modules that need API keys
_env_path = os.path.expanduser("~/.hermes/.env")
if os.path.exists(_env_path):
    with open(_env_path) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ.setdefault(k, v)

from flask import Flask, render_template, jsonify, request
from mvp.model.core import NodeType
from mvp.model.constraints import ConstraintStore, build_default_constraints
from mvp.loader import load_graph
from mvp.insights import generate_insights

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))

_graph = None
_constraints = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = load_graph()
    return _graph

def get_constraints():
    global _constraints
    if _constraints is None:
        _constraints = ConstraintStore()
        for c in build_default_constraints():
            _constraints.add(c)
    return _constraints


@app.route("/")
def index():
    g = get_graph()
    cs = get_constraints()
    level0 = g.get_level(0)

    pnl = []
    for node in level0:
        constraints = cs.get_for_node(node.id, g)
        pnl.append({
            "id": node.id,
            "label": node.label,
            "value": round(node.value, 2),
            "unit": node.unit,
            "icon": node.icon or "📊",
            "color": node.color or "#607d8b",
            "efficiency": node.efficiency,
            "efficiency_label": node.efficiency_label,
            "type": node.node_type.value,
            "has_children": len(node.children) > 0,
            "change_7d": round(node.change_7d, 2),
            "change_7d_pct": round(node.change_7d_pct, 1),
            "change_30d": round(node.change_30d, 2),
            "change_30d_pct": round(node.change_30d_pct, 1),
            "trend": node.trend.value if hasattr(node.trend, 'value') else str(node.trend),
            "sparkline": [round(v, 2) for v in node.sparkline[-30:]] if node.sparkline else [],
            "constraint_count": len(constraints),
            "hard_constraints": sum(1 for c in constraints if c.severity.value == "hard"),
        })

    company = {
        "name": "JONCO COFFEE LIMITED",
        "number": "15999847",
        "period": "Oct–Dec 2024 (monthly averages)"
    }

    kpis = []
    for node in g.get_by_type(NodeType.METRIC):
        if node.benchmark is not None:
            kpis.append({
                "name": node.label,
                "value": round(node.value, 2),
                "unit": node.unit,
                "benchmark": node.benchmark,
                "id": node.id,
            })

    return render_template("index.html",
                         company=company,
                         pnl=pnl,
                         kpis=kpis)


@app.route("/drill/<node_id>")
def drill(node_id):
    g = get_graph()
    cs = get_constraints()
    node = g.get(node_id)
    if not node:
        return "Not found", 404

    subgraph = g.get_subgraph(node_id, depth=2)
    path = g.get_drill_path(node_id)

    graph_nodes = []
    for nid, ndata in subgraph["nodes"].items():
        graph_nodes.append(ndata)

    # Constraints for this node
    constraints = cs.get_for_node(node_id, g)
    constraints_list = [c.to_dict() for c in constraints]

    # All constraints summary
    all_constraints = cs.to_dict()

    return render_template("drill.html",
                         node=node.to_dict(),
                         subgraph=subgraph,
                         path=path,
                         graph_nodes=graph_nodes,
                         constraints=constraints_list,
                         all_constraints=all_constraints)


@app.route("/api/insights/<node_id>", methods=["POST"])
def api_insights(node_id):
    """Generate AI-powered insights for a node."""
    g = get_graph()
    cs = get_constraints()
    node = g.get(node_id)
    if not node:
        return jsonify({"error": "node not found"}), 404

    data = request.json or {}
    model = data.get("model", "z-ai/glm-4.5-air")

    result = generate_insights(
        node_id=node.id,
        node_label=node.label,
        node_value=node.value,
        node_trend=node.trend.value if hasattr(node.trend, 'value') else str(node.trend),
        node_change_7d_pct=node.change_7d_pct,
        node_change_30d_pct=node.change_30d_pct,
        node_type=node.node_type.value,
        constraint_store=cs,
        graph=g,
        model=model
    )
    return jsonify(result)


@app.route("/api/constraints")
def api_constraints():
    cs = get_constraints()
    return jsonify(cs.to_dict())


@app.route("/api/constraints/<node_id>")
def api_node_constraints(node_id):
    g = get_graph()
    cs = get_constraints()
    constraints = cs.get_for_node(node_id, g)
    return jsonify([c.to_dict() for c in constraints])


@app.route("/api/node/<node_id>")
def api_node(node_id):
    g = get_graph()
    node = g.get(node_id)
    if not node:
        return jsonify({"error": "not found"}), 404
    return jsonify(node.to_dict())


@app.route("/api/subgraph/<node_id>")
def api_subgraph(node_id):
    g = get_graph()
    depth = request.args.get("depth", 2, type=int)
    subgraph = g.get_subgraph(node_id, depth=depth)
    return jsonify(subgraph)


@app.route("/api/levels")
def api_levels():
    g = get_graph()
    result = {}
    for level in range(3):
        result[f"level_{level}"] = [n.to_dict() for n in g.get_level(level)]
    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
