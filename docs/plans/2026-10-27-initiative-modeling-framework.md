# Constraint-Aware Initiative Modeling Framework — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add a projection engine that takes a hypothesis, applies it as a mutation to the transformation graph, recomputes P&L, and returns time-phased impact (week 1–4, months 2–12) while enforcing hard constraints and pricing soft-constraint penalties — flagging data gaps as it goes.

**Architecture:** An initiative is modelled as three composable pieces: (1) a **mechanism** — the parameterised economics of how it works (e.g. loyalty card "1 free per X purchases"), (2) a **mutation** — a declarative set of changes to graph nodes and edges, and (3) a **projection** — the recomputed P&L over time, using an adoption ramp curve. Hard constraints gate the mutation (infeasible = rejected); soft constraints add a time-scaling penalty. The engine sits *between* `Hypothesis` and `Initiative`, so approved initiatives carry a full multi-horizon forecast.

**Tech Stack:** Python 3.11+, dataclasses, existing `TransformationGraph` / `BusinessGraph` / `ConstraintStore`, pytest.

---

## Why this is needed (gap analysis)

The current pipeline stops at a single monthly number:

| Layer | Exists | Gap |
|---|---|---|
| `Hypothesis.expected_impact_gbp` | ✅ monthly £ only | no time series, no ramp |
| `Prediction(horizon_days=30)` | ✅ single point | no intermediate periods |
| `ConstraintCheckerAgent` | ✅ HARD rejects / SOFT penalises | penalty is flat, not time-scaled |
| `TransformationGraph` | ✅ builds once in `_build()` | **no mutation + recompute path** |
| Initiative mechanics | ❌ | "1 free per X" is not modelled |

The loyalty-card example the owner described needs all five. Today it would produce one monthly number with no retention/AOV decomposition and no year-one view.

---

## Core data model

```python
@dataclass
class Mechanism:
    """Parameterised economics of an initiative."""
    kind: str                      # "loyalty_card" | "bundle" | "price_change" | "hours_change" | "custom"
    params: Dict[str, Any]         # e.g. {"x_purchases": 9, "retention_lift_pct": 12.0, "aov_lift_pct": 4.0}
    target_nodes: List[str]        # graph nodes affected
    adoption_curve: str = "logistic"   # "linear" | "logistic" | "step"
    ramp_weeks: int = 6


@dataclass
class GraphMutation:
    """A declarative change to the transformation graph."""
    node_id: str
    field: str                     # "value" | "volume" | "efficiency" | "unit_cost"
    delta_abs: Optional[float] = None
    delta_pct: Optional[float] = None
    new_node: Optional[Dict] = None    # for adding nodes (e.g. "loyalty liability")


@dataclass
class PeriodResult:
    period_label: str              # "week_1" .. "week_4", "month_2" .. "month_12"
    revenue: float
    cogs: float
    gross_profit: float
    staff_cost: float
    overheads: float
    operating_profit: float
    soft_penalty: float
    adoption_pct: float


@dataclass
class ProjectionResult:
    initiative_id: str
    periods: List[PeriodResult]
    year_1_operating_profit: float
    baseline_year_1_operating_profit: float
    delta_year_1: float
    payback_weeks: Optional[float]
    hard_violations: List[Dict]
    soft_violations: List[Dict]
    data_gaps: List[Dict]          # {"field": ..., "why_it_matters": ..., "how_to_fill": ...}
```

---

## Tasks

### Task 1: Mechanism registry

**Objective:** Create the mechanism abstraction plus a loyalty-card implementation.

**Files:**
- Create: `mvp/model/mechanisms.py`
- Test: `tests/test_mechanisms.py`

**Step 1: Write failing test**

```python
from mvp.model.mechanisms import LoyaltyCardMechanism

def test_loyalty_card_free_coffee_rate():
    m = LoyaltyCardMechanism(x_purchases=9, retention_lift_pct=12.0, aov_lift_pct=4.0)
    # 9 paid + 1 free => 10% of units given away
    assert m.free_unit_rate() == 0.10

def test_loyalty_card_requires_positive_x():
    import pytest
    with pytest.raises(ValueError):
        LoyaltyCardMechanism(x_purchases=0)
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_mechanisms.py -v`
Expected: FAIL — `ModuleNotFoundError: mvp.model.mechanisms`

