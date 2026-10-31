"""Monte Carlo outcome ranges for hypotheses and initiatives.

Why this exists
---------------
``projection.ProjectionEngine`` is deterministic: one mechanism, one adoption
curve, one P&L curve. That answers "what happens if the world is exactly as I
assume". It cannot answer the question a business actually asks — "how wrong
could I be, and how bad is the bad case".

This module keeps the projection engine as the *inner* model and wraps it in a
sampling loop. Each draw perturbs the assumptions the engine is most sensitive
to, projects a full P&L curve, and records the outcome. The result is a
distribution per initiative: a P10/P50/P90 band on profit, a probability that
the move loses money, a probability of payback inside the horizon, and a
downside figure (expected shortfall) for ranking risk.

Where the uncertainty comes from
--------------------------------
Two sources, and keeping them separate matters:

* **Graph-derived** — the target node's own history. ``sparkline`` carries the
  period series the node was built from; its coefficient of variation is the
  honest measure of how noisy that driver is in *this* business. A café whose
  revenue swings 25% week to week gets a wider band than a SaaS with 3% MRR
  churn, without anyone hand-tuning a number.
* **Mechanism-derived** — the parameters of the change itself. ``n_paid`` for a
  loyalty card is a decision, not a measurement, so its band comes from the
  hypothesis's confidence: high confidence means a tight band, low confidence a
  wide one.

Demand-side drivers are correlated. If uptake is high, volume lift is high and
revenue is high — sampling those independently would understate the spread of
the tail. ``Driver.group`` puts them on a shared latent factor with correlation
``rho`` (a Gaussian copula over each driver's own marginal distribution).

Everything here is pure Python and deterministic given a seed.
"""

from __future__ import annotations

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .mechanisms import Mechanism, MechanismEffect, get_mechanism
from .projection import (
    AdoptionCurve,
    ProjectionEngine,
    ProjectionResult,
    baseline_from_business,
    make_curve,
)


# ---------------------------------------------------------------------------
# Small numerics — no scipy in this project, so the two functions we need are
# implemented here and unit-tested against known values.
# ---------------------------------------------------------------------------


def _norm_cdf(z: float) -> float:
    """Standard normal CDF via erf."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation).

    Accurate to ~1.15e-9 over (0, 1). Guarded at the open interval ends so a
    copula draw of exactly 0 or 1 cannot produce an infinity.
    """
    if p <= 0.0:
        return -8.0
    if p >= 1.0:
        return 8.0
    a = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
         1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
    b = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
         6.680131188771972e01, -1.328068155288572e01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
         -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
         3.754408661907416e00)
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
                ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)


