"""Integration test for initiative drill-down, activation, agent awareness and progress.

Drives the Flask app through its test client against a temporary SQLite DB, so
the real data/initiatives.db is untouched. Arbiter runs deterministically
(use_llm=False).

Run: python initiative_tracking_test.py
Exit code 0 = all pass.
"""

import os
import sys
import tempfile
import time
import traceback
from datetime import datetime, timedelta, timezone

from integration_test import check, PASS, FAIL  # reuse the harness

import mvp.ui.app as webapp
from mvp.multiagent import MultiAgentOrchestrator, OrchestratorConfig


def main():
    db = os.path.join(tempfile.mkdtemp(prefix="bam_test_"), "initiatives.db")
    # Orchestrators are now per-tenant via mvp.tenancy.registry; there is no
    # module-level _orchestrator to monkeypatch.
    from mvp.tenancy import registry
    registry._orchestrators["jonco"] = MultiAgentOrchestrator(OrchestratorConfig(db_path=db))
    registry._orchestrators["jonco"].constraint_store = webapp.get_constraints("jonco")
    client = webapp.app.test_client()
    state = {}

    print("=" * 70)
    print("BAM initiative tracking test")
    print("=" * 70)

    def index_renders():
        r = client.get("/")
        assert r.status_code == 200, r.status_code
        html = r.get_data(as_text=True)
        assert "Run Arbiter" in html and "initiativePanel" in html
        return "index 200, detail panel present"

    def run_arbiter(key):
        r = client.post("/api/multiagent/run", json={"use_llm": False, "max_initiatives": 5, "budget_effort": 15})
        job_id = r.get_json()["job_id"]
        for _ in range(120):
            job = client.get(f"/api/multiagent/job/{job_id}").get_json()
            if job["status"] != "running":
                break
            time.sleep(0.5)
        assert job["status"] == "done", job
        state[key] = job["plan"]
        assert client.get("/api/multiagent/plan").status_code == 200
        return f"{len(job['plan']['initiatives'])} initiatives"

    def detail():
        ini = state["plan1"]["initiatives"][0]
        state["ini"] = ini
        d = client.get(f"/api/multiagent/initiatives/{ini['id']}").get_json()
        assert d["ok"] and not d["active"], d
        roles = {i["role"] for i in d["impact"]["impacted"]}
        assert "target" in roles and "outcome" in roles, roles
        assert all(len(i["projection"]) == 6 for i in d["impact"]["impacted"])
        assert all(i["reasoning"] for i in d["impact"]["impacted"])
        assert d["graph"]["edges"], "expected edges between impacted nodes"
        assert d["analysis"]["effort"] is not None
        return f"{len(d['impact']['impacted'])} impacted nodes, {len(d['graph']['edges'])} edges"

    def progress_requires_active():
        r = client.post(f"/api/multiagent/initiatives/{state['ini']['id']}/progress")
        assert r.status_code == 409, r.status_code

    def activate():
        r = client.post(f"/api/multiagent/initiatives/{state['ini']['id']}/activate", json={})
        d = r.get_json()
        assert d["ok"] and d["initiative"]["status"] == "running", d
        assert d["initiative"]["metadata"]["activation_snapshot"]
        active = client.get("/api/multiagent/initiatives?status=active").get_json()["initiatives"]
        assert [i["id"] for i in active] == [state["ini"]["id"]]
        return "status=running, snapshot stored"

    def arbiter_respects_active():
        plan = state["plan2"]
        assert all(i["title"] != state["ini"]["title"] for i in plan["initiatives"]), "duplicate re-proposed"
        meta = plan["metadata"]
        assert [a["id"] for a in meta["active_initiatives"]] == [state["ini"]["id"]]
        assert meta["effort_reserved_for_active"] > 0
        return f"duplicate excluded, effort reserved={meta['effort_reserved_for_active']}"

    def progress():
        kb = webapp._orchestrator.knowledge
        ini = kb.get_initiative(state["ini"]["id"])
        # Backdate so the ramp expects something by now.
        ini.started_at = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        kb.record_initiative(ini)
        d = client.post(f"/api/multiagent/initiatives/{ini.id}/progress").get_json()
        rep = d["report"]
        assert rep["status"] in ("on_track", "behind", "ahead")
        assert rep["expected_benefit_now_gbp"] > 0 and rep["nodes"] and rep["summary"]
        hist = client.get(f"/api/multiagent/initiatives/{ini.id}").get_json()["progress_history"]
        assert len(hist) == 1
        return f"{rep['status']} — {len(rep['deviations'])} deviations, {len(rep['blockers'])} blockers"

    def deactivate():
        d = client.post(f"/api/multiagent/initiatives/{state['ini']['id']}/deactivate").get_json()
        assert d["ok"] and d["initiative"]["status"] == "proposed"
        assert client.get("/api/multiagent/initiatives?status=active").get_json()["initiatives"] == []

    def existing_routes():
        for path in ("/api/subgraph/pnl_revenue", "/api/node/pnl_revenue", "/api/multiagent/initiatives",
                     "/drill/pnl_revenue"):
            assert client.get(path).status_code == 200, path
        r = client.post(f"/api/multiagent/initiatives/{state['ini']['id']}/measure", json={"actual_impact_gbp": 100})
        assert r.get_json()["initiative"]["status"] == "measured"
        assert client.post(f"/api/multiagent/initiatives/{state['ini']['id']}/activate").status_code == 409

    check("index renders", index_renders)
    check("arbiter run (cycle 1)", lambda: run_arbiter("plan1"))
    check("initiative detail", detail)
    check("progress rejects inactive", progress_requires_active)
    check("activate initiative", activate)
    check("arbiter run (cycle 2)", lambda: run_arbiter("plan2"))
    check("arbiter respects active", arbiter_respects_active)
    check("progress agent", progress)
    check("deactivate toggle", deactivate)
    check("existing routes + measure", existing_routes)

    print("=" * 70)
    print(f"RESULT: {len(PASS)}/{len(PASS) + len(FAIL)} passed")
    return 0 if not FAIL else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        traceback.print_exc()
        sys.exit(1)
