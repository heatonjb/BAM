"""Feasibility layer: combine economics with market reasonableness.

The projection engine tells you whether a scheme pays for itself. The
benchmark layer tells you whether anyone would want it. Neither alone is
enough — this module merges them into a single verdict so a scheme that is
profitable but insulting (or generous but ruinous) is caught before launch.

The core entry point is ``assess_scheme``, which returns a ``FeasibilityReport``
with a GO / CONDITIONAL / NO-GO verdict and the reasoning behind it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .benchmark import (
    BenchmarkRegistry,
    CommonSenseChecker,
    ReasonablenessChecker,
    ReasonablenessScore,
    RuleResult,
)
from .mechanisms import LoyaltyCardMechanism
from .projection import (
    AdoptionCurve,
    LogisticAdoption,
    ProjectionEngine,
    ProjectionResult,
    baseline_from_business,
)


@dataclass
class FeasibilityReport:
    """Combined economic and reasonableness verdict for a scheme."""

    scheme: str
    stamps_required: int
    giveaway_rate: float

    # Economics
    projection: ProjectionResult
    break_even_lift: Optional[float]

    # Reasonableness
    reasonableness: ReasonablenessScore
    rules: List[RuleResult]

    verdict: str
    reasons: List[str] = field(default_factory=list)
    recommendation: str = ""

    @property
    def economic_pass(self) -> bool:
        return self.projection.delta_operating_profit > 0

    @property
    def reasonable_pass(self) -> bool:
        return self.reasonableness.verdict in ("generous", "competitive")

    def summary(self) -> str:
        lines = [
            f"Scheme: {self.scheme}",
            f"Giveaway: {self.giveaway_rate:.1%} of units",
            "",
            "--- ECONOMICS ---",
            f"12-month delta vs baseline: £{self.projection.delta_operating_profit:,.0f}",
            f"Payback: month {self.projection.payback_month}" if self.projection.payback_month else "Payback: not within 12 months",
            f"Break-even volume lift needed: {self.break_even_lift:.1%}" if self.break_even_lift is not None else "Break-even lift: not attainable",
            "",
            "--- REASONABLENESS ---",
            self.reasonableness.summary(),
        ]
        for r in self.rules:
            lines.append(f"  [{'PASS' if r.passed else 'FAIL'}] {r.rule}: {r.message}")
        lines += ["", f"VERDICT: {self.verdict}"]
        for reason in self.reasons:
            lines.append(f"  - {reason}")
        if self.recommendation:
            lines.append(f"Recommendation: {self.recommendation}")
        return "\n".join(lines)


class FeasibilityChecker:
    """Merge projection economics with benchmark reasonableness."""

    def __init__(
        self,
        baseline: Dict[str, float],
        segment: str = "coffee",
        registry: Optional[BenchmarkRegistry] = None,
        gross_margin: Optional[float] = None,
        avg_spend: Optional[float] = None,
        reward_value: Optional[float] = None,
        visits_per_week: float = 1.0,
        months: int = 12,
    ):
        self.baseline = baseline
        self.segment = segment
        self.reasonableness_checker = ReasonablenessChecker(registry)
        self.common_sense = CommonSenseChecker()
        self.gross_margin = gross_margin or (
            (baseline["revenue"] - baseline["cogs"]) / baseline["revenue"]
            if baseline.get("revenue")
            else 0.0
        )
        self.avg_spend = avg_spend or 0.0
        self.reward_value = reward_value or 0.0
        self.visits_per_week = visits_per_week
        self.months = months

    # -- economics --------------------------------------------------------

    def _break_even_lift(self, stamps: int, curve: AdoptionCurve) -> Optional[float]:
        """Smallest volume lift at which the scheme breaks even."""
        for lift in [x / 100 for x in range(0, 101, 2)]:
            eng = ProjectionEngine(self.baseline, volume_lift=lift, months=self.months)
            mech = LoyaltyCardMechanism(n_paid=stamps, adoption_rate=0.5)
            res = eng.project(mech, curve)
            if res.delta_operating_profit > 0:
                return lift
        return None

    # -- main -------------------------------------------------------------

    def assess(
        self,
        stamps_required: int,
        scheme_name: Optional[str] = None,
        adoption_peak: float = 0.55,
        adoption_midpoint: float = 3.0,
    ) -> FeasibilityReport:
        scheme = scheme_name or f"{stamps_required}+1 card"
        curve = LogisticAdoption(peak=adoption_peak, midpoint=adoption_midpoint)

        mech = LoyaltyCardMechanism(n_paid=stamps_required, adoption_rate=0.5)
        eng = ProjectionEngine(self.baseline, volume_lift=0.12, months=self.months)
        proj = eng.project(mech, curve)
        bel = self._break_even_lift(stamps_required, curve)

        reason = self.reasonableness_checker.assess(stamps_required, self.segment)
        rules = self.common_sense.check({
            "stamps_required": stamps_required,
            "gross_margin": self.gross_margin,
            "avg_spend": self.avg_spend,
            "reward_value": self.reward_value,
            "visits_per_week": self.visits_per_week,
        })
        rules_pass = all(r.passed for r in rules)

        reasons: List[str] = []
        econ_ok = proj.delta_operating_profit > 0
        reason_ok = reason.verdict in ("generous", "competitive")

        if econ_ok and reason_ok and rules_pass:
            verdict = "GO"
            reasons.append("Pays for itself and is competitive against the market.")
        elif econ_ok and not reason_ok:
            verdict = "NO-GO"
            reasons.append(
                f"Profitable but reads as {reason.verdict} vs market — customers "
                f"will compare and the scheme will under-deliver on sign-up."
            )
        elif not econ_ok and reason_ok:
            verdict = "CONDITIONAL"
            reasons.append(
                "Competitive offer but loses money at modelled frequency gain. "
                f"Needs at least {bel:.0%} volume lift to break even."
                if bel is not None else
                "Competitive offer but loses money and cannot break even at any modelled lift."
            )
        else:
            verdict = "NO-GO"
            reasons.append("Neither profitable nor competitive.")

        if not rules_pass:
            for r in rules:
                if not r.passed:
                    reasons.append(f"{r.rule}: {r.message}")

        recommendation = self._recommend(stamps_required, bel, reason, econ_ok)

        return FeasibilityReport(
            scheme=scheme,
            stamps_required=stamps_required,
            giveaway_rate=1.0 / (stamps_required + 1),
            projection=proj,
            break_even_lift=bel,
            reasonableness=reason,
            rules=rules,
            verdict=verdict,
            reasons=reasons,
            recommendation=recommendation,
        )

    def _recommend(
        self, stamps: int, bel: Optional[float], reason: ReasonablenessScore, econ_ok: bool
    ) -> str:
        med = reason.median_stamps
        med_int = int(round(med)) if med else 9
        if reason.verdict == "poor":
            return (
                f"Do not launch {stamps}+1. Market median is {med_int}+1. "
                f"Test {med_int}+1 or better instead."
            )
        if reason.verdict == "stingy":
            return (
                f"{stamps}+1 is weaker than the {med_int}+1 market median and may "
                f"suppress sign-up. Prefer {med_int}+1 unless frequency data says otherwise."
            )
        if not econ_ok and bel is not None:
            return (
                f"Offer is market-appropriate but needs >= {bel:.0%} volume lift to pay back. "
                f"Run a controlled trial to measure real frequency gain before committing."
            )
        if not econ_ok:
            return "Offer is market-appropriate but does not pay back at plausible frequency gains."
        return "Scheme clears both economics and market reasonableness."

    def sweep(self, candidates: Optional[List[int]] = None) -> List[FeasibilityReport]:
        """Assess a range of stamp counts and return reports ordered by stamps."""
        candidates = candidates or [4, 6, 8, 9, 10, 12, 15, 20]
        return [self.assess(n) for n in candidates]


def assess_loyalty_scheme(
    business,
    stamps_required: int,
    segment: str = "coffee",
    volume_lift: float = 0.12,
    avg_spend: Optional[float] = None,
    reward_value: Optional[float] = None,
    visits_per_week: float = 1.0,
) -> FeasibilityReport:
    """Convenience wrapper: build baseline from a flat business object."""
    baseline = baseline_from_business(business)
    if avg_spend is None and baseline.get("units"):
        avg_spend = baseline["revenue"] / baseline["units"]
    if reward_value is None:
        reward_value = avg_spend or 0.0
    checker = FeasibilityChecker(
        baseline=baseline,
        segment=segment,
        avg_spend=avg_spend,
        reward_value=reward_value,
        visits_per_week=visits_per_week,
    )
    # volume_lift is baked into _break_even_lift's sweep; assess() uses 0.12.
    rep = checker.assess(stamps_required)
    if volume_lift != 0.12:
        eng = ProjectionEngine(baseline, volume_lift=volume_lift, months=checker.months)
        mech = LoyaltyCardMechanism(n_paid=stamps_required, adoption_rate=0.5)
        rep.projection = eng.project(mech, LogisticAdoption(peak=0.55, midpoint=3.0))
    return rep


__all__ = ["FeasibilityReport", "FeasibilityChecker", "assess_loyalty_scheme"]
