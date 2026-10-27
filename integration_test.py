"""Full integration test for BAM.

Exercises every layer end-to-end against real JonCo data:
  1. Loader / flat business object
  2. TransformationGraph build + mutation
  3. Mechanism registry
  4. Projection engine (12-month P&L)
  5. Constraint gate
  6. Benchmark / reasonableness / common sense
  7. Feasibility verdict
  8. Experiment design
  9. Data gap analyzer
 10. Full run_bam pipeline (specialists -> arbiter -> initiatives)

Run: python integration_test.py
Exit code 0 = all pass.
"""

import datetime
import sys
import traceback

PASS, FAIL = [], []


def check(name, fn):
    try:
        detail = fn()
        PASS.append(name)
        print(f"  PASS  {name}" + (f" — {detail}" if detail else ""))
        return True
    except Exception as e:
        FAIL.append((name, e))
        print(f"  FAIL  {name} — {type(e).__name__}: {e}")
        traceback.print_exc(limit=2)
        return False


def main():
    print("=" * 70)
    print("BAM FULL INTEGRATION TEST")
    print("=" * 70)

    # -- 1. Loader ----------------------------------------------------------
    print("\n[1] Loader")
    from mvp.loader import load_all
    state = {}

    def _load():
        b = load_all()
        state["b"] = b
        pnls = list(b.monthly_pnl.values())
        avg = sum(p.revenue for p in pnls) / len(pnls)
        return f"{b.company_name} | avg revenue £{avg:,.0f}/mo over {len(pnls)} months"

    check("load_all returns flat business", _load)

    # -- 2. TransformationGraph + mutation ----------------------------------
    print("\n[2] TransformationGraph")
    from mvp.transform import TransformationGraph

    def _graph():
        tg = TransformationGraph(state["b"])
        state["tg"] = tg
        return f"{len(tg.nodes)} nodes, {len(tg.edges)} edges"

    check("build graph", _graph)

    def _mutate():
        snap = tg = state["tg"]
        before = tg._financial_snapshot()
        res = tg.apply_mutation("total_revenue", "value", before["total_revenue"] * 1.10)
        delta = res["delta"]["operating_profit"]
        assert "delta" in res and "before" in res and "after" in res
        return f"+10% revenue -> operating profit delta £{delta:,.0f}"

    check("apply_mutation recomputes financial flow", _mutate)

    # -- 3. Mechanisms ------------------------------------------------------
    print("\n[3] Mechanisms")
    from mvp.multiagent.mechanisms import get_mechanism

    def _mech():
        m = get_mechanism("loyalty_card")
        eff = m.apply({"revenue": 20763, "cogs": 4940, "units": 6106})
        assert eff.revenue_delta_gbp < 0
        return f"loyalty_card -> {eff.note[:70]}"

    check("loyalty_card mechanism economics", _mech)

    # -- 4. Projection ------------------------------------------------------
    print("\n[4] Projection")
    from mvp.multiagent.projection import (
        baseline_from_business, ProjectionEngine, LogisticAdoption,
    )

    def _proj():
        base = baseline_from_business(state["b"])
        m = get_mechanism("loyalty_card")
        eng = ProjectionEngine(base, volume_lift=0.12, months=12)
        res = eng.project(m, curve=LogisticAdoption(peak=0.5))
        state["proj"] = res
        return f"12mo delta operating profit £{res.delta_operating_profit:,.0f}, payback={res.payback_month}"

    check("12-month projection", _proj)

    # -- 5. Constraint gate -------------------------------------------------
    print("\n[5] Constraint gate")
    from mvp.multiagent.orchestrator import MultiAgentOrchestrator

    def _gate():
        o = MultiAgentOrchestrator(business=state["b"])
        g = o.constraint_gate(state["proj"])
        assert "allowed" in g and "hard_violations" in g
        return f"allowed={g['allowed']}, hard={len(g['hard_violations'])}"

    check("constraint_gate returns verdict", _gate)

    # -- 6. Benchmark / common sense ---------------------------------------
    print("\n[6] Benchmark layer")
    from mvp.multiagent.benchmark import ReasonablenessChecker, CommonSenseChecker

    def _bench():
        rc = ReasonablenessChecker()
        sc = rc.assess(9, "coffee")
        assert sc.verdict in ("generous", "competitive", "stingy", "poor")
        ctx = {"stamps_required": 9, "gross_margin": 0.762, "avg_spend": 3.40,
               "reward_value": 3.40, "visits_per_week": 1.0}
        results = CommonSenseChecker().check(ctx)
        return f"9+1 = {sc.verdict} ({sc.percentile:.0f}th pct); {sum(r.passed for r in results)}/{len(results)} rules pass"

    check("benchmark + common sense rules", _bench)

    # -- 7. Feasibility -----------------------------------------------------
    print("\n[7] Feasibility")
    from mvp.multiagent.feasibility import assess_loyalty_scheme

    def _feas():
        rep = assess_loyalty_scheme(state["b"], stamps_required=9, volume_lift=0.12)
        assert rep.verdict in ("GO", "CONDITIONAL", "NO-GO")
        return f"9+1 verdict={rep.verdict}, econ={'PASS' if rep.economic_pass else 'FAIL'}"

    check("feasibility verdict", _feas)

    # -- 8. Experiment design ----------------------------------------------
    print("\n[8] Experiment design")
    from mvp.multiagent.experiment import design_loyalty_experiment

    def _exp():
        d = design_loyalty_experiment("9+1", 0.18, baseline_conversion=0.35,
                                      baseline_visits_per_week=0.7)
        assert d.per_arm_customers > 0 and d.duration_weeks > 0
        return f"{d.per_arm_customers}/arm, {d.duration_weeks} weeks, {d.total_customers:,} total"

    check("A/B sample sizing", _exp)

    # -- 9. Data gap analyzer ----------------------------------------------
    print("\n[9] Data gap analyzer")
    from mvp.multiagent.data_gaps import DataGapAnalyzer

    def _gaps():
        rep = DataGapAnalyzer(business="JONCO").analyze_directory("data/jonco")
        assert rep.checked > 0
        return f"{len(rep.satisfied)} satisfied, {len(rep.gaps)} gaps ({len(rep.critical)} critical)"

    check("gap analysis on real data", _gaps)

    # -- 10. Full pipeline --------------------------------------------------
    print("\n[10] Full run_bam pipeline")
    import subprocess
    def _pipeline():
        r = subprocess.run([sys.executable, "run_bam.py", "--db", "/tmp/bam_itest.db"],
                           capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            raise RuntimeError(f"exit {r.returncode}: {r.stderr[-300:]}")
        out = r.stdout
        assert "Graph loaded" in out
        assert "Arbiter" in out or "initiatives" in out.lower()
        tail = [l for l in out.strip().splitlines() if "STATUS" in l or "initiative" in l.lower()]
        return (tail[-1][:100] if tail else "pipeline completed")

    check("end-to-end pipeline", _pipeline)

    # -- Summary ------------------------------------------------------------
    print("\n" + "=" * 70)
    total = len(PASS) + len(FAIL)
    print(f"RESULT: {len(PASS)}/{total} passed")
    if FAIL:
        print("\nFAILURES:")
        for name, e in FAIL:
            print(f"  - {name}: {e}")
        print("=" * 70)
        return 1
    print("ALL CHECKS PASSED")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    sys.exit(main())
