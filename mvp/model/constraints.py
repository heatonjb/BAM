"""Constraint modelling system for the Business as a Machine graph.

Constraints can be attached at any level:
  - Global: applies to every node in the graph
  - Category: applies to a node and all its descendants
  - Node-specific: applies only to a single node

Each constraint has:
  - type: capacity, temporal, legal, ethical, physical, seasonal, quality
  - severity: hard (cannot be violated) or soft (can be violated at a cost)
  - description: human-readable explanation
  - parameters: constraint-specific key-value pairs
  - applicable_to: list of node IDs this constraint applies to (empty = all)
  - inherited: whether child nodes inherit this constraint
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum


class ConstraintType(Enum):
    CAPACITY = "capacity"       # max hours, max throughput, max volume
    TEMPORAL = "temporal"       # operating hours, day-of-week, seasonal
    LEGAL = "legal"             # employment law, food safety, licensing
    ETHICAL = "ethical"         # fair wages, sourcing standards, brand values
    PHYSICAL = "physical"       # equipment limits, space constraints
    SEASONAL = "seasonal"       # product availability, demand patterns
    QUALITY = "quality"         # freshness, use-by dates, waste thresholds
    FINANCIAL = "financial"     # budget caps, cashflow limits


class ConstraintSeverity(Enum):
    HARD = "hard"  # cannot be violated — produces infeasible solution
    SOFT = "soft"  # can be violated but incurs a penalty cost


@dataclass
class Constraint:
    """A single constraint that limits the feasible solution space."""
    
    id: str
    name: str
    constraint_type: ConstraintType
    severity: ConstraintSeverity
    description: str
    
    # Scope
    applicable_to: List[str] = field(default_factory=list)  # node IDs (empty = global/all)
    inherited: bool = True  # whether children inherit this constraint
    
    # Parameters — constraint-specific
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # Penalty (for soft constraints) — cost per unit of violation
    penalty_per_unit: float = 0.0
    penalty_unit: str = "GBP"
    
    # Metadata
    source: str = ""  # where this constraint comes from (e.g., "UK Employment Law")
    tags: List[str] = field(default_factory=list)
    
    def applies_to(self, node_id: str) -> bool:
        """Check if this constraint applies to a given node."""
        if not self.applicable_to:
            return True  # global constraint
        return node_id in self.applicable_to
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.constraint_type.value,
            "severity": self.severity.value,
            "description": self.description,
            "applicable_to": self.applicable_to,
            "inherited": self.inherited,
            "parameters": self.parameters,
            "penalty_per_unit": self.penalty_per_unit,
            "penalty_unit": self.penalty_unit,
            "source": self.source,
            "tags": self.tags,
        }


class ConstraintStore:
    """Manages all constraints and provides efficient lookup."""
    
    def __init__(self):
        self.constraints: Dict[str, Constraint] = {}
        # Cache: node_id -> list of constraint IDs that apply
        self._node_cache: Dict[str, List[str]] = {}
        self._cache_valid = False
    
    def add(self, constraint: Constraint):
        self.constraints[constraint.id] = constraint
        self._cache_valid = False
    
    def get(self, constraint_id: str) -> Optional[Constraint]:
        return self.constraints.get(constraint_id)
    
    def get_for_node(self, node_id: str, graph=None) -> List[Constraint]:
        """Get all constraints that apply to a node, including inherited ones."""
        if not self._cache_valid:
            self._rebuild_cache(graph)
        constraint_ids = self._node_cache.get(node_id, [])
        return [self.constraints[cid] for cid in constraint_ids if cid in self.constraints]
    
    def get_by_type(self, constraint_type: ConstraintType) -> List[Constraint]:
        return [c for c in self.constraints.values() if c.constraint_type == constraint_type]
    
    def get_hard_constraints(self) -> List[Constraint]:
        return [c for c in self.constraints.values() if c.severity == ConstraintSeverity.HARD]
    
    def get_soft_constraints(self) -> List[Constraint]:
        return [c for c in self.constraints.values() if c.severity == ConstraintSeverity.SOFT]
    
    def _rebuild_cache(self, graph=None):
        """Rebuild the node -> constraints cache."""
        self._node_cache = {}
        
        for cid, constraint in self.constraints.items():
            if not constraint.applicable_to:
                # Global constraint — applies to all nodes
                if graph:
                    for nid in graph.nodes:
                        self._node_cache.setdefault(nid, []).append(cid)
                # If no graph, we'll resolve at query time
            else:
                for nid in constraint.applicable_to:
                    self._node_cache.setdefault(nid, []).append(cid)
                    # Inherit to children if graph is available
                    if constraint.inherited and graph:
                        self._inherit_to_children(nid, cid, graph)
        
        self._cache_valid = True
    
    def _inherit_to_children(self, node_id: str, constraint_id: str, graph):
        """Recursively inherit a constraint to all descendants."""
        node = graph.get(node_id)
        if not node:
            return
        for child_id in node.children:
            self._node_cache.setdefault(child_id, []).append(constraint_id)
            self._inherit_to_children(child_id, constraint_id, graph)
    
    def to_dict(self) -> dict:
        return {cid: c.to_dict() for cid, c in self.constraints.items()}
    
    def summary(self) -> str:
        lines = [f"Constraint Store: {len(self.constraints)} constraints"]
        by_type = {}
        for c in self.constraints.values():
            by_type.setdefault(c.constraint_type.value, []).append(c)
        for ctype, constraints in sorted(by_type.items()):
            hard = sum(1 for c in constraints if c.severity == ConstraintSeverity.HARD)
            soft = len(constraints) - hard
            lines.append(f"  {ctype}: {len(constraints)} ({hard} hard, {soft} soft)")
        return "\n".join(lines)


# ── Pre-built constraint templates for a UK coffee shop ──

def build_default_constraints() -> List[Constraint]:
    """Build the default constraint set for JonCo Coffee."""
    return [
        # ── CAPACITY constraints ──
        Constraint(
            id="cap_staff_hours_weekly",
            name="Weekly Staff Hours Cap",
            constraint_type=ConstraintType.CAPACITY,
            severity=ConstraintSeverity.HARD,
            description="No staff member may work more than 48 hours per week (UK Working Time Regulations 1998, with opt-out). Default without opt-out: 48h/week averaged over 17 weeks.",
            applicable_to=["pnl_staff", "staff_barista", "staff_shift_supervisor", "staff_manager", "staff_s001", "staff_s002", "staff_s003", "staff_s004", "staff_s005"],
            inherited=True,
            parameters={"max_hours_per_week": 48, "reference_period_weeks": 17},
            source="UK Working Time Regulations 1998",
            tags=["employment_law", "staff", "capacity"]
        ),
        Constraint(
            id="cap_staff_daily",
            name="Daily Rest Period",
            constraint_type=ConstraintType.CAPACITY,
            severity=ConstraintSeverity.HARD,
            description="Workers are entitled to 11 consecutive hours rest in each 24-hour period. Effectively caps daily working time.",
            applicable_to=["pnl_staff", "staff_barista", "staff_shift_supervisor", "staff_manager", "staff_s001", "staff_s002", "staff_s003", "staff_s004", "staff_s005"],
            inherited=True,
            parameters={"min_rest_hours": 11, "max_hours_per_day": 13},
            source="UK Working Time Regulations 1998",
            tags=["employment_law", "staff", "capacity"]
        ),
        Constraint(
            id="cap_espresso_throughput",
            name="Espresso Machine Throughput",
            constraint_type=ConstraintType.CAPACITY,
            severity=ConstraintSeverity.HARD,
            description="La Marzocco Linea PB: max ~120 shots/hour sustained (2 groups). Beyond this, quality degrades and machine overheats.",
            applicable_to=["prod_latte", "prod_cappuccino", "prod_flat_white", "prod_americano", "prod_mocha", "prod_espresso"],
            inherited=False,
            parameters={"max_shots_per_hour": 120, "machine": "La Marzocco Linea PB 2-group"},
            source="Equipment specification",
            tags=["equipment", "capacity", "quality"]
        ),
        Constraint(
            id="cap_shop_capacity",
            name="Shop Seating Capacity",
            constraint_type=ConstraintType.CAPACITY,
            severity=ConstraintSeverity.SOFT,
            description="Shop has ~20 seats. Beyond this, customers queue outside or leave. Each additional customer beyond capacity has 60% chance of abandoning.",
            applicable_to=["pnl_revenue", "rev_coffee", "rev_pastry", "rev_hot_drink", "rev_cold_drink"],
            inherited=False,
            parameters={"max_seated_customers": 20, "abandonment_rate": 0.6},
            source="Premises assessment",
            tags=["premises", "capacity"],
            penalty_per_unit=5.0,  # lost revenue per abandoned customer
            penalty_unit="GBP/customer"
        ),

        # ── TEMPORAL constraints ──
        Constraint(
            id="temp_operating_hours",
            name="Operating Hours",
            constraint_type=ConstraintType.TEMPORAL,
            severity=ConstraintSeverity.HARD,
            description="Shop opens 06:00-20:00 Mon-Sat, 07:00-18:00 Sun. No revenue can be generated outside these hours.",
            applicable_to=["pnl_revenue", "rev_coffee", "rev_pastry", "rev_hot_drink", "rev_cold_drink"],
            inherited=False,
            parameters={
                "weekday_open": "06:00", "weekday_close": "20:00",
                "sunday_open": "07:00", "sunday_close": "18:00",
                "hours_per_weekday": 14, "hours_per_sunday": 11
            },
            source="Business policy",
            tags=["temporal", "operating_hours"]
        ),
        Constraint(
            id="temp_closed_days",
            name="Christmas & Bank Holiday Closures",
            constraint_type=ConstraintType.TEMPORAL,
            severity=ConstraintSeverity.HARD,
            description="Shop closed on Christmas Day, Boxing Day, New Year's Day, Easter Monday, Early May, Spring, Summer, and Late Summer bank holidays. ~8 days/year with zero revenue.",
            applicable_to=["pnl_revenue"],
            inherited=False,
            parameters={"closed_days_per_year": 8, "fixed_dates": ["2024-12-25", "2024-12-26", "2025-01-01"]},
            source="UK bank holidays + business policy",
            tags=["temporal", "closures"]
        ),

        # ── LEGAL constraints ──
        Constraint(
            id="legal_national_wage",
            name="National Living Wage (NLW)",
            constraint_type=ConstraintType.LEGAL,
            severity=ConstraintSeverity.HARD,
            description="All staff aged 21+ must be paid at least the National Living Wage. From April 2024: £11.44/hour. All current staff are above this threshold.",
            applicable_to=["pnl_staff", "staff_barista", "staff_shift_supervisor", "staff_manager", "staff_s001", "staff_s002", "staff_s003", "staff_s004", "staff_s005"],
            inherited=True,
            parameters={"nlw_rate": 11.44, "effective_from": "2024-04-01", "age_threshold": 21},
            source="UK Government — National Minimum Wage rates 2024",
            tags=["employment_law", "wages", "staff"]
        ),
        Constraint(
            id="legal_food_hygiene",
            name="Food Hygiene & Safety Regulations",
            constraint_type=ConstraintType.LEGAL,
            severity=ConstraintSeverity.HARD,
            description="Food Safety Act 1990 and EU Regulation 852/2004. Requires temperature logs, allergen info, HACCP plan. Non-compliance risks closure.",
            applicable_to=["pnl_cogs", "cog_pastries", "cog_milk", "cog_consumables"],
            inherited=False,
            parameters={"regulation": "EU 852/2004", "requires_haccp": True, "allergen_labelling": True},
            source="Food Standards Agency / EU Regulation 852/2004",
            tags=["food_safety", "legal", "compliance"]
        ),
        Constraint(
            id="legal_premises_licence",
            name="Premises Use Class E",
            constraint_type=ConstraintType.LEGAL,
            severity=ConstraintSeverity.HARD,
            description="Class E (commercial, business and service) allows cafe/restaurant use. Cannot operate outside permitted hours (typically 06:00-23:00) without variation.",
            applicable_to=["pnl_overheads", "oh_premises", "oh_rates", "oh_utilities", "oh_rent"],
            inherited=False,
            parameters={"use_class": "E", "max_operating_hours": "06:00-23:00"},
            source="Town and Country Planning (Use Classes) Order 1987 (as amended)",
            tags=["planning", "legal", "premises"]
        ),

        # ── ETHICAL constraints ──
        Constraint(
            id="eth_real_living_wage",
            name="Real Living Wage Commitment",
            constraint_type=ConstraintType.ETHICAL,
            severity=ConstraintSeverity.SOFT,
            description="Voluntary commitment to pay the Real Living Wage (£12.00/hour London, £11.00 rest of UK as of 2024). Breach damages brand reputation.",
            applicable_to=["pnl_staff", "staff_barista", "staff_shift_supervisor", "staff_manager"],
            inherited=True,
            parameters={"rlw_rate_rest_of_uk": 11.00, "rlw_rate_london": 12.00, "location": "West Sussex"},
            source="Living Wage Foundation",
            tags=["ethical", "wages", "brand"],
            penalty_per_unit=500.0,  # brand damage cost per month below RLW
            penalty_unit="GBP/month"
        ),
        Constraint(
            id="eth_ethical_sourcing",
            name="Ethical Coffee Sourcing",
            constraint_type=ConstraintType.ETHICAL,
            severity=ConstraintSeverity.SOFT,
            description="Brand commitment to ethically sourced beans (Fairtrade or direct trade). Switching to cheaper non-ethical suppliers damages brand and customer loyalty.",
            applicable_to=["cog_beans", "bean_wholesale"],
            inherited=False,
            parameters={"certification": "Fairtrade or direct trade", "min_price_per_kg": 18.00},
            source="Brand values / customer expectations",
            tags=["ethical", "sourcing", "brand"],
            penalty_per_unit=1000.0,
            penalty_unit="GBP/month"
        ),

        # ── SEASONAL constraints ──
        Constraint(
            id="season_cold_drink_demand",
            name="Cold Drink Seasonality",
            constraint_type=ConstraintType.SEASONAL,
            severity=ConstraintSeverity.SOFT,
            description="Cold drinks (iced latte, smoothies) see 60-80% demand reduction Oct-Mar. Cannot sustain year-round cold drink volume at summer levels.",
            applicable_to=["rev_cold_drink", "prod_iced_latte", "prod_smoothie"],
            inherited=False,
            parameters={"winter_demand_multiplier": 0.3, "summer_demand_multiplier": 1.8, "transition_months": ["Apr", "May", "Sep", "Oct"]},
            source="Historical sales data / industry benchmarks",
            tags=["seasonal", "demand", "products"]
        ),
        Constraint(
            id="season_pastry_supply",
            name="Pastry Supply Seasonality",
            constraint_type=ConstraintType.SEASONAL,
            severity=ConstraintSeverity.SOFT,
            description="Some pastry items (e.g., seasonal specials) only available certain months. Bakers Delight reduces supply of certain items during low-demand periods.",
            applicable_to=["cog_pastries", "rev_pastry"],
            inherited=False,
            parameters={"low_supply_months": ["Jan", "Feb"]},
            source="Supplier agreement with Bakers Delight",
            tags=["seasonal", "supply"]
        ),

        # ── QUALITY constraints ──
        Constraint(
            id="qual_milk_freshness",
            name="Milk Freshness & Use-By",
            constraint_type=ConstraintType.QUALITY,
            severity=ConstraintSeverity.HARD,
            description="Fresh milk has 7-day shelf life from delivery. Milk past use-by must be discarded. Oat milk: 14-day shelf life once opened.",
            applicable_to=["pnl_cogs", "cog_milk", "milk_whole_buy", "milk_oat_buy", "milk_almond_buy"],
            inherited=False,
            parameters={"milk_shelf_life_days": 7, "oat_milk_opened_days": 14, "waste_threshold_pct": 5.0},
            source="Food Safety / Supplier specifications",
            tags=["quality", "waste", "food_safety"]
        ),
        Constraint(
            id="qual_pastry_freshness",
            name="Pastry Day-Fresh Policy",
            constraint_type=ConstraintType.QUALITY,
            severity=ConstraintSeverity.HARD,
            description="Pastries must be sold same day as delivery. Unsold pastries at close are discarded or donated. Waste target: <5% of pastry spend.",
            applicable_to=["cog_pastries", "rev_pastry"],
            inherited=False,
            parameters={"max_age_hours": 12, "waste_target_pct": 5.0, "donation_allowed": True},
            source="Brand quality standards / Food Safety",
            tags=["quality", "waste", "food_safety"]
        ),
        Constraint(
            id="qual_espresso_quality",
            name="Espresso Quality Degradation",
            constraint_type=ConstraintType.QUALITY,
            severity=ConstraintSeverity.SOFT,
            description="Coffee beans peak 7-21 days post-roast. Quality degrades after 28 days. Using beans >28 days old risks customer satisfaction decline.",
            applicable_to=["cog_beans", "bean_wholesale", "prod_latte", "prod_cappuccino", "prod_flat_white"],
            inherited=False,
            parameters={"peak_days_min": 7, "peak_days_max": 21, "degradation_days": 28},
            source="Specialty Coffee Association guidelines",
            tags=["quality", "coffee"],
            penalty_per_unit=200.0,
            penalty_unit="GBP/month"
        ),

        # ── FINANCIAL constraints ──
        Constraint(
            id="fin_cashflow_minimum",
            name="Minimum Cash Reserve",
            constraint_type=ConstraintType.FINANCIAL,
            severity=ConstraintSeverity.HARD,
            description="Business must maintain minimum £5,000 cash reserve for operational continuity. Below this, supplier payments and staff wages at risk.",
            applicable_to=["pnl_revenue", "pnl_gross_profit", "pnl_operating_profit"],
            inherited=False,
            parameters={"min_cash_reserve": 5000.0, "currency": "GBP"},
            source="Financial prudence / bank covenant",
            tags=["financial", "cashflow"]
        ),
        Constraint(
            id="fin_marketing_budget",
            name="Marketing Budget Cap",
            constraint_type=ConstraintType.FINANCIAL,
            severity=ConstraintSeverity.SOFT,
            description="Marketing spend capped at 3% of revenue. Exceeding this requires director approval and justification.",
            applicable_to=["oh_marketing", "oh_marketing_ads"],
            inherited=False,
            parameters={"max_pct_of_revenue": 3.0},
            source="Business policy",
            tags=["financial", "budget"],
            penalty_per_unit=1.0,  # £1 penalty per £1 over budget
            penalty_unit="GBP"
        ),
    ]