def percentile(values: Sequence[float], p: float) -> float:
    """Linear-interpolated percentile (numpy's default convention), p in 0..1."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = p * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = min(lo + 1, len(ordered) - 1)
    frac = pos - lo
    return float(ordered[lo]) + frac * (float(ordered[hi]) - float(ordered[lo]))


def rank_correlation(xs: Sequence[float], ys: Sequence[float]) -> float:
    """Spearman rank correlation with average ranks for ties."""
    n = min(len(xs), len(ys))
    if n < 3:
        return 0.0

    def ranks(vals: Sequence[float]) -> List[float]:
        order = sorted(range(n), key=lambda i: vals[i])
        out = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return 0.0
    return num / (dx * dy)


# ---------------------------------------------------------------------------
# Distributions — each exposes quantile(u) so the copula can drive it.
# ---------------------------------------------------------------------------


class Distribution:
    """Base distribution. ``quantile(u)`` must accept u in (0, 1)."""

    kind = "base"
    unit = ""

    def quantile(self, u: float) -> float:
        raise NotImplementedError

    def sample(self, rng: random.Random) -> float:
        return self.quantile(rng.random())

    def mean(self) -> float:
        return self.quantile(0.5)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "unit": self.unit}


class Fixed(Distribution):
    kind = "fixed"

    def __init__(self, value: float, unit: str = "") -> None:
        self.value = float(value)
        self.unit = unit

    def quantile(self, u: float) -> float:
        return self.value

    def to_dict(self) -> dict:
        return {"kind": self.kind, "value": round(self.value, 4), "unit": self.unit}


class Uniform(Distribution):
    kind = "uniform"

    def __init__(self, low: float, high: float, unit: str = "") -> None:
        if high < low:
            low, high = high, low
        self.low = float(low)
        self.high = float(high)
        self.unit = unit

    def quantile(self, u: float) -> float:
        u = min(max(u, 1e-12), 1 - 1e-12)
        return self.low + u * (self.high - self.low)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "low": round(self.low, 4),
                "high": round(self.high, 4), "unit": self.unit}


class Triangular(Distribution):
    """low / mode / high — the workhorse for elicited assumptions."""

    kind = "triangular"

    def __init__(self, low: float, mode: float, high: float, unit: str = "") -> None:
        lo, hi = (low, high) if high >= low else (high, low)
        lo = float(lo)
        hi = float(hi)
        mode = float(mode)
        mode = min(max(mode, lo), hi)
        self.low, self.mode, self.high = lo, mode, hi
        self.unit = unit

    def quantile(self, u: float) -> float:
        lo, mo, hi = self.low, self.mode, self.high
        if u <= 0.0:
            return lo
        if u >= 1.0:
            return hi
        u = min(max(u, 1e-12), 1 - 1e-12)
        if hi - lo < 1e-12:
            return lo
        c = (mo - lo) / (hi - lo)
        if u < c:
            return lo + math.sqrt(u * (hi - lo) * (mo - lo))
        if u > c:
            return hi - math.sqrt((1 - u) * (hi - lo) * (hi - mo))
        return mo

    def mean(self) -> float:
        return (self.low + self.mode + self.high) / 3.0

    def to_dict(self) -> dict:
        return {"kind": self.kind, "low": round(self.low, 4),
                "mode": round(self.mode, 4), "high": round(self.high, 4),
                "unit": self.unit}


class Normal(Distribution):
    kind = "normal"

    def __init__(self, mean: float, sd: float, unit: str = "") -> None:
        self.mu = float(mean)
        self.sigma = max(abs(float(sd)), 1e-9)
        self.unit = unit

    def quantile(self, u: float) -> float:
        return self.mu + self.sigma * _norm_ppf(u)

    def mean(self) -> float:
        return self.mu

    def to_dict(self) -> dict:
        return {"kind": self.kind, "mean": round(self.mu, 4),
                "sd": round(self.sigma, 4), "unit": self.unit}


class LogNormal(Distribution):
    """Right-skewed — the right shape for costs and overruns."""

    kind = "lognormal"

    def __init__(self, median: float, sigma: float, unit: str = "") -> None:
        self.median = max(float(median), 1e-9)
        self.sigma = max(abs(float(sigma)), 1e-9)
        self.unit = unit

    def quantile(self, u: float) -> float:
        return self.median * math.exp(self.sigma * _norm_ppf(u))

    def mean(self) -> float:
        return self.median * math.exp(self.sigma ** 2 / 2.0)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "median": round(self.median, 4),
                "sigma": round(self.sigma, 4), "unit": self.unit}


class Empirical(Distribution):
    """Quantiles taken straight from observed values — no distributional assumption."""

    kind = "empirical"

    def __init__(self, values: Sequence[float], unit: str = "") -> None:
        if not values:
            raise ValueError("Empirical needs at least one value")
        self.values = [float(v) for v in sorted(values)]
        self.unit = unit

    def quantile(self, u: float) -> float:
        return percentile(self.values, min(max(u, 0.0), 1.0))

    def mean(self) -> float:
        return sum(self.values) / len(self.values)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "n": len(self.values),
                "min": round(self.values[0], 4),
                "max": round(self.values[-1], 4), "unit": self.unit}


# ---------------------------------------------------------------------------
# Drivers
# ---------------------------------------------------------------------------

#: Targets the engine knows how to apply to a draw.
TARGET_CURVE_PEAK = "curve:peak"
TARGET_CURVE_RAMP = "curve:ramp"
TARGET_VOLUME_LIFT = "engine:volume_lift"
TARGET_BASELINE = "baseline:"          # + field name
TARGET_MECHANISM = "mechanism:"        # + param name

DEMAND_GROUP = "demand"


@dataclass
class Driver:
    """One uncertain assumption feeding the projection.

    ``target`` tells the engine where to put the sampled value:

    * ``curve:peak`` — adoption plateau (fraction of demand affected)
    * ``curve:ramp`` — months to reach plateau (sets curve midpoint)
    * ``engine:volume_lift`` — fractional volume increase at full adoption
    * ``baseline:<field>`` — revenue / cogs / labour / overheads run-rate
    * ``mechanism:<param>`` — a parameter of the mechanism itself

    ``group`` puts drivers on a shared latent factor. Everything in ``demand``
    moves together, because uptake, volume and revenue are not independent.
    """

    name: str
    dist: Distribution
    target: str
    group: str = "independent"
    unit: str = ""
    source: str = "prior"
    note: str = ""

    def to_dict(self) -> dict:
        d = self.dist.to_dict()
        d.update({"name": self.name, "target": self.target, "group": self.group,
                  "source": self.source, "note": self.note})
        return d


@dataclass
class DriverSet:
    drivers: List[Driver] = field(default_factory=list)
    rho: float = 0.6

    def add(self, driver: Driver) -> "DriverSet":
        self.drivers.append(driver)
        return self

    def by_target(self, prefix: str) -> List[Driver]:
        return [d for d in self.drivers if d.target.startswith(prefix)]

    def sample(self, rng: random.Random, rho: Optional[float] = None) -> Dict[str, float]:
        """Draw one value per driver, correlating within the demand group.

        One latent standard-normal shock is shared by every ``demand`` driver;
        each driver then takes its own idiosyncratic component. With rho=0 this
        degenerates to independent draws; with rho=1 every demand driver moves
        in lockstep.
        """
        r = self.rho if rho is None else rho
        r = min(max(r, 0.0), 0.999)
        latent = _norm_ppf(rng.random())
        out: Dict[str, float] = {}
        for d in self.drivers:
            if d.group == DEMAND_GROUP and r > 0.0:
                e = _norm_ppf(rng.random())
                z = r * latent + math.sqrt(max(1.0 - r * r, 0.0)) * e
                u = _norm_cdf(z)
            else:
                u = rng.random()
            out[d.target] = d.dist.quantile(u)
        return out

    def to_dict(self) -> dict:
        return {"rho": self.rho, "drivers": [d.to_dict() for d in self.drivers]}


# ---------------------------------------------------------------------------
# Deriving drivers from the graph
# ---------------------------------------------------------------------------


def _series_stats(node: Any) -> Optional[Dict[str, float]]:
    """Coefficient of variation and span of a node's sparkline, if it has one."""
    series = [float(v) for v in getattr(node, "sparkline", []) or [] if v is not None]
    series = [v for v in series if v > 0]
    if len(series) < 4:
        return None
    mean = statistics.fmean(series)
    if mean <= 0:
        return None
    sd = statistics.pstdev(series)
    # Monthly revenue is a sum of ~n period values. Under independence the
    # relative sd of the sum shrinks by sqrt(n); real series are autocorrelated,
    # so inflate to avoid pretending the monthly figure is tighter than it is.
    monthly_rel_sd = (sd / mean) / math.sqrt(len(series)) * 1.5
    return {
        "n": float(len(series)),
        "mean": mean,
        "cv": sd / mean,
        "monthly_rel_sd": min(max(monthly_rel_sd, 0.005), 0.60),
    }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def drivers_from_graph(
    graph: Any,
    node_id: str = "",
    *,
    confidence: float = 0.5,
    base_lift: Optional[float] = None,
    peak: float = 0.6,
    ramp_months: float = 6.0,
    mechanism: Optional[Mechanism] = None,
    baseline: Optional[Dict[str, float]] = None,
    months: int = 12,
) -> DriverSet:
    """Build a DriverSet from the target node's history plus the mechanism.

    ``confidence`` is the hypothesis's own confidence: 1.0 gives point values,
    0.0 gives the widest band the engine will allow. It scales the *mechanism*
    drivers. Graph-derived drivers are not scaled by confidence — the business's
    own volatility is a fact, not an opinion.
    """
    ds = DriverSet()
    confidence = _clamp(float(confidence), 0.0, 1.0)
    width = 1.0 - confidence          # 0 = certain, 1 = no idea

    node = None
    if graph is not None and node_id:
        nodes = getattr(graph, "nodes", {}) or {}
        node = nodes.get(node_id) if hasattr(nodes, "get") else None

    stats = _series_stats(node) if node is not None else None
    monthly_sd = stats["monthly_rel_sd"] if stats else 0.12
    source = "graph" if stats else "prior"

    # 1. Volume lift — the demand-side driver. Band widens with the node's own
    #    historical dispersion and with how unsure the hypothesis is.
    lift_mode = base_lift
    if lift_mode is None:
        # No explicit lift supplied: infer a modest one from the node's trend.
        chg = getattr(node, "change_30d_pct", 0.0) if node is not None else 0.0
        try:
            chg = float(chg or 0.0)
        except (TypeError, ValueError):
            chg = 0.0
        lift_mode = _clamp(chg / 100.0 * 0.25, 0.02, 0.20)
    w = _clamp(monthly_sd * 1.5 + width * 0.25, 0.05, 0.65)
    ds.add(Driver(
        name="volume_lift",
        dist=Triangular(max(lift_mode * (1 - w), 0.0), lift_mode, lift_mode * (1 + w)),
        target=TARGET_VOLUME_LIFT,
        group=DEMAND_GROUP,
        unit="fraction",
        source=source,
        note=("derived from the target node's period dispersion"
              if stats else "prior — the node has no usable history"),
    ))

    # 2. Adoption plateau — mechanism-side, scaled by confidence.
    peak = _clamp(float(peak), 0.0, 1.0)
    peak_w = _clamp(width * 0.5, 0.02, 0.45)
    ds.add(Driver(
        name="adoption_peak",
        dist=Triangular(max(peak - peak_w, 0.0), peak, min(peak + peak_w, 1.0)),
        target=TARGET_CURVE_PEAK,
        group=DEMAND_GROUP,
        unit="fraction",
        source="prior",
        note="how much of demand the change reaches at plateau",
    ))

    # 3. Ramp — asymmetric: ramps overrun more often than they finish early.
    ramp_months = max(float(ramp_months), 1.0)
    ds.add(Driver(
        name="ramp_months",
        dist=Triangular(max(ramp_months * (1 - 0.35 - width * 0.2), 1.0),
                        ramp_months,
                        ramp_months * (1 + 0.45 + width * 0.4)),
        target=TARGET_CURVE_RAMP,
        unit="months",
        source="prior",
        note="time to reach the adoption plateau",
    ))

    # 4. Mechanism parameters — every numeric parameter gets a band. Integer
    #    parameters are sampled continuously and rounded at draw time so the
    #    distribution is not distorted by pre-rounding.
    if mechanism is not None:
        for key, value in (getattr(mechanism, "params", {}) or {}).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                continue
            v = float(value)
            if v == 0.0:
                continue
            pw = _clamp(width * 0.4, 0.03, 0.40)
            lo, hi = v * (1 - pw), v * (1 + pw)
            if key == "adoption_rate":
                lo, hi = max(lo, 0.0), min(hi, 1.0)
            else:
                lo = max(lo, 0.0)
            ds.add(Driver(
                name=f"mechanism.{key}",
                dist=Triangular(lo, v, hi),
                target=TARGET_MECHANISM + key,
                unit="",
                source="prior",
                note="decision parameter, banded by hypothesis confidence",
            ))

    # 5. Baseline run-rate — the P&L the change is applied to is itself noisy.
    #    Only revenue and cogs are banded: labour and overheads are contractual
    #    month to month, so treating them as uncertain would inflate the tail
    #    without justification.
    if baseline:
        for key in ("revenue", "cogs"):
            v = float(baseline.get(key, 0.0) or 0.0)
            if v <= 0:
                continue
            bw = _clamp(monthly_sd, 0.02, 0.35)
            ds.add(Driver(
                name=f"baseline.{key}",
                dist=Triangular(v * (1 - bw), v, v * (1 + bw)),
                target=TARGET_BASELINE + key,
                group=DEMAND_GROUP if key == "revenue" else "independent",
                unit="GBP",
                source=source,
                note="run-rate uncertainty carried from the graph",
            ))
    return ds


# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


@dataclass
class MonteCarloResult:
    """Distribution of outcomes across draws."""

    draws: int
    months: int
    seed: Optional[int]
    drivers: DriverSet

    # per-draw outcomes
    delta_profit: List[float] = field(default_factory=list)
    payback_month: List[int] = field(default_factory=list)
    total_revenue: List[float] = field(default_factory=list)
    trough_profit: List[float] = field(default_factory=list)
    peak_adoption: List[float] = field(default_factory=list)
    breaches: int = 0
    failures: int = 0

    # per-month operating-profit band
    monthly_bands: List[Dict[str, float]] = field(default_factory=list)
    # distribution shape for plotting: 5% quantiles of the profit impact, and
    # a binned density so a chart never has to guess at the shape
    quantiles: List[float] = field(default_factory=list)
    histogram: List[Dict[str, float]] = field(default_factory=list)

    # summary
    stats: Dict[str, Any] = field(default_factory=dict)
    sensitivity: List[Dict[str, Any]] = field(default_factory=list)

    # ---------------------------------------------------------------- derived
    @property
    def p10(self) -> float:
        return percentile(self.delta_profit, 0.10)

    @property
    def p50(self) -> float:
        return percentile(self.delta_profit, 0.50)

    @property
    def p90(self) -> float:
        return percentile(self.delta_profit, 0.90)

    @property
    def prob_positive(self) -> float:
        if not self.delta_profit:
            return 0.0
        return sum(1 for d in self.delta_profit if d > 0) / len(self.delta_profit)

    @property
    def prob_payback(self) -> float:
        if not self.payback_month:
            return 0.0
        return sum(1 for m in self.payback_month if m <= self.months) / len(self.payback_month)

    @property
    def expected_shortfall_10(self) -> float:
        """Mean of the worst 10% of outcomes — the downside figure for ranking."""
        if not self.delta_profit:
            return 0.0
        ordered = sorted(self.delta_profit)
        cut = max(int(len(ordered) * 0.10), 1)
        return sum(ordered[:cut]) / cut

    def summary(self) -> str:
        band = f"£{self.p10:,.0f} to £{self.p90:,.0f}"
        return (
            f"Monte Carlo: {self.draws} draws over {self.months} months\n"
            f"Median profit impact: £{self.p50:,.0f}\n"
            f"80% band: {band}\n"
            f"Probability of improving profit: {self.prob_positive:.0%}\n"
            f"Probability of payback in horizon: {self.prob_payback:.0%}\n"
            f"Expected shortfall (worst 10%): £{self.expected_shortfall_10:,.0f}"
        )

    def narrative(self) -> str:
        """One sentence suitable for a UI card."""
        direction = "improve" if self.p50 > 0 else "reduce"
        return (
            f"Most likely {direction}s 12-month profit by £{abs(self.p50):,.0f}, "
            f"with an 80% range of £{self.p10:,.0f} to £{self.p90:,.0f}. "
            f"{self.prob_positive:.0%} chance the move is profit-positive; "
            f"worst-decile outcome £{self.expected_shortfall_10:,.0f}."
        )

    def to_dict(self) -> dict:
        return {
            "draws": self.draws,
            "months": self.months,
            "seed": self.seed,
            "failures": self.failures,
            "breaches": self.breaches,
            "percentiles": {
                "delta_profit": {
                    "p10": round(self.p10, 2),
                    "p25": round(percentile(self.delta_profit, 0.25), 2),
                    "p50": round(self.p50, 2),
                    "p75": round(percentile(self.delta_profit, 0.75), 2),
                    "p90": round(self.p90, 2),
                },
                "trough_profit": {
                    "p10": round(percentile(self.trough_profit, 0.10), 2),
                    "p50": round(percentile(self.trough_profit, 0.50), 2),
                    "p90": round(percentile(self.trough_profit, 0.90), 2),
                },
                "peak_adoption": {
                    "p10": round(percentile(self.peak_adoption, 0.10), 4),
                    "p50": round(percentile(self.peak_adoption, 0.50), 4),
                    "p90": round(percentile(self.peak_adoption, 0.90), 4),
                },
            },
            "probabilities": {
                "positive": round(self.prob_positive, 4),
                "payback_in_horizon": round(self.prob_payback, 4),
                "constraint_breach": round(self.breaches / self.draws, 4) if self.draws else 0.0,
                "loss_gt_zero": round(1 - self.prob_positive, 4),
            },
            "expected_shortfall_10": round(self.expected_shortfall_10, 2),
            "risk_adjusted_score": round(risk_adjusted_score(self), 2),
            "monthly_bands": self.monthly_bands,
            "quantiles": self.quantiles,
            "histogram": self.histogram,
            "drivers": self.drivers.to_dict(),
            "sensitivity": self.sensitivity,
            "stats": self.stats,
            "narrative": self.narrative(),
        }