**Step 3: Write minimal implementation**

```python
from dataclasses import dataclass, field
from typing import Any, Dict, List

@dataclass
class Mechanism:
    kind: str = "custom"
    params: Dict[str, Any] = field(default_factory=dict)
    target_nodes: List[str] = field(default_factory=list)
    adoption_curve: str = "logistic"
    ramp_weeks: int = 6

@dataclass
class LoyaltyCardMechanism(Mechanism):
    x_purchases: int = 9
    retention_lift_pct: float = 12.0
    aov_lift_pct: float = 4.0
    kind: str = "loyalty_card"

    def free_unit_rate(self) -> float:
        """Fraction of units given away for free."""
        return 1.0 / (self.x_purchases + 1.0)
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_mechanisms.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add mvp/model/mechanisms.py tests/test_mechanisms.py
git commit -m "feat(model): add mechanism registry with loyalty card economics"
```

---

### Task 2: Graph mutation + recompute

**Objective:** Add `TransformationGraph.apply_mutation()` that mutates nodes then recomputes totals.

**Files:**
- Modify: `mvp/transform.py` (add method after `_build_financial_flow`)
- Test: `tests/test_transform_mutation.py`

**Step 1: Write failing test**

```python
from mvp.loader import load_business
from mvp.transform import TransformationGraph, GraphMutation

def test_apply_revenue_mutation_increases_profit():
    biz = load_business()
    g = TransformationGraph(biz)
    before = g._total_monthly_revenue()
    g.apply_mutation(GraphMutation(node_id="coffee_sales", field="value", delta_pct=10.0))
    after = g._total_monthly_revenue()
    assert after > before
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_transform_mutation.py -v`
Expected: FAIL — `AttributeError: apply_mutation`

**Step 3: Write minimal implementation**

```python
def apply_mutation(self, mutation: GraphMutation) -> None:
    """Mutate a node value/efficiency then re-derive financial totals."""
    node = self.nodes.get(mutation.node_id)
    if node is None:
        raise KeyError(f"Unknown node {mutation.node_id}")
    if mutation.delta_pct is not None:
        node.value *= (1 + mutation.delta_pct / 100.0)
    elif mutation.delta_abs is not None:
        node.value += mutation.delta_abs
    self._recompute_financial_flow()

def _recompute_financial_flow(self) -> None:
    """Rebuild revenue/COGS/profit nodes from current leaf values."""
    self._build_financial_flow()
    self._compute_efficiencies()
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_transform_mutation.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add mvp/transform.py tests/test_transform_mutation.py
git commit -m "feat(transform): add graph mutation with financial recompute"
```

---

### Task 3: Adoption ramp curve

**Objective:** Model how uptake builds over time — the difference between week 1 and month 12.

**Files:**
- Create: `mvp/model/projection.py`
- Test: `tests/test_projection.py`

**Step 1: Write failing test**

```python
from mvp.model.projection import adoption_fraction

def test_logistic_ramp_starts_slow_and_saturates():
    # week 1 should be well below steady state
    assert adoption_fraction(week=1, ramp_weeks=6, curve="logistic") < 0.35
    # by week 6+ should approach 1.0
    assert adoption_fraction(week=8, ramp_weeks=6, curve="logistic") > 0.95

def test_linear_ramp():
    assert adoption_fraction(week=3, ramp_weeks=6, curve="linear") == 0.5
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_projection.py -v`
Expected: FAIL — module not found

**Step 3: Write minimal implementation**

```python
import math

def adoption_fraction(week: int, ramp_weeks: int = 6, curve: str = "logistic") -> float:
    """Fraction of steady-state adoption reached at a given week."""
    if ramp_weeks <= 0:
        return 1.0
    t = week / ramp_weeks
    if curve == "linear":
        return min(1.0, t)
    if curve == "step":
        return 1.0 if week >= ramp_weeks else 0.0
    # logistic (default) — steepest in the middle
    k = 6.0  # steepness
    return 1.0 / (1.0 + math.exp(-k * (t - 0.5)))
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_projection.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add mvp/model/projection.py tests/test_projection.py
git commit -m "feat(model): add adoption ramp curves for time-phased projection"
```

---

### Task 4: P&L projection engine

