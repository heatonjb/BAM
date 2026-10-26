"""Core object model for the Business as a Machine transformation graph.

Everything extends BaseNode. Each node carries current value, 7-day and 30-day
rolling changes, trend direction, and sparkline data for stock-ticker display.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class NodeType(Enum):
    REVENUE = "revenue"
    COST = "cost"
    PROCESS = "process"
    INPUT = "input"
    ASSET = "asset"
    LIABILITY = "liability"
    EQUITY = "equity"
    METRIC = "metric"
    AGGREGATE = "aggregate"


class TrendDirection(Enum):
    UP = "up"
    DOWN = "down"
    FLAT = "flat"
    UNKNOWN = "unknown"


@dataclass
class BaseNode:
    """All graph objects extend this. Shared interface for rendering, traversal, and computation."""

    # Identity
    id: str
    label: str
    node_type: NodeType

    # Current value
    value: float = 0.0
    unit: str = "GBP"
    period: str = "monthly"

    # Stock-ticker change fields
    change_7d: float = 0.0          # absolute change over last 7 days vs prior 7
    change_7d_pct: float = 0.0      # percentage change
    change_30d: float = 0.0         # absolute change over last 30 days vs prior 30
    change_30d_pct: float = 0.0     # percentage change
    trend: TrendDirection = TrendDirection.UNKNOWN
    sparkline: List[float] = field(default_factory=list)  # last 30 daily values

    # Graph structure
    parents: List[str] = field(default_factory=list)
    children: List[str] = field(default_factory=list)

    # Analytics
    efficiency: Optional[float] = None
    efficiency_label: Optional[str] = None

    # Edge annotations: for each child, what % it contributes to this node
    child_contribution_pct: Dict[str, float] = field(default_factory=dict)

    # Optimisation
    constraint: Optional[str] = None
    constraint_detail: Optional[str] = None
    lever: Optional[str] = None
    lever_action: Optional[str] = None

    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Hierarchy
    level: int = 0
    parent_group: Optional[str] = None

    # UI
    icon: Optional[str] = None
    color: Optional[str] = None

    def summary(self) -> str:
        parts = [f"{self.label}: {self.value:.2f} {self.unit}"]
        if self.efficiency is not None:
            parts.append(f"({self.efficiency:.2f}x)")
        return " | ".join(parts)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "node_type": self.node_type.value,
            "value": round(self.value, 2),
            "unit": self.unit,
            "period": self.period,
            "change_7d": round(self.change_7d, 2),
            "change_7d_pct": round(self.change_7d_pct, 1),
            "change_30d": round(self.change_30d, 2),
            "change_30d_pct": round(self.change_30d_pct, 1),
            "trend": self.trend.value if isinstance(self.trend, TrendDirection) else str(self.trend),
            "sparkline": [round(v, 2) for v in self.sparkline[-30:]],
            "parents": self.parents,
            "children": self.children,
            "child_contribution_pct": {k: round(v, 1) for k, v in self.child_contribution_pct.items()},
            "efficiency": round(self.efficiency, 2) if self.efficiency is not None else None,
            "efficiency_label": self.efficiency_label,
            "constraint": self.constraint,
            "constraint_detail": self.constraint_detail,
            "lever": self.lever,
            "lever_action": self.lever_action,
            "description": self.description,
            "tags": self.tags,
            "metadata": self.metadata,
            "level": self.level,
            "parent_group": self.parent_group,
            "icon": self.icon,
            "color": self.color,
        }


@dataclass
class RevenueNode(BaseNode):
    node_type: NodeType = field(default=NodeType.REVENUE, init=False)
    volume: float = 0.0
    unit_type: str = ""
    price: float = 0.0
    growth_rate: float = 0.0
    color: str = "#4caf50"
    icon: str = "💰"


@dataclass
class CostNode(BaseNode):
    node_type: NodeType = field(default=NodeType.COST, init=False)
    cost_type: str = "fixed"
    per_unit_cost: float = 0.0
    is_controllable: bool = True
    color: str = "#f44336"
    icon: str = "💸"


@dataclass
class ProcessNode(BaseNode):
    node_type: NodeType = field(default=NodeType.PROCESS, init=False)
    throughput: float = 0.0
    capacity: float = 0.0
    utilisation: float = 0.0
    cycle_time: float = 0.0
    color: str = "#2196f3"
    icon: str = "⚙️"


@dataclass
class InputNode(BaseNode):
    node_type: NodeType = field(default=NodeType.INPUT, init=False)
    quantity: float = 0.0
    unit_measure: str = ""
    supplier: str = ""
    lead_time_days: float = 0.0
    waste_pct: float = 0.0
    color: str = "#ff9800"
    icon: str = "📦"


@dataclass
class AssetNode(BaseNode):
    node_type: NodeType = field(default=NodeType.ASSET, init=False)
    original_cost: float = 0.0
    accumulated_depreciation: float = 0.0
    net_book_value: float = 0.0
    useful_life_years: float = 0.0
    purchase_date: str = ""
    color: str = "#00bcd4"
    icon: str = "🏢"


@dataclass
class LiabilityNode(BaseNode):
    node_type: NodeType = field(default=NodeType.LIABILITY, init=False)
    principal: float = 0.0
    interest_rate: float = 0.0
    maturity_date: str = ""
    creditor: str = ""
    color: str = "#e91e63"
    icon: str = "📋"


@dataclass
class MetricNode(BaseNode):
    node_type: NodeType = field(default=NodeType.METRIC, init=False)
    formula: str = ""
    benchmark: Optional[float] = None
    benchmark_source: str = ""
    direction: str = "higher_better"
    color: str = "#9c27b0"
    icon: str = "📊"


@dataclass
class AggregateNode(BaseNode):
    node_type: NodeType = field(default=NodeType.AGGREGATE, init=False)
    composition: Dict[str, float] = field(default_factory=dict)
    color: str = "#607d8b"
    icon: str = "📁"


class BusinessGraph:
    """Holds all nodes and provides traversal, query, and rendering helpers."""

    def __init__(self):
        self.nodes: Dict[str, BaseNode] = {}
        self.edges: List[dict] = []
        self.root_nodes: List[str] = []
        self._adjacency: Dict[str, List[str]] = {}
        self._reverse_adj: Dict[str, List[str]] = {}

    def add(self, node: BaseNode):
        self.nodes[node.id] = node
        self._adjacency[node.id] = node.children[:]
        self._reverse_adj[node.id] = node.parents[:]
        if node.level == 0:
            self.root_nodes.append(node.id)

    def get(self, node_id: str) -> Optional[BaseNode]:
        return self.nodes.get(node_id)

    def get_subgraph(self, node_id: str, depth: int = 2) -> dict:
        visited = set()
        subgraph_nodes = {}
        subgraph_edges = []

        def _traverse(nid: str, current_depth: int):
            if nid in visited or current_depth > depth:
                return
            visited.add(nid)
            node = self.nodes.get(nid)
            if node:
                subgraph_nodes[nid] = node.to_dict()
                for child_id in node.children:
                    if child_id in self.nodes:
                        child = self.nodes[child_id]
                        contrib = 0
                        if node.value != 0:
                            contrib = round(abs(child.value) / abs(node.value) * 100, 1) if node.value != 0 else 0
                        subgraph_edges.append({
                            "source": nid,
                            "target": child_id,
                            "label": child.label,
                            "value": round(child.value, 2),
                            "contribution_pct": contrib,
                            "trend": child.trend.value if isinstance(child.trend, TrendDirection) else str(child.trend),
                            "change_pct": round(child.change_7d_pct, 1)
                        })
                        _traverse(child_id, current_depth + 1)
                for parent_id in node.parents:
                    if parent_id in self.nodes and parent_id not in visited:
                        subgraph_edges.append({
                            "source": parent_id,
                            "target": nid,
                            "label": node.label,
                            "value": round(node.value, 2)
                        })
                        _traverse(parent_id, current_depth + 1)

        _traverse(node_id, 0)
        return {"nodes": subgraph_nodes, "edges": subgraph_edges}

    def get_drill_path(self, node_id: str) -> List[str]:
        path = []
        current = node_id
        while current:
            path.append(current)
            node = self.nodes.get(current)
            current = node.parent_group if node and node.parent_group else None
        return list(reversed(path))

    def get_level(self, level: int) -> List[BaseNode]:
        return [n for n in self.nodes.values() if n.level == level]

    def get_by_type(self, node_type: NodeType) -> List[BaseNode]:
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def to_dict(self) -> dict:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": self.edges,
            "root_nodes": self.root_nodes
        }
