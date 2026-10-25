#!/usr/bin/env python3
"""Business as a Machine MVP — JonCo Coffee.

Usage:
  python -m mvp              # Run full pipeline + interactive prompt
  python -m mvp --query "question"  # One-shot query
  python -m mvp --experiment "name" --params '{...}'  # Run experiment
  python -m mvp --kpi        # Show KPI dashboard
  python -m mvp --graph      # Show transformation graph
  python -m mvp --all        # Run everything
"""

import sys
import json
import argparse
from .loader import load_all
from .transform import TransformationGraph
from .kpi import KPITree
from .agent import AgentHarness


def run_full_pipeline():
    """Load data, build graph, compute KPIs, return harness."""
    print("Loading business data...")
    business = load_all()
    
    print(f"Building transformation graph for {business.company_name}...")
    graph = TransformationGraph(business)
    
    print("Computing KPIs and benchmarks...")
    kpi_tree = KPITree(business, graph)
    
    print("Initialising agent harness...")
    harness = AgentHarness(business, graph, kpi_tree)
    
    return business, graph, kpi_tree, harness


def interactive_mode(harness):
    """Run interactive query loop."""
    print(f"\n{'='*60}")
    print(f"  Business as a Machine — Interactive Query Mode")
    print(f"  Company: {harness.business.company_name}")
    print(f"{'='*60}")
    print(f"\nTry asking:")
    print(f"  - How profitable is the business?")
    print(f"  - What are our biggest costs?")
    print(f"  - Show me the KPI dashboard")
    print(f"  - What products sell best?")
    print(f"  - What's our break-even point?")
    print(f"  - How can we optimise?")
    print(f"  - Show hourly patterns")
    print(f"  - Show monthly trends")
    print(f"  - Benchmarks vs industry")
    print(f"\nOr propose experiments:")
    print(f"  - experiment: raise_prices_5pct, lever: price, value: 5")
    print(f"  - experiment: cut_staff_10pct, lever: staff_cost_change_pct, value: -10")
    print(f"  - experiment: increase_volume_20pct, lever: volume_increase_pct, value: 20")
    print(f"\nType 'quit' to exit.\n")
    
    while True:
        try:
            question = input(f"$ ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break
        
        if not question:
            continue
        if question.lower() in ["quit", "exit", "q"]:
            print("Goodbye!")
            break
        
        # Check if it's an experiment
        if question.lower().startswith("experiment:"):
            parts = question.split(",")
            name = parts[0].replace("experiment:", "").strip()
            params = {}
            for part in parts[1:]:
                key, value = part.split(":")
                params[key.strip()] = float(value.strip())
            
            exp = harness.propose_experiment(name=name, description=name, params=params)
            print(f"\n  Experiment: {exp.name}")
            print(f"  Impact:")
            for k, v in exp.projected_impact.items():
                print(f"    {k}: £{v:,.2f}")
            print(f"  Assumptions:")
            for a in exp.assumptions:
                print(f"    - {a}")
            print()
            continue
        
        # Regular query
        answer = harness.query(question)
        print(f"\n{answer}\n")


def main():
    parser = argparse.ArgumentParser(description="Business as a Machine MVP")
    parser.add_argument("--query", type=str, help="One-shot query question")
    parser.add_argument("--kpi", action="store_true", help="Show KPI dashboard")
    parser.add_argument("--graph", action="store_true", help="Show transformation graph")
    parser.add_argument("--experiment", type=str, help="Experiment name")
    parser.add_argument("--params", type=str, help="Experiment params as JSON")
    parser.add_argument("--all", action="store_true", help="Run full pipeline with all outputs")
    parser.add_argument("--interactive", action="store_true", help="Run in interactive mode")
    
    args = parser.parse_args()
    
    # Load everything
    business, graph, kpi_tree, harness = run_full_pipeline()
    
    if args.all:
        print(f"\n{'='*60}")
        print(f"  TRANSFORMATION GRAPH")
        print(f"{'='*60}")
        print(graph.summary())
        
        print(f"\n{'='*60}")
        print(f"  KPI DASHBOARD")
        print(f"{'='*60}")
        print(kpi_tree.report())
        
        print(f"\n{'='*60}")
        print(f"  OPTIMISATION OPPORTUNITIES")
        print(f"{'='*60}")
        for i, opp in enumerate(kpi_tree.optimisation_opportunities()[:5], 1):
            print(f"  {i}. {opp['kpi']}: {opp['current']:.1f} → {opp['target']:.1f} (gap: {opp['gap']:+.1f})")
        
        print(f"\n{'='*60}")
        print(f"  SAMPLE EXPERIMENTS")
        print(f"{'='*60}")
        
        # Run some sample experiments
        experiments = [
            {"name": "raise_prices_5pct", "lever": "price_change_pct", "value": 5},
            {"name": "raise_prices_10pct", "lever": "price_change_pct", "value": 10},
            {"name": "cut_staff_10pct", "lever": "staff_cost_change_pct", "value": -10},
            {"name": "increase_volume_20pct", "lever": "volume_increase_pct", "value": 20},
            {"name": "negotiate_rent_10pct", "lever": "rent_reduction", "value": 220},
        ]
        
        for exp_params in experiments:
            exp = harness.propose_experiment(
                name=exp_params["name"],
                description=exp_params["name"],
                params={exp_params["lever"]: exp_params["value"]}
            )
            print(f"\n  ── {exp.name} ──")
            for k, v in exp.projected_impact.items():
                print(f"    {k}: £{v:,.2f}")
        
        print(f"\n{'='*60}")
        print(f"  COMPLETE")
        print(f"{'='*60}")
        return
    
    if args.kpi:
        print(kpi_tree.report())
        return
    
    if args.graph:
        print(graph.summary())
        return
    
    if args.query:
        print(harness.query(args.query))
        return
    
    if args.experiment:
        params = json.loads(args.params) if args.params else {}
        exp = harness.propose_experiment(name=args.experiment, description=args.experiment, params=params)
        print(f"Experiment: {exp.name}")
        for k, v in exp.projected_impact.items():
            print(f"  {k}: £{v:,.2f}")
        return
    
    # Default: interactive mode
    interactive_mode(harness)


if __name__ == "__main__":
    main()
