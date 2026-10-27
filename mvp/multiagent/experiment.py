"""Experiment design for loyalty-scheme frequency trials.

The projection engine needs a volume-lift input. Rather than guessing, run a
controlled trial and measure it. This module sizes that trial: how long, how
many customers, and what result would count as success.

Uses a two-proportion test for visit conversion (did this customer return
within the window) and a means test for spend. Deliberately conservative:
power 0.80, alpha 0.05, two-sided.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExperimentDesign:
    """A sized A/B test for a loyalty scheme."""

    scheme: str
    baseline_visits_per_week: float
    target_lift: float
    baseline_conversion: float
    alpha: float
    power: float
    per_arm_customers: int
    total_customers: int
    duration_weeks: int
    primary_metric: str
    decision_rule: str

    def summary(self) -> str:
        return (
            f"Experiment: {self.scheme}\n"
            f"Target lift: {self.target_lift:.0%} on {self.primary_metric}\n"
            f"Baseline conversion: {self.baseline_conversion:.1%}\n"
            f"Sample: {self.per_arm_customers:,} per arm "
            f"({self.total_customers:,} total)\n"
            f"Duration: {self.duration_weeks} weeks\n"
            f"Decision rule: {self.decision_rule}"
        )


def _z(p: float) -> float:
    """Inverse normal CDF via rational approximation (Acklam)."""
    if p <= 0 or p >= 1:
        raise ValueError("p must be in (0,1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


def sample_size_two_proportions(
    p1: float, p2: float, alpha: float = 0.05, power: float = 0.80
) -> int:
    """Customers per arm for a two-proportion test."""
    if not (0 < p1 < 1 and 0 < p2 < 1):
        raise ValueError("proportions must be in (0,1)")
    if p1 == p2:
        raise ValueError("proportions must differ")
    z_a = _z(1 - alpha / 2)
    z_b = _z(power)
    pbar = (p1 + p2) / 2
    num = (z_a * math.sqrt(2 * pbar * (1 - pbar)) + z_b * math.sqrt(p1*(1-p1)+p2*(1-p2))) ** 2
    return math.ceil(num / (p2 - p1) ** 2)


def design_loyalty_experiment(
    scheme: str,
    target_lift: float,
    baseline_conversion: float = 0.35,
    baseline_visits_per_week: float = 0.7,
    alpha: float = 0.05,
    power: float = 0.80,
    customers_available: Optional[int] = None,
) -> ExperimentDesign:
    """Size a trial that can detect ``target_lift`` in return-visit rate.

    ``baseline_conversion`` is the share of customers who return within the
    measurement window without a scheme. The trial detects a relative lift on
    that rate.
    """
    p1 = baseline_conversion
    p2 = min(baseline_conversion * (1 + target_lift), 0.99)
    per_arm = sample_size_two_proportions(p1, p2, alpha, power)
    total = per_arm * 2

    # Weeks needed: enough for each customer to earn the card at their visit rate.
    stamps = int(scheme.split("+")[0]) if "+" in scheme else 9
    weeks = math.ceil(stamps / max(baseline_visits_per_week, 0.1))
    weeks = max(weeks, 4)

    rule = (
        f"Launch {scheme} if return-visit rate rises by >= {target_lift:.0%} "
        f"(from {p1:.0%} to {p2:.0%}) with p < {alpha}. "
        f"Stop if lift is < {target_lift/2:.0%} after {weeks} weeks."
    )
    if customers_available and customers_available < total:
        rule += (
            f" Note: only {customers_available:,} customers available vs "
            f"{total:,} needed — extend duration or widen the effect you accept."
        )

    return ExperimentDesign(
        scheme=scheme,
        baseline_visits_per_week=baseline_visits_per_week,
        target_lift=target_lift,
        baseline_conversion=p1,
        alpha=alpha,
        power=power,
        per_arm_customers=per_arm,
        total_customers=total,
        duration_weeks=weeks,
        primary_metric="return-visit rate within earn window",
        decision_rule=rule,
    )


__all__ = ["ExperimentDesign", "sample_size_two_proportions", "design_loyalty_experiment"]
