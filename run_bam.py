#!/usr/bin/env python3
"""BAM production runner — bypasses the buggy run_cycle wrapper.

Runs the proven path: load graph → specialists recommend → arbiter decide →
register initiatives. Prints a human-readable plan.

Usage:
    python run_bam.py [--llm] [--control-model hierarchical|blackboard|debate|market_auction]
"""

import argparse
import sys
import time

from mvp.loader import load_graph
from mvp.multiagent import MultiAgentOrchestrator, OrchestratorConfig
from mvp.multiagent.control_models import ControlModel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="Enable LLM for specialists and arbiter")
    ap.add_argument("--control-model", default="hierarchical",
                    choices=[m.value for m in ControlModel])
    ap.add_argument("--budget", type=float, default=15.0)
    ap.add_argument("--max-initiatives", type=int, default=5)
    ap.add_argument("--db", default="/tmp/bam_run.db")
    args = ap.parse_args()

    t0 = time.time()
    g = load_graph()
    print(f"[{time.time()-t0:.2f}s] Graph loaded: {len(g.nodes)} nodes")

    t1 = time.time()
    orch = MultiAgentOrchestrator(OrchestratorConfig(
        control_model=ControlModel(args.control_model),
        budget_effort=args.budget,
        max_initiatives=args.max_initiatives,
        db_path=args.db,
    ))
    print(f"[{time.time()-t1:.2f}s] Orchestrator initialised ({args.control_model})")

    if not args.llm:
        for s in orch.specialists:
            s.use_llm = False
        orch.arbiter.use_llm = False
        print("[mode] deterministic (heuristics only)")

    t2 = time.time()
    recommendations = []
    for s in orch.specialists:
        t3 = time.time()
        rec = s.recommend(g)
        recommendations.append(rec)
        print(f"  {s.agent_id}: {len(rec['hypotheses'])} hypotheses in {time.time()-t3:.2f}s")

    t4 = time.time()
    plan = orch.arbiter.decide(g, recommendations)
    print(f"[{time.time()-t4:.2f}s] Arbiter selected {len(plan.initiatives)} initiatives")

    # Register initiatives
    for ini in plan.initiatives:
        try:
            orch.knowledge.record_initiative(ini)
        except Exception as e:
            print(f"  [warn] could not register {ini.id}: {e}")

    print()
    print("=" * 70)
    print(f"PLAN: {plan.title}")
    print("=" * 70)
    print(plan.narrative or "(deterministic — no narrative)")
    print()
    print(f"Total expected impact: £{plan.total_expected_impact_gbp:,.2f}/month")
    print(f"Total effort: {plan.total_effort:.1f} units | Budget used: {plan.budget_used_pct:.0f}%")
    print()
    print("INITIATIVES:")
    for i, ini in enumerate(plan.initiatives, 1):
        why = ini.metadata.get("why_now", "")
        print(f"  {i}. [{ini.lever_type.value}] {ini.title}")
        print(f"     Node: {ini.node_label} | Impact: £{ini.predicted_impact_gbp:,.0f}/mo")
        if why:
            print(f"     Why now: {why[:120]}")
        print()
    print(f"Rejected: {len(plan.rejected)} hypotheses (constraint violations or budget)")
    print()
    print("STATUS:", orch.status())
    print(f"Total wall time: {time.time()-t0:.2f}s")


if __name__ == "__main__":
    main()