def _histogram(values: Sequence[float], bins: int = 24) -> List[Dict[str, float]]:
    """Bin values for a density strip. Empty input returns an empty list."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-9:
        return [{"from": round(lo, 2), "to": round(hi, 2), "count": len(values)}]
    width = (hi - lo) / bins
    counts = [0] * bins
    for v in values:
        idx = min(int((v - lo) / width), bins - 1)
        counts[idx] += 1
    return [
        {"from": round(lo + i * width, 2), "to": round(lo + (i + 1) * width, 2),
         "count": counts[i]}
        for i in range(bins)
    ]


def risk_adjusted_score(result: MonteCarloResult) -> float:
    """Rank by expected value discounted by the chance and depth of loss.

    A move with a higher median but a 40% chance of a large loss should not
    outrank a smaller certain gain. The score is deliberately conservative:
    it adds a fraction of the (negative) expected shortfall, so downside is
    always a drag and never a bonus.
    """
    if not result.delta_profit:
        return 0.0
    return result.p50 * result.prob_positive + 0.35 * result.expected_shortfall_10


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class MonteCarloEngine:
    """Sample assumptions, run the deterministic projection each time.

    The projection engine stays the single source of truth for *how* a
    mechanism becomes a P&L curve. This class only decides *what to vary* and
    summarises the resulting distribution.
    """

    def __init__(
        self,
        baseline: Dict[str, float],
        mechanism: Mechanism,
        drivers: DriverSet,
        *,
        months: int = 12,
        curve_kind: str = "logistic",
        curve_params: Optional[Dict[str, float]] = None,
        rho: Optional[float] = None,
    ) -> None:
        self.baseline = dict(baseline)
        self.mechanism = mechanism
        self.drivers = drivers
        self.months = max(int(months), 1)
        self.curve_kind = curve_kind
        self.curve_params = dict(curve_params or {})
        self.rho = drivers.rho if rho is None else rho

    # -- helpers ----------------------------------------------------------

    def _curve_for(self, draw: Dict[str, float]) -> AdoptionCurve:
        params = dict(self.curve_params)
        peak = draw.get(TARGET_CURVE_PEAK)
        ramp = draw.get(TARGET_CURVE_RAMP)
        if peak is not None:
            params["peak"] = _clamp(float(peak), 0.0, 1.0)
        if self.curve_kind == "linear":
            if ramp is not None:
                params["ramp_months"] = max(int(round(float(ramp))), 1)
        else:
            if ramp is not None:
                params["midpoint"] = max(float(ramp) / 2.0, 0.5)
        params.setdefault("peak", 0.6)
        return make_curve(self.curve_kind, **params)

    def _mechanism_for(self, draw: Dict[str, float]) -> Mechanism:
        params = dict(getattr(self.mechanism, "params", {}) or {})
        cls = type(self.mechanism)
        for target, value in draw.items():
            if not target.startswith(TARGET_MECHANISM):
                continue
            key = target[len(TARGET_MECHANISM):]
            if key in params and isinstance(params[key], int) and not isinstance(params[key], bool):
                params[key] = max(int(round(value)), 0)
            else:
                params[key] = value
        try:
            return cls(**params)
        except TypeError:
            # Mechanism whose signature does not accept all params — keep the
            # original instance and let the projection engine override what it
            # understands.
            return self.mechanism

    def _baseline_for(self, draw: Dict[str, float]) -> Dict[str, float]:
        b = dict(self.baseline)
        for target, value in draw.items():
            if target.startswith(TARGET_BASELINE):
                b[target[len(TARGET_BASELINE):]] = max(float(value), 0.0)
        return b

    # -- main -------------------------------------------------------------

    def run(
        self,
        draws: int = 2000,
        *,
        seed: Optional[int] = None,
        constraint_probe: Optional[Callable[[ProjectionResult], bool]] = None,
    ) -> MonteCarloResult:
        rng = random.Random(seed)
        draws = max(int(draws), 1)
        result = MonteCarloResult(
            draws=draws, months=self.months, seed=seed, drivers=self.drivers
        )
        monthly_ops: List[List[float]] = [[] for _ in range(self.months)]
        sample_log: Dict[str, List[float]] = {d.target: [] for d in self.drivers.drivers}

        for _ in range(draws):
            draw = self.drivers.sample(rng, self.rho)
            for target, value in draw.items():
                sample_log[target].append(value)

            baseline = self._baseline_for(draw)
            mech = self._mechanism_for(draw)
            curve = self._curve_for(draw)
            lift = draw.get(TARGET_VOLUME_LIFT)
            engine = ProjectionEngine(
                baseline,
                volume_lift=float(lift) if lift is not None else 0.0,
                months=self.months,
            )
            try:
                proj = engine.project(mech, curve=curve)
            except Exception:
                # A single bad draw must not destroy the whole run — count it
                # and move on. ``failures`` surfaces in the result so a high
                # rate is visible rather than silently swallowed.
                result.failures += 1
                continue

            result.delta_profit.append(proj.delta_operating_profit)
            result.total_revenue.append(proj.total_revenue)
            result.payback_month.append(proj.payback_month or (self.months + 1))
            result.peak_adoption.append(proj.peak_adoption)
            ops = [m.operating_profit for m in proj.months]
            result.trough_profit.append(min(ops) if ops else 0.0)
            for i, op in enumerate(ops[: self.months]):
                monthly_ops[i].append(op)

            if constraint_probe is not None:
                try:
                    if constraint_probe(proj):
                        result.breaches += 1
                except Exception:
                    pass

        valid = len(result.delta_profit)
        result.monthly_bands = [
            {
                "month": i + 1,
                "p10": round(percentile(vals, 0.10), 2),
                "p25": round(percentile(vals, 0.25), 2),
                "p50": round(percentile(vals, 0.50), 2),
                "p75": round(percentile(vals, 0.75), 2),
                "p90": round(percentile(vals, 0.90), 2),
            }
            for i, vals in enumerate(monthly_ops)
        ]
        # 5% quantile ladder — the input a quantile dotplot needs.
        result.quantiles = [
            round(percentile(result.delta_profit, q / 20.0), 2) for q in range(0, 21)
        ]
        result.histogram = _histogram(result.delta_profit, bins=24)

        result.sensitivity = [
            {
                "driver": d.name,
                "target": d.target,
                "group": d.group,
                "rank_correlation": round(
                    rank_correlation(sample_log.get(d.target, []), result.delta_profit), 3
                ),
            }
            for d in self.drivers.drivers
        ]
        result.sensitivity.sort(key=lambda s: abs(s["rank_correlation"]), reverse=True)

        base_total = float(self.baseline.get("revenue", 0.0)) - float(self.baseline.get("cogs", 0.0)) \
            - float(self.baseline.get("labour", 0.0)) - float(self.baseline.get("overheads", 0.0))
        result.stats = {
            "valid_draws": valid,
            "baseline_monthly_profit": round(base_total, 2),
            "baseline_total_profit": round(base_total * self.months, 2),
            "mean_delta_profit": round(statistics.fmean(result.delta_profit), 2) if valid else 0.0,
            "sd_delta_profit": round(statistics.pstdev(result.delta_profit), 2) if valid > 1 else 0.0,
            "median_payback_month": round(percentile(result.payback_month, 0.50), 1) if valid else None,
            "worst_draw": round(min(result.delta_profit), 2) if valid else 0.0,
            "best_draw": round(max(result.delta_profit), 2) if valid else 0.0,
            "top_driver": result.sensitivity[0]["driver"] if result.sensitivity else None,
            "constraint_probe_used": constraint_probe is not None,
        }
        return result


# ---------------------------------------------------------------------------
# Convenience wrappers
# ---------------------------------------------------------------------------


def simulate(
    business: Any,
    *,
    mechanism_name: str = "loyalty_card",
    mechanism_params: Optional[Dict[str, Any]] = None,
    graph: Any = None,
    node_id: str = "",
    confidence: float = 0.5,
    months: int = 12,
    draws: int = 2000,
    seed: Optional[int] = None,
    volume_lift: Optional[float] = None,
    peak: float = 0.6,
    ramp_months: float = 6.0,
    curve_kind: str = "logistic",
    curve_params: Optional[Dict[str, float]] = None,
    baseline: Optional[Dict[str, float]] = None,
    constraint_probe: Optional[Callable[[ProjectionResult], bool]] = None,
) -> MonteCarloResult:
    """Simulate an outcome range without needing an Initiative record.

    ``business`` may be the flat business object (``load_all``) or anything with
    ``monthly_pnl``; ``baseline`` overrides the derived run-rate when supplied.
    ``graph`` is only used to derive drivers from the target node's history.
    """
    base = dict(baseline) if baseline else baseline_from_business(business)
    mech = get_mechanism(mechanism_name, **(mechanism_params or {}))
    drivers = drivers_from_graph(
        graph,
        node_id,
        confidence=confidence,
        base_lift=volume_lift,
        peak=peak,
        ramp_months=ramp_months,
        mechanism=mech,
        baseline=base,
        months=months,
    )
    engine = MonteCarloEngine(
        base, mech, drivers, months=months,
        curve_kind=curve_kind, curve_params=curve_params,
    )
    return engine.run(draws=draws, seed=seed, constraint_probe=constraint_probe)


__all__ = [
    "Distribution",
    "Fixed",
    "Uniform",
    "Triangular",
    "Normal",
    "LogNormal",
    "Empirical",
    "Driver",
    "DriverSet",
    "drivers_from_graph",
    "MonteCarloEngine",
    "MonteCarloResult",
    "risk_adjusted_score",
    "simulate",
    "percentile",
    "rank_correlation",
    "TARGET_CURVE_PEAK",
    "TARGET_CURVE_RAMP",
    "TARGET_VOLUME_LIFT",
    "TARGET_BASELINE",
    "TARGET_MECHANISM",
    "DEMAND_GROUP",
]
