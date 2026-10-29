"""Provider registry: maps external SaaS tools to BAM canonical fields.

Each provider declares:
  - how Nango authenticates it (integration_id = the Nango integration config key)
  - which canonical fields it can supply
  - the API endpoint(s) to pull from (via Nango proxy)
  - how to extract values from the vendor's response shape

Canonical fields come from mvp/multiagent/data_gaps.py:
  revenue, cogs, units, gross_margin, visits_per_week, avg_spend,
  customer_segments, adoption_rate, volume_lift, reward_value

The registry is intentionally declarative: adding a provider means adding a
ProviderSpec here, not writing a new class. The sync engine reads these specs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# ── Extraction helpers ─────────────────────────────────────────────────────
# Each takes the raw JSON from the vendor and returns a float or dict.
# They are defensive: missing keys yield 0.0 rather than raising, so one broken
# endpoint cannot take down a whole sync run.


def _sum_paths(obj: Any, *paths: str) -> float:
    """Sum numeric values found at dotted paths across a list or dict."""
    total = 0.0
    items = obj if isinstance(obj, list) else [obj]
    for item in items:
        for path in paths:
            cur: Any = item
            ok = True
            for part in path.split("."):
                if isinstance(cur, dict) and part in cur:
                    cur = cur[part]
                elif isinstance(cur, list) and part.isdigit() and int(part) < len(cur):
                    cur = cur[int(part)]
                else:
                    ok = False
                    break
            if ok and isinstance(cur, (int, float)):
                total += float(cur)
    return total


def _count(obj: Any, path: Optional[str] = None) -> float:
    if isinstance(obj, list):
        return float(len(obj))
    if path:
        v = _sum_paths(obj, path)
        return v
    return 0.0


# ── Specs ──────────────────────────────────────────────────────────────────

@dataclass
class ProviderSpec:
    """Declarative description of one external provider."""

    id: str                          # Nango integration config key
    label: str
    category: str                    # accounting | payments | analytics | crm | pos | marketing
    fields: List[str]                # canonical fields this provider can supply
    auth: str = "oauth2"
    docs: str = ""

    # Endpoint templates. {since}/{until} are substituted by the sync engine.
    # Each entry: canonical_field -> (method, path, extractor)
    endpoints: Dict[str, tuple] = field(default_factory=dict)

    # Optional per-provider notes surfaced in the UI / logs
    notes: str = ""


def _xero_spec() -> ProviderSpec:
    return ProviderSpec(
        id="xero",
        label="Xero",
        category="accounting",
        fields=["revenue", "cogs", "gross_margin"],
        docs="https://docs.nango.dev/integrations/all/xero",
        notes=(
            "Reports API returns rendered Rows/Cells layout, not typed fields. "
            "Prefer BankTransactions + Invoices and build the GL mapping locally."
        ),
        endpoints={
            # Invoices: ACCPAY/ACCREC with totals
            "revenue": ("GET", "/api.xro/2.0/Invoices", lambda r: _sum_paths(
                r.get("Invoices", []), "Total")),
            # BankTransactions for spend; negative amounts are money out
            "cogs": ("GET", "/api.xro/2.0/BankTransactions", lambda r: abs(_sum_paths(
                [t for t in r.get("BankTransactions", []) if t.get("Total", 0) < 0],
                "Total"))),
        },
    )


def _stripe_spec() -> ProviderSpec:
    return ProviderSpec(
        id="stripe",
        label="Stripe",
        category="payments",
        fields=["revenue", "units", "avg_spend"],
        docs="https://docs.nango.dev/integrations/all/stripe",
        notes="Use invoice.paid / customer.subscription.updated webhooks for near-real-time.",
        endpoints={
            "revenue": ("GET", "/v1/charges", lambda r: _sum_paths(
                [c for c in r.get("data", []) if c.get("paid")], "amount") / 100.0),
            "units": ("GET", "/v1/charges", lambda r: _count(
                [c for c in r.get("data", []) if c.get("paid")])),
            "avg_spend": ("GET", "/v1/charges", lambda r: (
                _sum_paths([c for c in r.get("data", []) if c.get("paid")], "amount") / 100.0
                / max(_count([c for c in r.get("data", []) if c.get("paid")]), 1)
            )),
        },
    )


def _ga4_spec() -> ProviderSpec:
    return ProviderSpec(
        id="google-analytics",
        label="Google Analytics 4",
        category="analytics",
        fields=["visits_per_week", "adoption_rate"],
        docs="https://docs.nango.dev/integrations/all/google-analytics",
        notes=(
            "No webhooks — must poll. 200k core tokens/property/day. "
            "Data can be sampled and lags 24–48h."
        ),
        endpoints={
            "visits_per_week": ("POST", "/v1beta/properties/{property_id}:runReport", None),
        },
    )


def _plausible_spec() -> ProviderSpec:
    return ProviderSpec(
        id="plausible",
        label="Plausible Analytics",
        category="analytics",
        fields=["visits_per_week"],
        docs="https://docs.nango.dev/integrations/all/plausible",
        notes="Cookieless, GDPR-simple. 600 req/hour. POST /api/v2/query.",
        endpoints={
            "visits_per_week": ("POST", "/api/v2/query", lambda r: _sum_paths(
                r.get("results", []), "metrics.0")),
        },
    )


def _hubspot_spec() -> ProviderSpec:
    return ProviderSpec(
        id="hubspot",
        label="HubSpot",
        category="crm",
        fields=["customer_segments", "revenue"],
        docs="https://docs.nango.dev/integrations/all/hubspot",
        notes="100 req/10s per app, 250k/day per account on free/starter.",
        endpoints={
            "customer_segments": ("GET", "/crm/v3/objects/contacts", lambda r: _count(
                r.get("results", []))),
        },
    )


def _shopify_spec() -> ProviderSpec:
    return ProviderSpec(
        id="shopify",
        label="Shopify",
        category="pos",
        fields=["revenue", "units", "avg_spend"],
        docs="https://docs.nango.dev/integrations/all/shopify",
        notes="Leaky bucket ~2 req/s REST, ~50 GraphQL cost points/s. HMAC-verified webhooks.",
        endpoints={
            "revenue": ("GET", "/admin/api/2024-10/orders.json", lambda r: _sum_paths(
                r.get("orders", []), "total_price")),
            "units": ("GET", "/admin/api/2024-10/orders.json", lambda r: _sum_paths(
                [li for o in r.get("orders", []) for li in o.get("line_items", [])], "quantity")),
        },
    )


def _freeagent_spec() -> ProviderSpec:
    return ProviderSpec(
        id="freeagent",
        label="FreeAgent",
        category="accounting",
        fields=["revenue", "cogs", "gross_margin"],
        docs="https://docs.nango.dev/integrations/all/freeagent",
        notes="UK MTD-native. 120/min, 3600/hour, 15 token refreshes/min.",
        endpoints={
            "revenue": ("GET", "/v2/invoices", lambda r: _sum_paths(
                [i for i in r.get("invoices", []) if i.get("status") == "Paid"], "total_value")),
        },
    )


def _quickbooks_spec() -> ProviderSpec:
    return ProviderSpec(
        id="quickbooks",
        label="QuickBooks",
        category="accounting",
        fields=["revenue", "cogs"],
        docs="https://docs.nango.dev/integrations/all/quickbooks",
        endpoints={
            "revenue": ("GET", "/v3/company/{realm_id}/reports/ProfitAndLoss", None),
        },
    )


def _posthog_spec() -> ProviderSpec:
    return ProviderSpec(
        id="posthog",
        label="PostHog",
        category="analytics",
        fields=["adoption_rate", "volume_lift", "visits_per_week"],
        docs="https://docs.nango.dev/integrations/all/posthog",
        endpoints={
            "adoption_rate": ("GET", "/api/projects/{project_id}/insights", lambda r: _count(
                r.get("results", []))),
        },
    )


def _sumup_spec() -> ProviderSpec:
    return ProviderSpec(
        id="sumup",
        label="SumUp",
        category="pos",
        fields=["revenue", "units", "avg_spend"],
        docs="https://docs.nango.dev/integrations/all/sumup",
        endpoints={
            "revenue": ("GET", "/v0.1/me/transactions/history", lambda r: _sum_paths(
                r.get("items", []), "amount")),
        },
    )


def _square_spec() -> ProviderSpec:
    return ProviderSpec(
        id="square",
        label="Square",
        category="pos",
        fields=["revenue", "units", "avg_spend"],
        docs="https://docs.nango.dev/integrations/all/square",
        endpoints={
            "revenue": ("GET", "/v2/payments", lambda r: _sum_paths(
                r.get("payments", []), "amount_money.amount") / 100.0),
        },
    )


def _klaviyo_spec() -> ProviderSpec:
    return ProviderSpec(
        id="klaviyo",
        label="Klaviyo",
        category="marketing",
        fields=["reward_value", "adoption_rate"],
        docs="https://docs.nango.dev/integrations/all/klaviyo",
        endpoints={},
    )


def _mailchimp_spec() -> ProviderSpec:
    return ProviderSpec(
        id="mailchimp",
        label="Mailchimp",
        category="marketing",
        fields=["adoption_rate", "reward_value"],
        docs="https://docs.nango.dev/integrations/all/mailchimp",
        endpoints={
            "adoption_rate": ("GET", "/3.0/lists/{list_id}/members", lambda r: _count(
                r.get("members", []))),
        },
    )


_BUILDERS: Dict[str, Callable[[], ProviderSpec]] = {
    "xero": _xero_spec,
    "stripe": _stripe_spec,
    "ga4": _ga4_spec,
    "plausible": _plausible_spec,
    "hubspot": _hubspot_spec,
    "shopify": _shopify_spec,
    "freeagent": _freeagent_spec,
    "quickbooks": _quickbooks_spec,
    "posthog": _posthog_spec,
    "sumup": _sumup_spec,
    "square": _square_spec,
    "klaviyo": _klaviyo_spec,
    "mailchimp": _mailchimp_spec,
}

_CACHE: Dict[str, ProviderSpec] = {}


def get_spec(provider_id: str) -> Optional[ProviderSpec]:
    if provider_id not in _BUILDERS:
        return None
    if provider_id not in _CACHE:
        _CACHE[provider_id] = _BUILDERS[provider_id]()
    return _CACHE[provider_id]


def all_specs() -> List[ProviderSpec]:
    specs: List[ProviderSpec] = []
    for pid in _BUILDERS:
        spec = get_spec(pid)
        if spec is not None:
            specs.append(spec)
    return specs


def providers_for_field(canonical_field: str) -> List[ProviderSpec]:
    """Which providers can supply a given canonical field."""
    return [s for s in all_specs() if canonical_field in s.fields]


def fields_for_provider(provider_id: str) -> List[str]:
    spec = get_spec(provider_id)
    return list(spec.fields) if spec else []


def coverage_report() -> Dict[str, Any]:
    """Which canonical fields are covered, and by whom. Drives the UI gap panel."""
    from ..multiagent.data_gaps import DEFAULT_REQUIREMENTS

    canonical = [r.key for r in DEFAULT_REQUIREMENTS]
    covered: Dict[str, List[str]] = {}
    for f in canonical:
        covered[f] = [s.id for s in providers_for_field(f)]
    return {
        "canonical_fields": canonical,
        "coverage": covered,
        "uncovered": [f for f, ps in covered.items() if not ps],
        "providers": [s.id for s in all_specs()],
    }
