"""Sync engine: pull canonical fields from Nango and feed the business graph.

Flow:
    provider spec -> Nango proxy -> extractor -> canonical value -> store + graph

The graph update is deliberately *additive*: BAM keeps its existing JSON data as
the baseline. Live values overwrite node.value when a sync succeeds and are
recorded in sync_runs so the UI can show freshness. If a sync fails, the old
value stays and the gap is reported rather than silently zeroed.

Node targeting:
    Each canonical field maps to one or more node IDs per tenant. Mappings are
    declared in NODE_MAP below. A missing mapping is reported, not guessed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .connector import NangoConnector
from .providers import get_spec, all_specs, coverage_report
from . import store

log = logging.getLogger(__name__)

# ── Tenant node mappings ───────────────────────────────────────────────────
# canonical_field -> node_id (or list of node IDs) for that tenant's graph.
# Only fields whose node ID is known are listed; everything else is reported
# as an unmapped gap.

NODE_MAP: Dict[str, Dict[str, List[str]]] = {
    "jonco": {
        "revenue": ["revenue"],
        "cogs": ["cogs"],
        "units": ["units_sold"],
        "gross_margin": ["gross_margin"],
        "visits_per_week": ["footfall"],
        "avg_spend": ["avg_transaction_value"],
    },
    "joncrm": {
        "revenue": ["revenue"],
        "units": ["new_customers"],
        "adoption_rate": ["activation_rate"],
        "visits_per_week": ["website_visits"],
        "customer_segments": ["segments"],
    },
}


def _node_targets(tenant: str, field: str) -> List[str]:
    return NODE_MAP.get(tenant, {}).get(field, [])


# ── Single-field pull ──────────────────────────────────────────────────────

def pull_field(
    tenant: str,
    provider: str,
    field: str,
    connector: Optional[NangoConnector] = None,
    query: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Pull one canonical field and record the result."""
    conn = connector or NangoConnector()
    result = conn.execute("pull_metric", {
        "tenant": tenant, "provider": provider, "field": field, "query": query,
    })

    if result.get("ok"):
        store.record_sync(tenant, provider, field, result.get("value"), "ok")
        targets = _node_targets(tenant, field)
        return {
            "ok": True,
            "field": field,
            "value": result.get("value"),
            "provider": provider,
            "nodes": targets,
            "mapped": bool(targets),
        }

    store.record_sync(tenant, provider, field, None, "error", result.get("error"))
    return {
        "ok": False,
        "field": field,
        "provider": provider,
        "error": result.get("error"),
    }


# ── Full tenant sync ───────────────────────────────────────────────────────

def sync_tenant(
    tenant: str,
    providers: Optional[List[str]] = None,
    connector: Optional[NangoConnector] = None,
) -> Dict[str, Any]:
    """Pull every canonical field available for a tenant's connected providers.

    Providers default to those with a stored connection for the tenant.
    Returns a per-field report so the UI can show what arrived and what didn't.
    """
    conn = connector or NangoConnector()

    # Which providers does this tenant actually have connected?
    connected = [c for c in store.list_connections(tenant=tenant)]
    connected_ids = {c["provider"] for c in connected}

    if providers:
        targets = [p for p in providers if p in connected_ids]
        skipped = [p for p in providers if p not in connected_ids]
    else:
        targets = sorted(connected_ids)
        skipped = []

    if not targets:
        return {
            "ok": False,
            "tenant": tenant,
            "error": "no connected providers — connect one first",
            "skipped": skipped,
        }

    report: Dict[str, Any] = {
        "ok": True,
        "tenant": tenant,
        "providers": {},
        "skipped": skipped,
        "fields_ok": 0,
        "fields_failed": 0,
        "unmapped": [],
    }

    for provider in targets:
        spec = get_spec(provider)
        if spec is None:
            report["providers"][provider] = {"ok": False, "error": "unknown provider"}
            continue

        prov_report: Dict[str, Any] = {"ok": True, "fields": {}}
        for field in spec.endpoints:
            r = pull_field(tenant, provider, field, connector=conn)
            prov_report["fields"][field] = r
            if r.get("ok"):
                report["fields_ok"] += 1
                if not r.get("mapped"):
                    report["unmapped"].append(field)
            else:
                report["fields_failed"] += 1
        report["providers"][provider] = prov_report

    report["coverage"] = coverage_report()
    return report


# ── Scheduler entry point ──────────────────────────────────────────────────

def scheduled_sync_all() -> Dict[str, Any]:
    """Sync every tenant that has connections. Intended for a cron job.

    Idempotency: Nango's proxy handles provider rate limits; this function is
    safe to call repeatedly because store.record_sync appends rather than upserts
    and latest_value() reads the most recent successful row.
    """
    tenants = sorted({c["tenant"] for c in store.list_connections()})
    results: Dict[str, Any] = {}
    for tenant in tenants:
        try:
            results[tenant] = sync_tenant(tenant)
        except Exception as e:  # one tenant must not break the rest
            log.exception("sync failed for %s", tenant)
            results[tenant] = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return {"ok": True, "tenants": results}


def freshness_report(tenant: str) -> Dict[str, Any]:
    """How stale is each canonical field? Drives the UI's data-health panel."""
    fields = set()
    for spec in all_specs():
        fields.update(spec.fields)
    out: Dict[str, Any] = {}
    for f in sorted(fields):
        row = store.latest_value(tenant, f)
        out[f] = {
            "value": row["value"] if row else None,
            "last_sync": row["run_at"] if row else None,
            "provider": row["provider"] if row else None,
            "stale": row is None,
        }
    return out
