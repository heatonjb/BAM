"""Mechanism registry for BAM.

A **Mechanism** is an economic primitive that translates a business lever into
quantifiable financial flows. For example "1 free per 9 purchases" is not just
free text — it is a mechanism whose effective give-away rate is 1/(N+1) = 10%.

Mechanisms are referenced by ``Hypothesis.mechanism`` and consumed by the
projection engine to produce time-phased P&L deltas.

Design notes
------------
* ``apply()`` returns a ``MechanismEffect`` describing *monthly* deltas as
  percentages of the baseline plus optional absolute figures.
* Mechanisms are pure: they take a baseline dict and return an effect. They do
  not mutate the graph. The projection engine composes them.
* ``units_affected`` metadata is carried through so the constraint checker can
  price SOFT violations per unit.
"""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class MechanismEffect:
    """Financial deltas produced by a mechanism for a single projection month."""

    revenue_delta_pct: float = 0.0
    cogs_delta_pct: float = 0.0
    volume_delta_pct: float = 0.0
    # Absolute monthly figures, useful when a mechanism cannot be expressed
    # as a clean percentage (e.g. a fixed marketing spend).
    revenue_delta_gbp: float = 0.0
    cogs_delta_gbp: float = 0.0
    # Units affected — consumed by the constraint checker for per-unit pricing.
    units_affected: float = 0.0
    # Accounting treatment hint: "provision_on_earn" | "contingent"
    liability_treatment: str = "provision_on_earn"
    note: str = ""


class Mechanism(abc.ABC):
    """Base class for economic mechanisms."""

    name: str = "base"
    #: Which LeverType this mechanism belongs to (string to avoid import cycles).
    lever_type: str = "other"

    def __init__(self, **params: Any) -> None:
        self.params: Dict[str, Any] = params

    @abc.abstractmethod
    def apply(self, baseline: Dict[str, float]) -> MechanismEffect:
        """Compute the financial effect given baseline metrics.

        Expected baseline keys (all optional, default 0):
            revenue, cogs, units, gross_margin, headcount, hours
        """
        raise NotImplementedError

    def describe(self) -> str:
        return f"{self.name}({self.params})"


class LoyaltyCardMechanism(Mechanism):
    """Buy-N-get-1-free loyalty card.

    A customer who makes ``n_paid`` paid purchases earns 1 free unit. Under full
    participation the give-away fraction of total dispensed units is::

        giveaway_rate = 1 / (n_paid + 1)

    With ``n_paid = 9`` that is 10% of units given away.

    Parameters
    ----------
    n_paid:
        Number of paid purchases required before the free one.
    adoption_rate:
        Fraction of transactions that participate (0..1). Ramps over time via
        the projection engine's adoption curve; passed here per-month.
    liability_treatment:
        ``"provision_on_earn"`` books the unredeemed reward as a P&L provision
        in the month it is earned (default). ``"contingent"`` leaves it off the
        P&L until redeemed.
    """

    name = "loyalty_card"
    lever_type = "retention"

    def __init__(
        self,
        n_paid: int = 9,
        adoption_rate: float = 1.0,
        liability_treatment: str = "provision_on_earn",
    ) -> None:
        if n_paid < 1:
            raise ValueError("n_paid must be >= 1")
        if not 0.0 <= adoption_rate <= 1.0:
            raise ValueError("adoption_rate must be within [0, 1]")
        if liability_treatment not in {"provision_on_earn", "contingent"}:
            raise ValueError(
                "liability_treatment must be 'provision_on_earn' or 'contingent'"
            )
        super().__init__(
            n_paid=n_paid,
            adoption_rate=adoption_rate,
            liability_treatment=liability_treatment,
        )
        self.n_paid = n_paid
        self.adoption_rate = adoption_rate
        self.liability_treatment = liability_treatment

    @property
    def giveaway_rate(self) -> float:
        """Fraction of units given away at full adoption."""
        return 1.0 / (self.n_paid + 1)

    def effective_giveaway_rate(self) -> float:
        """Give-away fraction scaled by current adoption."""
        return self.giveaway_rate * self.adoption_rate

    def apply(self, baseline: Dict[str, float]) -> MechanismEffect:
        revenue = float(baseline.get("revenue", 0.0))
        cogs = float(baseline.get("cogs", 0.0))
        units = float(baseline.get("units", 0.0))

        if units <= 0 or revenue <= 0:
            return MechanismEffect(
                note="No baseline units/revenue — loyalty card has no effect."
            )

        unit_revenue = revenue / units
        unit_cogs = cogs / units if cogs else 0.0

        eff = self.effective_giveaway_rate()
        given_units = eff * units
        revenue_lost = given_units * unit_revenue

        # Conservative model: free units are dispensed from existing demand, so
        # total volume is unchanged and the baseline COGS already covers all
        # dispensed units. The loss is revenue only.
        #
        # Under "provision_on_earn" we additionally accrue the *future* liability
        # of rewards earned but not yet redeemed. We model that as a small
        # provision against the same month's revenue (the reward is an IOU).
        # The provision is the unit COGS of earned-but-unredeemed rewards, which
        # we approximate at the same giveaway rate.
        provision_gbp = 0.0
        if self.liability_treatment == "provision_on_earn":
            provision_gbp = given_units * unit_cogs

        return MechanismEffect(
            revenue_delta_gbp=-revenue_lost,
            cogs_delta_gbp=provision_gbp,
            revenue_delta_pct=(-revenue_lost / revenue) * 100.0,
            cogs_delta_pct=((provision_gbp / cogs) * 100.0) if cogs else 0.0,
            units_affected=given_units,
            liability_treatment=self.liability_treatment,
            note=(
                f"Loyalty card {self.n_paid}+1 at {self.adoption_rate:.0%} adoption: "
                f"{eff:.2%} of units free, revenue -£{revenue_lost:,.0f}, "
                f"provision £{provision_gbp:,.0f} ({self.liability_treatment})."
            ),
        )


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

MECHANISM_REGISTRY: Dict[str, type[Mechanism]] = {}


def register_mechanism(cls: type[Mechanism]) -> type[Mechanism]:
    """Decorator registering a mechanism class by its ``name``."""
    MECHANISM_REGISTRY[cls.name] = cls
    return cls


def get_mechanism(name: str, **params: Any) -> Mechanism:
    """Instantiate a registered mechanism by name."""
    try:
        cls = MECHANISM_REGISTRY[name]
    except KeyError:
        available = ", ".join(sorted(MECHANISM_REGISTRY)) or "(none)"
        raise KeyError(f"Unknown mechanism '{name}'. Available: {available}")
    return cls(**params)


register_mechanism(LoyaltyCardMechanism)


__all__ = [
    "Mechanism",
    "MechanismEffect",
    "LoyaltyCardMechanism",
    "MECHANISM_REGISTRY",
    "register_mechanism",
    "get_mechanism",
]
