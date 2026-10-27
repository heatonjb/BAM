"""Data-gap analyzer for BAM.

The projection and mechanism layers silently assume certain inputs exist. When
they are missing, results are produced anyway — from guesses — with no signal
that an assumption is load-bearing. This module makes those gaps explicit.

Design: each *consumer* (mechanism, projection, benchmark check) declares the
data fields it needs. The analyzer scans the business's data files, resolves
which fields are present, and reports gaps ranked by how much they undermine a
result if absent.

A gap is not an error. It is a flagged assumption. The caller decides whether to
fill it (ask the user, query a system, estimate) or accept the risk.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DataRequirement:
    """One input a consumer needs, and why it matters.

    ``severity``:
      * ``critical`` — result is meaningless without it; do not present output.
      * ``important`` — result shifts materially; flag prominently.
      * ``nice`` — improves confidence only.
    """

    key: str
    description: str
    consumers: Sequence[str]
    severity: str = "important"
    fallback: str = ""


@dataclass
class DataGap:
    """A requirement that could not be satisfied."""

    requirement: DataRequirement
    found_in: Optional[str] = None
    partial: bool = False
    note: str = ""

    @property
    def severity(self) -> str:
        return self.requirement.severity

    def summary(self) -> str:
        status = "partial" if self.partial else "missing"
        where = f" (in {self.found_in})" if self.found_in else ""
        return (
            f"[{self.severity.upper()}] {self.requirement.key} — {status}{where}: "
            f"{self.requirement.description}"
        )


# Requirements keyed by canonical field name. Consumers list which modules read
# the field. Keep this in sync when adding mechanisms or projection inputs.
DEFAULT_REQUIREMENTS: List[DataRequirement] = [
    # --- Core financials (projection baseline) ---
    DataRequirement(
        "revenue", "Monthly revenue or enough transactions to derive it",
        ["projection.baseline_from_business", "feasibility", "benchmark.discount_depth"],
        severity="critical", fallback="derive from transactions",
    ),
    DataRequirement(
        "cogs", "Cost of goods sold over the same period as revenue",
        ["projection", "feasibility", "benchmark.discount_depth"],
        severity="critical", fallback="derive from purchases",
    ),
    DataRequirement(
        "units", "Units sold, for average spend and per-unit economics",
        ["projection", "mechanisms.loyalty_card", "benchmark.discount_depth"],
        severity="critical", fallback="derive from transactions line items",
    ),
    DataRequirement(
        "gross_margin", "Gross margin ratio; drives discount-depth rule",
        ["benchmark.discount_depth", "feasibility"],
        severity="important", fallback="(revenue - cogs) / revenue",
    ),
    # --- Customer behaviour (adoption + attainability) ---
    DataRequirement(
        "visits_per_week", "Customer purchase frequency; drives attainability",
        ["benchmark.attainability", "experiment.design"],
        severity="important", fallback="segment avg_visits_per_month / 4.33",
    ),
    DataRequirement(
        "avg_spend", "Average transaction value; drives perceived-value rule",
        ["benchmark.perceived_value", "mechanisms.loyalty_card"],
        severity="important", fallback="revenue / units",
    ),
    DataRequirement(
        "customer_segments", "Segment mix for weighting average behaviour",
        ["benchmark", "feasibility", "experiment"],
        severity="important", fallback="treat business as one segment",
    ),
    # --- Mechanism-specific ---
    DataRequirement(
        "adoption_rate", "Expected share of customers who take up the offer",
        ["mechanisms.loyalty_card", "projection"],
        severity="critical", fallback="none — must be assumed or tested",
    ),
    DataRequirement(
        "volume_lift", "Expected increase in purchase frequency from the offer",
        ["projection", "feasibility"],
        severity="critical", fallback="none — must be assumed or tested",
    ),
    # --- Benchmark support ---
    DataRequirement(
        "reward_value", "Cost to the business of the free/discounted item",
        ["benchmark.perceived_value", "mechanisms.loyalty_card"],
        severity="important", fallback="menu price or cogs per unit",
    ),
]


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


@dataclass
class GapReport:
    """Result of a gap analysis."""

    business: str
    checked: int
    gaps: List[DataGap] = field(default_factory=list)
    satisfied: List[str] = field(default_factory=list)

    @property
    def critical(self) -> List[DataGap]:
        return [g for g in self.gaps if g.severity == "critical"]

    @property
    def important(self) -> List[DataGap]:
        return [g for g in self.gaps if g.severity == "important"]

    def is_viable(self) -> bool:
        """No critical gaps means projections may be presented."""
        return not self.critical

    def summary(self) -> str:
        lines = [
            f"Data gap report — {self.business}",
            f"Checked {self.checked} requirements: "
            f"{len(self.satisfied)} satisfied, {len(self.gaps)} gaps "
            f"({len(self.critical)} critical).",
        ]
        if self.critical:
            lines.append("\nCRITICAL — fill before trusting any projection:")
            lines += [f"  {g.summary()}" for g in self.critical]
        if self.important:
            lines.append("\nIMPORTANT — material impact on results:")
            lines += [f"  {g.summary()}" for g in self.important]
        nice = [g for g in self.gaps if g.severity == "nice"]
        if nice:
            lines.append("\nNICE TO HAVE:")
            lines += [f"  {g.summary()}" for g in nice]
        return "\n".join(lines)


class DataGapAnalyzer:
    """Scan business data for fields consumers assume exist."""

    def __init__(
        self,
        requirements: Optional[Sequence[DataRequirement]] = None,
        business: str = "business",
    ):
        self.requirements = list(
            requirements if requirements is not None else DEFAULT_REQUIREMENTS
        )
        self.business = business

    # -- field presence checks -------------------------------------------------

    @staticmethod
    def _flatten_keys(obj: Any, prefix: str = "") -> set:
        """Collect dotted key paths from nested dicts/lists."""
        keys: set = set()
        if isinstance(obj, dict):
            for k, v in obj.items():
                path = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
                keys.add(path)
                keys.add(k)
                keys |= DataGapAnalyzer._flatten_keys(v, path)
        elif isinstance(obj, list):
            for item in obj[:5]:  # sample to avoid huge walks
                keys |= DataGapAnalyzer._flatten_keys(item, prefix)
        return keys

    def _scan_sources(self, sources: Dict[str, Any]) -> Dict[str, set]:
        """Map source name -> set of key paths it contains."""
        return {name: self._flatten_keys(payload) for name, payload in sources.items()}

    # -- public API ------------------------------------------------------------

    def analyze(
        self,
        sources: Dict[str, Any],
        requirements: Optional[Sequence[DataRequirement]] = None,
    ) -> GapReport:
        """Analyze a mapping of source-name -> parsed JSON payload.

        ``sources`` might be ``{"transactions": [...], "balance_sheet": {...}}``.
        A requirement is satisfied if its key appears in any source's key set.
        """
        reqs = list(requirements if requirements is not None else self.requirements)
        scanned = self._scan_sources(sources)

        # A requirement is satisfied if its key appears in any source's key set.
        found: Dict[str, List[str]] = {}
        for name, keys in scanned.items():
            for req in reqs:
                if req.key in keys or req.key.replace("_", "") in {k.replace("_", "") for k in keys}:
                    found.setdefault(req.key, []).append(name)

        # Coarse completeness: revenue & units often only exist as derived
        # aggregates rather than literal keys. Treat a source that clearly
        # carries the underlying rows as a partial match.
        partial_hints = {
            "revenue": ("transactions", "bottom_up_pl", "balance_sheet"),
            "cogs": ("cogs_purchases", "transactions", "bottom_up_pl"),
            "units": ("transactions", "menu"),
            "customer_segments": ("customer_segments",),
            "visits_per_week": ("customer_segments", "transactions"),
            "avg_spend": ("transactions", "customer_segments", "menu"),
        }

        gaps: List[DataGap] = []
        satisfied: List[str] = []
        for req in reqs:
            if req.key in found:
                satisfied.append(req.key)
                continue
            # Partial: underlying source present but field name not literal.
            hint = partial_hints.get(req.key)
            hit = next((h for h in (hint or ()) if h in sources), None)
            if hit:
                gaps.append(DataGap(req, found_in=hit, partial=True,
                                    note="underlying source present; field not literal"))
            else:
                gaps.append(DataGap(req, note="no matching source file"))

        # Sort: critical first, then important, then nice.
        order = {"critical": 0, "important": 1, "nice": 2}
        gaps.sort(key=lambda g: order.get(g.severity, 3))
        return GapReport(
            business=self.business,
            checked=len(reqs),
            gaps=gaps,
            satisfied=satisfied,
        )

    def analyze_directory(self, data_dir: str) -> GapReport:
        """Load every .json in ``data_dir`` and analyze the combined set."""
        import os

        sources: Dict[str, Any] = {}
        for fn in sorted(os.listdir(data_dir)):
            if not fn.endswith(".json"):
                continue
            path = os.path.join(data_dir, fn)
            try:
                with open(path, "r", encoding="utf-8") as fh:
                    sources[fn[:-5]] = json.load(fh)
            except (json.JSONDecodeError, OSError):
                sources[fn[:-5]] = {}
        return self.analyze(sources)


__all__ = [
    "DataRequirement",
    "DataGap",
    "GapReport",
    "DataGapAnalyzer",
    "DEFAULT_REQUIREMENTS",
]
