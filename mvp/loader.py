"""Load all JonCo data sources into a unified business graph model."""

import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "jonco")


@dataclass
class Transaction:
    receipt_id: int
    timestamp: str
    date: str
    staff_id: str
    items: List[dict]
    total: float
    payment_method: str


@dataclass
class StaffMember:
    id: str
    name: str
    role: str
    hourly_rate: float
    contract_hours: int


@dataclass
class MonthlyPnL:
    month: str
    revenue: float
    cogs: float
    gross_profit: float
    staff_costs: float
    overheads: float
    operating_profit: float
    net_profit: float
    transactions: int


@dataclass
class BusinessGraph:
    """The core model: a business as a transformation graph."""
    
    # Identity layer
    company_name: str = ""
    company_number: str = ""
    
    # Financial layer
    monthly_pnl: Dict[str, MonthlyPnL] = field(default_factory=dict)
    balance_sheet: dict = field(default_factory=dict)
    
    # Transaction layer (bottom-up source)
    transactions: List[Transaction] = field(default_factory=list)
    
    # Staff layer
    staff: Dict[str, StaffMember] = field(default_factory=dict)
    payroll: List[dict] = field(default_factory=list)
    
    # Product layer
    menu: dict = field(default_factory=dict)
    
    # Supply chain layer
    cogs: dict = field(default_factory=dict)
    
    # Overhead layer
    overheads: dict = field(default_factory=dict)
    
    # KPIs (computed)
    kpis: dict = field(default_factory=dict)
    
    # Transformation algebra (computed)
    transformations: List[dict] = field(default_factory=list)


def load_all() -> BusinessGraph:
    """Load every data source into the unified graph."""
    g = BusinessGraph()
    
    # Company profile
    with open(os.path.join(DATA_DIR, "company_profile.json")) as f:
        profile = json.load(f)
    g.company_name = profile["company_name"]
    g.company_number = profile["company_number"]
    
    # Transactions
    with open(os.path.join(DATA_DIR, "transactions.json")) as f:
        raw_txns = json.load(f)
    g.transactions = [
        Transaction(
            receipt_id=t["receipt_id"],
            timestamp=t["timestamp"],
            date=t["date"],
            staff_id=t["staff_id"],
            items=t["items"],
            total=t["total"],
            payment_method=t["payment_method"]
        )
        for t in raw_txns
    ]
    
    # Staff
    with open(os.path.join(DATA_DIR, "staff_roster.json")) as f:
        for s in json.load(f):
            g.staff[s["id"]] = StaffMember(
                id=s["id"],
                name=s["name"],
                role=s["role"],
                hourly_rate=s["hourly_rate"],
                contract_hours=s.get("contract_hours_per_week", s.get("contract_hours", 0))
            )
    
    # Payroll
    with open(os.path.join(DATA_DIR, "payroll.json")) as f:
        g.payroll = json.load(f)
    
    # Menu
    with open(os.path.join(DATA_DIR, "menu.json")) as f:
        g.menu = json.load(f)
    
    # COGS
    with open(os.path.join(DATA_DIR, "cogs_purchases.json")) as f:
        g.cogs = json.load(f)
    
    # Overheads
    with open(os.path.join(DATA_DIR, "overheads.json")) as f:
        g.overheads = json.load(f)
    
    # Bottom-up P&L
    with open(os.path.join(DATA_DIR, "bottom_up_pl.json")) as f:
        pl_data = json.load(f)
    for month, data in pl_data["monthly"].items():
        g.monthly_pnl[month] = MonthlyPnL(
            month=month,
            revenue=data["revenue"]["total"],
            cogs=data["cost_of_goods_sold"]["total"],
            gross_profit=data["gross_profit"]["amount"],
            staff_costs=data["staff_costs"]["total_employer_cost"],
            overheads=data["overheads"]["total"],
            operating_profit=data["operating_profit"]["amount"],
            net_profit=data["net_profit"]["amount"],
            transactions=data["revenue"]["transaction_count"]
        )
    
    # Balance sheet
    with open(os.path.join(DATA_DIR, "balance_sheet.json")) as f:
        g.balance_sheet = json.load(f)
    
    return g
