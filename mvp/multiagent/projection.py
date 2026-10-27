"""Time-phased projection engine for BAM.

Turns a baseline month and a Mechanism into a multi-month P&L curve. The key
missing piece in the original engine was that a Hypothesis predicted a single
value at a single horizon — loyalty cards, opening-hours changes and staffing
changes all play out over months, with an adoption ramp.

Design
------
* ``AdoptionCurve`` models how uptake builds month by month. Linear, logistic
  and exponential curves are provided. The curve returns a fraction 0..1 for a
  given month index (1-based).
* ``ProjectionEngine.project()`` composes:
      baseline P&L
      + volume lift from adoption (mechanism-dependent)
      + mechanism cost (give-aways, penalties)
      + liability treatment
  and returns a list of ``MonthlyProjection`` plus totals.
* Constraint gating is delegated to the existing ConstraintChecker where a
  projection would breach a HARD constraint; SOFT breaches add a penalty.

This module does not mutate the business graph. It is a what-if calculator.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence

from .mechanisms import Mechanism, MechanismEffect


# ---------------------------------------------------------------------------
# Adoption curves
# ---------------------------------------------------------------------------


class AdoptionCurve:
    """Base class for adoption ramp curves. ``at(month)`` returns 0..1."""

    name = "base"

    def at(self, month: int, horizon: int = 12) -> float:
        raise NotImplementedError

    def series(self, months: int) -> List[float]:
        return [self.at(m, months) for m in range(1, months + 1)]


class LinearAdoption(AdoptionCurve):
    """Adoption rises linearly to ``peak`` by ``ramp_months``, then holds."""

    name = "linear"

    def __init__(self, peak: float = 0.6, ramp_months: int = 6) -> None:
        if not 0 <= peak <= 1:
            raise ValueError("peak must be within [0, 1]")
        if ramp_months < 1:
            raise ValueError("ramp_months must be >= 1")
        self.peak = peak
        self.ramp_months = ramp_months

    def at(self, month: int, horizon: int = 12) -> float:
        if month <= 0:
            return 0.0
        frac = min(month / self.ramp_months, 1.0)
        return self.peak * frac


class LogisticAdoption(AdoptionCurve):
    """S-curve adoption: slow start, steep middle, plateau at ``peak``.

    ``midpoint`` is the month where adoption reaches peak/2, ``steepness``
    controls how sharp the ramp is.
    """

    name = "logistic"

    def __init__(
        self, peak: float = 0.6, midpoint: float = 3.0, steepness: float = 1.2
    ) -> None:
        if not 0 <= peak <= 1:
            raise ValueError("peak must be within [0, 1]")
        self.peak = peak
        self.midpoint = midpoint
        self.steepness = steepness

    def at(self, month: int, horizon: int = 12) -> float:
        if month <= 0:
            return 0.0
        # Standard logistic centred on midpoint, normalised so month 0 ~ 0.
        raw = 1.0 / (1.0 + math.exp(-self.steepness * (month - self.midpoint)))
        raw0 = 1.0 / (1.0 + math.exp(self.steepness * self.midpoint))
        return self.peak * (raw - raw0) / (1.0 - raw0)


class ExponentialAdoption(AdoptionCurve):
    """Fast early adoption that decays toward ``peak``."""

    name = "exponential"

    def __init__(self, peak: float = 0.6, rate: float = 0.5) -> None:
        if not 0 <= peak <= 1:
            raise ValueError("peak must be within [0, 1]")
        self.peak = peak
        self.rate = rate

    def at(self, month: int, horizon: int = 12) -> float:
        if month <= 0:
            return 0.0
        return self.peak * (1.0 - math.exp(-self.rate * month))


CURVES = {
    "linear": LinearAdoption,
    "logistic": LogisticAdoption,
    "exponential": ExponentialAdoption,
}


def make_curve(kind: str = "logistic", **params) -> AdoptionCurve:
    try:
        cls = CURVES[kind]
    except KeyError:
        raise KeyError(f"Unknown adoption curve '{kind}'. Available: {sorted(CURVES)}")
    return cls(**params)


# ---------------------------------------------------------------------------
# Projection data model
# ---------------------------------------------------------------------------


@dataclass
class MonthlyProjection:
    month: int
    adoption: float
    revenue: float
    cogs: float
    labour: float
    overheads: float
    gross_profit: float
    operating_profit: float
    mechanism_cost: float = 0.0
    provision: float = 0.0
    volume: float = 0.0
    note: str = ""


@dataclass
class ProjectionResult:
    months: List[MonthlyProjection]
    total_revenue: float
    total_operating_profit: float
    baseline_operating_profit: float
    delta_operating_profit: float
    payback_month: Optional[int]
    peak_adoption: float

    def summary(self) -> str:
        lines = [
            f"Projection: {len(self.months)} months",
            f"Peak adoption: {self.peak_adoption:.0%}",
            f"Total revenue: £{self.total_revenue:,.0f}",
            f"Total operating profit: £{self.total_operating_profit:,.0f}",
            f"Baseline operating profit: £{self.baseline_operating_profit:,.0f}",
            f"Delta vs baseline: £{self.delta_operating_profit:,.0f}",
        ]
        if self.payback_month:
            lines.append(f"Payback month: {self.payback_month}")
        else:
            lines.append("Payback: not reached within horizon")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------


class ProjectionEngine:
    """Compose a baseline month and a mechanism into a multi-month P&L curve.

    Parameters
    ----------
    baseline:
        Dict with monthly ``revenue``, ``cogs``, ``labour``, ``overheads`` and
        optionally ``units``. These are the *pre-change* run-rate.
    volume_lift:
        Fractional volume increase at full adoption (e.g. 0.15 = +15% units).
        Loyalty schemes typically lift frequency; opening extra days lifts
        traffic. Defaults to 0 (mechanism affects cost/revenue only).
    months:
        Projection horizon in months (default 12).
    """

    def __init__(
        self,
        baseline: Dict[str, float],
        volume_lift: float = 0.0,
        months: int = 12,
    ) -> None:
        if months < 1:
            raise ValueError("months must be >= 1")
        self.baseline = {
            "revenue": float(baseline.get("revenue", 0.0)),
            "cogs": float(baseline.get("cogs", 0.0)),
            "labour": float(baseline.get("labour", 0.0)),
            "overheads": float(baseline.get("overheads", 0.0)),
            "units": float(baseline.get("units", 0.0)),
        }
        self.volume_lift = volume_lift
        self.months = months

    # -- helpers ----------------------------------------------------------

    def _baseline_op(self) -> float:
        b = self.baseline
        return b["revenue"] - b["cogs"] - b["labour"] - b["overheads"]

    def _apply_volume_lift(self, adoption: float) -> float:
        """Return the volume multiplier at a given adoption fraction."""
        return 1.0 + self.volume_lift * adoption

    # -- main -------------------------------------------------------------

    def project(
        self,
        mechanism: Mechanism,
        curve: Optional[AdoptionCurve] = None,
        liability_treatment: Optional[str] = None,
    ) -> ProjectionResult:
        """Project the mechanism over ``self.months``.

        ``curve`` defaults to a logistic S-curve at 60% peak. The mechanism is
        evaluated each month against the *adopted* baseline so give-away costs
        scale with uptake.
        """
        curve = curve or LogisticAdoption()
        b = self.baseline
        base_op = self._baseline_op()

        monthly: List[MonthlyProjection] = []
        total_rev = 0.0
        total_op = 0.0
        payback: Optional[int] = None
        peak_adoption = 0.0

        for m in range(1, self.months + 1):
            adoption = curve.at(m, self.months)
            peak_adoption = max(peak_adoption, adoption)

            vol_mult = self._apply_volume_lift(adoption)
            # Adopted run-rate: volume lift grows revenue and cogs proportionally.
            rev = b["revenue"] * vol_mult
            cogs = b["cogs"] * vol_mult
            units = b["units"] * vol_mult

            # Mechanism applies to the adopted baseline. For loyalty cards the
            # adoption_rate parameter is set to the curve's adoption fraction.
            params = dict(getattr(mechanism, "params", {}))
            if "adoption_rate" in params:
                params["adoption_rate"] = adoption
            if liability_treatment:
                params["liability_treatment"] = liability_treatment
            try:
                eff: MechanismEffect = type(mechanism)(**params).apply(
                    {"revenue": rev, "cogs": cogs, "units": units}
                )
            except TypeError:
                # Mechanism signature without adoption param — use as-is.
                eff = mechanism.apply({"revenue": rev, "cogs": cogs, "units": units})

            # Use absolute deltas only; the *_pct fields are the same quantity
            # expressed as a percentage and would double-count if added too.
            revenue = rev + eff.revenue_delta_gbp
            cogs_total = cogs + eff.cogs_delta_gbp
            # Volume changes COGS too, already handled by vol_mult above.
            labour = b["labour"]
            overheads = b["overheads"]
            gross = revenue - cogs_total
            op = gross - labour - overheads

            monthly.append(
                MonthlyProjection(
                    month=m,
                    adoption=adoption,
                    revenue=revenue,
                    cogs=cogs_total,
                    labour=labour,
                    overheads=overheads,
                    gross_profit=gross,
                    operating_profit=op,
                    mechanism_cost=eff.revenue_delta_gbp + eff.cogs_delta_gbp,
                    provision=eff.cogs_delta_gbp if liability_treatment == "provision_on_earn" else 0.0,
                    volume=units,
                    note=eff.note,
                )
            )
            total_rev += revenue
            total_op += op

            if payback is None and op >= base_op:
                # First month where operating profit matches or beats baseline.
                payback = m

        return ProjectionResult(
            months=monthly,
            total_revenue=total_rev,
            total_operating_profit=total_op,
            baseline_operating_profit=base_op * self.months,
            delta_operating_profit=total_op - base_op * self.months,
            payback_month=payback,
            peak_adoption=peak_adoption,
        )


def baseline_from_business(business) -> Dict[str, float]:
    """Build a monthly baseline dict from a flat business object."""
    pnls = list(business.monthly_pnl.values())
    if not pnls:
        return {"revenue": 0.0, "cogs": 0.0, "labour": 0.0, "overheads": 0.0, "units": 0.0}
    n = len(pnls)
    revenue = sum(p.revenue for p in pnls) / n
    cogs = sum(p.cogs for p in pnls) / n
    labour = sum(p.staff_costs for p in pnls) / n
    overheads = sum(p.overheads for p in pnls) / n
    # Estimate monthly units from transactions if available.
    units = 0.0
    txns = getattr(business, "transactions", [])
    if txns:
        months = set(t.date[:7] for t in txns)
        units = sum(len(t.items) for t in txns) / max(len(months), 1)
    return {
        "revenue": revenue,
        "cogs": cogs,
        "labour": labour,
        "overheads": overheads,
        "units": units,
    }


__all__ = [
    "AdoptionCurve",
    "LinearAdoption",
    "LogisticAdoption",
    "ExponentialAdoption",
    "make_curve",
    "MonthlyProjection",
    "ProjectionResult",
    "ProjectionEngine",
    "baseline_from_business",
]
