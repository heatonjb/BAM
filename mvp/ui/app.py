"""Flask web UI for Business as a Machine MVP."""

import os
import sys
import json
import threading
import uuid
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor

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
from mvp.loader import load_graph, list_tenants, load_tenant_config
from mvp.insights import generate_insights
from mvp.multiagent import MultiAgentOrchestrator, OrchestratorConfig
from mvp.multiagent.control_models import ControlModel
from mvp.multiagent.external import build_default_registry
from mvp.multiagent.controller import AutonomousGraphController, HealthThresholds, ControllerState

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))

_graph = None
_graphs = {}
_constraints = None
_orchestrators = {}
_last_plans = {}
_controller = None
_controller_lock = threading.Lock()


def _current_tenant():
    """Resolve the active tenant from the query string or default to jonco."""
    tenant_id = request.args.get("tenant", "jonco")
    try:
        return load_tenant_config(tenant_id)["id"]
    except Exception:
        return "jonco"

# --- Async insight job infrastructure ---
_jobs = {}
_jobs_lock = threading.Lock()
_insights_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="insights")

def _job_set(job_id, **fields):
    with _jobs_lock:
        _jobs.setdefault(job_id, {}).update(fields)

def _run_insights_job(job_id, node_id, model, tenant_id="jonco"):
    """Background worker: generates insights and stores result in _jobs."""
    try:
        _job_set(job_id, status="running", started_at=datetime.now(timezone.utc).isoformat())
        g = get_graph(tenant_id)
        cs = get_constraints()
        node = g.get(node_id)
        if not node:
            _job_set(job_id, status="error", error="node not found", finished_at=datetime.now(timezone.utc).isoformat())
            return
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
            model=model,
            tenant_id=tenant_id,
        )
        _job_set(job_id, status="completed", result=result, finished_at=datetime.now(timezone.utc).isoformat())
    except Exception as e:
        import traceback
        _job_set(job_id, status="error", error=str(e), traceback=traceback.format_exc(), finished_at=datetime.now(timezone.utc).isoformat())

def get_orchestrator(tenant_id=None):
    """Return a tenant-scoped orchestrator with its own initiative database."""
    global _orchestrators
    if tenant_id is None:
        tenant_id = _current_tenant()
    if tenant_id not in _orchestrators:
        db_path = os.path.join(PROJECT_ROOT, 'data', f'initiatives_{tenant_id}.db')
        orch = MultiAgentOrchestrator(OrchestratorConfig(
            control_model=ControlModel.HIERARCHICAL,
            budget_effort=20.0,
            max_initiatives=6,
            db_path=db_path,
        ))
        orch.constraint_store = get_constraints()
        orch.checker = orch.checker or __import__('mvp.multiagent.constraint_checker', fromlist=['ConstraintCheckerAgent']).ConstraintCheckerAgent(orch.constraint_store)
        _orchestrators[tenant_id] = orch
    return _orchestrators[tenant_id]

def get_graph(tenant_id=None):
    global _graphs
    if tenant_id is None:
        tenant_id = _current_tenant()
    if tenant_id not in _graphs:
        _graphs[tenant_id] = load_graph(tenant_id)
    return _graphs[tenant_id]

def get_constraints():
    global _constraints
    if _constraints is None:
        _constraints = ConstraintStore()
        for c in build_default_constraints():
            _constraints.add(c)
    return _constraints


@app.route("/")
def index():
    tenant_id = _current_tenant()
    g = get_graph(tenant_id)
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

    tenant_cfg = load_tenant_config(tenant_id)
    company = {
        "name": tenant_cfg.get("name", "Unknown"),
        "number": tenant_cfg.get("number", ""),
        "period": tenant_cfg.get("period", ""),
    }

    # Metrics are graph nodes, reachable by drilling down — not custom homepage chips.
    kpis = []

    # ── Projections: "nothing changes" — hold current monthly averages flat ──
    projections = []
    for row in pnl:
        base = row["value"]
        projections.append({
            "label": row["label"],
            "icon": row["icon"],
            "type": row["type"],
            "current": round(base, 2),
            "m1": round(base * 1, 2),
            "m3": round(base * 3, 2),
            "y1": round(base * 12, 2),
        })

    return render_template("index.html",
                         company=company,
                         pnl=pnl,
                         kpis=kpis,
                         projections=projections,
                         tenants=list_tenants(),
                         current_tenant=tenant_id)


