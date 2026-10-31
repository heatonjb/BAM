"""Break-even inversion — a generic BAM capability.

The Monte Carlo engine answers "what is the probability this initiative makes
money?". That is the wrong question when the answer is a flat zero: a single
"0%" tells an operator nothing they can act on. It collapses "this loses money
under every plausible assumption" and "this loses money unless demand responds"
into the same number.

The inverse question is decision-useful:

    What volume response would this need in order to pay for itself?

That threshold is an *input* an operator can argue with. "This needs +17.8%
frequency" is a claim you can test against experience — a café owner knows
whether 18% more transactions is plausible. "0% chance of profit" is a verdict
you can only accept or ignore.

Why this lives in core
----------------------
Break-even inversion is pure arithmetic over a ``Mechanism`` and a baseline.
It knows nothing about cafés, loyalty cards or any tenant's business. It is a
generic capability, so it belongs here rather than in a tenant agent. The
*mechanism* is the tenant's business; the *inversion* is not.

The threshold is not a forecast. It is the point at which the sign of the
outcome flips, reported so a human can judge plausibility. BAM does not know
whether a 17.8% lift is achievable — that is precisely why the number is worth
showing instead of hiding behind a probability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .mechanisms import Mechanism
from .projection import AdoptionCurve, ProjectionEngine

#: Search ceiling for the bisection. A mechanism needing more than a doubling
#: of volume to break even is not a marginal decision, so we report it as
#: out-of-range rather than pretending a precise number is meaningful.
DEFAULT_UPPER_BOUND = 2.0


@dataclass
class BreakEvenResult:
    """The volume response a mechanism needs in order to pay for itself."""

    #: Required increase in volume, as a fraction (0.178 = +17.8%).
    required_lift: Optional[float]
    #: True when the requirement exceeded the search ceiling.
    beyond_bound: bool = False
    #: True when the mechanism already breaks even with no volume response.
    already_profitable: bool = False
    #: Operating-profit delta at zero lift — the cost of the mechanism alone.
    zero_lift_delta: float = 0.0
    months: int = 12
    #: Extra units per month at the threshold, when baseline units are known.
    required_extra_units: Optional[float] = None
    baseline_units: float = 0.0
    #: Human-readable sentence, ready for a UI or an agent envelope.
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "required_lift_pct": (
                None if self.required_lift is None else self.required_lift * 100.0
            ),
            "beyond_bound": self.beyond_bound,
            "already_profitable": self.already_profitable,
            "zero_lift_delta_gbp": round(self.zero_lift_delta, 2),
            "months": self.months,
            "baseline_units": round(self.baseline_units, 2),
            "note": self.note,
        }
        if self.required_extra_units is not None:
            d["required_extra_units_per_month"] = round(self.required_extra_units, 2)
        return d

    def as_statement(self, mechanism_label: str = "this initiative") -> str:
        """One sentence an operator can act on."""
        if self.already_profitable:
            return (
                f"{mechanism_label} breaks even with no volume response "
                f"(£{self.zero_lift_delta:+,.0f} over {self.months} months)."
            )
        if self.beyond_bound:
            return (
                f"{mechanism_label} does not break even within "
                f"+{DEFAULT_UPPER_BOUND:.0%} volume — the economics are not "
                f"marginal, they are structurally unprofitable."
            )
        units = (
            f" ({self.required_extra_units:,.0f} extra units/month)"
            if self.required_extra_units is not None
            else ""
        )
        return (
            f"{mechanism_label} needs +{self.required_lift:.1%} volume over "
            f"{self.months} months to break even{units}."
        )


def _delta_at(
    mechanism: Mechanism,
    baseline: Dict[str, float],
    lift: float,
    months: int,
    curve: Optional[AdoptionCurve],
    liability_treatment: Optional[str],
) -> float:
    engine = ProjectionEngine(baseline, volume_lift=lift, months=months)
    return engine.project(
        mechanism, curve=curve, liability_treatment=liability_treatment
    ).delta_operating_profit


def break_even_lift(
    mechanism: Mechanism,
    baseline: Dict[str, float],
    months: int = 12,
    *,
    curve: Optional[AdoptionCurve] = None,
    liability_treatment: Optional[str] = None,
    upper_bound: float = DEFAULT_UPPER_BOUND,
    tolerance: float = 1e-7,
) -> BreakEvenResult:
    """Solve for the volume lift at which ``mechanism`` stops losing money.

    Bisects on the projection engine's ``volume_lift`` parameter. Assumes the
    delta is monotonically increasing in lift, which holds for give-away and
    discount mechanisms: more volume spreads a fixed cost over more units.

    Returns ``already_profitable`` when the mechanism pays for itself without
    any volume response, and ``beyond_bound`` when it never does within
    ``upper_bound``. Both are reported explicitly rather than being flattened
    into a number that looks precise but means nothing.
    """
    base = {
        "revenue": float(baseline.get("revenue", 0.0)),
        "cogs": float(baseline.get("cogs", 0.0)),
        "labour": float(baseline.get("labour", 0.0)),
        "overheads": float(baseline.get("overheads", 0.0)),
        "units": float(baseline.get("units", 0.0)),
    }
    units = base["units"]

    zero = _delta_at(mechanism, base, 0.0, months, curve, liability_treatment)
    if zero >= 0.0:
        return BreakEvenResult(
            required_lift=0.0,
            already_profitable=True,
            zero_lift_delta=zero,
            months=months,
            required_extra_units=0.0,
            baseline_units=units,
            note="Mechanism is profitable without any volume response.",
        )

    top = _delta_at(mechanism, base, upper_bound, months, curve, liability_treatment)
    if top < 0.0:
        return BreakEvenResult(
            required_lift=None,
            beyond_bound=True,
            zero_lift_delta=zero,
            months=months,
            baseline_units=units,
            note=(
                f"Still loss-making at +{upper_bound:.0%} volume; the ceiling is "
                f"not the answer, the mechanism is."
            ),
        )

    lo, hi = 0.0, upper_bound
    while hi - lo > tolerance:
        mid = (lo + hi) / 2.0
        if _delta_at(mechanism, base, mid, months, curve, liability_treatment) < 0.0:
            lo = mid
        else:
            hi = mid

    extra = hi * units if units > 0 else None
    return BreakEvenResult(
        required_lift=hi,
        zero_lift_delta=zero,
        months=months,
        required_extra_units=extra,
        baseline_units=units,
        note=(
            f"Needs +{hi:.2%} volume over {months} months"
            + (f" ({extra:,.0f} extra units/month)." if extra else ".")
        ),
    )


def clearing_probability(
    break_even: BreakEvenResult,
    lift_draws: list,
) -> Optional[float]:
    """Share of sampled volume responses that reach the break-even threshold.

    Turns "what lift is needed" into "how likely is that", using the same draws
    the Monte Carlo engine already produced. Returns ``None`` when there is no
    threshold to clear (already profitable or out of range) — a probability
    against an undefined bar would be a fabricated number.
    """
    if break_even.required_lift is None or break_even.already_profitable:
        return None
    if not lift_draws:
        return None
    cleared = sum(1 for d in lift_draws if d >= break_even.required_lift)
    return cleared / len(lift_draws)


__all__ = [
    "BreakEvenResult",
    "break_even_lift",
    "clearing_probability",
    "DEFAULT_UPPER_BOUND",
]
