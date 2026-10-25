"""Transformation Algebra Engine.

Models the business as a graph of asset transformations:
  Raw Materials -> Finished Goods -> Sales Revenue -> Operating Expenses -> Profit

Each node is an asset/liability/cost pool. Each edge is a transformation
with associated efficiency metrics, constraints, and optimisation levers.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from .loader import BusinessGraph, Transaction


@dataclass
class GraphNode:
    """A node in the business transformation graph."""
    node_id: str
    node_type: str  # 'input', 'process', 'output', 'cost', 'revenue', 'asset', 'liability'
    label: str
    value: float  # monetary value for the period
    unit: str = "GBP"
    description: str = ""
    parents: List[str] = field(default_factory=list)  # inputs to this node
    children: List[str] = field(default_factory=list)  # outputs from this node
    efficiency: Optional[float] = None  # output/input ratio
    constraint: Optional[str] = None  # what limits this node
    lever: Optional[str] = None  # what can be pulled to optimise


@dataclass
class TransformationEdge:
    """An edge between nodes representing a transformation."""
    source: str
    target: str
    transformation_type: str  # 'purchase', 'process', 'sell', 'allocate'
    efficiency: float  # output value / input value
    volume: float  # physical quantity
    unit: str
    description: str


class TransformationGraph:
    """The core transformation graph of the business."""
    
    def __init__(self, business: BusinessGraph):
        self.business = business
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[TransformationEdge] = []
        self._build()
    
    def _build(self):
        """Construct the full transformation graph from loaded data."""
        self._build_supply_chain()
        self._build_labour()
        self._build_overheads()
        self._build_financial_flow()
        self._compute_efficiencies()
    
    def _build_supply_chain(self):
        """Build the ingredient -> product -> sale chain."""
        # Input nodes: raw materials
        raw_materials = [
            ("coffee_beans", "input", "Coffee Beans", self._monthly_avg_cogs("coffee_beans")),
            ("milk", "input", "Milk (whole+oat+almond)", self._monthly_avg_cogs("milk")),
            ("pastries", "input", "Pastries (all types)", self._monthly_avg_cogs("pastries")),
            ("packaging", "input", "Packaging (cups, lids, napkins)", self._monthly_avg_cogs("packaging")),
            ("consumables", "input", "Consumables (sugar, tea, chocolate)", self._monthly_avg_cogs("consumables")),
        ]
        
        for node_id, ntype, label, value in raw_materials:
            self.nodes[node_id] = GraphNode(
                node_id=node_id, node_type=ntype, label=label, value=value,
                description=f"Monthly avg spend on {label.lower()}"
            )
        
        # Process nodes: barista transforms raw materials into products
        products = [
            ("coffee_products", "process", "Coffee Products", self._monthly_revenue("coffee")),
            ("pastry_products", "process", "Pastry Products", self._monthly_revenue("pastry")),
            ("hot_drinks", "process", "Hot Drinks (non-coffee)", self._monthly_revenue("hot_drink")),
            ("cold_drinks", "process", "Cold Drinks", self._monthly_revenue("cold_drink")),
        ]
        
        for node_id, ntype, label, value in products:
            self.nodes[node_id] = GraphNode(
                node_id=node_id, node_type=ntype, label=label, value=value,
                parents=self._get_input_parents_for_product(node_id),
                constraint="barista_capacity",
                lever=f"price_{node_id}"
            )
        
        # Revenue nodes
        self.nodes["total_revenue"] = GraphNode(
            node_id="total_revenue", node_type="revenue", label="Total Revenue",
            value=self._total_monthly_revenue(),
            parents=["coffee_products", "pastry_products", "hot_drinks", "cold_drinks"]
        )
    
    def _build_labour(self):
        """Build labour cost nodes."""
        total_monthly_labour = sum(p["total_employer_cost"] for p in self.business.payroll) / 3
        
        # Group by role
        roles = defaultdict(float)
        for p in self.business.payroll:
            roles[p["role"]] += p["total_employer_cost"]
        
        for role, cost in roles.items():
            monthly_cost = cost / 3
            self.nodes[f"labour_{role}"] = GraphNode(
                node_id=f"labour_{role}", node_type="cost",
                label=f"Labour: {role.replace('_', ' ').title()}",
                value=monthly_cost, unit="GBP/month",
                parents=["total_revenue"],
                constraint=f"{role}_productivity",
                lever=f"optimise_{role}_schedule"
            )
        
        self.nodes["total_labour"] = GraphNode(
            node_id="total_labour", node_type="cost",
            label="Total Labour Cost", value=total_monthly_labour,
            unit="GBP/month",
            parents=[f"labour_{r}" for r in roles.keys()]
        )
    
    def _build_overheads(self):
        """Build overhead cost nodes."""
        total_monthly_oh = sum(v["amount"] for v in self.business.overheads.values())
        
        # Group into categories
        categories = {
            "premises": ["rent", "business_rates", "utilities_electric", "utilities_water", "utilities_gas"],
            "operations": ["insurance", "waste_collection", "cleaning", "equipment_maintenance", "water_filters"],
            "technology": ["internet", "pos_software", "phone"],
            "professional": ["accountant", "bank_charges"],
            "marketing": ["marketing", "music_licence"],
            "depreciation": ["depreciation"],
            "supplies": [k for k in self.business.overheads if k not in [
                "rent", "business_rates", "utilities_electric", "utilities_water", "utilities_gas",
                "insurance", "waste_collection", "cleaning", "equipment_maintenance", "water_filters",
                "internet", "pos_software", "phone", "accountant", "bank_charges",
                "marketing", "music_licence", "depreciation"
            ]]
        }
        
        for cat, items in categories.items():
            if not items:
                continue
            monthly_cost = sum(self.business.overheads.get(k, {}).get("amount", 0) for k in items)
            self.nodes[f"overhead_{cat}"] = GraphNode(
                node_id=f"overhead_{cat}", node_type="cost",
                label=f"Overhead: {cat.title()}",
                value=monthly_cost, unit="GBP/month",
                parents=["total_revenue"],
                lever=f"reduce_{cat}"
            )
        
        self.nodes["total_overheads"] = GraphNode(
            node_id="total_overheads", node_type="cost",
            label="Total Overheads", value=total_monthly_oh,
            unit="GBP/month",
            parents=[f"overhead_{c}" for c in categories if categories[c]]
        )
    
    def _build_financial_flow(self):
        """Connect everything to profit."""
        monthly_rev = self._total_monthly_revenue()
        monthly_cogs = self._total_monthly_cogs()
        monthly_labour = self.nodes["total_labour"].value
        monthly_oh = self.nodes["total_overheads"].value
        
        self.nodes["gross_profit"] = GraphNode(
            node_id="gross_profit", node_type="output",
            label="Gross Profit", value=monthly_rev - monthly_cogs,
            unit="GBP/month",
            parents=["total_revenue", "coffee_beans", "milk", "pastries", "packaging", "consumables"],
            efficiency=(monthly_rev - monthly_cogs) / monthly_rev if monthly_rev > 0 else 0
        )
        
        self.nodes["operating_profit"] = GraphNode(
            node_id="operating_profit", node_type="output",
            label="Operating Profit", 
            value=monthly_rev - monthly_cogs - monthly_labour - monthly_oh,
            unit="GBP/month",
            parents=["gross_profit", "total_labour", "total_overheads"],
            efficiency=(monthly_rev - monthly_cogs - monthly_labour - monthly_oh) / monthly_rev if monthly_rev > 0 else 0,
            constraint="break_even_volume",
            lever="optimise_all"
        )
    
    def _compute_efficiencies(self):
        """Calculate efficiency metrics for each transformation."""
        monthly_rev = self._total_monthly_revenue()
        
        # Revenue per labour hour
        total_hours = sum(p["actual_hours_worked"] for p in self.business.payroll) / 3
        self.nodes["total_labour"].efficiency = monthly_rev / total_hours if total_hours > 0 else 0
        
        # Revenue per pound of labour
        monthly_labour = self.nodes["total_labour"].value
        if monthly_labour > 0:
            self.nodes["total_labour"].efficiency = monthly_rev / monthly_labour
        
        # COGS efficiency by product
        for product in ["coffee_products", "pastry_products", "hot_drinks", "cold_drinks"]:
            if product in self.nodes and self.nodes[product].value > 0:
                input_cost = sum(self.nodes[p].value for p in self.nodes[product].parents if p in self.nodes)
                if input_cost > 0:
                    self.nodes[product].efficiency = self.nodes[product].value / input_cost
    
    # Helper methods
    def _monthly_avg_cogs(self, category: str) -> float:
        """Get average monthly COGS for a category."""
        totals = {"2024-10": 0, "2024-11": 0, "2024-12": 0}
        
        for month, items in self.business.cogs.items():
            if month.startswith("_"):
                continue
            for key, item in items.items():
                if isinstance(item, dict) and "total" in item:
                    if category == "coffee_beans" and "coffee" in key and "beans" in key and "filter" not in key:
                        totals[month] += item["total"]
                    elif category == "milk" and "milk" in key:
                        totals[month] += item["total"]
                    elif category == "pastries" and "pastries" in key:
                        totals[month] += item["total"]
                    elif category == "packaging" and key in ["cups_8oz", "cups_12oz", "lids_8oz", "lids_12oz", "napkins", "stirrers"]:
                        totals[month] += item["total"]
                    elif category == "consumables" and key in ["chocolate_powder", "chai_concentrate", "tea_bags", "sugar_sachets", "smoothie_ingredients"]:
                        totals[month] += item["total"]
        
        return sum(totals.values()) / 3
    
    def _total_monthly_cogs(self) -> float:
        """Get average monthly COGS total."""
        return sum(v["_month_total"] for v in self.business.cogs.values()) / 3
    
    def _monthly_revenue(self, category: str) -> float:
        """Get average monthly revenue for a category."""
        total = 0
        for month, pnl in self.business.monthly_pnl.items():
            # Calculate from transactions
            cat_revenue = 0
            for t in self.business.transactions:
                if t.date.startswith(month):
                    for item in t.items:
                        if item.get("category") == category:
                            cat_revenue += item["price"]
            total += cat_revenue
        return total / 3
    
    def _total_monthly_revenue(self) -> float:
        """Get average monthly revenue."""
        return sum(pnl.revenue for pnl in self.business.monthly_pnl.values()) / 3
    
    def _get_input_parents_for_product(self, product_id: str) -> List[str]:
        """Get which raw material inputs feed into a product."""
        mapping = {
            "coffee_products": ["coffee_beans", "milk", "packaging"],
            "pastry_products": ["pastries"],
            "hot_drinks": ["coffee_beans", "milk", "consumables", "packaging"],
            "cold_drinks": ["milk", "consumables", "packaging"],
        }
        return mapping.get(product_id, [])
    
    def get_critical_path(self) -> List[str]:
        """Find the path from inputs to profit with lowest efficiency."""
        # Simple approach: find nodes with lowest efficiency
        inefficient = []
        for node_id, node in self.nodes.items():
            if node.efficiency is not None and node.efficiency < 2.0:
                inefficient.append((node_id, node.efficiency, node.label))
        
        return sorted(inefficient, key=lambda x: x[1])
    
    def summary(self) -> str:
        """Human-readable summary of the transformation graph."""
        lines = []
        lines.append(f"=== {self.business.company_name} - Transformation Graph ===")
        lines.append(f"Nodes: {len(self.nodes)}")
        lines.append(f"Company: {self.business.company_number}")
        lines.append("")
        
        monthly_rev = self._total_monthly_revenue()
        lines.append(f"Monthly Revenue: £{monthly_rev:,.2f}")
        
        if "gross_profit" in self.nodes:
            gp = self.nodes["gross_profit"]
            lines.append(f"Gross Profit: £{gp.value:,.2f} ({gp.efficiency*100:.1f}%)")
        
        if "operating_profit" in self.nodes:
            op = self.nodes["operating_profit"]
            lines.append(f"Operating Profit: £{op.value:,.2f} ({op.efficiency*100:.1f}%)")
        
        lines.append("")
        lines.append("Critical Path (lowest efficiency first):")
        for node_id, eff, label in self.get_critical_path():
            lines.append(f"  {label}: {eff:.2f}x")
        
        return "\n".join(lines)