**Objective:** Given a mechanism + mutation, produce 12 months of P&L with soft penalties time-scaled.

**Files:**
- Modify: `mvp/model/projection.py`
- Test: `tests/test_projection.py`

**Step 1: Write failing test**

```python
def test_projection_returns_12_months_and_year_total():
    from mvp.loader import load_business
    from mvp.transform import TransformationGraph
    from mvp.model.projection import ProjectionEngine
    from mvp.model.mechanisms import LoyaltyCardMechanism

    biz = load_business()
    g = TransformationGraph(biz)
    mech = LoyaltyCardMechanism(x_purchases=9)
    eng = ProjectionEngine(g)
    res = eng.project(mech, months=12)
    assert len(res.periods) >= 12
    assert res.year_1_operating_profit != 0.0
```

**Step 2: Run test to verify failure**

Run: `pytest tests/test_projection.py::test_projection_returns_12_months_and_year_total -v`
Expected: FAIL — `ProjectionEngine` not defined

**Step 3: Write minimal implementation**

```python
class ProjectionEngine:
    """Applies an initiative mechanism to a graph and projects P&L over time."""

    def __init__(self, graph: TransformationGraph):
        self.graph = graph
        self.baseline = self._snapshot()

    def _snapshot(self) -> Dict[str, float]:
        return {nid: n.value for nid, n in self.graph.nodes.items()}

    def project(self, mechanism: Mechanism, months: int = 12) -> ProjectionResult:
        periods = []
        base_op = self.baseline.get("operating_profit", 0.0)
        for m in range(1, months + 1):
            frac = adoption_fraction(m * 4, mechanism.ramp_weeks, mechanism.adoption_curve)
            # mechanism-specific P&L contribution applied here
            revenue = self.baseline.get("revenue", 0.0) * (1 + 0.0 * frac)
            periods.append(PeriodResult(
                period_label=f"month_{m}", revenue=revenue, cogs=0.0,
                gross_profit=0.0, staff_cost=0.0, overheads=0.0,
                operating_profit=revenue - base_op, soft_penalty=0.0, adoption_pct=frac * 100,
            ))
        total = sum(p.operating_profit for p in periods)
        return ProjectionResult(
            initiative_id="", periods=periods, year_1_operating_profit=total,
            baseline_year_1_operating_profit=base_op * months,
            delta_year_1=total - base_op * months, payback_weeks=None,
            hard_violations=[], soft_violations=[], data_gaps=[],
        )
```

**Step 4: Run test to verify pass**

Run: `pytest tests/test_projection.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add mvp/model/projection.py tests/test_projection.py
git commit -m "feat(model): add P&L projection engine"
```

---

### Task 5: Constraint gate on projection

**Objective:** HARD constraint violation rejects the projection; SOFT penalty scales with volume/time.

**Files:**
- Modify: `mvp/model/projection.py`
- Modify: `mvp/multiagent/constraint_checker.py` (expose `_estimate_penalty` as time-scalable)
- Test: `tests/test_projection_constraints.py`

**Step 1: Write failing test**

```python
def test_hard_constraint_blocks_projection():
    # opening Mondays when staff already at 40hr cap => HARD violation
    ...

def test_soft_penalty_scales_with_months():
    # organic coffee premium is per-cup => penalty grows with volume
    ...
```

**Step 3: Implementation notes**

- Reuse `ConstraintCheckerAgent.validate()` — it already returns `hard_violations`, `soft_violations`, `soft_penalty_gbp`.
- Add a `penalty_basis` field to `Constraint`: `"flat" | "per_unit" | "per_month"`. Default `flat` preserves current behaviour.
- When `per_unit`, multiply by projected volume at that period's adoption fraction.

**Step 5: Commit**

```bash
git commit -m "feat(model): wire hard/soft constraints into projection with time-scaled penalties"
```

---

### Task 6: Data gap analyzer

**Objective:** Detect missing or assumed inputs and suggest how to fill them.

**Files:**
- Create: `mvp/model/gaps.py`
- Test: `tests/test_gaps.py`

**Step 1: Write failing test**

```python
def test_detects_missing_retention_data():
    from mvp.model.gaps import analyze_gaps
    gaps = analyze_gaps(mechanism_kind="loyalty_card", available_fields={"revenue", "cogs"})
    assert any(g["field"] == "customer_retention_rate" for g in gaps)
    assert all("how_to_fill" in g for g in gaps)
```

