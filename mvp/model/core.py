"""Core object model for the Business as a Machine transformation graph.

Everything in the graph extends BaseNode. Each node type adds
type-specific attributes while sharing a common interface for
rendering, traversal, and computation.
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
    AGGREGATE = "aggregate"  # composite node (sum of children)


class MetricDirection(Enum):
    HIGHER_BETTER = "higher_better"
    LOWER_BETTER = "lower_better"
    NEUTRAL = "neutral"


@dataclass
class BaseNode:
    """All graph objects extend this. Shared interface for rendering and traversal."""
    
    # Identity
    id: str
    label: str
    node_type: NodeType
    
    # Value
    value: float = 0.0
    unit: str = "GBP"
    period: str = "monthly"
    
    # Graph structure
    parents: List[str] = field(default_factory=list)   # inputs to this node
    children: List[str] = field(default_factory=list)   # outputs from this node
    
    # Analytics
    efficiency: Optional[float] = None  # output/input ratio
    efficiency_label: Optional[str] = None  # human-readable: "3.2x revenue per £1 input"
    
    # Optimisation
    constraint: Optional[str] = None  # what limits this node
    constraint_detail: Optional[str] = None
    lever: Optional[str] = None  # what can be pulled
    lever_action: Optional[str] = None  # description of the action
    
    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Hierarchy
    level: int = 0  # 0 = top-level P&L, 1 = breakdown, 2 = granular
    parent_group: Optional[str] = None  # which P&L line this rolls up to
    
    # UI
    icon: Optional[str] = None
    color: Optional[str] = None
    
    # Computed (set during graph build)
    _computed: Dict[str, Any] = field(default_factory=dict, repr=False)
    
    def summary(self) -> str:
        """Human-readable one-liner."""
        parts = [f"{self.label}: {self.value:.2f} {self.unit}"]
        if self.efficiency is not None:
            parts.append(f"({self.efficiency:.2f}x)")
        return " | ".join(parts)
    
    def to_dict(self) -> dict:
        """Serialize for JSON/UI."""
        return {
            "id": self.id,
            "label": self.label,
            "node_type": self.node_type.value,
            "value": round(self.value, 2),
            "unit": self.unit,
            "period": self.period,
            "parents": self.parents,
            "children": self.children,
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


# ── Specialised Node Types ──

@dataclass
class RevenueNode(BaseNode):
    """A revenue source — product, service, or income stream."""
    node_type: NodeType = field(default=NodeType.REVENUE, init=False)
    volume: float = 0.0  # units sold
    unit_type: str = ""  # "cups", "transactions", etc.
    price: float = 0.0   # average price per unit
    growth_rate: float = 0.0  # month-over-month
    color: str = "#4caf50"
    icon: str = "💰"


@dataclass
class CostNode(BaseNode):
    """A cost — variable, fixed, or semi-variable."""
    node_type: NodeType = field(default=NodeType.COST, init=False)
    cost_type: str = "fixed"  # fixed, variable, semi_variable
    per_unit_cost: float = 0.0  # cost per unit of output
    is_controllable: bool = True  # can management influence this?
    color: str = "#f44336"
    icon: str = "💸"


@dataclass
class ProcessNode(BaseNode):
    """A transformation step — inputs become outputs."""
    node_type: NodeType = field(default=NodeType.PROCESS, init=False)
    throughput: float = 0.0  # units processed per period
    capacity: float = 0.0  # max throughput
    utilisation: float = 0.0  # throughput/capacity
    cycle_time: float = 0.0  # time per unit
    color: str = "#2196f3"
    icon: str = "⚙️"


@dataclass
class InputNode(BaseNode):
    """A raw material or resource input."""
    node_type: NodeType = field(default=NodeType.INPUT, init=False)
    quantity: float = 0.0
    unit_measure: str = ""  # kg, litres, units
    supplier: str = ""
    lead_time_days: float = 0.0
    waste_pct: float = 0.0
    color: str = "#ff9800"
    icon: str = "📦"


@dataclass
class AssetNode(BaseNode):
    """A business asset — tangible or intangible."""
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
    """A business liability — debt, payables, etc."""
    node_type: NodeType = field(default=NodeType.LIABILITY, init=False)
    principal: float = 0.0
    interest_rate: float = 0.0
    maturity_date: str = ""
    creditor: str = ""
    color: str = "#e91e63"
    icon: str = "📋"


@dataclass
class MetricNode(BaseNode):
    """A derived metric — ratio, percentage, or KPI."""
    node_type: NodeType = field(default=NodeType.METRIC, init=False)
    formula: str = ""
    benchmark: Optional[float] = None
    benchmark_source: str = ""
    direction: MetricDirection = MetricDirection.HIGHER_BETTER
    color: str = "#9c27b0"
    icon: str = "📊"


@dataclass
class AggregateNode(BaseNode):
    """A composite node that sums its children (e.g., Total Revenue)."""
    node_type: NodeType = field(default=NodeType.AGGREGATE, init=False)
    composition: Dict[str, float] = field(default_factory=dict)  # child_id -> weight
    color: str = "#607d8b"
    icon: str = "📁"


# ── Graph Container ──

class BusinessGraph:
    """Holds all nodes and provides traversal, query, and rendering helpers."""
    
    def __init__(self):
        self.nodes: Dict[str, BaseNode] = {}
        self.edges: List[dict] = []  # {source, target, label, value}
        self.root_nodes: List[str] = []  # top-level P&L nodes
        self._adjacency: Dict[str, List[str]] = {}
        self._reverse_adj: Dict[str, List[str]] = {}
    
    def add(self, node: BaseNode):
        """Add a node to the graph."""
        self.nodes[node.id] = node
        self._adjacency[node.id] = node.children[:]
        self._reverse_adj[node.id] = node.parents[:]
        if node.level == 0:
            self.root_nodes.append(node.id)
    
    def get(self, node_id: str) -> Optional[BaseNode]:
        return self.nodes.get(node_id)
    
    def get_subgraph(self, node_id: str, depth: int = 2) -> dict:
        """Get the subgraph rooted at node_id, up to depth levels."""
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
                
                # Edges to children
                for child_id in node.children:
                    if child_id in self.nodes:
                        subgraph_edges.append({
                            "source": nid,
                            "target": child_id,
                            "label": self.nodes[child_id].label,
                            "value": self.nodes[child_id].value
                        })
                        _traverse(child_id, current_depth + 1)
                
                # Edges to parents (upstream)
                for parent_id in node.parents:
                    if parent_id in self.nodes and parent_id not in visited:
                        subgraph_edges.append({
                            "source": parent_id,
                            "target": nid,
                            "label": node.label,
                            "value": node.value
                        })
                        _traverse(parent_id, current_depth + 1)
        
        _traverse(node_id, 0)
        return {"nodes": subgraph_nodes, "edges": subgraph_edges}
    
    def get_drill_path(self, node_id: str) -> List[str]:
        """Get the path from root to this node."""
        path = []
        current = node_id
        while current:
            path.append(current)
            node = self.nodes.get(current)
            current = node.parent_group if node and node.parent_group else None
        return list(reversed(path))
    
    def get_level(self, level: int) -> List[BaseNode]:
        """Get all nodes at a given level."""
        return [n for n in self.nodes.values() if n.level == level]
    
    def get_by_type(self, node_type: NodeType) -> List[BaseNode]:
        return [n for n in self.nodes.values() if n.node_type == node_type]
    
    def to_dict(self) -> dict:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": self.edges,
            "root_nodes": self.root_nodes
        }
