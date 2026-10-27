"""Market benchmark and "common sense" layer for scheme design.

The projection engine answers *will this make money*. It cannot answer *will
this look like a decent offer to a customer*. Those are different questions and
a scheme can pass the first while failing the second — a 15+1 card can be
profitable and still feel stingy enough that nobody joins.

This module adds the missing judgement layer:

* ``LoyaltyBenchmark`` — a comparable scheme in the market (stamps required,
  reward type, segment, source).
* ``BenchmarkRegistry`` — a curated set of real-world comparables, queried by
  segment, with percentile ranking.
* ``ReasonablenessScore`` — where a proposed scheme sits against the market
  distribution, plus a plain-English verdict.
* ``CommonSenseRule`` / ``CommonSenseChecker`` — hard-won heuristics that no
  financial model catches (attainability, discount depth, perceived value).

Benchmarks below are encoded from public loyalty-programme terms. They are a
starting reference and should be refreshed against current published terms
before being used for a real commitment.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Benchmark data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LoyaltyBenchmark:
    """A real-world loyalty scheme used as a comparison point.

    ``stamps_required`` is the number of paid purchases needed per reward, so a
    "9 stamps then free" card is ``stamps_required=9`` and its giveaway rate is
    ``1/(9+1)``. ``reward_type`` distinguishes a free item from a discount or
    points scheme, because those are not directly comparable.
    """

    name: str
    segment: str
    stamps_required: int
    reward_type: str = "free_item"
    notes: str = ""
    source: str = "public programme terms"

    @property
    def giveaway_rate(self) -> float:
        """Fraction of units given away, e.g. 9 stamps -> 10.0%."""
        return 1.0 / (self.stamps_required + 1)


class BenchmarkRegistry:
    """Queryable set of loyalty comparables, grouped by segment."""

    def __init__(self, benchmarks: Optional[Sequence[LoyaltyBenchmark]] = None):
        self.benchmarks: List[LoyaltyBenchmark] = list(
            benchmarks if benchmarks is not None else DEFAULT_BENCHMARKS
        )

    def by_segment(self, segment: str, stamp_based_only: bool = False) -> List[LoyaltyBenchmark]:
        seg = segment.lower()
        out = [b for b in self.benchmarks if b.segment.lower() == seg]
        if stamp_based_only:
            out = [b for b in out if b.stamps_required > 0 and b.reward_type == "free_item"]
        return out

    def segments(self) -> List[str]:
        return sorted({b.segment for b in self.benchmarks})

    def stamps_distribution(self, segment: str) -> List[int]:
        """Stamp counts for genuinely stamp-based free-item schemes.

        Subscription and points programmes are excluded: a "0 stamps" scheme
        is not a comparison point for a stamp card.
        """
        return [b.stamps_required for b in self.by_segment(segment, stamp_based_only=True)]

    def median_stamps(self, segment: str) -> Optional[float]:
        d = self.stamps_distribution(segment)
        return statistics.median(d) if d else None

    def percentile_of(self, stamps_required: int, segment: str) -> Optional[float]:
        """Percentile of a proposed stamp count within the segment.

        0th percentile = most generous (fewest stamps). 100th = stingiest.
        """
        d = sorted(self.stamps_distribution(segment))
        if not d:
            return None
        below = sum(1 for x in d if x < stamps_required)
        equal = sum(1 for x in d if x == stamps_required)
        return (below + 0.5 * equal) / len(d) * 100.0

    def best_practice(self, segment: str) -> Optional[LoyaltyBenchmark]:
        d = self.by_segment(segment, stamp_based_only=True)
        if not d:
            return None
        return min(d, key=lambda b: b.stamps_required)


# Encoded from published programme terms. Segment names are free-form; the
# checker matches case-insensitively. Treat these as reference, not gospel.
DEFAULT_BENCHMARKS: List[LoyaltyBenchmark] = [
    # --- Coffee / QSR ---
    LoyaltyBenchmark("Costa Club", "coffee", 8, "free_item",
                     "8 beans, any drink; beans expire after 12 months"),
    LoyaltyBenchmark("Greggs Rewards", "coffee", 9, "free_item",
                     "9 stamps, free hot drink; app-based"),
    LoyaltyBenchmark("Caffe Nero", "coffee", 9, "free_item",
                     "9 stamps, 10th drink free"),
    LoyaltyBenchmark("Starbucks Rewards", "coffee", 15, "points",
                     "150 stars ~ £15 spend; redeem from 25 stars"),
    LoyaltyBenchmark("Pret Subscription", "coffee", 0, "subscription",
                     "~£30/mo unlimited drinks; not stamp-based"),
    LoyaltyBenchmark("Independent coffee (typical)", "coffee", 9, "free_item",
                     "modal indie card in UK is 9+1"),
    LoyaltyBenchmark("Independent coffee (generous)", "coffee", 6, "free_item",
                     "6+1 used by newer entrants to drive sign-up"),
    # --- Bakery / food retail ---
    LoyaltyBenchmark("Greggs (bakery)", "bakery", 9, "free_item",
                     "9 stamps across bakery range"),
    LoyaltyBenchmark("Lidl Plus", "grocery", 0, "points",
                     "digital coupons, no fixed stamp count"),
    LoyaltyBenchmark("Tesco Clubcard", "grocery", 0, "points",
                     "1 point per £1; 150 points = £1.50 voucher"),
    # --- Generic F&B ---
    LoyaltyBenchmark("Subway MyWay", "qsr", 0, "points",
                     "points per £; redeem against any item"),
    LoyaltyBenchmark("Nando's Rewards", "qsr", 0, "points",
                     "points per £ spend, tiered rewards"),
]


# ---------------------------------------------------------------------------
# Reasonableness scoring
# ---------------------------------------------------------------------------


@dataclass
class ReasonablenessScore:
    """Where a proposed scheme sits against the market."""

    segment: str
    stamps_required: int
    giveaway_rate: float
    percentile: Optional[float]
    median_stamps: Optional[float]
    best_practice_stamps: Optional[int]
    verdict: str
    concerns: List[str] = field(default_factory=list)

    def summary(self) -> str:
        pct = f"{self.percentile:.0f}th percentile" if self.percentile is not None else "n/a"
        return (
            f"{self.stamps_required}+1 ({self.giveaway_rate:.1%} giveaway) in "
            f"{self.segment}: {pct} vs market median "
            f"{self.median_stamps} stamps — {self.verdict}"
        )


class ReasonablenessChecker:
    """Judge a proposed stamp scheme against market comparables.

    Thresholds are expressed in percentiles of the segment distribution:

    * <= 25th percentile  -> "generous" (better than three-quarters of market)
    * <= 60th percentile  -> "competitive"
    * <= 80th percentile  -> "stingy" (weaker than most, may suppress sign-up)
    * >  80th percentile  -> "poor" (do not launch; customers will compare)
    """

    GENEROUS = 25.0
    COMPETITIVE = 65.0
    STINGY = 85.0

    def __init__(self, registry: Optional[BenchmarkRegistry] = None):
        self.registry = registry or BenchmarkRegistry()

    def assess(self, stamps_required: int, segment: str = "coffee") -> ReasonablenessScore:
        if stamps_required < 1:
            raise ValueError("stamps_required must be >= 1")
        pct = self.registry.percentile_of(stamps_required, segment)
        med = self.registry.median_stamps(segment)
        best = self.registry.best_practice(segment)
        concerns: List[str] = []

        if pct is None or med is None:
            verdict = "unknown — no comparables for segment"
            concerns.append(f"No stamp-based benchmarks registered for segment '{segment}'.")
        else:
            # Judge against the median scheme, not the raw percentile. The
            # modal scheme (e.g. 9+1 in UK coffee) is the one customers will
            # compare against, so matching it must count as competitive.
            ratio = stamps_required / med
            if ratio <= 0.8:
                verdict = "generous"
            elif ratio <= 1.1:
                verdict = "competitive"
            elif ratio <= 1.5:
                verdict = "stingy"
            else:
                verdict = "poor"

        if verdict in ("stingy", "poor") and best is not None:
            concerns.append(
                f"{stamps_required}+1 is weaker than {best.name} ({best.stamps_required}+1). "
                f"Customers will compare directly."
            )
        if verdict == "poor":
            concerns.append(
                "At this level the offer is unlikely to drive sign-up; the "
                "scheme may cost money and still fail to change behaviour."
            )
        if stamps_required >= 12 and verdict != "generous":
            concerns.append(
                "Long earn period: reward feels distant. Consider a smaller "
                "first-tier reward to keep engagement."
            )

        return ReasonablenessScore(
            segment=segment,
            stamps_required=stamps_required,
            giveaway_rate=1.0 / (stamps_required + 1),
            percentile=pct,
            median_stamps=med,
            best_practice_stamps=best.stamps_required if best else None,
            verdict=verdict,
            concerns=concerns,
        )

    def suggested_max_stamps(self, segment: str = "coffee", margin: float = 10.0) -> Optional[int]:
        """Highest stamp count that stays within the 'competitive' band."""
        d = sorted(self.registry.stamps_distribution(segment))
        if not d:
            return None
        cutoff = d[min(int(len(d) * self.COMPETITIVE / 100.0), len(d) - 1)]
        return cutoff


# ---------------------------------------------------------------------------
# Common sense rules
# ---------------------------------------------------------------------------


@dataclass
class RuleResult:
    rule: str
    passed: bool
    message: str


class CommonSenseRule:
    """A single heuristic. ``check(ctx)`` returns RuleResult."""

    name = "base"

    def check(self, ctx: Dict) -> RuleResult:  # pragma: no cover - abstract
        raise NotImplementedError


class AttainabilityRule(CommonSenseRule):
    """A reward should be reachable within a plausible visit window.

    If a typical customer visits once a fortnight, a 15+1 card takes ~30 weeks.
    That is long enough that most people never reach it, so the scheme reads as
    a discount nobody gets rather than a reward.
    """

    name = "attainability"

    def __init__(self, max_weeks: float = 12.0):
        self.max_weeks = max_weeks

    def check(self, ctx: Dict) -> RuleResult:
        stamps = ctx.get("stamps_required", 0)
        visits_per_week = ctx.get("visits_per_week", 1.0)
        if visits_per_week <= 0:
            return RuleResult(self.name, True, "No visit frequency supplied; skipped.")
        weeks = stamps / visits_per_week
        ok = weeks <= self.max_weeks
        msg = (
            f"{stamps}+1 takes ~{weeks:.0f} weeks at {visits_per_week:.1f} visits/week "
            f"(limit {self.max_weeks:.0f})."
        )
        if not ok:
            msg += " Reward is too distant to motivate repeat visits."
        return RuleResult(self.name, ok, msg)


class DiscountDepthRule(CommonSenseRule):
    """Giveaway must not exceed a safe share of gross margin.

    Giving away 10% of units at 76% gross margin costs ~13% of gross profit.
    Beyond roughly a third of gross margin, the scheme cannot pay for itself
    without unrealistic frequency gains.
    """

    name = "discount_depth"

    def __init__(self, max_margin_share: float = 0.35):
        self.max_margin_share = max_margin_share

    def check(self, ctx: Dict) -> RuleResult:
        stamps = ctx.get("stamps_required", 0)
        margin = ctx.get("gross_margin", 0.0)
        if margin <= 0:
            return RuleResult(self.name, True, "No gross margin supplied; skipped.")
        giveaway = 1.0 / (stamps + 1)
        share = giveaway / margin
        ok = share <= self.max_margin_share
        msg = (
            f"{giveaway:.1%} giveaway consumes {share:.0%} of gross margin "
            f"(limit {self.max_margin_share:.0%})."
        )
        if not ok:
            msg += " Scheme eats too much margin to be self-funding."
        return RuleResult(self.name, ok, msg)


class PerceivedValueRule(CommonSenseRule):
    """The reward must be worth more than the effort of earning it.

    Rule of thumb: the free item's value should be at least ~8% of the total
    spend required to earn it. Below that, customers do not perceive value and
    participation collapses regardless of the maths.
    """

    name = "perceived_value"

    def __init__(self, min_value_ratio: float = 0.08):
        self.min_value_ratio = min_value_ratio

    def check(self, ctx: Dict) -> RuleResult:
        stamps = ctx.get("stamps_required", 0)
        avg_spend = ctx.get("avg_spend", 0.0)
        reward_value = ctx.get("reward_value", 0.0)
        if avg_spend <= 0 or reward_value <= 0:
            return RuleResult(self.name, True, "Spend/reward value not supplied; skipped.")
        total_spend = stamps * avg_spend
        ratio = reward_value / total_spend if total_spend else 0.0
        ok = ratio >= self.min_value_ratio
        msg = (
            f"Reward £{reward_value:.2f} on £{total_spend:.2f} spend = {ratio:.1%} "
            f"(floor {self.min_value_ratio:.0%})."
        )
        if not ok:
            msg += " Reward feels token; raise value or shorten the earn."
        return RuleResult(self.name, ok, msg)


DEFAULT_RULES = [AttainabilityRule(), DiscountDepthRule(), PerceivedValueRule()]


class CommonSenseChecker:
    """Run all heuristic rules and aggregate the verdict."""

    def __init__(self, rules: Optional[Sequence[CommonSenseRule]] = None):
        self.rules = list(rules if rules is not None else DEFAULT_RULES)

    def check(self, ctx: Dict) -> List[RuleResult]:
        return [r.check(ctx) for r in self.rules]

    def passed(self, ctx: Dict) -> bool:
        return all(r.passed for r in self.check(ctx))


__all__ = [
    "LoyaltyBenchmark",
    "BenchmarkRegistry",
    "DEFAULT_BENCHMARKS",
    "ReasonablenessScore",
    "ReasonablenessChecker",
    "RuleResult",
    "CommonSenseRule",
    "AttainabilityRule",
    "DiscountDepthRule",
    "PerceivedValueRule",
    "CommonSenseChecker",
    "DEFAULT_RULES",
]