@app.route("/api/tenants")
def api_tenants():
    """Return the list of tenants for the company selector."""
    return jsonify(list_tenants())


@app.route("/drill/<node_id>")
def drill(node_id):
    tenant_id = _current_tenant()
    g = get_graph(tenant_id)
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
                         all_constraints=all_constraints,
                         current_tenant=tenant_id,
                         tenants=list_tenants())


@app.route("/api/insights/<node_id>", methods=["POST"])
def api_insights(node_id):
    """Queue AI-powered insights generation. Returns a job_id immediately."""
    g = get_graph(_current_tenant())
    node = g.get(node_id)
    if not node:
        return jsonify({"error": "node not found"}), 404

    data = request.get_json(silent=True) or {}
    model = data.get("model", "deepseek/deepseek-v4.1-flash")

    job_id = uuid.uuid4().hex[:12]
    _job_set(job_id, status="queued", node_id=node_id, node_label=node.label,
             queued_at=datetime.now(timezone.utc).isoformat())
    _insights_pool.submit(_run_insights_job, job_id, node_id, model, _current_tenant())
    return jsonify({"ok": True, "job_id": job_id, "status": "queued",
                    "poll": f"/api/insights/jobs/{job_id}"}), 202


@app.route("/api/insights/jobs/<job_id>", methods=["GET"])
def api_insights_job(job_id):
    """Poll an insights job."""
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            return jsonify({"ok": False, "error": "job not found"}), 404
        snapshot = dict(job)
    status = snapshot.get("status")
    if status in ("queued", "running"):
        return jsonify({"ok": True, "job_id": job_id, "status": status}), 200
    if status == "error":
        return jsonify({"ok": False, "job_id": job_id, "status": "error",
                        "error": snapshot.get("error"), "traceback": snapshot.get("traceback")}), 500
    return jsonify({"ok": True, "job_id": job_id, "status": "completed",
                    "result": snapshot.get("result")}), 200


@app.route("/api/constraints")
def api_constraints():
    cs = get_constraints()
    return jsonify(cs.to_dict())


@app.route("/api/constraints/<node_id>")
def api_node_constraints(node_id):
    g = get_graph(_current_tenant())
    cs = get_constraints()
    constraints = cs.get_for_node(node_id, g)
    return jsonify([c.to_dict() for c in constraints])


@app.route("/api/node/<node_id>")
def api_node(node_id):
    g = get_graph(_current_tenant())
    node = g.get(node_id)
    if not node:
        return jsonify({"error": "not found"}), 404
    return jsonify(node.to_dict())


@app.route("/api/subgraph/<node_id>")
def api_subgraph(node_id):
    g = get_graph(_current_tenant())
    depth = request.args.get("depth", 2, type=int)
    subgraph = g.get_subgraph(node_id, depth=depth)
    return jsonify(subgraph)


@app.route("/api/levels")
def api_levels():
    g = get_graph(_current_tenant())
    result = {}
    for level in range(3):
        result[f"level_{level}"] = [n.to_dict() for n in g.get_level(level)]
    return jsonify(result)


# ── Multi-agent routes ─────────────────────────────────────────────────────

@app.route("/api/multiagent/plan", methods=["GET"])
def api_multiagent_plan():
    """Return the most recent optimisation plan."""
    plan = _last_plans.get(_current_tenant())
    if plan is None:
        return jsonify({"ok": False, "error": "No plan yet. POST to /api/multiagent/run first."}), 404
    return jsonify({"ok": True, "plan": plan.to_dict()})


