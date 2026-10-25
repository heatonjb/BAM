"""Run the closed-loop agent harness: deterministic baselines first, then (with
--llm) one or more LLM agents.  Writes results JSON + a human-readable table."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import defaultdict

from sim import Simulator, scenario_set
from agents import (GreedyProfitAgent, CashPreserverAgent, GraderExploitAgent,
                    RecklessExtractor, LLMAgent)


def run_agent(agent, scenarios, seeds, roll_forward=True):
    out = []
    for sname, sc in scenarios.items():
        for seed in seeds:
            sc = copy.deepcopy(sc)
            sim = Simulator(sc, seed=seed)
            for t in range(sc.periods):
                action = agent.decide(sim.observe(t))
                sim.step(t, action)
            s = sim.summary(getattr(agent, "name", "agent"))
            s["scenario"] = sname
            s["parse_failures"] = getattr(agent, "parse_failures", 0)
            if roll_forward:
                rf = sim.roll_forward(GreedyProfitAgent(), extra=3)
                s["roll_forward_ni"] = rf["roll_forward_ni"]
                s["roll_forward_equity"] = rf["roll_forward_equity"]
                # future position = terminal equity + out-of-sample equity gain
                s["future_position"] = rf["roll_forward_equity"]
            out.append(s)
    return out


def table(rows):
    hdr = ("agent", "scenario", "cumNI", "equity", "future", "cash", "debt",
           "sold", "hard", "soft", "accept")
    lines = [" | ".join(hdr), "-" * 120]
    for r in rows:
        lines.append(" | ".join(str(x) for x in (
            r["agent"], r["scenario"], r["cum_net_income"],
            r["terminal_equity"], r.get("future_position", ""), r["terminal_cash"],
            r["terminal_debt"], r["total_sold"], r["hard_violations"],
            r["soft_violations"], r["accepted_by_grader"])))
    return "\n".join(lines)


def agg(rows):
    g = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for k in ("cum_net_income", "terminal_equity", "future_position",
                  "hard_violations", "soft_violations", "total_sold",
                  "authority_violations"):
            g[r["agent"]][k].append(r[k])
    out = {}
    for a, m in g.items():
        out[a] = {k: round(sum(v) / len(v), 2) for k, v in m.items()}
        out[a]["accept_rate"] = round(
            sum(1 for r in rows if r["agent"] == a and r["accepted_by_grader"])
            / sum(1 for r in rows if r["agent"] == a), 3)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--models", default="x-ai/grok-4.7")
    ap.add_argument("--seeds", default="1,2,3")
    ap.add_argument("--out", default="results.json")
    args = ap.parse_args()

    scenarios = scenario_set()
    seeds = [int(s) for s in args.seeds.split(",")]

    agents = [GreedyProfitAgent(), CashPreserverAgent()]
    rows = []
    for a in agents:
        rows += run_agent(a, scenarios, seeds)
    # exploit agents need the scenario constants (red-team reverse-engineering)
    for sname, sc in scenarios.items():
        rows += run_agent(GraderExploitAgent(sc), {sname: sc}, seeds)
        rows += run_agent(RecklessExtractor(), {sname: sc}, seeds)

    if args.llm:
        for model in args.models.split(","):
            for persona in ("operator", "scoreboard"):
                a = LLMAgent(model, persona)
                rows += run_agent(a, {"A_benign": scenarios["A_benign"],
                                      "B_shock": scenarios["B_shock"],
                                      "C_squeeze": scenarios["C_squeeze"]}, [1])
                print(f"[llm] {a.name} parse_failures={a.parse_failures}",
                      file=sys.stderr)

    print(table(rows))
    print("\n=== per-agent means ===")
    print(json.dumps(agg(rows), indent=2))
    with open(args.out, "w") as fh:
        json.dump({"rows": rows, "agg": agg(rows)}, fh, indent=2)
    print(f"\nwrote {args.out} ({len(rows)} episodes)")


if __name__ == "__main__":
    main()
