"""KPI Trees and Benchmarking.

Builds KPI trees from the transformation graph,
computes bottom-up metrics, and benchmarks against industry standards.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from collections import defaultdict
from .loader import BusinessGraph, Transaction
from .transform import TransformationGraph


@dataclass
class KPI:
    name: str
    value: float
    unit: str
    benchmark: Optional[float] = None
    benchmark_source: str = ""
    status: str = "unknown"  # "good", "ok", "poor", "unknown"
    parent: Optional[str] = None
    children: List[str] = field(default_factory=list)


class KPITree:
    """Build and navigate KPI trees for the business."""
    
    # Industry benchmarks for UK independent coffee shops (per Square/Barista Hustle data)
    # For cost metrics (labour_pct, overhead_pct, cogs_pct), lower is better.
    # For efficiency metrics, higher is better.
    BENCHMARKS = {
        "gross_margin_pct": {"target": 75.0, "good": 78.0, "poor": 65.0, "source": "Square UK Coffee Report 2024", "lower_better": False},
        "labour_pct_of_revenue": {"target": 30.0, "good": 28.0, "poor": 40.0, "source": "UK Coffee Industry Report 2024", "lower_better": True},
        "overhead_pct_of_revenue": {"target": 20.0, "good": 18.0, "poor": 28.0, "source": "UK Coffee Industry Report 2024", "lower_better": True},
        "operating_margin_pct": {"target": 10.0, "good": 15.0, "poor": 0.0, "source": "UK Coffee Industry Report 2024", "lower_better": False},
        "revenue_per_labour_hour": {"target": 25.0, "good": 30.0, "poor": 18.0, "source": "Barista Hustle UK 2024", "lower_better": False},
        "avg_transaction_value": {"target": 7.50, "good": 8.50, "poor": 5.50, "source": "Square UK Coffee Report 2024", "lower_better": False},
        "transactions_per_day": {"target": 120, "good": 150, "poor": 80, "source": "UK Coffee Industry Report 2024", "lower_better": False},
        "food_attachment_rate": {"target": 35.0, "good": 45.0, "poor": 20.0, "source": "Square UK Coffee Report 2024", "lower_better": False},
        "cogs_pct_of_revenue": {"target": 25.0, "good": 22.0, "poor": 35.0, "source": "UK Coffee Industry Report 2024", "lower_better": True},
    }
    
    def __init__(self, business: BusinessGraph, graph: TransformationGraph):
        self.business = business
        self.graph = graph
        self.kpis: Dict[str, KPI] = {}
        self._build()
    
    def _build(self):
        """Compute all KPIs from the loaded data."""
        monthly_rev = sum(pnl.revenue for pnl in self.business.monthly_pnl.values()) / 3
        monthly_cogs = sum(pnl.cogs for pnl in self.business.monthly_pnl.values()) / 3
        monthly_labour = sum(pnl.staff_costs for pnl in self.business.monthly_pnl.values()) / 3
        monthly_oh = sum(pnl.overheads for pnl in self.business.monthly_pnl.values()) / 3
        monthly_op = sum(pnl.operating_profit for pnl in self.business.monthly_pnl.values()) / 3
        
        total_txns = sum(pnl.transactions for pnl in self.business.monthly_pnl.values())
        monthly_txns = total_txns / 3
        days_per_month = 30.44
        daily_txns = monthly_txns / days_per_month
        
        # Labour hours
        total_hours = sum(p["actual_hours_worked"] for p in self.business.payroll) / 3
        
        # Revenue by category
        cat_revenue = defaultdict(float)
        for t in self.business.transactions:
            for item in t.items:
                cat_revenue[item["category"]] += item["price"]
        
        # Food attachment rate: % of transactions with at least one pastry
        food_txns = 0
        total_txn_count = len(self.business.transactions)
        for t in self.business.transactions:
            if any(item["category"] == "pastry" for item in t.items):
                food_txns += 1
        food_attachment = (food_txns / total_txn_count * 100) if total_txn_count > 0 else 0
        
        # ── Root KPI: Profitability ──
        self._add_kpi("gross_margin_pct", (monthly_rev - monthly_cogs) / monthly_rev * 100 if monthly_rev > 0 else 0, "%")
        self._add_kpi("labour_pct_of_revenue", monthly_labour / monthly_rev * 100 if monthly_rev > 0 else 0, "%")
        self._add_kpi("overhead_pct_of_revenue", monthly_oh / monthly_rev * 100 if monthly_rev > 0 else 0, "%")
        self._add_kpi("operating_margin_pct", monthly_op / monthly_rev * 100 if monthly_rev > 0 else 0, "%")
        
        # ── Efficiency KPIs ──
        self._add_kpi("revenue_per_labour_hour", monthly_rev / total_hours if total_hours > 0 else 0, "£/hour")
        self._add_kpi("revenue_per_transaction", monthly_rev / monthly_txns if monthly_txns > 0 else 0, "£")
        self._add_kpi("transactions_per_day", daily_txns, "txns/day")
        self._add_kpi("food_attachment_rate", food_attachment, "%")
        self._add_kpi("cogs_pct_of_revenue", monthly_cogs / monthly_rev * 100 if monthly_rev > 0 else 0, "%")
        
        # ── Product KPIs ──
        total_items_sold = sum(len(t.items) for t in self.business.transactions)
        for cat in ["coffee", "pastry", "hot_drink", "cold_drink"]:
            cat_rev = cat_revenue.get(cat, 0) / 3  # monthly
            cat_items = sum(1 for t in self.business.transactions for item in t.items if item["category"] == cat) / 3
            self._add_kpi(f"revenue_{cat}", cat_rev, "£/month", parent="total_revenue")
            self._add_kpi(f"volume_{cat}", cat_items, "items/month", parent="total_revenue")
            if cat_items > 0:
                self._add_kpi(f"avg_price_{cat}", cat_rev / cat_items, "£", parent=f"revenue_{cat}")
        
        # ── Staff Productivity KPIs ──
        staff_hours = defaultdict(float)
        for p in self.business.payroll:
            staff_hours[p["role"]] += p["actual_hours_worked"] / 3
        
        for role, hours in staff_hours.items():
            role_revenue = self._revenue_by_staff_role(role) / 3
            if hours > 0:
                self._add_kpi(f"revenue_per_hour_{role}", role_revenue / hours, "£/hour", parent="revenue_per_labour_hour")
        
        # ── Unit Economics ──
        self._add_kpi("contribution_margin_per_txn", 
                      (monthly_rev - monthly_cogs) / monthly_txns if monthly_txns > 0 else 0,
                      "£/txn")
        # Break-even: fixed costs / contribution margin per transaction, then convert to daily
        contrib_per_txn = (monthly_rev - monthly_cogs) / monthly_txns if monthly_txns > 0 else 0
        break_even_monthly_txns = (monthly_labour + monthly_oh) / contrib_per_txn if contrib_per_txn > 0 else 0
        break_even_daily_txns = break_even_monthly_txns / days_per_month
        self._add_kpi("break_even_daily_txns", break_even_daily_txns, "txns/day")
    
    def _revenue_by_staff_role(self, role: str) -> float:
        """Calculate total revenue generated by a specific role."""
        staff_ids = [sid for sid, s in self.business.staff.items() if s.role == role]
        return sum(t.total for t in self.business.transactions if t.staff_id in staff_ids)
    
    def _add_kpi(self, name: str, value: float, unit: str, parent: Optional[str] = None):
        """Add a KPI with benchmark comparison."""
        benchmark = self.BENCHMARKS.get(name)
        if benchmark:
            lower_better = benchmark.get("lower_better", False)
            if lower_better:
                # For cost metrics, lower is better
                if value <= benchmark["good"]:
                    status = "good"
                elif value <= benchmark["target"]:
                    status = "ok"
                elif value <= benchmark["poor"]:
                    status = "poor"
                else:
                    status = "critical"
            else:
                # For efficiency/revenue metrics, higher is better
                if value >= benchmark["good"]:
                    status = "good"
                elif value >= benchmark["target"]:
                    status = "ok"
                elif value >= benchmark["poor"]:
                    status = "poor"
                else:
                    status = "critical"
            
            kpi = KPI(
                name=name, value=value, unit=unit,
                benchmark=benchmark["target"],
                benchmark_source=benchmark["source"],
                status=status,
                parent=parent
            )
        else:
            kpi = KPI(name=name, value=value, unit=unit, status="unknown", parent=parent)
        
        self.kpis[name] = kpi
        
        if parent and parent in self.kpis:
            self.kpis[parent].children.append(name)
    
    def report(self) -> str:
        """Generate a formatted KPI report with benchmark comparisons."""
        lines = []
        lines.append(f"=== {self.business.company_name} - KPI Dashboard ===")
        lines.append(f"Period: Oct-Dec 2024 (monthly averages)")
        lines.append("")
        
        # Group by status
        for status in ["critical", "poor", "ok", "good", "unknown"]:
            status_kpis = [k for k in self.kpis.values() if k.status == status and k.benchmark is not None]
            if status_kpis:
                lines.append(f"\n── {status.upper()} ──")
                for kpi in sorted(status_kpis, key=lambda k: k.name):
                    gap = kpi.value - kpi.benchmark if kpi.benchmark else 0
                    gap_str = f"({gap:+.1f})" if gap != 0 else ""
                    lines.append(f"  {kpi.name:35s} {kpi.value:>10.1f} {kpi.unit:>8s}  benchmark: {kpi.benchmark:.1f} {gap_str}")
        
        # Unknown metrics (no benchmark)
        unknown_kpis = [k for k in self.kpis.values() if k.status == "unknown"]
        if unknown_kpis:
            lines.append(f"\n── METRICS (no benchmark) ──")
            for kpi in sorted(unknown_kpis, key=lambda k: k.name):
                lines.append(f"  {kpi.name:35s} {kpi.value:>10.2f} {kpi.unit:>8s}")
        
        return "\n".join(lines)
    
    def optimisation_opportunities(self) -> List[dict]:
        """Identify the biggest optimisation opportunities."""
        opportunities = []
        
        for name, kpi in self.kpis.items():
            if kpi.status in ["critical", "poor"] and kpi.benchmark is not None:
                gap = kpi.benchmark - kpi.value
                impact = abs(gap) * 0.1  # rough impact estimate
                opportunities.append({
                    "kpi": name,
                    "current": kpi.value,
                    "target": kpi.benchmark,
                    "gap": round(gap, 2),
                    "status": kpi.status,
                    "estimated_monthly_impact": round(impact, 2)
                })
        
        return sorted(opportunities, key=lambda x: abs(x["gap"]), reverse=True)