def _run_arbiter_job(job_id, use_llm, control_model, budget, max_init, tenant_id=None):
    """Background worker: run specialists -> arbiter -> register initiatives."""
    global _last_plans
    try:
        orch = get_orchestrator(tenant_id)
        orch.config.control_model = ControlModel(control_model)
        orch.config.budget_effort = budget
        orch.config.max_initiatives = max_init
        for sp in orch.specialists:
            sp.use_llm = use_llm
        orch.arbiter.use_llm = use_llm

        g = get_graph(tenant_id)

        # Proven path (run_cycle wrapper is buggy — see run_bam.py).
        recommendations = []
        for s in orch.specialists:
            recommendations.append(s.recommend(g))

        plan = orch.arbiter.decide(g, recommendations)

        for ini in plan.initiatives:
            try:
                orch.knowledge.record_initiative(ini)
            except Exception:
                pass

        _last_plans[tenant_id or "jonco"] = plan
        _jobs[job_id] = {"status": "done", "plan": plan.to_dict(), "tenant": tenant_id}
    except Exception as e:
        import traceback
        _jobs[job_id] = {"status": "error", "error": str(e), "traceback": traceback.format_exc()}


@app.route("/api/multiagent/run", methods=["POST"])
def api_multiagent_run():
    """Start an async multi-agent optimisation cycle. Returns a job_id immediately."""
    data = request.get_json(silent=True) or {}
    use_llm = bool(data.get("use_llm", False))
    control_model = data.get("control_model", "hierarchical")
    budget = float(data.get("budget_effort", 20.0))
    max_init = int(data.get("max_initiatives", 6))

    job_id = uuid.uuid4().hex[:12]
    _jobs[job_id] = {"status": "running"}
    t = threading.Thread(
        target=_run_arbiter_job,
        args=(job_id, use_llm, control_model, budget, max_init, _current_tenant()),
        daemon=True,
    )
    t.start()
    return jsonify({"ok": True, "job_id": job_id, "status": "running"})


@app.route("/api/multiagent/job/<job_id>", methods=["GET"])
def api_multiagent_job(job_id):
    """Poll the status/result of an async arbiter job."""
    job = _jobs.get(job_id)
    if job is None:
        return jsonify({"ok": False, "error": "Unknown job_id"}), 404
    return jsonify({"ok": True, **job})


@app.route("/api/multiagent/initiatives", methods=["GET"])
def api_multiagent_initiatives():
    """List tracked initiatives. ``?status=active`` returns APPROVED + RUNNING."""
    try:
        orch = get_orchestrator()
        status = request.args.get("status")
        if status == "active":
            inis = orch.knowledge.active_initiatives(limit=50)
        else:
            inis = orch.knowledge.list_initiatives(status=status, limit=50)
        return jsonify({"ok": True, "initiatives": [i.to_dict() for i in inis]})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


def _find_initiative(initiative_id, tenant_id=None):
    """Load from the knowledge base; fall back to (and persist) the tenant's last plan."""
    if tenant_id is None:
        tenant_id = _current_tenant()
    kb = get_orchestrator(tenant_id).knowledge
    ini = kb.get_initiative(initiative_id)
    last_plan = _last_plans.get(tenant_id)
    if ini is None and last_plan is not None:
        for candidate in last_plan.initiatives:
            if candidate.id == initiative_id:
                kb.record_initiative(candidate)
                ini = kb.get_initiative(initiative_id)
                break
    return ini


def _impact_edges(g, node_ids):
    """Edges between impacted nodes, following the P&L hierarchy (parent -> child)."""
    ids = set(node_ids)
    edges = []
    for nid in ids:
        node = g.get(nid)
        if not node:
            continue
        if node.parent_group in ids:
            edges.append({"source": node.parent_group, "target": nid})
        for cid in node.children:
            if cid in ids and g.get(cid) and g.get(cid).parent_group != nid:
                edges.append({"source": nid, "target": cid})
    return edges


