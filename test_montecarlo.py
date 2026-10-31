"""Checks for Monte Carlo outcome ranges.

The behaviours under test are the ones that would fail quietly: a sampler that
silently loses draws, a band that is inverted, a confidence level that does not
actually change the width of the answer, a copula that distorts the marginals it
is supposed to preserve, and an initiative that runs a simulation but never
stores the result where the UI can read it.
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile

FAILS: list[str] = []


RECORDS: list = []


def check(label, cond, detail=""):
    ok = bool(cond)
    RECORDS.append((str(label), ok, str(detail)))
    if ok:
        print(f"  PASS  {label}")
    else:
        print(f"  FAIL  {label}{' — ' + detail if detail else ''}")
        FAILS.append(str(label))


from mvp.multiagent import montecarlo as MC
from mvp.multiagent.mechanisms import get_mechanism
from mvp.multiagent.montecarlo import (
    Driver, DriverSet, Empirical, Fixed, LogNormal, Normal, Triangular, Uniform,
    MonteCarloEngine, drivers_from_graph, percentile, rank_correlation, simulate,
)

# ---------------------------------------------------------------------------
print("== numerics ==")

check("percentile median of 1..5", abs(percentile([1, 2, 3, 4, 5], 0.5) - 3.0) < 1e-9)
check("percentile p10 interpolates",
      abs(percentile(list(range(0, 101)), 0.10) - 10.0) < 0.51)
check("percentile on empty is 0", percentile([], 0.5) == 0.0)
check("rank correlation of a monotone pair is 1",
      abs(rank_correlation([1, 2, 3, 4], [10, 20, 30, 40]) - 1.0) < 1e-9)
check("rank correlation of an inverse pair is -1",
      abs(rank_correlation([1, 2, 3, 4], [40, 30, 20, 10]) + 1.0) < 1e-9)
check("rank correlation handles ties without blowing up",
      rank_correlation([1, 1, 2, 2], [5, 6, 7, 8]) > 0.5)

# Normal quantiles: the classic 1.2816 / 1.6449 landmarks.
check("normal p90 ≈ 1.2816 sd", abs(MC._norm_ppf(0.90) - 1.2816) < 1e-3)
check("normal p95 ≈ 1.6449 sd", abs(MC._norm_ppf(0.95) - 1.6449) < 1e-3)
check("normal round-trip", abs(MC._norm_cdf(MC._norm_ppf(0.37)) - 0.37) < 1e-6)

# ---------------------------------------------------------------------------
print("== distributions ==")

tri = Triangular(0, 5, 10)
check("triangular quantile(0) is the low bound", tri.quantile(0.0) == 0.0)
check("triangular quantile(1) is the high bound", tri.quantile(1.0) == 10.0)
check("triangular mode at its own cdf point",
      abs(tri.quantile((5 - 0) / (10 - 0)) - 5.0) < 1e-6)
check("triangular mean", abs(tri.mean() - 5.0) < 1e-9)
check("uniform stays inside bounds",
      all(2.0 <= Uniform(2, 7).quantile(u / 100) <= 7.0 for u in range(1, 100)))
ln = LogNormal(median=100, sigma=0.5)
check("lognormal median", abs(ln.quantile(0.5) - 100.0) < 1e-6)
check("lognormal is right-skewed", ln.mean() > ln.quantile(0.5))
check("empirical reads observed quantiles",
      abs(Empirical([1, 2, 3, 4, 5]).quantile(0.5) - 3.0) < 1e-9)
check("fixed ignores u", Fixed(4.2).quantile(0.01) == 4.2)

# ---------------------------------------------------------------------------
print("== copula preserves marginals ==")

ds = DriverSet(rho=0.9)
ds.add(Driver("a", Triangular(0, 5, 10), "curve:peak", group="demand"))
ds.add(Driver("b", Triangular(1, 2, 4), "engine:volume_lift", group="demand"))
ds.add(Driver("c", Fixed(0.5), "curve:ramp", group="independent"))

import random as _random

for rho in (0.0, 0.9):
    rng = _random.Random(7)
    a_vals, b_vals = [], []
    for _ in range(4000):
        d = ds.sample(rng, rho)
        a_vals.append(d["curve:peak"])
        b_vals.append(d["engine:volume_lift"])
    mean_a = statistics.fmean(a_vals)
    mean_b = statistics.fmean(b_vals)
    check(f"rho={rho} keeps mean of driver a near 5", abs(mean_a - 5.0) < 0.15, f"{mean_a:.2f}")
    check(f"rho={rho} keeps mean of driver b near 2.33", abs(mean_b - 2.33) < 0.12, f"{mean_b:.2f}")

rng = _random.Random(11)
d_a, d_b = [], []
for _ in range(4000):
    d = ds.sample(rng, 0.9)
    d_a.append(d["curve:peak"])
    d_b.append(d["engine:volume_lift"])
rho_high = rank_correlation(d_a, d_b)
rng = _random.Random(11)
i_a, i_b = [], []
for _ in range(4000):
    d = ds.sample(rng, 0.0)
    i_a.append(d["curve:peak"])
    i_b.append(d["engine:volume_lift"])
rho_low = rank_correlation(i_a, i_b)
check("correlated draws are strongly associated", rho_high > 0.75, f"{rho_high:.2f}")
check("independent draws are not associated", abs(rho_low) < 0.10, f"{rho_low:.2f}")

# ---------------------------------------------------------------------------
print("== engine on a real business ==")

from mvp.loader import load_graph, load_all

graph = load_graph("jonco")
business = load_all("jonco")

mech = get_mechanism("loyalty_card", n_paid=9, adoption_rate=0.6)
drivers = drivers_from_graph(graph, "pnl_revenue", confidence=0.5,
                            base_lift=0.12, mechanism=mech,
                            baseline={"revenue": 20763.0, "cogs": 4937.0,
                                      "labour": 11062.0, "overheads": 4674.0})
check("drivers include a volume lift", any(d.target == "engine:volume_lift" for d in drivers.drivers))
check("drivers include the adoption peak", any(d.target == "curve:peak" for d in drivers.drivers))
check("drivers include a mechanism parameter",
      any(d.target.startswith("mechanism:") for d in drivers.drivers))
check("drivers include baseline revenue",
      any(d.target == "baseline:revenue" for d in drivers.drivers))
check("demand drivers are grouped",
      sum(1 for d in drivers.drivers if d.group == MC.DEMAND_GROUP) >= 2)

engine = MonteCarloEngine(
    {"revenue": 20763.0, "cogs": 4937.0, "labour": 11062.0,
     "overheads": 4674.0, "units": 2000.0},
    mech, drivers, months=12,
)
res = engine.run(draws=600, seed=99)

check("every draw produced an outcome", len(res.delta_profit) == 600,
      f"{len(res.delta_profit)} of 600")
check("no draw failed", res.failures == 0, f"{res.failures} failures")
check("p10 <= p50 <= p90", res.p10 <= res.p50 <= res.p90,
      f"{res.p10:.0f} / {res.p50:.0f} / {res.p90:.0f}")
check("probability is a fraction", 0.0 <= res.prob_positive <= 1.0, str(res.prob_positive))
check("payback probability is a fraction", 0.0 <= res.prob_payback <= 1.0, str(res.prob_payback))
check("expected shortfall is no better than the median",
      res.expected_shortfall_10 <= res.p50)
check("monthly bands cover the horizon", len(res.monthly_bands) == 12)
check("each month band is ordered",
      all(b["p10"] <= b["p25"] <= b["p50"] <= b["p75"] <= b["p90"]
          for b in res.monthly_bands))
check("bands carry the interquartile range", all("p25" in b and "p75" in b
      for b in res.monthly_bands))
check("quantile ladder has 21 steps", len(res.quantiles) == 21)
check("quantile ladder is monotone",
      all(res.quantiles[i] <= res.quantiles[i + 1] for i in range(20)))
check("quantile ladder spans the sample",
      abs(res.quantiles[0] - min(res.delta_profit)) < 0.01
      and abs(res.quantiles[-1] - max(res.delta_profit)) < 0.01)
check("histogram counts every draw",
      sum(b["count"] for b in res.histogram) == 600,
      str(sum(b["count"] for b in res.histogram)))
check("histogram bins are contiguous",
      all(abs(res.histogram[i]["to"] - res.histogram[i + 1]["from"]) < 0.02
          for i in range(len(res.histogram) - 1)))
check("sensitivity is sorted by absolute strength",
      all(abs(res.sensitivity[i]["rank_correlation"]) >= abs(res.sensitivity[i + 1]["rank_correlation"])
          for i in range(len(res.sensitivity) - 1)))
check("the strongest driver is identified", bool(res.stats.get("top_driver")))

# Determinism and seed sensitivity.
again = MonteCarloEngine(
    {"revenue": 20763.0, "cogs": 4937.0, "labour": 11062.0,
     "overheads": 4674.0, "units": 2000.0},
    mech, drivers, months=12,
).run(draws=600, seed=99)
check("same seed reproduces the same median", abs(res.p50 - again.p50) < 1e-9,
      f"{res.p50:.2f} vs {again.p50:.2f}")
other = MonteCarloEngine(
    {"revenue": 20763.0, "cogs": 4937.0, "labour": 11062.0,
     "overheads": 4674.0, "units": 2000.0},
    mech, drivers, months=12,
).run(draws=600, seed=100)
check("a different seed moves the sample", abs(res.p50 - other.p50) > 1e-6)

# ---------------------------------------------------------------------------
print("== confidence controls the width ==")

def band_width(conf: float) -> float:
    ds2 = drivers_from_graph(graph, "pnl_revenue", confidence=conf,
                             base_lift=0.12, mechanism=mech,
                             baseline={"revenue": 20763.0, "cogs": 4937.0,
                                       "labour": 11062.0, "overheads": 4674.0})
    r = MonteCarloEngine(
        {"revenue": 20763.0, "cogs": 4937.0, "labour": 11062.0,
         "overheads": 4674.0, "units": 2000.0},
        mech, ds2, months=12,
    ).run(draws=500, seed=5)
    return r.p90 - r.p10

wide = band_width(0.1)
narrow = band_width(0.95)
check("low confidence gives a wider band", wide > narrow, f"{wide:.0f} vs {narrow:.0f}")

# ---------------------------------------------------------------------------
print("== graph dispersion drives the width ==")


class FakeNode:
    def __init__(self, sparkline, change=0.0):
        self.sparkline = sparkline
        self.change_30d_pct = change


class FakeGraph:
    def __init__(self, nodes):
        self.nodes = nodes


steady = FakeGraph({"n": FakeNode([100.0] * 30)})
volatile = FakeGraph({"n": FakeNode([60.0, 140.0] * 15)})


def width_for(g):
    ds3 = drivers_from_graph(g, "n", confidence=0.5, base_lift=0.12, mechanism=mech)
    lift = [d for d in ds3.drivers if d.target == "engine:volume_lift"][0]
    return lift.dist.high - lift.dist.low


w_steady, w_vol = width_for(steady), width_for(volatile)
check("a volatile node produces a wider lift band", w_vol > w_steady,
      f"{w_vol:.3f} vs {w_steady:.3f}")
check("graph-derived drivers are labelled as such",
      any(d.source == "graph" for d in drivers_from_graph(volatile, "n", mechanism=mech).drivers))

# ---------------------------------------------------------------------------
print("== simulate() convenience path ==")

sres = simulate(
    business, mechanism_name="loyalty_card",
    mechanism_params={"n_paid": 9, "adoption_rate": 0.6},
    graph=graph, node_id="pnl_revenue", confidence=0.5,
    months=12, draws=400, seed=3, volume_lift=0.12,
)
check("simulate runs without an initiative", len(sres.delta_profit) == 400)
d = sres.to_dict()
check("to_dict exposes percentiles", "delta_profit" in d["percentiles"])
check("to_dict exposes probabilities", "positive" in d["probabilities"])
check("to_dict carries a narrative", isinstance(d.get("narrative"), str) and len(d["narrative"]) > 20)
check("narrative names the band", "80% range" in d["narrative"])

# ---------------------------------------------------------------------------
print("== orchestrator attaches the range to the initiative ==")

from mvp.multiagent.hypothesis import Initiative, LeverType
from mvp.multiagent.orchestrator import MultiAgentOrchestrator, OrchestratorConfig

tmpdir = tempfile.mkdtemp(prefix="bam_mc_")
orch = MultiAgentOrchestrator(
    config=OrchestratorConfig(tenant_id="jonco", db_path=os.path.join(tmpdir, "kb.db")),
    business=business,
)
ini = Initiative(
    node_id="pnl_revenue", node_label="Revenue",
    title="Loyalty card trial", description="Test a 9+1 loyalty card",
    lever_type=LeverType.VOLUME, predicted_impact_gbp=1500.0,
    metadata={"confidence": 0.4},
)
out = orch.monte_carlo_initiative(
    ini, "loyalty_card", mechanism_params={"n_paid": 9, "adoption_rate": 0.6},
    months=12, draws=300, seed=1, volume_lift=0.12, graph=graph,
)
check("orchestrator returns a result", len(out.delta_profit) == 300)
check("result stored in metadata", "monte_carlo" in ini.metadata)
check("metadata carries the range",
      isinstance(ini.metadata.get("predicted_range_gbp"), list)
      and len(ini.metadata["predicted_range_gbp"]) == 2)
check("initiative records its mechanism", ini.mechanism == "loyalty_card")
check("metadata survives to_dict", "monte_carlo" in ini.to_dict()["metadata"])
stored = ini.metadata["monte_carlo"]
check("stored payload has probabilities", "probabilities" in stored)
check("stored payload has monthly bands", len(stored.get("monthly_bands", [])) == 12)

# A mechanism whose params cannot be constructed must fail loudly, not silently.
try:
    orch.monte_carlo_initiative(ini, "not_a_mechanism", draws=10)
    check("unknown mechanism raises", False)
except Exception:
    check("unknown mechanism raises", True)

# ---------------------------------------------------------------------------
print("== risk-adjusted ranking ==")

from mvp.multiagent.montecarlo import risk_adjusted_score

safe = MC.MonteCarloResult(draws=4, months=12, seed=None, drivers=DriverSet())
safe.delta_profit = [1000.0, 1100.0, 1200.0, 1300.0]
risky = MC.MonteCarloResult(draws=4, months=12, seed=None, drivers=DriverSet())
risky.delta_profit = [-4000.0, 200.0, 3000.0, 4000.0]
check("risk score penalises downside", risk_adjusted_score(safe) > risk_adjusted_score(risky),
      f"{risk_adjusted_score(safe):.0f} vs {risk_adjusted_score(risky):.0f}")
check("risk score is zero without draws",
      risk_adjusted_score(MC.MonteCarloResult(draws=0, months=12, seed=None, drivers=DriverSet())) == 0.0)

# ---------------------------------------------------------------------------
print()
if __name__ == "__main__":
    if FAILS:
        print(f"{len(FAILS)} FAILURES:")
        for f in FAILS:
            print(f"  - {f}")
        sys.exit(1)
    else:
        print("All Monte Carlo checks passed.")
    sys.exit(1 if FAILS else 0)

def test_checks(case):
    """Each recorded check is reported as its own pytest test."""
    assert case is not None, "harness recorded no checks — did it run?"
    label, ok, detail = case
    assert ok, f"{label}{' — ' + detail if detail else ''}"