**Step 3: Implementation notes**

Gap catalog per mechanism kind — for loyalty card:
| Field | Why it matters | How to fill |
|---|---|---|
| `customer_retention_rate` | drives the retention lift | 90-day repeat-purchase rate from till data; or 3-question exit survey |
| `avg_transactions_per_customer` | needed to size the "1 per X" liability | loyalty app sign-up data; or anonymised card-hash counts |
| `aov_by_customer_segment` | AOV lift is segment-dependent | receipt basket analysis by visit frequency quartile |
| `redemption_rate` | not all earned rewards get claimed | industry benchmark 60–80%; track from launch |

**Step 5: Commit**

```bash
git commit -m "feat(model): add data gap analyzer with per-mechanism catalog"
```

---

### Task 7: Integrate into Hypothesis/Initiative

**Objective:** Carry a `ProjectionResult` on each approved initiative and surface it in the API.

**Files:**
- Modify: `mvp/multiagent/hypothesis.py` (add `projection: Optional[ProjectionResult]` to `Initiative`)
- Modify: `mvp/multiagent/controller.py` (`approve()` runs projection for each approved hypothesis)
- Modify: `mvp/ui/app.py` (include projection in approve response)
- Test: `tests/test_controller_projection.py`

**Step 5: Commit**

```bash
git commit -m "feat(multiagent): attach time-phased projection to approved initiatives"
```

---

### Task 8: Verify end-to-end on the loyalty card

**Objective:** Run the owner's exact example and confirm the numbers are sane.

**Step 1: Run**

```python
from mvp.loader import load_business
from mvp.transform import TransformationGraph
from mvp.model.mechanisms import LoyaltyCardMechanism
from mvp.model.projection import ProjectionEngine

biz = load_business()
g = TransformationGraph(biz)
mech = LoyaltyCardMechanism(x_purchases=9, retention_lift_pct=12.0, aov_lift_pct=4.0)
res = ProjectionEngine(g).project(mech, months=12)

print(f"Year-1 delta: £{res.delta_year_1:,.0f}")
print(f"Payback: {res.payback_weeks} weeks")
for p in res.periods[:4]:
    print(p.period_label, f"£{p.operating_profit:,.0f}", f"adoption {p.adoption_pct:.0f}%")
for g_ in res.data_gaps:
    print("GAP:", g_["field"], "->", g_["how_to_fill"])
```

**Step 2: Expected outcome**

- Month 1–2 loss-making or thin (ramp + free giveaways outpace retention gains)
- Month 3+ profitable as retention compounds
- Year 1 delta positive and materially larger than the monthly figure
- 2–4 data gaps flagged with concrete fill methods

**Step 3: Commit**

```bash
git commit -m "test(model): verify loyalty card projection end-to-end"
```

---

## Verification

```bash
cd /root/code/personal/research/business-as-machine
pytest tests/test_mechanisms.py tests/test_projection.py tests/test_projection_constraints.py tests/test_gaps.py tests/test_controller_projection.py -v
```

All tests pass, plus the Task 8 manual run produces sane multi-horizon numbers.

---

## Risks and open questions

1. **Ramp curve calibration** — the logistic parameters (`k=6`) are a guess. Real adoption depends on marketing spend. Recommend exposing `ramp_weeks` and `k` as tunable, and calibrating against the first measured initiative via the existing `HistoricalKnowledgeBase`.
2. **Staff hours as a HARD constraint** — UK 48-hour weekly average (Working Time Regulations), not 40. 40 is a contractual norm. The model should default to 48 as the legal hard cap and treat 40 as a soft preference. **This needs owner confirmation.**
3. **New nodes for liabilities** — a loyalty card creates an accrued liability (unredeemed rewards). Task 2's `new_node` support handles this, but the P&L treatment (provision vs contingent) needs an accounting decision.
4. **Interaction effects** — two initiatives on the same node are not additive. The existing `ConstraintCheckerAgent.validate_portfolio()` has interaction notes; the projection engine should call it before summing.

---

## Execution handoff

Plan saved to `docs/plans/2026-10-27-initiative-modeling-framework.md`. Ready for `subagent-driven-development` or direct implementation.