@app.route("/api/multiagent/initiatives/<initiative_id>", methods=["GET"])
def api_initiative_detail(initiative_id):
    """Everything the detail view needs: analysis, impacted nodes + reasoning, projection, progress history."""
    from mvp.multiagent.progress import analyse_impact
    try:
        ini = _find_initiative(initiative_id)
        if not ini:
            return jsonify({"ok": False, "error": "Initiative not found"}), 404
        g = get_graph(_current_tenant())
        node = g.get(ini.node_id)
        impact = analyse_impact(ini, g, baseline_values=ini.metadata.get("activation_snapshot"))
        ids = [i["node_id"] for i in impact["impacted"]]
        return jsonify({
            "ok": True,
            "initiative": ini.to_dict(),
            "active": ini.status.value in ("approved", "running"),
            "node": node.to_dict() if node else None,
            "analysis": {
                "description": ini.description,
                "why_now": ini.metadata.get("why_now") or "",
                "rationale": ini.metadata.get("rationale") or "",
                "effort": ini.metadata.get("effort"),
                "risk": ini.metadata.get("risk"),
                "confidence": ini.metadata.get("confidence"),
                "source": ini.metadata.get("source"),
                "validation": ini.metadata.get("validation"),
                "predictions": [p.to_dict() for p in ini.predictions],
            },
            "impact": impact,
            "graph": {"nodes": ids, "edges": _impact_edges(g, ids)},
            "progress_history": ini.metadata.get("progress_history", []),
        })
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/multiagent/initiatives/<initiative_id>/activate", methods=["POST"])
def api_activate_initiative(initiative_id):
    """Mark an initiative active (RUNNING by default, or APPROVED).

    Snapshots the impacted nodes' current values so the Progress Agent has a
    fixed baseline. Active initiatives are read by specialists and the arbiter
    on every subsequent run (see StrategyArbiter.decide).
    """
    from mvp.multiagent.hypothesis import InitiativeStatus
    from mvp.multiagent.progress import baseline_snapshot
    data = request.get_json(silent=True) or {}
    status = data.get("status", "running")
    if status not in ("running", "approved"):
        return jsonify({"ok": False, "error": "status must be 'running' or 'approved'"}), 400
    try:
        ini = _find_initiative(initiative_id)
        if not ini:
            return jsonify({"ok": False, "error": "Initiative not found"}), 404
        if ini.status == InitiativeStatus.MEASURED:
            return jsonify({"ok": False, "error": "Initiative already measured"}), 409
        updates = {}
        if not ini.metadata.get("activation_snapshot"):
            updates["activation_snapshot"] = baseline_snapshot(ini, get_graph(_current_tenant()))
        ini = get_orchestrator().knowledge.set_status(initiative_id, InitiativeStatus(status), updates)
        return jsonify({"ok": True, "initiative": ini.to_dict(), "active": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/multiagent/initiatives/<initiative_id>/deactivate", methods=["POST"])
def api_deactivate_initiative(initiative_id):
    """Toggle an active initiative back to PROPOSED (or ABANDONED with {"abandon": true})."""
    from mvp.multiagent.hypothesis import InitiativeStatus
    data = request.get_json(silent=True) or {}
    try:
        ini = _find_initiative(initiative_id)
        if not ini:
            return jsonify({"ok": False, "error": "Initiative not found"}), 404
        if ini.status not in (InitiativeStatus.APPROVED, InitiativeStatus.RUNNING):
            return jsonify({"ok": False, "error": f"Initiative is not active (status={ini.status.value})"}), 409
        new_status = InitiativeStatus.ABANDONED if data.get("abandon") else InitiativeStatus.PROPOSED
        ini = get_orchestrator().knowledge.set_status(initiative_id, new_status)
        return jsonify({"ok": True, "initiative": ini.to_dict(), "active": False})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/multiagent/initiatives/<initiative_id>/progress", methods=["POST"])
def api_initiative_progress(initiative_id):
    """Run the Progress Agent: current node values vs the time-phased projection."""
    from mvp.multiagent.progress import ProgressAgent
    try:
        ini = _find_initiative(initiative_id)
        if not ini:
            return jsonify({"ok": False, "error": "Initiative not found"}), 404
        if ini.status.value not in ("approved", "running"):
            return jsonify({"ok": False, "error": "Progress can only be checked for active initiatives"}), 409
        kb = get_orchestrator().knowledge
        report = ProgressAgent().check(ini, get_graph(_current_tenant()),
                                       constraint_store=get_constraints(),
                                       other_active=kb.active_initiatives())
        history = (ini.metadata.get("progress_history") or [])[-9:]
        history.append({k: report[k] for k in ("checked_at", "status", "achieved_benefit_gbp",
                                               "expected_benefit_now_gbp", "summary")})
        kb.update_metadata(initiative_id, {"progress_history": history})
        return jsonify({"ok": True, "report": report})
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/multiagent/initiatives/<initiative_id>/measure", methods=["POST"])
def api_measure_initiative(initiative_id):
    """Record actual outcome for an initiative."""
    data = request.get_json(silent=True) or {}
    actual = data.get("actual_impact_gbp")
    if actual is None:
        return jsonify({"ok": False, "error": "actual_impact_gbp required"}), 400
    try:
        orch = get_orchestrator()
        ini = orch.measure_initiative(
            initiative_id, float(actual),
            actual_metrics=data.get("actual_metrics"),
            notes=data.get("notes"),
        )
        if not ini:
            return jsonify({"ok": False, "error": "Initiative not found"}), 404
        return jsonify({"ok": True, "initiative": ini.to_dict()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/multiagent/calibration", methods=["GET"])
def api_multiagent_calibration():
    """Return prediction accuracy / calibration report."""
    try:
        orch = get_orchestrator()
        return jsonify({"ok": True, "report": orch.calibration_report()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/multiagent/connectors", methods=["GET"])
def api_multiagent_connectors():
    """Return connector health and capabilities."""
    try:
        reg = build_default_registry()
        return jsonify({
            "ok": True,
            "health": reg.health_report(),
            "capabilities": reg.capabilities_report(),
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/multiagent/control_models", methods=["GET"])
def api_control_models():
    """Return the control model comparison."""
    from mvp.multiagent.control_models import describe_models
    return jsonify({"ok": True, "markdown": describe_models()})


# ── Human-in-the-loop controller API ──────────────────────────────────────
# These routes expose the stateful AutonomousGraphController. The flow is:
#   POST /api/controller/diagnose  -> Gate 1 payload (branches + suggested specialists)
#   POST /api/controller/dispatch  -> Gate 2 payload (hypotheses)
#   POST /api/controller/approve   -> final approval (initiatives)
# Nothing runs without an explicit call. Thresholds decide what is OFFERED.

def get_controller():
    global _controller
    with _controller_lock:
        if _controller is None:
            orch = get_orchestrator()
            _controller = AutonomousGraphController(specialists=orch.specialists)
        return _controller


@app.route("/api/controller/diagnose", methods=["POST"])
def api_controller_diagnose():
    data = request.get_json(silent=True) or {}
    try:
        ctrl = get_controller()
        # Allow per-call threshold overrides from the UI.
        if any(k in data for k in ("change_7d_pct", "change_30d_pct", "min_abs_value_gbp")):
            th = ctrl.thresholds
            th.change_7d_pct = float(data.get("change_7d_pct", th.change_7d_pct))
            th.change_30d_pct = float(data.get("change_30d_pct", th.change_30d_pct))
            th.min_abs_value_gbp = float(data.get("min_abs_value_gbp", th.min_abs_value_gbp))
            ctrl.monitor.thresholds = th
        payload = ctrl.diagnose(get_graph(_current_tenant()))
        return jsonify(payload)
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/controller/dispatch", methods=["POST"])
def api_controller_dispatch():
    data = request.get_json(silent=True) or {}
    ids = data.get("specialist_ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"ok": False, "error": "specialist_ids must be a non-empty list"}), 400
    use_llm = bool(data.get("use_llm", False))
    try:
        payload = get_controller().dispatch(ids, get_graph(_current_tenant()), use_llm=use_llm)
        return jsonify(payload), (200 if payload.get("ok") else 409)
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/controller/approve", methods=["POST"])
def api_controller_approve():
    data = request.get_json(silent=True) or {}
    ids = data.get("hypothesis_ids") or []
    if not isinstance(ids, list) or not ids:
        return jsonify({"ok": False, "error": "hypothesis_ids must be a non-empty list"}), 400
    try:
        payload = get_controller().approve(ids)
        return jsonify(payload), (200 if payload.get("ok") else 409)
    except Exception as e:
        import traceback
        return jsonify({"ok": False, "error": str(e), "traceback": traceback.format_exc()}), 500


@app.route("/api/controller/status", methods=["GET"])
def api_controller_status():
    try:
        return jsonify({"ok": True, "status": get_controller().status()})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/controller/reset", methods=["POST"])
def api_controller_reset():
    global _controller
    with _controller_lock:
        _controller = None
    return jsonify({"ok": True, "message": "controller reset"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
