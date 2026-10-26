"""Flask web UI for Business as a Machine MVP — hierarchical drill-down with stock tickers."""

import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, PROJECT_ROOT)

from flask import Flask, render_template, jsonify, request
from mvp.model.core import NodeType
from mvp.loader import load_graph

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))

_graph = None

def get_graph():
    global _graph
    if _graph is None:
        _graph = load_graph()
    return _graph


@app.route("/")
def index():
    g = get_graph()
    level0 = g.get_level(0)

    pnl = []
    for node in level0:
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
        })

    company = {
        "name": "JONCO COFFEE LIMITED",
        "number": "15999847",
        "period": "Oct–Dec 2024 (monthly averages)"
    }

    # Benchmark KPIs
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
    node = g.get(node_id)
    if not node:
        return "Not found", 404

    subgraph = g.get_subgraph(node_id, depth=2)
    path = g.get_drill_path(node_id)

    graph_nodes = []
    for nid, ndata in subgraph["nodes"].items():
        graph_nodes.append(ndata)

    return render_template("drill.html",
                         node=node.to_dict(),
                         subgraph=subgraph,
                         path=path,
                         graph_nodes=graph_nodes)


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


@app.route("/api/search")
def api_search():
    g = get_graph()
    q = request.args.get("q", "").lower()
    if not q:
        return jsonify([])
    results = []
    for node in g.nodes.values():
        if q in node.label.lower() or any(q in t.lower() for t in node.tags):
            results.append(node.to_dict())
    return jsonify(results)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
