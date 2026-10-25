"""Agent Harness - Ask questions and run experiments against the business model.

This is the interface layer: an agent (human or LLM) can:
1. Query the business graph and KPI tree
2. Propose experiments ("what if we raise latte prices by 10p?")
3. See the projected impact on profit, revenue, and KPIs
"""

import json
import re
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from .loader import BusinessGraph
from .transform import TransformationGraph
from .kpi import KPITree


@dataclass
class Experiment:
    name: str
    description: str
    lever: str  # which graph node/lever this pulls
    change: dict  # {parameter: delta_or_new_value}
    projected_impact: dict
    assumptions: List[str] = field(default_factory=list)


class AgentHarness:
    """The agentic interface to the business model."""
    
    def __init__(self, business: BusinessGraph, graph: TransformationGraph, kpi_tree: KPITree):
        self.business = business
        self.graph = graph
        self.kpi_tree = kpi_tree
        self.experiments: List[Experiment] = []
    
    def query(self, question: str) -> str:
        """Answer natural language questions about the business."""
        q = question.lower().strip()
        
        # Pattern match common question types
        if any(w in q for w in ["profit", "making money", "profitable"]):
            return self._answer_profitability()
        elif any(w in q for w in ["revenue", "sales", "income", "turnover"]):
            return self._answer_revenue()
        elif any(w in q for w in ["cost", "spend", "expense"]):
            return self._answer_costs()
        elif any(w in q for w in ["staff", "labour", "employee", "wage"]):
            return self._answer_staff()
        elif any(w in q for w in ["product", "menu", "item", "coffee", "pastry"]):
            return self._answer_products()
        elif any(w in q for w in ["bench", "compare", "industry", "average"]):
            return self._answer_benchmark()
        elif any(w in q for w in ["break even", "breakeven", "break-even"]):
            return self._answer_break_even()
        elif any(w in q for w in ["optimise", "improve", "grow", "increase"]):
            return self._answer_optimisation()
        elif any(w in q for w in ["hourly", "per hour", "per labour"]):
            return self._answer_hourly_metrics()
        elif any(w in q for w in ["trend", "month", "over time"]):
            return self._answer_trends()
        else:
            return self._general_answer(q)
    
    def propose_experiment(self, name: str, description: str, params: dict) -> Experiment:
        """Propose a "what if" experiment and calculate projected impact."""
        experiment = Experiment(
            name=name,
            description=description,
            lever=params.get("lever", "unknown"),
            change={k: v for k, v in params.items() if k != "lever"},
            projected_impact={},
            assumptions=[]
        )
        
        # Calculate impact based on experiment type
        monthly_rev = sum(pnl.revenue for pnl in self.business.monthly_pnl.values()) / 3
        monthly_cogs = sum(pnl.cogs for pnl in self.business.monthly_pnl.values()) / 3
        monthly_labour = sum(pnl.staff_costs for pnl in self.business.monthly_pnl.values()) / 3
        monthly_oh = sum(pnl.overheads for pnl in self.business.monthly_pnl.values()) / 3
        current_op = monthly_rev - monthly_cogs - monthly_labour - monthly_oh
        
        impact = {"current_operating_profit": round(current_op, 2)}
        
        # Price change experiment
        if "price_change_pct" in params:
            pct = params["price_change_pct"]
            # Assume volume drops 0.5x the price increase (elasticity)
            volume_change = -pct * 0.5
            new_rev = monthly_rev * (1 + pct/100) * (1 + volume_change/100)
            new_cogs = monthly_cogs * (1 + volume_change/100)  # COGS scales with volume
            new_op = new_rev - new_cogs - monthly_labour - monthly_oh
            impact["new_revenue"] = round(new_rev, 2)
            impact["new_cogs"] = round(new_cogs, 2)
            impact["new_operating_profit"] = round(new_op, 2)
            impact["profit_delta"] = round(new_op - current_op, 2)
            experiment.assumptions.append(f"Price elasticity of -0.5 (volume drops {abs(volume_change):.1f}% for {pct:+.1f}% price change)")
        
        # Staff cost change
        elif "staff_cost_change_pct" in params:
            pct = params["staff_cost_change_pct"]
            new_labour = monthly_labour * (1 + pct/100)
            new_op = monthly_rev - monthly_cogs - new_labour - monthly_oh
            impact["new_labour_cost"] = round(new_labour, 2)
            impact["new_operating_profit"] = round(new_op, 2)
            impact["profit_delta"] = round(new_op - current_op, 2)
            experiment.assumptions.append(f"Staff costs {'reduced' if pct < 0 else 'increased'} by {abs(pct):.1f}%")
        
        # Overhead reduction
        elif "overhead_reduction_pct" in params:
            pct = params["overhead_reduction_pct"]
            new_oh = monthly_oh * (1 + pct/100)
            new_op = monthly_rev - monthly_cogs - monthly_labour - new_oh
            impact["new_overheads"] = round(new_oh, 2)
            impact["new_operating_profit"] = round(new_op, 2)
            impact["profit_delta"] = round(new_op - current_op, 2)
            experiment.assumptions.append(f"Overheads reduced by {abs(pct):.1f}%")
        
        # Volume increase
        elif "volume_increase_pct" in params:
            pct = params["volume_increase_pct"]
            new_rev = monthly_rev * (1 + pct/100)
            new_cogs = monthly_cogs * (1 + pct/100)
            # Labour might need to increase slightly for higher volume
            labour_increase = pct * 0.3  # 30% of volume increase flows to labour
            new_labour = monthly_labour * (1 + labour_increase/100)
            new_op = new_rev - new_cogs - new_labour - monthly_oh
            impact["new_revenue"] = round(new_rev, 2)
            impact["new_cogs"] = round(new_cogs, 2)
            impact["new_labour"] = round(new_labour, 2)
            impact["new_operating_profit"] = round(new_op, 2)
            impact["profit_delta"] = round(new_op - current_op, 2)
            experiment.assumptions.append(f"Volume increases {pct:.1f}%, labour scales at 30% of volume increase")
        
        # Rent negotiation
        elif "rent_reduction" in params:
            reduction = params["rent_reduction"]
            new_oh = monthly_oh - reduction
            new_op = monthly_rev - monthly_cogs - monthly_labour - new_oh
            impact["new_overheads"] = round(new_oh, 2)
            impact["new_operating_profit"] = round(new_op, 2)
            impact["profit_delta"] = round(new_op - current_op, 2)
            experiment.assumptions.append(f"Rent reduced by £{reduction:.2f}/month")
        
        # Multi-lever experiment
        elif "changes" in params:
            changes = params["changes"]
            new_rev = monthly_rev
            new_cogs = monthly_cogs
            new_labour = monthly_labour
            new_oh = monthly_oh
            
            for change in changes:
                lever = change.get("lever", "")
                value = change.get("value", 0)
                
                if "price" in lever:
                    pct = value
                    vol_change = -pct * 0.5
                    new_rev = new_rev * (1 + pct/100) * (1 + vol_change/100)
                    new_cogs = new_cogs * (1 + vol_change/100)
                    experiment.assumptions.append(f"Price {lever}: {pct:+.1f}%, volume elasticity -0.5")
                elif "staff" in lever or "labour" in lever:
                    new_labour = new_labour * (1 + value/100)
                    experiment.assumptions.append(f"Staff costs: {value:+.1f}%")
                elif "overhead" in lever or "rent" in lever:
                    new_oh = new_oh * (1 + value/100)
                    experiment.assumptions.append(f"Overheads: {value:+.1f}%")
            
            new_op = new_rev - new_cogs - new_labour - new_oh
            impact["new_revenue"] = round(new_rev, 2)
            impact["new_cogs"] = round(new_cogs, 2)
            impact["new_labour"] = round(new_labour, 2)
            impact["new_overheads"] = round(new_oh, 2)
            impact["new_operating_profit"] = round(new_op, 2)
            impact["profit_delta"] = round(new_op - current_op, 2)
        
        experiment.projected_impact = impact
        self.experiments.append(experiment)
        return experiment
    
    def list_experiments(self) -> List[Experiment]:
        """Return all proposed experiments."""
        return self.experiments
    
    # ── Answer methods ──
    
    def _answer_profitability(self) -> str:
        monthly_pnl = list(self.business.monthly_pnl.values())
        lines = []
        lines.append(f"=== Profitability Analysis ===")
        for pnl in monthly_pnl:
            lines.append(f"  {pnl.month}: Rev=£{pnl.revenue:,.2f}, Op Profit=£{pnl.operating_profit:,.2f} ({pnl.operating_profit/pnl.revenue*100:.1f}%)")
        
        avg_op = sum(p.operating_profit for p in monthly_pnl) / 3
        if avg_op > 0:
            lines.append(f"\n  Average monthly operating profit: £{avg_op:,.2f}")
            lines.append(f"  The business is barely profitable — making ~£{avg_op:,.0f}/month before tax.")
        else:
            lines.append(f"\n  Average monthly operating loss: £{avg_op:,.2f}")
            lines.append(f"  The business is losing money.")
        
        return "\n".join(lines)
    
    def _answer_revenue(self) -> str:
        monthly_pnl = list(self.business.monthly_pnl.values())
        avg_rev = sum(p.revenue for p in monthly_pnl) / 3
        avg_txn = sum(p.transactions for p in monthly_pnl) / 3
        
        # Revenue by category
        cat_rev = {}
        for t in self.business.transactions:
            for item in t.items:
                cat = item["category"]
                cat_rev[cat] = cat_rev.get(cat, 0) + item["price"]
        
        lines = []
        lines.append(f"=== Revenue Analysis ===")
        for pnl in monthly_pnl:
            lines.append(f"  {pnl.month}: £{pnl.revenue:,.2f} ({pnl.transactions} transactions, avg £{pnl.revenue/pnl.transactions:.2f}/txn)")
        
        lines.append(f"\n  Average: £{avg_rev:,.2f}/month ({avg_txn:.0f} txns/month, £{avg_rev/avg_txn:.2f}/txn)")
        lines.append(f"\n  Revenue by category (3-month total):")
        for cat, rev in sorted(cat_rev.items(), key=lambda x: -x[1]):
            pct = rev / sum(cat_rev.values()) * 100
            lines.append(f"    {cat:15s}: £{rev:>10,.2f} ({pct:.1f}%)")
        
        return "\n".join(lines)
    
    def _answer_costs(self) -> str:
        monthly_pnl = list(self.business.monthly_pnl.values())
        avg_cogs = sum(p.cogs for p in monthly_pnl) / 3
        avg_labour = sum(p.staff_costs for p in monthly_pnl) / 3
        avg_oh = sum(p.overheads for p in monthly_pnl) / 3
        
        lines = []
        lines.append(f"=== Cost Breakdown (monthly avg) ===")
        lines.append(f"  COGS:        £{avg_cogs:>10,.2f} ({avg_cogs/sum(p.revenue for p in monthly_pnl)*3/3*100:.1f}% of revenue)")
        lines.append(f"  Staff:       £{avg_labour:>10,.2f} ({avg_labour/sum(p.revenue for p in monthly_pnl)*3/3*100:.1f}% of revenue)")
        lines.append(f"  Overheads:   £{avg_oh:>10,.2f} ({avg_oh/sum(p.revenue for p in monthly_pnl)*3/3*100:.1f}% of revenue)")
        
        total = avg_cogs + avg_labour + avg_oh
        lines.append(f"\n  Biggest cost driver: {'Staff' if avg_labour > avg_cogs else 'COGS'} at {max(avg_labour, avg_cogs)/total*100:.1f}% of total costs")
        
        # Overhead detail
        lines.append(f"\n  Top overheads:")
        sorted_oh = sorted(self.business.overheads.items(), key=lambda x: -x[1])
        for name, cost in sorted_oh[:5]:
            lines.append(f"    {name:25s}: £{cost:>8,.2f}/month")
        
        return "\n".join(lines)
    
    def _answer_staff(self) -> str:
        lines = []
        lines.append(f"=== Staff Analysis ===")
        
        # Hours by role
        role_hours = {}
        role_costs = {}
        for p in self.business.payroll:
            role = p["role"]
            role_hours[role] = role_hours.get(role, 0) + p["actual_hours_worked"] / 3
            role_costs[role] = role_costs.get(role, 0) + p["total_employer_cost"] / 3
        
        for role in sorted(role_hours):
            hours = role_hours[role]
            cost = role_costs[role]
            rev_per_hour = self._revenue_for_role(role) / 3 / hours if hours > 0 else 0
            lines.append(f"  {role:20s}: {hours:>7.1f}h/month, £{cost:>8,.2f}/month, £{rev_per_hour:.2f} revenue/hour")
        
        # Staff cost as % of revenue
        total_cost = sum(role_costs.values())
        avg_rev = sum(pnl.revenue for pnl in self.business.monthly_pnl.values()) / 3
        lines.append(f"\n  Total staff cost: £{total_cost:,.2f}/month ({total_cost/avg_rev*100:.1f}% of revenue)")
        lines.append(f"  Benchmark: 30% of revenue — this is {total_cost/avg_rev*100 - 30:+.1f}pp from target")
        
        return "\n".join(lines)
    
    def _revenue_for_role(self, role: str) -> float:
        staff_ids = [sid for sid, s in self.business.staff.items() if s.role == role]
        return sum(t.total for t in self.business.transactions if t.staff_id in staff_ids)
    
    def _answer_products(self) -> str:
        # Product performance
        product_stats = {}
        for t in self.business.transactions:
            for item in t.items:
                name = item["item"]
                if name not in product_stats:
                    product_stats[name] = {"count": 0, "revenue": 0, "category": item["category"]}
                product_stats[name]["count"] += 1
                product_stats[name]["revenue"] += item["price"]
        
        lines = []
        lines.append(f"=== Product Performance (3 months) ===")
        lines.append(f"{'Item':20s} {'Count':>7s} {'Revenue':>10s} {'Avg Price':>10s} {'Category':12s}")
        lines.append("-" * 65)
        
        for name, stats in sorted(product_stats.items(), key=lambda x: -x[1]["revenue"]):
            avg_price = stats["revenue"] / stats["count"] if stats["count"] > 0 else 0
            lines.append(f"{name:20s} {stats['count']:>7,} £{stats['revenue']:>9,.2f} £{avg_price:>9.2f} {stats['category']:12s}")
        
        return "\n".join(lines)
    
    def _answer_benchmark(self) -> str:
        return self.kpi_tree.report()
    
    def _answer_break_even(self) -> str:
        monthly_rev = sum(pnl.revenue for pnl in self.business.monthly_pnl.values()) / 3
        monthly_cogs = sum(pnl.cogs for pnl in self.business.monthly_pnl.values()) / 3
        monthly_fixed = sum(pnl.staff_costs + pnl.overheads for pnl in self.business.monthly_pnl.values()) / 3
        
        contribution_margin = (monthly_rev - monthly_cogs) / monthly_rev if monthly_rev > 0 else 0
        break_even_rev = monthly_fixed / contribution_margin if contribution_margin > 0 else float('inf')
        
        avg_txn_value = monthly_rev / (sum(pnl.transactions for pnl in self.business.monthly_pnl.values()) / 3)
        break_even_txns = break_even_rev / avg_txn_value if avg_txn_value > 0 else float('inf')
        break_even_daily = break_even_txns / 30.44
        
        current_daily = (sum(pnl.transactions for pnl in self.business.monthly_pnl.values()) / 3) / 30.44
        
        lines = []
        lines.append(f"=== Break-Even Analysis ===")
        lines.append(f"  Fixed costs/month:        £{monthly_fixed:,.2f}")
        lines.append(f"  Contribution margin:      {contribution_margin*100:.1f}%")
        lines.append(f"  Break-even revenue/month: £{break_even_rev:,.2f}")
        lines.append(f"  Break-even txns/month:    {break_even_txns:.0f}")
        lines.append(f"  Break-even txns/day:      {break_even_daily:.0f}")
        lines.append(f"  Current txns/day:         {current_daily:.0f}")
        lines.append(f"  Gap:                      {break_even_daily - current_daily:+.0f} txns/day")
        
        return "\n".join(lines)
    
    def _answer_optimisation(self) -> str:
        opps = self.kpi_tree.optimisation_opportunities()
        if not opps:
            return "No optimisation opportunities found — all KPIs are at or above benchmark."
        
        lines = []
        lines.append(f"=== Top Optimisation Opportunities ===")
        for i, opp in enumerate(opps[:5], 1):
            lines.append(f"  {i}. {opp['kpi']}: {opp['current']:.1f} → target {opp['target']:.1f} (gap: {opp['gap']:+.1f})")
        
        # Suggest experiments
        lines.append(f"\n  Suggested experiments:")
        lines.append(f"  1. Raise prices 5-10% on top items (coffee has best margin)")
        lines.append(f"  2. Reduce staff costs through schedule optimisation")
        lines.append(f"  3. Increase food attachment rate (currently below benchmark)")
        lines.append(f"  4. Negotiate rent down or find cheaper premises")
        
        return "\n".join(lines)
    
    def _answer_hourly_metrics(self) -> str:
        # Revenue by hour of day
        hourly_rev = {}
        hourly_txns = {}
        for t in self.business.transactions:
            hour = int(t.timestamp.split("T")[1].split(":")[0])
            hourly_rev[hour] = hourly_rev.get(hour, 0) + t.total
            hourly_txns[hour] = hourly_txns.get(hour, 0) + 1
        
        lines = []
        lines.append(f"=== Hourly Metrics (3-month total) ===")
        lines.append(f"{'Hour':>4s} {'Transactions':>14s} {'Revenue':>12s} {'Avg Txn':>10s} {'% of Daily':>12s}")
        lines.append("-" * 60)
        
        total_rev = sum(hourly_rev.values())
        for hour in sorted(hourly_rev):
            rev = hourly_rev[hour]
            txns = hourly_txns[hour]
            avg = rev / txns if txns > 0 else 0
            pct = rev / total_rev * 100 if total_rev > 0 else 0
            lines.append(f"  {hour:02d}:00  {txns:>14,}  £{rev:>10,.2f}  £{avg:>9.2f}  {pct:>11.1f}%")
        
        return "\n".join(lines)
    
    def _answer_trends(self) -> str:
        monthly_pnl = list(self.business.monthly_pnl.values())
        lines = []
        lines.append(f"=== Monthly Trends ===")
        lines.append(f"{'Month':8s} {'Revenue':>12s} {'COGS':>10s} {'Staff':>10s} {'Overheads':>10s} {'Op Profit':>12s} {'Margin':>8s}")
        lines.append("-" * 75)
        
        for pnl in monthly_pnl:
            margin = pnl.operating_profit / pnl.revenue * 100 if pnl.revenue > 0 else 0
            lines.append(f"{pnl.month:8s} £{pnl.revenue:>11,.2f} £{pnl.cogs:>9,.2f} £{pnl.staff_costs:>9,.2f} £{pnl.overheads:>9,.2f} £{pnl.operating_profit:>11,.2f} {margin:>7.1f}%")
        
        # Month-over-month changes
        if len(monthly_pnl) >= 2:
            lines.append(f"\n  Month-over-month revenue change:")
            for i in range(1, len(monthly_pnl)):
                prev = monthly_pnl[i-1]
                curr = monthly_pnl[i]
                change = (curr.revenue - prev.revenue) / prev.revenue * 100
                lines.append(f"    {prev.month} → {curr.month}: {change:+.1f}%")
        
        return "\n".join(lines)
    
    def _general_answer(self, q: str) -> str:
        """Fallback for unmatched questions."""
        # Try to extract numbers or keywords
        return f"I can answer questions about: profitability, revenue, costs, staff, products, benchmarks, break-even, optimisation, hourly patterns, and trends. Try asking something like \"How profitable is the business?\" or \"What are our biggest costs?\""
